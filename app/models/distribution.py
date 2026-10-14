"""Distribution transactions and the auditable party subledger."""

from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin, utc_now


class DistributionIssue(TimestampMixin, db.Model):
    __tablename__ = "distribution_issues"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0 AND total_amount >= 0", name="amounts_nonnegative"),
    )

    id = db.Column(Integer, primary_key=True)
    party_id = db.Column(
        Integer, ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id = db.Column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity = db.Column(Integer, nullable=False)
    unit_price = db.Column(Numeric(14, 2), nullable=False)
    total_amount = db.Column(Numeric(14, 2), nullable=False)
    business_date = db.Column(Date, nullable=False, index=True)
    period_code = db.Column(String(12), nullable=False, default="daily")
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    party = relationship("Party")
    product = relationship("Product")
    created_by = relationship("User")


class PartyPayment(TimestampMixin, db.Model):
    __tablename__ = "party_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    id = db.Column(Integer, primary_key=True)
    party_id = db.Column(
        Integer, ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount = db.Column(Numeric(14, 2), nullable=False)
    business_date = db.Column(Date, nullable=False, index=True)
    period_code = db.Column(String(12), nullable=False, default="daily")
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    party = relationship("Party")
    created_by = relationship("User")


class PartyLedgerEntry(TimestampMixin, db.Model):
    __tablename__ = "party_ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "debit_amount >= 0 AND credit_amount >= 0",
            name="ledger_amounts_nonnegative",
        ),
        CheckConstraint(
            "NOT (debit_amount > 0 AND credit_amount > 0)",
            name="ledger_single_side",
        ),
        UniqueConstraint("source_type", "source_id", name="uq_party_ledger_source"),
    )

    id = db.Column(Integer, primary_key=True)
    party_id = db.Column(
        Integer, ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    entry_type = db.Column(String(24), nullable=False)
    debit_amount = db.Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    credit_amount = db.Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    business_date = db.Column(Date, nullable=False, index=True)
    source_type = db.Column(String(40), nullable=False)
    source_id = db.Column(Integer, nullable=False)
    statement = db.Column(Text, nullable=True)
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    party = relationship("Party")
    created_by = relationship("User")
