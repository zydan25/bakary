"""Operating expenses and transfers between cash accounts."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class Expense(TimestampMixin, db.Model):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("request_key", name="uq_expenses_request_key"),
    )

    id = db.Column(Integer, primary_key=True)
    title = db.Column(String(160), nullable=False, index=True)
    amount = db.Column(Numeric(14, 2), nullable=False)
    cash_account_id = db.Column(
        Integer, ForeignKey("cash_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_date = db.Column(Date, nullable=False, index=True)
    period_id = db.Column(
        Integer, ForeignKey("business_periods.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    statement = db.Column(Text, nullable=True)
    request_key = db.Column(String(64), nullable=True)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    cash_account = relationship("CashAccount")
    period = relationship("BusinessPeriod")
    created_by = relationship("User")


class CashTransfer(TimestampMixin, db.Model):
    __tablename__ = "cash_transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("source_account_id <> destination_account_id", name="accounts_different"),
        UniqueConstraint("request_key", name="uq_cash_transfers_request_key"),
    )

    id = db.Column(Integer, primary_key=True)
    source_account_id = db.Column(
        Integer, ForeignKey("cash_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    destination_account_id = db.Column(
        Integer, ForeignKey("cash_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount = db.Column(Numeric(14, 2), nullable=False)
    business_date = db.Column(Date, nullable=False, index=True)
    statement = db.Column(Text, nullable=True)
    request_key = db.Column(String(64), nullable=False)
    created_by_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    source_account = relationship("CashAccount", foreign_keys=[source_account_id])
    destination_account = relationship("CashAccount", foreign_keys=[destination_account_id])
    created_by = relationship("User")
