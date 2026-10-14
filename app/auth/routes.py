"""User authentication routes."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from app.auth import auth_bp
from app.auth.forms import LoginForm, PasswordChangeForm, PhoneRecoveryForm
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
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("كلمة المرور الحالية غير صحيحة.")
        else:
            try:
                current_user.set_password(form.new_password.data)
                current_user.must_change_password = False
                db.session.commit()
                flash("تم تحديث كلمة المرور.", "success")
                return redirect(url_for("auth.account"))
            except ValueError as exc:
                form.new_password.errors.append(str(exc))

    return render_template("auth/account.html", form=form)


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
