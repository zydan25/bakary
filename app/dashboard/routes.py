"""Dashboard entry page and permission-safe quick shortcuts."""

from flask import render_template
from flask_login import current_user
from sqlalchemy import select

from app.auth.decorators import permission_required
from app.dashboard import dashboard_bp
from app.extensions import db
from app.models.setting import Setting


DEFAULT_QUICK_ACTIONS = {
    "product_new",
    "inventory_new",
    "production_batch",
    "employee_new",
    "free_recipient",
    "expense_new",
    "products",
    "distributor_new",
    "customer_new",
    "account",
}


@dashboard_bp.get("/")
@permission_required("dashboard.view")
def index():
    role_names = [role.name for role in current_user.roles]
    setting = db.session.scalar(
        select(Setting).where(Setting.key == "dashboard_quick_actions")
    )
    # Older installs have no saved preference, so keep the original buttons visible.
    quick_actions_enabled = (
        set(setting.value)
        if setting is not None and isinstance(setting.value, list)
        else set(DEFAULT_QUICK_ACTIONS)
    )
    return render_template(
        "dashboard/index.html",
        role_names=role_names,
        quick_actions_enabled=quick_actions_enabled,
    )
