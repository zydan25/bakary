"""CSRF-protected forms for account access."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class LoginForm(FlaskForm):
    phone = StringField(
        "رقم الهاتف",
        validators=[DataRequired(message="أدخل رقم الهاتف."), Length(max=32)],
    )
    password = PasswordField(
        "كلمة المرور",
        validators=[DataRequired(message="أدخل كلمة المرور.")],
    )
    remember = BooleanField("تذكرني على هذا الجهاز")
    submit = SubmitField("تسجيل الدخول")


class PhoneRecoveryForm(FlaskForm):
    phone = StringField(
        "رقم الهاتف",
        validators=[DataRequired(message="أدخل رقم الهاتف."), Length(max=32)],
    )
    submit = SubmitField("متابعة")


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField(
        "كلمة المرور الحالية",
        validators=[DataRequired(message="أدخل كلمة المرور الحالية.")],
    )
    new_password = PasswordField(
        "كلمة المرور الجديدة",
        validators=[
            DataRequired(message="أدخل كلمة المرور الجديدة."),
            Length(min=8, max=128, message="يجب أن تكون كلمة المرور 8 أحرف على الأقل."),
        ],
    )
    confirm_password = PasswordField(
        "تأكيد كلمة المرور الجديدة",
        validators=[
            DataRequired(message="أكد كلمة المرور الجديدة."),
            EqualTo("new_password", message="كلمتا المرور غير متطابقتين."),
        ],
    )
    submit = SubmitField("تحديث كلمة المرور")
