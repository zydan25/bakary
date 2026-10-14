"""Free-distribution records and period close/handover screens."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.closing import PeriodCloseProduct, PeriodHandover
from app.models.employee import Employee
from app.models.free_distribution import FreeDistribution, FreeRecipient
from app.models.production import BusinessPeriod
from app.models.product import Product
from app.operations import operations_bp
from app.operations.forms import FreeIssueForm, FreeRecipientForm, PeriodClosingForm
from app.services.closing import (
    ClosingRuleError,
    calculate_close_rows,
    close_period_with_handover,
    get_closed_period_summary,
)
from app.services.periods import PeriodRuleError, get_or_create_open_period, period_label, period_mode, suggested_period_code


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else date.today()
    except (TypeError, ValueError):
        return date.today()


def _period_choices():
    return [("daily", "اليوم كاملًا")] if period_mode() == "daily" else [
        ("morning", "الفترة الصباحية"), ("evening", "الفترة المسائية")
    ]


def _clean_period_code(value):
    codes = {code for code, _label in _period_choices()}
    return value if value in codes else suggested_period_code()


def _free_context(*, recipient_form=None, issue_form=None, action=None, selected_date=None, selected_code=None):
    selected_date = selected_date or _parse_date(request.args.get("date") or request.form.get("business_date"))
    selected_code = _clean_period_code(selected_code or request.args.get("period_code") or request.form.get("period_code"))
    recipients = db.session.scalars(
        select(FreeRecipient).where(FreeRecipient.is_active.is_(True)).order_by(FreeRecipient.name.asc())
    ).all()
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    period = db.session.scalar(
        select(BusinessPeriod).where(
            BusinessPeriod.business_date == selected_date,
            BusinessPeriod.period_code == selected_code,
        )
    )
    records = []
    if period:
        records = db.session.scalars(
            select(FreeDistribution).where(FreeDistribution.period_id == period.id)
            .order_by(FreeDistribution.created_at.desc(), FreeDistribution.id.desc())
        ).all()

    recipient_form = recipient_form or FreeRecipientForm()
    issue_form = issue_form or FreeIssueForm()
    issue_form.recipient_id.choices = [(0, "اختر المستفيد...")] + [(row.id, row.name) for row in recipients]
    issue_form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    issue_form.period_code.choices = _period_choices()
    if request.method == "GET" and issue_form.recipient_id.data in (None, 0):
        issue_form.recipient_id.data = request.args.get("recipient_id", type=int) or 0
    if request.method == "GET" and issue_form.product_id.data in (None, 0):
        default_product = next((row for row in products if row.is_default), products[0] if products else None)
        issue_form.product_id.data = default_product.id if default_product else 0
    if request.method == "GET":
        issue_form.business_date.data = selected_date
        issue_form.period_code.data = selected_code
        issue_form.quantity.data = None
    return render_template(
        "operations/free_distribution.html",
        recipients=recipients,
        products=products,
        records=records,
        period=period,
        selected_date=selected_date,
        selected_code=selected_code,
        selected_period_label=period_label(selected_code),
        period_choices=_period_choices(),
        recipient_form=recipient_form,
        issue_form=issue_form,
        show_recipient_form=action == "recipient" or (recipient_form is not None and bool(recipient_form.errors)),
        show_issue_form=action == "issue" or (issue_form is not None and bool(issue_form.errors)),
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
    if form.validate_on_submit():
        recipient = FreeRecipient(
            name=form.name.data.strip(),
            notes=(form.notes.data or "").strip() or None,
            is_active=True,
            created_by_id=current_user.id,
        )
        db.session.add(recipient)
        db.session.commit()
        flash("تمت إضافة المستفيد المجاني.", "success")
        return redirect(url_for("operations.free_distribution"))
    return _free_context(recipient_form=form, action="recipient")


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
    # Choices are set before WTForms validates selected values.
    recipients = db.session.scalars(select(FreeRecipient).where(FreeRecipient.is_active.is_(True)).order_by(FreeRecipient.name.asc())).all()
    products = db.session.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())).all()
    form.recipient_id.choices = [(0, "اختر المستفيد...")] + [(row.id, row.name) for row in recipients]
    form.product_id.choices = [(0, "اختر الصنف...")] + [(row.id, row.name) for row in products]
    form.period_code.choices = _period_choices()
    if form.validate_on_submit():
        try:
            recipient = db.session.scalar(select(FreeRecipient).where(
                FreeRecipient.id == form.recipient_id.data, FreeRecipient.is_active.is_(True)
            ).with_for_update())
            product = db.session.scalar(select(Product).where(
                Product.id == form.product_id.data, Product.is_active.is_(True)
            ))
            if recipient is None or product is None:
                raise ValueError("المستفيد أو الصنف غير موجود أو موقوف.")
            period, _created = get_or_create_open_period(
                business_date=form.business_date.data,
                period_code=form.period_code.data,
                actor_id=current_user.id,
            )
            existing = db.session.scalar(select(FreeDistribution).where(
                FreeDistribution.period_id == period.id,
                FreeDistribution.recipient_id == recipient.id,
                FreeDistribution.product_id == product.id,
            ))
            if existing:
                raise ValueError("تم تسجيل صرف هذا الصنف لهذا المستفيد في الفترة نفسها بالفعل.")
            record = FreeDistribution(
                period_id=period.id,
                recipient_id=recipient.id,
                product_id=product.id,
                quantity=form.quantity.data,
                statement=(form.statement.data or "").strip() or None,
                created_by_id=current_user.id,
            )
            db.session.add(record)
            db.session.commit()
            flash("تم تسجيل الصرف المجاني واحتسابه ضمن الفترة.", "success")
            return redirect(url_for(
                "operations.free_distribution",
                date=form.business_date.data.isoformat(),
                period_code=form.period_code.data,
            ))
        except (ValueError, PeriodRuleError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
        except IntegrityError:
            db.session.rollback()
            flash("سبق تسجيل صرف لهذا المستفيد والصنف في الفترة؛ لم يُكرر.", "info")
    return _free_context(issue_form=form, action="issue")


def _closing_context(*, form=None, action=None, selected_date=None, selected_code=None, quantity_inputs=None, calculation=None):
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
    if period and period.status == "closed":
        closed_rows, handover = get_closed_period_summary(period)
    quantity_inputs = quantity_inputs or {}
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
        handover=handover,
        quantity_inputs=quantity_inputs,
        calculation=calculation,
        show_details=action in {"details", "calculate"} or (period is not None and period.status == "open" and request.method == "POST"),
        show_calculation=action == "calculate" and calculation is not None,
    )


@operations_bp.route("/closing/", methods=["GET", "POST"])
@login_required
def closing():
    _require("production.manage")
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
                received = Decimal(str(form.received_amount.data or 0))
                calculation = {
                    "rows": rows,
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
        calculation=calculation,
    )
