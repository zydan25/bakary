"""Dashboard entry page. Business widgets are added by later project stages."""

from datetime import date

from flask import render_template
from flask_login import current_user

from app.auth.decorators import permission_required
from app.dashboard import dashboard_bp


@dashboard_bp.get("/")
@permission_required("dashboard.view")
def index():
    role_names = [role.name for role in current_user.roles]
    return render_template(
        "dashboard/index.html",
        today=date.today(),
        role_names=role_names,
    )
