"""System settings restricted to authorized administrators."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models.product import Product
from app.models.setting import Setting
from app.settings import settings_bp
from app.settings.forms import BakerySettingsForm
from app.services.dashboard import DEFAULT_QUICK_ACTIONS, normalize_quick_actions, validate_internal_path


SETTING_DESCRIPTIONS = {
    "business_name": "اسم المنشأة الظاهر في الصفحة الرئيسية والتقارير",
    "default_product_id": "معرف الصنف الافتراضي",
    "operating_period_mode": "daily أو morning_evening",
    "currency_code": "رمز العملة",
    "dashboard_quick_actions": "الاختصارات الظاهرة في الصفحة الرئيسية",
    "dashboard_card_theme": "تصميم بطاقات وحدات الصفحة الرئيسية",
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
        actions = []
        errors = []
        for index in range(20):
            label = (request.form.get(f"action_label_{index}") or "").strip()
            raw_url = (request.form.get(f"action_url_{index}") or "").strip()
            enabled = request.form.get(f"action_enabled_{index}") == "1"
            if not label and not raw_url:
                continue
            if not label:
                errors.append(f"الاختصار رقم {index + 1}: أدخل اسم الزر.")
                continue
            safe_url = validate_internal_path(raw_url)
            if safe_url is None:
                errors.append(f"الاختصار «{label}»: أدخل مسارًا داخليًا يبدأ بـ / مثل /distribution/payment/distributor.")
                continue
            actions.append({"label": label[:50], "url": safe_url, "enabled": enabled})
        if len(actions) > 20:
            errors.append("الحد الأقصى هو 20 اختصارًا.")
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            try:
                _save_setting("dashboard_quick_actions", actions)
                db.session.commit()
                flash("تم حفظ أسماء أزرار الصفحة الرئيسية وروابطها وترتيبها.", "success")
                return redirect(url_for("settings.index"))
            except Exception:
                db.session.rollback()
                flash("تعذر حفظ أزرار الإجراءات السريعة. لم يتم تأكيد التغييرات.", "error")
    elif request.method == "POST" and request.form.get("action") == "save_bottom_nav":
        try:
            _save_setting("show_bottom_nav", request.form.get("show_bottom_nav") == "1")
            db.session.commit()
            flash("تم حفظ إعداد الشريط السفلي.", "success")
            return redirect(url_for("settings.index"))
        except Exception:
            db.session.rollback()
            flash("تعذر حفظ إعداد الشريط السفلي.", "error")
    elif request.method == "POST" and request.form.get("action") == "save_dashboard_card_theme":
        selected_theme = (request.form.get("dashboard_card_theme") or "current").strip()
        if selected_theme not in {"current", "water_pos"}:
            flash("اختر تصميمًا صحيحًا لبطاقات الصفحة الرئيسية.", "error")
        else:
            try:
                _save_setting("dashboard_card_theme", selected_theme)
                db.session.commit()
                flash("تم حفظ تصميم بطاقات الصفحة الرئيسية.", "success")
                return redirect(url_for("settings.index"))
            except Exception:
                db.session.rollback()
                flash("تعذر حفظ تصميم بطاقات الصفحة الرئيسية.", "error")
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
    quick_actions = normalize_quick_actions(saved_quick_actions)
    show_bottom_nav = _setting_value("show_bottom_nav", True) is not False
    dashboard_card_theme = _setting_value("dashboard_card_theme", "current")
    if dashboard_card_theme not in {"current", "water_pos"}:
        dashboard_card_theme = "current"

    return render_template(
        "settings/index.html",
        form=form,
        products=products,
        active_default=next((product for product in products if product.is_default), None),
        quick_actions=quick_actions,
        show_bottom_nav=show_bottom_nav,
        dashboard_card_theme=dashboard_card_theme,
    )
