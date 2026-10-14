"""Dough production and operating-period blueprint."""

from flask import Blueprint

production_bp = Blueprint("production", __name__, url_prefix="/production")

from app.production import routes  # noqa: E402,F401
