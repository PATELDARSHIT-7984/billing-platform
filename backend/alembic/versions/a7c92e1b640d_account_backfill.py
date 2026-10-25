"""Approved Phase 2B Account backfill; no transaction cutover.

Revision ID: a7c92e1b640d
Revises: f2b61d9a430c
"""
import hashlib
import json
from pathlib import Path
from decimal import Decimal
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'a7c92e1b640d'
down_revision = 'f2b61d9a430c'
branch_labels = None
depends_on = None

# Frozen historical mapping; intentionally independent of mutable runtime helpers.
STATES = {'01': 'Jammu and Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab', '04': 'Chandigarh', '05': 'Uttarakhand', '06': 'Haryana', '07': 'Delhi', '08': 'Rajasthan', '09': 'Uttar Pradesh', '10': 'Bihar', '11': 'Sikkim', '12': 'Arunachal Pradesh', '13': 'Nagaland', '14': 'Manipur', '15': 'Mizoram', '16': 'Tripura', '17': 'Meghalaya', '18': 'Assam', '19': 'West Bengal', '20': 'Jharkhand', '21': 'Odisha', '22': 'Chhattisgarh', '23': 'Madhya Pradesh', '24': 'Gujarat', '25': 'Daman and Diu', '26': 'Dadra and Nagar Haveli and Daman and Diu', '27': 'Maharashtra', '28': 'Andhra Pradesh (Old)', '29': 'Karnataka', '30': 'Goa', '31': 'Lakshadweep', '32': 'Kerala', '33': 'Tamil Nadu', '34': 'Puducherry', '35': 'Andaman and Nicobar Islands', '36': 'Telangana', '37': 'Andhra Pradesh', '38': 'Ladakh', '97': 'Other Territory'}
BASELINE = Path(__file__).resolve().parents[1] / 'data' / 'phase_2b_approved.json'
BASELINE_SHA256 = 'c67cdf4128e30c15ccb01677766711e00a48d2918876c0cebad91d2d7cf30026'
TRANSACTIONS = ('bill', 'sales_returns', 'purchases', 'purchase_returns', 'quotations', 'rojmel')
DOCUMENT_LINES = ('bill_item', 'sales_return_items', 'purchase_items', 'purchase_return_items', 'quotation_items')
TARGETS = ('accounts', 'account_roles', 'account_ledgers')


def _baseline():
    try:
        content = BASELINE.read_bytes()
    except OSError as error:
        raise RuntimeError('Phase 2B approved baseline file is missing or unreadable.') from error
    if hashlib.sha256(content).hexdigest() != BASELINE_SHA256:
        raise RuntimeError('Phase 2B approved baseline integrity check failed (SHA-256 mismatch).')
    return json.loads(content)


def _rows(connection, table):
    return [dict(row) for row in connection.execute(sa.text(f'SELECT * FROM {table} ORDER BY id')).mappings()]


def _business(row):
    return json.loads(json.dumps({k: v for k, v in row.items() if k not in ('created_at', 'updated_at')}, default=str))


def _references(connection):
    return {key: {str(i): n for i, n in connection.execute(sa.text(
        f"SELECT {key.split('.')[1]},count(*) FROM {key.split('.')[0]} GROUP BY {key.split('.')[1]}"))}
        for key in _baseline()['references']}


def _transaction_snapshot(connection):
    return {table: connection.execute(sa.text(
        f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text')).scalars().all()
        for table in (*TRANSACTIONS, *DOCUMENT_LINES)}


def _fingerprint(connection, table, identity):
    return connection.execute(sa.text(f'SELECT md5(row_to_json(t)::text) FROM {table} t WHERE id=:id'),
                              {'id': identity}).scalar_one()


def _preflight(connection):
    expected = _baseline()
    rows = {source: _rows(connection, table) for source, table in [('customer', 'customers'), ('party', 'parties')]}
    for table in TARGETS:
        if connection.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one():
            raise RuntimeError('Phase 2B requires empty target Account tables.')
    if not rows['customer'] and not rows['party']:
        # Approved fresh-bootstrap exception: never accept a partially populated DB.
        if any(connection.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one()
               for table in (*TRANSACTIONS, *DOCUMENT_LINES)):
            raise RuntimeError('Empty identity bootstrap requires empty transaction tables.')
        return rows
    for source in ('customer', 'party'):
        originals = expected[source]
        if [r['id'] for r in rows[source]] != [r['id'] for r in originals]:
            raise RuntimeError(f'Phase 2B source identity set drift: {source}')
        for actual, original in zip(rows[source], originals):
            approved = dict(original)
            if _business(actual) != approved:
                fields = [key for key in approved if _business(actual).get(key) != approved[key]]
                raise RuntimeError(f'Phase 2B material drift: {source}:{original["id"]}, fields={fields}')
    if _references(connection) != expected['references']:
        raise RuntimeError('Phase 2B transaction reference baseline differs.')
    codes = [r.get('customer_code', r.get('party_code')) for group in rows.values() for r in group]
    if len(codes) != len(set(codes)) or any(not code or not code.strip() for code in codes):
        raise RuntimeError('Phase 2B duplicate or missing legacy code.')
    return rows


def _target(source, original):
    row = dict(original)
    gstin = row['gstin']
    code = gstin[:2] if gstin else None
    if not gstin and row.get('state'):
        code = next((k for k, v in STATES.items() if v.casefold() == row['state'].strip().casefold()), None)
        if code is None:
            raise RuntimeError(f'Unrecognized legacy state: {source}:{row["id"]}')
    if code is not None and code not in STATES:
        raise RuntimeError(f'Unrecognized GST state code: {source}:{row["id"]}')
    pan = row['pan_card']
    if gstin:
        derived = gstin[2:12]  # Frozen historical derivation, not a runtime helper import.
        if pan and pan != derived:
            raise RuntimeError('Unapproved legacy PAN mismatch.')
        pan = derived
    account = {key: row.get(key) for key in ('country_code', 'mobile', 'email', 'address', 'city', 'pincode', 'remarks')}
    account.update(account_code=row.get('customer_code', row.get('party_code')),
                   account_name=row.get('customer_name', row.get('name')), gstin=gstin, pan_card=pan,
                   state_code=code, state=STATES.get(code), is_active=row['is_active'],
                   gstin_pending=False)
    role = 'CUSTOMER' if source == 'customer' else {'Supplier': 'SUPPLIER', 'PURCHASE_VENDOR': 'PURCHASE_VENDOR'}[row['party_type']]
    ledger = {'role': role, 'opening_remark': row.get('opening_remark')}
    for field, direction in [('opening_balance', 'balance_type'), ('current_balance', 'current_balance_type')]:
        amount = Decimal(str(row[field]))
        if not amount.is_finite() or amount < 0 or amount >= Decimal('10000000000000000') or amount != amount.quantize(Decimal('.01')):
            raise RuntimeError(f'Invalid legacy balance: {source}:{row["id"]}:{field}')
        if amount and row[direction] not in ('Debit', 'Credit'):
            raise RuntimeError('Invalid legacy balance direction.')
        ledger[field], ledger[direction] = amount, row[direction] if amount else None
    return account, role, ledger


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text('LOCK TABLE customers, parties, accounts, account_roles, account_ledgers, '
                               + ', '.join((*TRANSACTIONS, *DOCUMENT_LINES)) + ' IN SHARE ROW EXCLUSIVE MODE'))
    rows = _preflight(connection)
    transactions = _transaction_snapshot(connection)
    op.add_column('accounts', sa.Column('gstin_pending', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_check_constraint('ck_accounts_gstin_pending', 'accounts', 'gstin IS NULL OR NOT gstin_pending')
    op.create_check_constraint('ck_accounts_gstin_state', 'accounts',
                              'gstin IS NULL OR (state_code IS NOT NULL AND substr(gstin,1,2)=state_code)')
    op.create_check_constraint('ck_accounts_state_code', 'accounts',
                              'state_code IS NULL OR state_code IN (' + ','.join(repr(code) for code in STATES) + ')')
    op.create_unique_constraint('uq_account_ledgers_identity', 'account_ledgers', ['id', 'account_id', 'role'])
    op.create_table('legacy_account_map',
        sa.Column('legacy_source', sa.String(20), primary_key=True),
        sa.Column('legacy_id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('account_role', sa.String(20), nullable=False),
        sa.Column('account_ledger_id', sa.Integer(), nullable=False),
        sa.Column('legacy_code', sa.String(30), nullable=False),
        sa.Column('migration_revision', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('source_snapshot', JSONB(), nullable=False),
        sa.CheckConstraint("legacy_source IN ('customer','party')", name='ck_legacy_account_source'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='RESTRICT'),
        sa.ForeignKeyConstraint(['account_id', 'account_role'], ['account_roles.account_id', 'account_roles.role'],
                                name='fk_legacy_map_role', ondelete='RESTRICT', onupdate='RESTRICT'),
        sa.ForeignKeyConstraint(['account_ledger_id', 'account_id', 'account_role'],
                                ['account_ledgers.id', 'account_ledgers.account_id', 'account_ledgers.role'],
                                name='fk_legacy_map_ledger', ondelete='RESTRICT', onupdate='RESTRICT'))
    # Reflection uses the actual schema, never application ORM classes.
    metadata = sa.MetaData()
    tables = {name: sa.Table(name, metadata, autoload_with=connection)
              for name in (*TARGETS, 'legacy_account_map')}
    expected = _baseline()
    for source in ('customer', 'party'):
        for row, original in zip(rows[source], expected[source]):
            account, role, ledger = _target(source, row)
            aid = connection.execute(tables['accounts'].insert().values(**account).returning(tables['accounts'].c.id)).scalar_one()
            rid = connection.execute(tables['account_roles'].insert().values(account_id=aid, role=role,
                is_active=row['is_active']).returning(tables['account_roles'].c.id)).scalar_one()
            lid = connection.execute(tables['account_ledgers'].insert().values(account_id=aid, **ledger)
                .returning(tables['account_ledgers'].c.id)).scalar_one()
            snapshot = dict(original=original, at_backfill=_business(row),
                target_fingerprints={name: dict(id=identity, digest=_fingerprint(connection, name, identity))
                                     for name, identity in zip(TARGETS, (aid, rid, lid))})
            connection.execute(tables['legacy_account_map'].insert().values(legacy_source=source, legacy_id=row['id'],
                account_id=aid, account_role=role, account_ledger_id=lid, legacy_code=account['account_code'],
                migration_revision=revision, source_snapshot=snapshot))
            saved = connection.execute(tables['account_ledgers'].select().where(tables['account_ledgers'].c.id == lid)).mappings().one()
            if any(saved[key] != value for key, value in ledger.items()):
                raise RuntimeError(f'Ledger reconciliation failed: {source}:{row["id"]}')
            saved_account = connection.execute(tables['accounts'].select().where(tables['accounts'].c.id == aid)).mappings().one()
            saved_role = connection.execute(tables['account_roles'].select().where(tables['account_roles'].c.id == rid)).mappings().one()
            if any(saved_account[key] != value for key, value in account.items()) or saved_role['is_active'] != row['is_active']:
                raise RuntimeError(f'Identity/activity reconciliation failed: {source}:{row["id"]}')
    for table in (*TARGETS, 'legacy_account_map'):
        if connection.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() != sum(map(len, rows.values())):
            raise RuntimeError('Phase 2B target count reconciliation failed.')
    if _transaction_snapshot(connection) != transactions or (any(rows.values()) and _references(connection) != expected['references']):
        raise RuntimeError('Transactions changed during Account backfill.')
    for source, table in [('customer', 'customers'), ('party', 'parties')]:
        if _rows(connection, table) != rows[source]:
            raise RuntimeError('Legacy source changed during Account backfill.')


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text('LOCK TABLE legacy_account_map, accounts, account_roles, account_ledgers IN SHARE ROW EXCLUSIVE MODE'))
    mappings = connection.execute(sa.text('SELECT * FROM legacy_account_map')).mappings().all()
    for table in TARGETS:
        if connection.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() != len(mappings):
            raise RuntimeError('Downgrade refused: target Accounts changed after backfill.')
    for row in mappings:
        if row['migration_revision'] != revision:
            raise RuntimeError('Downgrade refused: unexpected mapping provenance.')
        for table, saved in row['source_snapshot']['target_fingerprints'].items():
            if _fingerprint(connection, table, saved['id']) != saved['digest']:
                raise RuntimeError('Downgrade refused: target identity or ledger changed after backfill.')
    # No public Account writes are supported. Refuse changed data rather than erase it.
    op.drop_table('legacy_account_map')
    for table in reversed(TARGETS):
        connection.execute(sa.text(f'DELETE FROM {table}'))
    op.drop_constraint('uq_account_ledgers_identity', 'account_ledgers', type_='unique')
    for name in ('ck_accounts_gstin_pending', 'ck_accounts_gstin_state', 'ck_accounts_state_code'):
        op.drop_constraint(name, 'accounts', type_='check')
    op.drop_column('accounts', 'gstin_pending')
