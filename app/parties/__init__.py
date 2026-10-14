"""Distributor and customer management blueprint."""

from flask import Blueprint

parties_bp = Blueprint("parties", __name__)

from app.parties import routes  # noqa: E402,F401
