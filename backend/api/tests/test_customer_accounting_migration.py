"""Opt-in round trip on a new disposable PostgreSQL DB, never the configured DB."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from api.config.database import DATABASE_URL
from api.model.bill import Bill
from api.model.sales_return import SalesReturn


def test_customer_accounting_postgresql_migration():
    if os.environ.get('BILLING_ACCOUNT_MIGRATION_TEST') != '1':
        pytest.skip('Opt in with BILLING_ACCOUNT_MIGRATION_TEST=1; requires CREATE DATABASE')
    backend = Path(__file__).resolve().parents[2]
    python = os.environ.get('BILLING_ALEMBIC_PYTHON', sys.executable)
    database = 'billing_test_bootstrap_account_' + uuid4().hex[:12]
    assert database.isidentifier() and database.startswith('billing_test_bootstrap_account_')
    source = make_url(DATABASE_URL)
    admin = create_engine(source, isolation_level='AUTOCOMMIT')
    engine = None
    created = False
    env = dict(os.environ, DATABASE_URL=source.set(database=database).render_as_string(hide_password=False),
               PYTHONDONTWRITEBYTECODE='1')

    def migrate(*args, succeeds=True):
        result = subprocess.run([python, '-B', '-m', 'alembic', *args], cwd=backend,
                                env=env, capture_output=True, text=True, timeout=60)
        # Never echo connection-bearing CLI errors or configured secrets.
        assert (result.returncode == 0) == succeeds, 'Unexpected Alembic result (output suppressed)'

    def balances():
        with engine.connect() as conn:
            return [tuple(row) for row in conn.execute(text(
                'SELECT current_balance,current_balance_type FROM customers ORDER BY id'))]

    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE {database}'))
        created = True
        engine = create_engine(source.set(database=database))
        migrate('upgrade', '7414692a3849')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO customers (customer_name,mobile,address,city,state,is_active) VALUES "
                              "('Fixture','9876543210','Road','City','State',false),"
                              "('Second','9876543211','Road','City','State',true)"))
        migrate('upgrade', 'b8f2d9a73106')
        assert balances() == [(0, 'Credit'), (0, 'Credit')]
        with engine.begin() as conn:
            conn.execute(text("UPDATE customers SET opening_balance=1000,balance_type='Debit',"
                              "current_balance=1000,current_balance_type='Debit' WHERE id=1"))
            for active, total, number in [(True, 5000, 'Active'), (False, 999, 'Inactive')]:
                conn.execute(Bill.__table__.insert().values(invoice_no=number, customer_id=1,
                    bill_date=date.today(), customer_name='Fixture', mobile='9876543210', address='Road',
                    city='City', state='State', total_boxes=0, subtotal=total, taxable_amount=total,
                    grand_total=total, amount_in_words='Fixture', is_active=active))
                conn.execute(SalesReturn.__table__.insert().values(return_no=number, customer_id=1,
                    return_date=date.today(), grand_total=1500 if active else 999, return_reason='Fixture', is_active=active))
        migrate('upgrade', 'head')
        assert balances() == [(4500, 'Debit'), (0, 'Credit')]
        migrate('upgrade', 'head') # no second posting
        assert balances() == [(4500, 'Debit'), (0, 'Credit')]
        with engine.connect() as conn:
            assert any(fk['constrained_columns'] == ['customer_id'] and fk['referred_table'] == 'customers'
                       for fk in inspect(conn).get_foreign_keys('rojmel'))
            assert any(c['name'] == 'ck_rojmel_one_account' for c in inspect(conn).get_check_constraints('rojmel'))
        migrate('downgrade', 'b8f2d9a73106')
        assert balances() == [(1000, 'Debit'), (0, 'Credit')]
        migrate('upgrade', 'head')
        assert balances() == [(4500, 'Debit'), (0, 'Credit')]
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO banks (name,is_active) VALUES ('Cash',true)"))
            conn.execute(text("INSERT INTO doneby (name,is_active) VALUES ('Operator',true)"))
            conn.execute(text("INSERT INTO rojmel (transaction_type,receipt_no,given_taken_date,effective_date,"
                              "customer_id,cash_bank_id,done_by_id,pay_mode,amount,net_amount) VALUES "
                              "('CR_PAY','Guard',CURRENT_DATE,CURRENT_DATE,1,1,1,'Cash',100,100)"))
        migrate('downgrade', 'b8f2d9a73106', succeeds=False)
        assert balances() == [(4500, 'Debit'), (0, 'Credit')]
        with engine.begin() as conn:
            assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'c4a9e7120d35'
            conn.execute(text("DELETE FROM rojmel WHERE receipt_no='Guard'"))
        migrate('downgrade', '7414692a3849')
        migrate('upgrade', 'head')
        assert balances() == [(3500, 'Debit'), (0, 'Credit')] # opening removed by foundation downgrade
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE {database}'))
        admin.dispose()
