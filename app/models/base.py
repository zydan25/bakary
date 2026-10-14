"""Shared ORM model helpers."""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
