"""Add idempotency key to expenses.

Revision ID: 20261014_0005
Revises: 20261014_0004
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20261014_0005"
down_revision = "20261014_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expenses", sa.Column("request_key", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_expenses_request_key", "expenses", ["request_key"])


def downgrade():
    op.drop_constraint("uq_expenses_request_key", "expenses", type_="unique")
    op.drop_column("expenses", "request_key")
