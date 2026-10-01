# Client #1 PostgreSQL backup and recovery

Run these PowerShell commands from the project root. Use the existing Python
environment and PostgreSQL 18 tools (currently installed at the path below).
Use pg_dump from the same PostgreSQL major version as the server, or a supported
newer client. Restore to the same or a supported newer PostgreSQL version.

## Create a backup

```powershell
backend/venv/Scripts/python.exe -B backend/scripts/database_backup.py backup --pg-bin "C:/Program Files/PostgreSQL/18/bin"
```

This reads the configured application database without changing its records or
sequences. It writes a PostgreSQL custom-format archive under `backend/backups`,
using the database name and UTC timestamp (including microseconds).
Use `--directory "D:/BillingBackups"` to select a different local NTFS directory.
Use `--database NAME` to back up a different database on the configured server.
Omit `--pg-bin` if both pg_dump and pg_restore are on PATH.

The script uses exclusive temporary-file creation, checks pg_dump's exit code,
flushes the file, checks nonzero size and the archive directory, then publishes
the `.dump` file without overwriting any existing file. Atomic publication uses
a hard link: the backup directory must support hard links (NTFS does).
An interrupted `.partial` file is not a successful backup.

Only a successful restore verifies recoverability; the archive-directory check
alone does not validate every data block. Copy completed `.dump` files to a
separate physical device for PC/disk failure protection. Do not rely on a copy
on the same disk. No automatic retention or deletion is implemented.

## Restore for testing

Use the actual archive path printed by backup and a NEW database name:

```powershell
backend/venv/Scripts/python.exe -B backend/scripts/database_backup.py restore "backend/backups/Billing_db_YYYYMMDDTHHMMSS_microsecondsZ.dump" --database billing_restore_test_20260916 --pg-bin "C:/Program Files/PostgreSQL/18/bin"
```

The script creates the target database; do not create it yourself first.
It always refuses the configured application database and any existing target,
even an empty one. There is no destructive override, DROP, --clean or --create
pg_restore mode. Restore uses a single transaction and stops on the first error.
On failure the newly created target is left for inspection; retry with a new
name. The connecting PostgreSQL account needs CREATEDB and restore privileges.

Only restore archives you trust. Database archives contain executable database
definitions as well as sensitive business data. Keep the backup directory
accessible only to the software owner/authorized account. The archive is not
encrypted. Passwords are passed in the child process environment, never in
command arguments, filenames or normal output; this is not protection against
an administrator inspecting the process. Global users/roles and server settings
are not included. --no-owner/--no-privileges restores objects under the recovery
account rather than requiring the source machine's roles.

## Emergency recovery

1. Stop application use so nobody enters data into the wrong database.
2. Preserve the damaged database and select the latest known-good backup.
3. On the recovery PC, install PostgreSQL and the matching application version;
   configure its connection account. Ensure the archive is locally available.
4. Restore into a NEW name such as `billing_recovery_20260916` with the command
   above. Never erase the original as part of recovery.
5. Verify the restored revision, key record counts, latest bill/purchase totals,
   stock and balances. Test new records/code generation on a disposable recovery
   drill copy before using the recovered business database.
6. Stop FastAPI, point `api.config.database.DATABASE_URL` at the verified recovered
   database, and start the full application (`api.main:app`). Check existing
   records before resuming business use. Connection-setting cleanup is separate.
7. Keep the original database and archive until the owner confirms recovery.

A full restore includes `alembic_version`, tables, data, indexes, constraints,
enum types and sequence state. Check revision without applying migrations:

```powershell
backend/venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini -x database=billing_recovery_20260916 current
```

For the current application it should be `7414692a3849`. Do not run upgrade or
stamp automatically after restore. An older archive needs its corresponding
application version and a reviewed forward migration path. The baseline remains
frozen and is never reapplied to a restored populated database.

## Reproducible PostgreSQL drill

```powershell
$env:BILLING_BACKUP_VERIFY = '1'
$env:BILLING_TEST_PG_BIN = 'C:/Program Files/PostgreSQL/18/bin'
python -B -m pytest backend/api/tests/test_postgresql_backup.py -q -s -p no:cacheprovider --tb=short
```

This opt-in test creates uniquely named disposable source/restore databases,
seeds through the existing API smoke test plus a company profile, compares all
rows/sequence states/constraints, and creates new documents after restore. It
also tests refusal paths, failed backup cleanup and rollback of truncated data.
It leaves databases and successful archives for inspection; it never drops a
database or touches Billing_db. Test archives are under ignored backend/backups.

## Scheduling later

The same backup command is noninteractive, uses absolute script-relative default
paths, never prompts for a password and exits 0 on success or nonzero on failure.
Windows Task Scheduler can run it unchanged with absolute Python/script/tool
paths and an account that can access PostgreSQL and the destination. No schedule
has been installed. Monitor failures and disk space when scheduling is added.
