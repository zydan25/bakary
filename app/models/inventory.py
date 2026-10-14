"""Raw material catalog and quantity movement ledger."""

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class InventoryItem(TimestampMixin, db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(140), nullable=False, unique=True)
    code = db.Column(String(40), nullable=False, unique=True, index=True)
    unit_label = db.Column(String(24), nullable=False, default="كجم")
    is_active = db.Column(Boolean, nullable=False, default=True, index=True)
    reorder_level = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    movements = relationship("InventoryMovement", back_populates="item")

    def __repr__(self):
        return f"<InventoryItem {self.code} {self.name}>"


class InventoryMovement(TimestampMixin, db.Model):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("direction IN ('in', 'out')", name="direction_valid"),
        UniqueConstraint(
            "source_type", "source_id", "item_id",
            name="uq_inventory_movement_source_item",
        ),
    )

    id = db.Column(Integer, primary_key=True)
    item_id = db.Column(
        Integer, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type = db.Column(String(32), nullable=False)
    direction = db.Column(String(3), nullable=False)
    quantity = db.Column(Numeric(14, 3), nullable=False)
    unit_cost = db.Column(Numeric(14, 2), nullable=True)
    business_date = db.Column(Date, nullable=False, index=True)
    source_type = db.Column(String(40), nullable=True)
    source_id = db.Column(Integer, nullable=True)
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    item = relationship("InventoryItem", back_populates="movements")
    created_by = relationship("User")
