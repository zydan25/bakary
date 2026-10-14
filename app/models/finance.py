"""Cash accounts and immutable inbound/outbound movements."""

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class CashAccount(TimestampMixin, db.Model):
    __tablename__ = "cash_accounts"

    id = db.Column(Integer, primary_key=True)
    code = db.Column(String(40), nullable=False, unique=True)
    name = db.Column(String(140), nullable=False, unique=True)
    account_type = db.Column(String(24), nullable=False, default="cash")
    is_main = db.Column(Boolean, nullable=False, default=False)
    is_active = db.Column(Boolean, nullable=False, default=True, index=True)
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    movements = relationship("CashMovement", back_populates="cash_account")

    def __repr__(self):
        return f"<CashAccount {self.code} {self.name}>"


class CashMovement(TimestampMixin, db.Model):
    __tablename__ = "cash_movements"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("direction IN ('in', 'out')", name="direction_valid"),
        UniqueConstraint("source_type", "source_id", name="uq_cash_movements_source"),
    )

    id = db.Column(Integer, primary_key=True)
    cash_account_id = db.Column(
        Integer,
        ForeignKey("cash_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    party_id = db.Column(
        Integer, ForeignKey("parties.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    movement_type = db.Column(String(32), nullable=False)
    direction = db.Column(String(3), nullable=False)
    amount = db.Column(Numeric(14, 2), nullable=False)
    business_date = db.Column(Date, nullable=False, index=True)
    statement = db.Column(Text, nullable=True)
    source_type = db.Column(String(40), nullable=True)
    source_id = db.Column(Integer, nullable=True)
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    cash_account = relationship("CashAccount", back_populates="movements")
    party = relationship("Party")
    created_by = relationship("User")
