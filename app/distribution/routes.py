"""Issue, payment, daily issue reports, and party ledger reports."""

from datetime import date, datetime
from app.services.clock import business_today
from decimal import Decimal
from uuid import uuid4

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.distribution import distribution_bp
from app.distribution.forms import IssueForm, PaymentForm
from app.extensions import db
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
from app.models.production import BusinessPeriod
from app.models.party import Party
from app.models.product import Product
from app.services.amount_words import amount_to_arabic_words, quantity_to_arabic_words
from app.services.ledger import (
    BusinessRuleError,
    create_issue,
    create_payment,
    last_issue,
    money,
    party_balance,
    party_period_summary,
)
from app.services.periods import PeriodRuleError, get_or_create_open_period, period_label, suggested_period_code, selectable_open_periods, period_option_label, period_day_name


PARTY_LABELS = {
    "distributor": {"title": "صرف موزع", "plural": "الموزعون", "plural_genitive": "الموزعين", "singular": "الموزع"},
    "customer": {"title": "صرف عميل", "plural": "العملاء والنقاط", "singular": "العميل"},
    "all": {"title": "صرف عام", "plural": "الموزعون والعملاء", "plural_genitive": "الموزعين والعملاء", "singular": "الحساب"},
}


def _valid_party_type(party_type):
    if party_type not in PARTY_LABELS:
        abort(404)
    return PARTY_LABELS[party_type]


def _require(permission):
    if not current_user.has_permission(permission):
        abort(403)


def _party_choices(party_type):
    statement = select(Party).where(Party.is_active.is_(True))
    if party_type != "all":
        statement = statement.where(Party.party_type == party_type)
    parties = db.session.scalars(statement.order_by(Party.name.asc())).all()
    labels = [
        (party.id, f"{party.name} — {'موزع' if party.party_type == 'distributor' else 'عميل'}" if party_type == "all" else party.name)
        for party in parties
    ]
    return [(0, "اختر الحساب...")] + labels, parties


def _product_choices():
    products = db.session.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    return [(0, "اختر الصنف...")] + [(product.id, product.name) for product in products], products


def _parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


@distribution_bp.route("/issue/<party_type>", methods=["GET", "POST"])
@login_required
def issue(party_type):
    meta = _valid_party_type(party_type)
    _require("distribution.issue")
    form = IssueForm()
    party_choices, parties = _party_choices(party_type)
    product_choices, products = _product_choices()
    periods = selectable_open_periods(actor_id=current_user.id)
    form.party_id.choices = party_choices
    form.product_id.choices = product_choices
    form.period_id.choices = [(row.id, period_option_label(row)) for row in periods]

    requested_party_id = request.args.get("party_id", type=int)
    if request.method == "GET":
        form.party_id.data = requested_party_id if requested_party_id and any(p.id == requested_party_id for p in parties) else 0
        default_product = next((p for p in products if p.is_default), products[0] if products else None)
        form.product_id.data = default_product.id if default_product else 0
        form.quantity.data = None
        form.period_id.data = periods[0].id if periods else 0
        form.request_key.data = uuid4().hex
    else:
        if not form.request_key.data:
            form.request_key.data = uuid4().hex
        # Accept forms opened before the period selector rollout, but only map them to an
        # already-open matching period. New forms post period_id directly.
        if not request.form.get("period_id") and request.form.get("business_date"):
            legacy_date = _parse_date(request.form.get("business_date"), business_today())
            legacy_code = request.form.get("period_code") or suggested_period_code()
            legacy_period = db.session.scalar(select(BusinessPeriod).where(
                BusinessPeriod.business_date == legacy_date,
                BusinessPeriod.period_code == legacy_code,
                BusinessPeriod.status == "open",
            ))
            if legacy_period is None:
                try:
                    legacy_period, _created = get_or_create_open_period(
                        business_date=legacy_date, period_code=legacy_code, actor_id=current_user.id
                    )
                except PeriodRuleError:
                    legacy_period = None
            if legacy_period:
                form.period_id.data = legacy_period.id

    if request.method == "POST" and form.validate_on_submit():
        try:
            period = db.session.scalar(select(BusinessPeriod).where(
                BusinessPeriod.id == form.period_id.data,
                BusinessPeriod.status == "open",
            ))
            if period is None:
                raise PeriodRuleError("الفترة المختارة غير مفتوحة؛ اختر فترة أخرى.")
            transaction, created = create_issue(
                party_id=form.party_id.data,
                product_id=form.product_id.data,
                quantity=form.quantity.data,
                business_date=period.business_date,
                period_code=period.period_code,
                statement=form.statement.data,
                actor_id=current_user.id,
                request_key=form.request_key.data,
            )
            if created:
                flash(
                    f"تم تسجيل صرف {transaction.quantity} {transaction.product.unit_label} إلى {transaction.party.name} بنجاح.",
                    "success",
                )
            else:
                flash("تم استلام طلب الصرف سابقًا؛ لم يُسجّل مرة أخرى.", "info")
            return redirect(url_for("distribution.issue", party_type=party_type, saved=transaction.id))
        except (BusinessRuleError, PeriodRuleError) as exc:
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            flash("تعذر تسجيل الصرف. لم يتم تأكيد الحفظ؛ تحقق من البيانات وحاول مجددًا.", "error")

    chosen_party = next((p for p in parties if p.id == form.party_id.data), None)
    chosen_product = next((p for p in products if p.id == form.product_id.data), None)
    chosen_period = next((p for p in periods if p.id == form.period_id.data), None)
    default_price = None
    last = None
    if chosen_party is not None and chosen_product is not None:
        default_price = chosen_party.price_for(chosen_product)
        last = last_issue(chosen_party.id)
    saved_id = request.args.get("saved", type=int)
    saved_transaction = db.session.get(DistributionIssue, saved_id) if saved_id else None
    if saved_transaction and party_type != "all" and saved_transaction.party.party_type != party_type:
        saved_transaction = None
    return render_template(
        "distribution/issue.html",
        party_type=party_type,
        meta=meta,
        form=form,
        parties=parties,
        products=products,
        chosen_party=chosen_party,
        chosen_product=chosen_product,
        chosen_period=chosen_period,
        default_price=default_price,
        last_issue=last,
        period_label=period_option_label(chosen_period) if chosen_period else "لا توجد فترة مفتوحة",
        period_day_name=period_day_name,
        saved_transaction=saved_transaction,
        show_form=True,
    )


@distribution_bp.get("/quote")
@login_required
def quote():
    _require("distribution.issue")
    party_type = request.args.get("party_type", "")
    if party_type not in PARTY_LABELS:
        return jsonify({"ok": False, "message": "نوع الحساب غير صالح."}), 400
    party_statement = select(Party).where(
        Party.id == request.args.get("party_id", type=int),
        Party.is_active.is_(True),
    )
    if party_type != "all":
        party_statement = party_statement.where(Party.party_type == party_type)
    party = db.session.scalar(party_statement)
    product = db.session.scalar(
        select(Product).where(
            Product.id == request.args.get("product_id", type=int),
            Product.is_active.is_(True),
        )
    )
    if party is None or product is None:
        return jsonify({"ok": False, "message": "اختر الحساب والصنف أولًا."}), 400
    try:
        quantity = int(request.args.get("quantity", "0") or 0)
        if quantity < 0:
            quantity = 0
    except (TypeError, ValueError):
        quantity = 0
    unit_price = money(party.price_for(product))
    total = money(unit_price * quantity)
    last = last_issue(party.id)
    last_data = None
    if last:
        created = last.created_at
        last_data = {
            "quantity": last.quantity,
            "unit": last.product.unit_label,
            "product": last.product.name,
            "time": created.strftime("%Y-%m-%d %H:%M") if created else "",
        }
    return jsonify({
        "ok": True,
        "party": party.name,
        "product": product.name,
        "unit": product.unit_label,
        "unit_price": str(unit_price),
        "total": str(total),
        "total_words": amount_to_arabic_words(total),
        "quantity_words": quantity_to_arabic_words(quantity, product.unit_label) if quantity else "",
        "last_issue": last_data,
        "price_ready": unit_price > 0,
        "message": None if unit_price > 0 else "سعر الصنف لهذا الحساب يساوي صفرًا؛ اضبط السعر أولًا.",
    })


@distribution_bp.route("/payment/<party_type>", methods=["GET", "POST"])
@login_required
def payment(party_type):
    meta = _valid_party_type(party_type)
    _require("distribution.payment")
    form = PaymentForm()
    choices, parties = _party_choices(party_type)
    periods = selectable_open_periods(actor_id=current_user.id)
    form.party_id.choices = choices
    form.period_id.choices = [(row.id, period_option_label(row)) for row in periods]
    requested_party_id = request.args.get("party_id", type=int)
    if request.method == "GET":
        form.party_id.data = requested_party_id if requested_party_id and any(p.id == requested_party_id for p in parties) else 0
        form.amount.data = ""
        form.period_id.data = periods[0].id if periods else 0
        form.request_key.data = uuid4().hex
    else:
        if not form.request_key.data:
            form.request_key.data = uuid4().hex
        if not request.form.get("period_id") and request.form.get("business_date"):
            legacy_date = _parse_date(request.form.get("business_date"), business_today())
            legacy_code = request.form.get("period_code") or suggested_period_code()
            legacy_period = db.session.scalar(select(BusinessPeriod).where(
                BusinessPeriod.business_date == legacy_date,
                BusinessPeriod.period_code == legacy_code,
                BusinessPeriod.status == "open",
            ))
            if legacy_period is None:
                try:
                    legacy_period, _created = get_or_create_open_period(
                        business_date=legacy_date, period_code=legacy_code, actor_id=current_user.id
                    )
                except PeriodRuleError:
                    legacy_period = None
            if legacy_period:
                form.period_id.data = legacy_period.id

    receipt = None
    receipt_id = request.args.get("receipt", type=int)
    if receipt_id:
        saved = db.session.get(PartyPayment, receipt_id)
        if saved and (party_type == "all" or saved.party.party_type == party_type):
            before = party_balance(saved.party_id) + Decimal(str(saved.amount))
            after = party_balance(saved.party_id)
            summary = party_period_summary(saved.party_id, saved.business_date, saved.business_date)
            receipt = {
                "id": saved.id, "party": saved.party, "amount": saved.amount,
                "business_date": saved.business_date, "statement": saved.statement,
                "quantity": summary["quantity"], "issue_total": summary["issue_total"],
                "balance_before": before, "balance_after": after, "created_at": saved.created_at,
            }

    if request.method == "POST" and form.validate_on_submit():
        try:
            period = db.session.scalar(select(BusinessPeriod).where(
                BusinessPeriod.id == form.period_id.data,
                BusinessPeriod.status == "open",
            ))
            if period is None:
                raise PeriodRuleError("الفترة المختارة غير مفتوحة؛ اختر فترة أخرى.")
            transaction, created = create_payment(
                party_id=form.party_id.data,
                amount=form.amount.data,
                business_date=period.business_date,
                period_code=period.period_code,
                statement=form.statement.data,
                actor_id=current_user.id,
                request_key=form.request_key.data,
            )
            if created:
                flash(f"تم تسجيل دفع {transaction.amount} ريال إلى حساب الصندوق بنجاح.", "success")
            else:
                flash("تم استلام طلب الدفع سابقًا؛ لم يُسجّل مرة أخرى.", "info")
            return redirect(url_for("distribution.payment", party_type=party_type, receipt=transaction.id))
        except (BusinessRuleError, PeriodRuleError) as exc:
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            flash("تعذر تسجيل الدفع. لم يتم تأكيد الحفظ؛ تحقق من البيانات وحاول مجددًا.", "error")

    chosen_party = next((p for p in parties if p.id == form.party_id.data), None)
    chosen_period = next((p for p in periods if p.id == form.period_id.data), None)
    payment_summary = None
    if chosen_party and chosen_period:
        try:
            period_summary = party_period_summary(
                chosen_party.id, chosen_period.business_date, chosen_period.business_date
            )
            payment_summary = {**period_summary, "current_balance": party_balance(chosen_party.id)}
        except BusinessRuleError:
            payment_summary = None
    return render_template(
        "distribution/payment.html",
        party_type=party_type, meta=meta, form=form, parties=parties,
        chosen_party=chosen_party, chosen_period=chosen_period,
        payment_summary=payment_summary,
        period_label=period_option_label(chosen_period) if chosen_period else "لا توجد فترة مفتوحة",
        period_day_name=period_day_name,
        receipt=receipt, show_form=True,
    )


@distribution_bp.get("/payment-summary/<party_type>/<int:party_id>")
@login_required
def payment_summary(party_type, party_id):
    _valid_party_type(party_type)
    _require("distribution.payment")
    payment_party_query = select(Party).where(Party.id == party_id, Party.is_active.is_(True))
    if party_type != "all":
        payment_party_query = payment_party_query.where(Party.party_type == party_type)
    party = db.session.scalar(payment_party_query)
    if party is None:
        return jsonify({"ok": False, "message": "الحساب غير موجود أو موقوف."}), 404
    selected_period_id = request.args.get("period_id", type=int)
    selected_period = db.session.scalar(select(BusinessPeriod).where(
        BusinessPeriod.id == selected_period_id,
        BusinessPeriod.status == "open",
    )) if selected_period_id else None
    business_date = selected_period.business_date if selected_period else _parse_date(request.args.get("date"), business_today())
    try:
        summary = party_period_summary(party.id, business_date, business_date)
    except BusinessRuleError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    current_balance = party_balance(party.id)
    return jsonify({
        "ok": True,
        "party": party.name,
        "quantity": str(summary["quantity"]),
        "unit_price": str(summary["unit_price"]) if summary["unit_price"] is not None else None,
        "issue_total": str(summary["issue_total"]),
        "arrears": str(summary["arrears"]),
        "total_due": str(summary["total_due"]),
        "payment_total": str(summary["payment_total"]),
        "current_balance": str(current_balance),
        "balance_label": "عليه" if current_balance > 0 else ("له" if current_balance < 0 else "متزن"),
        "total_due_words": amount_to_arabic_words(summary["total_due"]),
    })


def _report_rows(party_type, selected_date, party_id=None):
    statement = (
        select(DistributionIssue)
        .join(Party, DistributionIssue.party_id == Party.id)
        .where(Party.party_type == party_type, DistributionIssue.business_date == selected_date)
    )
    if party_id:
        statement = statement.where(DistributionIssue.party_id == party_id)
    return db.session.scalars(
        statement.order_by(DistributionIssue.created_at.desc(), DistributionIssue.id.desc())
    ).all()


@distribution_bp.get("/reports/issues/<party_type>")
@login_required
def issue_report(party_type):
    meta = _valid_party_type(party_type)
    _require("distribution.reports")
    selected_date = _parse_date(request.args.get("date"), business_today())
    party_id = request.args.get("party_id", type=int)
    summary_only = request.args.get("summary_only") == "1"
    parties = db.session.scalars(
        select(Party).where(Party.party_type == party_type).order_by(Party.name.asc())
    ).all()
    rows = _report_rows(party_type, selected_date, party_id)
    totals = {
        "quantity": sum((Decimal(row.quantity) for row in rows), Decimal("0")),
        "amount": sum((Decimal(str(row.total_amount)) for row in rows), Decimal("0.00")),
    }
    summaries = {}
    for row in rows:
        entry = summaries.setdefault(row.party_id, {
            "party": row.party,
            "quantity": Decimal("0"),
            "amount": Decimal("0.00"),
            "count": 0,
        })
        entry["quantity"] += Decimal(row.quantity)
        entry["amount"] += Decimal(str(row.total_amount))
        entry["count"] += 1
    summary_rows = sorted(summaries.values(), key=lambda value: value["party"].name.casefold())
    return render_template(
        "distribution/issue_report.html",
        meta=meta,
        party_type=party_type,
        parties=parties,
        selected_date=selected_date,
        selected_party_id=party_id,
        rows=rows,
        totals=totals,
        summary_rows=summary_rows,
        summary_only=summary_only,
    )


@distribution_bp.get("/reports/statement/<party_type>/<int:party_id>")
@login_required
def party_statement(party_type, party_id):
    meta = _valid_party_type(party_type)
    _require("distribution.reports")
    party = db.session.scalar(
        select(Party).where(Party.id == party_id, Party.party_type == party_type)
    )
    if party is None:
        abort(404)
    today = business_today()
    start_date = _parse_date(request.args.get("start"), today)
    end_date = _parse_date(request.args.get("end"), today)
    if start_date > end_date:
        flash("تاريخ البداية يجب ألا يتجاوز تاريخ النهاية.", "error")
        start_date, end_date = end_date, start_date

    opening = party_balance(party_id, before_date=start_date)
    entries = db.session.scalars(
        select(PartyLedgerEntry)
        .where(
            PartyLedgerEntry.party_id == party_id,
            PartyLedgerEntry.business_date >= start_date,
            PartyLedgerEntry.business_date <= end_date,
        )
        .order_by(PartyLedgerEntry.business_date.asc(), PartyLedgerEntry.created_at.asc(), PartyLedgerEntry.id.asc())
    ).all()
    issue_ids = [entry.source_id for entry in entries if entry.source_type == "distribution_issue"]
    payment_ids = [entry.source_id for entry in entries if entry.source_type == "party_payment"]
    issues = {
        row.id: row for row in db.session.scalars(select(DistributionIssue).where(DistributionIssue.id.in_(issue_ids))).all()
    } if issue_ids else {}
    payments = {
        row.id: row for row in db.session.scalars(select(PartyPayment).where(PartyPayment.id.in_(payment_ids))).all()
    } if payment_ids else {}

    running = opening
    statement_rows = []
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    for entry in entries:
        debit = Decimal(str(entry.debit_amount or 0))
        credit = Decimal(str(entry.credit_amount or 0))
        running += debit - credit
        source = None
        description = entry.statement or ("صرف بضاعة" if debit else "دفع نقدي")
        quantity = None
        unit_price = None
        if entry.source_type == "distribution_issue":
            source = issues.get(entry.source_id)
            if source:
                description = f"صرف {source.product.name}" + (f" — {source.statement}" if source.statement else "")
                quantity = source.quantity
                unit_price = source.unit_price
        elif entry.source_type == "party_payment":
            source = payments.get(entry.source_id)
            if source:
                description = source.statement or "دفع نقدي"
        debit_total += debit
        credit_total += credit
        statement_rows.append({
            "entry": entry,
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "debit": debit,
            "credit": credit,
            "balance": running,
        })

    return render_template(
        "distribution/statement.html",
        meta=meta,
        party=party,
        party_type=party_type,
        start_date=start_date,
        end_date=end_date,
        opening_balance=opening,
        entries=statement_rows,
        debit_total=debit_total,
        credit_total=credit_total,
        closing_balance=running,
    )
