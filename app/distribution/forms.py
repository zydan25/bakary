"""Validated forms for distributor/customer issue and cash collection."""

from datetime import date
from app.services.clock import business_today

from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, SelectField, TextAreaField, StringField
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
    period_id = SelectField(
        "الفترة التشغيلية",
        coerce=int,
        validators=[DataRequired(message="اختر فترة مفتوحة.")],
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
    period_id = SelectField(
        "الفترة التشغيلية",
        coerce=int,
        validators=[DataRequired(message="اختر فترة مفتوحة.")],
    )
    statement = TextAreaField(
        "البيان",
        validators=[Length(max=1000, message="البيان طويل جدًا.")],
    )
    request_key = HiddenField(validators=[DataRequired()])



class IssueEditForm(FlaskForm):
    party_id = SelectField(
        "الحساب",
        coerce=int,
        validators=[DataRequired(message="اختر الحساب.")],
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
    statement = TextAreaField("البيان", validators=[Length(max=1000, message="البيان طويل جدًا.")])


class PaymentEditForm(FlaskForm):
    party_id = SelectField(
        "الحساب",
        coerce=int,
        validators=[DataRequired(message="اختر الحساب.")],
    )
    amount = StringField(
        "المبلغ المدفوع",
        validators=[DataRequired(message="أدخل المبلغ المدفوع.")],
    )
    statement = TextAreaField("البيان", validators=[Length(max=1000, message="البيان طويل جدًا.")])
