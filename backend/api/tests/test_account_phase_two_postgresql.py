"""Remediation/backfill rehearsals exclusively on disposable PostgreSQL."""
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from api.tests.test_gstin_postgresql import postgres_database
from scripts.remediate_account_tax import remediate

ROOT = Path(__file__).resolve().parents[2]
BASELINE = json.loads((ROOT / 'alembic/data/phase_2b_approved.json').read_text(encoding='utf-8'))
HEAD = 'a7c92e1b640d'
PRE = 'c4a9e7120d35'


@pytest.mark.parametrize('baseline_case', ['approved','tampered','missing','malformed'])
def test_deployment_copy_baseline_integrity(postgres_database, tmp_path, baseline_case):
    import os
    import shutil
    import subprocess
    engine, migrate = postgres_database
    migrate('upgrade','f2b61d9a430c')
    deployment = tmp_path / 'checkout' / 'backend'
    deployment.mkdir(parents=True)
    shutil.copytree(ROOT / 'alembic', deployment / 'alembic', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / 'api', deployment / 'api', ignore=shutil.ignore_patterns('__pycache__','tests'))
    shutil.copy2(ROOT / 'alembic.ini', deployment / 'alembic.ini')
    baseline = deployment / 'alembic/data/phase_2b_approved.json'
    if baseline_case == 'tampered':
        baseline.write_bytes(baseline.read_bytes().replace(b'Krunal', b'krunal', 1))
    elif baseline_case == 'missing':
        baseline.unlink()
    elif baseline_case == 'malformed':
        baseline.write_bytes(b'{')
    result = subprocess.run([os.environ['BILLING_ALEMBIC_PYTHON'],'-B','-m','alembic',
                             '-c',str(deployment / 'alembic.ini'),'upgrade',HEAD],
        cwd=tmp_path, env=dict(os.environ, DATABASE_URL=engine.url.render_as_string(hide_password=False)),
        capture_output=True,text=True,timeout=60)
    assert (result.returncode == 0) == (baseline_case == 'approved'), 'Unexpected migration result; connection-bearing output suppressed'
    with engine.connect() as conn:
        if baseline_case == 'approved':
            assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == HEAD
            assert conn.execute(sa.text('SELECT count(*) FROM legacy_account_map')).scalar_one() == 0
        else:
            expected = 'missing or unreadable' if baseline_case == 'missing' else 'SHA-256 mismatch'
            assert expected in result.stderr
            assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == 'f2b61d9a430c'
            assert 'legacy_account_map' not in sa.inspect(conn).get_table_names()
            assert 'gstin_pending' not in {col['name'] for col in sa.inspect(conn).get_columns('accounts')}


def test_strictly_empty_bootstrap_and_roundtrip(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade','head')
    with engine.connect() as conn:
        for table in ('accounts','account_roles','account_ledgers','legacy_account_map'):
            assert conn.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() == 0
    migrate('downgrade','f2b61d9a430c')
    migrate('upgrade','head')


def test_partial_database_cannot_use_empty_bootstrap(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade','f2b61d9a430c')
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO parties(name,opening_balance,current_balance,balance_type,current_balance_type,is_active) VALUES ('Not empty',0,0,'Credit','Credit',true)"))
    migrate('upgrade','head',succeeds=False)


def test_zero_identities_with_transaction_rejects_bootstrap(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade','f2b61d9a430c')
    with engine.begin() as conn:
        bank = conn.execute(sa.text("INSERT INTO banks(name,is_active) VALUES ('Cash',true) RETURNING id")).scalar_one()
        operator = conn.execute(sa.text("INSERT INTO doneby(name,is_active) VALUES ('Operator',true) RETURNING id")).scalar_one()
        # Rojmel permits a cash/bank transaction without a Customer or Party.
        conn.execute(sa.text("INSERT INTO rojmel(transaction_type,receipt_no,given_taken_date,effective_date,"
                             "cash_bank_id,done_by_id,pay_mode,amount,net_amount) VALUES "
                             "('CASH_BANK','Existing',CURRENT_DATE,CURRENT_DATE,:bank,:operator,'Cash',1,1)"),
                     {'bank':bank,'operator':operator})
    before = snapshot(engine)
    output = migrate('upgrade','head',succeeds=False)
    assert 'Empty identity bootstrap requires empty transaction tables' in output
    assert snapshot(engine) == before
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT count(*) FROM customers')).scalar_one() == 0
        assert conn.execute(sa.text('SELECT count(*) FROM parties')).scalar_one() == 0
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == 'f2b61d9a430c'
        assert 'legacy_account_map' not in sa.inspect(conn).get_table_names()


def seed(engine):
    """Exact audited identities; representative documents with exact reference counts."""
    metadata = sa.MetaData()
    metadata.reflect(bind=engine)
    with engine.begin() as conn:
        for source, table in [('customer','customers'),('party','parties')]:
            for original in BASELINE[source]:
                row = dict(original)
                for field in ('opening_balance','current_balance'):
                    row[field] = Decimal(row[field])
                conn.execute(metadata.tables[table].insert().values(**row))

        def document(table_name, **overrides):
            table = metadata.tables[table_name]
            values = dict(overrides)
            for col in table.columns:
                if col.name in values or col.primary_key or col.nullable or col.server_default is not None:
                    continue
                if col.foreign_keys:
                    remote = next(iter(col.foreign_keys)).column
                    existing = conn.execute(sa.select(remote).limit(1)).scalar()
                    values[col.name] = existing if existing is not None else document(remote.table.name)
                elif isinstance(col.type, sa.Enum):
                    values[col.name] = col.type.enums[0]
                elif isinstance(col.type, sa.Boolean):
                    values[col.name] = True
                elif isinstance(col.type, sa.DateTime):
                    values[col.name] = datetime(2026, 10, 18)
                elif isinstance(col.type, sa.Date):
                    values[col.name] = date(2026, 10, 18)
                elif isinstance(col.type, (sa.Numeric, sa.Float, sa.Integer)):
                    values[col.name] = 0
                else:
                    values[col.name] = 'fixture'
            pk = list(table.primary_key)[0]
            return conn.execute(table.insert().values(**values).returning(pk)).scalar_one()

        numbers = {'bill':'invoice_no','sales_returns':'return_no','purchases':'bill_no',
                   'purchase_returns':'return_no','quotations':'quotation_no','rojmel':'receipt_no'}
        for key, counts in BASELINE['references'].items():
            table, column = key.split('.')
            if table == 'rojmel' and column == 'customer_id':
                continue
            for identity, count in counts.items():
                for index in range(count):
                    document(table, **{column: int(identity), numbers[table]: f'{table}-{identity}-{index}'})


def snapshot(engine):
    with engine.connect() as conn:
        return {table: conn.execute(sa.text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text')).scalars().all()
                for table in ('customers','parties','bill','sales_returns','purchases','purchase_returns','quotations','rojmel',
                              'bill_item','sales_return_items','purchase_items','purchase_return_items','quotation_items')}


def upgrade(migrate, succeeds=True):
    return migrate('upgrade', HEAD, succeeds=succeeds)


def prepare(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'f2b61d9a430c')
    seed(engine)
    return engine, migrate


def seed_historical_remediation(engine):
    """Obsolete localhost dataset only; independent of the approved Neon baseline."""
    from scripts.remediate_account_tax import EXPECTED
    with engine.begin() as conn:
        for identity, (gstin, pan) in EXPECTED.items():
            conn.execute(sa.text("INSERT INTO parties(id,name,party_code,gstin,pan_card,opening_balance,"
                                 "current_balance,balance_type,current_balance_type,is_active) VALUES "
                                 "(:id,'Historical local fixture',:code,:gstin,:pan,10,20,'Debit','Credit',true)"),
                         dict(id=identity,code=f'PTY-{identity:04}',gstin=gstin,pan=pan))


def test_remediation_dry_run_and_exact_changes(postgres_database, tmp_path):
    engine, migrate = postgres_database
    migrate('upgrade', PRE)
    seed_historical_remediation(engine)
    before = snapshot(engine)
    report = remediate(engine)
    assert snapshot(engine) == before
    assert report['status'] == 'dry-run'
    artifact = tmp_path / 'audit.json'
    remediate(engine, apply=True, audit_path=artifact)
    after = snapshot(engine)
    assert {k:v for k,v in before.items() if k != 'parties'} == {k:v for k,v in after.items() if k != 'parties'}
    old = {r['id']:r for r in map(json.loads, before['parties'])}
    new = {r['id']:r for r in map(json.loads, after['parties'])}
    for identity, row in old.items():
        if identity in (4,5,10):
            row.update(gstin=None, pan_card=None)
        assert new[identity] == row
    assert [r['id'] for r in json.loads(artifact.read_text())['parties']] == [4,5,10]
    with pytest.raises(ValueError):
        remediate(engine, apply=True, audit_path=tmp_path / 'repeat.json')


@pytest.mark.parametrize('failure', ['tax_drift','missing_row','revision','artifact','db_failure'])
def test_remediation_aborts_atomically(postgres_database, tmp_path, failure):
    engine, migrate = postgres_database
    migrate('upgrade', PRE)
    seed_historical_remediation(engine)
    artifact = tmp_path / 'audit.json'
    with engine.begin() as conn:
        if failure == 'tax_drift':
            conn.execute(sa.text("UPDATE parties SET pan_card='ABCDE1234F' WHERE id=5"))
        elif failure == 'missing_row':
            conn.execute(sa.text('DELETE FROM parties WHERE id=5'))
        elif failure == 'revision':
            conn.execute(sa.text("UPDATE alembic_version SET version_num='unexpected'"))
        elif failure == 'artifact':
            artifact.write_text('existing provenance', encoding='utf-8')
        elif failure == 'db_failure':
            conn.execute(sa.text("CREATE FUNCTION reject_cleanup() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.id=10 AND NEW.gstin IS NULL THEN RAISE EXCEPTION 'injected'; END IF; RETURN NEW; END $$"))
            conn.execute(sa.text('CREATE TRIGGER reject_cleanup BEFORE UPDATE ON parties FOR EACH ROW EXECUTE FUNCTION reject_cleanup()'))
    before = snapshot(engine)
    with pytest.raises(Exception):
        remediate(engine, apply=True, audit_path=artifact)
    assert snapshot(engine) == before


def test_full_chain_reconciliation_and_downgrade(postgres_database, tmp_path):
    engine, migrate = prepare(postgres_database)
    before = snapshot(engine)
    assert [row['id'] for row in BASELINE['customer']] == [1,2,3]
    assert [row['id'] for row in BASELINE['party']] == [1,2,3,4,5]
    assert BASELINE['references'] == {
        'bill.customer_id': {'3':1}, 'purchases.party_id': {'1':1},
        'sales_returns.customer_id': {}, 'purchase_returns.party_id': {},
        'quotations.customer_id': {}, 'rojmel.party_id': {}, 'rojmel.customer_id': {},
    }
    with engine.connect() as conn:
        foreign_keys = {table: sa.inspect(conn).get_foreign_keys(table) for table in before}
        for key, counts in BASELINE['references'].items():
            table, column = key.split('.')
            actual = conn.execute(sa.text(f'SELECT {column},count(*) FROM {table} GROUP BY {column}')).all()
            assert {str(identity): count for identity,count in actual} == counts
    upgrade(migrate)
    assert snapshot(engine) == before
    with engine.connect() as conn:
        assert {table: sa.inspect(conn).get_foreign_keys(table) for table in before} == foreign_keys
        assert dict(conn.execute(sa.text('SELECT role,count(*) FROM account_roles GROUP BY role')).all()) == {
            'CUSTOMER':3, 'SUPPLIER':3, 'PURCHASE_VENDOR':2,
        }
        assert conn.execute(sa.text("SELECT mobile FROM accounts WHERE account_code='PTY-0001'")).scalar_one() == '94293 06505'
        assert conn.execute(sa.text("SELECT mobile FROM accounts WHERE account_code='PTY-0002'")).scalar_one() == '798568984'
        for table in ('accounts','account_roles','account_ledgers','legacy_account_map'):
            assert conn.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() == 8
        mappings = conn.execute(sa.text('SELECT * FROM legacy_account_map ORDER BY legacy_source,legacy_id')).mappings().all()
        assert len({m['account_id'] for m in mappings}) == 8  # No merges of any kind.
        zero_count = 0
        for mapping in mappings:
            source, identity = mapping['legacy_source'], mapping['legacy_id']
            original = next(r for r in BASELINE[source] if r['id'] == identity)
            account = conn.execute(sa.text('SELECT * FROM accounts WHERE id=:id'), {'id':mapping['account_id']}).mappings().one()
            ledger = conn.execute(sa.text('SELECT * FROM account_ledgers WHERE id=:id'), {'id':mapping['account_ledger_id']}).mappings().one()
            role = conn.execute(sa.text('SELECT * FROM account_roles WHERE account_id=:id'), {'id':mapping['account_id']}).mappings().one()
            assert mapping['source_snapshot']['original'] == original
            assert account['account_code'] == mapping['legacy_code'] == original.get('customer_code', original.get('party_code'))
            assert account['is_active'] == role['is_active'] == original['is_active']
            for amount, direction in [('opening_balance','balance_type'),('current_balance','current_balance_type')]:
                assert ledger[amount] == Decimal(original[amount]), (source,identity,amount)
                assert ledger[direction] == (original[direction] if Decimal(original[amount]) else None), (source,identity,direction)
                zero_count += not Decimal(original[amount])
            assert mapping['source_snapshot']['at_backfill'] == original
            assert 'remediation_audit' not in mapping['source_snapshot']
            assert account['gstin_pending'] is False
            assert account['gstin'] == original['gstin']
            assert account['pan_card'] == original['pan_card']
            for field in ('mobile','address','city','country_code','email'):
                assert account[field] == original.get(field)
            expected_role = 'CUSTOMER' if source == 'customer' else ('SUPPLIER' if identity <= 3 else 'PURCHASE_VENDOR')
            assert role['role'] == ledger['role'] == mapping['account_role'] == expected_role
            if (source, identity) in [('customer',3),('party',2)]:
                assert original['state'] == 'Gujarat'
                assert (account['state_code'],account['state']) == ('07','Delhi')
                if source == 'customer':
                    assert original['state_code'] is None
            else:
                assert (account['state_code'],account['state']) == ('24','Gujarat')
            if source == 'party' and identity in (4,5):
                assert account['gstin'] is account['pan_card'] is None
        assert zero_count == 3
    migrate('downgrade','f2b61d9a430c')
    assert snapshot(engine) == before
    upgrade(migrate)
    assert snapshot(engine) == before


@pytest.mark.parametrize('drift', ['unexpected_customer','missing_customer','unexpected_party','missing_party','code','balance','pan','state','reference','target'])
def test_backfill_drift_rolls_back(postgres_database, tmp_path, drift):
    engine, migrate = prepare(postgres_database)
    migrate('upgrade','f2b61d9a430c')
    with engine.begin() as conn:
        statements = {
            'unexpected_customer': "INSERT INTO customers(id,customer_name,customer_code,mobile,address,city,state,is_active) VALUES (99,'New','CUS-NEW','123','Road','City','Gujarat',true)",
            'missing_customer': 'DELETE FROM customers WHERE id=1',
            'missing_party': 'DELETE FROM parties WHERE id=5',
            'unexpected_party': "INSERT INTO parties(id,name,party_code,party_type,opening_balance,current_balance,balance_type,current_balance_type,is_active) VALUES (99,'New','PTY-NEW','Supplier',0,0,'Credit','Credit',true)",
            'code': "UPDATE parties SET party_code='CHANGED' WHERE id=2",
            'balance': 'UPDATE customers SET current_balance=current_balance+1 WHERE id=1',
            'pan': "UPDATE parties SET pan_card='ABCDE1234F' WHERE id=2",
            'state': "UPDATE parties SET state='Unknown' WHERE id=1",
            'reference': 'UPDATE bill SET customer_id=1 WHERE customer_id=3',
            'target': "INSERT INTO accounts(account_code,account_name) VALUES ('UNREVIEWED','Unreviewed')",
        }
        conn.execute(sa.text(statements[drift]))
    before = snapshot(engine)
    output = upgrade(migrate, succeeds=False)
    assert ('source identity set drift' if 'customer' in drift or 'party' in drift else
            'transaction reference baseline differs' if drift == 'reference' else
            'empty target Account tables' if drift == 'target' else 'material drift') in output
    assert snapshot(engine) == before
    with engine.connect() as conn:
        for table in ('accounts','account_roles','account_ledgers'):
            expected_count = int(drift == 'target' and table == 'accounts')
            assert conn.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() == expected_count
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == 'f2b61d9a430c'
        assert 'gstin_pending' not in {c['name'] for c in sa.inspect(conn).get_columns('accounts')}
        assert 'legacy_account_map' not in sa.inspect(conn).get_table_names()


def test_database_guards_and_downgrade_refusal(postgres_database, tmp_path):
    engine, migrate = prepare(postgres_database)
    upgrade(migrate)
    with engine.begin() as conn:
        for sql in [
            "UPDATE accounts SET state_code='27' WHERE account_code='CUS-0001'",
            "UPDATE accounts SET state_code=NULL WHERE account_code='CUS-0001'",
            "UPDATE accounts SET state_code='GJ' WHERE account_code='PTY-0001'",
            "UPDATE accounts SET gstin_pending=true WHERE account_code='CUS-0001'",
            "UPDATE accounts SET pan_card='FGHIJ5678K' WHERE account_code='CUS-0001'",
            "UPDATE legacy_account_map SET account_ledger_id=(SELECT account_ledger_id FROM legacy_account_map WHERE legacy_source='party' AND legacy_id=1) WHERE legacy_source='customer' AND legacy_id=1",
            "DELETE FROM account_ledgers WHERE id=(SELECT account_ledger_id FROM legacy_account_map LIMIT 1)",
            "DELETE FROM accounts WHERE account_code='CUS-0001'",
        ]:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(sa.text(sql))
        conn.execute(sa.text("UPDATE accounts SET remarks='Post-cutover edit' WHERE account_code='CUS-0001'"))
    migrate('downgrade','f2b61d9a430c', succeeds=False)
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT count(*) FROM legacy_account_map')).scalar_one() == 8


def test_failure_after_backfill_writes_rolls_back_schema_and_data(postgres_database, tmp_path):
    engine, migrate = prepare(postgres_database)
    migrate('upgrade','f2b61d9a430c')
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE FUNCTION reject_last_account() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.account_code='PTY-0005' THEN RAISE EXCEPTION 'injected'; END IF; RETURN NEW; END $$"))
        conn.execute(sa.text('CREATE TRIGGER reject_last_account BEFORE INSERT ON accounts FOR EACH ROW EXECUTE FUNCTION reject_last_account()'))
    before = snapshot(engine)
    output = upgrade(migrate, succeeds=False)
    assert 'injected' in output
    assert snapshot(engine) == before
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == 'f2b61d9a430c'
        for table in ('accounts','account_roles','account_ledgers'):
            assert conn.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar_one() == 0
        assert 'legacy_account_map' not in sa.inspect(conn).get_table_names()
        assert 'gstin_pending' not in {col['name'] for col in sa.inspect(conn).get_columns('accounts')}


def test_new_constraints_preserve_nulls_pan_and_concurrent_uniqueness(postgres_database, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    engine, migrate = prepare(postgres_database)
    upgrade(migrate)
    with engine.begin() as conn:
        for code in ('NULL-A','NULL-B'):
            conn.execute(sa.text("INSERT INTO accounts(account_code,account_name,pan_card,gstin_pending) VALUES (:code,'Manual','ZZZZZ1234Z',true)"), {'code':code})
        for values in [dict(state=None, pending=False), dict(state='27', pending=False), dict(state='24', pending=True)]:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(sa.text("INSERT INTO accounts(account_code,account_name,gstin,pan_card,state_code,gstin_pending) VALUES ('BAD','Bad','24ZZZZZ1234Z1Z1','ZZZZZ1234Z',:state,:pending)"), values)
    gate = Barrier(2)
    def insert(worker):
        try:
            with engine.begin() as conn:
                conn.execute(sa.text("SET LOCAL lock_timeout='10s'"))
                gate.wait(timeout=10)
                conn.execute(sa.text("INSERT INTO accounts(account_code,account_name,gstin,pan_card,state_code,state) VALUES (:code,'Race','24ZZZZZ1234Z1Z1','ZZZZZ1234Z','24','Gujarat')"), {'code':f'RACE-{worker}'})
            return 'created'
        except IntegrityError as error:
            assert error.orig.pgcode == '23505'
            assert error.orig.diag.constraint_name == 'uq_accounts_gstin'
            return 'duplicate'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(insert,[1,2])) == ['created','duplicate']
