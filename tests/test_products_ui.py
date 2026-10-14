from decimal import Decimal

from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models.product import Product
from app.models.role import Role
from app.models.user import User


def setup_product_ui():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="مالك واجهة الأصناف", code="owner", is_system=True)
        user = User(full_name="مدير الاختبار", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        roti = Product(
            name="روتي",
            code="ROTI",
            unit_label="حبة",
            is_default=True,
            is_active=True,
            default_distributor_price=Decimal("8.00"),
            default_customer_price=Decimal("10.00"),
            shop_price=Decimal("15.00"),
        )
        bread = Product(
            name="خبز خاص",
            code="BREAD-TEST",
            unit_label="ربطة",
            is_default=False,
            is_active=True,
            default_distributor_price=Decimal("20.00"),
            default_customer_price=Decimal("22.00"),
            shop_price=Decimal("25.00"),
        )
        db.session.add_all([role, user, roti, bread])
        db.session.commit()
        ids = (roti.id, bread.id)
    return app, ids


def teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post(
        "/auth/login",
        data={"phone": "+967771234567", "password": "Strong-pass-123"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_product_detail_report_and_dedicated_edit_page_work():
    app, (product_id, _unused_product_id) = setup_product_ui()
    try:
        client = app.test_client()
        login(client)

        detail = client.get(f"/products/{product_id}")
        assert detail.status_code == 200
        assert "تقرير الأسعار وحركات الصرف" in detail.get_data(as_text=True)
        assert "سعر الموزع العام" in detail.get_data(as_text=True)

        edit_page = client.get(f"/products/{product_id}/edit")
        assert edit_page.status_code == 200
        assert "تعديل الصنف" in edit_page.get_data(as_text=True)

        updated = client.post(
            f"/products/{product_id}/edit",
            data={
                "product_id": str(product_id),
                "name": "روتي محسن",
                "code": "ROTI",
                "unit_label": "حبة",
                "default_distributor_price": "9.50",
                "default_customer_price": "11.50",
                "shop_price": "16.00",
                "is_default": "y",
            },
            follow_redirects=True,
        )
        assert updated.status_code == 200
        assert "روتي محسن" in updated.get_data(as_text=True)

        with app.app_context():
            saved = db.session.get(Product, product_id)
            assert saved is not None
            assert saved.default_distributor_price == Decimal("9.50")
    finally:
        teardown(app)


def test_product_without_history_can_be_deleted_permanently():
    app, (_default_product_id, delete_product_id) = setup_product_ui()
    try:
        client = app.test_client()
        login(client)
        response = client.post(
            f"/products/{delete_product_id}/delete",
            data={},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "تم حذف الصنف" in response.get_data(as_text=True)
        with app.app_context():
            assert db.session.get(Product, delete_product_id) is None
            assert db.session.scalar(select(func.count()).select_from(Product)) == 1
    finally:
        teardown(app)
