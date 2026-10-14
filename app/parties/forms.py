"""Form fields for distributor/customer profile management."""

from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class PartyForm(FlaskForm):
    party_id = HiddenField()
    name = StringField(
        "اسم الحساب",
        validators=[
            DataRequired(message="اسم الحساب مطلوب."),
            Length(max=160, message="الاسم لا يتجاوز 160 حرفًا."),
        ],
    )
    phone = StringField(
        "رقم الهاتف",
        validators=[Length(max=32, message="رقم الهاتف طويل جدًا.")],
    )
    notes = TextAreaField(
        "ملاحظات",
        validators=[Length(max=3000, message="الملاحظات طويلة جدًا.")],
    )
    submit = SubmitField("حفظ")
