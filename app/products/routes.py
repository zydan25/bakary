"""Product catalog views."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from app.extensions import db
from app.models.product import Product
from app.products import products_bp
from app.products.forms import ProductForm
from app.services.catalog import CatalogRuleError, save_product


@products_bp.route("/", methods=["GET", "POST"])
@login_required
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
