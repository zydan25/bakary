"""System settings restricted to authorized administrators."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models.product import Product
from app.models.setting import Setting
from app.settings import settings_bp
from app.settings.forms import BakerySettingsForm


SETTING_DESCRIPTIONS = {
    "business_name": "اسم المنشأة الظاهر في الصفحة الرئيسية والتقارير",
    "default_product_id": "معرف الصنف الافتراضي",
    "operating_period_mode": "daily أو morning_evening",
    "currency_code": "رمز العملة",
    "dashboard_quick_actions": "الاختصارات الظاهرة في الصفحة الرئيسية",
}

QUICK_ACTION_OPTIONS = [
    ("product_new", "إضافة صنف", "فتح نموذج إضافة صنف جديد"),
    ("inventory_new", "إضافة مادة خام", "فتح نموذج إضافة مادة خام"),
    ("production_batch", "تسجيل عجنة", "فتح نموذج تسجيل عجنة"),
    ("employee_new", "إضافة موظف", "فتح نموذج إضافة موظف"),
    ("free_recipient", "مستفيد مجاني", "فتح تسجيل مستفيد للتوزيع المجاني"),
    ("expense_new", "تسجيل مصروف", "فتح نموذج مصروف جديد"),
    ("products", "الأصناف", "فتح قائمة الأصناف"),
    ("distributor_new", "إضافة موزع", "فتح نموذج إضافة موزع"),
    ("customer_new", "إضافة عميل", "فتح نموذج إضافة عميل"),
    ("account", "حسابي", "اختصار إلى صفحة الحساب"),
]
QUICK_ACTION_KEYS = tuple(key for key, _label, _description in QUICK_ACTION_OPTIONS)


def _setting_value(key, default=None):
    row = db.session.scalar(select(Setting).where(Setting.key == key))
    return row.value if row is not None and row.value is not None else default


def _save_setting(key, value):
    row = db.session.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        row = Setting(key=key, value=value, description=SETTING_DESCRIPTIONS.get(key))
        db.session.add(row)
    else:
        row.value = value
        if not row.description:
            row.description = SETTING_DESCRIPTIONS.get(key)


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if not current_user.has_permission("settings.manage"):
        abort(403)

    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    form = BakerySettingsForm()
    form.default_product_id.choices = [(product.id, product.name) for product in products]

    if not products:
        flash("أضف صنفًا نشطًا واحدًا على الأقل قبل ضبط الصنف الافتراضي.", "error")

    if request.method == "POST" and request.form.get("action") == "save_quick_actions":
        requested = set(request.form.getlist("quick_actions"))
        enabled = [key for key in QUICK_ACTION_KEYS if key in requested]
        try:
            _save_setting("dashboard_quick_actions", enabled)
            db.session.commit()
            flash("تم حفظ أزرار الإجراءات السريعة في الصفحة الرئيسية.", "success")
            return redirect(url_for("settings.index"))
        except Exception:
            db.session.rollback()
            flash("تعذر حفظ أزرار الإجراءات السريعة. لم يتم تأكيد التغييرات.", "error")
    elif form.validate_on_submit():
        product = db.session.scalar(
            select(Product).where(
                Product.id == form.default_product_id.data,
                Product.is_active.is_(True),
            )
        )
        if product is None:
            form.default_product_id.errors.append("الصنف الافتراضي غير موجود أو موقوف.")
        else:
            try:
                for item in db.session.scalars(select(Product)).all():
                    item.is_default = item.id == product.id
                _save_setting("business_name", form.business_name.data.strip())
                _save_setting("default_product_id", product.id)
                _save_setting("operating_period_mode", form.operating_period_mode.data)
                db.session.commit()
                flash("تم حفظ إعدادات المخبز ونمط الفترات والصنف الافتراضي.", "success")
                return redirect(url_for("settings.index"))
            except Exception:
                db.session.rollback()
                flash("تعذر حفظ الإعدادات. لم يتم تأكيد التغييرات.", "error")

    if not form.is_submitted():
        form.business_name.data = str(_setting_value("business_name", "نظام إدارة المخبز"))
        configured_default = _setting_value("default_product_id")
        current_default = next((product for product in products if product.is_default), None)
        default_id = int(configured_default) if configured_default not in (None, "") else (current_default.id if current_default else (products[0].id if products else None))
        form.default_product_id.data = default_id
        mode = _setting_value("operating_period_mode", "daily")
        form.operating_period_mode.data = mode if mode in {"daily", "morning_evening"} else "daily"

    saved_quick_actions = _setting_value("dashboard_quick_actions")
    quick_actions_enabled = (
        set(saved_quick_actions)
        if isinstance(saved_quick_actions, list)
        else set(QUICK_ACTION_KEYS)
    )

    return render_template(
        "settings/index.html",
        form=form,
        products=products,
        active_default=next((product for product in products if product.is_default), None),
        quick_action_options=QUICK_ACTION_OPTIONS,
        quick_actions_enabled=quick_actions_enabled,
    )
