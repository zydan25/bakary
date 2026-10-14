"""Idempotent first-run seed data for the bakery.

The first Alembic migration inserts the main cash account with code 'main'
(lowercase). This service deliberately matches that code case-insensitively and
also falls back to the unique display name, so running 'seed-defaults' after
'flask db upgrade' never tries to insert a duplicate cash account.
"""

from decimal import Decimal

from sqlalchemy import func, select

from app.extensions import db
from app.models.finance import CashAccount
from app.models.product import Product
from app.models.setting import Setting


def seed_default_data():
    """Create baseline records without overwriting configured prices/settings."""
    try:
        product = db.session.scalar(select(Product).where(Product.code == "ROTI"))
        if product is None:
            product = Product(
                name="روتي",
                code="ROTI",
                unit_label="حبة",
                is_default=False,
                is_active=True,
                default_distributor_price=Decimal("0.00"),
                default_customer_price=Decimal("0.00"),
                shop_price=Decimal("0.00"),
            )
            db.session.add(product)
            db.session.flush()
        else:
            product.is_active = True

        default_product = db.session.scalar(
            select(Product)
            .where(Product.is_default.is_(True))
            .order_by(Product.id)
            .limit(1)
        )
        if default_product is None:
            product.is_default = True

        # Migration 0002 uses code="main"; match both legacy/current casing and
        # the unique name to recover existing installs safely.
        main_account = db.session.scalar(
            select(CashAccount)
            .where(
                (func.lower(CashAccount.code) == "main")
                | (CashAccount.name == "الصندوق الرئيسي")
            )
            .order_by(CashAccount.id)
            .limit(1)
        )
        if main_account is None:
            main_account = CashAccount(
                code="MAIN",
                name="الصندوق الرئيسي",
                account_type="cash",
                is_main=True,
                is_active=True,
            )
            db.session.add(main_account)
            db.session.flush()
        else:
            main_account.is_main = True
            main_account.is_active = True

        # Exactly one account is designated as the main cash account.
        other_main_accounts = db.session.scalars(
            select(CashAccount).where(
                CashAccount.is_main.is_(True),
                CashAccount.id != main_account.id,
            )
        ).all()
        for account in other_main_accounts:
            account.is_main = False

        db.session.flush()
        defaults = [
            (
                "business_name",
                "نظام إدارة المخبز",
                "اسم المنشأة الظاهر في الواجهة والتقارير",
            ),
            (
                "default_product_id",
                product.id,
                "معرف الصنف الافتراضي المحدد مبدئيًا",
            ),
            (
                "operating_period_mode",
                "daily",
                "نمط التشغيل: daily أو morning_evening",
            ),
            (
                "currency_code",
                "YER",
                "رمز العملة",
            ),
        ]
        for key, value, description in defaults:
            setting = db.session.scalar(select(Setting).where(Setting.key == key))
            if setting is None:
                db.session.add(
                    Setting(key=key, value=value, description=description)
                )
            elif setting.value is None:
                setting.value = value
                setting.description = description

        db.session.commit()
        return {
            "default_product_id": product.id,
            "main_cash_account_id": main_account.id,
        }
    except Exception:
        db.session.rollback()
        raise
