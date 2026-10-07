"""Customer opening balances, without transaction posting.

Revision ID: b8f2d9a73106
Revises: 7414692a3849
"""
from alembic import op
import sqlalchemy as sa

revision = "b8f2d9a73106"
down_revision = "7414692a3849"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customers", sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("customers", sa.Column("current_balance", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("customers", sa.Column("balance_type", sa.String(10), nullable=False, server_default="Credit"))
    op.add_column("customers", sa.Column("current_balance_type", sa.String(10), nullable=False, server_default="Credit"))


def downgrade():
    op.drop_column("customers", "current_balance_type")
    op.drop_column("customers", "balance_type")
    op.drop_column("customers", "current_balance")
    op.drop_column("customers", "opening_balance")
