"""Inventory catalog and stock movement forms."""

from datetime import date
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, HiddenField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange


class InventoryItemForm(FlaskForm):
    name = StringField(
        "اسم المادة",
        validators=[DataRequired(message="اسم المادة مطلوب."), Length(max=140)],
    )
    code = StringField(
        "رمز المادة",
        validators=[DataRequired(message="رمز المادة مطلوب."), Length(max=40)],
    )
    unit_label = StringField(
        "وحدة القياس",
        default="كجم",
        validators=[DataRequired(message="وحدة القياس مطلوبة."), Length(max=24)],
    )
    reorder_level = DecimalField(
        "حد التنبيه عند انخفاض المخزون",
        places=3,
        default=Decimal("0.000"),
        validators=[DataRequired(message="أدخل حد التنبيه."), NumberRange(min=0)],
    )
    submit = SubmitField("حفظ المادة")


class StockMovementForm(FlaskForm):
    item_id = SelectField(
        "المادة الخام",
        coerce=int,
        validators=[DataRequired(message="اختر المادة الخام.")],
    )
    movement_type = SelectField(
        "نوع الإضافة",
        choices=[
            ("opening_balance", "رصيد افتتاحي"),
            ("addition", "إضافة مخزون"),
        ],
        validators=[DataRequired(message="اختر نوع الحركة.")],
    )
    quantity = DecimalField(
        "الكمية",
        places=3,
        validators=[
            DataRequired(message="أدخل الكمية."),
            NumberRange(min=Decimal("0.001"), message="يجب أن تكون الكمية أكبر من صفر."),
        ],
    )
    unit_cost = DecimalField(
        "تكلفة الوحدة الواحدة (اختياري)",
        places=2,
        validators=[
            NumberRange(min=Decimal("0"), message="تكلفة الوحدة لا يمكن أن تكون سالبة."),
        ],
    )
    business_date = DateField(
        "تاريخ الحركة",
        format="%Y-%m-%d",
        default=date.today,
        validators=[DataRequired(message="التاريخ مطلوب.")],
    )
    statement = TextAreaField(
        "البيان",
        validators=[Length(max=1000, message="البيان طويل جدًا.")],
    )
    request_id = HiddenField(validators=[DataRequired(message="أعد فتح النموذج وحاول مجددًا.")])
    submit = SubmitField("تسجيل المخزون")
