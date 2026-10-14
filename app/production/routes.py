"""Production register and period-level ingredient consumption pages."""

from datetime import date
from app.services.clock import business_today
from decimal import Decimal
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models.production import BusinessPeriod, DoughBatch
from app.models.product import Product
from app.production import production_bp
from app.production.forms import DoughBatchForm
from app.services.periods import PeriodRuleError, period_label, period_mode, suggested_period_code
from app.services.production import (
    ProductionRuleError,
    create_dough_batch,
)


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else business_today()
    except (TypeError, ValueError):
        return business_today()


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
        batch_form.business_date.data = selected_date
        batch_form.period_code.data = selected_code
        batch_form.idempotency_key.data = uuid4().hex
    product_choices = [(0, "اختر الصنف المخبوز...")] + [
        (product.id, product.name) for product in product_rows
    ]
    batch_form.product_id.choices = product_choices
    batch_form.period_code.choices = periods

    batches = []
    if period is not None:
        batches = db.session.scalars(
            select(DoughBatch)
            .where(DoughBatch.period_id == period.id)
            .order_by(DoughBatch.created_at.desc(), DoughBatch.id.desc())
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
    saved_batch = db.session.get(DoughBatch, saved_batch_id) if saved_batch_id else None

    return render_template(
        "production/index.html",
        products=product_rows,
        period=period,
        selected_date=selected_date,
        selected_code=selected_code,
        selected_period_label=period_label(selected_code),
        period_choices=periods,
        batches=batches,
        produced_by_product=produced_by_product,
        produced_total=produced_total,
        batch_form=batch_form,
        show_batch_form=action == "batch" or (batch_form is not None and bool(batch_form.errors)),
        saved_batch=saved_batch,
        can_manage=current_user.has_permission("production.manage"),
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
                statement=form.statement.data,
                actor_id=current_user.id,
                idempotency_key=form.idempotency_key.data,
            )
            flash(
                "تم تسجيل العجنة بنجاح؛ سيُحتسب استهلاك المواد الخام عند إقفال الفترة."
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
    flash("تُسجّل كميات استهلاك المواد الخام عند إقفال الفترة بعد إدخال الجرد الفعلي.", "info")
    return redirect(url_for(
        "operations.closing",
        date=request.form.get("business_date") or request.args.get("date"),
        period_code=request.form.get("period_code") or request.args.get("period_code"),
    ))
