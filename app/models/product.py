"""Baked product catalog and default price policy."""

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(120), nullable=False, unique=True)
    code = db.Column(String(40), nullable=False, unique=True, index=True)
    unit_label = db.Column(String(30), nullable=False, default="حبة")
    is_default = db.Column(Boolean, nullable=False, default=False, index=True)
    is_active = db.Column(Boolean, nullable=False, default=True, index=True)
    default_distributor_price = db.Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    default_customer_price = db.Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    shop_price = db.Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    created_by_id = db.Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    prices = relationship(
        "PartyPrice",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    def default_price_for(self, party_type):
        if party_type == "distributor":
            return self.default_distributor_price
        if party_type == "customer":
            return self.default_customer_price
        raise ValueError("نوع الطرف غير معروف.")

    def __repr__(self):
        return f"<Product {self.code} {self.name}>"
