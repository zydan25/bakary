from datetime import date, timedelta
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
from app.models.inventory import InventoryItem, InventoryMovement
from app.models.closing import PeriodRawMaterialClose
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


def test_free_recipient_form_requires_quantity_and_saves_daily_target():
    app, (actor_id, product_id, _employee_id) = setup()
    try:
        client = app.test_client()
        response = client.post("/auth/login", data={
            "phone": "+967771234567", "password": "Strong-pass-123"
        }, follow_redirects=True)
        assert response.status_code == 200

        bad = client.post("/operations/free-recipients/", data={
            "name": "مستفيد كمية ناقصة",
            "product_id": str(product_id),
            "business_date": date.today().isoformat(),
            "period_code": "daily",
        }, follow_redirects=True)
        assert bad.status_code == 200
        assert "أدخل الكمية المصروفة" in bad.get_data(as_text=True)

        created = client.post("/operations/free-recipients/", data={
            "name": "مستفيد جديد",
            "product_id": str(product_id),
            "quantity": "7.500",
            "business_date": date.today().isoformat(),
            "period_code": "daily",
            "notes": "صرف أولي",
        }, follow_redirects=True)
        assert created.status_code == 200
        with app.app_context():
            recipient = db.session.scalar(select(FreeRecipient).where(FreeRecipient.name == "مستفيد جديد"))
            assert recipient is not None
            assert recipient.default_product_id == product_id
            assert recipient.daily_quantity == Decimal("7.500")
            issue = db.session.scalar(select(FreeDistribution).where(FreeDistribution.recipient_id == recipient.id))
            assert issue is None
    finally:
        cleanup(app)


def test_period_close_records_raw_material_opening_and_calculated_consumption():
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
                idempotency_key="raw-close-dough-001",
            )
            assert created
            period = db.session.get(BusinessPeriod, batch.period_id)
            material = InventoryItem(
                name="دقيق الإقفال",
                code="FLOUR-CLOSE-TEST",
                unit_label="كجم",
                is_active=True,
                reorder_level=Decimal("1.000"),
                created_by_id=actor_id,
            )
            db.session.add(material)
            db.session.flush()
            db.session.add(InventoryMovement(
                item_id=material.id,
                movement_type="opening_balance",
                direction="in",
                quantity=Decimal("100.000"),
                business_date=date.today() - timedelta(days=1),
                source_type="raw_close_test_opening",
                source_id=material.id,
                statement="رصيد افتتاحي للاختبار",
                created_by_id=actor_id,
            ))
            db.session.commit()

            _handover, _rows, _expected = close_period_with_handover(
                period_id=period.id,
                employee_id=employee_id,
                received_amount="1500.00",
                expenses_amount="0.00",
                handed_to_cash_amount="1500.00",
                damaged_quantities={product_id: "0"},
                carried_quantities={product_id: "0"},
                raw_material_endings={material.id: "80.000"},
                statement="إقفال مع جرد مواد خام",
                actor_id=actor_id,
            )
            saved = db.session.scalar(select(PeriodRawMaterialClose).where(
                PeriodRawMaterialClose.period_id == period.id,
                PeriodRawMaterialClose.item_id == material.id,
            ))
            assert saved is not None
            assert saved.opening_quantity == Decimal("100.000")
            assert saved.incoming_quantity == Decimal("0.000")
            assert saved.calculated_consumption == Decimal("20.000")
            assert saved.ending_quantity == Decimal("80.000")
            material_consumption = db.session.scalar(select(InventoryMovement).where(
                InventoryMovement.item_id == material.id,
                InventoryMovement.source_type == "period_raw_material_close",
                InventoryMovement.source_id == period.id,
            ))
            assert material_consumption is not None
            assert material_consumption.direction == "out"
            assert material_consumption.quantity == Decimal("20.000")
    finally:
        cleanup(app)


def test_free_recipient_profile_edit_delete_and_period_reports_render():
    app, (actor_id, product_id, _employee_id) = setup()
    try:
        client = app.test_client()
        login = client.post("/auth/login", data={
            "phone": "+967771234567", "password": "Strong-pass-123"
        }, follow_redirects=True)
        assert login.status_code == 200

        with app.app_context():
            recipient = FreeRecipient(
                name="مستفيد ملف",
                notes="ملاحظة أولى",
                default_product_id=product_id,
                daily_quantity=Decimal("6.000"),
                is_active=True,
                created_by_id=actor_id,
            )
            db.session.add(recipient)
            db.session.commit()
            recipient_id = recipient.id

        profile = client.get(f"/operations/free-recipients/{recipient_id}")
        assert profile.status_code == 200
        assert "مستفيد ملف" in profile.get_data(as_text=True)

        edited = client.post(f"/operations/free-recipients/{recipient_id}/edit", data={
            "name": "مستفيد محدث",
            "product_id": str(product_id),
            "quantity": "8.000",
            "notes": "ملاحظة محدثة",
        }, follow_redirects=True)
        assert edited.status_code == 200
        assert "مستفيد محدث" in edited.get_data(as_text=True)
        with app.app_context():
            saved = db.session.get(FreeRecipient, recipient_id)
            assert saved.name == "مستفيد محدث"
            assert saved.daily_quantity == Decimal("8.000")

        periods = client.get("/operations/periods/")
        assert periods.status_code == 200
        assert "تقرير الأيام والفترات" in periods.get_data(as_text=True)

        with app.app_context():
            period = db.session.scalar(select(BusinessPeriod).where(
                BusinessPeriod.business_date == date.today(), BusinessPeriod.period_code == "daily"
            ))
            period_id = period.id if period else None
        if period_id:
            period_page = client.get(f"/operations/periods/{period_id}")
            assert period_page.status_code == 200
            assert "افتتاح الفترة" in period_page.get_data(as_text=True)

        deleted = client.post(f"/operations/free-recipients/{recipient_id}/delete", data={}, follow_redirects=True)
        assert deleted.status_code == 200
        with app.app_context():
            assert db.session.get(FreeRecipient, recipient_id) is None
    finally:
        cleanup(app)
