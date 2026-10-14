"""Inventory, employees, production periods, free issue, closing and expenses.

Revision ID: 20261014_0003
Revises: 20261014_0002
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20261014_0003"
down_revision = "20261014_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("job_title", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_employees_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_employees_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_employees"),
        sa.UniqueConstraint("user_id", name="uq_employees_user_id"),
    )
    op.create_index("ix_employees_full_name", "employees", ["full_name"], unique=False)
    op.create_index("ix_employees_phone", "employees", ["phone"], unique=False)
    op.create_index("ix_employees_is_active", "employees", ["is_active"], unique=False)

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("unit_label", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_inventory_items_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_items"),
        sa.UniqueConstraint("name", name="uq_inventory_items_name"),
    )
    op.create_index("ix_inventory_items_code", "inventory_items", ["code"], unique=True)
    op.create_index("ix_inventory_items_is_active", "inventory_items", ["is_active"], unique=False)

    op.create_table(
        "business_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("period_code", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_by_id", sa.Integer(), nullable=True),
        sa.Column("closed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opened_by_id"], ["users.id"], name="fk_business_periods_opened_by_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by_id"], ["users.id"], name="fk_business_periods_closed_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_business_periods"),
        sa.UniqueConstraint("business_date", "period_code", name="uq_business_period_date_code"),
    )
    op.create_index("ix_business_periods_business_date", "business_periods", ["business_date"], unique=False)
    op.create_index("ix_business_periods_status", "business_periods", ["status"], unique=False)

    op.create_table(
        "dough_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("flour_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("produced_quantity > 0", name="ck_dough_batches_produced_quantity_positive"),
        sa.CheckConstraint("flour_quantity IS NULL OR flour_quantity >= 0", name="ck_dough_batches_flour_quantity_nonnegative"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], name="fk_dough_batches_period_id_business_periods", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_dough_batches_product_id_products", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_dough_batches_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_dough_batches"),
        sa.UniqueConstraint("idempotency_key", name="uq_dough_batches_idempotency"),
    )
    op.create_index("ix_dough_batches_period_id", "dough_batches", ["period_id"], unique=False)
    op.create_index("ix_dough_batches_product_id", "dough_batches", ["product_id"], unique=False)

    op.create_table(
        "period_ingredient_usages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_period_ingredient_usages_quantity_positive"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], name="fk_period_ingredient_usages_period_id_business_periods", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], name="fk_period_ingredient_usages_item_id_inventory_items", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_period_ingredient_usages_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_period_ingredient_usages"),
        sa.UniqueConstraint("period_id", "item_id", name="uq_period_ingredient_usage"),
    )
    op.create_index("ix_period_ingredient_usages_period_id", "period_ingredient_usages", ["period_id"], unique=False)
    op.create_index("ix_period_ingredient_usages_item_id", "period_ingredient_usages", ["item_id"], unique=False)

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_movements_quantity_positive"),
        sa.CheckConstraint("direction IN ('in', 'out')", name="ck_inventory_movements_direction_valid"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], name="fk_inventory_movements_item_id_inventory_items", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_inventory_movements_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_movements"),
        sa.UniqueConstraint("source_type", "source_id", "item_id", name="uq_inventory_movement_source_item"),
    )
    op.create_index("ix_inventory_movements_item_id", "inventory_movements", ["item_id"], unique=False)
    op.create_index("ix_inventory_movements_business_date", "inventory_movements", ["business_date"], unique=False)

    op.create_table(
        "free_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_free_recipients_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_free_recipients"),
    )
    op.create_index("ix_free_recipients_name", "free_recipients", ["name"], unique=False)
    op.create_index("ix_free_recipients_is_active", "free_recipients", ["is_active"], unique=False)

    op.create_table(
        "free_distributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_free_distributions_quantity_positive"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], name="fk_free_distributions_period_id_business_periods", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_id"], ["free_recipients.id"], name="fk_free_distributions_recipient_id_free_recipients", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_free_distributions_product_id_products", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_free_distributions_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_free_distributions"),
        sa.UniqueConstraint("period_id", "recipient_id", "product_id", name="uq_free_distribution_period_recipient_product"),
    )
    op.create_index("ix_free_distributions_period_id", "free_distributions", ["period_id"], unique=False)
    op.create_index("ix_free_distributions_recipient_id", "free_distributions", ["recipient_id"], unique=False)
    op.create_index("ix_free_distributions_product_id", "free_distributions", ["product_id"], unique=False)

    op.create_table(
        "period_close_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("opening_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("paid_distribution_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("free_distribution_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("damaged_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("carried_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("shop_sale_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("shop_unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_shop_sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("opening_quantity >= 0", name="ck_period_close_products_opening_quantity_nonnegative"),
        sa.CheckConstraint("produced_quantity >= 0", name="ck_period_close_products_produced_quantity_nonnegative"),
        sa.CheckConstraint("paid_distribution_quantity >= 0", name="ck_period_close_products_paid_distribution_nonnegative"),
        sa.CheckConstraint("free_distribution_quantity >= 0", name="ck_period_close_products_free_distribution_nonnegative"),
        sa.CheckConstraint("damaged_quantity >= 0", name="ck_period_close_products_damaged_quantity_nonnegative"),
        sa.CheckConstraint("carried_quantity >= 0", name="ck_period_close_products_carried_quantity_nonnegative"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], name="fk_period_close_products_period_id_business_periods", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_period_close_products_product_id_products", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_period_close_products_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_period_close_products"),
        sa.UniqueConstraint("period_id", "product_id", name="uq_period_close_product"),
    )
    op.create_index("ix_period_close_products_period_id", "period_close_products", ["period_id"], unique=False)
    op.create_index("ix_period_close_products_product_id", "period_close_products", ["product_id"], unique=False)

    op.create_table(
        "period_handovers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("receiver_employee_id", sa.Integer(), nullable=False),
        sa.Column("received_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expenses_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("handed_to_cash_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("calculated_expected_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("cash_difference", sa.Numeric(14, 2), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("received_amount >= 0", name="ck_period_handovers_received_amount_nonnegative"),
        sa.CheckConstraint("expenses_amount >= 0", name="ck_period_handovers_expenses_amount_nonnegative"),
        sa.CheckConstraint("handed_to_cash_amount >= 0", name="ck_period_handovers_handed_to_cash_nonnegative"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], name="fk_period_handovers_period_id_business_periods", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["receiver_employee_id"], ["employees.id"], name="fk_period_handovers_receiver_employee_id_employees", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_period_handovers_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_period_handovers"),
        sa.UniqueConstraint("period_id", name="uq_period_handover_period"),
    )
    op.create_index("ix_period_handovers_period_id", "period_handovers", ["period_id"], unique=False)
    op.create_index("ix_period_handovers_receiver_employee_id", "period_handovers", ["receiver_employee_id"], unique=False)

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("cash_account_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], name="fk_expenses_cash_account_id_cash_accounts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["period_id"], ["business_periods.id"], name="fk_expenses_period_id_business_periods", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_expenses_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_title", "expenses", ["title"], unique=False)
    op.create_index("ix_expenses_cash_account_id", "expenses", ["cash_account_id"], unique=False)
    op.create_index("ix_expenses_business_date", "expenses", ["business_date"], unique=False)
    op.create_index("ix_expenses_period_id", "expenses", ["period_id"], unique=False)

    op.create_table(
        "cash_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_account_id", sa.Integer(), nullable=False),
        sa.Column("destination_account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_cash_transfers_amount_positive"),
        sa.CheckConstraint("source_account_id <> destination_account_id", name="ck_cash_transfers_accounts_different"),
        sa.ForeignKeyConstraint(["source_account_id"], ["cash_accounts.id"], name="fk_cash_transfers_source_account_id_cash_accounts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_account_id"], ["cash_accounts.id"], name="fk_cash_transfers_destination_account_id_cash_accounts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_cash_transfers_created_by_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_cash_transfers"),
        sa.UniqueConstraint("request_key", name="uq_cash_transfers_request_key"),
    )
    op.create_index("ix_cash_transfers_source_account_id", "cash_transfers", ["source_account_id"], unique=False)
    op.create_index("ix_cash_transfers_destination_account_id", "cash_transfers", ["destination_account_id"], unique=False)
    op.create_index("ix_cash_transfers_business_date", "cash_transfers", ["business_date"], unique=False)


def downgrade():
    op.drop_index("ix_cash_transfers_business_date", table_name="cash_transfers")
    op.drop_index("ix_cash_transfers_destination_account_id", table_name="cash_transfers")
    op.drop_index("ix_cash_transfers_source_account_id", table_name="cash_transfers")
    op.drop_table("cash_transfers")

    op.drop_index("ix_expenses_period_id", table_name="expenses")
    op.drop_index("ix_expenses_business_date", table_name="expenses")
    op.drop_index("ix_expenses_cash_account_id", table_name="expenses")
    op.drop_index("ix_expenses_title", table_name="expenses")
    op.drop_table("expenses")

    op.drop_index("ix_period_handovers_receiver_employee_id", table_name="period_handovers")
    op.drop_index("ix_period_handovers_period_id", table_name="period_handovers")
    op.drop_table("period_handovers")

    op.drop_index("ix_period_close_products_product_id", table_name="period_close_products")
    op.drop_index("ix_period_close_products_period_id", table_name="period_close_products")
    op.drop_table("period_close_products")

    op.drop_index("ix_free_distributions_product_id", table_name="free_distributions")
    op.drop_index("ix_free_distributions_recipient_id", table_name="free_distributions")
    op.drop_index("ix_free_distributions_period_id", table_name="free_distributions")
    op.drop_table("free_distributions")

    op.drop_index("ix_free_recipients_is_active", table_name="free_recipients")
    op.drop_index("ix_free_recipients_name", table_name="free_recipients")
    op.drop_table("free_recipients")

    op.drop_index("ix_inventory_movements_business_date", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_item_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_index("ix_period_ingredient_usages_item_id", table_name="period_ingredient_usages")
    op.drop_index("ix_period_ingredient_usages_period_id", table_name="period_ingredient_usages")
    op.drop_table("period_ingredient_usages")

    op.drop_index("ix_dough_batches_product_id", table_name="dough_batches")
    op.drop_index("ix_dough_batches_period_id", table_name="dough_batches")
    op.drop_table("dough_batches")

    op.drop_index("ix_business_periods_status", table_name="business_periods")
    op.drop_index("ix_business_periods_business_date", table_name="business_periods")
    op.drop_table("business_periods")

    op.drop_index("ix_inventory_items_is_active", table_name="inventory_items")
    op.drop_index("ix_inventory_items_code", table_name="inventory_items")
    op.drop_table("inventory_items")

    op.drop_index("ix_employees_is_active", table_name="employees")
    op.drop_index("ix_employees_phone", table_name="employees")
    op.drop_index("ix_employees_full_name", table_name="employees")
    op.drop_table("employees")
