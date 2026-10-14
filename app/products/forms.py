"""Forms for the baked product catalog."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


class ProductForm(FlaskForm):
    product_id = HiddenField()
    name = StringField("اسم الصنف", validators=[DataRequired(message="اسم الصنف مطلوب."), Length(max=120)])
    code = StringField("رمز الصنف", validators=[DataRequired(message="رمز الصنف مطلوب."), Length(max=40)])
    unit_label = StringField("وحدة البيع", validators=[DataRequired(message="وحدة البيع مطلوبة."), Length(max=30)])
    default_distributor_price = StringField("سعر الموزع العام", validators=[DataRequired(message="أدخل سعر الموزع العام.")])
    default_customer_price = StringField("سعر العميل العام", validators=[DataRequired(message="أدخل سعر العميل العام.")])
    shop_price = StringField("سعر بيع المحل", validators=[DataRequired(message="أدخل سعر بيع المحل.")])
    is_default = BooleanField("اجعل هذا الصنف الافتراضي")
    submit = SubmitField("حفظ الصنف")
