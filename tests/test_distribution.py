from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from app import create_app
from app.extensions import db
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
from app.models.production import BusinessPeriod
from app.models.user import User
from app.services.ledger import create_issue, create_payment
from app.models.finance import CashAccount, CashMovement
from app.models.party import Party, PartyPrice
from app.models.product import Product
from app.models.role import Role
from app.models.user import User


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="اختبار المالك", code="owner", is_system=True)
        user = User(full_name="مدير اختبار", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        product = Product(name="روتي", code="ROTI", unit_label="حبة", is_default=True,
                          is_active=True, default_distributor_price=Decimal("8.00"),
                          default_customer_price=Decimal("10.00"), shop_price=Decimal("15.00"))
        party = Party(party_type="distributor", name="موزع اختبار",
                      phone="+967777654321", is_active=True)
        cash = CashAccount(code="MAIN", name="الصندوق الرئيسي", account_type="cash",
                           is_main=True, is_active=True)
        db.session.add_all([role, user, product, party, cash])
        db.session.flush()
        db.session.add(PartyPrice(party_id=party.id, product_id=product.id,
                                  unit_price=Decimal("8.00"), is_custom=False))
        db.session.commit()
        result = (party.id, product.id)
    return app, result


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post("/auth/login",
        data={"phone": "+967771234567", "password": "Strong-pass-123"},
        follow_redirects=True)
    assert response.status_code == 200


def test_issue_and_collection_create_ledger_and_cash_entries():
    app, (party_id, product_id) = setup()
    try:
        client = app.test_client()
        login(client)
        issue_data = {
            "party_id": str(party_id), "product_id": str(product_id),
            "quantity": "10", "business_date": date.today().isoformat(),
            "statement": "صرف اختبار", "request_key": "issue-test-request-001"
        }
        issue_response = client.post("/distribution/issue/distributor",
                                     data=issue_data, follow_redirects=True)
        assert issue_response.status_code == 200
        assert "إيصال صرف" in issue_response.get_data(as_text=True)
        # The same idempotency key is accepted only once.
        client.post("/distribution/issue/distributor", data=issue_data, follow_redirects=True)
        with app.app_context():
            assert db.session.scalar(select(func.count()).select_from(DistributionIssue)) == 1
            issue = db.session.scalar(select(DistributionIssue))
            assert issue.total_amount == Decimal("80.00")
            assert db.session.scalar(select(PartyLedgerEntry).where(
                PartyLedgerEntry.source_type == "distribution_issue",
                PartyLedgerEntry.source_id == issue.id)) is not None

        payment_response = client.post("/distribution/payment/distributor", data={
            "party_id": str(party_id), "amount": "30.00",
            "business_date": date.today().isoformat(), "statement": "دفعة اختبار",
            "request_key": "payment-test-request-001"
        }, follow_redirects=True)
        assert payment_response.status_code == 200
        assert "إيصال قبض" in payment_response.get_data(as_text=True)
        with app.app_context():
            payment = db.session.scalar(select(PartyPayment))
            assert payment is not None and payment.amount == Decimal("30.00")
            movement = db.session.scalar(select(CashMovement).where(
                CashMovement.source_type == "party_payment",
                CashMovement.source_id == payment.id))
            assert movement is not None and movement.amount == Decimal("30.00")
            assert movement.direction == "in"
    finally:
        cleanup(app)


def test_issue_report_and_statement_render():
    app, (party_id, _product_id) = setup()
    try:
        client = app.test_client()
        login(client)
        report = client.get("/distribution/reports/issues/distributor")
        statement = client.get(f"/distribution/reports/statement/distributor/{party_id}")
        assert report.status_code == 200
        assert "تقرير صرف الموزعين" in report.get_data(as_text=True)
        assert statement.status_code == 200
        assert "كشف حساب موزع اختبار" in statement.get_data(as_text=True)
    finally:
        cleanup(app)


def _open_daily_period_for_test():
    actor = db.session.scalar(select(User).where(User.phone == "+967771234567"))
    period = db.session.scalar(select(BusinessPeriod).where(
        BusinessPeriod.business_date == date.today(),
        BusinessPeriod.period_code == "daily",
    ))
    if period is None:
        period = BusinessPeriod(
            business_date=date.today(),
            period_code="daily",
            status="open",
            opened_by_id=actor.id,
        )
        db.session.add(period)
        db.session.commit()
    return actor.id, period


def test_open_period_issue_can_be_edited_and_deleted_with_ledger():
    app, (party_id, product_id) = setup()
    try:
        with app.app_context():
            actor_id, _period = _open_daily_period_for_test()
            issue, _ = create_issue(
                party_id=party_id, product_id=product_id, quantity=4,
                business_date=date.today(), period_code="daily",
                statement="قبل التعديل", actor_id=actor_id,
                request_key="issue-crud-test-0001",
            )
            issue_id = issue.id
        client = app.test_client()
        login(client)
        listing = client.get("/distribution/issues")
        assert listing.status_code == 200
        assert "قبل التعديل" in listing.get_data(as_text=True)

        edited = client.post(f"/distribution/issues/{issue_id}/edit", data={
            "party_id": str(party_id),
            "product_id": str(product_id),
            "quantity": "7",
            "statement": "بعد التعديل",
        }, follow_redirects=True)
        assert edited.status_code == 200
        with app.app_context():
            issue = db.session.get(DistributionIssue, issue_id)
            ledger = db.session.scalar(select(PartyLedgerEntry).where(
                PartyLedgerEntry.source_type == "distribution_issue",
                PartyLedgerEntry.source_id == issue_id,
            ))
            assert issue.quantity == 7
            assert issue.total_amount == Decimal("56.00")
            assert ledger.debit_amount == Decimal("56.00")
            assert ledger.credit_amount == Decimal("0.00")

        deleted = client.post(f"/distribution/issues/{issue_id}/delete", data={}, follow_redirects=True)
        assert deleted.status_code == 200
        with app.app_context():
            assert db.session.get(DistributionIssue, issue_id) is None
            assert db.session.scalar(select(PartyLedgerEntry).where(
                PartyLedgerEntry.source_type == "distribution_issue",
                PartyLedgerEntry.source_id == issue_id,
            )) is None
    finally:
        cleanup(app)


def test_open_period_payment_edit_and_delete_update_linked_records():
    app, (party_id, _product_id) = setup()
    try:
        with app.app_context():
            actor_id, _period = _open_daily_period_for_test()
            payment, _ = create_payment(
                party_id=party_id, amount="30.00", business_date=date.today(),
                period_code="daily", statement="دفعة قبل التعديل", actor_id=actor_id,
                request_key="payment-crud-test-0001",
            )
            payment_id = payment.id
        client = app.test_client()
        login(client)
        listing = client.get("/distribution/payments")
        assert listing.status_code == 200
        assert "دفعة قبل التعديل" in listing.get_data(as_text=True)

        edited = client.post(f"/distribution/payments/{payment_id}/edit", data={
            "party_id": str(party_id), "amount": "45.50",
            "statement": "دفعة بعد التعديل",
        }, follow_redirects=True)
        assert edited.status_code == 200
        with app.app_context():
            payment = db.session.get(PartyPayment, payment_id)
            ledger = db.session.scalar(select(PartyLedgerEntry).where(
                PartyLedgerEntry.source_type == "party_payment",
                PartyLedgerEntry.source_id == payment_id,
            ))
            movement = db.session.scalar(select(CashMovement).where(
                CashMovement.source_type == "party_payment",
                CashMovement.source_id == payment_id,
            ))
            assert payment.amount == Decimal("45.50")
            assert ledger.credit_amount == Decimal("45.50")
            assert movement.amount == Decimal("45.50")
            assert movement.direction == "in"

        deleted = client.post(f"/distribution/payments/{payment_id}/delete", data={}, follow_redirects=True)
        assert deleted.status_code == 200
        with app.app_context():
            assert db.session.get(PartyPayment, payment_id) is None
            assert db.session.scalar(select(PartyLedgerEntry).where(
                PartyLedgerEntry.source_type == "party_payment",
                PartyLedgerEntry.source_id == payment_id,
            )) is None
            assert db.session.scalar(select(CashMovement).where(
                CashMovement.source_type == "party_payment",
                CashMovement.source_id == payment_id,
            )) is None
    finally:
        cleanup(app)
