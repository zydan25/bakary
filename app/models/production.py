"""Daily or morning/evening operating periods and baked production records."""

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin, utc_now


class BusinessPeriod(TimestampMixin, db.Model):
    __tablename__ = "business_periods"
    __table_args__ = (
        UniqueConstraint("business_date", "period_code", name="uq_business_period_date_code"),
    )

    id = db.Column(Integer, primary_key=True)
    business_date = db.Column(Date, nullable=False, index=True)
    period_code = db.Column(String(12), nullable=False, default="daily")
    status = db.Column(String(12), nullable=False, default="open", index=True)
    opened_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    closed_at = db.Column(DateTime(timezone=True), nullable=True)
    opened_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    closed_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    batches = relationship("DoughBatch", back_populates="period")
    flour_usages = relationship("PeriodIngredientUsage", back_populates="period")
    free_distributions = relationship("FreeDistribution", back_populates="period")
    close_rows = relationship("PeriodCloseProduct", back_populates="period")

    def __repr__(self):
        return f"<BusinessPeriod {self.business_date} {self.period_code} {self.status}>"


class DoughBatch(TimestampMixin, db.Model):
    __tablename__ = "dough_batches"
    __table_args__ = (
        CheckConstraint("produced_quantity > 0", name="produced_quantity_positive"),
        CheckConstraint(
            "flour_quantity IS NULL OR flour_quantity >= 0",
            name="flour_quantity_nonnegative",
        ),
        UniqueConstraint("idempotency_key", name="uq_dough_batches_idempotency"),
    )

    id = db.Column(Integer, primary_key=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id = db.Column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    produced_quantity = db.Column(Numeric(14, 3), nullable=False)
    flour_quantity = db.Column(Numeric(14, 3), nullable=True)
    statement = db.Column(Text, nullable=True)
    idempotency_key = db.Column(String(64), nullable=False)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    period = relationship("BusinessPeriod", back_populates="batches")
    product = relationship("Product")
    created_by = relationship("User")


class PeriodIngredientUsage(TimestampMixin, db.Model):
    """Aggregate raw-material consumption recorded once for a whole period."""

    __tablename__ = "period_ingredient_usages"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        UniqueConstraint("period_id", "item_id", name="uq_period_ingredient_usage"),
    )

    id = db.Column(Integer, primary_key=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_id = db.Column(
        Integer, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity = db.Column(Numeric(14, 3), nullable=False)
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    period = relationship("BusinessPeriod", back_populates="flour_usages")
    item = relationship("InventoryItem")
    created_by = relationship("User")
