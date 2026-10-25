"""Customer Rojmel reference and opening-era transaction cutover.

Revision ID: c4a9e7120d35
Revises: b8f2d9a73106
"""
from alembic import op
import sqlalchemy as sa

revision = "c4a9e7120d35"
down_revision = "b8f2d9a73106"
branch_labels = None
depends_on = None


def _adjust_existing_effects(sign):
    # Use booked totals, never recompute prices/GST. Include inactive accounts,
    # but only active documents. Rojmel customer references are NULL at upgrade.
    op.execute(sa.text(f"""
        WITH effects AS (
            SELECT customer_id, -CAST(grand_total AS NUMERIC(18,2)) AS amount
            FROM bill WHERE is_active = true
            UNION ALL
            SELECT customer_id, CAST(grand_total AS NUMERIC(18,2)) AS amount
            FROM sales_returns WHERE is_active = true
            UNION ALL
            SELECT customer_id, CASE WHEN transaction_type = 'CR_PAY' THEN net_amount
                                    WHEN transaction_type = 'DR_PAY' THEN -net_amount ELSE 0 END
            FROM rojmel WHERE customer_id IS NOT NULL
        ), totals AS (
            SELECT customer_id, SUM(amount) AS amount FROM effects GROUP BY customer_id
        ), adjusted AS (
            SELECT c.id, (CASE WHEN c.current_balance_type = 'Debit' THEN -c.current_balance
                              ELSE c.current_balance END) + ({sign}) * t.amount AS amount
            FROM customers c JOIN totals t ON t.customer_id = c.id
        )
        UPDATE customers SET current_balance = ABS(adjusted.amount),
            current_balance_type = CASE WHEN adjusted.amount < 0 THEN 'Debit' ELSE 'Credit' END
        FROM adjusted WHERE customers.id = adjusted.id
    """))


def upgrade():
    op.add_column('rojmel', sa.Column('customer_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_rojmel_customer_id', 'rojmel', 'customers', ['customer_id'], ['id'])
    op.create_check_constraint('ck_rojmel_one_account', 'rojmel', 'party_id IS NULL OR customer_id IS NULL')
    _adjust_existing_effects(1)


def downgrade():
    # Removing the FK after receipts exist would silently orphan their financial
    # meaning. Require explicit reconciliation instead of destroying that link.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM rojmel WHERE customer_id IS NOT NULL) THEN
            RAISE EXCEPTION 'Cannot downgrade while Customer-linked Rojmel entries exist';
        END IF;
    END $$;""")
    _adjust_existing_effects(-1)
    op.drop_constraint('ck_rojmel_one_account', 'rojmel', type_='check')
    op.drop_constraint('fk_rojmel_customer_id', 'rojmel', type_='foreignkey')
    op.drop_column('rojmel', 'customer_id')
