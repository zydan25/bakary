"""Persist raw-material counts and calculated consumption on period close.

Revision ID: 20261014_0006
Revises: 20261014_0005
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20261014_0006"
down_revision = "20261014_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "period_raw_material_closes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("opening_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("incoming_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("other_outgoing_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("calculated_consumption", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("previously_recorded_consumption", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("ending_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("opening_quantity >= 0", name="raw_close_opening_nonnegative"),
        sa.CheckConstraint("incoming_quantity >= 0", name="raw_close_incoming_nonnegative"),
        sa.CheckConstraint("other_outgoing_quantity >= 0", name="raw_close_other_outgoing_nonnegative"),
        sa.CheckConstraint("calculated_consumption >= 0", name="raw_close_consumption_nonnegative"),
        sa.CheckConstraint("previously_recorded_consumption >= 0", name="raw_close_previous_usage_nonnegative"),
        sa.CheckConstraint("ending_quantity >= 0", name="raw_close_ending_nonnegative"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_id", "item_id", name="uq_period_raw_material_close"),
    )
    op.create_index(
        "ix_period_raw_material_closes_period_id",
        "period_raw_material_closes",
        ["period_id"],
    )
    op.create_index(
        "ix_period_raw_material_closes_item_id",
        "period_raw_material_closes",
        ["item_id"],
    )


def downgrade():
    op.drop_index("ix_period_raw_material_closes_item_id", table_name="period_raw_material_closes")
    op.drop_index("ix_period_raw_material_closes_period_id", table_name="period_raw_material_closes")
    op.drop_table("period_raw_material_closes")
