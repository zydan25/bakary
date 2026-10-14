"""Import every ORM model so Flask-Migrate sees complete metadata."""

from app.models.audit import AuditLog
from app.models.role import Permission, Role
from app.models.setting import Setting
from app.models.user import User

__all__ = ["AuditLog", "Permission", "Role", "Setting", "User"]
