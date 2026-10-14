from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select

from app import create_app
from app.extensions import db
from app.models.expense import CashTransfer, Expense
from app.models.finance import CashAccount, CashMovement
from app.models.role import Role
from app.models.user import User
from app.services.finance import (
    cash_account_balance,
    create_cash_account,
    create_cash_transfer,
    create_expense,
)


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="مالك المالية", code="owner", is_system=True)
        user = User(full_name="مدير المالية", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        main = CashAccount(
            code="MAIN", name="الصندوق الرئيسي", account_type="cash",
            is_main=True, is_active=True,
        )
        db.session.add_all([role, user, main])
        db.session.flush()
        db.session.add(CashMovement(
            cash_account_id=main.id, movement_type="opening_balance",
            direction="in", amount=Decimal("500.00"), business_date=date.today(),
            statement="رصيد افتتاحي للاختبار", source_type="test_opening_cash",
            source_id=1, created_by_id=user.id,
        ))
        db.session.commit()
        ids = (user.id, main.id)
    return app, ids


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post("/auth/login", data={
        "phone": "+967771234567", "password": "Strong-pass-123"
    }, follow_redirects=True)
    assert response.status_code == 200


def test_expense_is_atomic_and_idempotent():
    app, (actor_id, main_id) = setup()
    try:
        with app.app_context():
            first, created = create_expense(
                title="شراء وقود", amount="75.00", cash_account_id=main_id,
                business_date=date.today(), statement="رحلة التوزيع",
                actor_id=actor_id, request_key="expense-request-001",
            )
            assert created is True
            repeated, created_again = create_expense(
                title="شراء وقود", amount="75.00", cash_account_id=main_id,
                business_date=date.today(), statement="رحلة التوزيع",
                actor_id=actor_id, request_key="expense-request-001",
            )
            assert repeated.id == first.id
            assert created_again is False
            assert cash_account_balance(main_id) == Decimal("425.00")
            assert db.session.scalar(select(func.count()).select_from(Expense)) == 1
            assert db.session.scalar(select(func.count()).select_from(CashMovement).where(
                CashMovement.source_type == "expense",
                CashMovement.source_id == first.id,
            )) == 1
    finally:
        cleanup(app)


def test_internal_transfer_posts_both_sides_once():
    app, (actor_id, main_id) = setup()
    try:
        with app.app_context():
            target = create_cash_account(
                name="حساب البيت", code="HOME", account_type="cash",
                opening_balance="25.00", actor_id=actor_id
            )
            transfer, created = create_cash_transfer(
                source_account_id=main_id, target_account_id=target.id,
                amount="120.00", business_date=date.today(),
                statement="تحويل شخصي", actor_id=actor_id,
                request_key="transfer-request-001",
            )
            assert created is True
            again, repeated = create_cash_transfer(
                source_account_id=main_id, target_account_id=target.id,
                amount="120.00", business_date=date.today(),
                statement="تحويل شخصي", actor_id=actor_id,
                request_key="transfer-request-001",
            )
            assert again.id == transfer.id
            assert repeated is False
            assert cash_account_balance(main_id) == Decimal("380.00")
            assert cash_account_balance(target.id) == Decimal("145.00")
            opening_movement = db.session.scalar(select(CashMovement).where(
                CashMovement.source_type == "cash_account_opening",
                CashMovement.source_id == target.id,
            ))
            assert opening_movement is not None
            assert opening_movement.amount == Decimal("25.00")
            assert db.session.scalar(select(func.count()).select_from(CashTransfer)) == 1
            sides = db.session.scalars(select(CashMovement).where(
                CashMovement.source_id == transfer.id,
                CashMovement.source_type.in_(["cash_transfer_in", "cash_transfer_out"]),
            )).all()
            assert len(sides) == 2
    finally:
        cleanup(app)


def test_finance_pages_render_and_require_login():
    app, _ids = setup()
    try:
        client = app.test_client()
        assert client.get("/finance/").status_code == 302
        login(client)
        assert client.get("/finance/").status_code == 200
        assert client.get("/finance/expenses/").status_code == 200
        assert client.get("/finance/transfers/").status_code == 200
    finally:
        cleanup(app)
