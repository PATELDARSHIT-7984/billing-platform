"""Create account_code_seq sequence and add customer_name to quotations

Revision ID: g4a1b2c4d5e7
Revises: f3a1b2c4d5e6
Create Date: 2026-10-27 11:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g4a1b2c4d5e7'
down_revision = 'f3a1b2c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [c['name'] for c in inspector.get_columns('quotations')]
    if 'customer_name' not in columns:
        op.add_column('quotations', sa.Column('customer_name', sa.String(length=255), nullable=True))
    if connection.dialect.name == "postgresql":
        op.alter_column('quotations', 'customer_id', nullable=True)
        op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS account_code_seq START WITH 100 INCREMENT BY 1;"))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [c['name'] for c in inspector.get_columns('quotations')]
    if 'customer_name' in columns:
        op.drop_column('quotations', 'customer_name')
    if connection.dialect.name == "postgresql":
        op.execute(sa.text("DROP SEQUENCE IF EXISTS account_code_seq;"))
