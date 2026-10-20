"""Phase 1 migrations and raw DB invariants; disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, DataError

from api.tests.test_gstin_postgresql import postgres_database  # Reuse guarded disposable DB fixture.

HEAD = 'f2b61d9a430c'
BRIDGE = 'e9a41c8d720b'


def test_additive_migration_and_round_trip(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'c4a9e7120d35')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO customers (customer_name,mobile,address,city,state,gstin,is_active) "
                          "VALUES ('Legacy','9876543210','Road','City','State','24ABCDE1234F1Z5',true)"))
        conn.execute(text("INSERT INTO parties (name,gstin,opening_balance,current_balance,balance_type,current_balance_type,is_active) "
                          "VALUES ('Legacy','24FGHIJ5678K1Z5',100,80,'Credit','Credit',false)"))
    migrate('upgrade', BRIDGE)

    def legacy_snapshot():
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = set(inspector.get_table_names()) - {'accounts', 'account_roles', 'account_ledgers', 'alembic_version'}
            values = {}
            for table in sorted(tables):
                quoted = engine.dialect.identifier_preparer.quote(table)
                rows = conn.execute(text(f'SELECT row_to_json(t)::text FROM {quoted} t ORDER BY row_to_json(t)::text')).scalars().all()
                columns = [(c['name'], str(c['type']), c['nullable']) for c in inspector.get_columns(table)]
                values[table] = (rows, columns, inspector.get_foreign_keys(table))
            return values

    before = legacy_snapshot()
    migrate('upgrade', 'f2b61d9a430c')
    assert legacy_snapshot() == before
    with engine.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == HEAD
        for table in ('accounts', 'account_roles', 'account_ledgers'):
            assert conn.execute(text(f'SELECT count(*) FROM {table}')).scalar_one() == 0
        indexes = inspect(conn).get_indexes('accounts')
        assert not any(i['unique'] and i['column_names'] == ['pan_card'] for i in indexes)
        fk = inspect(conn).get_foreign_keys('account_ledgers')[0]
        assert fk['constrained_columns'] == ['account_id', 'role']
        assert fk['referred_table'] == 'account_roles'
    migrate('downgrade', BRIDGE)
    assert legacy_snapshot() == before
    assert not {'accounts', 'account_roles', 'account_ledgers'} & set(inspect(engine).get_table_names())
    migrate('upgrade', 'f2b61d9a430c')
    assert legacy_snapshot() == before


def test_direct_sql_tax_integrity(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'f2b61d9a430c')
    with engine.begin() as conn:
        insert = text('INSERT INTO accounts (account_code,account_name,gstin,pan_card) VALUES (:code,\'Example\',:gstin,:pan)')
        for index, (gstin, pan) in enumerate([
            ('24abcde1234f1z5', 'ABCDE1234F'), (' 24ABCDE1234F1Z5', 'ABCDE1234F'),
            ('24ABCDE1234F1Z5 ', 'ABCDE1234F'), ('XXXXXXXXXXXXXXX', 'ABCDE1234F'),
            ('', None), ('24ABCDE1234F1Z5', None), ('24ABCDE1234F1Z5', 'FGHIJ5678K'),
            (None, 'abcde1234f'), (None, 'ABCDEFGHIJ'), (None, ''),
            (None, 'ABCDE1234F '), (None, ' ABCDE1234F'),
            ('24ABCDE1234F1Z5\n', 'ABCDE1234F'), (None, 'ABCDE1234F\n'),
        ]):
            with pytest.raises((IntegrityError, DataError)), conn.begin_nested():
                conn.execute(insert, dict(code=f'bad{index}', gstin=gstin, pan=pan))
        conn.execute(insert, dict(code='valid', gstin='24ABCDE1234F1Z5', pan='ABCDE1234F'))
        conn.execute(insert, dict(code='same-pan', gstin='27ABCDE1234F1Z5', pan='ABCDE1234F'))
        for code in ('null1', 'null2'):
            conn.execute(insert, dict(code=code, gstin=None, pan=None))
        for code in ('pan1', 'pan2'):
            conn.execute(insert, dict(code=code, gstin=None, pan='ABCDE1234F'))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(insert, dict(code='duplicate', gstin='24ABCDE1234F1Z5', pan='ABCDE1234F'))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(insert, dict(code='valid', gstin=None, pan=None))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text("UPDATE accounts SET pan_card='FGHIJ5678K' WHERE account_code='valid'"))
        conn.execute(text('SET LOCAL enable_seqscan = off'))
        plan = ' '.join(conn.execute(text("EXPLAIN SELECT id FROM accounts WHERE gstin='24ABCDE1234F1Z5'")).scalars())
        assert 'uq_accounts_gstin' in plan


def test_direct_sql_roles_and_ledgers(postgres_database):
    engine, migrate = postgres_database
    migrate('upgrade', 'f2b61d9a430c')
    with engine.begin() as conn:
        account = conn.execute(text("INSERT INTO accounts (account_code,account_name) VALUES ('A','Example') RETURNING id")).scalar_one()
        second = conn.execute(text("INSERT INTO accounts (account_code,account_name) VALUES ('B','Second') RETURNING id")).scalar_one()
        for role in ('CUSTOMER', 'SUPPLIER', 'PURCHASE_VENDOR'):
            conn.execute(text('INSERT INTO account_roles (account_id,role) VALUES (:id,:role)'), dict(id=account, role=role))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text("INSERT INTO account_roles (account_id,role) VALUES (:id,'OTHER')"), dict(id=account))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text("INSERT INTO account_roles (account_id,role) VALUES (:id,'CUSTOMER')"), dict(id=account))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text("INSERT INTO account_ledgers (account_id,role) VALUES (:id,'CUSTOMER')"), dict(id=second))
        for field, direction in [('opening_balance', 'balance_type'), ('current_balance', 'current_balance_type')]:
            for amount, kind in [('0', 'Debit'), ('0', 'Credit'), ('1', None), ('1', 'Unknown'),
                                 ('-1', 'Debit'), ('NaN', 'Credit'), ('Infinity', 'Credit'), ('-Infinity', 'Debit')]:
                with pytest.raises((IntegrityError, DataError)), conn.begin_nested():
                    conn.execute(text(f"INSERT INTO account_ledgers (account_id,role,{field},{direction}) "
                                      "VALUES (:id,'CUSTOMER',:amount,:kind)"), dict(id=account, amount=amount, kind=kind))
        customer_ledger = conn.execute(text("INSERT INTO account_ledgers "
            "(account_id,role,opening_balance,balance_type,current_balance,current_balance_type) "
            "VALUES (:id,'CUSTOMER',10000,'Debit',10000,'Debit') RETURNING id"), dict(id=account)).scalar_one()
        supplier_ledger = conn.execute(text("INSERT INTO account_ledgers "
            "(account_id,role,opening_balance,balance_type,current_balance,current_balance_type) "
            "VALUES (:id,'SUPPLIER',6000,'Credit',6000,'Credit') RETURNING id"), dict(id=account)).scalar_one()
        conn.execute(text("INSERT INTO account_ledgers (account_id,role) VALUES (:id,'PURCHASE_VENDOR')"), dict(id=account))
        conn.execute(text('UPDATE account_ledgers SET current_balance=9000 WHERE id=:id'), dict(id=customer_ledger))
        assert conn.execute(text('SELECT current_balance FROM account_ledgers WHERE id=:id'), dict(id=supplier_ledger)).scalar_one() == 6000
        assert conn.execute(text("SELECT current_balance,current_balance_type FROM account_ledgers WHERE role='PURCHASE_VENDOR'")).one() == (0, None)
        for statement in [
            "INSERT INTO account_ledgers (account_id,role) VALUES (:id,'CUSTOMER')",
            "UPDATE account_ledgers SET current_balance_type=NULL WHERE account_id=:id AND role='CUSTOMER'",
            "DELETE FROM account_roles WHERE account_id=:id AND role='CUSTOMER'",
            "UPDATE account_roles SET role='OTHER' WHERE account_id=:id AND role='CUSTOMER'",
            "DELETE FROM accounts WHERE id=:id",
        ]:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text(statement), dict(id=account))
        conn.execute(text('UPDATE account_roles SET is_active=false WHERE account_id=:id'), dict(id=account))
        conn.execute(text('UPDATE accounts SET is_active=false WHERE id=:id'), dict(id=account))
        assert conn.execute(text('SELECT count(*) FROM account_ledgers')).scalar_one() == 3


@pytest.mark.parametrize('kind', ['gstin', 'role'])
def test_concurrent_uniqueness(postgres_database, kind):
    engine, migrate = postgres_database
    migrate('upgrade', 'f2b61d9a430c')
    with engine.begin() as conn:
        account_id = conn.execute(text("INSERT INTO accounts (account_code,account_name) VALUES ('owner','Owner') RETURNING id")).scalar_one()
    for attempt in range(3):
        gate = Barrier(2)
        gstin = f'24ABCDE{1234 + attempt}F1Z5'

        def insert(worker):
            try:
                with engine.begin() as conn:
                    conn.execute(text("SET LOCAL lock_timeout='10s'"))
                    gate.wait(timeout=10)
                    if kind == 'gstin':
                        conn.execute(text("INSERT INTO accounts (account_code,account_name,gstin,pan_card) "
                            "VALUES (:code,'Race',:gstin,:pan)"),
                            dict(code=f'race{attempt}-{worker}', gstin=gstin, pan=f'ABCDE{1234 + attempt}F'))
                    else:
                        conn.execute(text("INSERT INTO account_roles (account_id,role) VALUES (:id,'CUSTOMER')"), dict(id=account_id))
                return 'created'
            except IntegrityError as error:
                assert error.orig.pgcode == '23505'
                assert error.orig.diag.constraint_name == ('uq_accounts_gstin' if kind == 'gstin' else 'uq_account_roles_account_role')
                return 'duplicate'  # No production write service exists in Phase 1.

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(insert, [1, 2])) == ['created', 'duplicate']
        with engine.begin() as conn:
            if kind == 'gstin':
                assert conn.execute(text('SELECT count(*) FROM accounts WHERE gstin=:gstin'), dict(gstin=gstin)).scalar_one() == 1
            else:
                assert conn.execute(text('SELECT count(*) FROM account_roles WHERE account_id=:id'), dict(id=account_id)).scalar_one() == 1
                conn.execute(text('DELETE FROM account_roles WHERE account_id=:id'), dict(id=account_id))
