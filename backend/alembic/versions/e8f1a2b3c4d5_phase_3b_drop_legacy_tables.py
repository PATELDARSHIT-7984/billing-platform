"""Phase 3B: Retire legacy customer and party tables; complete cutover to unified accounts.

Revision ID: e8f1a2b3c4d5
Revises: d6e83f2a910c
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e8f1a2b3c4d5'
down_revision = 'd6e83f2a910c'
branch_labels = None
depends_on = None

DOCUMENTS = ('bill', 'sales_returns', 'purchases', 'purchase_returns')
HEADERS = (*DOCUMENTS, 'quotations', 'rojmel')


def upgrade():
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())

    # Pre-flight check: ensure no active transaction rows have missing account ledger references
    if 'bill' in tables:
        unmapped_bills = connection.execute(sa.text(
            "SELECT count(*) FROM bill WHERE account_ledger_id IS NULL AND customer_id IS NOT NULL"
        )).scalar_one()
        if unmapped_bills > 0:
            raise RuntimeError(f"Phase 3B aborted: {unmapped_bills} bill rows lack account_ledger_id")

    if 'purchases' in tables:
        unmapped_purchases = connection.execute(sa.text(
            "SELECT count(*) FROM purchases WHERE account_ledger_id IS NULL AND party_id IS NOT NULL"
        )).scalar_one()
        if unmapped_purchases > 0:
            raise RuntimeError(f"Phase 3B aborted: {unmapped_purchases} purchase rows lack account_ledger_id")

    # Drop legacy foreign key constraints if present
    is_postgres = connection.dialect.name == "postgresql"

    # Drop legacy tables in dependency order
    if 'legacy_account_map' in tables:
        op.drop_table('legacy_account_map')

    if 'account_gstin_registry' in tables:
        op.drop_table('account_gstin_registry')

    # Drop legacy entities
    if 'customers' in tables:
        op.drop_table('customers')

    if 'parties' in tables:
        op.drop_table('parties')


def downgrade():
    # Re-create legacy customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_code', sa.String(30), unique=True, nullable=False),
        sa.Column('customer_name', sa.String(100), nullable=False),
        sa.Column('mobile', sa.String(15), nullable=False),
        sa.Column('email', sa.String(100), nullable=True),
        sa.Column('address', sa.String(255), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('state', sa.String(100), nullable=False),
        sa.Column('pincode', sa.String(10), nullable=True),
        sa.Column('gstin', sa.String(15), unique=True, nullable=True),
        sa.Column('pan_card', sa.String(10), nullable=True),
        sa.Column('state_code', sa.String(10), nullable=True),
        sa.Column('opening_balance', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('balance_type', sa.String(10), nullable=False, server_default='Credit'),
        sa.Column('current_balance', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('current_balance_type', sa.String(10), nullable=False, server_default='Credit'),
        sa.Column('remarks', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Re-create legacy parties table
    op.create_table(
        'parties',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('party_code', sa.String(30), unique=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('party_type', sa.String(20), nullable=False),
        sa.Column('country_code', sa.String(5), nullable=True),
        sa.Column('mobile', sa.String(15), nullable=True),
        sa.Column('address', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('gstin', sa.String(15), nullable=True),
        sa.Column('pan_card', sa.String(10), nullable=True),
        sa.Column('opening_balance', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('balance_type', sa.String(10), nullable=False, server_default='Credit'),
        sa.Column('opening_remark', sa.String(500), nullable=True),
        sa.Column('current_balance', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('current_balance_type', sa.String(10), nullable=False, server_default='Credit'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Re-create account_gstin_registry
    op.create_table(
        'account_gstin_registry',
        sa.Column('account_source', sa.String(30), primary_key=True),
        sa.Column('account_id', sa.Integer(), primary_key=True),
        sa.Column('normalized_gstin', sa.String(15), nullable=False),
        sa.UniqueConstraint('normalized_gstin', name='uq_account_gstin'),
    )

    # Re-create legacy_account_map
    op.create_table(
        'legacy_account_map',
        sa.Column('legacy_source', sa.String(20), primary_key=True),
        sa.Column('legacy_id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('account_role', sa.String(20), nullable=False),
        sa.Column('account_ledger_id', sa.Integer(), nullable=False),
        sa.Column('legacy_code', sa.String(50), nullable=False),
        sa.Column('migration_revision', sa.String(50), nullable=False),
        sa.Column('source_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['account_ledger_id'], ['account_ledgers.id'], ondelete='RESTRICT'),
    )

