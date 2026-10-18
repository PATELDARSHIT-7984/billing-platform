"""Add empty Account identity, roles and separate ledgers.

Revision ID: f2b61d9a430c
Revises: e9a41c8d720b
"""
from alembic import op
import sqlalchemy as sa

revision = "f2b61d9a430c"
down_revision = "e9a41c8d720b"
branch_labels = None
depends_on = None

# Frozen migration snapshot of the shared tax patterns and canonical role values.
# Do not import evolving application validators into a historical migration.
GSTIN_PATTERN = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]"
PAN_PATTERN = r"[A-Z]{5}[0-9]{4}[A-Z]"
ROLES = ("CUSTOMER", "SUPPLIER", "PURCHASE_VENDOR")


def upgrade():
    op.create_table("accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_code", sa.String(30), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(10)),
        sa.Column("mobile", sa.String(20)),
        sa.Column("email", sa.String(320)),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String()),
        sa.Column("state", sa.String()),
        sa.Column("pincode", sa.String(20)),
        sa.Column("state_code", sa.String(2)),
        sa.Column("gstin", sa.String()),
        sa.Column("pan_card", sa.String()),
        sa.Column("remarks", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_code", name="uq_accounts_code"),
        sa.UniqueConstraint("gstin", name="uq_accounts_gstin"),
        sa.CheckConstraint("length(trim(account_code)) > 0", name="ck_accounts_code"),
        sa.CheckConstraint("length(trim(account_name)) > 0", name="ck_accounts_name"),
        sa.CheckConstraint(f"gstin IS NULL OR gstin ~ '^{GSTIN_PATTERN}$'", name="ck_accounts_gstin"),
        sa.CheckConstraint(f"pan_card IS NULL OR pan_card ~ '^{PAN_PATTERN}$'", name="ck_accounts_pan"),
        sa.CheckConstraint("gstin IS NULL OR (pan_card IS NOT NULL AND pan_card = substr(gstin, 3, 10))",
                           name="ck_accounts_gstin_pan"))
    op.create_table("account_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.Enum(*ROLES, native_enum=False, create_constraint=True,
                                  name="ck_account_roles_role", length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "role", name="uq_account_roles_account_role"))
    op.create_index("ix_account_roles_role_account", "account_roles", ["role", "account_id"])
    op.create_table("account_ledgers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Enum(*ROLES, native_enum=False, create_constraint=True,
                                  name="ck_account_ledgers_role", length=20), nullable=False),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("balance_type", sa.String(10)),
        sa.Column("current_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("current_balance_type", sa.String(10)),
        sa.Column("opening_remark", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "role", name="uq_account_ledgers_account_role"),
        sa.ForeignKeyConstraint(["account_id", "role"], ["account_roles.account_id", "account_roles.role"],
                                name="fk_account_ledger_role", ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.CheckConstraint("opening_balance >= 0 AND opening_balance < 10000000000000000",
                           name="ck_account_ledgers_opening_amount"),
        sa.CheckConstraint("current_balance >= 0 AND current_balance < 10000000000000000",
                           name="ck_account_ledgers_current_amount"),
        sa.CheckConstraint("(opening_balance = 0 AND balance_type IS NULL) OR "
                           "(opening_balance > 0 AND balance_type IS NOT NULL AND balance_type IN ('Debit','Credit'))",
                           name="ck_account_ledgers_opening_direction"),
        sa.CheckConstraint("(current_balance = 0 AND current_balance_type IS NULL) OR "
                           "(current_balance > 0 AND current_balance_type IS NOT NULL AND current_balance_type IN ('Debit','Credit'))",
                           name="ck_account_ledgers_current_direction"))


def downgrade():
    op.drop_table("account_ledgers")
    op.drop_index("ix_account_roles_role_account", table_name="account_roles")
    op.drop_table("account_roles")
    op.drop_table("accounts")
