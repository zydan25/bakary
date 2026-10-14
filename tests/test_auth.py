from app import create_app
from app.extensions import db
from app.models.role import Role
from app.models.user import User
from app.services.phone import normalize_phone


def make_app_with_admin():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        role = Role(name="المالك", code="owner", is_system=True)
        user = User(full_name="مدير الاختبار", phone="+967771234567", is_active=True)
        user.set_password("Strong-pass-123")
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
    return app


def teardown_database(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_phone_normalization_supports_arabic_digits():
    assert normalize_phone("٠٠٩٦٧ ٧٧١-٢٣٤-٥٦٧") == "+967771234567"


def test_login_and_permission_protected_dashboard():
    app = make_app_with_admin()
    try:
        client = app.test_client()
        response = client.post(
            "/auth/login",
            data={"phone": "00967 771 234 567", "password": "Strong-pass-123"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert "إجراءات سريعة" in page
        assert "الأصناف والتسعير" in page
    finally:
        teardown_database(app)


def test_invalid_password_does_not_authenticate():
    app = make_app_with_admin()
    try:
        client = app.test_client()
        response = client.post(
            "/auth/login",
            data={"phone": "+967771234567", "password": "wrong-password"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "رقم الهاتف أو كلمة المرور غير صحيحة" in response.get_data(as_text=True)
    finally:
        teardown_database(app)


def test_protected_dashboard_redirects_to_sign_in():
    app = create_app("testing")
    client = app.test_client()
    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]



def test_manager_can_update_profile_and_password_from_account_dialogs():
    app = make_app_with_admin()
    try:
        client = app.test_client()
        client.post(
            "/auth/login",
            data={"phone": "+967771234567", "password": "Strong-pass-123"},
            follow_redirects=True,
        )

        page = client.get("/auth/account")
        html = page.get_data(as_text=True)
        assert page.status_code == 200
        assert "profile-edit-dialog" in html
        assert "password-edit-dialog" in html
        assert 'data-auto-open="false"' in html
        assert "مدير الاختبار" in html

        updated = client.post("/auth/account", data={
            "action": "profile",
            "full_name": "المدير المحدث",
            "phone": "+967771234568",
            "current_password": "Strong-pass-123",
        }, follow_redirects=True)
        assert updated.status_code == 200
        assert "تم تحديث بيانات الحساب بنجاح" in updated.get_data(as_text=True)
        with app.app_context():
            user = db.session.query(User).filter_by(phone="+967771234568").one()
            assert user.full_name == "المدير المحدث"

        password_update = client.post("/auth/account", data={
            "action": "password",
            "current_password": "Strong-pass-123",
            "new_password": "New-strong-pass-456",
            "confirm_password": "New-strong-pass-456",
        }, follow_redirects=True)
        assert password_update.status_code == 200
        assert "تم تحديث كلمة المرور بنجاح" in password_update.get_data(as_text=True)
        with app.app_context():
            user = db.session.query(User).filter_by(phone="+967771234568").one()
            assert user.check_password("New-strong-pass-456")
            assert not user.check_password("Strong-pass-123")
    finally:
        teardown_database(app)
