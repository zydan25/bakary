"""Permission-aware consolidated daily report center."""

from datetime import date
from decimal import Decimal

from flask import abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import case, func, select

from app.extensions import db
from app.models.closing import PeriodCloseProduct
from app.models.distribution import DistributionIssue, PartyPayment
from app.models.expense import Expense
from app.models.finance import CashAccount, CashMovement
from app.models.free_distribution import FreeDistribution
from app.models.inventory import InventoryItem
from app.models.party import Party
from app.models.production import BusinessPeriod, DoughBatch
from app.models.product import Product
from app.reports import reports_bp
from app.services.inventory import inventory_balance


def _amount(value):
    return Decimal(str(value or 0))


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else date.today()
    except (TypeError, ValueError):
        return date.today()


def _has_any(*permissions):
    return any(current_user.has_permission(permission) for permission in permissions)


@reports_bp.get("/")
@login_required
def index():
    can_distribution = _has_any("distribution.reports", "distribution.issue", "distribution.payment")
    can_production = _has_any("production.view", "production.manage", "handover.manage")
    can_free = current_user.has_permission("free_distribution.manage")
    can_inventory = _has_any("inventory.view", "inventory.manage")
    can_finance = _has_any("finance.view", "finance.manage", "expenses.manage", "cash.accounts.manage")
    can_party = _has_any("parties.view", "parties.manage")
    if not (
        current_user.has_permission("reports.view")
        or current_user.has_permission("reports.export")
        or can_distribution or can_production or can_free or can_inventory or can_finance or can_party
    ):
        abort(403)

    selected_date = _parse_date(request.args.get("date"))
    totals = {}
    issue_by_type = []
    payment_by_type = []

    if can_distribution or can_party:
        issue_rows = db.session.execute(
            select(
                Party.party_type,
                func.coalesce(func.sum(DistributionIssue.quantity), 0),
                func.coalesce(func.sum(DistributionIssue.total_amount), 0),
                func.count(DistributionIssue.id),
            )
            .join(Party, DistributionIssue.party_id == Party.id)
            .where(DistributionIssue.business_date == selected_date)
            .group_by(Party.party_type)
        ).all()
        for party_type, quantity, amount, count in issue_rows:
            issue_by_type.append({
                "party_type": party_type,
                "label": "الموزعون" if party_type == "distributor" else "العملاء والنقاط",
                "quantity": _amount(quantity),
                "amount": _amount(amount),
                "count": int(count or 0),
                "url": f"/distribution/reports/issues/{party_type}?date={selected_date.isoformat()}",
            })
        payment_rows = db.session.execute(
            select(
                Party.party_type,
                func.coalesce(func.sum(PartyPayment.amount), 0),
                func.count(PartyPayment.id),
            )
            .join(Party, PartyPayment.party_id == Party.id)
            .where(PartyPayment.business_date == selected_date)
            .group_by(Party.party_type)
        ).all()
        for party_type, amount, count in payment_rows:
            payment_by_type.append({
                "party_type": party_type,
                "label": "الموزعون" if party_type == "distributor" else "العملاء والنقاط",
                "amount": _amount(amount),
                "count": int(count or 0),
                "url": f"/distribution/reports/issues/{party_type}?date={selected_date.isoformat()}",
            })
        totals["issues_quantity"] = sum((row["quantity"] for row in issue_by_type), Decimal("0.000"))
        totals["issues_amount"] = sum((row["amount"] for row in issue_by_type), Decimal("0.00"))
        totals["payments_amount"] = sum((row["amount"] for row in payment_by_type), Decimal("0.00"))

    production_rows = []
    free_rows = []
    close_rows = []
    if can_production:
        production_rows = db.session.execute(
            select(
                Product.name,
                Product.unit_label,
                func.coalesce(func.sum(DoughBatch.produced_quantity), 0),
                func.count(DoughBatch.id),
            )
            .join(BusinessPeriod, DoughBatch.period_id == BusinessPeriod.id)
            .join(Product, DoughBatch.product_id == Product.id)
            .where(BusinessPeriod.business_date == selected_date)
            .group_by(Product.id, Product.name, Product.unit_label)
            .order_by(Product.name.asc())
        ).all()
        totals["produced_quantity"] = sum((_amount(row[2]) for row in production_rows), Decimal("0.000"))
        totals["batch_count"] = sum(int(row[3] or 0) for row in production_rows)

        close_data = db.session.execute(
            select(
                func.coalesce(func.sum(PeriodCloseProduct.expected_shop_sales), 0),
                func.coalesce(func.sum(PeriodCloseProduct.shop_sale_quantity), 0),
                func.coalesce(func.sum(PeriodCloseProduct.damaged_quantity), 0),
                func.coalesce(func.sum(PeriodCloseProduct.carried_quantity), 0),
                func.count(PeriodCloseProduct.id),
            )
            .join(BusinessPeriod, PeriodCloseProduct.period_id == BusinessPeriod.id)
            .where(
                BusinessPeriod.business_date == selected_date,
                BusinessPeriod.status == "closed",
            )
        ).one()
        close_rows.append({
            "expected_shop_sales": _amount(close_data[0]),
            "shop_sale_quantity": _amount(close_data[1]),
            "damaged_quantity": _amount(close_data[2]),
            "carried_quantity": _amount(close_data[3]),
            "count": int(close_data[4] or 0),
        })

    if can_free or can_production:
        free_rows = db.session.execute(
            select(
                Product.name,
                Product.unit_label,
                func.coalesce(func.sum(FreeDistribution.quantity), 0),
                func.count(FreeDistribution.id),
            )
            .join(BusinessPeriod, FreeDistribution.period_id == BusinessPeriod.id)
            .join(Product, FreeDistribution.product_id == Product.id)
            .where(BusinessPeriod.business_date == selected_date)
            .group_by(Product.id, Product.name, Product.unit_label)
            .order_by(Product.name.asc())
        ).all()
        totals["free_quantity"] = sum((_amount(row[2]) for row in free_rows), Decimal("0.000"))

    inventory_rows = []
    if can_inventory:
        items = db.session.scalars(
            select(InventoryItem)
            .where(InventoryItem.is_active.is_(True))
            .order_by(InventoryItem.name.asc())
        ).all()
        for item in items:
            balance = inventory_balance(item.id)
            inventory_rows.append({
                "name": item.name,
                "unit_label": item.unit_label,
                "balance": balance,
                "reorder_level": _amount(item.reorder_level),
                "is_low": balance <= _amount(item.reorder_level),
            })
        totals["inventory_items"] = len(inventory_rows)
        totals["low_stock_count"] = sum(1 for row in inventory_rows if row["is_low"])

    cash_rows = []
    if can_finance:
        inflow, outflow = db.session.execute(
            select(
                func.coalesce(func.sum(case((CashMovement.direction == "in", CashMovement.amount), else_=0)), 0),
                func.coalesce(func.sum(case((CashMovement.direction == "out", CashMovement.amount), else_=0)), 0),
            ).where(CashMovement.business_date == selected_date)
        ).one()
        expense_total = db.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.business_date == selected_date)
        )
        cash_rows = db.session.scalars(
            select(CashAccount)
            .where(CashAccount.is_active.is_(True))
            .order_by(CashAccount.is_main.desc(), CashAccount.name.asc())
        ).all()
        totals["cash_in"] = _amount(inflow)
        totals["cash_out"] = _amount(outflow)
        totals["expenses"] = _amount(expense_total)
        totals["cash_account_count"] = len(cash_rows)

    closed_summary = close_rows[0] if close_rows else None
    return render_template(
        "reports/index.html",
        selected_date=selected_date,
        totals=totals,
        issue_by_type=issue_by_type,
        payment_by_type=payment_by_type,
        production_rows=production_rows,
        free_rows=free_rows,
        inventory_rows=inventory_rows,
        cash_rows=cash_rows,
        closed_summary=closed_summary,
        can_distribution=can_distribution,
        can_production=can_production,
        can_free=can_free,
        can_inventory=can_inventory,
        can_finance=can_finance,
        can_party=can_party,
    )
