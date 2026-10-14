from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, func, case

from app import create_app
from app.extensions import db
from app.models.closing import PeriodCloseProduct, PeriodHandover
from app.models.employee import Employee
from app.models.expense import Expense
from app.models.finance import CashAccount, CashMovement
from app.models.free_distribution import FreeDistribution, FreeRecipient
from app.models.production import BusinessPeriod
from app.models.product import Product
from app.models.role import Permission, Role
from app.models.user import User
from app.services.closing import ClosingRuleError, close_period_with_handover
from app.services.production import create_dough_batch


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        owner_role = Role(name="المالك للإقفال", code="owner", is_system=True)
        receiver_role = Role(name="المستلم", code="receiver", is_system=True)
        handover_permission = Permission(
            name="تسجيل التسليمات", code="handover.manage", description="تسليم الفترة"
        )
        dashboard_permission = Permission(
            name="عرض الرئيسية", code="dashboard.view", description="عرض لوحة التحكم"
        )
        receiver_role.permissions.extend([handover_permission, dashboard_permission])
        owner = User(full_name="مدير المخبز", phone="+967771234567", is_active=True)
        owner.set_password("Strong-pass-123")
        owner.roles.append(owner_role)
        receiver = User(full_name="المستلم", phone="+967777111222", is_active=True)
        receiver.set_password("Receiver-pass-123")
        receiver.roles.append(receiver_role)
        product = Product(
            name="روتي", code="ROTI", unit_label="حبة", is_default=True,
            is_active=True, default_distributor_price=Decimal("8.00"),
            default_customer_price=Decimal("10.00"), shop_price=Decimal("15.00")
        )
        cash = CashAccount(code="MAIN", name="الصندوق الرئيسي", account_type="cash", is_main=True, is_active=True)
        employee = Employee(full_name="مسؤول البيع", phone="+967777123456", job_title="مستلم", is_active=True, created_by_id=1)
        db.session.add_all([owner_role, receiver_role, handover_permission, dashboard_permission, owner, receiver, product, cash, employee])
        db.session.commit()
        ids = (owner.id, product.id, employee.id)
    return app, ids


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_close_calculates_sales_and_records_handover_expense_and_cash():
    app, (actor_id, product_id, employee_id) = setup()
    try:
        with app.app_context():
            batch, created = create_dough_batch(
                product_id=product_id,
                produced_quantity="100",
                business_date=date.today(),
                period_code="daily",
                actor_id=actor_id,
                statement="إنتاج تجريبي",
                idempotency_key="close-test-dough-001",
            )
            assert created
            period = db.session.get(BusinessPeriod, batch.period_id)
            recipient = FreeRecipient(name="مستفيد", notes=None, is_active=True, created_by_id=actor_id)
            db.session.add(recipient)
            db.session.flush()
            db.session.add(FreeDistribution(
                period_id=period.id, recipient_id=recipient.id, product_id=product_id,
                quantity=Decimal("5.000"), statement="صرف مجاني", created_by_id=actor_id,
            ))
            db.session.commit()

            handover, rows, expected = close_period_with_handover(
                period_id=period.id,
                employee_id=employee_id,
                received_amount="1300.00",
                expenses_amount="100.00",
                handed_to_cash_amount="1200.00",
                damaged_quantities={product_id: "2"},
                carried_quantities={product_id: "3"},
                statement="تسليم اختبار",
                actor_id=actor_id,
            )
            assert expected == Decimal("1350.00")
            assert handover.cash_difference == Decimal("50.00")
            assert handover.handed_to_cash_amount == Decimal("1200.00")
            assert rows[0]["shop_sale_quantity"] == Decimal("90.000")
            saved = db.session.scalar(select(PeriodCloseProduct).where(PeriodCloseProduct.period_id == period.id))
            assert saved is not None
            assert saved.carried_quantity == Decimal("3.000")
            assert saved.expected_shop_sales == Decimal("1350.00")
            assert db.session.scalar(select(Expense).where(Expense.period_id == period.id)) is not None
            net_cash = db.session.execute(select(func.coalesce(func.sum(case(
                (CashMovement.direction == "in", CashMovement.amount),
                else_=-CashMovement.amount,
            )), 0)).where(CashMovement.cash_account_id == 1)).scalar_one()
            assert Decimal(str(net_cash)) == Decimal("1200.00")
            assert db.session.get(BusinessPeriod, period.id).status == "closed"
            with pytest.raises(ClosingRuleError):
                close_period_with_handover(
                    period_id=period.id, employee_id=employee_id,
                    received_amount="1300.00", expenses_amount="100.00",
                    handed_to_cash_amount="1200.00",
                    damaged_quantities={product_id: 0}, carried_quantities={product_id: 0},
                    actor_id=actor_id,
                )
    finally:
        cleanup(app)


def test_free_distribution_and_closing_screens_render_for_owner():
    app, _ids = setup()
    try:
        client = app.test_client()
        response = client.post("/auth/login", data={
            "phone": "+967771234567", "password": "Strong-pass-123"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert client.get("/operations/free-distribution/").status_code == 200
        assert client.get("/operations/closing/").status_code == 200
    finally:
        cleanup(app)



def test_receiver_role_can_open_handover_without_production_edit_permission():
    app, _ids = setup()
    try:
        client = app.test_client()
        response = client.post("/auth/login", data={
            "phone": "+967777111222", "password": "Receiver-pass-123"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert client.get("/operations/closing/").status_code == 200
        assert client.get("/production/").status_code == 403
    finally:
        cleanup(app)
