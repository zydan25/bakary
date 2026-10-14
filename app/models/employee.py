"""Employee directory kept separate from authentication accounts."""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class Employee(TimestampMixin, db.Model):
    __tablename__ = "employees"

    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    full_name = db.Column(String(160), nullable=False, index=True)
    phone = db.Column(String(32), nullable=True, index=True)
    job_title = db.Column(String(100), nullable=True)
    notes = db.Column(Text, nullable=True)
    is_active = db.Column(Boolean, nullable=False, default=True, index=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    user = relationship("User", foreign_keys=[user_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Employee {self.id} {self.full_name}>"
