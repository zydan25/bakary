"""Shared ORM model helpers."""

from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = __import__("app.extensions", fromlist=["db"]).db.Column(
        __import__("sqlalchemy", fromlist=["DateTime"]).DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at = __import__("app.extensions", fromlist=["db"]).db.Column(
        __import__("sqlalchemy", fromlist=["DateTime"]).DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
