"""Product catalog views."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_, select

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.product import Product
from app.models.party import Party, PartyPrice
from app.models.distribution import DistributionIssue
from app.models.free_distribution import FreeDistribution
from app.models.production import DoughBatch
from app.models.closing import PeriodCloseProduct
from app.products import products_bp
from app.products.forms import ProductForm
from app.services.catalog import CatalogRuleError, save_product


@products_bp.route("/", methods=["GET", "POST"])
@permission_required("products.view")
def index():
    query = (request.args.get("q") or "").strip()
    status = request.args.get("status", "active")
    action = request.args.get("action", "")
    edit_id = request.args.get("edit", type=int)
    form = ProductForm()

    if request.method == "POST":
        if not current_user.has_permission("products.manage"):
            abort(403)
        if form.validate_on_submit():
            try:
                save_product(
                    product_id=int(form.product_id.data) if form.product_id.data else None,
                    name=form.name.data,
                    code=form.code.data,
                    unit_label=form.unit_label.data,
                    default_distributor_price=form.default_distributor_price.data,
                    default_customer_price=form.default_customer_price.data,
                    shop_price=form.shop_price.data,
                    is_default=form.is_default.data,
                    actor_id=current_user.id,
                )
                flash("تم حفظ الصنف والأسعار بنجاح.", "success")
                return redirect(url_for("products.index", status=status, q=query or None))
            except CatalogRuleError as exc:
                flash(str(exc), "error")
        action = "edit" if form.product_id.data else "new"
        edit_id = int(form.product_id.data) if form.product_id.data else None

    editing = db.session.get(Product, edit_id) if edit_id else None
    if edit_id and editing is None:
        abort(404)
    if editing is not None and request.method == "GET":
        form.product_id.data = str(editing.id)
        form.name.data = editing.name
        form.code.data = editing.code
        form.unit_label.data = editing.unit_label
        form.default_distributor_price.data = str(editing.default_distributor_price)
        form.default_customer_price.data = str(editing.default_customer_price)
        form.shop_price.data = str(editing.shop_price)
        form.is_default.data = editing.is_default

    stmt = select(Product)
    if status == "active":
        stmt = stmt.where(Product.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(Product.is_active.is_(False))
    if query:
        needle = "%" + query + "%"
        stmt = stmt.where(or_(Product.name.ilike(needle), Product.code.ilike(needle)))
    items = db.session.scalars(
        stmt.order_by(Product.is_default.desc(), Product.is_active.desc(), Product.name.asc())
    ).all()

    return render_template(
        "products/list.html",
        items=items,
        form=form,
        query=query,
        status=status,
        show_form=(action in {"new", "edit"}) or (request.method == "POST" and bool(form.errors)),
        can_manage=current_user.has_permission("products.manage"),
    )


@products_bp.get("/<int:product_id>")
@permission_required("products.view")
def detail(product_id):
    """Product report: pricing, paid distributions, free distributions and production."""
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)

    issue_stats = db.session.execute(
        select(
            func.count(DistributionIssue.id),
            func.coalesce(func.sum(DistributionIssue.quantity), 0),
            func.coalesce(func.sum(DistributionIssue.total_amount), 0),
            func.count(func.distinct(DistributionIssue.party_id)),
        ).where(DistributionIssue.product_id == product.id)
    ).one()
    free_stats = db.session.execute(
        select(
            func.count(FreeDistribution.id),
            func.coalesce(func.sum(FreeDistribution.quantity), 0),
        ).where(FreeDistribution.product_id == product.id)
    ).one()
    production_stats = db.session.execute(
        select(
            func.count(DoughBatch.id),
            func.coalesce(func.sum(DoughBatch.produced_quantity), 0),
        ).where(DoughBatch.product_id == product.id)
    ).one()
    close_stats = db.session.execute(
        select(
            func.coalesce(func.sum(PeriodCloseProduct.shop_sale_quantity), 0),
            func.coalesce(func.sum(PeriodCloseProduct.expected_shop_sales), 0),
        ).where(PeriodCloseProduct.product_id == product.id)
    ).one()

    price_rows = db.session.scalars(
        select(PartyPrice)
        .join(Party, PartyPrice.party_id == Party.id)
        .where(PartyPrice.product_id == product.id, Party.is_active.is_(True))
        .order_by(Party.party_type.asc(), Party.name.asc())
    ).all()
    recent_issues = db.session.scalars(
        select(DistributionIssue)
        .where(DistributionIssue.product_id == product.id)
        .order_by(DistributionIssue.business_date.desc(), DistributionIssue.id.desc())
        .limit(8)
    ).all()
    recent_free = db.session.scalars(
        select(FreeDistribution)
        .where(FreeDistribution.product_id == product.id)
        .order_by(FreeDistribution.created_at.desc(), FreeDistribution.id.desc())
        .limit(8)
    ).all()
    recent_production = db.session.scalars(
        select(DoughBatch)
        .where(DoughBatch.product_id == product.id)
        .order_by(DoughBatch.created_at.desc(), DoughBatch.id.desc())
        .limit(8)
    ).all()

    return render_template(
        "products/detail.html",
        product=product,
        issue_count=issue_stats[0],
        issued_quantity=issue_stats[1],
        issued_amount=issue_stats[2],
        party_count=issue_stats[3],
        free_count=free_stats[0],
        free_quantity=free_stats[1],
        production_count=production_stats[0],
        produced_quantity=production_stats[1],
        shop_sale_quantity=close_stats[0],
        shop_sale_amount=close_stats[1],
        price_rows=price_rows,
        recent_issues=recent_issues,
        recent_free=recent_free,
        recent_production=recent_production,
        can_manage=current_user.has_permission("products.manage"),
    )


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id):
    if not current_user.has_permission("products.manage"):
        abort(403)
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)

    form = ProductForm()
    if request.method == "GET":
        form.product_id.data = str(product.id)
        form.name.data = product.name
        form.code.data = product.code
        form.unit_label.data = product.unit_label
        form.default_distributor_price.data = str(product.default_distributor_price)
        form.default_customer_price.data = str(product.default_customer_price)
        form.shop_price.data = str(product.shop_price)
        form.is_default.data = product.is_default

    if request.method == "POST" and form.validate_on_submit():
        try:
            saved = save_product(
                product_id=product.id,
                name=form.name.data,
                code=form.code.data,
                unit_label=form.unit_label.data,
                default_distributor_price=form.default_distributor_price.data,
                default_customer_price=form.default_customer_price.data,
                shop_price=form.shop_price.data,
                is_default=form.is_default.data,
                actor_id=current_user.id,
            )
            flash("تم تحديث بيانات الصنف وأسعاره بنجاح.", "success")
            return redirect(url_for("products.detail", product_id=saved.id))
        except CatalogRuleError as exc:
            flash(str(exc), "error")

    return render_template("products/form.html", form=form, product=product)


@products_bp.post("/<int:product_id>/delete")
@login_required
def delete(product_id):
    if not current_user.has_permission("products.manage"):
        abort(403)
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)

    historical_references = [
        ("حركات الصرف", db.session.scalar(select(func.count()).select_from(DistributionIssue).where(DistributionIssue.product_id == product.id)) or 0),
        ("التوزيع المجاني", db.session.scalar(select(func.count()).select_from(FreeDistribution).where(FreeDistribution.product_id == product.id)) or 0),
        ("سجلات الإنتاج", db.session.scalar(select(func.count()).select_from(DoughBatch).where(DoughBatch.product_id == product.id)) or 0),
        ("إقفالات الفترات", db.session.scalar(select(func.count()).select_from(PeriodCloseProduct).where(PeriodCloseProduct.product_id == product.id)) or 0),
    ]
    linked = [label for label, count in historical_references if count]
    if linked:
        flash("لا يمكن حذف الصنف نهائيًا لارتباطه بسجلات سابقة (" + "، ".join(linked) + "). أوقفه بدلًا من حذف تاريخه.", "error")
        return redirect(url_for("products.detail", product_id=product.id))

    replacement = None
    if product.is_default and product.is_active:
        replacement = db.session.scalar(
            select(Product)
            .where(Product.id != product.id, Product.is_active.is_(True))
            .order_by(Product.id.asc())
            .limit(1)
        )
        if replacement is None:
            flash("لا يمكن حذف الصنف الافتراضي الوحيد؛ أضف صنفًا آخر أولًا.", "error")
            return redirect(url_for("products.detail", product_id=product.id))
    try:
        if replacement is not None:
            replacement.is_default = True
        name = product.name
        db.session.delete(product)
        db.session.commit()
        flash(f"تم حذف الصنف «{name}» نهائيًا.", "success")
        return redirect(url_for("products.index"))
    except Exception:
        db.session.rollback()
        flash("تعذر حذف الصنف. لم يتم تأكيد أي تغيير.", "error")
        return redirect(url_for("products.detail", product_id=product.id))


@products_bp.post("/<int:product_id>/toggle")
@login_required
def toggle(product_id):
    if not current_user.has_permission("products.manage"):
        abort(403)
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)
    if product.is_default and product.is_active:
        active_count = db.session.scalar(
            select(db.func.count()).select_from(Product).where(
                Product.is_active.is_(True), Product.id != product.id
            )
        )
        if not active_count:
            flash("لا يمكن إيقاف الصنف الافتراضي الوحيد.", "error")
            return redirect(url_for("products.index"))
    product.is_active = not product.is_active
    if not product.is_active and product.is_default:
        product.is_default = False
        replacement = db.session.scalar(
            select(Product).where(Product.is_active.is_(True), Product.id != product.id).order_by(Product.id.asc()).limit(1)
        )
        if replacement:
            replacement.is_default = True
    db.session.commit()
    flash("تم تحديث حالة الصنف.", "success")
    return redirect(url_for("products.index"))
