"""Operational endpoints used by reverse proxies and process monitors."""

from flask import jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.health import health_bp


@health_bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", service="bakary", database="ok"), 200
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(status="error", service="bakary", database="unavailable"), 503
