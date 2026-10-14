"""Bakery configuration and operating preferences."""

from flask import Blueprint

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

from app.settings import routes  # noqa: E402,F401
