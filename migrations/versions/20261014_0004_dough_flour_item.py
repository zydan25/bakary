"""Link dough batches to the raw-material flour item.

Revision ID: 20261014_0004
Revises: 20261014_0003
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20261014_0004"
down_revision = "20261014_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "dough_batches",
        sa.Column("flour_item_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dough_batches_flour_item_id_inventory_items",
        "dough_batches",
        "inventory_items",
        ["flour_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_dough_batches_flour_item_id",
        "dough_batches",
        ["flour_item_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_dough_batches_flour_item_id", table_name="dough_batches")
    op.drop_constraint(
        "fk_dough_batches_flour_item_id_inventory_items",
        "dough_batches",
        type_="foreignkey",
    )
    op.drop_column("dough_batches", "flour_item_id")
