"""System settings restricted to authorized administrators."""

from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from PIL import Image, ImageOps, UnidentifiedImageError
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
    "pwa_app_name": "اسم التطبيق الذي يظهر عند التثبيت",
    "pwa_app_short_name": "اسم التطبيق المختصر بجانب الأيقونة",
    "pwa_app_icon": "رمز الأيقونة المخصصة للتطبيق المثبت",
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


def _remove_app_icon_files(token):
    """Remove generated icon sizes only for a token created by this application."""
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        return
    icon_dir = Path(current_app.instance_path) / "app_icons"
    for size in (192, 512):
        try:
            (icon_dir / f"app-icon-{token}-{size}.png").unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Could not remove obsolete PWA icon file.")


def _store_app_icon(upload):
    """Validate an uploaded image and create correctly-sized PNG app icons."""
    if not upload or not upload.filename:
        return None

    payload = upload.stream.read(3 * 1024 * 1024 + 1)
    if len(payload) > 3 * 1024 * 1024:
        raise ValueError("حجم الأيقونة يتجاوز 3 ميجابايت.")

    try:
        with Image.open(BytesIO(payload)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("صيغة الأيقونة غير مدعومة. ارفع صورة PNG أو JPG أو WEBP.")
            if (
                source.width < 32 or source.height < 32
                or source.width > 4096 or source.height > 4096
                or source.width * source.height > 16_000_000
            ):
                raise ValueError("أبعاد الصورة غير مناسبة. استخدم صورة مربعة أو قريبة من المربّع بين 32 و4096 بكسل.")
            source.load()
            normalized = ImageOps.exif_transpose(source).convert("RGBA")
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("تعذر قراءة الصورة. اختر ملف صورة صالحًا بصيغة PNG أو JPG أو WEBP.") from None

    token = uuid4().hex
    icon_dir = Path(current_app.instance_path) / "app_icons"
    try:
        icon_dir.mkdir(parents=True, exist_ok=True)
        for size in (192, 512):
            resized = ImageOps.fit(
                normalized,
                (size, size),
                method=Image.Resampling.LANCZOS,
            )
            resized.save(icon_dir / f"app-icon-{token}-{size}.png", format="PNG", optimize=True)
    except Exception:
        _remove_app_icon_files(token)
        raise ValueError("تعذر تجهيز الأيقونة. حاول بصورة أخرى.") from None
    finally:
        normalized.close()

    return token


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
    elif request.method == "POST" and request.form.get("action") == "save_pwa_settings":
        app_name = (request.form.get("pwa_app_name") or "").strip()
        short_name = (request.form.get("pwa_app_short_name") or "").strip()
        if not app_name:
            flash("اسم التطبيق عند التثبيت مطلوب.", "error")
        elif len(app_name) > 80:
            flash("اسم التطبيق طويل جدًا؛ الحد الأقصى 80 حرفًا.", "error")
        else:
            if not short_name:
                short_name = app_name[:12].strip() or app_name[:12]
            if len(short_name) > 20:
                flash("الاسم المختصر يجب ألا يتجاوز 20 حرفًا.", "error")
            else:
                old_icon_token = _setting_value("pwa_app_icon")
                new_icon_token = None
                try:
                    new_icon_token = _store_app_icon(request.files.get("app_icon"))
                    _save_setting("pwa_app_name", app_name)
                    _save_setting("pwa_app_short_name", short_name)
                    if new_icon_token:
                        _save_setting("pwa_app_icon", new_icon_token)
                    db.session.commit()
                    if new_icon_token and old_icon_token and old_icon_token != new_icon_token:
                        _remove_app_icon_files(old_icon_token)
                    flash("تم حفظ اسم التطبيق وأيقونة التثبيت.", "success")
                    return redirect(url_for("settings.index"))
                except ValueError as exc:
                    db.session.rollback()
                    if new_icon_token:
                        _remove_app_icon_files(new_icon_token)
                    flash(str(exc), "error")
                except Exception:
                    db.session.rollback()
                    if new_icon_token:
                        _remove_app_icon_files(new_icon_token)
                    flash("تعذر حفظ إعدادات التطبيق. لم يتم تأكيد التغييرات.", "error")
    elif request.method == "POST" and request.form.get("action") == "restore_pwa_defaults":
        old_icon_token = _setting_value("pwa_app_icon")
        try:
            for key in ("pwa_app_name", "pwa_app_short_name", "pwa_app_icon"):
                row = db.session.scalar(select(Setting).where(Setting.key == key))
                if row is not None:
                    db.session.delete(row)
            db.session.commit()
            _remove_app_icon_files(old_icon_token)
            flash("تمت استعادة اسم التطبيق وأيقونة التثبيت الافتراضيين.", "success")
            return redirect(url_for("settings.index"))
        except Exception:
            db.session.rollback()
            flash("تعذرت استعادة إعدادات التطبيق الافتراضية.", "error")
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

    business_name = _setting_value("business_name", "نظام إدارة المخبز")
    if not isinstance(business_name, str) or not business_name.strip():
        business_name = "نظام إدارة المخبز"
    pwa_app_name = _setting_value("pwa_app_name", business_name)
    if not isinstance(pwa_app_name, str) or not pwa_app_name.strip():
        pwa_app_name = business_name
    pwa_app_short_name = _setting_value("pwa_app_short_name", pwa_app_name[:12].strip() or pwa_app_name[:12])
    if not isinstance(pwa_app_short_name, str) or not pwa_app_short_name.strip():
        pwa_app_short_name = pwa_app_name[:12].strip() or pwa_app_name[:12]
    if request.method == "POST" and request.form.get("action") == "save_pwa_settings":
        pwa_app_name = request.form.get("pwa_app_name", pwa_app_name)
        pwa_app_short_name = request.form.get("pwa_app_short_name", pwa_app_short_name)
        if not pwa_app_short_name.strip():
            pwa_app_short_name = pwa_app_name[:12].strip() or pwa_app_name[:12]
    pwa_icon_token = _setting_value("pwa_app_icon")
    if not isinstance(pwa_icon_token, str) or not re.fullmatch(r"[0-9a-f]{32}", pwa_icon_token):
        pwa_icon_token = None
    pwa_icon_url = (
        url_for("app_icon", token=pwa_icon_token, size=512)
        if pwa_icon_token else url_for("static", filename="icons/bakary.svg")
    )

    return render_template(
        "settings/index.html",
        form=form,
        products=products,
        active_default=next((product for product in products if product.is_default), None),
        quick_actions=quick_actions,
        show_bottom_nav=show_bottom_nav,
        dashboard_card_theme=dashboard_card_theme,
        pwa_app_name=pwa_app_name,
        pwa_app_short_name=pwa_app_short_name,
        pwa_icon_token=pwa_icon_token,
        pwa_icon_url=pwa_icon_url,
    )
