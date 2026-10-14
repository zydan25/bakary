"""Validated forms for free distribution and period handover."""

from datetime import date
from app.services.clock import business_today
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, HiddenField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class FreeRecipientForm(FlaskForm):
    name = StringField(
        "اسم المستفيد",
        validators=[DataRequired(message="اسم المستفيد مطلوب."), Length(max=160)],
    )
    notes = TextAreaField("ملاحظات", validators=[Optional(), Length(max=2000)])


class FreeIssueForm(FlaskForm):
    recipient_id = SelectField("المستفيد", coerce=int, validators=[DataRequired(message="اختر المستفيد.")])
    product_id = SelectField("الصنف", coerce=int, validators=[DataRequired(message="اختر الصنف.")])
    quantity = DecimalField(
        "الكمية المصروفة",
        places=3,
        validators=[
            DataRequired(message="أدخل الكمية."),
            NumberRange(min=Decimal("0.001"), message="الكمية يجب أن تكون أكبر من صفر."),
        ],
    )
    business_date = DateField("التاريخ", format="%Y-%m-%d", default=business_today, validators=[DataRequired()])
    period_code = SelectField("الفترة", validators=[DataRequired()])
    statement = TextAreaField("البيان", validators=[Optional(), Length(max=1000)])


class PeriodClosingForm(FlaskForm):
    employee_id = SelectField(
        "المستلم / مسؤول البيع",
        coerce=int,
        validators=[DataRequired(message="اختر المستلم.")],
    )
    received_amount = StringField("المبلغ الذي استلمه المسؤول", validators=[DataRequired(message="أدخل المبلغ المستلم.")])
    expenses_amount = StringField("إجمالي خرجيات الفترة", validators=[DataRequired(message="أدخل إجمالي الخرجيات، ولو صفرًا.")])
    handed_to_cash_amount = StringField("المبلغ المسلم للصندوق", validators=[DataRequired(message="أدخل المبلغ المسلم للصندوق.")])
    statement = TextAreaField("بيان الإقفال", validators=[Optional(), Length(max=2000)])
