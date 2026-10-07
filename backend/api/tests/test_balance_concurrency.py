"""Real PostgreSQL contention; SQLite cannot verify account row locks."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from api.config.database import DATABASE_URL
from api.model.customer import Customer
from api.model.party import Party
from api.schema.customer import CustomerUpdate
from api.schema.party import PartyUpdate
from api.services import customer, party
from api.utils.account_balance import signed_balance


@pytest.fixture(scope='module')
def postgres_accounts():
    if os.environ.get('BILLING_BALANCE_CONCURRENCY_TEST') != '1':
        pytest.skip('Opt in with BILLING_BALANCE_CONCURRENCY_TEST=1; requires CREATE DATABASE')
    source = make_url(DATABASE_URL)
    database = 'billing_test_bootstrap_balance_' + uuid4().hex[:12]
    assert database.isidentifier() and database.startswith('billing_test_bootstrap_balance_')
    admin = create_engine(source, isolation_level='AUTOCOMMIT')
    engine = None
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE {database}'))
        created = True
        url = source.set(database=database)
        env = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([os.environ.get('BILLING_ALEMBIC_PYTHON', sys.executable),
            '-B', '-m', 'alembic', 'upgrade', 'head'], cwd=Path(__file__).resolve().parents[2],
            env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, 'Migration failed (connection-bearing output suppressed)'
        engine = create_engine(url)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE {database}'))
        admin.dispose()


@pytest.mark.parametrize('kind', ['Customer', 'Supplier', 'PURCHASE_VENDOR'])
@pytest.mark.parametrize('second_action', ['post', 'opening'])
@pytest.mark.parametrize('rollback_first', [False, True])
def test_waiting_writer_uses_latest_balance(postgres_accounts, kind, second_action, rollback_first):
    engine = postgres_accounts
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    model = Customer if kind == 'Customer' else Party
    mutate = customer.apply_customer_balance_delta if kind == 'Customer' else party.apply_party_balance_delta
    with sessions() as setup:
        values = dict(opening_balance=100, current_balance=100, balance_type='Credit', current_balance_type='Credit')
        account = (Customer(customer_name='Concurrent', mobile='9876543210', address='Road', city='City', state='State', **values)
                   if kind == 'Customer' else Party(name='Concurrent', party_type=kind, **values))
        setup.add(account)
        setup.commit()
        account_id = account.id

    cached, proceed = Event(), Event()
    worker_pid = []

    def second_writer():
        with sessions() as db:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            worker_pid.append(db.execute(text('SELECT pg_backend_pid()')).scalar_one())
            stale = db.get(model, account_id)  # strong reference deliberately retains stale identity map
            assert stale.current_balance == 100
            cached.set()
            assert proceed.wait(10), 'First writer never released the test gate'
            if second_action == 'post':
                mutate(db, account_id, Decimal('40'))
                db.commit()
            elif kind == 'Customer':
                customer.update_customer(db, account_id, CustomerUpdate(customer_name='Concurrent',
                    mobile='9876543210', address='Road', city='City', state='State', opening_balance=200))
            else:
                party.update_party_by_id(db, account_id, PartyUpdate(opening_balance=200))

    with ThreadPoolExecutor(max_workers=1) as pool, sessions() as first:
        future = pool.submit(second_writer)
        try:
            assert cached.wait(10), 'Second connection did not preload the account'
            mutate(first, account_id, Decimal('-125'))
            first_pid = first.execute(text('SELECT pg_backend_pid()')).scalar_one()
            assert first_pid != worker_pid[0]
            proceed.set()
            # Prove PostgreSQL actually blocked the second connection on this writer.
            deadline = monotonic() + 5
            blocked = False
            with engine.connect() as observer:
                while monotonic() < deadline and not future.done():
                    blockers = observer.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid': worker_pid[0]}).scalar_one()
                    if first_pid in blockers:
                        blocked = True
                        break
                    sleep(0.01)
            assert blocked, 'Second writer did not wait for the account row lock'
            if rollback_first:
                first.rollback()
            else:
                first.commit()
            future.result(timeout=10)
        finally:
            proceed.set()
            first.rollback()  # also releases the lock if any assertion above failed

    with sessions() as verify:
        saved = verify.get(model, account_id)
        expected = (100 if rollback_first else -25) + (40 if second_action == 'post' else 100)
        assert signed_balance(saved.current_balance, saved.current_balance_type) == expected
        assert saved.opening_balance == (100 if second_action == 'post' else 200)
