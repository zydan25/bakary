from decimal import Decimal

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.party import Party, PartyPrice
from app.models.product import Product
from app.models.role import Role
from app.models.user import User


def make_app_with_owner():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="المالك للاختبار", code="owner", is_system=True)
        product = Product(
            name="روتي",
            code="ROTI",
            unit_label="حبة",
            is_default=True,
            is_active=True,
            default_distributor_price=Decimal("8.00"),
            default_customer_price=Decimal("10.00"),
            shop_price=Decimal("15.00"),
        )
        user = User(full_name="مدير الاختبار", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        db.session.add_all([role, product, user])
        db.session.commit()
    return app


def teardown_database(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def log_in(client):
    response = client.post(
        "/auth/login",
        data={"phone": "+967771234567", "password": "Strong-pass-123"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_distributor_creation_saves_party_specific_price():
    app = make_app_with_owner()
    try:
        client = app.test_client()
        log_in(client)
        with app.app_context():
            product = db.session.scalar(select(Product).where(Product.code == "ROTI"))
            product_id = product.id

        response = client.post(
            "/distributors/?action=new",
            data={
                "name": "موزع التجربة",
                "phone": "777123456",
                "notes": "تجربة واجهة الموزعين",
                "party_id": "",
                f"price_{product_id}": "12.50",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "تم حفظ بيانات الموزع بنجاح" in response.get_data(as_text=True)
        with app.app_context():
            party = db.session.scalar(
                select(Party).where(Party.name == "موزع التجربة", Party.party_type == "distributor")
            )
            assert party is not None
            price = db.session.scalar(
                select(PartyPrice).where(
                    PartyPrice.party_id == party.id,
                    PartyPrice.product_id == product_id,
                )
            )
            assert price is not None
            assert price.unit_price == Decimal("12.50")
            assert price.is_custom is True
    finally:
        teardown_database(app)


def test_party_dialog_is_closed_by_default_and_opens_for_add_action():
    app = make_app_with_owner()
    try:
        client = app.test_client()
        log_in(client)
        default_page = client.get("/customers/")
        assert default_page.status_code == 200
        assert 'data-auto-open="false"' in default_page.get_data(as_text=True)

        new_page = client.get("/customers/?action=new")
        assert new_page.status_code == 200
        assert 'data-auto-open="true"' in new_page.get_data(as_text=True)
    finally:
        teardown_database(app)
