# PostgreSQL pilot baseline

The unreleased, incomplete migration history has been consolidated to:

```text
base -> 7414692a3849 (head)
```

`7414692a3849_pilot_schema_baseline.py` is a frozen Alembic snapshot of all
17 current model tables, their indexes/constraints, the Rojmel enum, and
`party_code_seq` / `customer_code_seq`. It does not import application models
or call `create_all`. Add new revisions for future schema changes.

## Existing development Billing_db: no action required

The read-only audit on 2026-09-16 found `Billing_db` already stamped
`7414692a3849`, with all model tables and both code sequences. Columns, types,
nullability, indexes and foreign keys match the models. There are 61 extra
legacy server defaults; these were left untouched. Fresh installations match
the model server defaults exactly; ORM-side defaults continue to work.

Do not recreate, downgrade, or stamp this database. No migration or backup
operation is required for this change: no development database data or schema
was written. Keeping the existing revision ID makes upgrade-to-head a no-op
for this audited database.

Databases at retired revisions `1e7ac6ee08ff` / `0adace7af290`, or populated
databases without an Alembic revision, need a separate schema/data audit before
reconciliation. Do not blindly stamp them. This baseline is not an upgrade
path for those states. No externally deployed database relying on that earlier
history is assumed for this first-client pilot.

## Fresh database

Create an empty PostgreSQL database first. From `backend`, with dependencies
installed, run:

```powershell
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/python.exe -m alembic current
venv/Scripts/python.exe -m alembic heads
```

By default Alembic uses `api.config.database.DATABASE_URL`, just like the app.
For another database on the same server, explicitly select its name:

```powershell
venv/Scripts/python.exe -m alembic -x database=billing_test_bootstrap_20260916 upgrade head
```

The override changes only the database name, not credentials or application
configuration. The target database must already exist. Launch the complete
application as `api.main:app`; it does not create schema at startup. Legacy
`backend/main.py` still contains `Base.metadata.create_all`; it was not changed
or used for bootstrap verification.

## Verification performed

On PostgreSQL 18.3, database `billing_test_bootstrap_20260916`:

- The old chain failed on the missing `parties` foreign-key target.
- Baseline upgrade succeeded from empty, with 17 application tables,
  18 foreign keys, 17 primary-key sequences, two code sequences, and the enum.
- Model comparison, including server defaults, returned zero differences.
- `current` and `heads` both reported `7414692a3849 (head)`.
- `alembic check` reported no new upgrade operations.
- Downgrade to base removed application tables, sequences and enum; a second
  upgrade and API smoke test succeeded. Downgrade is destructive and was tested
  only on this disposable database, never on `Billing_db`.

The small opt-in test uses real `api.main` routes and real PostgreSQL sessions:
Party, Customer, Item, Bill and Purchase creation/read, stock/balance checks,
and both code sequences. From the repository root:

```powershell
$env:BILLING_BOOTSTRAP_TEST_DATABASE = 'billing_test_bootstrap_20260916'
python -B -m pytest backend/api/tests/test_postgresql_bootstrap.py -q -p no:cacheprovider
```

It only accepts names starting with `billing_test_bootstrap_`, never creates or
drops tables, and leaves test records in the disposable database. Without the
environment variable it skips. The disposable database is retained for review.
