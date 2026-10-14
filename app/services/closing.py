"""Calculated bakery-period close and cash handover transactions."""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.closing import PeriodCloseProduct, PeriodHandover
from app.models.distribution import DistributionIssue
from app.models.employee import Employee
from app.models.expense import Expense
from app.models.finance import CashAccount, CashMovement
from app.models.free_distribution import FreeDistribution
from app.models.party import Party
from app.models.production import BusinessPeriod, DoughBatch
from app.models.product import Product
from app.models.base import utc_now


QTY = Decimal("0.001")
CENT = Decimal("0.01")


class ClosingRuleError(ValueError):
    """A close or handover request violates an operational or accounting rule."""


def _decimal(value, label, quantum, *, allow_zero=True):
    try:
        amount = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ClosingRuleError(f"قيمة {label} غير صالحة.") from exc
    if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero):
        raise ClosingRuleError(f"قيمة {label} يجب ألا تكون سالبة.")
    return amount


def _opening_quantity(period, product_id):
    condition = BusinessPeriod.business_date < period.business_date
    if period.period_code == "evening":
        condition = or_(
            condition,
            and_(
                BusinessPeriod.business_date == period.business_date,
                BusinessPeriod.period_code == "morning",
            ),
        )
    candidates = db.session.execute(
        select(PeriodCloseProduct, BusinessPeriod)
        .join(BusinessPeriod, PeriodCloseProduct.period_id == BusinessPeriod.id)
        .where(
            PeriodCloseProduct.product_id == product_id,
            BusinessPeriod.status == "closed",
            condition,
        )
    ).all()
    if not candidates:
        return Decimal("0.000")

    def key(pair):
        row, previous_period = pair
        priority = {"morning": 0, "daily": 1, "evening": 2}.get(previous_period.period_code, 0)
        return (previous_period.business_date, priority, previous_period.id)

    previous_row, _previous_period = max(candidates, key=key)
    return Decimal(str(previous_row.carried_quantity or 0))


def preview_period_close(period):
    """Calculate quantities from source ledgers without saving a close."""
    products = db.session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.is_default.desc(), Product.name.asc())
    ).all()
    if not products:
        raise ClosingRuleError("أضف صنفًا مخبوزًا واحدًا على الأقل قبل إقفال الفترة.")

    product_ids = [product.id for product in products]
    produced_map = {
        product_id: Decimal(str(quantity or 0))
        for product_id, quantity in db.session.execute(
            select(DoughBatch.product_id, func.sum(DoughBatch.produced_quantity))
            .where(DoughBatch.period_id == period.id)
            .group_by(DoughBatch.product_id)
        ).all()
    }
    paid_map = {
        product_id: Decimal(str(quantity or 0))
        for product_id, quantity in db.session.execute(
            select(DistributionIssue.product_id, func.sum(DistributionIssue.quantity))
            .where(
                DistributionIssue.business_date == period.business_date,
                DistributionIssue.period_code == period.period_code,
                DistributionIssue.product_id.in_(product_ids),
            )
            .group_by(DistributionIssue.product_id)
        ).all()
    }
    free_map = {
        product_id: Decimal(str(quantity or 0))
        for product_id, quantity in db.session.execute(
            select(FreeDistribution.product_id, func.sum(FreeDistribution.quantity))
            .where(
                FreeDistribution.period_id == period.id,
                FreeDistribution.product_id.in_(product_ids),
            )
            .group_by(FreeDistribution.product_id)
        ).all()
    }

    rows = []
    for product in products:
        opening = _opening_quantity(period, product.id)
        produced = produced_map.get(product.id, Decimal("0.000"))
        paid = paid_map.get(product.id, Decimal("0.000"))
        free = free_map.get(product.id, Decimal("0.000"))
        available = (opening + produced).quantize(QTY)
        rows.append({
            "product": product,
            "product_id": product.id,
            "opening_quantity": opening.quantize(QTY),
            "produced_quantity": produced.quantize(QTY),
            "available_quantity": available,
            "paid_distribution_quantity": paid.quantize(QTY),
            "free_distribution_quantity": free.quantize(QTY),
            "damaged_quantity": Decimal("0.000"),
            "carried_quantity": Decimal("0.000"),
            "shop_sale_quantity": (available - paid - free).quantize(QTY),
            "shop_unit_price": Decimal(str(product.shop_price or 0)).quantize(CENT),
            "expected_shop_sales": Decimal("0.00"),
        })
    return rows


def calculate_close_rows(period, damaged_quantities=None, carried_quantities=None):
    damaged_quantities = damaged_quantities or {}
    carried_quantities = carried_quantities or {}
    rows = preview_period_close(period)
    expected_total = Decimal("0.00")
    for row in rows:
        product_id = row["product_id"]
        damaged = _decimal(damaged_quantities.get(product_id, 0), "الكمية التالفة", QTY)
        carried = _decimal(carried_quantities.get(product_id, 0), "الكمية المرحلة", QTY)
        available = row["available_quantity"]
        accounted = (
            row["paid_distribution_quantity"]
            + row["free_distribution_quantity"]
            + damaged
            + carried
        ).quantize(QTY)
        shop_sale = (available - accounted).quantize(QTY)
        if shop_sale < 0:
            raise ClosingRuleError(
                f"الكميات المصروفة والتالفة والمرحلة تتجاوز المتاح من صنف «{row['product'].name}»."
            )
        price = row["shop_unit_price"]
        if shop_sale > 0 and price <= 0:
            raise ClosingRuleError(
                f"سعر البيع المباشر للصنف «{row['product'].name}» غير مضبوط. حدّد سعر المحل أولًا."
            )
        expected = (shop_sale * price).quantize(CENT, rounding=ROUND_HALF_UP)
        row.update({
            "damaged_quantity": damaged,
            "carried_quantity": carried,
            "shop_sale_quantity": shop_sale,
            "expected_shop_sales": expected,
        })
        expected_total += expected
    return rows, expected_total.quantize(CENT)


def close_period_with_handover(
    *,
    period_id,
    employee_id,
    received_amount,
    expenses_amount,
    handed_to_cash_amount,
    damaged_quantities,
    carried_quantities,
    statement=None,
    actor_id=None,
):
    """Atomically create close rows, handover, expense and cash movements."""
    period = db.session.scalar(
        select(BusinessPeriod).where(BusinessPeriod.id == period_id).with_for_update()
    )
    if period is None:
        raise ClosingRuleError("الفترة المحددة غير موجودة.")
    if period.status != "open":
        raise ClosingRuleError("هذه الفترة مختتمة بالفعل ولا يمكن إقفالها مرة أخرى.")
    if db.session.scalar(select(PeriodHandover.id).where(PeriodHandover.period_id == period.id)):
        raise ClosingRuleError("يوجد تسليم مسجل لهذه الفترة بالفعل.")

    employee = db.session.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.is_active.is_(True))
    )
    if employee is None:
        raise ClosingRuleError("اختر مستلمًا/موظفًا نشطًا.")

    received = _decimal(received_amount, "المبلغ المستلم", CENT)
    expenses_value = _decimal(expenses_amount, "الخرجيات", CENT)
    handed = _decimal(handed_to_cash_amount, "المبلغ المسلم", CENT)
    if (handed + expenses_value).quantize(CENT) != received:
        raise ClosingRuleError(
            "يجب أن يساوي المبلغ المسلم للصندوق مضافًا إليه الخرجيات إجمالي المبلغ المستلم، حتى لا تبقى نقدية غير مفسرة."
        )

    rows, expected = calculate_close_rows(period, damaged_quantities, carried_quantities)
    account = db.session.scalar(
        select(CashAccount)
        .where(CashAccount.is_main.is_(True), CashAccount.is_active.is_(True))
        .with_for_update()
    )
    if account is None:
        raise ClosingRuleError("لم يتم إعداد الصندوق الرئيسي.")

    existing_cash = db.session.execute(
        select(
            func.coalesce(
                func.sum(
                    func.case(
                        (CashMovement.direction == "in", CashMovement.amount),
                        else_=-CashMovement.amount,
                    )
                ),
                0,
            )
        ).where(CashMovement.cash_account_id == account.id)
    ).scalar_one()
    if Decimal(str(existing_cash or 0)) + received < expenses_value:
        raise ClosingRuleError("الرصيد النقدي الناتج لا يكفي لتسجيل خرجيات الفترة.")

    try:
        for row in rows:
            db.session.add(PeriodCloseProduct(
                period_id=period.id,
                product_id=row["product_id"],
                opening_quantity=row["opening_quantity"],
                produced_quantity=row["produced_quantity"],
                paid_distribution_quantity=row["paid_distribution_quantity"],
                free_distribution_quantity=row["free_distribution_quantity"],
                damaged_quantity=row["damaged_quantity"],
                carried_quantity=row["carried_quantity"],
                shop_sale_quantity=row["shop_sale_quantity"],
                shop_unit_price=row["shop_unit_price"],
                expected_shop_sales=row["expected_shop_sales"],
                statement=(statement or "").strip() or None,
                created_by_id=actor_id,
            ))
        handover = PeriodHandover(
            period_id=period.id,
            receiver_employee_id=employee.id,
            received_amount=received,
            expenses_amount=expenses_value,
            handed_to_cash_amount=handed,
            calculated_expected_amount=expected,
            cash_difference=(expected - received).quantize(CENT),
            statement=(statement or "").strip() or None,
            created_by_id=actor_id,
        )
        db.session.add(handover)
        db.session.flush()

        if received > 0:
            db.session.add(CashMovement(
                cash_account_id=account.id,
                movement_type="period_sales_receipt",
                direction="in",
                amount=received,
                business_date=period.business_date,
                statement=f"متحصلات بيع مباشر — {period.business_date.isoformat()} — {period.period_code}",
                source_type="period_handover_receipt",
                source_id=handover.id,
                created_by_id=actor_id,
            ))
        if expenses_value > 0:
            expense = Expense(
                title=f"خرجيات الفترة {period.business_date.isoformat()}",
                amount=expenses_value,
                cash_account_id=account.id,
                business_date=period.business_date,
                period_id=period.id,
                statement=(statement or "").strip() or "خرجيات معتمدة ضمن تسليم الفترة",
                created_by_id=actor_id,
            )
            db.session.add(expense)
            db.session.flush()
            db.session.add(CashMovement(
                cash_account_id=account.id,
                movement_type="expense",
                direction="out",
                amount=expenses_value,
                business_date=period.business_date,
                statement=expense.title,
                source_type="expense",
                source_id=expense.id,
                created_by_id=actor_id,
            ))

        period.status = "closed"
        period.closed_at = utc_now()
        period.closed_by_id = actor_id
        db.session.commit()
        return handover, rows, expected
    except IntegrityError as exc:
        db.session.rollback()
        raise ClosingRuleError("تم إقفال الفترة أو تسجيل التسليم من طلب آخر؛ لم يتم تكرار العملية.") from exc
    except Exception:
        db.session.rollback()
        raise


def get_closed_period_summary(period):
    rows = db.session.scalars(
        select(PeriodCloseProduct)
        .where(PeriodCloseProduct.period_id == period.id)
        .order_by(PeriodCloseProduct.product_id.asc())
    ).all()
    handover = db.session.scalar(
        select(PeriodHandover).where(PeriodHandover.period_id == period.id)
    )
    return rows, handover
