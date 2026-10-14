"""Free distribution recipients and daily/period issue records."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class FreeRecipient(TimestampMixin, db.Model):
    __tablename__ = "free_recipients"

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(160), nullable=False, index=True)
    notes = db.Column(Text, nullable=True)
    default_product_id = db.Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True)
    daily_quantity = db.Column(Numeric(14, 3), nullable=False, default=Decimal("0.000"))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    default_product = relationship("Product", foreign_keys=[default_product_id])


class FreeDistribution(TimestampMixin, db.Model):
    __tablename__ = "free_distributions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        UniqueConstraint(
            "period_id", "recipient_id", "product_id",
            name="uq_free_distribution_period_recipient_product",
        ),
    )

    id = db.Column(Integer, primary_key=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recipient_id = db.Column(
        Integer, ForeignKey("free_recipients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id = db.Column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity = db.Column(Numeric(14, 3), nullable=False)
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    period = relationship("BusinessPeriod", back_populates="free_distributions")
    recipient = relationship("FreeRecipient")
    product = relationship("Product")
    created_by = relationship("User")
