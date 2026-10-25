# Account Phase 3A: transaction references only

Revision `d6e83f2a910c` follows deployed, immutable `a7c92e1b640d`.
Apply only after deployment approval; development verification uses disposable
local PostgreSQL databases. This work does not deploy or access Neon/Railway.

## Additive schema

| Table | New nullable reference | Allowed role |
| --- | --- | --- |
| bill | account_ledger_id + account_role | CUSTOMER |
| sales_returns | account_ledger_id + account_role | CUSTOMER |
| purchases | account_ledger_id + account_role | SUPPLIER / PURCHASE_VENDOR |
| purchase_returns | account_ledger_id + account_role | SUPPLIER / PURCHASE_VENDOR |
| rojmel | account_ledger_id + account_role | All three roles, matching legacy source |
| quotations | account_id only | Eligibility remains a future service concern |

Financial references use `MATCH FULL` composite FKs to `account_ledgers(id, role)`,
backed by the new `uq_account_ledgers_id_role`. Both FK actions are RESTRICT.
An explicit pair CHECK also enforces both-NULL/both-populated semantics in SQLite
ORM fixtures, whose FK implementation does not enforce MATCH FULL. Existing
ledger constraints are unchanged. Each new identity reference has one index.
Quotation is non-financial and has no ledger or role column.

Legacy Customer/Party foreign keys and public schemas are unchanged. New fields
are internal, optional, and have no runtime financial authority.

## Deterministic backfill and preservation

Resolve only `(legacy_source, legacy_id)` in `legacy_account_map`; copy the stored
Account or Ledger/role IDs. Use set-based `UPDATE ... FROM`, with no transaction
count/ID pinning, fuzzy matching, per-row commits, or Python row materialization.
All current linked rows are migrated, including inactive historical records.

Preflight rejects missing maps/targets, inconsistent role/account/ledger triples,
unsupported Party classifications, duplicate source mappings/unapproved merges,
unmapped new identities, Rojmel dual identities, and linked return ledger
disagreement. Optional original-document strings remain unchanged. If an original
exists, its normalized number must resolve unambiguously and its mapped ledger
must agree; absent references/standalone returns do not acquire invented parents.
Unexpected pre-existing new columns abort for manual review, rather than being
overwritten or treated as a partially completed migration.

Before backfill, PostgreSQL temporary tables capture the original complete rows
of all six document headers, their five item tables, Item Master, legacy identities,
Accounts, Roles, Ledgers, and maps. Bidirectional `EXCEPT ALL` comparisons after
backfill exclude only the newly added document columns. These server-side exact
comparisons verify counts, legacy IDs, money, dates, status, timestamps, stock,
all balances/directions, and identity/map contents. Temporary data is transaction
scoped and dropped at commit. Plan temporary-disk capacity for large deployments.

**Existing legacy-versus-AccountLedger balance drift is allowed.** Each side must
remain exactly unchanged; no parity repair, posting-service call, transaction
replay, or opening-to-current recomputation is performed. Exact parity is a
**Phase 3B activation gate**, not a Phase 3A mapping prerequisite.

## Legacy writer compatibility

Bill, SalesReturn, Purchase, PurchaseReturn, and Quotation repository updates
clear their transitional reference when the legacy Customer/Party ID changes.
Unchanged identities and metadata-only edits preserve the reference. New records
may leave it NULL. No runtime mapping lookup or financial posting is added.

### Rojmel

The existing one-identity CHECK remains. Populated references must match Customer
versus purchasing-Party role context; identity-less rows cannot have a reference.
Both new fields may remain NULL for legacy writers, even with a selected identity.
Post-backfill reconciliation requires references for every existing linked row.

Approved compatibility exception: when Rojmel's legacy identity changes, its
update service clears both new reference fields before validation/flush. Metadata
or type-only edits retain the reference. This is not provisioning or posting.
It preserves existing Customer/Party switches and identity clearing without
making new fields public inputs. Balance arithmetic remains untouched.

References do not imply posting. Customer Cr Pay/Dr Pay and purchasing-Party
Dr Pay keep their existing effects; Party Cr Pay, Cash/Bank, and JV remain
non-posting. No new type-related database restriction is introduced.

## Locking, rollback, downgrade

Quiesce application writers for deployment. Acquire protected-table locks in
alphabetical order, at the strongest mode required up front:

- Document headers and AccountLedger: ACCESS EXCLUSIVE, required by schema changes.
- Other preserved source/item/stock/map tables: SHARE, allowing
  ordinary reads while preventing writes through reconciliation.

DDL tables necessarily block reads during the migration; this is not an online
zero-downtime migration. Up-front acquisition avoids lock promotion. Lock acquisition
may wait for active transactions; deadlocks or database errors abort the transaction.
Resolve conflicting writers before retrying a failed migration.
PostgreSQL rolls back new schema, references, and Alembic revision atomically.

Before runtime cutover, downgrade removes only Phase 3A columns, constraints, and
indexes. It never changes legacy rows, balances, or map provenance. Upgrade /
downgrade / upgrade is tested. After financial cutover, schema downgrade alone is
not a financial rollback plan.

## Phase 3B prerequisites

Current writers still update Customer/Party balances only. New records may have
NULL references, and legacy identity changes clear existing references without
resolving replacements. These fields must not be consumed as live authority yet.
Before activation, deterministically catch up/revalidate every reference and
require balance parity under a write pause. Any balance reconciliation requires
separate approval and must not replay historical transactions blindly.

New identity provisioning/operational binding, Account/role activity policy,
same-document concurrency protection, authoritative ledger posting and balance
reads, and unsupported legacy classifications remain Phase 3B work. Phase 3A
does not create missing Accounts/Roles/Ledgers or fabricate map provenance.

## Verification

From `backend`, with local PostgreSQL configured:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:BILLING_GSTIN_POSTGRES_TEST='1'
$env:BILLING_BALANCE_CONCURRENCY_TEST='1'
$env:BILLING_ACCOUNT_MIGRATION_TEST='1'
$env:BILLING_ALEMBIC_PYTHON=(Resolve-Path '.\venv\Scripts\python.exe').Path
python -B -m pytest api/tests/test_account_phase_three_postgresql.py -q --tb=short
python -B -m pytest -q --tb=short
```

Historical Phase 2B integrity tests remain pinned to their own revision. The
new full-chain empty-bootstrap test verifies the latest head separately.
