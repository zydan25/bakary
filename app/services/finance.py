"""Cash-account balances, expenses, and transfers kept in a transaction."""

from datetime import date
from uuid import uuid4
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.expense import Expense
from app.models.finance import CashAccount, CashMovement, CashTransfer


CENT = Decimal("0.01")


class FinanceRuleError(ValueError):
    """A cash entry violates accounting rules."""


def money(value):
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FinanceRuleError("المبلغ غير صالح.") from exc
    if not amount.is_finite() or amount <= 0:
        raise FinanceRuleError("المبلغ يجب أن يكون أكبر من صفر.")
    return amount


def cash_account_balance(account_id):
    value = db.session.execute(
        select(func.coalesce(
            func.sum(case(
                (CashMovement.direction == "in", CashMovement.amount),
                else_=-CashMovement.amount,
            )),
            0,
        )).where(CashMovement.cash_account_id == account_id)
    ).scalar_one()
    return Decimal(str(value or 0)).quantize(CENT)


def create_cash_account(*, name, code, account_type="cash", actor_id=None):
    name = (name or "").strip()
    code = (code or "").strip().upper()
    if not name or not code:
        raise FinanceRuleError("اسم الحساب ورمزه مطلوبان.")
    if account_type not in {"cash", "bank", "other"}:
        raise FinanceRuleError("نوع الحساب غير صحيح.")
    existing = db.session.scalar(select(CashAccount.id).where(
        (func.upper(CashAccount.code) == code) | (CashAccount.name == name)
    ))
    if existing:
        raise FinanceRuleError("رمز الحساب أو اسمه مستخدم بالفعل.")
    account = CashAccount(
        code=code,
        name=name,
        account_type=account_type,
        is_main=False,
        is_active=True,
        created_by_id=actor_id,
    )
    db.session.add(account)
    try:
        db.session.commit()
        return account
    except IntegrityError as exc:
        db.session.rollback()
        raise FinanceRuleError("يوجد حساب بنفس الرمز أو الاسم.") from exc


def create_expense(*, title, amount, cash_account_id, business_date=None, statement=None, period_id=None, actor_id=None, request_key=None):
    amount = money(amount)
    title = (title or "").strip()
    if not title:
        raise FinanceRuleError("اسم المصروف مطلوب.")
    account = db.session.scalar(
        select(CashAccount).where(
            CashAccount.id == cash_account_id,
            CashAccount.is_active.is_(True),
        ).with_for_update()
    )
    if account is None:
        raise FinanceRuleError("الحساب النقدي غير موجود أو موقوف.")
    if cash_account_balance(account.id) < amount:
        raise FinanceRuleError("رصيد الحساب لا يكفي لتسجيل هذا المصروف.")
    key = (request_key or "").strip()
    if not key:
        raise FinanceRuleError("انتهت صلاحية نموذج المصروف. أعد فتحه وحاول مجددًا.")
    prior = db.session.scalar(select(Expense).where(Expense.request_key == key))
    if prior is not None:
        return prior, False
    expense = Expense(
        title=title,
        amount=amount,
        cash_account_id=account.id,
        business_date=business_date or date.today(),
        period_id=period_id,
        statement=(statement or "").strip() or None,
        request_key=key,
        created_by_id=actor_id,
    )
    try:
        db.session.add(expense)
        db.session.flush()
        db.session.add(CashMovement(
            cash_account_id=account.id,
            movement_type="expense",
            direction="out",
            amount=amount,
            business_date=expense.business_date,
            statement=expense.title + ((" — " + expense.statement) if expense.statement else ""),
            source_type="expense",
            source_id=expense.id,
            created_by_id=actor_id,
        ))
        db.session.commit()
        return expense
    except IntegrityError as exc:
        db.session.rollback()
        prior = db.session.scalar(select(Expense).where(Expense.request_key == key))
        if prior is not None:
            return prior, False
        raise FinanceRuleError("تعذر حفظ المصروف بسبب تعارض في البيانات.") from exc
    except Exception:
        db.session.rollback()
        raise


def create_cash_transfer(*, source_account_id, target_account_id, amount, business_date=None, statement=None, actor_id=None, request_key=None):
    amount = money(amount)
    if source_account_id == target_account_id:
        raise FinanceRuleError("اختر حسابين مختلفين للتحويل.")
    source = db.session.scalar(
        select(CashAccount).where(
            CashAccount.id == source_account_id,
            CashAccount.is_active.is_(True),
        ).with_for_update()
    )
    target = db.session.scalar(
        select(CashAccount).where(
            CashAccount.id == target_account_id,
            CashAccount.is_active.is_(True),
        ).with_for_update()
    )
    if source is None or target is None:
        raise FinanceRuleError("حساب المصدر أو الوجهة غير موجود أو موقوف.")
    if cash_account_balance(source.id) < amount:
        raise FinanceRuleError("رصيد حساب المصدر لا يكفي للتحويل.")

    key = (request_key or "").strip()
    if not key:
        raise FinanceRuleError("انتهت صلاحية نموذج التحويل. أعد فتحه وحاول مجددًا.")
    prior = db.session.scalar(select(CashTransfer).where(CashTransfer.request_key == key))
    if prior is not None:
        return prior, False
    transfer = CashTransfer(
        request_key=key,
        source_account_id=source.id,
        target_account_id=target.id,
        amount=amount,
        business_date=business_date or date.today(),
        statement=(statement or "").strip() or None,
        created_by_id=actor_id,
    )
    try:
        db.session.add(transfer)
        db.session.flush()
        description = transfer.statement or f"تحويل من {source.name} إلى {target.name}"
        db.session.add_all([
            CashMovement(
                cash_account_id=source.id,
                movement_type="cash_transfer",
                direction="out",
                amount=amount,
                business_date=transfer.business_date,
                statement=description,
                source_type="cash_transfer_out",
                source_id=transfer.id,
                created_by_id=actor_id,
            ),
            CashMovement(
                cash_account_id=target.id,
                movement_type="cash_transfer",
                direction="in",
                amount=amount,
                business_date=transfer.business_date,
                statement=description,
                source_type="cash_transfer_in",
                source_id=transfer.id,
                created_by_id=actor_id,
            ),
        ])
        db.session.commit()
        return transfer
    except IntegrityError as exc:
        db.session.rollback()
        prior = db.session.scalar(select(CashTransfer).where(CashTransfer.request_key == key))
        if prior is not None:
            return prior, False
        raise FinanceRuleError("تعذر حفظ التحويل؛ لم يتم تكراره.") from exc
    except Exception:
        db.session.rollback()
        raise
