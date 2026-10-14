"""Roles and granular permissions."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.associations import role_permissions, user_roles
from app.models.base import TimestampMixin


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False, unique=True)
    code = db.Column(String(80), nullable=False, unique=True, index=True)
    description = db.Column(String(300), nullable=True)
    is_system = db.Column(Boolean, nullable=False, default=False)

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Role {self.code}>"


class Permission(TimestampMixin, db.Model):
    __tablename__ = "permissions"

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(140), nullable=False)
    code = db.Column(String(120), nullable=False, unique=True, index=True)
    description = db.Column(String(300), nullable=True)

    roles = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
    )

    def __repr__(self):
        return f"<Permission {self.code}>"
