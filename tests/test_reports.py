from datetime import date
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.closing import PeriodCloseProduct
from app.models.distribution import DistributionIssue, PartyPayment
from app.models.expense import Expense
from app.models.finance import CashAccount, CashMovement
from app.models.free_distribution import FreeDistribution, FreeRecipient
from app.models.party import Party
from app.models.production import BusinessPeriod, DoughBatch
from app.models.product import Product
from app.models.role import Permission, Role
from app.models.user import User
from app.reports.routes import _safe_csv_cell


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="مالك التقارير", code="owner", is_system=True)
        user = User(full_name="مدير التقارير", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        product = Product(
            name="روتي", code="ROTI", unit_label="حبة", is_default=True,
            is_active=True, default_distributor_price=Decimal("8.00"),
            default_customer_price=Decimal("10.00"), shop_price=Decimal("15.00"),
        )
        party = Party(party_type="distributor", name="موزع التقارير", is_active=True)
        cash = CashAccount(code="MAIN", name="الصندوق الرئيسي", account_type="cash", is_main=True, is_active=True)
        period = BusinessPeriod(business_date=date.today(), period_code="daily", status="closed")
        db.session.add_all([role, user, product, party, cash, period])
        db.session.flush()
        issue = DistributionIssue(
            party_id=party.id, product_id=product.id, quantity=25,
            unit_price=Decimal("8.00"), total_amount=Decimal("200.00"),
            business_date=date.today(), period_code="daily", request_key="report-issue-001",
            created_by_id=user.id,
        )
        payment = PartyPayment(
            party_id=party.id, amount=Decimal("30.00"), business_date=date.today(),
            period_code="daily", request_key="report-payment-001", created_by_id=user.id,
        )
        batch = DoughBatch(
            period_id=period.id, product_id=product.id, produced_quantity=Decimal("100.000"),
            flour_quantity=None, flour_item_id=None, statement="تقرير اختبار",
            idempotency_key="report-batch-001", created_by_id=user.id,
        )
        recipient = FreeRecipient(name="مستفيد تقرير", notes=None, is_active=True, created_by_id=user.id)
        db.session.add_all([issue, payment, batch, recipient])
        db.session.flush()
        db.session.add_all([
            FreeDistribution(
                period_id=period.id, recipient_id=recipient.id, product_id=product.id,
                quantity=Decimal("5.000"), statement="صرف مجاني", created_by_id=user.id,
            ),
            PeriodCloseProduct(
                period_id=period.id, product_id=product.id,
                opening_quantity=Decimal("0.000"), produced_quantity=Decimal("100.000"),
                paid_distribution_quantity=Decimal("0.000"), free_distribution_quantity=Decimal("5.000"),
                damaged_quantity=Decimal("2.000"), carried_quantity=Decimal("3.000"),
                shop_sale_quantity=Decimal("90.000"), shop_unit_price=Decimal("15.00"),
                expected_shop_sales=Decimal("1350.00"), created_by_id=user.id,
            ),
            CashMovement(
                cash_account_id=cash.id, movement_type="test_in", direction="in",
                amount=Decimal("1300.00"), business_date=date.today(), statement="قبض للتقرير",
                source_type="report_test_in", source_id=1, created_by_id=user.id,
            ),
            CashMovement(
                cash_account_id=cash.id, movement_type="test_out", direction="out",
                amount=Decimal("100.00"), business_date=date.today(), statement="خرجيات للتقرير",
                source_type="report_test_out", source_id=1, created_by_id=user.id,
            ),
            Expense(
                title="خرجيات التقرير", amount=Decimal("100.00"), cash_account_id=cash.id,
                business_date=date.today(), statement="مصروف اختبار", created_by_id=user.id,
            ),
        ])
        db.session.commit()
    return app


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post("/auth/login", data={
        "phone": "+967771234567", "password": "Strong-pass-123",
    }, follow_redirects=True)
    assert response.status_code == 200


def test_report_center_aggregates_daily_business_data():
    app = setup()
    try:
        client = app.test_client()
        login(client)
        response = client.get("/reports/")
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "private, no-store"
        page = response.get_data(as_text=True)
        assert "مركز التقارير" in page
        assert "200.00" in page
        assert "30.00" in page
        assert "100.000" in page
        assert "1,350.00" in page
        assert "1,300.00" in page
        assert "مخزون" in page
        export_response = client.get("/reports/export.csv")
        assert export_response.status_code == 200
        assert "text/csv" in export_response.content_type
        assert export_response.data.startswith(bytes((239, 187, 191)))
        assert "القيمة".encode("utf-8") in export_response.data
        assert export_response.headers.get("Cache-Control") == "private, no-store"
        assert _safe_csv_cell("=1+1") == "'=1+1"
        assert _safe_csv_cell("@SUM(A1:A2)") == "'@SUM(A1:A2)"
        assert _safe_csv_cell("موزع طبيعي") == "موزع طبيعي"
    finally:
        cleanup(app)


def test_report_center_requires_authentication():
    app = setup()
    try:
        assert app.test_client().get("/reports/").status_code == 302
    finally:
        cleanup(app)



def test_report_viewer_cannot_export_without_export_permission():
    app = setup()
    try:
        with app.app_context():
            viewer_role = Role(name="قارئ تقارير", code="reports_reader", is_system=False)
            view_permission = Permission(
                name="عرض التقارير", code="reports.view", description="عرض ملخصات مسموحة"
            )
            dashboard_permission = Permission(
                name="عرض الرئيسية", code="dashboard.view", description="عرض الرئيسية"
            )
            viewer_role.permissions.extend([view_permission, dashboard_permission])
            viewer = User(full_name="قارئ", phone="+967771234568", is_active=True)
            viewer.set_password("Reader-pass-123")
            viewer.roles.append(viewer_role)
            db.session.add_all([viewer_role, view_permission, dashboard_permission, viewer])
            db.session.commit()

        client = app.test_client()
        response = client.post("/auth/login", data={
            "phone": "+967771234568", "password": "Reader-pass-123",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert client.get("/reports/").status_code == 200
        assert client.get("/reports/export.csv").status_code == 403
    finally:
        cleanup(app)
