"""Validated financial entry forms."""

from datetime import date
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp


class CashAccountForm(FlaskForm):
    name = StringField("اسم الحساب", validators=[DataRequired(message="اسم الحساب مطلوب."), Length(max=120)])
    code = StringField(
        "رمز الحساب",
        validators=[
            DataRequired(message="رمز الحساب مطلوب."),
            Length(max=32),
            Regexp(r"^[A-Za-z0-9_-]+$", message="استخدم أحرفًا لاتينية أو أرقامًا أو شرطة سفلية."),
        ],
    )
    account_type = SelectField(
        "نوع الحساب",
        choices=[("cash", "نقدي"), ("bank", "بنكي"), ("other", "آخر")],
        validators=[DataRequired()],
    )


class ExpenseForm(FlaskForm):
    title = StringField("اسم المصروف", validators=[DataRequired(message="اسم المصروف مطلوب."), Length(max=160)])
    amount = DecimalField(
        "المبلغ",
        places=2,
        validators=[
            DataRequired(message="المبلغ مطلوب."),
            NumberRange(min=Decimal("0.01"), message="المبلغ يجب أن يكون أكبر من صفر."),
        ],
    )
    cash_account_id = SelectField("الحساب الذي صُرف منه", coerce=int, validators=[DataRequired(message="اختر الحساب.")])
    business_date = DateField("التاريخ", format="%Y-%m-%d", default=date.today, validators=[DataRequired()])
    statement = TextAreaField("البيان", validators=[Optional(), Length(max=2000)])


class TransferForm(FlaskForm):
    source_account_id = SelectField("من حساب", coerce=int, validators=[DataRequired(message="اختر حساب المصدر.")])
    target_account_id = SelectField("إلى حساب", coerce=int, validators=[DataRequired(message="اختر حساب الوجهة.")])
    amount = DecimalField(
        "المبلغ المحوّل",
        places=2,
        validators=[
            DataRequired(message="المبلغ مطلوب."),
            NumberRange(min=Decimal("0.01"), message="المبلغ يجب أن يكون أكبر من صفر."),
        ],
    )
    business_date = DateField("التاريخ", format="%Y-%m-%d", default=date.today, validators=[DataRequired()])
    statement = TextAreaField("البيان", validators=[Optional(), Length(max=2000)])
