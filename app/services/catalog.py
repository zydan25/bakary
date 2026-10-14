"""Product catalog operations and default-price policy."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.product import Product


CENT = Decimal("0.01")


class CatalogRuleError(ValueError):
    pass


def _price(value, label):
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CatalogRuleError(f"قيمة {label} غير صحيحة.") from exc
    if not result.is_finite() or result < 0:
        raise CatalogRuleError(f"لا يمكن أن يكون {label} سالبًا.")
    return result


def save_product(
    *,
    product_id=None,
    name,
    code,
    unit_label,
    default_distributor_price,
    default_customer_price,
    shop_price,
    is_default=False,
    actor_id=None,
):
    name = (name or "").strip()
    code = (code or "").strip().upper()
    unit_label = (unit_label or "").strip()
    if not name:
        raise CatalogRuleError("اسم الصنف مطلوب.")
    if not unit_label:
        raise CatalogRuleError("وحدة البيع مطلوبة.")

    product = None
    if product_id:
        product = db.session.scalar(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        if product is None:
            raise CatalogRuleError("لم يتم العثور على الصنف المطلوب.")
        if not code:
            code = product.code
    if not code:
        code = f"PRD-{uuid4().hex[:12].upper()}"
    if len(code) > 40:
        raise CatalogRuleError("رمز الصنف لا يتجاوز 40 حرفًا.")

    distributor_price = _price(default_distributor_price, "سعر الموزع العام")
    customer_price = _price(default_customer_price, "سعر العميل العام")
    shop_price = _price(shop_price, "سعر بيع المحل")

    try:
        if is_default:
            db.session.query(Product).filter(Product.id != (product.id if product else -1)).update(
                {Product.is_default: False},
                synchronize_session=False,
            )

        if product is None:
            product = Product(
                name=name,
                code=code,
                unit_label=unit_label,
                is_default=bool(is_default),
                is_active=True,
                default_distributor_price=distributor_price,
                default_customer_price=customer_price,
                shop_price=shop_price,
                created_by_id=actor_id,
            )
            db.session.add(product)
        else:
            product.name = name
            product.code = code
            product.unit_label = unit_label
            product.is_default = bool(is_default)
            product.default_distributor_price = distributor_price
            product.default_customer_price = customer_price
            product.shop_price = shop_price

        db.session.flush()
        defaults = db.session.scalars(
            select(Product).where(Product.is_default.is_(True), Product.is_active.is_(True))
        ).all()
        if not defaults:
            product.is_default = True
        db.session.commit()
        return product
    except IntegrityError as exc:
        db.session.rollback()
        raise CatalogRuleError("اسم الصنف أو رمزه مستخدم بالفعل.") from exc
    except Exception:
        db.session.rollback()
        raise


def default_product():
    product = db.session.scalar(
        select(Product)
        .where(Product.is_active.is_(True), Product.is_default.is_(True))
        .order_by(Product.id.asc())
        .limit(1)
    )
    if product is not None:
        return product
    product = db.session.scalar(
        select(Product)
        .where(Product.is_active.is_(True), Product.code == "ROTI")
        .limit(1)
    )
    if product is not None:
        product.is_default = True
        db.session.commit()
    return product
