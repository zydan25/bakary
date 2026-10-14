from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from app import create_app
from app.extensions import db
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
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
        assert "تقرير صرف الموزعون" in report.get_data(as_text=True)
        assert statement.status_code == 200
        assert "كشف حساب موزع اختبار" in statement.get_data(as_text=True)
    finally:
        cleanup(app)
