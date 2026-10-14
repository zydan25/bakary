"""Raw-material item catalogue, stock intake, and movement history."""

from datetime import date
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.inventory import inventory_bp
from app.inventory.forms import InventoryItemForm, StockMovementForm
from app.models.inventory import InventoryItem, InventoryMovement
from app.services.inventory import (
    InventoryRuleError,
    create_inventory_item,
    inventory_balance,
    register_stock_movement,
)


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _set_item_choices(form):
    items = db.session.scalars(
        select(InventoryItem)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.name.asc())
    ).all()
    form.item_id.choices = [(0, "اختر المادة الخام...")] + [
        (item.id, item.name) for item in items
    ]
    return items


@inventory_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if not (
        current_user.has_permission("inventory.view")
        or current_user.has_permission("inventory.manage")
    ):
        abort(403)

    form = InventoryItemForm()
    query = (request.args.get("q") or "").strip()
    status = request.args.get("status", "active")
    if status not in {"active", "inactive", "all"}:
        status = "active"
    action = request.args.get("action", "")

    if request.method == "POST":
        _require("inventory.manage")
        if form.validate_on_submit():
            try:
                create_inventory_item(
                    name=form.name.data,
                    code=form.code.data,
                    unit_label=form.unit_label.data,
                    reorder_level=form.reorder_level.data,
                    actor_id=current_user.id,
                )
                flash("تمت إضافة المادة الخام بنجاح.", "success")
                return redirect(url_for("inventory.index", status=status, q=query or None))
            except InventoryRuleError as exc:
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                flash("تعذر حفظ المادة الخام. راجع البيانات وحاول مجددًا.", "error")
        action = "new"

    statement = select(InventoryItem)
    if status == "active":
        statement = statement.where(InventoryItem.is_active.is_(True))
    elif status == "inactive":
        statement = statement.where(InventoryItem.is_active.is_(False))
    if query:
        needle = "%" + query + "%"
        statement = statement.where(
            db.or_(InventoryItem.name.ilike(needle), InventoryItem.code.ilike(needle))
        )
    items = db.session.scalars(statement.order_by(InventoryItem.name.asc())).all()
    balances = {item.id: inventory_balance(item.id) for item in items}

    return render_template(
        "inventory/index.html",
        items=items,
        balances=balances,
        query=query,
        status=status,
        form=form,
        can_manage=current_user.has_permission("inventory.manage"),
        show_form=action == "new" or (request.method == "POST" and bool(form.errors)),
    )


@inventory_bp.route("/stock", methods=["GET", "POST"])
@login_required
def stock():
    _require("inventory.manage")
    form = StockMovementForm()
    items = _set_item_choices(form)
    requested_item_id = request.args.get("item_id", type=int)

    if request.method == "GET":
        form.item_id.data = (
            requested_item_id
            if any(item.id == requested_item_id for item in items)
            else 0
        )
        form.movement_type.data = request.args.get("kind", "addition")
        if form.movement_type.data not in {"opening_balance", "addition"}:
            form.movement_type.data = "addition"
        form.business_date.data = date.today()
        form.quantity.data = None
        form.request_id.data = str(uuid4().int % 9000000000000000000 + 1)
    elif not form.request_id.data:
        form.request_id.data = str(uuid4().int % 9000000000000000000 + 1)

    if request.method == "POST" and form.validate_on_submit():
        try:
            item_id = form.item_id.data
            request_id = int(form.request_id.data)
            existing_request = db.session.scalar(
                select(InventoryMovement).where(
                    InventoryMovement.item_id == item_id,
                    InventoryMovement.source_type == "inventory_manual_request",
                    InventoryMovement.source_id == request_id,
                )
            )
            if existing_request is not None:
                flash("تم تسجيل هذه الحركة سابقًا؛ لم تُكرر.", "info")
                return redirect(url_for("inventory.stock", item_id=item_id))
            
            if form.movement_type.data == "opening_balance":
                opening_exists = db.session.scalar(
                    select(InventoryMovement.id)
                    .where(
                        InventoryMovement.item_id == item_id,
                        InventoryMovement.movement_type == "opening_balance",
                    )
                    .limit(1)
                )
                if opening_exists is not None:
                    raise InventoryRuleError(
                        "يوجد رصيد افتتاحي مسجل لهذه المادة. استخدم «إضافة مخزون» للحركات الجديدة."
                    )

            movement, created = register_stock_movement(
                item_id=item_id,
                quantity=form.quantity.data,
                direction="in",
                movement_type=form.movement_type.data,
                business_date=form.business_date.data,
                actor_id=current_user.id,
                statement=form.statement.data,
                source_type="inventory_manual_request",
                source_id=request_id,
            )
            flash(
                "تم تسجيل حركة المخزون بنجاح." if created else "كانت حركة المخزون مسجلة بالفعل.",
                "success" if created else "info",
            )
            return redirect(url_for("inventory.stock", item_id=item_id))
        except InventoryRuleError as exc:
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            flash("تعذر تسجيل حركة المخزون. لم يتم تأكيد الحفظ.", "error")

    selected_item = next((item for item in items if item.id == form.item_id.data), None)
    item_units = {str(item.id): item.unit_label for item in items}
    return render_template(
        "inventory/stock.html",
        form=form,
        items=items,
        selected_item=selected_item,
        item_units=item_units,
        show_form=True,
    )


@inventory_bp.get("/<int:item_id>/movements")
@login_required
def movements(item_id):
    if not (
        current_user.has_permission("inventory.view")
        or current_user.has_permission("inventory.manage")
    ):
        abort(403)
    item = db.session.get(InventoryItem, item_id)
    if item is None:
        abort(404)
    rows = db.session.scalars(
        select(InventoryMovement)
        .where(InventoryMovement.item_id == item_id)
        .order_by(
            InventoryMovement.business_date.desc(),
            InventoryMovement.created_at.desc(),
            InventoryMovement.id.desc(),
        )
    ).all()
    balance = inventory_balance(item_id)
    return render_template(
        "inventory/movements.html",
        item=item,
        rows=rows,
        balance=balance,
    )
