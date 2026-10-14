"""Production register and period-level ingredient consumption pages."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.production import BusinessPeriod, DoughBatch, PeriodIngredientUsage
from app.models.product import Product
from app.production import production_bp
from app.production.forms import DoughBatchForm, PeriodFlourForm
from app.services.periods import PeriodRuleError, period_label, period_mode, suggested_period_code
from app.services.production import (
    ProductionRuleError,
    create_dough_batch,
    record_period_flour_usage,
)


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else date.today()
    except (TypeError, ValueError):
        return date.today()


def _selected_period_code(value):
    if period_mode() == "daily":
        return "daily"
    if value in {"morning", "evening"}:
        return value
    return suggested_period_code()


def _period_choices():
    if period_mode() == "daily":
        return [("daily", "اليوم كاملًا")]
    return [("morning", "الفترة الصباحية"), ("evening", "الفترة المسائية")]


def _page_context(
    *,
    selected_date=None,
    selected_code=None,
    batch_form=None,
    flour_form=None,
    action=None,
    saved_batch_id=None,
):
    selected_date = selected_date or _parse_date(request.args.get("date"))
    selected_code = _selected_period_code(
        selected_code or request.args.get("period_code")
    )
    periods = _period_choices()
    product_rows = db.session.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    inventory_rows = db.session.scalars(
        select(InventoryItem)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.name.asc())
    ).all()
    period = db.session.scalar(
        select(BusinessPeriod).where(
            BusinessPeriod.business_date == selected_date,
            BusinessPeriod.period_code == selected_code,
        )
    )

    if batch_form is None:
        batch_form = DoughBatchForm()
        batch_form.product_id.data = next(
            (product.id for product in product_rows if product.is_default),
            product_rows[0].id if product_rows else 0,
        )
        batch_form.flour_item_id.data = 0
        batch_form.flour_mode.data = "none"
        batch_form.business_date.data = selected_date
        batch_form.period_code.data = selected_code
        batch_form.idempotency_key.data = uuid4().hex
    if flour_form is None:
        flour_form = PeriodFlourForm()
        default_flour = next(
            (
                item for item in inventory_rows
                if "دقيق" in item.name or "طحين" in item.name
            ),
            inventory_rows[0] if inventory_rows else None,
        )
        flour_form.item_id.data = default_flour.id if default_flour else 0
        flour_form.business_date.data = selected_date
        flour_form.period_code.data = selected_code

    product_choices = [(0, "اختر الصنف المخبوز...")] + [
        (product.id, product.name) for product in product_rows
    ]
    flour_choices = [(0, "اختر مادة الدقيق...")] + [
        (item.id, item.name) for item in inventory_rows
    ]
    batch_form.product_id.choices = product_choices
    batch_form.flour_item_id.choices = [(0, "لا توجد مادة محددة")] + [
        (item.id, item.name) for item in inventory_rows
    ]
    batch_form.period_code.choices = periods
    flour_form.item_id.choices = flour_choices
    flour_form.period_code.choices = periods

    batches = []
    flour_usages = []
    if period is not None:
        batches = db.session.scalars(
            select(DoughBatch)
            .where(DoughBatch.period_id == period.id)
            .order_by(DoughBatch.created_at.desc(), DoughBatch.id.desc())
        ).all()
        flour_usages = db.session.scalars(
            select(PeriodIngredientUsage)
            .where(PeriodIngredientUsage.period_id == period.id)
            .order_by(PeriodIngredientUsage.id.asc())
        ).all()

    produced_by_product = {}
    for batch in batches:
        produced_by_product[batch.product_id] = (
            produced_by_product.get(batch.product_id, Decimal("0.000"))
            + Decimal(str(batch.produced_quantity))
        )
    produced_total = sum(
        produced_by_product.values(), Decimal("0.000")
    )
    per_batch_flour = sum(
        (Decimal(str(batch.flour_quantity or 0)) for batch in batches),
        Decimal("0.000"),
    )
    aggregate_flour = sum(
        (Decimal(str(row.quantity)) for row in flour_usages),
        Decimal("0.000"),
    )
    saved_batch = db.session.get(DoughBatch, saved_batch_id) if saved_batch_id else None

    return render_template(
        "production/index.html",
        products=product_rows,
        inventory_items=inventory_rows,
        period=period,
        selected_date=selected_date,
        selected_code=selected_code,
        selected_period_label=period_label(selected_code),
        period_choices=periods,
        batches=batches,
        flour_usages=flour_usages,
        produced_by_product=produced_by_product,
        produced_total=produced_total,
        per_batch_flour=per_batch_flour,
        aggregate_flour=aggregate_flour,
        batch_form=batch_form,
        flour_form=flour_form,
        show_batch_form=action == "batch" or (batch_form is not None and bool(batch_form.errors)),
        show_flour_form=action == "flour" or (flour_form is not None and bool(flour_form.errors)),
        saved_batch=saved_batch,
        can_manage=current_user.has_permission("production.manage"),
        item_units={str(item.id): item.unit_label for item in inventory_rows},
        product_units={str(product.id): product.unit_label for product in product_rows},
    )


@production_bp.get("/")
@login_required
def index():
    if not (
        current_user.has_permission("production.view")
        or current_user.has_permission("production.manage")
    ):
        abort(403)
    return _page_context(
        selected_date=_parse_date(request.args.get("date")),
        selected_code=_selected_period_code(request.args.get("period_code")),
        action=request.args.get("action"),
        saved_batch_id=request.args.get("saved_batch", type=int),
    )


@production_bp.post("/batches")
@login_required
def create_batch():
    _require("production.manage")
    form = DoughBatchForm()
    context = _page_context(
        selected_date=_parse_date(request.form.get("business_date")),
        selected_code=_selected_period_code(request.form.get("period_code")),
        batch_form=form,
        action="batch",
    )
    # _page_context assigns dynamic select choices before validating.
    if form.validate_on_submit():
        try:
            batch, created = create_dough_batch(
                product_id=form.product_id.data,
                produced_quantity=form.produced_quantity.data,
                business_date=form.business_date.data,
                period_code=form.period_code.data,
                flour_mode=form.flour_mode.data,
                flour_item_id=form.flour_item_id.data,
                flour_quantity=form.flour_quantity.data,
                statement=form.statement.data,
                actor_id=current_user.id,
                idempotency_key=form.idempotency_key.data,
            )
            flash(
                "تم تسجيل العجنة واستهلاك الدقيق بنجاح."
                if created else "هذه العجنة مسجلة بالفعل؛ لم تُكرر.",
                "success" if created else "info",
            )
            return redirect(
                url_for(
                    "production.index",
                    date=batch.period.business_date.isoformat(),
                    period_code=batch.period.period_code,
                    action="batch",
                    saved_batch=batch.id,
                )
            )
        except (ProductionRuleError, PeriodRuleError) as exc:
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            flash("تعذر تسجيل العجنة. لم يتم تأكيد الحفظ.", "error")
    return _page_context(
        selected_date=_parse_date(request.form.get("business_date")),
        selected_code=_selected_period_code(request.form.get("period_code")),
        batch_form=form,
        action="batch",
    )


@production_bp.post("/flour-usage")
@login_required
def create_flour_usage():
    _require("production.manage")
    form = PeriodFlourForm()
    _page_context(
        selected_date=_parse_date(request.form.get("business_date")),
        selected_code=_selected_period_code(request.form.get("period_code")),
        flour_form=form,
        action="flour",
    )
    if form.validate_on_submit():
        try:
            usage, created = record_period_flour_usage(
                item_id=form.item_id.data,
                quantity=form.quantity.data,
                business_date=form.business_date.data,
                period_code=form.period_code.data,
                statement=form.statement.data,
                actor_id=current_user.id,
            )
            flash(
                "تم تسجيل إجمالي الدقيق للفترة وخصمه من المخزون."
                if created else "إجمالي الدقيق نفسه مسجل بالفعل؛ لم يُخصم مرة أخرى.",
                "success" if created else "info",
            )
            return redirect(
                url_for(
                    "production.index",
                    date=usage.period.business_date.isoformat(),
                    period_code=usage.period.period_code,
                    action="flour",
                )
            )
        except (ProductionRuleError, PeriodRuleError) as exc:
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            flash("تعذر تسجيل إجمالي الدقيق. لم يتم تأكيد الحفظ.", "error")
    return _page_context(
        selected_date=_parse_date(request.form.get("business_date")),
        selected_code=_selected_period_code(request.form.get("period_code")),
        flour_form=form,
        action="flour",
    )
