"""Store daily target products and quantities for free recipients.
Revision ID: 20261014_0007
Revises: 20261014_0006
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0007"
down_revision = "20261014_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("free_recipients", sa.Column("default_product_id", sa.Integer(), nullable=True))
    op.add_column("free_recipients", sa.Column("daily_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"))
    op.create_index("ix_free_recipients_default_product_id", "free_recipients", ["default_product_id"])
    op.create_foreign_key("fk_free_recipients_default_product_id_products", "free_recipients", "products", ["default_product_id"], ["id"], ondelete="RESTRICT")
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE free_recipients
        SET default_product_id = (SELECT fd.product_id FROM free_distributions fd WHERE fd.recipient_id = free_recipients.id ORDER BY fd.created_at DESC, fd.id DESC LIMIT 1),
            daily_quantity = COALESCE((SELECT fd.quantity FROM free_distributions fd WHERE fd.recipient_id = free_recipients.id ORDER BY fd.created_at DESC, fd.id DESC LIMIT 1), 0)
    """))
    bind.execute(sa.text("""
        UPDATE free_recipients
        SET default_product_id = (SELECT p.id FROM products p WHERE p.is_active = TRUE AND p.is_default = TRUE ORDER BY p.id LIMIT 1)
        WHERE default_product_id IS NULL
    """))


def downgrade():
    op.drop_constraint("fk_free_recipients_default_product_id_products", "free_recipients", type_="foreignkey")
    op.drop_index("ix_free_recipients_default_product_id", table_name="free_recipients")
    op.drop_column("free_recipients", "daily_quantity")
    op.drop_column("free_recipients", "default_product_id")
