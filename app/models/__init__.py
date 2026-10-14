"""Import every ORM model so Flask-Migrate sees complete metadata."""

from app.models.audit import AuditLog
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
from app.models.finance import CashAccount, CashMovement
from app.models.party import Party, PartyPrice
from app.models.product import Product
from app.models.role import Permission, Role
from app.models.setting import Setting
from app.models.user import User

__all__ = [
    "AuditLog",
    "CashAccount",
    "CashMovement",
    "DistributionIssue",
    "Party",
    "PartyLedgerEntry",
    "PartyPayment",
    "PartyPrice",
    "Permission",
    "Product",
    "Role",
    "Setting",
    "User",
]
