"""Add igst column to item_master table

Revision ID: f3a1b2c4d5e6
Revises: d6e83f2a910c
Create Date: 2026-10-25 21:57:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a1b2c4d5e6'
down_revision = 'd6e83f2a910c'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [c['name'] for c in inspector.get_columns('item_master')]
    if 'igst' not in columns:
        op.add_column(
            'item_master',
            sa.Column('igst', sa.Float(), nullable=False, server_default='0.0')
        )


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [c['name'] for c in inspector.get_columns('item_master')]
    if 'igst' in columns:
        op.drop_column('item_master', 'igst')

