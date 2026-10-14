"""Application users. Employee records are linked in a later feature stage."""

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.associations import user_roles
from app.models.base import TimestampMixin


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(Integer, primary_key=True)
    full_name = db.Column(String(160), nullable=False)
    phone = db.Column(String(32), nullable=False, unique=True, index=True)
    password_hash = db.Column(String(255), nullable=False)
    is_active = db.Column(Boolean, nullable=False, default=True, index=True)
    must_change_password = db.Column(Boolean, nullable=False, default=False)
    last_login_at = db.Column(DateTime(timezone=True), nullable=True)

    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")

    def set_password(self, password):
        if not password or len(password) < 8:
            raise ValueError("يجب أن تتكون كلمة المرور من 8 أحرف على الأقل.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password or "")

    def has_permission(self, permission_code):
        if not self.is_active:
            return False
        if any(role.code == "owner" for role in self.roles):
            return True
        return any(
            permission.code == permission_code
            for role in self.roles
            for permission in role.permissions
        )

    def __repr__(self):
        return f"<User {self.id} {self.phone}>"
