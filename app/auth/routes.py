"""User authentication routes."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import auth_bp
from app.auth.forms import AccountProfileForm, LoginForm, PasswordChangeForm, PhoneRecoveryForm
from app.extensions import db
from app.models.user import User
from app.services.phone import normalize_phone


def _safe_next_url(target):
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return None
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        phone = normalize_phone(form.phone.data)
        user = db.session.scalar(select(User).where(User.phone == phone))

        if user is None or not user.is_active or not user.check_password(form.password.data):
            flash("رقم الهاتف أو كلمة المرور غير صحيحة.", "error")
        else:
            login_user(user, remember=form.remember.data, fresh=True)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            next_url = _safe_next_url(request.args.get("next"))
            flash("تم تسجيل الدخول بنجاح.", "success")
            return redirect(next_url or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("تم تسجيل الخروج.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = PasswordChangeForm()
    profile_form = AccountProfileForm()
    open_dialog = None

    if request.method == "GET":
        profile_form.full_name.data = current_user.full_name
        profile_form.phone.data = current_user.phone

    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            open_dialog = "profile"
            if profile_form.validate_on_submit():
                full_name = (profile_form.full_name.data or "").strip()
                phone = normalize_phone(profile_form.phone.data)
                if len(full_name) < 2:
                    profile_form.full_name.errors.append("أدخل اسمًا صحيحًا مكوّنًا من حرفين على الأقل.")
                elif not phone:
                    profile_form.phone.errors.append("أدخل رقم هاتف صحيحًا.")
                elif not current_user.check_password(profile_form.current_password.data):
                    profile_form.current_password.errors.append("كلمة المرور الحالية غير صحيحة.")
                else:
                    duplicate = db.session.scalar(select(User.id).where(
                        User.phone == phone,
                        User.id != current_user.id,
                    ))
                    if duplicate is not None:
                        profile_form.phone.errors.append("رقم الهاتف مستخدم لحساب آخر.")
                    else:
                        try:
                            current_user.full_name = full_name
                            current_user.phone = phone
                            db.session.commit()
                            flash("تم تحديث بيانات الحساب بنجاح.", "success")
                            return redirect(url_for("auth.account"))
                        except IntegrityError:
                            db.session.rollback()
                            profile_form.phone.errors.append("تعذر حفظ الرقم؛ ربما أصبح مستخدمًا لحساب آخر.")
                        except Exception:
                            db.session.rollback()
                            profile_form.full_name.errors.append("تعذر حفظ البيانات؛ لم يتم تأكيد أي تغيير.")
        elif action == "password":
            open_dialog = "password"
            if form.validate_on_submit():
                if not current_user.check_password(form.current_password.data):
                    form.current_password.errors.append("كلمة المرور الحالية غير صحيحة.")
                else:
                    try:
                        current_user.set_password(form.new_password.data)
                        current_user.must_change_password = False
                        db.session.commit()
                        flash("تم تحديث كلمة المرور بنجاح.", "success")
                        return redirect(url_for("auth.account"))
                    except ValueError as exc:
                        form.new_password.errors.append(str(exc))
                    except Exception:
                        db.session.rollback()
                        form.new_password.errors.append("تعذر تحديث كلمة المرور؛ لم يتم حفظ أي تغيير.")

    return render_template(
        "auth/account.html",
        form=form,
        profile_form=profile_form,
        open_dialog=open_dialog,
    )


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = PhoneRecoveryForm()
    if form.validate_on_submit():
        # Do not reveal whether the number exists; a delivery provider is not configured yet.
        normalize_phone(form.phone.data)
        flash(
            "لحماية حسابك، لم يتم كشف حالة الرقم. لم تُفعّل خدمة إرسال رموز الاستعادة بعد؛ "
            "تواصل مع مدير النظام لإعادة تعيين كلمة المرور.",
            "info",
        )
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/forgot_password.html", form=form)
