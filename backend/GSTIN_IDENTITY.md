# Global account GSTIN identity

Customer and Party (including Supplier and Purchase Vendor) share
`account_gstin_registry`. Its `uq_account_gstin` unique index is the concurrency
authority. `(account_source, account_id)` is the owner primary key; numeric IDs
alone are not identities. Inactive accounts retain their reservations.

`api/utils/gstin.py` trims, uppercases and validates the existing Customer format
for every participating account. Empty values become null. This checks format,
not GST registration status or checksum.

Account create/update services use `validate_available` for a friendly indexed
precheck and `save_account` for the write. The existing repository flush obtains
the account ID; the registry is inserted/updated/deleted before the same commit.
Neither write persists if reservation or commit fails. Updates retain the existing
account row lock. A flush does not expose an uncommitted account to other requests.
GSTIN uniqueness failures become HTTP 400:
`GSTIN is already used by another account.`

Future roles backed by Party automatically participate. A new account domain must
use the same normalization and identity service with a distinct source value.
Account imports/maintenance must also use this service: direct SQL writes to the
Customer/Party GSTIN columns bypass application reservation. Do not run older
application versions that write accounts after the registry cutover.

## Migration

`e9a41c8d720b` follows `c4a9e7120d35`. Stop account writers during deployment,
upgrade, then start the new application. The migration locks both account tables,
checks normalized duplicates and invalid formats, normalizes stored values and
backfills the registry. It fails transactionally with source/ID diagnostics rather
than choosing a conflicting owner. Null/blank values receive no registry row.
This one-time audit/backfill scans existing accounts in SQL; request validation
does not scan account tables. Historical migrations are unchanged.

Downgrade removes the registry and its global guarantee, retaining canonical GSTIN
spellings and all account data. Run downgrade only with account writers stopped.
Production migration execution is a separate deployment action.

## Verification

From `backend`:

```powershell
python -m pytest api/tests/test_gstin_identity.py api/tests/customer api/tests/party -q
$env:BILLING_GSTIN_POSTGRES_TEST='1'
$env:BILLING_ALEMBIC_PYTHON=(Resolve-Path '.\venv\Scripts\python.exe').Path
python -m pytest api/tests/test_gstin_postgresql.py -q
```

The PostgreSQL tests create/drop uniquely named `billing_test_bootstrap_gstin_*`
databases. They never migrate the configured application database. Races force
both prechecks to pass before writing; the unique constraint selects one winner.
Migration checks cover conflicts, invalid data, backfill, downgrade/upgrade,
balance preservation and index availability. Query-plan verification disables
sequential scans only inside its test transaction to demonstrate index eligibility;
it is not a million-row performance benchmark.
