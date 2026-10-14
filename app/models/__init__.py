"""Import every ORM model so Flask-Migrate sees complete metadata."""

from app.models.audit import AuditLog
from app.models.closing import PeriodCloseProduct, PeriodHandover
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
from app.models.employee import Employee
from app.models.expense import CashTransfer, Expense
from app.models.finance import CashAccount, CashMovement
from app.models.free_distribution import FreeDistribution, FreeRecipient
from app.models.inventory import InventoryItem, InventoryMovement
from app.models.party import Party, PartyPrice
from app.models.production import BusinessPeriod, DoughBatch, PeriodIngredientUsage
from app.models.product import Product
from app.models.role import Permission, Role
from app.models.setting import Setting
from app.models.user import User

__all__ = [
    "AuditLog",
    "BusinessPeriod",
    "CashAccount",
    "CashMovement",
    "CashTransfer",
    "DistributionIssue",
    "DoughBatch",
    "Employee",
    "Expense",
    "FreeDistribution",
    "FreeRecipient",
    "InventoryItem",
    "InventoryMovement",
    "Party",
    "PartyLedgerEntry",
    "PartyPayment",
    "PartyPrice",
    "PeriodCloseProduct",
    "PeriodHandover",
    "PeriodIngredientUsage",
    "Permission",
    "Product",
    "Role",
    "Setting",
    "User",
]
