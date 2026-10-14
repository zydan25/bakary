"""Validated employee profile form."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class EmployeeForm(FlaskForm):
    full_name = StringField(
        "اسم الموظف",
        validators=[DataRequired(message="اسم الموظف مطلوب."), Length(max=160)],
    )
    phone = StringField(
        "رقم الهاتف للدخول",
        validators=[DataRequired(message="رقم الهاتف مطلوب."), Length(max=32)],
    )
    job_title = StringField(
        "المسمى الوظيفي",
        validators=[Optional(), Length(max=100)],
    )
    notes = TextAreaField(
        "ملاحظات",
        validators=[Optional(), Length(max=3000)],
    )
    user_password = PasswordField(
        "كلمة المرور للحساب الجديد",
        validators=[Optional(), Length(min=8, message="كلمة المرور لا تقل عن 8 أحرف.")],
    )
    is_active = BooleanField("الموظف نشط", default=True)
