"""Opt-in real pg_dump/pg_restore drill; creates only disposable databases."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from api.config.database import DATABASE_URL
from api.model.company_profile import CompanyProfile
from api.tests.test_postgresql_bootstrap import test_migrated_postgresql_application as smoke


def snapshot(engine):
    with engine.connect() as connection:
        inspector = inspect(connection)
        data = {}
        for table in sorted(inspector.get_table_names()):
            rows = connection.exec_driver_sql(f'SELECT row_to_json(t)::text FROM "{table}" t').scalars().all()
            data[table] = sorted(rows)
        sequences = {name: tuple(connection.exec_driver_sql(
            f'SELECT last_value, is_called FROM "{name}"').one())
            for name in inspector.get_sequence_names()}
        constraints = {name: (inspector.get_foreign_keys(name), inspector.get_indexes(name),
                             inspector.get_unique_constraints(name)) for name in data}
        return data, sequences, constraints


@pytest.mark.skipif(os.environ.get('BILLING_BACKUP_VERIFY') != '1', reason='Opt-in PostgreSQL recovery drill')
def test_native_backup_restore(monkeypatch):
    root = Path(__file__).resolve().parents[3]
    suffix = uuid4().hex[:8]
    source = 'billing_test_bootstrap_backup_' + suffix
    target = 'billing_test_bootstrap_restore_' + suffix
    url = make_url(DATABASE_URL)
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{source}" TEMPLATE template0')
    admin.dispose()
    command = [str(root / 'backend/venv/Scripts/python.exe'), '-B', '-m', 'alembic',
               '-c', str(root / 'backend/alembic.ini'), '-x', 'database=' + source, 'upgrade', 'head']
    subprocess.run(command, check=True)
    monkeypatch.setenv('BILLING_BOOTSTRAP_TEST_DATABASE', source)
    smoke(monkeypatch)
    source_engine = create_engine(url.set(database=source))
    target_engine = create_engine(url.set(database=target))
    try:
        with Session(source_engine) as session:
            session.add(CompanyProfile(company_name='Recovery Test Company', terms_and_conditions=['Test terms']))
            session.commit()
        before = snapshot(source_engine)
        directory = root / 'backend/backups' / source
        script = [sys.executable, '-B', str(root / 'backend/scripts/database_backup.py')]
        pg_bin = os.environ['BILLING_TEST_PG_BIN']
        subprocess.run(script + ['backup', '--database', source, '--directory', str(directory),
                                 '--pg-bin', pg_bin], check=True)
        archive, = directory.glob('*.dump')
        assert snapshot(source_engine) == before, 'Backup must not modify source data or sequences'
        subprocess.run(script + ['restore', str(archive), '--database', target, '--pg-bin', pg_bin], check=True)
        assert snapshot(target_engine) == before, 'All rows, sequence state and constraints must survive'
        print('RECOVERY_VERIFIED', json.dumps({'source': source, 'target': target,
              'archive': str(archive), 'bytes': archive.stat().st_size,
              'counts': {table: len(rows) for table, rows in before[0].items()},
              'sequences': before[1]}))
        monkeypatch.setenv('BILLING_BOOTSTRAP_TEST_DATABASE', target)
        smoke(monkeypatch)  # Create new Customer, Party, Item, Bill and Purchase after restore.
        after = snapshot(target_engine)
        for table in ('customers', 'parties', 'item_master', 'bill', 'bill_item', 'purchases', 'purchase_items'):
            assert len(after[0][table]) == len(before[0][table]) + 1
        for sequence in ('party_code_seq', 'customer_code_seq', 'parties_id_seq',
                         'customers_id_seq', 'bill_bill_id_seq', 'purchases_id_seq'):
            assert after[1][sequence][0] > before[1][sequence][0]
        # Refused operations must leave the populated restored database untouched.
        for arguments in ([str(archive), '--database', target],
                          [str(archive), '--database', url.database],
                          [str(archive)], ['missing.dump', '--database', target + '_missing']):
            result = subprocess.run(script + ['restore', *arguments, '--pg-bin', pg_bin], capture_output=True)
            assert result.returncode != 0
            assert not url.password or url.password.encode() not in result.stderr
        assert snapshot(target_engine) == after
        for operation, arguments in [('backup', ['--database', source, '--directory', str(directory)]),
                                     ('restore', [str(archive), '--database', target + '_missing'])]:
            result = subprocess.run(script + [operation, *arguments, '--pg-bin', str(directory / 'missing-tools')],
                                    capture_output=True)
            assert result.returncode != 0 and b'not found' in result.stderr
        # A real native-tool failure must not leave a published/partial backup.
        failed_dir = directory / 'failed'
        result = subprocess.run(script + ['backup', '--database', source + '_missing',
                                '--directory', str(failed_dir), '--pg-bin', pg_bin], capture_output=True)
        assert result.returncode != 0 and not list(failed_dir.iterdir())
        # Valid archive header/TOC but truncated data: restoration must roll back.
        corrupt = directory / 'truncated.dump'
        corrupt.write_bytes(archive.read_bytes()[:-512])
        failed_target = target + '_failed'
        result = subprocess.run(script + ['restore', str(corrupt), '--database', failed_target,
                                         '--pg-bin', pg_bin], capture_output=True)
        assert result.returncode != 0
        failed_engine = create_engine(url.set(database=failed_target))
        try:
            assert not inspect(failed_engine).get_table_names()
        finally:
            failed_engine.dispose()
            corrupt.unlink()
    finally:
        source_engine.dispose()
        target_engine.dispose()
