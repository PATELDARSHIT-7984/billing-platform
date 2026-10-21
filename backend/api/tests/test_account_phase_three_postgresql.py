"""Phase 3A reference-only migration rehearsals on disposable PostgreSQL."""
from datetime import date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.tests.test_gstin_postgresql import postgres_database
from api.tests.test_account_phase_two_postgresql import seed

PRE = 'a7c92e1b640d'
HEAD = 'd6e83f2a910c'
HEADERS = ('bill', 'sales_returns', 'purchases', 'purchase_returns', 'quotations', 'rojmel')
PROTECTED = ('customers', 'parties', 'accounts', 'account_roles', 'account_ledgers', 'legacy_account_map',
             'item_master', 'bill_item', 'sales_return_items', 'purchase_items', 'purchase_return_items', 'quotation_items')


def document(conn, metadata, table_name, **overrides):
    """Representative stored documents, without invoking financial services."""
    table = metadata.tables[table_name]
    values = dict(overrides)
    for col in table.columns:
        if col.name in values or col.primary_key or col.nullable or col.server_default is not None:
            continue
        if col.foreign_keys:
            remote = next(iter(col.foreign_keys)).column
            existing = conn.execute(sa.select(remote).limit(1)).scalar()
            values[col.name] = existing if existing is not None else document(conn, metadata, remote.table.name)
        elif isinstance(col.type, sa.Enum):
            values[col.name] = col.type.enums[0]
        elif isinstance(col.type, sa.Boolean):
            values[col.name] = True
        elif isinstance(col.type, sa.DateTime):
            values[col.name] = datetime(2026, 10, 21, 10, 30)
        elif isinstance(col.type, sa.Date):
            values[col.name] = date(2026, 10, 21)
        elif isinstance(col.type, (sa.Numeric, sa.Float, sa.Integer)):
            values[col.name] = 1
        else:
            values[col.name] = 'fixture'
    return conn.execute(table.insert().values(**values).returning(*table.primary_key)).scalar_one()


def contents(engine):
    with engine.connect() as conn:
        return {table: conn.execute(sa.text(
            f"SELECT (to_jsonb(t) - 'account_ledger_id' - 'account_role' - 'account_id')::text "
            f"FROM {table} t ORDER BY 1" if table in HEADERS else
            f'SELECT to_jsonb(t)::text FROM {table} t ORDER BY 1')).scalars().all()
            for table in (*HEADERS, *PROTECTED)}


@pytest.fixture
def prepared(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'f2b61d9a430c')
    seed(engine)
    migrate('upgrade', PRE)
    metadata = sa.MetaData()
    metadata.reflect(engine)
    with engine.begin() as conn:
        # More documents than the former live count; all classifications and histories.
        vendor = document(conn, metadata, 'purchases', bill_no='VENDOR', party_id=4, grand_total=125.50)
        sale = conn.execute(sa.text('SELECT bill_id FROM bill')).scalar_one()
        purchase = conn.execute(sa.text("SELECT id FROM purchases WHERE party_id=1")).scalar_one()
        for index in range(40):
            document(conn, metadata, 'bill', invoice_no=f'EXTRA-{index}', customer_id=1,
                     grand_total=100.25, is_active=index % 2 == 0)
        sr = document(conn, metadata, 'sales_returns', return_no='SR-LINK', customer_id=3,
                      original_invoice_no='bill-3-0', grand_total=23.45)
        document(conn, metadata, 'sales_returns', return_no='SR-STANDALONE', customer_id=2)
        pr = document(conn, metadata, 'purchase_returns', return_no='PR-LINK', party_id=1,
                      original_bill_no='purchases-1-0', grand_total=25.25)
        document(conn, metadata, 'purchase_returns', return_no='PR-VENDOR', party_id=4, original_bill_no='VENDOR')
        document(conn, metadata, 'purchase_returns', return_no='PR-STANDALONE', party_id=5)
        quote = document(conn, metadata, 'quotations', quotation_no='QUOTE', customer_id=2)
        item = document(conn, metadata, 'item_master', name='Stock fixture', current_stock=73.25)
        for table, fk, identity in [('bill_item','bill_id',sale), ('purchase_items','purchase_id',purchase),
                                    ('sales_return_items','sales_return_id',sr),
                                    ('purchase_return_items','purchase_return_id',pr),
                                    ('quotation_items','quotation_id',quote)]:
            document(conn, metadata, table, **{fk:identity, 'item_id':item, 'quantity':2.5})
        for index, (customer, party, kind) in enumerate([
            (1,None,'CR_PAY'), (1,None,'DR_PAY'), (None,1,'DR_PAY'), (None,1,'CR_PAY'),
            (None,4,'DR_PAY'), (None,4,'CR_PAY'), (None,1,'CASH_BANK'), (None,4,'JV'),
            (None,None,'CASH_BANK'), (None,None,'DR_PAY'),
        ]):
            document(conn, metadata, 'rojmel', receipt_no=f'R-{index}', customer_id=customer,
                     party_id=party, transaction_type=kind, amount=100, net_amount=118,
                     sgst_percent=9, cgst_percent=9, igst_percent=0)
        conn.execute(sa.text('UPDATE banks SET is_active=true'))
        conn.execute(sa.text('UPDATE doneby SET is_active=true'))
        # Legitimate post-2B balance drift MUST NOT block, repair, or replay history.
        conn.execute(sa.text('UPDATE customers SET current_balance=current_balance+123.45 WHERE id=1'))
        conn.execute(sa.text('UPDATE parties SET current_balance=current_balance+67.89 WHERE id=1'))
    return engine, migrate


def test_full_backfill_preservation_constraints_and_roundtrip(prepared):
    engine, migrate = prepared
    before = contents(engine)
    with engine.connect() as conn:
        old_fks = {t: sa.inspect(conn).get_foreign_keys(t) for t in HEADERS}
    migrate('upgrade', HEAD)
    assert contents(engine) == before
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == HEAD
        for table, source, column in [('bill','customer','customer_id'), ('sales_returns','customer','customer_id'),
                                     ('purchases','party','party_id'), ('purchase_returns','party','party_id'),
                                     ('quotations','customer','customer_id'), ('rojmel','customer','customer_id'),
                                     ('rojmel','party','party_id')]:
            rows = conn.execute(sa.text(f"SELECT d.*, m.account_id AS expected_account, "
                f"m.account_ledger_id AS expected_ledger,m.account_role AS expected_role FROM {table} d "
                f"JOIN legacy_account_map m ON m.legacy_source='{source}' AND m.legacy_id=d.{column}")).mappings().all()
            assert rows
            for row in rows:
                if table == 'quotations':
                    assert row['account_id'] == row['expected_account']
                else:
                    assert (row['account_ledger_id'],row['account_role']) == (row['expected_ledger'],row['expected_role'])
        assert conn.execute(sa.text('SELECT count(*) FROM bill')).scalar_one() == 41
        assert conn.execute(sa.text('SELECT count(*) FROM rojmel WHERE customer_id IS NULL AND party_id IS NULL '
                                    'AND account_ledger_id IS NULL AND account_role IS NULL')).scalar_one() == 2
        assert conn.execute(sa.text('SELECT is_active FROM parties WHERE id=1')).scalar_one() is False
        for table in HEADERS:
            fks = sa.inspect(conn).get_foreign_keys(table)
            assert all(fk in fks for fk in old_fks[table])
            new_fk = next(f for f in fks if f['name'] == (f'fk_{table}_account_ledger_role' if table != 'quotations' else 'fk_quotations_account_id'))
            assert new_fk['options']['ondelete'] == new_fk['options']['onupdate'] == 'RESTRICT'
            if table != 'quotations':
                # SQLAlchemy reflection may omit MATCH, so inspect PostgreSQL directly.
                assert conn.execute(sa.text('SELECT confmatchtype FROM pg_constraint WHERE conname=:name'),
                                    {'name':new_fk['name']}).scalar_one() == 'f'
                assert new_fk['constrained_columns'] == ['account_ledger_id','account_role']
            assert any(i['column_names'] == ['account_id' if table=='quotations' else 'account_ledger_id']
                       for i in sa.inspect(conn).get_indexes(table))
    migrate('downgrade', PRE)
    assert contents(engine) == before
    with engine.connect() as conn:
        assert 'uq_account_ledgers_id_role' not in {u['name'] for u in sa.inspect(conn).get_unique_constraints('account_ledgers')}
    migrate('upgrade', HEAD)
    assert contents(engine) == before


@pytest.mark.parametrize('table', ['bill','sales_returns','purchases','purchase_returns','rojmel'])
def test_direct_db_role_pair_and_reference_guards(prepared, table):
    engine, migrate = prepared
    migrate('upgrade', HEAD)
    with engine.begin() as conn:
        ledger = dict(conn.execute(sa.text('SELECT account_role, min(account_ledger_id) FROM legacy_account_map GROUP BY account_role')).all())
        wrong = 'SUPPLIER' if table in ('bill','sales_returns','rojmel') else 'CUSTOMER'
        where = " WHERE customer_id IS NOT NULL" if table == 'rojmel' else ''
        statements = [
            f"UPDATE {table} SET account_role=NULL{where}",
            f"UPDATE {table} SET account_ledger_id=NULL{where}",
            f"UPDATE {table} SET account_ledger_id=999999{where}",
            f"UPDATE {table} SET account_ledger_id={ledger[wrong]}{where}",
            f"UPDATE {table} SET account_role='{wrong}',account_ledger_id={ledger[wrong]}{where}",
            f"UPDATE {table} SET account_role='INVALID'{where}",
        ]
        for sql in statements:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(sa.text(sql))
        # Legacy writers may still omit BOTH columns.
        conn.execute(sa.text(f'UPDATE {table} SET account_ledger_id=NULL,account_role=NULL{where}'))


def test_rojmel_context_and_quotation_fk(prepared):
    engine, migrate = prepared
    migrate('upgrade', HEAD)
    with engine.begin() as conn:
        for sql in [
            "UPDATE rojmel SET account_ledger_id=(SELECT account_ledger_id FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=1),account_role='CUSTOMER' WHERE party_id IS NOT NULL",
            "UPDATE rojmel SET account_ledger_id=(SELECT account_ledger_id FROM legacy_account_map WHERE legacy_source='party' AND legacy_id=1),account_role='SUPPLIER' WHERE customer_id IS NULL AND party_id IS NULL",
            "UPDATE quotations SET account_id=999999",
            "DELETE FROM account_ledgers WHERE role='CUSTOMER'",
            "UPDATE account_ledgers SET id=id+1000 WHERE role='CUSTOMER'",
        ]:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(sa.text(sql))
        columns = {c['name'] for c in sa.inspect(conn).get_columns('quotations')}
        assert 'account_id' in columns and not columns & {'account_ledger_id','account_role'}


@pytest.mark.parametrize('failure', ['missing_map','missing_mapping','malformed','missing_account','missing_role',
    'missing_ledger','wrong_customer_role','wrong_party_role','unsupported_party','dual_rojmel',
    'sales_parent','purchase_parent','unmapped_new_identity','duplicate_target','duplicate_source','preexisting_reference'])
def test_preflight_failure_is_atomic(prepared, failure):
    engine, migrate = prepared
    with engine.begin() as conn:
        # Deliberately corrupt disposable fixtures by dropping only the constraints
        # needed for the malformed-data case. Production guards are not disabled.
        if failure in ('missing_account','missing_role','missing_ledger','wrong_customer_role','wrong_party_role','duplicate_target'):
            for table in ('legacy_account_map','account_ledgers','account_roles'):
                for fk in sa.inspect(conn).get_foreign_keys(table):
                    conn.execute(sa.text(f'ALTER TABLE {table} DROP CONSTRAINT "{fk["name"]}"'))
        statements = {
            'missing_map':'ALTER TABLE legacy_account_map RENAME TO hidden_map',
            'missing_mapping':"DELETE FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=3",
            'malformed':"UPDATE legacy_account_map SET source_snapshot='[]'::jsonb WHERE legacy_source='customer' AND legacy_id=3",
            'missing_account':"DELETE FROM accounts WHERE account_code='CUS-0003'",
            'missing_role':"DELETE FROM account_roles WHERE account_id=(SELECT account_id FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=3)",
            'missing_ledger':"DELETE FROM account_ledgers WHERE id=(SELECT account_ledger_id FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=3)",
            'wrong_customer_role':"UPDATE legacy_account_map SET account_role='SUPPLIER' WHERE legacy_source='customer' AND legacy_id=3",
            'wrong_party_role':"UPDATE legacy_account_map SET account_role='CUSTOMER' WHERE legacy_source='party' AND legacy_id=1",
            'unsupported_party':"UPDATE parties SET party_type='Customer' WHERE id=1",
            'dual_rojmel':"ALTER TABLE rojmel DROP CONSTRAINT ck_rojmel_one_account",
            'sales_parent':"UPDATE sales_returns SET customer_id=2 WHERE return_no='SR-LINK'",
            'purchase_parent':"UPDATE purchase_returns SET party_id=4 WHERE return_no='PR-LINK'",
            'unmapped_new_identity':"INSERT INTO customers(id,customer_name,mobile,address,city,state,is_active) VALUES(999,'Unmapped','123','Road','City','Gujarat',true)",
            'duplicate_target':"UPDATE legacy_account_map SET account_id=(SELECT account_id FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=1),account_ledger_id=(SELECT account_ledger_id FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=1) WHERE legacy_source='customer' AND legacy_id=2",
            'duplicate_source':'ALTER TABLE legacy_account_map DROP CONSTRAINT legacy_account_map_pkey',
            'preexisting_reference':'ALTER TABLE bill ADD COLUMN account_ledger_id INTEGER DEFAULT 999999',
        }
        conn.execute(sa.text(statements[failure]))
        if failure == 'duplicate_source':
            conn.execute(sa.text("INSERT INTO legacy_account_map SELECT * FROM legacy_account_map WHERE legacy_source='customer' AND legacy_id=1"))
        if failure == 'dual_rojmel':
            conn.execute(sa.text('UPDATE rojmel SET party_id=1 WHERE customer_id IS NOT NULL'))
        if failure == 'unmapped_new_identity':
            conn.execute(sa.text('UPDATE bill SET customer_id=999 WHERE customer_id=3'))
    if failure == 'missing_map':
        before = None
    else:
        before = contents(engine)
    output = migrate('upgrade', HEAD, succeeds=False)
    assert 'Phase 3A aborted:' in output
    if before is not None:
        assert contents(engine) == before
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == PRE
        assert 'account_id' not in {c['name'] for c in sa.inspect(conn).get_columns('quotations')}
        assert 'uq_account_ledgers_id_role' not in {u['name'] for u in sa.inspect(conn).get_unique_constraints('account_ledgers')}


@pytest.mark.parametrize('failure', ['raise','balance','stock','item','timestamp'])
def test_failure_after_backfill_rolls_back_everything(prepared, failure):
    engine, migrate = prepared
    with engine.begin() as conn:
        actions = {
            'raise':"RAISE EXCEPTION 'injected after document backfill';",
            'balance':'UPDATE account_ledgers SET current_balance=current_balance+1,current_balance_type=COALESCE(current_balance_type,\'Credit\');',
            'stock':'UPDATE item_master SET current_stock=current_stock+1;',
            'item':'UPDATE bill_item SET quantity=quantity+1;',
            'timestamp':"UPDATE purchases SET updated_at=updated_at+interval '1 second';",
        }
        conn.execute(sa.text('CREATE FUNCTION p3a_inject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
                             + actions[failure] + ' RETURN NEW; END $$'))
        conn.execute(sa.text('CREATE TRIGGER p3a_inject BEFORE UPDATE ON rojmel FOR EACH ROW EXECUTE FUNCTION p3a_inject()'))
    before = contents(engine)
    output = migrate('upgrade', HEAD, succeeds=False)
    assert ('injected after document backfill' if failure=='raise' else 'protected contents changed') in output
    assert contents(engine) == before
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == PRE
        for table in HEADERS:
            assert not {c['name'] for c in sa.inspect(conn).get_columns(table)} & {'account_id','account_ledger_id','account_role'}


def test_legacy_runtime_rojmel_reference_compatibility(prepared):
    # Populated rehearsal proves old Rojmel writers work with populated references.
    from api.schema.rojmel import RojmelCreate, RojmelUpdate
    from api.services import rojmel
    engine, migrate = prepared
    migrate('upgrade', HEAD)
    with Session(engine) as db:
        record = rojmel.get_rojmel(db, db.execute(sa.text("SELECT id FROM rojmel WHERE receipt_no='R-0'")).scalar_one())
        saved_reference = (record.account_ledger_id, record.account_role)
        before = db.execute(sa.text('SELECT current_balance FROM account_ledgers ORDER BY id')).scalars().all()
        rojmel.update_rojmel(db, record.id, RojmelUpdate(remarks='Metadata only'))
        assert (record.account_ledger_id, record.account_role) == saved_reference
        rojmel.update_rojmel(db, record.id, RojmelUpdate(customer_id=None, party_id=4))
        assert record.account_ledger_id is record.account_role is None
        rojmel.update_rojmel(db, record.id, RojmelUpdate(party_id=None))
        assert record.account_ledger_id is record.account_role is None
        created = rojmel.create_rojmel(db, RojmelCreate(transaction_type='Cr Pay',customer_id=2,
            receipt_no='ignored',given_taken_date=date.today(),effective_date=date.today(),
            cash_bank_id=record.cash_bank_id,done_by_id=record.done_by_id,pay_mode='Cash',amount=10))
        assert created.account_ledger_id is created.account_role is None
        rojmel.delete_rojmel(db, created.id)
        assert db.execute(sa.text('SELECT current_balance FROM account_ledgers ORDER BY id')).scalars().all() == before


def test_strict_empty_full_chain(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'head')
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == HEAD
        for table in (*HEADERS, 'account_ledgers','legacy_account_map'):
            assert conn.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() == 0


@pytest.mark.parametrize('receipt,changes', [
    ('R-0', dict(customer_id=2)),
    ('R-4', dict(party_id=5)),
    ('R-4', dict(party_id=None, customer_id=2)),
    ('R-0', dict(customer_id=None)),
])
def test_legacy_runtime_rojmel_identity_changes(prepared, receipt, changes):
    from api.schema.rojmel import RojmelUpdate
    from api.services import rojmel
    engine, migrate = prepared
    migrate('upgrade', HEAD)
    with Session(engine) as db:
        record = rojmel.get_rojmel(db, db.execute(sa.text('SELECT id FROM rojmel WHERE receipt_no=:receipt'),
                                                 dict(receipt=receipt)).scalar_one())
        saved = (record.account_ledger_id, record.account_role)
        assert all(value is not None for value in saved)
        rojmel.update_rojmel(db, record.id, RojmelUpdate(customer_id=record.customer_id, party_id=record.party_id))
        db.refresh(record)
        assert (record.account_ledger_id, record.account_role) == saved
        rojmel.update_rojmel(db, record.id, RojmelUpdate(**changes))
        db.refresh(record)
        assert record.account_ledger_id is record.account_role is None


@pytest.mark.parametrize('kind', ['bill', 'sales_return', 'purchase', 'purchase_return', 'quotation'])
def test_legacy_runtime_document_reference_compatibility(prepared, kind):
    """Exercise public payloads through real services/repositories on migrated PG."""
    from importlib import import_module
    engine, migrate = prepared
    migrate('upgrade', HEAD)
    schema = import_module(f'api.schema.{kind}')
    service = import_module(f'api.services.{kind}')
    prefix = ''.join(word.title() for word in kind.split('_'))
    create_schema = getattr(schema, prefix + 'Create')
    update_schema = getattr(schema, prefix + 'Update')
    create = getattr(service, 'create_' + kind)
    update = getattr(service, 'update_' + kind + ('' if kind == 'bill' else '_by_id'))
    purchasing = kind in ('purchase', 'purchase_return')
    identity = 'party_id' if purchasing else 'customer_id'
    old_id, new_id = (4, 5) if purchasing else (1, 2)
    with Session(engine) as db:
        item_id = db.execute(sa.text("SELECT id FROM item_master WHERE name='Stock fixture'")).scalar_one()
        db.execute(sa.text('UPDATE item_master SET is_active=true'))
        db.execute(sa.text('UPDATE customers SET is_active=true'))
        db.execute(sa.text('UPDATE parties SET is_active=true'))
        db.commit()
        ledger_before = db.execute(sa.text('SELECT to_jsonb(l)::text FROM account_ledgers l ORDER BY id')).scalars().all()
        line = dict(item_id=item_id, item_name='Stock fixture', hsn_code='1234', unit='units',
                    quantity=1, price=100, rate=100, disc_percent=0, cgst=0, sgst=0, igst=0)
        payload = {identity: old_id, 'items': [line], 'is_gst': False}
        if kind in ('bill', 'purchase'):
            payload.update(bill_date=date(2026, 10, 21), bill_no='COMPAT-PURCHASE')
        if kind.endswith('return'):
            payload['return_reason'] = 'Compatibility test'
        record = create(db, create_schema(**payload))
        fields = ('account_id',) if kind == 'quotation' else ('account_ledger_id', 'account_role')
        assert all(getattr(record, field) is None for field in fields)
        mapping = db.execute(sa.text('SELECT * FROM legacy_account_map WHERE legacy_source=:source AND legacy_id=:id'),
                             dict(source='party' if purchasing else 'customer', id=old_id)).mappings().one()
        saved = tuple(mapping[field] for field in fields)
        for field, value in zip(fields, saved):
            setattr(record, field, value)
        db.commit()
        record_id = record.bill_id if kind == 'bill' else record.id
        # Bill uses full PUT; other modules accept partial updates.
        base = payload if kind == 'bill' else {}
        for changes in ({'remarks': 'Metadata only'}, {identity: old_id}):
            update(db, record_id, update_schema(**(base | changes)))
            db.refresh(record)
            assert tuple(getattr(record, field) for field in fields) == saved
        update(db, record_id, update_schema(**(base | {identity: new_id})))
        db.refresh(record)
        assert getattr(record, identity) == new_id
        assert all(getattr(record, field) is None for field in fields)
        assert db.execute(sa.text('SELECT to_jsonb(l)::text FROM account_ledgers l ORDER BY id')).scalars().all() == ledger_before
