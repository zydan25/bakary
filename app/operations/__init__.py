"""Free distribution, period closing, and cash handover."""

from flask import Blueprint

operations_bp = Blueprint("operations", __name__, url_prefix="/operations")

from app.operations import routes  # noqa: E402,F401
