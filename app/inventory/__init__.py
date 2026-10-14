"""Raw-material inventory blueprint."""

from flask import Blueprint

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

from app.inventory import routes  # noqa: E402,F401
