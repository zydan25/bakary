"""Dashboard entry page and configurable quick shortcuts."""

from flask import render_template
from flask_login import current_user
from sqlalchemy import select

from app.auth.decorators import permission_required
from app.dashboard import dashboard_bp
from app.extensions import db
from app.models.setting import Setting
from app.services.dashboard import normalize_quick_actions


def _can_open_shortcut(path):
    checks = (
        (("/distribution/payment/",), ("distribution.payment",)),
        (("/distribution/issue/",), ("distribution.issue",)),
        (("/products",), ("products.view", "products.manage")),
        (("/inventory",), ("inventory.view", "inventory.manage")),
        (("/production",), ("production.view", "production.manage")),
        (("/staff/employees",), ("employees.manage",)),
        (("/staff/roles",), ("users.manage",)),
        (("/operations/free-distribution",), ("free_distribution.manage",)),
        (("/finance/expenses",), ("expenses.manage",)),
        (("/finance",), ("finance.view", "finance.manage", "expenses.manage", "cash.accounts.manage")),
        (("/parties",), ("parties.view", "parties.manage")),
        (("/reports",), ("reports.view", "reports.export")),
    )
    for prefixes, permissions in checks:
        if any(path.startswith(prefix) for prefix in prefixes):
            return any(current_user.has_permission(permission) for permission in permissions)
    # Custom links remain configurable; destination routes still enforce authorization.
    return True


@dashboard_bp.get("/")
@permission_required("dashboard.view")
def index():
    role_names = [role.name for role in current_user.roles]
    setting = db.session.scalar(
        select(Setting).where(Setting.key == "dashboard_quick_actions")
    )
    configured = normalize_quick_actions(setting.value if setting is not None else None)
    quick_actions = [
        action for action in configured
        if action["enabled"] and _can_open_shortcut(action["url"].split("?", 1)[0])
    ]
    theme_setting = db.session.scalar(
        select(Setting).where(Setting.key == "dashboard_card_theme")
    )
    dashboard_card_theme = (
        theme_setting.value
        if theme_setting is not None and theme_setting.value in {"current", "water_pos"}
        else "current"
    )
    return render_template(
        "dashboard/index.html",
        role_names=role_names,
        quick_actions=quick_actions,
        dashboard_card_theme=dashboard_card_theme,
    )
