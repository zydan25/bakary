"""Idempotent first-run seed data for the bakery."""

from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.finance import CashAccount
from app.models.product import Product
from app.models.setting import Setting


def seed_default_data():
    """Create safe baseline records without overwriting configured prices/settings."""
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
        select(Product).where(Product.is_default.is_(True)).order_by(Product.id).limit(1)
    )
    if default_product is None:
        product.is_default = True

    main_account = db.session.scalar(
        select(CashAccount).where(CashAccount.code == "MAIN")
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
    else:
        main_account.is_main = True
        main_account.is_active = True

    # Keep a single designated main account if old data exists.
    other_main_accounts = db.session.scalars(
        select(CashAccount).where(
            CashAccount.is_main.is_(True),
            CashAccount.code != "MAIN",
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
            db.session.add(Setting(key=key, value=value, description=description))
        elif setting.value is None:
            setting.value = value
            setting.description = description

    db.session.commit()
    return {"default_product_id": product.id, "main_cash_account_id": main_account.id}
