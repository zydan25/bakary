"""Shared party model for distributors and customers, shown in separate screens."""

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class Party(TimestampMixin, db.Model):
    __tablename__ = "parties"

    id = db.Column(Integer, primary_key=True)
    party_type = db.Column(String(20), nullable=False, index=True)
    name = db.Column(String(160), nullable=False, index=True)
    phone = db.Column(String(32), nullable=True, index=True)
    notes = db.Column(Text, nullable=True)
    is_active = db.Column(Boolean, nullable=False, default=True, index=True)
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    prices = relationship(
        "PartyPrice",
        back_populates="party",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def price_for(self, product):
        for price in self.prices:
            if price.product_id == product.id:
                return price.unit_price
        return product.default_price_for(self.party_type)

    def __repr__(self):
        return f"<Party {self.party_type} {self.name}>"


class PartyPrice(TimestampMixin, db.Model):
    __tablename__ = "party_prices"
    __table_args__ = (
        UniqueConstraint(
            "party_id", "product_id", name="uq_party_prices_party_product"
        ),
    )

    id = db.Column(Integer, primary_key=True)
    party_id = db.Column(
        Integer, ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_price = db.Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    is_custom = db.Column(Boolean, nullable=False, default=False)

    party = relationship("Party", back_populates="prices")
    product = relationship("Product", back_populates="prices")

    def __repr__(self):
        return f"<PartyPrice party={self.party_id} product={self.product_id}>"
