"""Validated dough-batch and aggregate flour usage forms."""

from datetime import date
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class DoughBatchForm(FlaskForm):
    product_id = SelectField(
        "الصنف المخبوز",
        coerce=int,
        validators=[DataRequired(message="اختر الصنف المخبوز.")],
    )
    produced_quantity = DecimalField(
        "الكمية المنتجة",
        places=3,
        validators=[
            DataRequired(message="أدخل الكمية المنتجة."),
            NumberRange(min=Decimal("0.001"), message="يجب أن تكون الكمية أكبر من صفر."),
        ],
    )
    flour_mode = SelectField(
        "احتساب الدقيق",
        choices=[
            ("none", "لا تسجل دقيقًا مع هذه العجنة"),
            ("per_batch", "تسجيل دقيق هذه العجنة"),
        ],
        validators=[DataRequired(message="اختر طريقة احتساب الدقيق.")],
    )
    flour_item_id = SelectField("مادة الدقيق", coerce=int, validators=[])
    flour_quantity = DecimalField(
        "كمية الدقيق المستهلكة",
        places=3,
        validators=[
            Optional(),
            NumberRange(min=Decimal("0"), message="كمية الدقيق لا يمكن أن تكون سالبة."),
        ],
    )
    business_date = DateField(
        "تاريخ الإنتاج",
        format="%Y-%m-%d",
        default=date.today,
        validators=[DataRequired(message="تاريخ الإنتاج مطلوب.")],
    )
    period_code = SelectField(
        "الفترة",
        validators=[DataRequired(message="اختر الفترة التشغيلية.")],
    )
    statement = TextAreaField("ملاحظات", validators=[Length(max=1000)])
    idempotency_key = HiddenField(validators=[DataRequired()])


class PeriodFlourForm(FlaskForm):
    item_id = SelectField(
        "مادة الدقيق",
        coerce=int,
        validators=[DataRequired(message="اختر مادة الدقيق.")],
    )
    quantity = DecimalField(
        "إجمالي الدقيق المستهلك للفترة",
        places=3,
        validators=[
            DataRequired(message="أدخل إجمالي كمية الدقيق."),
            NumberRange(min=Decimal("0.001"), message="يجب أن تكون الكمية أكبر من صفر."),
        ],
    )
    business_date = DateField(
        "تاريخ الإنتاج",
        format="%Y-%m-%d",
        default=date.today,
        validators=[DataRequired(message="تاريخ الإنتاج مطلوب.")],
    )
    period_code = SelectField(
        "الفترة",
        validators=[DataRequired(message="اختر الفترة التشغيلية.")],
    )
    statement = TextAreaField("ملاحظات", validators=[Length(max=1000)])
