from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.employee import Employee
from app.models.role import Role
from app.models.user import User


def setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        owner_role = Role(name="مالك اختبار", code="owner", is_system=True)
        distribution_role = Role(name="مسؤول توزيع اختبار", code="distribution", is_system=True)
        owner = User(full_name="المدير", phone="+967771234567", is_active=True)
        owner.set_password("Strong-pass-123")
        owner.roles.append(owner_role)
        db.session.add_all([owner_role, distribution_role, owner])
        db.session.commit()
    return app


def cleanup(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post("/auth/login", data={
        "phone": "+967771234567",
        "password": "Strong-pass-123",
    }, follow_redirects=True)
    assert response.status_code == 200


def test_employee_create_makes_login_account_and_assigns_role():
    app = setup()
    try:
        client = app.test_client()
        login(client)
        response = client.post("/staff/employees/?action=new", data={
            "full_name": "موظف تجريبي",
            "phone": "777123456",
            "job_title": "مسؤول توزيع",
            "notes": "اختبار حساب الدخول",
            "user_password": "Employee-pass-123",
            "role_codes": ["distribution"],
            "is_active": "y",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "تم حفظ الموظف وحساب الدخول والصلاحيات" in response.get_data(as_text=True)
        with app.app_context():
            employee = db.session.scalar(select(Employee).where(Employee.full_name == "موظف تجريبي"))
            assert employee is not None
            assert employee.user is not None
            assert employee.user.phone == "+967777123456"
            assert employee.user.check_password("Employee-pass-123")
            assert [role.code for role in employee.user.roles] == ["distribution"]
    finally:
        cleanup(app)


def test_employee_page_and_role_editor_are_protected_by_login():
    app = setup()
    try:
        client = app.test_client()
        assert client.get("/staff/employees/").status_code == 302
        login(client)
        assert client.get("/staff/employees/").status_code == 200
        assert client.get("/staff/roles").status_code == 200
    finally:
        cleanup(app)
