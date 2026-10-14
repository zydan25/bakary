"""Product catalog, parties, distribution ledgers and cash accounts.

Revision ID: 20261014_0002
Revises: 20261014_0001
Create Date: 2026-10-14
"""

from datetime import datetime, timezone
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "20261014_0002"
down_revision = "20261014_0001"
branch_labels = None
depends_on = None


def upgrade():
    now = datetime.now(timezone.utc)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("unit_label", sa.String(length=30), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("default_distributor_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("default_customer_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("shop_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_products_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("name", name="uq_products_name"),
    )
    op.create_index("ix_products_code", "products", ["code"], unique=True)
    op.create_index("ix_products_is_default", "products", ["is_default"], unique=False)
    op.create_index("ix_products_is_active", "products", ["is_active"], unique=False)

    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("party_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_parties_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_parties"),
    )
    op.create_index("ix_parties_party_type", "parties", ["party_type"], unique=False)
    op.create_index("ix_parties_name", "parties", ["name"], unique=False)
    op.create_index("ix_parties_phone", "parties", ["phone"], unique=False)
    op.create_index("ix_parties_is_active", "parties", ["is_active"], unique=False)

    op.create_table(
        "party_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["party_id"], ["parties.id"],
            name="fk_party_prices_party_id_parties",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_party_prices_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_party_prices"),
        sa.UniqueConstraint(
            "party_id", "product_id", name="uq_party_prices_party_product"
        ),
    )
    op.create_index("ix_party_prices_party_id", "party_prices", ["party_id"], unique=False)
    op.create_index("ix_party_prices_product_id", "party_prices", ["product_id"], unique=False)

    op.create_table(
        "distribution_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("period_code", sa.String(length=12), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_distribution_issues_quantity_positive"),
        sa.CheckConstraint(
            "unit_price >= 0 AND total_amount >= 0",
            name="ck_distribution_issues_amounts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["parties.id"],
            name="fk_distribution_issues_party_id_parties",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_distribution_issues_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_distribution_issues_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_distribution_issues"),
        sa.UniqueConstraint("request_key", name="uq_distribution_issues_request_key"),
    )
    op.create_index("ix_distribution_issues_party_id", "distribution_issues", ["party_id"], unique=False)
    op.create_index("ix_distribution_issues_product_id", "distribution_issues", ["product_id"], unique=False)
    op.create_index("ix_distribution_issues_business_date", "distribution_issues", ["business_date"], unique=False)

    op.create_table(
        "party_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("period_code", sa.String(length=12), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_party_payments_amount_positive"),
        sa.ForeignKeyConstraint(
            ["party_id"], ["parties.id"],
            name="fk_party_payments_party_id_parties",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_party_payments_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_party_payments"),
        sa.UniqueConstraint("request_key", name="uq_party_payments_request_key"),
    )
    op.create_index("ix_party_payments_party_id", "party_payments", ["party_id"], unique=False)
    op.create_index("ix_party_payments_business_date", "party_payments", ["business_date"], unique=False)

    op.create_table(
        "party_ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=24), nullable=False),
        sa.Column("debit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("credit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "debit_amount >= 0 AND credit_amount >= 0",
            name="ck_party_ledger_entries_ledger_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "NOT (debit_amount > 0 AND credit_amount > 0)",
            name="ck_party_ledger_entries_ledger_single_side",
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["parties.id"],
            name="fk_party_ledger_entries_party_id_parties",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_party_ledger_entries_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_party_ledger_entries"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_party_ledger_source"),
    )
    op.create_index("ix_party_ledger_entries_party_id", "party_ledger_entries", ["party_id"], unique=False)
    op.create_index("ix_party_ledger_entries_business_date", "party_ledger_entries", ["business_date"], unique=False)

    op.create_table(
        "cash_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("account_type", sa.String(length=24), nullable=False),
        sa.Column("is_main", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_cash_accounts_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cash_accounts"),
        sa.UniqueConstraint("code", name="uq_cash_accounts_code"),
        sa.UniqueConstraint("name", name="uq_cash_accounts_name"),
    )
    op.create_index("ix_cash_accounts_is_active", "cash_accounts", ["is_active"], unique=False)

    op.create_table(
        "cash_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cash_account_id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=True),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_cash_movements_amount_positive"),
        sa.CheckConstraint(
            "direction IN ('in', 'out')", name="ck_cash_movements_direction_valid"
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_id"], ["cash_accounts.id"],
            name="fk_cash_movements_cash_account_id_cash_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["parties.id"],
            name="fk_cash_movements_party_id_parties",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"],
            name="fk_cash_movements_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cash_movements"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_cash_movements_source"),
    )
    op.create_index("ix_cash_movements_cash_account_id", "cash_movements", ["cash_account_id"], unique=False)
    op.create_index("ix_cash_movements_party_id", "cash_movements", ["party_id"], unique=False)
    op.create_index("ix_cash_movements_business_date", "cash_movements", ["business_date"], unique=False)

    # Seed the required default bread product and the main cash account.
    op.execute(
        sa.text(
            "INSERT INTO products "
            "(name, code, unit_label, is_default, is_active, "
            "default_distributor_price, default_customer_price, shop_price, "
            "created_by_id, created_at, updated_at) "
            "VALUES (:name, :code, :unit_label, TRUE, TRUE, :zero, :zero, :zero, "
            "NULL, :created_at, :updated_at)"
        ).bindparams(
            name="روتي",
            code="ROTI",
            unit_label="حبة",
            zero=Decimal("0.00"),
            created_at=now,
            updated_at=now,
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO cash_accounts "
            "(code, name, account_type, is_main, is_active, created_by_id, created_at, updated_at) "
            "VALUES (:code, :name, 'cash', TRUE, TRUE, NULL, :created_at, :updated_at)"
        ).bindparams(
            code="main",
            name="الصندوق الرئيسي",
            created_at=now,
            updated_at=now,
        )
    )


def downgrade():
    op.drop_index("ix_cash_movements_business_date", table_name="cash_movements")
    op.drop_index("ix_cash_movements_party_id", table_name="cash_movements")
    op.drop_index("ix_cash_movements_cash_account_id", table_name="cash_movements")
    op.drop_table("cash_movements")

    op.drop_index("ix_cash_accounts_is_active", table_name="cash_accounts")
    op.drop_table("cash_accounts")

    op.drop_index("ix_party_ledger_entries_business_date", table_name="party_ledger_entries")
    op.drop_index("ix_party_ledger_entries_party_id", table_name="party_ledger_entries")
    op.drop_table("party_ledger_entries")

    op.drop_index("ix_party_payments_business_date", table_name="party_payments")
    op.drop_index("ix_party_payments_party_id", table_name="party_payments")
    op.drop_table("party_payments")

    op.drop_index("ix_distribution_issues_business_date", table_name="distribution_issues")
    op.drop_index("ix_distribution_issues_product_id", table_name="distribution_issues")
    op.drop_index("ix_distribution_issues_party_id", table_name="distribution_issues")
    op.drop_table("distribution_issues")

    op.drop_index("ix_party_prices_product_id", table_name="party_prices")
    op.drop_index("ix_party_prices_party_id", table_name="party_prices")
    op.drop_table("party_prices")

    op.drop_index("ix_parties_is_active", table_name="parties")
    op.drop_index("ix_parties_phone", table_name="parties")
    op.drop_index("ix_parties_name", table_name="parties")
    op.drop_index("ix_parties_party_type", table_name="parties")
    op.drop_table("parties")

    op.drop_index("ix_products_is_active", table_name="products")
    op.drop_index("ix_products_is_default", table_name="products")
    op.drop_index("ix_products_code", table_name="products")
    op.drop_table("products")
