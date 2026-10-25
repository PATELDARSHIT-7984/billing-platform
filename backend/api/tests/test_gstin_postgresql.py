"""Opt-in real PostgreSQL races and migration safety on disposable databases."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from api.config.database import DATABASE_URL
from sqlalchemy.engine import make_url
from api.model.account_gstin import AccountGSTIN
from api.model.customer import Customer
from api.model.party import Party
from api.schema.customer import CustomerCreate
from api.schema.party import PartyCreate
from api.services import customer, party
from api.services import gstin_identity
from api.tests.test_gstin_identity import payload


@pytest.fixture
def postgres_database():
    if os.environ.get('BILLING_GSTIN_POSTGRES_TEST') != '1':
        pytest.skip('Opt in with BILLING_GSTIN_POSTGRES_TEST=1; creates disposable PostgreSQL DBs')
    source = make_url(DATABASE_URL)
    database = 'billing_test_bootstrap_gstin_' + uuid4().hex[:12]
    admin = create_engine(source, isolation_level='AUTOCOMMIT')
    engine = None
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE {database}'))
        created = True
        url = source.set(database=database)
        engine = create_engine(url)

        def migrate(*args, succeeds=True):
            result = subprocess.run([os.environ.get('BILLING_ALEMBIC_PYTHON', sys.executable), '-B', '-m', 'alembic', *args],
                cwd=Path(__file__).resolve().parents[2],
                env=dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False)),
                capture_output=True, text=True, timeout=60)
            assert (result.returncode == 0) == succeeds, 'Unexpected migration result (connection-bearing output suppressed)'
            return result.stdout + result.stderr

        yield engine, migrate
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE {database}'))
        admin.dispose()


@pytest.mark.parametrize('kinds', [
    ('customer', 'Supplier'), ('customer', 'PURCHASE_VENDOR'),
    ('Supplier', 'PURCHASE_VENDOR'), ('customer', 'customer'),
])
def test_concurrent_global_reservation(postgres_database, monkeypatch, kinds):
    engine, migrate = postgres_database
    migrate('upgrade', 'e9a41c8d720b')
    sessions = sessionmaker(bind=engine)
    validate = gstin_identity.validate_available
    barrier = Barrier(2)

    def both_prechecks_pass(*args, **kwargs):
        validate(*args, **kwargs)
        barrier.wait(timeout=10)

    monkeypatch.setattr(customer.customer_validation, 'validate_gstin_is_unique',
                        lambda db, gstin, exclude_id=None: both_prechecks_pass(db, gstin, 'customer', exclude_id))
    monkeypatch.setattr(party.party_validation, 'validate_gstin_is_unique',
                        lambda db, gstin, exclude_id=None: both_prechecks_pass(db, gstin, 'party', exclude_id))

    for attempt in range(3):
        gstin = f'24ABCDE{1234 + attempt}F1Z5'

        def create(kind):
            with sessions() as db:
                db.execute(text("SET LOCAL lock_timeout = '10s'"))
                try:
                    if kind == 'customer':
                        # Explicit distinct PAN isolates the GSTIN race from the
                        # independent Customer PAN uniqueness constraint.
                        values = payload(kind, gstin)
                        values['pan_card'] = uuid4().hex[:10].upper()
                        customer.create_customer(db, CustomerCreate(**values))
                    else:
                        party.create_party(db, PartyCreate(**payload(kind, gstin)))
                    return 201
                except HTTPException as error:
                    assert error.detail == gstin_identity.DUPLICATE_GSTIN
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, kinds))
        assert sorted(results) == [201, 400]
        with sessions() as db:
            assert db.query(AccountGSTIN).filter_by(normalized_gstin=gstin).count() == 1
            assert (db.query(Customer).filter_by(gstin=gstin).count()
                    + db.query(Party).filter_by(gstin=gstin).count()) == 1


def test_migration_backfill_conflicts_and_round_trip(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'c4a9e7120d35')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO customers (customer_name,mobile,address,city,state,gstin,is_active) "
                          "VALUES ('Test','9876543210','Road','City','State','24abcde1234f1z5',true)"))
        conn.execute(text("INSERT INTO parties (name,gstin,opening_balance,current_balance,balance_type,current_balance_type,is_active) "
                          "VALUES ('Test','24ABCDE1234F1Z5',12,34,'Credit','Debit',false)"))
    output = migrate('upgrade', 'e9a41c8d720b', succeeds=False)
    assert 'conflicting account identities' in output
    with engine.begin() as conn:
        assert 'account_gstin_registry' not in inspect(conn).get_table_names()
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'c4a9e7120d35'
        conn.execute(text("UPDATE parties SET gstin='INVALIDGSTIN123'"))
    output = migrate('upgrade', 'e9a41c8d720b', succeeds=False)
    assert 'invalid account GSTINs' in output
    with engine.begin() as conn:
        conn.execute(text("UPDATE parties SET gstin='  '"))
    migrate('upgrade', 'e9a41c8d720b')

    def verify():
        with engine.connect() as conn:
            assert conn.execute(text('SELECT account_source, account_id, normalized_gstin FROM account_gstin_registry')).all() == [
                ('customer', 1, '24ABCDE1234F1Z5')]
            assert conn.execute(text('SELECT gstin FROM customers')).scalar_one() == '24ABCDE1234F1Z5'
            assert conn.execute(text('SELECT gstin,opening_balance,current_balance,balance_type,current_balance_type,is_active FROM parties')).one() == (
                None, 12, 34, 'Credit', 'Debit', False)
            conn.execute(text('SET LOCAL enable_seqscan = off'))
            plan = conn.execute(text("EXPLAIN SELECT * FROM account_gstin_registry WHERE normalized_gstin='24ABCDE1234F1Z5'"))
            assert 'uq_account_gstin' in ' '.join(row[0] for row in plan)

    verify()
    migrate('downgrade', 'c4a9e7120d35')
    migrate('upgrade', 'e9a41c8d720b')
    verify()
