"""Database-backed settings for defaults that admins may change."""

from sqlalchemy import Integer, JSON, String

from app.extensions import db
from app.models.base import TimestampMixin


class Setting(TimestampMixin, db.Model):
    __tablename__ = "settings"

    id = db.Column(Integer, primary_key=True)
    key = db.Column(String(120), nullable=False, unique=True, index=True)
    value = db.Column(JSON, nullable=True)
    description = db.Column(String(300), nullable=True)

    def __repr__(self):
        return f"<Setting {self.key}>"
