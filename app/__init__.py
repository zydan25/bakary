"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from app.config import config_by_name
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name=None, test_config=None):
    name = config_name or os.getenv("FLASK_CONFIG", "development")
    if name not in config_by_name:
        raise ValueError(f"Unknown FLASK_CONFIG: {name}")

    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        instance_path=str(project_root / "instance"),
        instance_relative_config=True,
        template_folder=str(project_root / "templates"),
        static_folder="static",
    )
    app.config.from_object(config_by_name[name])
    if test_config:
        app.config.update(test_config)

    if name == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured for production.")
    if name == "production" and os.getenv("SECRET_KEY") == "development-only-change-me":
        raise RuntimeError("The development SECRET_KEY cannot be used in production.")

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "سجّل الدخول لمتابعة هذه الصفحة."
    login_manager.login_message_category = "info"

    # Import all models before migrations inspect SQLAlchemy metadata.
    from app import models  # noqa: F401
    from app.models.user import User
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.health import health_bp
    from app.products import products_bp
    from app.parties import parties_bp
    from app.distribution import distribution_bp
    from app.inventory import inventory_bp
    from app.production import production_bp
    from app.staff import staff_bp
    from app.operations import operations_bp
    from app.finance import finance_bp
    from app.settings import settings_bp
    from app.reports import reports_bp
    from app.cli import register_cli

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(parties_bp)
    app.register_blueprint(distribution_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(reports_bp)
    register_cli(app)

    @app.context_processor
    def inject_bakery_business_name():
        try:
            setting = db.session.query(models.Setting).filter_by(key="business_name").first()
            name = setting.value if setting is not None else None
            if not isinstance(name, str) or not name.strip():
                name = "نظام إدارة المخبز"
        except Exception:
            name = "نظام إدارة المخبز"
        bottom_setting = None
        try:
            bottom_setting = db.session.query(models.Setting).filter_by(key="show_bottom_nav").first()
        except Exception:
            bottom_setting = None
        show_bottom_nav = bottom_setting.value is not False if bottom_setting is not None else True
        return {"bakery_business_name": name, "show_bottom_nav": show_bottom_nav}

    @app.before_request
    def require_first_password_change():
        if not current_user.is_authenticated or not current_user.must_change_password:
            return None
        allowed_endpoints = {
            "auth.account",
            "auth.logout",
            "static",
            "service_worker",
            "health.health",
        }
        if request.endpoint not in allowed_endpoints:
            return redirect(url_for("auth.account"))
        return None

    @app.get("/sw.js", endpoint="service_worker")
    def service_worker():
        response = send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
            max_age=0,
        )
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(_error):
        return render_template(
            "error.html",
            title="تعذر التحقق من الطلب",
            message="انتهت صلاحية النموذج أو تعذر التحقق منه. أعد تحميل الصفحة وحاول مجددًا.",
        ), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template(
            "error.html",
            title="ليست لديك صلاحية",
            message="حسابك لا يملك الإذن لتنفيذ هذا الإجراء.",
        ), 403

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
