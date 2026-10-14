"""Free-distribution records and period close/handover screens."""

from datetime import date
from app.services.clock import business_today
from decimal import Decimal
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.closing import PeriodCloseProduct, PeriodHandover
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
from app.models.employee import Employee
from app.models.expense import Expense
from app.models.finance import CashMovement
from app.models.free_distribution import FreeDistribution, FreeRecipient
from app.models.party import Party
from app.models.production import BusinessPeriod, DoughBatch
from app.models.product import Product
from app.models.user import User
from app.operations import operations_bp
from app.operations.forms import FreeIssueForm, FreeRecipientForm, PeriodClosingForm
from app.services.closing import (
    ClosingRuleError,
    calculate_close_rows,
    preview_period_close,
    close_period_with_handover,
    get_closed_period_summary,
    get_closed_raw_material_summary,
    preview_raw_material_balances,
    calculate_raw_material_close_rows,
)
from app.services.periods import PeriodRuleError, get_or_create_open_period, period_label, period_mode, suggested_period_code, selectable_open_periods, period_option_label, period_day_name


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else business_today()
    except (TypeError, ValueError):
        return business_today()


def _period_choices():
    return [("daily", "اليوم كاملًا")] if period_mode() == "daily" else [
        ("morning", "الفترة الصباحية"), ("evening", "الفترة المسائية")
    ]


def _clean_period_code(value):
    codes = {code for code, _label in _period_choices()}
    return value if value in codes else suggested_period_code()


def _free_context(*, recipient_form=None, issue_form=None, action=None, selected_date=None, selected_code=None, editing_recipient=None):
    selected_date = selected_date or _parse_date(request.args.get("date") or request.form.get("business_date"))
    selected_code = _clean_period_code(selected_code or request.args.get("period_code") or request.form.get("period_code"))
    recipients = db.session.scalars(
        select(FreeRecipient).order_by(FreeRecipient.is_active.desc(), FreeRecipient.name.asc())
    ).all()
    active_recipients = [row for row in recipients if row.is_active]
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    open_periods = selectable_open_periods(actor_id=current_user.id)
    requested_period_id = request.args.get("period_id", type=int)
    period = db.session.get(BusinessPeriod, requested_period_id) if requested_period_id else db.session.scalar(
        select(BusinessPeriod).where(
            BusinessPeriod.business_date == selected_date,
            BusinessPeriod.period_code == selected_code,
            BusinessPeriod.status == "open",
        )
    )
    if period is None or period.status != "open":
        period = next((row for row in open_periods if row.business_date == selected_date and row.period_code == selected_code), None)
    if period is None and open_periods:
        period = open_periods[0]
    if period is not None:
        selected_date, selected_code = period.business_date, period.period_code
    records = []
    if period:
        records = db.session.scalars(
            select(FreeDistribution).where(FreeDistribution.period_id == period.id)
            .order_by(FreeDistribution.created_at.desc(), FreeDistribution.id.desc())
        ).all()

    recipient_form = recipient_form or FreeRecipientForm()
    issue_form = issue_form or FreeIssueForm()
    issue_form.recipient_id.choices = [(0, "اختر المستفيد...")] + [(row.id, row.name) for row in active_recipients]
    issue_form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    issue_form.period_id.choices = [(row.id, period_option_label(row)) for row in open_periods]
    recipient_form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    default_product = next((row for row in products if row.is_default), products[0] if products else None)
    requested_recipient_id = request.args.get("recipient_id", type=int)
    if request.method == "GET":
        issue_form.recipient_id.data = requested_recipient_id or 0
        issue_form.period_id.data = period.id if period else (open_periods[0].id if open_periods else 0)
        recipient_form.product_id.data = default_product.id if default_product else 0
        if editing_recipient is not None:
            recipient_form.name.data = editing_recipient.name
            recipient_form.notes.data = editing_recipient.notes or ""
            recipient_form.product_id.data = editing_recipient.default_product_id or (default_product.id if default_product else 0)
            recipient_form.quantity.data = editing_recipient.daily_quantity

        # Prefill from the current period record or the recipient's expected daily target.
        if requested_recipient_id:
            latest_issue = db.session.scalar(
                select(FreeDistribution)
                .where(FreeDistribution.recipient_id == requested_recipient_id)
                .order_by(FreeDistribution.created_at.desc(), FreeDistribution.id.desc())
                .limit(1)
            )
            current_recipient_issue = next(
                (row for row in records if row.recipient_id == requested_recipient_id),
                None,
            )
            target_recipient = db.session.get(FreeRecipient, requested_recipient_id)
            preferred_issue = current_recipient_issue or latest_issue
            preferred_product_id = (
                current_recipient_issue.product_id if current_recipient_issue
                else (target_recipient.default_product_id if target_recipient and target_recipient.default_product_id
                      else (preferred_issue.product_id if preferred_issue else (default_product.id if default_product else 0)))
            )
            issue_form.product_id.data = preferred_product_id
            issue_form.quantity.data = (
                current_recipient_issue.quantity if current_recipient_issue
                else (target_recipient.daily_quantity if target_recipient else (preferred_issue.quantity if preferred_issue else None))
            )

        else:
            issue_form.product_id.data = default_product.id if default_product else 0
            issue_form.quantity.data = None

    selected_recipient_id = issue_form.recipient_id.data
    selected_recipient = next(
        (row for row in active_recipients if row.id == selected_recipient_id),
        None,
    )
    selected_product = next(
        (row for row in products if row.id == issue_form.product_id.data),
        None,
    )
    return render_template(
        "operations/free_distribution.html",
        recipients=recipients,
        active_recipients=active_recipients,
        products=products,
        records=records,
        period=period,
        selected_date=selected_date,
        selected_code=selected_code,
        selected_period_label=period_label(selected_code),
        period_choices=_period_choices(),
        recipient_form=recipient_form,
        issue_form=issue_form,
        selected_recipient=selected_recipient,
        selected_issue_product=selected_product,
        open_periods=open_periods,
        period_options=[{"period": row, "label": period_option_label(row)} for row in open_periods],
        editing_recipient=editing_recipient,
        expected_total=sum((row.daily_quantity for row in active_recipients), Decimal("0.000")),
        distributed_total=sum((row.quantity for row in records), Decimal("0.000")),
        target_rows=[
            {
                "product": product,
                "expected": sum((row.daily_quantity for row in active_recipients if row.default_product_id == product.id), Decimal("0.000")),
                "distributed": sum((row.quantity for row in records if row.product_id == product.id), Decimal("0.000")),
            }
            for product in products
            if any(row.default_product_id == product.id and row.daily_quantity > 0 for row in active_recipients)
            or any(row.product_id == product.id for row in records)
        ],
        period_day_name=period_day_name,
        period_option_label=period_option_label,
        show_recipient_form=action in {"recipient", "edit_recipient"} or bool(recipient_form.errors),
        show_issue_form=action == "issue" or bool(issue_form.errors),
    )


@operations_bp.get("/free-distribution/")
@login_required
def free_distribution():
    _require("free_distribution.manage")
    return _free_context(action=request.args.get("action"))


@operations_bp.post("/free-recipients/")
@login_required
def create_free_recipient():
    _require("free_distribution.manage")
    form = FreeRecipientForm()
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    if form.validate_on_submit():
        product = db.session.scalar(select(Product).where(
            Product.id == form.product_id.data, Product.is_active.is_(True)
        ))
        if product is None:
            flash("الصنف غير موجود أو موقوف.", "error")
        else:
            recipient = FreeRecipient(
                name=form.name.data.strip(),
                notes=(form.notes.data or "").strip() or None,
                default_product_id=product.id,
                daily_quantity=form.quantity.data,
                is_active=True,
                created_by_id=current_user.id,
            )
            db.session.add(recipient)
            db.session.commit()
            flash("تم حفظ المستفيد والهدف اليومي. سجّل الصرف الفعلي من زر الصرف.", "success")
            return redirect(url_for("operations.recipient_detail", recipient_id=recipient.id))
    return _free_context(recipient_form=form, action="recipient")


@operations_bp.get("/free-recipients/<int:recipient_id>")
@login_required
def recipient_detail(recipient_id):
    _require("free_distribution.manage")
    recipient = db.session.get(FreeRecipient, recipient_id)
    if recipient is None:
        abort(404)
    history = db.session.scalars(
        select(FreeDistribution).where(FreeDistribution.recipient_id == recipient.id)
        .order_by(FreeDistribution.created_at.desc(), FreeDistribution.id.desc())
    ).all()
    total = sum((Decimal(str(row.quantity)) for row in history), Decimal("0.000"))
    return render_template(
        "operations/recipient_detail.html",
        recipient=recipient,
        history=history,
        total_quantity=total,
        period_label=period_label,
    )


@operations_bp.route("/free-recipients/<int:recipient_id>/edit", methods=["GET", "POST"])
@login_required
def edit_free_recipient(recipient_id):
    _require("free_distribution.manage")
    recipient = db.session.get(FreeRecipient, recipient_id)
    if recipient is None:
        abort(404)
    form = FreeRecipientForm()
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    if request.method == "POST" and form.validate_on_submit():
        product = db.session.scalar(select(Product).where(
            Product.id == form.product_id.data, Product.is_active.is_(True)
        ))
        if product is None:
            flash("الصنف غير موجود أو موقوف.", "error")
        else:
            recipient.name = form.name.data.strip()
            recipient.notes = (form.notes.data or "").strip() or None
            recipient.default_product_id = product.id
            recipient.daily_quantity = form.quantity.data
            db.session.commit()
            flash("تم تحديث بيانات المستفيد والكمية اليومية المتوقعة.", "success")
            return redirect(url_for("operations.recipient_detail", recipient_id=recipient.id))
    return _free_context(recipient_form=form, action="edit_recipient", editing_recipient=recipient)


@operations_bp.post("/free-recipients/<int:recipient_id>/delete")
@login_required
def delete_free_recipient(recipient_id):
    _require("free_distribution.manage")
    recipient = db.session.get(FreeRecipient, recipient_id)
    if recipient is None:
        abort(404)
    history = db.session.scalars(
        select(FreeDistribution).where(FreeDistribution.recipient_id == recipient.id)
    ).all()
    closed_history = [row for row in history if row.period.status == "closed"]
    if closed_history:
        recipient.is_active = False
        db.session.commit()
        flash("للمستفيد عمليات في فترات مختتمة؛ تم إيقافه وحفظ التاريخ المالي بدل حذفه.", "error")
        return redirect(url_for("operations.recipient_detail", recipient_id=recipient.id))
    name = recipient.name
    # Actual distributions in still-open periods can be removed with the recipient;
    # closed-period transactions remain immutable for reliable close reports.
    for row in history:
        db.session.delete(row)
    db.session.flush()
    db.session.delete(recipient)
    db.session.commit()
    flash(f"تم حذف المستفيد «{name}» وسجلاته من الفترات المفتوحة.", "success")
    return redirect(url_for("operations.free_distribution"))


@operations_bp.post("/free-recipients/<int:recipient_id>/toggle")
@login_required
def toggle_free_recipient(recipient_id):
    _require("free_distribution.manage")
    recipient = db.session.get(FreeRecipient, recipient_id)
    if recipient is None:
        abort(404)
    recipient.is_active = not recipient.is_active
    db.session.commit()
    flash("تم تحديث حالة المستفيد.", "success")
    return redirect(url_for("operations.free_distribution"))


@operations_bp.post("/free-issues/")
@login_required
def create_free_issue():
    _require("free_distribution.manage")
    form = FreeIssueForm()
    recipients = db.session.scalars(
        select(FreeRecipient).where(FreeRecipient.is_active.is_(True)).order_by(FreeRecipient.name.asc())
    ).all()
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    open_periods = selectable_open_periods(actor_id=current_user.id)
    form.recipient_id.choices = [(0, "اختر المستفيد...")] + [(row.id, row.name) for row in recipients]
    form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    form.period_id.choices = [(row.id, period_option_label(row)) for row in open_periods]

    # Preserve compatibility with older already-open forms that still post date/period_code.
    if request.method == "POST" and not request.form.get("period_id"):
        legacy_date = _parse_date(request.form.get("business_date"))
        legacy_code = _clean_period_code(request.form.get("period_code"))
        legacy_period = db.session.scalar(select(BusinessPeriod).where(
            BusinessPeriod.business_date == legacy_date,
            BusinessPeriod.period_code == legacy_code,
            BusinessPeriod.status == "open",
        ))
        if legacy_period is not None:
            form.period_id.data = legacy_period.id

    if form.validate_on_submit():
        try:
            recipient = db.session.scalar(select(FreeRecipient).where(
                FreeRecipient.id == form.recipient_id.data,
                FreeRecipient.is_active.is_(True),
            ).with_for_update())
            product = db.session.scalar(select(Product).where(
                Product.id == form.product_id.data,
                Product.is_active.is_(True),
            ))
            period = db.session.scalar(select(BusinessPeriod).where(
                BusinessPeriod.id == form.period_id.data,
                BusinessPeriod.status == "open",
            ))
            if recipient is None or product is None or period is None:
                raise ValueError("المستفيد أو الصنف أو الفترة غير موجود أو غير مفتوح.")
            existing = db.session.scalar(select(FreeDistribution).where(
                FreeDistribution.period_id == period.id,
                FreeDistribution.recipient_id == recipient.id,
                FreeDistribution.product_id == product.id,
            ))
            statement = (form.statement.data or "").strip() or None
            if existing:
                existing.quantity = form.quantity.data
                existing.statement = statement
                existing.created_by_id = current_user.id
                flash("تم تحديث كمية الصرف المسجلة لهذا المستفيد في الفترة.", "success")
            else:
                db.session.add(FreeDistribution(
                    period_id=period.id,
                    recipient_id=recipient.id,
                    product_id=product.id,
                    quantity=form.quantity.data,
                    statement=statement,
                    created_by_id=current_user.id,
                ))
                flash("تم تسجيل الصرف المجاني ضمن الفترة المحددة.", "success")
            db.session.commit()
            return redirect(url_for("operations.free_distribution", period_id=period.id))
        except (ValueError, PeriodRuleError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
        except IntegrityError:
            db.session.rollback()
            flash("سبق تسجيل صرف لهذا المستفيد والصنف في الفترة؛ لم يُكرر.", "info")
    return _free_context(issue_form=form, action="issue")


def _closing_context(*, form=None, action=None, selected_date=None, selected_code=None, quantity_inputs=None, raw_material_inputs=None, calculation=None):
    selected_date = selected_date or _parse_date(request.args.get("date") or request.form.get("business_date"))
    selected_code = _clean_period_code(selected_code or request.args.get("period_code") or request.form.get("period_code"))
    period = db.session.scalar(select(BusinessPeriod).where(
        BusinessPeriod.business_date == selected_date,
        BusinessPeriod.period_code == selected_code,
    ))
    employees = db.session.scalars(select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.full_name.asc())).all()
    form = form or PeriodClosingForm()
    form.employee_id.choices = [(0, "اختر المستلم...")] + [(row.id, row.full_name) for row in employees]
    if request.method == "GET":
        form.employee_id.data = 0
        form.received_amount.data = ""
        form.expenses_amount.data = "0"
        form.handed_to_cash_amount.data = ""
    closed_rows, handover = ([], None)
    closed_material_rows = []
    base_rows = []
    base_material_rows = []
    if period and period.status == "closed":
        closed_rows, handover = get_closed_period_summary(period)
        closed_material_rows = get_closed_raw_material_summary(period)
    elif period and period.status == "open":
        try:
            base_rows = preview_period_close(period)
            base_material_rows = preview_raw_material_balances(period)
        except ClosingRuleError as exc:
            flash(str(exc), "error")
            base_rows = []
            base_material_rows = []
    quantity_inputs = quantity_inputs or {}
    raw_material_inputs = raw_material_inputs or {}
    return render_template(
        "operations/closing.html",
        period=period,
        employees=employees,
        form=form,
        selected_date=selected_date,
        selected_code=selected_code,
        selected_period_label=period_label(selected_code),
        period_choices=_period_choices(),
        closed_rows=closed_rows,
        closed_material_rows=closed_material_rows,
        handover=handover,
        base_rows=base_rows,
        base_material_rows=base_material_rows,
        quantity_inputs=quantity_inputs,
        raw_material_inputs=raw_material_inputs,
        calculation=calculation,
        show_details=action in {"details", "calculate"} or (period is not None and period.status == "open" and request.method == "POST"),
        show_calculation=action == "calculate" and calculation is not None,
    )


@operations_bp.route("/closing/", methods=["GET", "POST"])
@login_required
def closing():
    _require("handover.manage")
    selected_date = _parse_date(request.args.get("date") or request.form.get("business_date"))
    selected_code = _clean_period_code(request.args.get("period_code") or request.form.get("period_code"))
    form = PeriodClosingForm()
    form.employee_id.choices = [(0, "اختر المستلم...")] + [
        (row.id, row.full_name) for row in db.session.scalars(
            select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.full_name.asc())
        ).all()
    ]
    action = request.form.get("action") if request.method == "POST" else request.args.get("action")
    quantity_inputs = {}
    raw_material_inputs = {}
    calculation = None
    if request.method == "POST":
        form.process(request.form)
        form.employee_id.choices = [(0, "اختر المستلم...")] + [
            (row.id, row.full_name) for row in db.session.scalars(
                select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.full_name.asc())
            ).all()
        ]
        period = db.session.scalar(select(BusinessPeriod).where(
            BusinessPeriod.business_date == selected_date,
            BusinessPeriod.period_code == selected_code,
        ))
        if period is None:
            flash("لا توجد فترة مفتوحة لهذا التاريخ. سجّل الإنتاج أو عملية للفترة أولًا.", "error")
            return _closing_context(form=form, selected_date=selected_date, selected_code=selected_code)
        if period.status != "open":
            flash("الفترة مختتمة بالفعل ولا يمكن تعديلها.", "info")
            return _closing_context(selected_date=selected_date, selected_code=selected_code)
        if action in {"details", "calculate", "close"} and not form.validate():
            return _closing_context(form=form, action=action, selected_date=selected_date, selected_code=selected_code)
        products = db.session.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())).all()
        quantity_inputs = {
            product.id: {
                "damaged": request.form.get(f"damaged_{product.id}", "0"),
                "carried": request.form.get(f"carried_{product.id}", "0"),
            }
            for product in products
        }
        damaged = {product_id: values["damaged"] for product_id, values in quantity_inputs.items()}
        carried = {product_id: values["carried"] for product_id, values in quantity_inputs.items()}
        material_preview = preview_raw_material_balances(period)
        raw_material_inputs = {
            row["item_id"]: request.form.get(f"raw_ending_{row['item_id']}", "")
            for row in material_preview
        }
        if action == "close":
            try:
                handover, rows, expected = close_period_with_handover(
                    period_id=period.id,
                    employee_id=form.employee_id.data,
                    received_amount=form.received_amount.data,
                    expenses_amount=form.expenses_amount.data,
                    handed_to_cash_amount=form.handed_to_cash_amount.data,
                    damaged_quantities=damaged,
                    carried_quantities=carried,
                    raw_material_endings=raw_material_inputs,
                    statement=form.statement.data,
                    actor_id=current_user.id,
                )
                flash("تم إقفال الفترة وترحيل المتبقي وتسجيل التسليم والخرجيات.", "success")
                return redirect(url_for("operations.closing", date=selected_date.isoformat(), period_code=selected_code))
            except (ClosingRuleError, PeriodRuleError) as exc:
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                flash("تعذر إقفال الفترة. لم يتم تأكيد التسجيل.", "error")
        elif action == "calculate":
            try:
                rows, expected = calculate_close_rows(period, damaged, carried)
                material_rows = calculate_raw_material_close_rows(period, raw_material_inputs)
                received = Decimal(str(form.received_amount.data or 0))
                calculation = {
                    "rows": rows,
                    "material_rows": material_rows,
                    "expected": expected,
                    "received": received,
                    "difference": expected - received,
                    "expenses": Decimal(str(form.expenses_amount.data or 0)),
                    "handed": Decimal(str(form.handed_to_cash_amount.data or 0)),
                }
            except (ClosingRuleError, ValueError) as exc:
                flash(str(exc), "error")
                action = "details"
    return _closing_context(
        form=form,
        action=action,
        selected_date=selected_date,
        selected_code=selected_code,
        quantity_inputs=quantity_inputs,
        raw_material_inputs=raw_material_inputs,
        calculation=calculation,
    )


def _period_report_permission():
    if not any(current_user.has_permission(code) for code in (
        "handover.manage", "free_distribution.manage", "distribution.reports",
        "reports.view", "reports.export", "production.view", "production.manage",
    )):
        abort(403)


@operations_bp.get("/periods/")
@login_required
def periods_report():
    _period_report_permission()
    selectable_open_periods(actor_id=current_user.id)
    rows = db.session.scalars(
        select(BusinessPeriod).order_by(
            BusinessPeriod.business_date.desc(),
            BusinessPeriod.opened_at.desc(),
            BusinessPeriod.id.desc(),
        ).limit(120)
    ).all()
    summaries = []
    for period_row in rows:
        issue_totals = db.session.execute(select(
            func.coalesce(func.sum(DistributionIssue.quantity), 0),
            func.coalesce(func.sum(DistributionIssue.total_amount), 0),
        ).where(
            DistributionIssue.business_date == period_row.business_date,
            DistributionIssue.period_code == period_row.period_code,
        )).one()
        payments = db.session.scalar(select(func.coalesce(func.sum(PartyPayment.amount), 0)).where(
            PartyPayment.business_date == period_row.business_date,
            PartyPayment.period_code == period_row.period_code,
        )) or 0
        free_quantity = db.session.scalar(select(func.coalesce(func.sum(FreeDistribution.quantity), 0)).where(
            FreeDistribution.period_id == period_row.id,
        )) or 0
        production_quantity = db.session.scalar(select(func.coalesce(func.sum(DoughBatch.produced_quantity), 0)).where(
            DoughBatch.period_id == period_row.id,
        )) or 0
        handover = db.session.scalar(select(PeriodHandover).where(PeriodHandover.period_id == period_row.id))
        summaries.append({
            "period": period_row,
            "weekday": period_day_name(period_row.business_date),
            "issue_quantity": Decimal(str(issue_totals[0] or 0)),
            "issue_amount": Decimal(str(issue_totals[1] or 0)),
            "payments": Decimal(str(payments)),
            "free_quantity": Decimal(str(free_quantity)),
            "produced_quantity": Decimal(str(production_quantity)),
            "handover": handover,
        })
    current_period = next((
        item["period"] for item in summaries
        if item["period"].status == "open"
        and item["period"].business_date == business_today()
        and item["period"].period_code == suggested_period_code()
    ), None)
    return render_template(
        "operations/periods.html",
        rows=summaries,
        current_period=current_period,
        period_option_label=period_option_label,
    )


@operations_bp.get("/periods/<int:period_id>")
@login_required
def period_detail(period_id):
    _period_report_permission()
    period = db.session.get(BusinessPeriod, period_id)
    if period is None:
        abort(404)
    issues = db.session.scalars(select(DistributionIssue).where(
        DistributionIssue.business_date == period.business_date,
        DistributionIssue.period_code == period.period_code,
    ).order_by(DistributionIssue.created_at.asc(), DistributionIssue.id.asc())).all()
    payments = db.session.scalars(select(PartyPayment).where(
        PartyPayment.business_date == period.business_date,
        PartyPayment.period_code == period.period_code,
    ).order_by(PartyPayment.created_at.asc(), PartyPayment.id.asc())).all()
    free_rows = db.session.scalars(select(FreeDistribution).where(
        FreeDistribution.period_id == period.id,
    ).order_by(FreeDistribution.created_at.asc(), FreeDistribution.id.asc())).all()
    batches = db.session.scalars(select(DoughBatch).where(
        DoughBatch.period_id == period.id,
    ).order_by(DoughBatch.created_at.asc(), DoughBatch.id.asc())).all()
    expenses = db.session.scalars(select(Expense).where(
        Expense.period_id == period.id,
    ).order_by(Expense.created_at.asc(), Expense.id.asc())).all()
    handover = db.session.scalar(select(PeriodHandover).where(PeriodHandover.period_id == period.id))
    opener = db.session.get(User, period.opened_by_id) if period.opened_by_id else None

    issue_quantity = sum((Decimal(str(row.quantity)) for row in issues), Decimal("0.000"))
    issue_amount = sum((Decimal(str(row.total_amount)) for row in issues), Decimal("0.00"))
    payment_amount = sum((Decimal(str(row.amount)) for row in payments), Decimal("0.00"))
    free_quantity = sum((Decimal(str(row.quantity)) for row in free_rows), Decimal("0.000"))
    production_quantity = sum((Decimal(str(row.produced_quantity)) for row in batches), Decimal("0.000"))

    cash_opening = db.session.execute(select(func.coalesce(func.sum(case(
        (CashMovement.direction == "in", CashMovement.amount), else_=-CashMovement.amount,
    )), 0)).where(
        (CashMovement.business_date < period.business_date)
        | ((CashMovement.business_date == period.business_date) & (CashMovement.created_at < period.opened_at))
    )).scalar_one()
    cash_opening = Decimal(str(cash_opening or 0))

    product_rows, material_rows, closed_rows = [], [], []
    if period.status == "closed":
        closed_rows, _saved_handover = get_closed_period_summary(period)
        material_rows = get_closed_raw_material_summary(period)
    else:
        try:
            for row in preview_period_close(period):
                available = Decimal(str(row["available_quantity"]))
                used = Decimal(str(row["paid_distribution_quantity"])) + Decimal(str(row["free_distribution_quantity"]))
                product_rows.append({
                    "product": row["product"],
                    "opening": row["opening_quantity"],
                    "produced": row["produced_quantity"],
                    "paid": row["paid_distribution_quantity"],
                    "free": row["free_distribution_quantity"],
                    "available": available,
                    "remaining": available - used,
                    "unit_label": row["product"].unit_label,
                })
            material_rows = preview_raw_material_balances(period)
        except ClosingRuleError as exc:
            flash(str(exc), "error")

    parties = {}
    for row in issues:
        item = parties.setdefault(row.party_id, {
            "party": row.party,
            "party_type": row.party.party_type,
            "quantity": Decimal("0.000"),
            "issued": Decimal("0.00"),
            "paid": Decimal("0.00"),
        })
        item["quantity"] += Decimal(str(row.quantity))
        item["issued"] += Decimal(str(row.total_amount))
    for row in payments:
        item = parties.setdefault(row.party_id, {
            "party": row.party,
            "party_type": row.party.party_type,
            "quantity": Decimal("0.000"),
            "issued": Decimal("0.00"),
            "paid": Decimal("0.00"),
        })
        item["paid"] += Decimal(str(row.amount))
    for party_id, item in parties.items():
        entries = db.session.scalars(select(PartyLedgerEntry).where(
            PartyLedgerEntry.party_id == party_id,
        )).all()
        item["remaining_due"] = sum(
            (Decimal(str(entry.debit_amount or 0)) - Decimal(str(entry.credit_amount or 0)) for entry in entries),
            Decimal("0.00"),
        )

    return render_template(
        "operations/period_detail.html",
        period=period,
        weekday=period_day_name(period.business_date),
        opener=opener,
        issues=issues,
        payments=payments,
        free_rows=free_rows,
        batches=batches,
        expenses=expenses,
        handover=handover,
        paid_quantity=issue_quantity,
        paid_amount=issue_amount,
        payment_amount=payment_amount,
        free_quantity=free_quantity,
        production_quantity=production_quantity,
        cash_opening=cash_opening,
        product_rows=product_rows,
        closed_rows=closed_rows,
        material_rows=material_rows,
        party_summaries=sorted(parties.values(), key=lambda item: (item["party_type"], item["party"].name.casefold())),
        period_label=period_label,
    )
