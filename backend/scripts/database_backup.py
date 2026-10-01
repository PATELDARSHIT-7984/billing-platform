"""Native PostgreSQL backup and restore into a NEW database only."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.config.database import DATABASE_URL


def postgres_tool(name, directory):
    executable = name + ('.exe' if os.name == 'nt' else '')
    found = Path(directory) / executable if directory else shutil.which(executable)
    if not found or not Path(found).is_file():
        raise ValueError(f'{name} not found. Add PostgreSQL bin to PATH or supply --pg-bin.')
    return str(Path(found).resolve())


def run_tool(command, url, output=None):
    # Credentials are passed only in the child environment, never in arguments.
    env = os.environ.copy()
    env.update(PGHOST=url.host or 'localhost', PGPORT=str(url.port or 5432),
               PGUSER=url.username or '', PGPASSWORD=url.password or '',
               PGDATABASE=url.database, PGCONNECT_TIMEOUT='10')
    result = subprocess.run(command, env=env, stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=False)
    if result.returncode:
        message = result.stderr.decode(errors='replace').strip()
        if url.password:
            message = message.replace(url.password, '[redacted]')
        raise RuntimeError(f'{Path(command[0]).stem} failed ({result.returncode}): {message}')


def backup(url, directory, pg_bin):
    dump = postgres_tool('pg_dump', pg_bin)
    restore = postgres_tool('pg_restore', pg_bin)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    destination = directory / f'{url.database}_{timestamp}.dump'
    partial = destination.with_suffix('.dump.partial')
    # Exclusive creation and publication prevent accidental overwrite.
    with partial.open('xb') as output:
        try:
            run_tool([dump, '--format=custom', '--no-password', '--lock-wait-timeout=30000'], url, output)
            output.flush()
            os.fsync(output.fileno())
        except Exception:
            output.close()
            partial.unlink()
            raise
    try:
        if not partial.stat().st_size:
            raise RuntimeError('pg_dump produced an empty backup')
        run_tool([restore, '--list', str(partial)], url)
        # Hard-link publication fails if the destination already exists.
        os.link(partial, destination)
    finally:
        partial.unlink()
    print(f'Backup complete: {destination} ({destination.stat().st_size} bytes)')


def restore(url, archive, pg_bin):
    tool = postgres_tool('pg_restore', pg_bin)
    archive = Path(archive).resolve()
    if not archive.is_file() or not archive.stat().st_size:
        raise ValueError('Backup path must be an existing, non-empty custom-format archive')
    run_tool([tool, '--list', str(archive)], url)
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT',
                          connect_args={'connect_timeout': 10})
    try:
        with admin.connect() as connection:
            if connection.execute(text('SELECT 1 FROM pg_database WHERE datname=:name'),
                                  {'name': url.database}).scalar():
                raise ValueError('Restore refused: target database already exists. Choose a NEW name.')
            identifier = connection.dialect.identifier_preparer.quote_identifier(url.database)
            connection.exec_driver_sql(f'CREATE DATABASE {identifier} TEMPLATE template0')
    finally:
        admin.dispose()
    try:
        run_tool([tool, '--dbname', url.database, '--no-password', '--no-owner',
                  '--no-privileges', '--single-transaction', '--exit-on-error', str(archive)], url)
    except (RuntimeError, OSError) as error:
        raise RuntimeError(f'{error}\nRestore failed; the newly created database was left for inspection. '
                           'No existing database was dropped. Retry with a new target name.') from None
    print(f'Restore complete: {url.database}. Verify data and application before switching connections.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('backup', help='Read-only dump of the configured database')
    create.add_argument('--database', help='Override source database name on the configured server')
    create.add_argument('--directory', default=str(Path(__file__).resolve().parents[1] / 'backups'))
    recover = commands.add_parser('restore', help='Restore only into a newly created database')
    recover.add_argument('archive')
    recover.add_argument('--database', required=True, help='Required NEW target database name')
    for command in (create, recover):
        command.add_argument('--pg-bin', help='PostgreSQL bin directory if utilities are not on PATH')
    args = parser.parse_args()
    configured = make_url(DATABASE_URL)
    database = args.database or configured.database
    try:
        if configured.get_backend_name() != 'postgresql':
            raise ValueError('This utility requires PostgreSQL')
        if not database or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', database):
            raise ValueError('Use a database name of 1-63 ASCII letters, digits or underscores, starting with a letter or underscore')
        if args.command == 'restore' and database.casefold() == configured.database.casefold():
            raise ValueError('Restore refused: target is the configured application database')
        url = configured.set(database=database)
        if args.command == 'backup':
            backup(url, args.directory, args.pg_bin)
        else:
            restore(url, args.archive, args.pg_bin)
    except (ValueError, RuntimeError, OSError, SQLAlchemyError) as error:
        message = str(error)
        if configured.password:
            message = message.replace(configured.password, '[redacted]')
        print(f'ERROR: {message}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
