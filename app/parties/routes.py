"""Distributor and customer profile routes.

Party profiles share one data model and service layer but retain separate URLs,
permissions and labels. Each party receives a price row per active baked product
when created, initialized from that party type's current global prices.
"""

from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.models.distribution import PartyLedgerEntry
from app.models.party import Party
from app.models.product import Product
from app.parties import parties_bp
from app.parties.forms import PartyForm
from app.services.parties import PartyRuleError, list_parties, save_party, set_party_active


PARTY_META = {
    "distributor": {
        "endpoint": "parties.distributors",
        "toggle_endpoint": "parties.toggle_distributor",
        "title": "الموزعون",
        "singular": "الموزع",
        "new_action": "إضافة موزع",
        "empty_title": "لا يوجد موزعون هنا",
        "empty_body": "أضف موزعًا لتحديد أسعاره الخاصة ومتابعة حسابه.",
    },
    "customer": {
        "endpoint": "parties.customers",
        "toggle_endpoint": "parties.toggle_customer",
        "title": "العملاء والنقاط",
        "singular": "العميل",
        "new_action": "إضافة عميل",
        "empty_title": "لا يوجد عملاء هنا",
        "empty_body": "أضف عميلًا أو نقطة بيع وحدد الأسعار المناسبة لها.",
    },
}


def _can_view_parties():
    return current_user.has_permission("parties.view") or current_user.has_permission("parties.manage")


def _party_page(party_type):
    if not _can_view_parties():
        abort(403)

    meta = PARTY_META[party_type]
    can_manage = current_user.has_permission("parties.manage")
    query = (request.args.get("q") or "").strip()
    status = request.args.get("status", "active")
    if status not in {"active", "inactive", "all"}:
        status = "active"
    sort = request.args.get("sort", "name")
    if sort not in {"name", "name_desc", "newest", "oldest", "balance_high", "balance_low"}:
        sort = "name"

    form = PartyForm()
    action = request.args.get("action", "")
    edit_id = request.args.get("edit", type=int)
    selected_party = None
    products = db.session.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.is_default.desc(), Product.name.asc())
    ).all()

    if request.method == "POST":
        if not can_manage:
            abort(403)
        raw_party_id = (request.form.get("party_id") or "").strip()
        party_id = int(raw_party_id) if raw_party_id.isdigit() else None
        if form.validate_on_submit():
            prices = {
                str(product.id): request.form.get(f"price_{product.id}", "")
                for product in products
                if f"price_{product.id}" in request.form
            }
            try:
                save_party(
                    party_type=party_type,
                    name=form.name.data,
                    phone=form.phone.data,
                    notes=form.notes.data,
                    prices=prices,
                    party_id=party_id,
                    actor_id=current_user.id,
                )
                flash(f"تم حفظ بيانات {meta['singular']} بنجاح.", "success")
                return redirect(url_for(meta["endpoint"], status=status, sort=sort, q=query or None))
            except PartyRuleError as exc:
                flash(str(exc), "error")
        action = "edit" if party_id else "new"
        edit_id = party_id

    if request.method == "GET" and action == "edit" and edit_id:
        selected_party = db.session.scalar(
            select(Party).where(Party.id == edit_id, Party.party_type == party_type)
        )
        if selected_party is None:
            abort(404)
        form.party_id.data = str(selected_party.id)
        form.name.data = selected_party.name
        form.phone.data = selected_party.phone or ""
        form.notes.data = selected_party.notes or ""

    if request.method == "POST" and edit_id:
        selected_party = db.session.scalar(
            select(Party).where(Party.id == edit_id, Party.party_type == party_type)
        )

    price_rows = []
    for product in products:
        default_price = product.default_price_for(party_type)
        field_name = f"price_{product.id}"
        if request.method == "POST" and field_name in request.form:
            value = request.form.get(field_name, "")
        elif selected_party is not None:
            value = str(selected_party.price_for(product))
        else:
            value = str(default_price)
        try:
            value_decimal = Decimal(str(value or default_price))
            custom = value_decimal != Decimal(str(default_price))
        except Exception:
            custom = False
        price_rows.append({
            "product": product,
            "value": value,
            "default_price": default_price,
            "is_custom": custom,
        })

    items = list_parties(party_type, query=query, status=status)
    balances = {}
    if items:
        rows = db.session.execute(
            select(
                PartyLedgerEntry.party_id,
                func.coalesce(func.sum(PartyLedgerEntry.debit_amount), 0),
                func.coalesce(func.sum(PartyLedgerEntry.credit_amount), 0),
            )
            .where(PartyLedgerEntry.party_id.in_([item.id for item in items]))
            .group_by(PartyLedgerEntry.party_id)
        ).all()
        for party_id, debit, credit in rows:
            balances[party_id] = Decimal(str(debit or 0)) - Decimal(str(credit or 0))
        for item in items:
            balances.setdefault(item.id, Decimal("0.00"))

    if sort == "name_desc":
        items.sort(key=lambda item: item.name.casefold(), reverse=True)
    elif sort == "newest":
        items.sort(key=lambda item: item.created_at, reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda item: item.created_at)
    elif sort == "balance_high":
        items.sort(key=lambda item: balances.get(item.id, Decimal("0.00")), reverse=True)
    elif sort == "balance_low":
        items.sort(key=lambda item: balances.get(item.id, Decimal("0.00")))

    return render_template(
        "parties/list.html",
        party_type=party_type,
        meta=meta,
        items=items,
        products=products,
        price_rows=price_rows,
        balances=balances,
        query=query,
        status=status,
        sort=sort,
        form=form,
        can_manage=can_manage,
        show_form=(action in {"new", "edit"}) or (request.method == "POST" and bool(form.errors)),
    )


@parties_bp.route("/distributors/", methods=["GET", "POST"])
@login_required
def distributors():
    return _party_page("distributor")


@parties_bp.route("/customers/", methods=["GET", "POST"])
@login_required
def customers():
    return _party_page("customer")


@parties_bp.get("/")
@login_required
def index():
    """Combined directory for distributors and customers."""
    if not _can_view_parties():
        abort(403)

    query = (request.args.get("q") or "").strip()
    status = request.args.get("status", "active")
    if status not in {"active", "inactive", "all"}:
        status = "active"
    type_filter = request.args.get("party_type", "all")
    if type_filter not in {"all", "distributor", "customer"}:
        type_filter = "all"
    sort = request.args.get("sort", "name")
    if sort not in {"name", "name_desc", "newest", "oldest", "balance_high", "balance_low"}:
        sort = "name"

    statement = select(Party)
    if status == "active":
        statement = statement.where(Party.is_active.is_(True))
    elif status == "inactive":
        statement = statement.where(Party.is_active.is_(False))
    if type_filter != "all":
        statement = statement.where(Party.party_type == type_filter)
    if query:
        needle = "%" + query + "%"
        statement = statement.where(
            or_(Party.name.ilike(needle), Party.phone.ilike(needle))
        )
    items = db.session.scalars(statement.order_by(Party.name.asc())).all()

    balances = {}
    if items:
        rows = db.session.execute(
            select(
                PartyLedgerEntry.party_id,
                func.coalesce(func.sum(PartyLedgerEntry.debit_amount), 0),
                func.coalesce(func.sum(PartyLedgerEntry.credit_amount), 0),
            )
            .where(PartyLedgerEntry.party_id.in_([item.id for item in items]))
            .group_by(PartyLedgerEntry.party_id)
        ).all()
        for party_id, debit, credit in rows:
            balances[party_id] = Decimal(str(debit or 0)) - Decimal(str(credit or 0))
        for item in items:
            balances.setdefault(item.id, Decimal("0.00"))

    if sort == "name_desc":
        items.sort(key=lambda item: item.name.casefold(), reverse=True)
    elif sort == "newest":
        items.sort(key=lambda item: item.created_at, reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda item: item.created_at)
    elif sort == "balance_high":
        items.sort(key=lambda item: balances.get(item.id, Decimal("0.00")), reverse=True)
    elif sort == "balance_low":
        items.sort(key=lambda item: balances.get(item.id, Decimal("0.00")))

    return render_template(
        "parties/all.html",
        items=items,
        balances=balances,
        query=query,
        status=status,
        party_type_filter=type_filter,
        sort=sort,
        can_manage=current_user.has_permission("parties.manage"),
    )


@parties_bp.post("/distributors/<int:party_id>/toggle")
@login_required
def toggle_distributor(party_id):
    if not current_user.has_permission("parties.manage"):
        abort(403)
    try:
        is_active = _is_active(party_id, "distributor")
        record = set_party_active(party_id, "distributor", not is_active)
        flash("تم إيقاف الموزع." if not record.is_active else "تم تفعيل الموزع.", "success")
    except PartyRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for("parties.distributors"))


@parties_bp.post("/customers/<int:party_id>/toggle")
@login_required
def toggle_customer(party_id):
    if not current_user.has_permission("parties.manage"):
        abort(403)
    try:
        is_active = _is_active(party_id, "customer")
        record = set_party_active(party_id, "customer", not is_active)
        flash("تم إيقاف العميل." if not record.is_active else "تم تفعيل العميل.", "success")
    except PartyRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for("parties.customers"))


def _is_active(party_id, party_type):
    record = db.session.scalar(
        select(Party).where(Party.id == party_id, Party.party_type == party_type)
    )
    if record is None:
        raise PartyRuleError("لم يتم العثور على الحساب.")
    return record.is_active
