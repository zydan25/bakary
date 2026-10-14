"""Validated forms for distributor/customer issue and cash collection."""

from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, HiddenField, IntegerField, SelectField, TextAreaField, StringField
from wtforms.validators import DataRequired, Length, NumberRange


class IssueForm(FlaskForm):
    party_id = SelectField(
        "الحساب",
        coerce=int,
        validators=[DataRequired(message="اختر الحساب أولًا.")],
    )
    product_id = SelectField(
        "الصنف",
        coerce=int,
        validators=[DataRequired(message="اختر الصنف.")],
    )
    quantity = IntegerField(
        "الكمية",
        validators=[
            DataRequired(message="أدخل الكمية."),
            NumberRange(min=1, message="يجب أن تكون الكمية أكبر من صفر."),
        ],
    )
    business_date = DateField(
        "تاريخ العملية",
        format="%Y-%m-%d",
        default=date.today,
        validators=[DataRequired(message="تاريخ العملية مطلوب.")],
    )
    statement = TextAreaField(
        "البيان",
        validators=[Length(max=1000, message="البيان طويل جدًا.")],
    )
    request_key = HiddenField(validators=[DataRequired()])


class PaymentForm(FlaskForm):
    party_id = SelectField(
        "الحساب",
        coerce=int,
        validators=[DataRequired(message="اختر الحساب أولًا.")],
    )
    amount = StringField(
        "المبلغ المدفوع",
        validators=[DataRequired(message="أدخل المبلغ المدفوع.")],
    )
    business_date = DateField(
        "تاريخ الدفع",
        format="%Y-%m-%d",
        default=date.today,
        validators=[DataRequired(message="تاريخ الدفع مطلوب.")],
    )
    statement = TextAreaField(
        "البيان",
        validators=[Length(max=1000, message="البيان طويل جدًا.")],
    )
    request_key = HiddenField(validators=[DataRequired()])
