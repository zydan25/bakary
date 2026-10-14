from decimal import Decimal
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.product import Product
from app.models.role import Role
from app.models.setting import Setting
from app.models.user import User


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        owner_role = Role(name="مالك الإعدادات", code="owner", is_system=True)
        owner = User(full_name="مدير", phone="+967771234567", is_active=True)
        owner.set_password("Strong-pass-123")
        owner.roles.append(owner_role)
        bread = Product(
            name="روتي", code="ROTI", unit_label="حبة", is_default=True, is_active=True,
            default_distributor_price=Decimal("8.00"),
            default_customer_price=Decimal("10.00"), shop_price=Decimal("15.00"),
        )
        bun = Product(
            name="كعك", code="BUN", unit_label="حبة", is_default=False, is_active=True,
            default_distributor_price=Decimal("9.00"),
            default_customer_price=Decimal("12.00"), shop_price=Decimal("18.00"),
        )
        db.session.add_all([owner_role, owner, bread, bun])
        db.session.commit()
        ids = (bread.id, bun.id)
    return app, ids


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post("/auth/login", data={
        "phone": "+967771234567", "password": "Strong-pass-123",
    }, follow_redirects=True)
    assert response.status_code == 200


def test_settings_can_update_default_product_and_operating_period():
    app, (bread_id, bun_id) = setup()
    try:
        client = app.test_client()
        login(client)
        page = client.get("/settings/")
        assert page.status_code == 200
        assert "إعدادات المخبز" in page.get_data(as_text=True)
        response = client.post("/settings/", data={
            "business_name": "مخبز التجربة",
            "default_product_id": str(bun_id),
            "operating_period_mode": "morning_evening",
        }, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            bread = db.session.get(Product, bread_id)
            bun = db.session.get(Product, bun_id)
            assert bread.is_default is False
            assert bun.is_default is True
            assert db.session.scalar(select(Setting).where(Setting.key == "business_name")).value == "مخبز التجربة"
            assert db.session.scalar(select(Setting).where(Setting.key == "default_product_id")).value == bun_id
            assert db.session.scalar(select(Setting).where(Setting.key == "operating_period_mode")).value == "morning_evening"
    finally:
        cleanup(app)


def test_settings_page_requires_login():
    app, _ids = setup()
    try:
        assert app.test_client().get("/settings/").status_code == 302
    finally:
        cleanup(app)


def test_quick_action_visibility_is_saved_and_applied_to_dashboard():
    app, _ids = setup()
    try:
        client = app.test_client()
        login(client)

        settings_page = client.get("/settings/")
        assert settings_page.status_code == 200
        assert "تخصيص أزرار الرئيسية" in settings_page.get_data(as_text=True)
        assert 'name="action_label_0"' in settings_page.get_data(as_text=True)
        assert 'id="add-dashboard-shortcut"' in settings_page.get_data(as_text=True)

        response = client.post("/settings/", data={
            "action": "save_quick_actions",
            "action_label_0": "صرف عميل مخصص",
            "action_url_0": "/distribution/payment/customer",
            "action_enabled_0": "1",
            "action_label_1": "اختصار مخفي",
            "action_url_1": "/auth/account",
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            saved = db.session.scalar(
                select(Setting).where(Setting.key == "dashboard_quick_actions")
            )
            assert saved is not None
            assert saved.value == [
                {"label": "صرف عميل مخصص", "url": "/distribution/payment/customer", "enabled": True},
                {"label": "اختصار مخفي", "url": "/auth/account", "enabled": False},
            ]

        dashboard = client.get("/dashboard/")
        assert dashboard.status_code == 200
        html = dashboard.get_data(as_text=True)
        assert "صرف عميل مخصص" in html
        assert "اختصار مخفي" not in html
    finally:
        cleanup(app)

def test_install_name_is_configurable_and_restorable():
    app, _ids = setup()
    try:
        client = app.test_client()
        login(client)
        initial = client.get("/manifest.webmanifest").get_json()
        assert initial["name"] == "نظام إدارة المخبز"
        assert initial["short_name"] != "Bakary"

        saved = client.post("/settings/", data={
            "action": "save_pwa_settings",
            "pwa_app_name": "مخبز العطاب",
            "pwa_app_short_name": "مخبز العطاب",
        }, follow_redirects=True)
        assert saved.status_code == 200
        manifest = client.get("/manifest.webmanifest").get_json()
        assert manifest["name"] == "مخبز العطاب"
        assert manifest["short_name"] == "مخبز العطاب"

        reset = client.post("/settings/", data={"action": "restore_pwa_defaults"}, follow_redirects=True)
        assert reset.status_code == 200
        restored = client.get("/manifest.webmanifest").get_json()
        assert restored["name"] == "نظام إدارة المخبز"
        assert restored["short_name"] != "Bakary"
    finally:
        cleanup(app)

def test_install_icon_upload_generates_installable_png_sizes():
    app, _ids = setup()
    try:
        client = app.test_client()
        login(client)
        image_stream = BytesIO()
        Image.new("RGB", (64, 64), "blue").save(image_stream, format="PNG")
        image_stream.seek(0)

        response = client.post("/settings/", data={
            "action": "save_pwa_settings",
            "pwa_app_name": "مخبز الاختبار",
            "pwa_app_short_name": "المخبز",
            "app_icon": (image_stream, "icon.png"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert response.status_code == 200
        manifest = client.get("/manifest.webmanifest").get_json()
        assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
        for icon in manifest["icons"]:
            result = client.get(icon["src"])
            assert result.status_code == 200
            assert result.mimetype == "image/png"

        client.post("/settings/", data={"action": "restore_pwa_defaults"}, follow_redirects=True)
    finally:
        cleanup(app)

