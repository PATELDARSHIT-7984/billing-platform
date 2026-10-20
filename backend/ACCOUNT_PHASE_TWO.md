# Account Phase 2B: prepared, not deployed

Revision `a7c92e1b640d` follows `f2b61d9a430c`. This is a backend-only
identity/ledger backfill. It does not change transaction tables, legacy balances,
stock, PDFs, Customer/Party services, or the transitional GSTIN registry.
No public Account writer or delete endpoint exists.

## Identity contracts

`api/utils/gst_state.py` is the single runtime state mapping. `state_code` is
authoritative; `state` is canonical display text. Friendly names may be resolved
to codes, but a supplied code always determines the name. Codes are two-character
strings. The mapping includes current Indian registration states/UTs and Other
Territory (97), plus historical codes 25 and 28 for legacy registrations. Code 99
is a foreign-country place-of-supply sentinel and is not accepted for an Account
registration state. Historical code 28 has the unambiguous display name
`Andhra Pradesh (Old)`; `Andhra Pradesh` maps to 37.

`HISTORICAL_STATE_CODES` classifies 25/28; `CURRENT_STATE_CODES` excludes them.
Create and explicit state/GSTIN selections require current codes. Historical
responses and unrelated/PAN-only PATCH edits retain compatible saved identity.
Database checks deliberately retain historical compatibility for migrated rows.

Reference: https://docs.ewaybillgst.gov.in/apidocs/state-code.html

AccountCreate requires a selected state when GSTIN is supplied. GSTIN must match
that state's code. Existing normalization and PAN extraction are reused. A valid
GSTIN derives omitted PAN, rejects mismatching PAN, and clears `gstin_pending`.
Without GSTIN, canonical manual PAN and either pending value are allowed.
PAN remains non-unique; nullable GSTIN remains unique when non-null.

AccountUpdate is a partial input, not a complete identity. Future writers MUST
load the saved identity and call `patch.apply_to(current)` before persistence:

* GSTIN-only/state-only changes are checked against the saved counterpart.
* Matching simultaneous changes succeed; changed GSTIN derives omitted PAN.
* Clearing GSTIN preserves omitted PAN/state/pending. Explicit PAN/state clearing
  remains possible when the resulting GSTIN is null.
* Omitted fields are preserved. Valid GSTIN forces pending false.
* Free-text state cannot override the canonical name for an authoritative code.

Future architecture: router -> Account service -> merged validation -> repository
-> commit with controlled uniqueness-error handling. PostgreSQL unique constraints
remain the concurrency authority; no runtime identity table scan was introduced.
DB checks additionally enforce valid state codes, GSTIN/code agreement, and
GSTIN/pending exclusion. Existing GSTIN/PAN and ledger checks remain intact.
Display-name derivation is an application contract, not a database trigger.

## Corrected approved baseline: Neon audit

The original Phase 2B baseline was mistakenly taken from localhost and assumed to
represent UAT. The user-supplied SELECT-only Neon audit instead confirms persisted
revision `f2b61d9a430c`, empty Account/Role/Ledger tables, and no legacy map. The
failed Phase 2B attempt did not persist its schema or backfill. This correction
changes only the failed Phase 2B revision; earlier migrations remain frozen.
No Neon query, remediation, migration, or Railway action is part of this correction.

`alembic/data/phase_2b_approved.json` contains the exact approved raw business
fields supplied from that audit: Customer IDs **1,2,3** and Party IDs **1,2,3,4,5**.
Contact formatting, casing, NULLs, and balance strings are preserved verbatim.
It contains business contact/tax information, no credentials. Treat it as migration
provenance. Do not regenerate it to bypass drift checks.

The migration pins SHA-256
`c67cdf4128e30c15ccb01677766711e00a48d2918876c0cebad91d2d7cf30026`
and verifies exact bytes before parsing, including empty bootstrap. Missing,
unreadable, or altered files abort. `.gitattributes` preserves these bytes across
Windows/Linux checkouts. Ship the JSON alongside the migration. Git-checkout
deployment includes it; any other packaging must explicitly preserve this path.
The path is relative to the migration, independent of the working directory.

The populated branch requires every approved identity, business field, and
reference count exactly. There are no tax-field exceptions or remediation-artifact
requirements. Expected transaction references and header counts:

| Table / reference | Approved rows |
| --- | --- |
| bill.customer_id | Customer 3: 1 |
| purchases.party_id | Party 1: 1 |
| sales_returns.customer_id | 0 |
| purchase_returns.party_id | 0 |
| quotations.customer_id | 0 |
| rojmel.party_id / customer_id | 0 |

No merges: **8 Accounts, 8 roles, 8 ledgers, 8 mappings**. Roles comprise 3 CUSTOMER,
3 SUPPLIER, and 2 PURCHASE_VENDOR. Codes are retained verbatim. P1 remains inactive
in both Account and role; all other identities remain active.

Valid GSTIN determines target PAN, state code, and canonical state name. C3 and P2
retain their raw source state Gujarat (C3 state_code NULL) in the original and
at-backfill snapshots; their targets become Delhi/07 from GSTIN prefix 07.
All other targets use Gujarat/24. All six non-null GSTIN/PAN pairs agree. P4/P5
already have NULL GSTIN/PAN and remain NULL. All eight targets have pending=false;
no pending-tax intention is inferred from nullable tax fields. Any PAN mismatch
or other material source drift aborts.

Opening and current balances are copied independently as Decimal, not recalculated.
Exactly three zero-direction pairs become 0/NULL: P1 opening, P5 opening, and P5
current. Nonzero amounts and directions remain exact. Opening-to-current
initialization belongs only to future brand-new Account creation.

Strict empty bootstrap requires both legacy identity tables, all transaction
headers/lines, and all Account targets to be empty. It creates schema only.
Every other unapproved populated dataset aborts before backfill. Locks cover source,
target, and transaction tables. PostgreSQL transactional DDL/data roll back together
on failure, including failures after target inserts. Reconciliation verifies target
identities, activity, balances, counts, and unchanged source/transaction rows.

## Historical localhost remediation utility

`scripts/remediate_account_tax.py` remains unchanged for its original localhost
P4/P5/P10 dataset at revision `c4a9e7120d35`. Its tests use a separate historical
fixture. **Do not run it against Neon.** Neon has no P10 and its P4/P5 tax fields are
already NULL; neither remediation nor an audit artifact is required here.
The earlier `e9a41c8d720b` registry migration and its validation remain unchanged.

## Future deployment sequence (NOT executed)

1. Obtain deployment approval; verify destination and persisted revision.
2. Back up and verify recoverability before migration; pause legacy writes.
3. Confirm the frozen source snapshot and exact reference counts still match.
4. From `backend`, run with the deployment interpreter:

```powershell
.\venv\Scripts\python.exe -B -m alembic upgrade head
```

Expected Neon transition: `f2b61d9a430c` -> `a7c92e1b640d`. No `account_tax_audit`
argument or remediation step is needed. A fresh empty database can traverse the
complete unchanged earlier chain before applying Phase 2B.

5. Verify all four target counts equal 8, role split 3/3/2, balances and state
   transformations, and unchanged source/transaction rows and foreign keys.
6. Smoke-test the existing application before resuming writes.

## Durable map and downgrade

`legacy_account_map` has source/id composite primary key, target Account/role/
ledger IDs, original code, migration revision, timestamp and JSONB snapshot.
Account ID is not unique. Composite foreign keys ensure the target ledger belongs
to exactly the mapped Account/role; deletes/updates are RESTRICT. The extra ledger
unique triple supports that foreign key. Original source fields, at-backfill
fields and target fingerprints are distinguishable. Both source snapshots retain
the exact approved raw Neon fields; no remediation metadata is fabricated.

Keep the map through final legacy cleanup. It is provenance, not a replacement
for immutable document snapshots or future transaction foreign keys.

Downgrade is only intended before Account write cutover. It locks targets and
refuses extra targets, changed target rows or unexpected mapping provenance.
It removes backfilled targets/map/schema additions only. It never changes legacy
rows or restores invalid tax data. A fresh empty bootstrap also downgrades safely.
Do not use downgrade as a substitute for post-cutover recovery.

## Verification

All mutation testing uses disposable PostgreSQL databases via the existing opt-in
fixture. No UAT remediation or migration is performed by the test suite.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:BILLING_GSTIN_POSTGRES_TEST='1'
$env:BILLING_BALANCE_CONCURRENCY_TEST='1'
$env:BILLING_ACCOUNT_MIGRATION_TEST='1'
$env:BILLING_ALEMBIC_PYTHON=(Resolve-Path '.\venv\Scripts\python.exe').Path
python -B -m pytest -q --tb=short
```

Historical migration tests pin their own revision so their synthetic, nonapproved
legacy data cannot accidentally enter the strict Phase 2B backfill. Phase 2B tests
cover empty bootstrap through the full chain and the populated f2-to-a7 path with
the approved business baseline and
representative transaction documents matching every reference count.

Deferred: UAT execution; transaction FKs/cutover; Account public API/service;
new-account ledger initialization; frontend state/pending/PAN controls; soft-delete
UI/API; Dashboard migration; registry/legacy-table retirement; simultaneous
SUPPLIER/PURCHASE_VENDOR policy. No commit, push or PR is part of this work.
