"""Flask application factory."""

import os

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError

from app.config import config_by_name
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name=None, test_config=None):
    name = config_name or os.getenv("FLASK_CONFIG", "development")
    if name not in config_by_name:
        raise ValueError(f"Unknown FLASK_CONFIG: {name}")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[name])
    if test_config:
        app.config.update(test_config)

    if name == "production" and (
        not os.getenv("SECRET_KEY")
        or os.getenv("SECRET_KEY") == "development-only-change-me"
    ):
        raise RuntimeError("SECRET_KEY must be configured for production.")

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import all models before migrations inspect SQLAlchemy metadata.
    from app import models  # noqa: F401
    from app.health import health_bp

    app.register_blueprint(health_bp)

    @app.get("/")
    def home():
        return render_template("landing.html")

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template(
            "error.html",
            title="تعذر التحقق من الطلب",
            message="انتهت صلاحية النموذج أو تعذر التحقق منه. أعد تحميل الصفحة وحاول مجددًا.",
        ), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "error.html",
            title="الصفحة غير موجودة",
            message="لم نعثر على الصفحة المطلوبة.",
        ), 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return render_template(
            "error.html",
            title="حدث خطأ",
            message="تعذر إكمال الطلب. حاول مجددًا، وإذا تكرر الخطأ فأبلغ المسؤول.",
        ), 500

    return app
