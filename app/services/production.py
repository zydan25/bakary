"""Atomic production operations with an auditable raw-material ledger."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.inventory import InventoryItem, InventoryMovement
from app.models.production import DoughBatch, PeriodIngredientUsage
from app.models.product import Product
from app.services.inventory import inventory_balance
from app.services.periods import PeriodRuleError, get_or_create_open_period


QUANTITY_STEP = Decimal("0.001")


class ProductionRuleError(ValueError):
    """A requested production operation violates an operating rule."""


def _quantity(value, label, *, allow_zero=False):
    try:
        amount = Decimal(str(value)).quantize(QUANTITY_STEP, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProductionRuleError(f"قيمة {label} غير صحيحة.") from exc
    if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero):
        qualifier = "لا يمكن أن تكون سالبة." if allow_zero else "يجب أن تكون أكبر من صفر."
        raise ProductionRuleError(f"{label} {qualifier}")
    return amount


def create_dough_batch(
    *,
    product_id,
    produced_quantity,
    business_date,
    period_code="daily",
    flour_mode="none",
    flour_item_id=None,
    flour_quantity=None,
    statement=None,
    actor_id=None,
    idempotency_key,
):
    key = (idempotency_key or "").strip()
    if not key or len(key) > 64:
        raise ProductionRuleError("انتهت صلاحية نموذج العجنة. أعد فتح النموذج وحاول مجددًا.")

    prior = db.session.scalar(
        select(DoughBatch).where(DoughBatch.idempotency_key == key)
    )
    if prior is not None:
        return prior, False

    produced = _quantity(produced_quantity, "الكمية المنتجة")
    if flour_mode not in {"none", "per_batch"}:
        raise ProductionRuleError("طريقة احتساب الدقيق غير صالحة.")

    try:
        period, _created = get_or_create_open_period(
            business_date=business_date,
            period_code=period_code,
            actor_id=actor_id,
        )
    except PeriodRuleError:
        raise

    product = db.session.scalar(
        select(Product).where(Product.id == product_id, Product.is_active.is_(True))
    )
    if product is None:
        raise ProductionRuleError("الصنف المخبوز غير موجود أو موقوف.")

    flour_item = None
    flour_qty = None
    if flour_mode == "per_batch":
        if not flour_item_id:
            raise ProductionRuleError("اختر مادة الدقيق قبل تسجيل استهلاك العجنة.")
        if flour_quantity is None:
            raise ProductionRuleError("أدخل كمية الدقيق المستهلكة لهذه العجنة.")
        flour_qty = _quantity(flour_quantity, "كمية الدقيق")
        flour_item = db.session.scalar(
            select(InventoryItem)
            .where(InventoryItem.id == flour_item_id, InventoryItem.is_active.is_(True))
            .with_for_update()
        )
        if flour_item is None:
            raise ProductionRuleError("مادة الدقيق غير موجودة أو موقوفة.")

        aggregate_usage = db.session.scalar(
            select(PeriodIngredientUsage).where(
                PeriodIngredientUsage.period_id == period.id,
                PeriodIngredientUsage.item_id == flour_item.id,
            )
        )
        if aggregate_usage is not None:
            raise ProductionRuleError(
                "تم تسجيل إجمالي الدقيق لهذه الفترة. لا يمكن مزجه مع تسجيل الدقيق لكل عجنة."
            )
        available = inventory_balance(flour_item.id)
        if available < flour_qty:
            raise ProductionRuleError(
                f"كمية الدقيق غير كافية. المتوفر {available} {flour_item.unit_label}."
            )

    batch = DoughBatch(
        period_id=period.id,
        product_id=product.id,
        produced_quantity=produced,
        flour_quantity=flour_qty,
        flour_item_id=flour_item.id if flour_item else None,
        statement=(statement or "").strip() or None,
        idempotency_key=key,
        created_by_id=actor_id,
    )
    try:
        db.session.add(batch)
        db.session.flush()
        if flour_item is not None and flour_qty is not None:
            db.session.add(
                InventoryMovement(
                    item_id=flour_item.id,
                    movement_type="production_consumption",
                    direction="out",
                    quantity=flour_qty,
                    business_date=period.business_date,
                    source_type="dough_batch",
                    source_id=batch.id,
                    statement=f"استهلاك الدقيق للعجنة رقم {batch.id}",
                    created_by_id=actor_id,
                )
            )
        db.session.commit()
        return batch, True
    except IntegrityError:
        db.session.rollback()
        duplicate = db.session.scalar(
            select(DoughBatch).where(DoughBatch.idempotency_key == key)
        )
        if duplicate is not None:
            return duplicate, False
        raise ProductionRuleError("تعذر تسجيل العجنة بسبب تعارض في البيانات.")
    except Exception:
        db.session.rollback()
        raise


def record_period_flour_usage(
    *,
    item_id,
    quantity,
    business_date,
    period_code="daily",
    statement=None,
    actor_id=None,
):
    flour_qty = _quantity(quantity, "إجمالي الدقيق")
    try:
        period, _created = get_or_create_open_period(
            business_date=business_date,
            period_code=period_code,
            actor_id=actor_id,
        )
    except PeriodRuleError:
        raise

    item = db.session.scalar(
        select(InventoryItem)
        .where(InventoryItem.id == item_id, InventoryItem.is_active.is_(True))
        .with_for_update()
    )
    if item is None:
        raise ProductionRuleError("مادة الدقيق غير موجودة أو موقوفة.")

    existing = db.session.scalar(
        select(PeriodIngredientUsage).where(
            PeriodIngredientUsage.period_id == period.id,
            PeriodIngredientUsage.item_id == item.id,
        )
    )
    if existing is not None:
        if Decimal(str(existing.quantity)) == flour_qty:
            return existing, False
        raise ProductionRuleError(
            "تم تسجيل إجمالي الدقيق لهذه الفترة بالفعل. لا يمكن استبداله بقيمة أخرى؛ سجّل تصحيحًا موثقًا لاحقًا."
        )

    per_batch_usage = db.session.scalar(
        select(DoughBatch.id)
        .where(
            DoughBatch.period_id == period.id,
            DoughBatch.flour_item_id == item.id,
            DoughBatch.flour_quantity.is_not(None),
        )
        .limit(1)
    )
    if per_batch_usage is not None:
        raise ProductionRuleError(
            "سبق تسجيل استهلاك الدقيق لكل عجنة في هذه الفترة؛ لا يمكن إضافة إجمالي مجمع فوقه."
        )

    available = inventory_balance(item.id)
    if available < flour_qty:
        raise ProductionRuleError(
            f"كمية الدقيق غير كافية. المتوفر {available} {item.unit_label}."
        )

    usage = PeriodIngredientUsage(
        period_id=period.id,
        item_id=item.id,
        quantity=flour_qty,
        statement=(statement or "").strip() or None,
        created_by_id=actor_id,
    )
    try:
        db.session.add(usage)
        db.session.flush()
        db.session.add(
            InventoryMovement(
                item_id=item.id,
                movement_type="production_consumption",
                direction="out",
                quantity=flour_qty,
                business_date=period.business_date,
                source_type="period_flour_usage",
                source_id=usage.id,
                statement=(usage.statement or "إجمالي استهلاك الدقيق للفترة"),
                created_by_id=actor_id,
            )
        )
        db.session.commit()
        return usage, True
    except IntegrityError:
        db.session.rollback()
        existing = db.session.scalar(
            select(PeriodIngredientUsage).where(
                PeriodIngredientUsage.period_id == period.id,
                PeriodIngredientUsage.item_id == item.id,
            )
        )
        if existing is not None and Decimal(str(existing.quantity)) == flour_qty:
            return existing, False
        raise ProductionRuleError("تعذر تسجيل إجمالي الدقيق بسبب تعارض في البيانات.")
    except Exception:
        db.session.rollback()
        raise
