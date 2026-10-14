"""Cash-account administration, expenses and internal transfers."""

from datetime import date
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.finance import finance_bp
from app.finance.forms import CashAccountForm, ExpenseForm, TransferForm
from app.models.expense import CashTransfer, Expense
from app.models.finance import CashAccount, CashMovement
from app.services.finance import (
    FinanceRuleError,
    cash_account_balance,
    create_cash_account,
    create_cash_transfer,
    create_expense,
)


def _require_any(*permissions):
    if not any(current_user.has_permission(permission) for permission in permissions):
        abort(403)


def _active_accounts():
    return db.session.scalars(
        select(CashAccount).where(CashAccount.is_active.is_(True)).order_by(CashAccount.is_main.desc(), CashAccount.name.asc())
    ).all()


def _account_balance_rows(accounts):
    return [{"account": account, "balance": cash_account_balance(account.id)} for account in accounts]


@finance_bp.get("/")
@login_required
def index():
    _require_any("finance.view", "cash.accounts.manage", "finance.manage", "expenses.manage")
    accounts = db.session.scalars(
        select(CashAccount).order_by(CashAccount.is_main.desc(), CashAccount.is_active.desc(), CashAccount.name.asc())
    ).all()
    balance_rows = _account_balance_rows(accounts)
    movements = db.session.scalars(
        select(CashMovement).order_by(
            CashMovement.business_date.desc(), CashMovement.created_at.desc(), CashMovement.id.desc()
        ).limit(20)
    ).all()
    account_by_id = {account.id: account for account in accounts}
    movement_rows = [{
        "movement": movement,
        "account_name": account_by_id[movement.cash_account_id].name if movement.cash_account_id in account_by_id else "حساب غير معروف",
        "signed_amount": movement.amount if movement.direction == "in" else -movement.amount,
    } for movement in movements]
    account_form = CashAccountForm()
    return render_template(
        "finance/index.html",
        balance_rows=balance_rows,
        movement_rows=movement_rows,
        account_form=account_form,
        can_manage_accounts=current_user.has_permission("cash.accounts.manage"),
        can_manage_expenses=current_user.has_permission("expenses.manage"),
        can_manage_transfers=current_user.has_permission("finance.manage"),
        show_account_form=request.args.get("action") == "new",
    )


@finance_bp.post("/accounts/")
@login_required
def add_account():
    _require_any("cash.accounts.manage")
    form = CashAccountForm()
    if form.validate_on_submit():
        try:
            create_cash_account(
                name=form.name.data,
                code=form.code.data,
                account_type=form.account_type.data,
                opening_balance=form.opening_balance.data,
                actor_id=current_user.id,
            )
            flash("تم إنشاء الحساب النقدي.", "success")
            return redirect(url_for("finance.index"))
        except FinanceRuleError as exc:
            flash(str(exc), "error")
    accounts = db.session.scalars(select(CashAccount).order_by(CashAccount.name.asc())).all()
    return render_template(
        "finance/index.html",
        balance_rows=_account_balance_rows(accounts),
        movement_rows=[],
        account_form=form,
        can_manage_accounts=True,
        can_manage_expenses=current_user.has_permission("expenses.manage"),
        can_manage_transfers=current_user.has_permission("finance.manage"),
        show_account_form=True,
    )


@finance_bp.route("/expenses/", methods=["GET", "POST"])
@login_required
def expenses():
    _require_any("finance.view", "expenses.manage")
    form = ExpenseForm()
    accounts = _active_accounts()
    form.cash_account_id.choices = [(0, "اختر الحساب...")] + [(row.id, row.name) for row in accounts]
    main = next((row for row in accounts if row.is_main), None)
    if request.method == "GET":
        form.cash_account_id.data = main.id if main else (accounts[0].id if accounts else 0)
        form.business_date.data = date.today()
        form.request_key.data = uuid4().hex
    if request.method == "POST":
        if not current_user.has_permission("expenses.manage"):
            abort(403)
        if form.validate_on_submit():
            try:
                expense, created = create_expense(
                    title=form.title.data,
                    amount=form.amount.data,
                    cash_account_id=form.cash_account_id.data,
                    business_date=form.business_date.data,
                    statement=form.statement.data,
                    actor_id=current_user.id,
                    request_key=form.request_key.data,
                )
                flash(
                    "تم تسجيل المصروف وحركة الصندوق." if created else "هذا المصروف مسجل بالفعل؛ لم يُكرر.",
                    "success" if created else "info",
                )
                return redirect(url_for("finance.expenses"))
            except FinanceRuleError as exc:
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                flash("تعذر تسجيل المصروف؛ لم يتم تأكيد العملية.", "error")
    rows = db.session.scalars(
        select(Expense).order_by(Expense.business_date.desc(), Expense.created_at.desc(), Expense.id.desc()).limit(100)
    ).all()
    account_map = {account.id: account.name for account in accounts}
    return render_template(
        "finance/expenses.html",
        rows=rows,
        account_map=account_map,
        accounts=accounts,
        form=form,
        can_manage=current_user.has_permission("expenses.manage"),
        show_form=request.args.get("action") == "new" or (request.method == "POST" and bool(form.errors)),
    )


@finance_bp.route("/transfers/", methods=["GET", "POST"])
@login_required
def transfers():
    _require_any("finance.view", "finance.manage")
    form = TransferForm()
    accounts = _active_accounts()
    choices = [(0, "اختر الحساب...")] + [(row.id, row.name) for row in accounts]
    form.source_account_id.choices = choices
    form.target_account_id.choices = choices
    main = next((row for row in accounts if row.is_main), None)
    other = next((row for row in accounts if not row.is_main), None)
    if request.method == "GET":
        form.source_account_id.data = main.id if main else (accounts[0].id if accounts else 0)
        form.target_account_id.data = other.id if other else 0
        form.business_date.data = date.today()
        form.request_key.data = uuid4().hex
    if request.method == "POST":
        if not current_user.has_permission("finance.manage"):
            abort(403)
        if form.validate_on_submit():
            try:
                transfer, created = create_cash_transfer(
                    source_account_id=form.source_account_id.data,
                    target_account_id=form.target_account_id.data,
                    amount=form.amount.data,
                    business_date=form.business_date.data,
                    statement=form.statement.data,
                    actor_id=current_user.id,
                    request_key=form.request_key.data,
                )
                flash(
                    "تم التحويل بين الحسابين وتسجيل الحركتين." if created else "هذا التحويل مسجل بالفعل؛ لم يُكرر.",
                    "success" if created else "info",
                )
                return redirect(url_for("finance.transfers"))
            except FinanceRuleError as exc:
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                flash("تعذر تسجيل التحويل؛ لم يتم تأكيد الحفظ.", "error")
    rows = db.session.scalars(
        select(CashTransfer).order_by(CashTransfer.business_date.desc(), CashTransfer.created_at.desc(), CashTransfer.id.desc()).limit(100)
    ).all()
    account_map = {account.id: account.name for account in accounts}
    return render_template(
        "finance/transfers.html",
        rows=rows,
        account_map=account_map,
        accounts=accounts,
        form=form,
        can_manage=current_user.has_permission("finance.manage"),
        show_form=request.args.get("action") == "new" or (request.method == "POST" and bool(form.errors)),
    )
