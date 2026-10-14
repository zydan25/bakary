"""Append-only raw-material inventory services."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.inventory import InventoryItem, InventoryMovement


QUANTITY_STEP = Decimal("0.001")


class InventoryRuleError(ValueError):
    pass


def quantity_value(value):
    try:
        amount = Decimal(str(value)).quantize(QUANTITY_STEP, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InventoryRuleError("أدخل كمية صحيحة.") from exc
    if not amount.is_finite() or amount <= 0:
        raise InventoryRuleError("يجب أن تكون الكمية أكبر من صفر.")
    return amount


def inventory_balance(item_id):
    in_total = func.coalesce(
        func.sum(
            case(
                (InventoryMovement.direction == "in", InventoryMovement.quantity),
                else_=0,
            )
        ),
        0,
    )
    out_total = func.coalesce(
        func.sum(
            case(
                (InventoryMovement.direction == "out", InventoryMovement.quantity),
                else_=0,
            )
        ),
        0,
    )
    inbound, outbound = db.session.execute(
        select(in_total, out_total).where(InventoryMovement.item_id == item_id)
    ).one()
    return Decimal(str(inbound or 0)) - Decimal(str(outbound or 0))


def create_inventory_item(*, name, code, unit_label="كجم", reorder_level=0, actor_id=None):
    name = (name or "").strip()
    code = (code or "").strip().upper()
    unit_label = (unit_label or "").strip()
    if not name:
        raise InventoryRuleError("اسم المادة مطلوب.")
    if not code:
        code = f"MAT-{uuid4().hex[:12].upper()}"
    if not unit_label:
        raise InventoryRuleError("وحدة القياس مطلوبة.")

    try:
        reorder = Decimal(str(reorder_level or 0)).quantize(QUANTITY_STEP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InventoryRuleError("حد التنبيه غير صالح.") from exc
    if not reorder.is_finite() or reorder < 0:
        raise InventoryRuleError("حد التنبيه لا يمكن أن يكون سالبًا.")

    item = InventoryItem(
        name=name,
        code=code,
        unit_label=unit_label,
        reorder_level=reorder,
        is_active=True,
        created_by_id=actor_id,
    )
    db.session.add(item)
    try:
        db.session.commit()
        return item
    except IntegrityError as exc:
        db.session.rollback()
        raise InventoryRuleError("اسم المادة أو رمزها مستخدم بالفعل.") from exc


def register_stock_movement(
    *,
    item_id,
    quantity,
    direction,
    movement_type,
    business_date,
    actor_id=None,
    statement=None,
    unit_cost=None,
    source_type=None,
    source_id=None,
    allow_negative=False,
):
    qty = quantity_value(quantity)
    if direction not in {"in", "out"}:
        raise InventoryRuleError("نوع حركة المخزون غير صالح.")
    item = db.session.scalar(
        select(InventoryItem)
        .where(InventoryItem.id == item_id)
        .with_for_update()
    )
    if item is None or not item.is_active:
        raise InventoryRuleError("المادة غير موجودة أو موقوفة.")

    if source_type and source_id is not None:
        existing = db.session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.source_type == source_type,
                InventoryMovement.source_id == source_id,
                InventoryMovement.item_id == item_id,
            )
        )
        if existing is not None:
            return existing, False

    current = inventory_balance(item_id)
    projected = current + qty if direction == "in" else current - qty
    if direction == "out" and projected < 0 and not allow_negative:
        raise InventoryRuleError(
            f"الكمية غير كافية. المتوفر {current} {item.unit_label}."
        )

    movement = InventoryMovement(
        item_id=item.id,
        movement_type=movement_type,
        direction=direction,
        quantity=qty,
        unit_cost=Decimal(str(unit_cost)).quantize(Decimal("0.01")) if unit_cost is not None else None,
        business_date=business_date,
        source_type=source_type,
        source_id=source_id,
        statement=(statement or "").strip() or None,
        created_by_id=actor_id,
    )
    try:
        db.session.add(movement)
        db.session.flush()
        if movement.source_type is None:
            movement.source_type = "inventory_manual"
        if movement.source_id is None:
            movement.source_id = movement.id
        db.session.commit()
        return movement, True
    except IntegrityError as exc:
        db.session.rollback()
        raise InventoryRuleError("تم تسجيل حركة مماثلة بالفعل.") from exc
    except Exception:
        db.session.rollback()
        raise



def inventory_valuation(item_id):
    """Return an estimated moving-average stock valuation from the immutable ledger.

    Value is intentionally reported as unknown if any still-relevant incoming stock
    has no unit cost. When quantity returns to zero, the unknown historical cost
    no longer affects the value of stock subsequently received.
    """
    from app.models.inventory import InventoryItem

    item = db.session.get(InventoryItem, item_id)
    if item is None:
        raise InventoryRuleError("المادة غير موجودة.")

    movements = db.session.scalars(
        select(InventoryMovement)
        .where(InventoryMovement.item_id == item_id)
        .order_by(
            InventoryMovement.business_date.asc(),
            InventoryMovement.created_at.asc(),
            InventoryMovement.id.asc(),
        )
    ).all()

    quantity = Decimal("0.000")
    value = Decimal("0.00")
    cost_known = True
    cent = Decimal("0.01")

    for movement in movements:
        qty = Decimal(str(movement.quantity))
        if movement.direction == "in":
            if movement.unit_cost is None:
                cost_known = False
            elif cost_known:
                value += qty * Decimal(str(movement.unit_cost))
        else:
            if cost_known and quantity > 0:
                average = value / quantity
                value -= qty * average
            quantity -= qty
            if quantity <= 0:
                quantity = Decimal("0.000")
                value = Decimal("0.00")
                cost_known = True

        if movement.direction == "in":
            quantity += qty

    balance = inventory_balance(item_id)
    if balance <= 0:
        return {
            "quantity": balance,
            "average_unit_cost": None,
            "stock_value": Decimal("0.00"),
            "is_valued": True,
        }

    if not cost_known or quantity <= 0:
        return {
            "quantity": balance,
            "average_unit_cost": None,
            "stock_value": None,
            "is_valued": False,
        }

    average = (value / quantity).quantize(cent, rounding=ROUND_HALF_UP)
    stock_value = (balance * average).quantize(cent, rounding=ROUND_HALF_UP)
    return {
        "quantity": balance,
        "average_unit_cost": average,
        "stock_value": stock_value,
        "is_valued": True,
    }
