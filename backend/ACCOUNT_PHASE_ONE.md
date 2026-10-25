# Account Phase 1: additive foundation

This phase adds `accounts`, `account_roles` and `account_ledgers`. It exposes no
Account API and performs no identity or transaction backfill. Customer/Party
remain the operational sources. Do not write production Accounts independently
of those sources during coexistence.

## Identity and roles

Account has one identity, unique caller-supplied `account_code`, optional GSTIN,
optional PAN and nullable contact fields. Account has no balance columns.
`AccountRoleCode` is the single new role definition. It is separate from legacy
PartyType, whose wire values and behavior are unchanged.

AccountRole is unique on `(account_id, role)`. AccountLedger has a stable ID,
the same unique pair, and a composite FK to that exact AccountRole. A CUSTOMER
role cannot support a SUPPLIER ledger. Deletion/update restrictions protect an
existing ledger. There is no cascading ledger deletion.

One Account can have CUSTOMER and SUPPLIER balances of 10,000 Debit and 6,000
Credit. They are independent; no net balance is stored on Account. Future creation
services must create each financial role and its ledger in the same transaction.
The FK enforces ledger-to-role existence; it does not force an unused role to
already have a ledger. No automatic ledger creation or posting service exists yet.

Account inactivity will prohibit all new transactions; role inactivity will
prohibit only that role. Historical reversals must remain possible. Phase 1 stores
those flags but does not alter existing transaction enforcement.

## Validation contracts

AccountCreate requires a code, name and at least one distinct canonical role.
Each role input accepts only its opening amount, direction and remark. Clients
cannot provide current balances. Account code generation is deferred; legacy
customer/party codes are not converted.

Contact columns remain nullable. Existing Customer-only requirements (mobile,
address, city and state, with current field validation) belong to future role-aware
services; Phase 1 does not impose them on Suppliers. Email syntax and supplied
field lengths are validated in the shared identity schema.

The existing GSTIN helper is reused. Its unchanged pattern is now a shared
constant. New PAN normalization validates five letters, four digits and one
letter. `pan_from_gstin` is the new Account derivation helper. Legacy endpoint
PAN validators and their uniqueness behavior are unchanged.

With GSTIN, PAN is derived if omitted/null and must match if provided. Without
GSTIN, valid manual PAN or null is allowed. PAN is not unique on Account.

AccountUpdate is an identity-only PATCH. A future writer **must call
`patch.apply_to(current_identity)` before writing** so PAN-only changes are checked
against the saved GSTIN. Changed GSTIN derives a new PAN; cleared GSTIN preserves
the previous PAN unless the patch explicitly changes/clears PAN. Role edits are
not part of this PATCH foundation.

Opening/current money uses Numeric(18,2), is finite and nonnegative. Zero requires
NULL direction; positive amounts require Debit or Credit. Both schemas and DB
checks enforce this. Legacy zero/Credit and posting functions are unchanged.

## Database integrity and portability

PostgreSQL checks enforce canonical GSTIN, canonical PAN and the matching embedded
PAN. Tax columns intentionally use unbounded VARCHAR plus exact-format checks:
VARCHAR(15/10) can silently truncate excess trailing spaces before checks run.
The checks enforce the effective lengths while rejecting malformed direct SQL.
API input normalization still accepts lowercase/outer-space spellings.

SQLite metadata tests enforce uniqueness, role/ledger FKs, amount/direction and
GSTIN/PAN correspondence. PostgreSQL regex-format checks are PostgreSQL-only;
the real PostgreSQL suite verifies those direct-SQL protections. The migration
freezes the current patterns/role values rather than importing mutable validators.

Indexes consist of PK/UNIQUE indexes and `(role, account_id)` on account_roles.
No redundant ID/GSTIN indexes, PAN index or balance-ranking index is added. GSTIN
lookup is keyed, role/ledger lookup uses the unique account/role pair. There is no
list-loading service, N+1 request path or new dependency.

## Migration and transition

Revision `f2b61d9a430c` follows `e9a41c8d720b` and only adds the three tables,
constraints and one explicit role-filter index. Its downgrade removes these new
tables (and any Phase 1 test data), leaving legacy tables/registry untouched.
Test the round trip on disposable PostgreSQL, never UAT for this phase.

The temporary GSTIN registry remains unchanged. `accounts.gstin` will become the
sole identity uniqueness authority only after reviewed backfill and cutover.
There is deliberately no cross-table Account/registry write synchronization yet,
and therefore no public Account write authority.

Known invalid GSTINs on Party IDs 4, 5 and 10 still block the registry migration.
No UAT record is changed by this phase. Customer 1/Party 1 identity review/merge,
all other backfill, transaction FKs, Rojmel ledgers, frontend multi-role forms,
GSTIN-to-PAN autofill, neutral-balance UI, Dashboard migration, registry retirement
and legacy table retirement are deferred. Simultaneous SUPPLIER/PURCHASE_VENDOR
business policy remains undecided; the foundation does not prohibit it.

## Tests

From `backend`, with the existing test interpreter and Alembic interpreter:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:BILLING_GSTIN_POSTGRES_TEST='1'
$env:BILLING_ALEMBIC_PYTHON=(Resolve-Path '.\venv\Scripts\python.exe').Path
python -B -m pytest api/tests/test_account_phase_one.py api/tests/test_account_phase_one_postgresql.py -q
```

The existing guarded PostgreSQL fixture creates and drops disposable
`billing_test_bootstrap_gstin_*` databases. It never migrates UAT. Concurrency tests
have no production service to call; they assert SQLSTATE 23505 and the expected
unique constraint, then verify exactly one row. Future public writers must map
these database errors to the established controlled API response.
