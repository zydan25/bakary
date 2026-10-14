"""Audit records for sensitive changes and actions."""

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class AuditLog(TimestampMixin, db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(Integer, primary_key=True)
    actor_user_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = db.Column(String(100), nullable=False, index=True)
    entity_type = db.Column(String(100), nullable=True, index=True)
    entity_id = db.Column(String(100), nullable=True)
    details = db.Column(JSON, nullable=False, default=dict)
    remote_addr = db.Column(String(64), nullable=True)
    user_agent = db.Column(String(300), nullable=True)

    actor = relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self):
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"
