"""Atomic operations for party issues, receipts and balance queries."""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.distribution import DistributionIssue, PartyLedgerEntry, PartyPayment
from app.models.finance import CashAccount, CashMovement
from app.models.party import Party
from app.models.product import Product


CENT = Decimal("0.01")


class BusinessRuleError(ValueError):
    """A validated user operation violates a business rule."""


def money(value):
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BusinessRuleError("أدخل مبلغًا رقميًا صحيحًا.") from exc
    if not result.is_finite():
        raise BusinessRuleError("قيمة المبلغ غير صالحة.")
    return result


def party_balance(party_id, before_date=None):
    query = select(
        func.coalesce(func.sum(PartyLedgerEntry.debit_amount), 0),
        func.coalesce(func.sum(PartyLedgerEntry.credit_amount), 0),
    ).where(PartyLedgerEntry.party_id == party_id)
    if before_date is not None:
        query = query.where(PartyLedgerEntry.business_date < before_date)
    debit, credit = db.session.execute(query).one()
    return Decimal(str(debit or 0)) - Decimal(str(credit or 0))


def create_issue(
    *,
    party_id,
    product_id,
    quantity,
    business_date,
    period_code="daily",
    statement=None,
    actor_id=None,
    request_key,
):
    key = (request_key or "").strip()
    if not key or len(key) > 64:
        raise BusinessRuleError("انتهت صلاحية نموذج الصرف. أعد فتح النموذج وحاول مجددًا.")

    existing = db.session.scalar(
        select(DistributionIssue).where(DistributionIssue.request_key == key)
    )
    if existing is not None:
        return existing, False

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise BusinessRuleError("أدخل كمية صحيحة.") from exc
    if quantity <= 0:
        raise BusinessRuleError("يجب أن تكون الكمية أكبر من صفر.")

    party = db.session.scalar(
        select(Party).where(Party.id == party_id).with_for_update()
    )
    product = db.session.get(Product, product_id)
    if party is None or party.party_type not in {"distributor", "customer"}:
        raise BusinessRuleError("الحساب المحدد غير موجود.")
    if not party.is_active:
        raise BusinessRuleError("هذا الحساب موقوف ولا يمكن تسجيل صرف جديد.")
    if product is None or not product.is_active:
        raise BusinessRuleError("الصنف المحدد غير متاح.")

    unit_price = money(party.price_for(product))
    if unit_price <= 0:
        raise BusinessRuleError("سعر هذا الصنف غير مضبوط لهذا الحساب. حدّد السعر أولًا.")
    total = money(unit_price * quantity)

    try:
        issue = DistributionIssue(
            party_id=party.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total,
            business_date=business_date or date.today(),
            period_code=period_code,
            statement=(statement or "").strip() or None,
            request_key=key,
            created_by_id=actor_id,
        )
        db.session.add(issue)
        db.session.flush()

        db.session.add(
            PartyLedgerEntry(
                party_id=party.id,
                entry_type="issue",
                debit_amount=total,
                credit_amount=Decimal("0.00"),
                business_date=issue.business_date,
                source_type="distribution_issue",
                source_id=issue.id,
                statement=issue.statement,
                created_by_id=actor_id,
            )
        )
        db.session.commit()
        return issue, True
    except IntegrityError:
        db.session.rollback()
        duplicate = db.session.scalar(
            select(DistributionIssue).where(DistributionIssue.request_key == key)
        )
        if duplicate is not None:
            return duplicate, False
        raise
    except Exception:
        db.session.rollback()
        raise


def create_payment(
    *,
    party_id,
    amount,
    business_date,
    period_code="daily",
    statement=None,
    actor_id=None,
    request_key,
):
    key = (request_key or "").strip()
    if not key or len(key) > 64:
        raise BusinessRuleError("انتهت صلاحية نموذج الدفع. أعد فتح النموذج وحاول مجددًا.")

    existing = db.session.scalar(
        select(PartyPayment).where(PartyPayment.request_key == key)
    )
    if existing is not None:
        return existing, False

    amount = money(amount)
    if amount <= 0:
        raise BusinessRuleError("يجب أن يكون المبلغ المدفوع أكبر من صفر.")

    party = db.session.scalar(
        select(Party).where(Party.id == party_id).with_for_update()
    )
    if party is None or party.party_type not in {"distributor", "customer"}:
        raise BusinessRuleError("الحساب المحدد غير موجود.")
    if not party.is_active:
        raise BusinessRuleError("هذا الحساب موقوف ولا يمكن تسجيل دفعة جديدة.")

    main_account = db.session.scalar(
        select(CashAccount)
        .where(CashAccount.is_main.is_(True), CashAccount.is_active.is_(True))
        .with_for_update()
    )
    if main_account is None:
        raise BusinessRuleError("لم يتم إعداد الصندوق الرئيسي بعد.")

    try:
        payment = PartyPayment(
            party_id=party.id,
            amount=amount,
            business_date=business_date or date.today(),
            period_code=period_code,
            statement=(statement or "").strip() or None,
            request_key=key,
            created_by_id=actor_id,
        )
        db.session.add(payment)
        db.session.flush()

        db.session.add(
            PartyLedgerEntry(
                party_id=party.id,
                entry_type="payment",
                debit_amount=Decimal("0.00"),
                credit_amount=amount,
                business_date=payment.business_date,
                source_type="party_payment",
                source_id=payment.id,
                statement=payment.statement,
                created_by_id=actor_id,
            )
        )
        db.session.add(
            CashMovement(
                cash_account_id=main_account.id,
                party_id=party.id,
                movement_type="party_payment",
                direction="in",
                amount=amount,
                business_date=payment.business_date,
                statement=payment.statement or f"تحصيل من {party.name}",
                source_type="party_payment",
                source_id=payment.id,
                created_by_id=actor_id,
            )
        )
        db.session.commit()
        return payment, True
    except IntegrityError:
        db.session.rollback()
        duplicate = db.session.scalar(
            select(PartyPayment).where(PartyPayment.request_key == key)
        )
        if duplicate is not None:
            return duplicate, False
        raise
    except Exception:
        db.session.rollback()
        raise


def party_period_summary(party_id, start_date, end_date, period_code=None):
    """Summarize a day or a single operating period, carrying earlier debts forward."""
    party = db.session.get(Party, party_id)
    if party is None:
        raise BusinessRuleError("الحساب المحدد غير موجود.")

    opening_balance = party_balance(party_id, before_date=start_date)
    if period_code == "evening":
        # The morning period on the same date is an opening balance for the evening.
        morning_issues = db.session.scalar(
            select(func.coalesce(func.sum(DistributionIssue.total_amount), 0)).where(
                DistributionIssue.party_id == party_id,
                DistributionIssue.business_date == start_date,
                DistributionIssue.period_code == "morning",
            )
        ) or 0
        morning_payments = db.session.scalar(
            select(func.coalesce(func.sum(PartyPayment.amount), 0)).where(
                PartyPayment.party_id == party_id,
                PartyPayment.business_date == start_date,
                PartyPayment.period_code == "morning",
            )
        ) or 0
        opening_balance += Decimal(str(morning_issues)) - Decimal(str(morning_payments))

    issue_stmt = select(
        func.coalesce(func.sum(DistributionIssue.quantity), 0),
        func.coalesce(func.sum(DistributionIssue.total_amount), 0),
        func.count(func.distinct(DistributionIssue.product_id)),
        func.min(DistributionIssue.unit_price),
        func.max(DistributionIssue.unit_price),
    ).where(
        DistributionIssue.party_id == party_id,
        DistributionIssue.business_date >= start_date,
        DistributionIssue.business_date <= end_date,
    )
    payment_stmt = select(func.coalesce(func.sum(PartyPayment.amount), 0)).where(
        PartyPayment.party_id == party_id,
        PartyPayment.business_date >= start_date,
        PartyPayment.business_date <= end_date,
    )
    if period_code is not None:
        issue_stmt = issue_stmt.where(DistributionIssue.period_code == period_code)
        payment_stmt = payment_stmt.where(PartyPayment.period_code == period_code)

    issue_rows = db.session.execute(issue_stmt).one()
    payment_total = db.session.scalar(payment_stmt) or 0
    quantity, issue_total, product_count, min_price, max_price = issue_rows
    opening_balance = Decimal(str(opening_balance))
    issue_total = Decimal(str(issue_total or 0))
    payment_total = Decimal(str(payment_total))
    total_due_before_payments = opening_balance + issue_total
    closing_balance = total_due_before_payments - payment_total
    unit_price = None
    if int(product_count or 0) == 1 and min_price is not None and max_price is not None:
        if Decimal(str(min_price)) == Decimal(str(max_price)):
            unit_price = Decimal(str(min_price))

    return {
        "party": party,
        "opening_balance": opening_balance,
        "quantity": Decimal(str(quantity or 0)),
        "issue_total": issue_total,
        "payment_total": payment_total,
        "arrears": opening_balance,
        "total_due": total_due_before_payments,
        "closing_balance": closing_balance,
        "unit_price": unit_price,
        "product_count": int(product_count or 0),
    }

def last_issue(party_id):
    return db.session.scalar(
        select(DistributionIssue)
        .where(DistributionIssue.party_id == party_id)
        .order_by(DistributionIssue.created_at.desc(), DistributionIssue.id.desc())
        .limit(1)
    )
