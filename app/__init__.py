"""Flask application factory."""

import json
import os
from pathlib import Path
import re

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
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

    @app.get("/manifest.webmanifest", endpoint="pwa_manifest")
    def pwa_manifest():
        def setting_value(key, default=None):
            try:
                row = db.session.query(models.Setting).filter_by(key=key).first()
                return row.value if row is not None and row.value is not None else default
            except Exception:
                return default

        business_name = setting_value("business_name", "نظام إدارة المخبز")
        if not isinstance(business_name, str) or not business_name.strip():
            business_name = "نظام إدارة المخبز"
        app_name = setting_value("pwa_app_name", business_name)
        if not isinstance(app_name, str) or not app_name.strip():
            app_name = business_name
        short_name = setting_value("pwa_app_short_name", app_name[:12].strip() or app_name[:12])
        if not isinstance(short_name, str) or not short_name.strip():
            short_name = app_name[:12].strip() or app_name[:12]

        icon_token = setting_value("pwa_app_icon")
        if not isinstance(icon_token, str) or not re.fullmatch(r"[0-9a-f]{32}", icon_token):
            icons = [{
                "src": url_for("static", filename="icons/bakary.svg"),
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }]
        else:
            icons = [
                {
                    "src": url_for("app_icon", token=icon_token, size=192),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": url_for("app_icon", token=icon_token, size=512),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
            ]

        manifest = {
            "id": "/",
            "name": app_name,
            "short_name": short_name,
            "description": "إدارة الموزعين والعملاء والإنتاج والمخزون والحسابات",
            "lang": "ar",
            "dir": "rtl",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": "#f6f8fb",
            "theme_color": "#1a56db",
            "icons": icons,
        }
        response = app.response_class(
            json.dumps(manifest, ensure_ascii=False),
            status=200,
            mimetype="application/manifest+json",
        )
        response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/app-icon/<token>/<int:size>.png", endpoint="app_icon")
    def app_icon(token, size):
        if size not in {192, 512} or not re.fullmatch(r"[0-9a-f]{32}", token):
            abort(404)
        try:
            row = db.session.query(models.Setting).filter_by(key="pwa_app_icon").first()
        except Exception:
            row = None
        if row is None or row.value != token:
            abort(404)
        icon_dir = Path(app.instance_path) / "app_icons"
        filename = f"app-icon-{token}-{size}.png"
        if not (icon_dir / filename).is_file():
            abort(404)
        response = send_from_directory(
            str(icon_dir),
            filename,
            mimetype="image/png",
            max_age=31536000,
        )
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

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
        try:
            pwa_name_setting = db.session.query(models.Setting).filter_by(key="pwa_app_name").first()
            pwa_app_name = pwa_name_setting.value if pwa_name_setting is not None else None
        except Exception:
            pwa_app_name = None
        if not isinstance(pwa_app_name, str) or not pwa_app_name.strip():
            pwa_app_name = name

        try:
            icon_setting = db.session.query(models.Setting).filter_by(key="pwa_app_icon").first()
            icon_token = icon_setting.value if icon_setting is not None else None
        except Exception:
            icon_token = None
        if isinstance(icon_token, str) and re.fullmatch(r"[0-9a-f]{32}", icon_token):
            pwa_app_icon_url = url_for("app_icon", token=icon_token, size=512)
            pwa_app_icon_custom = True
        else:
            pwa_app_icon_url = url_for("static", filename="icons/bakary.svg")
            pwa_app_icon_custom = False

        return {
            "bakery_business_name": name,
            "show_bottom_nav": show_bottom_nav,
            "pwa_app_name": pwa_app_name,
            "pwa_app_icon_url": pwa_app_icon_url,
            "pwa_app_icon_custom": pwa_app_icon_custom,
        }

    @app.before_request
    def require_first_password_change():
        if not current_user.is_authenticated or not current_user.must_change_password:
            return None
        allowed_endpoints = {
            "auth.account",
            "auth.logout",
            "static",
            "service_worker",
            "pwa_manifest",
            "app_icon",
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
