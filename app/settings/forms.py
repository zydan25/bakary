"""Validated editable bakery settings."""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import DataRequired, Length


class BakerySettingsForm(FlaskForm):
    business_name = StringField(
        "اسم المنشأة",
        validators=[
            DataRequired(message="اسم المنشأة مطلوب."),
            Length(max=160, message="اسم المنشأة طويل جدًا."),
        ],
    )
    default_product_id = SelectField(
        "الصنف الافتراضي",
        coerce=int,
        validators=[DataRequired(message="اختر الصنف الافتراضي.")],
    )
    operating_period_mode = SelectField(
        "نمط الفترات التشغيلية",
        choices=[
            ("daily", "فترة واحدة لليوم كاملًا"),
            ("morning_evening", "فترتان: صباحية ومسائية"),
        ],
        validators=[DataRequired(message="اختر نمط التشغيل.")],
    )
