"""Phase 3A: additive, reference-only transaction Account backfill.

Revision ID: d6e83f2a910c
Revises: a7c92e1b640d
"""
from alembic import op
import sqlalchemy as sa

revision = 'd6e83f2a910c'
down_revision = 'a7c92e1b640d'
branch_labels = None
depends_on = None

# Frozen migration definitions; never import runtime models or posting services.
DOCUMENTS = {
    'bill': ('customer', 'customer_id', ('CUSTOMER',)),
    'sales_returns': ('customer', 'customer_id', ('CUSTOMER',)),
    'purchases': ('party', 'party_id', ('SUPPLIER', 'PURCHASE_VENDOR')),
    'purchase_returns': ('party', 'party_id', ('SUPPLIER', 'PURCHASE_VENDOR')),
}
FINANCIAL = {**DOCUMENTS, 'rojmel': (None, None, ('CUSTOMER', 'SUPPLIER', 'PURCHASE_VENDOR'))}
HEADERS = (*DOCUMENTS, 'quotations', 'rojmel')
PRESERVED = ('customers', 'parties', 'accounts', 'account_roles', 'account_ledgers',
             'legacy_account_map', 'item_master', 'bill_item', 'sales_return_items',
             'purchase_items', 'purchase_return_items', 'quotation_items')


def _reject(connection, query, reason):
    if connection.execute(sa.text('SELECT EXISTS (' + query + ')')).scalar_one():
        raise RuntimeError('Phase 3A aborted: ' + reason)


def _preflight(connection):
    # Validate map targets and sources even if historical rows are inactive.
    _reject(connection, """
        SELECT 1 FROM legacy_account_map m
        LEFT JOIN accounts a ON a.id=m.account_id
        LEFT JOIN account_roles r ON r.account_id=m.account_id AND r.role=m.account_role
        LEFT JOIN account_ledgers l ON l.id=m.account_ledger_id
        LEFT JOIN customers c ON m.legacy_source='customer' AND c.id=m.legacy_id
        LEFT JOIN parties p ON m.legacy_source='party' AND p.id=m.legacy_id
        WHERE a.id IS NULL OR r.id IS NULL OR l.id IS NULL
           OR l.account_id IS DISTINCT FROM m.account_id OR l.role IS DISTINCT FROM m.account_role
           OR m.legacy_source IS NULL OR m.legacy_source NOT IN ('customer','party')
           OR m.migration_revision IS DISTINCT FROM 'a7c92e1b640d'
           OR m.legacy_code IS NULL OR trim(m.legacy_code)=''
           OR jsonb_typeof(m.source_snapshot) IS DISTINCT FROM 'object'
           OR (m.legacy_source='customer' AND (c.id IS NULL OR m.account_role IS DISTINCT FROM 'CUSTOMER'))
           OR (m.legacy_source='party' AND (p.id IS NULL OR
               m.account_role IS DISTINCT FROM CASE p.party_type
                   WHEN 'Supplier' THEN 'SUPPLIER' WHEN 'PURCHASE_VENDOR' THEN 'PURCHASE_VENDOR' END))
        """, 'malformed mapping, missing target/source, or unsupported source/role classification')
    for columns in ('legacy_source,legacy_id', 'account_id', 'account_ledger_id'):
        _reject(connection, f'SELECT 1 FROM legacy_account_map GROUP BY {columns} HAVING count(*)>1',
                'duplicate mapping or unapproved identity merge')
    _reject(connection, 'SELECT 1 FROM rojmel WHERE customer_id IS NOT NULL AND party_id IS NOT NULL',
            'Rojmel has both Customer and Party references')
    for table, source, column in [*( (t, s, c) for t, (s, c, _) in DOCUMENTS.items()),
                                  ('quotations', 'customer', 'customer_id'),
                                  ('rojmel', 'customer', 'customer_id'), ('rojmel', 'party', 'party_id')]:
        nullable = f'd.{column} IS NOT NULL AND ' if table == 'rojmel' else ''
        _reject(connection, f"SELECT 1 FROM {table} d LEFT JOIN legacy_account_map m "
                f"ON m.legacy_source='{source}' AND m.legacy_id=d.{column} "
                f"WHERE {nullable}m.account_ledger_id IS NULL", f'{table}: missing deterministic {source} mapping')
    for returns, parent, reference, number, source, identity in (
        ('sales_returns', 'bill', 'original_invoice_no', 'invoice_no', 'customer', 'customer_id'),
        ('purchase_returns', 'purchases', 'original_bill_no', 'bill_no', 'party', 'party_id'),
    ):
        # Optional string linkage stays unchanged. Missing historical parents do not
        # invent a link; when a parent exists it must be unambiguous and agree.
        parent_number = f'upper(trim(p.{number}))' if parent == 'bill' else f'upper(p.{number})'
        join = f"{parent_number}=upper(trim(d.{reference}))"
        _reject(connection, f"SELECT 1 FROM {returns} d JOIN {parent} p ON {join} "
                f"WHERE nullif(trim(d.{reference}),'') IS NOT NULL GROUP BY d.id HAVING count(*)>1",
                f'{returns}: ambiguous linked original')
        _reject(connection, f"SELECT 1 FROM {returns} d JOIN {parent} p ON {join} "
                f"JOIN legacy_account_map rm ON rm.legacy_source='{source}' AND rm.legacy_id=d.{identity} "
                f"JOIN legacy_account_map pm ON pm.legacy_source='{source}' AND pm.legacy_id=p.{identity} "
                f"WHERE nullif(trim(d.{reference}),'') IS NOT NULL "
                'AND rm.account_ledger_id IS DISTINCT FROM pm.account_ledger_id',
                f'{returns}: linked original ledger differs')


def _backfill(connection, verify=False):
    for table, source, column in [*((t, s, c) for t, (s, c, _) in DOCUMENTS.items()),
                                  ('quotations', 'customer', 'customer_id'),
                                  ('rojmel', 'customer', 'customer_id'), ('rojmel', 'party', 'party_id')]:
        fields = ('account_id',) if table == 'quotations' else ('account_ledger_id', 'account_role')
        join = f"m.legacy_source='{source}' AND m.legacy_id=d.{column}"
        if verify:
            mismatch = ' OR '.join(f'd.{field} IS DISTINCT FROM m.{field}' for field in fields)
            _reject(connection, f'SELECT 1 FROM {table} d JOIN legacy_account_map m ON {join} '
                    f'WHERE {mismatch}', f'{table}: reference reconciliation failed')
        else:
            assignments = ', '.join(f'{field}=m.{field}' for field in fields)
            connection.execute(sa.text(f'UPDATE {table} d SET {assignments} FROM legacy_account_map m WHERE {join}'))
    if verify:
        _reject(connection, 'SELECT 1 FROM rojmel WHERE customer_id IS NULL AND party_id IS NULL '
                'AND (account_ledger_id IS NOT NULL OR account_role IS NOT NULL)',
                'identity-less Rojmel acquired a reference')


def upgrade():
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    if 'legacy_account_map' not in tables:
        raise RuntimeError('Phase 3A aborted: missing legacy_account_map')
    # Alphabetical table order; acquire strongest required locks up front, avoiding
    # later lock promotion. DDL tables require ACCESS EXCLUSIVE; other protected
    # tables allow SELECT while rejecting writes. Deployment must quiesce writers.
    for table in sorted((*HEADERS, *PRESERVED)):
        mode = 'ACCESS EXCLUSIVE' if table in (*HEADERS, 'account_ledgers') else 'SHARE'
        connection.execute(sa.text(f'LOCK TABLE {table} IN {mode} MODE'))
    for table in HEADERS:
        columns = {c['name'] for c in sa.inspect(connection).get_columns(table)}
        if columns & {'account_id', 'account_ledger_id', 'account_role'}:
            raise RuntimeError(f'Phase 3A aborted: unexpected pre-existing new reference columns on {table}; review conflicts')
    _preflight(connection)
    # Server-side exact snapshots: no Python transaction materialization, no
    # aggregate balance parity requirement, no digest collision assumptions.
    for table in (*HEADERS, *PRESERVED):
        connection.execute(sa.text(f'CREATE TEMP TABLE p3a_before_{table} ON COMMIT DROP AS '
                                   f'SELECT to_jsonb(t) AS row_value FROM {table} t'))
    op.create_unique_constraint('uq_account_ledgers_id_role', 'account_ledgers', ['id', 'role'])
    for table, (_, _, roles) in FINANCIAL.items():
        op.add_column(table, sa.Column('account_ledger_id', sa.Integer(), nullable=True))
        op.add_column(table, sa.Column('account_role', sa.String(20), nullable=True))
        op.create_foreign_key(f'fk_{table}_account_ledger_role', table, 'account_ledgers',
                              ['account_ledger_id', 'account_role'], ['id', 'role'],
                              match='FULL', ondelete='RESTRICT', onupdate='RESTRICT')
        op.create_check_constraint(f'ck_{table}_account_role', table,
                                   'account_role IS NULL OR account_role IN (' + ','.join(repr(r) for r in roles) + ')')
        # Same explicit pair check in ORM metadata keeps SQLite fixtures honest;
        # PostgreSQL additionally enforces the required MATCH FULL composite FK.
        op.create_check_constraint(f'ck_{table}_account_reference_pair', table,
                                   '(account_ledger_id IS NULL) = (account_role IS NULL)')
        op.create_index(f'ix_{table}_account_ledger_id', table, ['account_ledger_id'])
    op.create_check_constraint('ck_rojmel_account_context', 'rojmel',
        "account_ledger_id IS NULL OR "
        "(customer_id IS NOT NULL AND party_id IS NULL AND account_role = 'CUSTOMER') OR "
        "(party_id IS NOT NULL AND customer_id IS NULL AND account_role IN ('SUPPLIER','PURCHASE_VENDOR'))")
    op.add_column('quotations', sa.Column('account_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_quotations_account_id', 'quotations', 'accounts', ['account_id'], ['id'],
                          ondelete='RESTRICT', onupdate='RESTRICT')
    op.create_index('ix_quotations_account_id', 'quotations', ['account_id'])
    _backfill(connection)
    _backfill(connection, verify=True)
    for table in (*HEADERS, *PRESERVED):
        projection = 'to_jsonb(t)'
        if table in FINANCIAL:
            projection += " - 'account_ledger_id' - 'account_role'"
        elif table == 'quotations':
            projection += " - 'account_id'"
        before = f'SELECT row_value FROM p3a_before_{table}'
        after = f'SELECT {projection} FROM {table} t'
        _reject(connection, f'({before} EXCEPT ALL {after}) UNION ALL ({after} EXCEPT ALL {before})',
                f'{table}: protected contents changed')


def downgrade():
    # Supported only before runtime financial cutover; never reverse financial data.
    for table in sorted((*HEADERS, 'account_ledgers')):
        op.get_bind().execute(sa.text(f'LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE'))
    op.drop_constraint('fk_quotations_account_id', 'quotations', type_='foreignkey')
    op.drop_index('ix_quotations_account_id', table_name='quotations')
    op.drop_column('quotations', 'account_id')
    op.drop_constraint('ck_rojmel_account_context', 'rojmel', type_='check')
    for table in FINANCIAL:
        op.drop_constraint(f'fk_{table}_account_ledger_role', table, type_='foreignkey')
        op.drop_constraint(f'ck_{table}_account_role', table, type_='check')
        op.drop_constraint(f'ck_{table}_account_reference_pair', table, type_='check')
        op.drop_index(f'ix_{table}_account_ledger_id', table_name=table)
        op.drop_column(table, 'account_role')
        op.drop_column(table, 'account_ledger_id')
    op.drop_constraint('uq_account_ledgers_id_role', 'account_ledgers', type_='unique')
