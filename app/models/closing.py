"""Period closing quantities and cash handover snapshots."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin, utc_now


class PeriodCloseProduct(TimestampMixin, db.Model):
    __tablename__ = "period_close_products"
    __table_args__ = (
        CheckConstraint("opening_quantity >= 0", name="opening_quantity_nonnegative"),
        CheckConstraint("produced_quantity >= 0", name="produced_quantity_nonnegative"),
        CheckConstraint("paid_distribution_quantity >= 0", name="paid_distribution_nonnegative"),
        CheckConstraint("free_distribution_quantity >= 0", name="free_distribution_nonnegative"),
        CheckConstraint("damaged_quantity >= 0", name="damaged_quantity_nonnegative"),
        CheckConstraint("carried_quantity >= 0", name="carried_quantity_nonnegative"),
        UniqueConstraint("period_id", "product_id", name="uq_period_close_product"),
    )

    id = db.Column(Integer, primary_key=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id = db.Column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    opening_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    produced_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    paid_distribution_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    free_distribution_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    damaged_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    carried_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    shop_sale_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    shop_unit_price = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    expected_shop_sales = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    period = relationship("BusinessPeriod", back_populates="close_rows")
    product = relationship("Product")
    created_by = relationship("User")


class PeriodHandover(TimestampMixin, db.Model):
    __tablename__ = "period_handovers"
    __table_args__ = (
        CheckConstraint("received_amount >= 0", name="received_amount_nonnegative"),
        CheckConstraint("expenses_amount >= 0", name="expenses_amount_nonnegative"),
        CheckConstraint("handed_to_cash_amount >= 0", name="handed_to_cash_nonnegative"),
        UniqueConstraint("period_id", name="uq_period_handover_period"),
    )

    id = db.Column(Integer, primary_key=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    receiver_employee_id = db.Column(
        Integer, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    received_amount = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    expenses_amount = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    handed_to_cash_amount = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    calculated_expected_amount = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cash_difference = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    statement = db.Column(Text, nullable=True)
    confirmed_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    period = relationship("BusinessPeriod")
    receiver_employee = relationship("Employee")
    created_by = relationship("User")


class PeriodRawMaterialClose(TimestampMixin, db.Model):
    """Physical raw-material count and calculated production consumption at period close."""

    __tablename__ = "period_raw_material_closes"
    __table_args__ = (
        CheckConstraint("opening_quantity >= 0", name="raw_close_opening_nonnegative"),
        CheckConstraint("incoming_quantity >= 0", name="raw_close_incoming_nonnegative"),
        CheckConstraint("other_outgoing_quantity >= 0", name="raw_close_other_outgoing_nonnegative"),
        CheckConstraint("calculated_consumption >= 0", name="raw_close_consumption_nonnegative"),
        CheckConstraint("previously_recorded_consumption >= 0", name="raw_close_previous_usage_nonnegative"),
        CheckConstraint("ending_quantity >= 0", name="raw_close_ending_nonnegative"),
        UniqueConstraint("period_id", "item_id", name="uq_period_raw_material_close"),
    )

    id = db.Column(Integer, primary_key=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_id = db.Column(
        Integer, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    opening_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    incoming_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    other_outgoing_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    calculated_consumption = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    previously_recorded_consumption = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    ending_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    period = relationship("BusinessPeriod")
    item = relationship("InventoryItem")
    created_by = relationship("User")
