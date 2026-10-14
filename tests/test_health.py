from app import create_app
from app.extensions import db


def test_health_endpoint_reports_database_healthy():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        response = app.test_client().get("/health")
        db.drop_all()

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["database"] == "ok"
