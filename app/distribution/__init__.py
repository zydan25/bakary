"""Distribution, collection, and account-statement blueprint."""

from flask import Blueprint

distribution_bp = Blueprint("distribution", __name__, url_prefix="/distribution")

from app.distribution import routes  # noqa: E402,F401
