"""Employee directory and role-permission administration."""

from flask import Blueprint

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")

from app.staff import routes  # noqa: E402,F401
