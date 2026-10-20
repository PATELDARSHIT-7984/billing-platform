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

## Approved baseline

`alembic/data/phase_2b_approved.json` is an immutable business-field snapshot of
the reviewed Phase 2A dataset. It contains business contact/tax information, no
credentials. Treat it as migration provenance, not a fresh runtime export.
Ship this file with the migration and do not regenerate it to bypass drift checks.
The migration pins SHA-256
`afad1de423c944b1fc12db8a037c8a814ce73b7b1d5ece0a5d7cdad39be55e57`
and verifies bytes before parsing, even for empty bootstrap. Missing/unreadable or
modified files abort. The repository `.gitattributes` preserves these exact bytes
across Windows/Linux checkouts. Commit the JSON alongside the migration: the
documented Git-checkout deployment then includes it. No container/package manifest
is defined; other packaging must explicitly preserve this file and directory.
Its path is relative to the migration, not the shell working directory.

The populated-data branch requires exactly Customer IDs 1,3,4,5 and Party IDs
1,2,3,4,5,6,7,10,11,12, with exact approved business fields, codes, balances,
activity and reference counts. Only P4/P5/P10 tax values may differ from that
snapshot, and they MUST already be NULL after approved remediation.

No merges: all 14 sources become 14 Accounts, 14 roles, 14 ledgers, 14 mappings.
C1/P1, C5/P6, C5/P10 remain separate. Existing codes are retained verbatim.
Activity copies independently to Account and role. No inactive source is omitted.

Valid legacy GSTIN determines target PAN, state code and canonical state name.
C3's approved target is GSTIN `27AAACR5055K1Z7`, PAN `AAACR5055K`, state code 27,
Maharashtra. Its source Customer remains unchanged. Any new PAN mismatch or
other material drift aborts. Without GSTIN, recognizable legacy state determines
the code; unknown nonempty state aborts. P4/P5/P10 receive pending=true; others false.

Opening and current balances are copied independently as Decimal. All 16 audited
zero amount/direction pairs become 0/NULL. Nonzero values/directions never change.
Opening-to-current initialization belongs only to future brand-new creation.

The explicitly approved fresh-bootstrap exception requires BOTH legacy identity
tables and ALL transaction headers/lines to be empty, as well as empty Account
targets. It creates schema only, with zero mappings and no remediation artifact.
Any partially populated or otherwise unapproved dataset aborts.

## Remediation tool (separate execution approval required)

From `backend`, using an interpreter with project dependencies:

```powershell
python -B -m scripts.remediate_account_tax
```

This is dry-run by default and uses a read-only transaction. To apply, only after
separate approval and after verifying the configured destination:

```powershell
python -B -m scripts.remediate_account_tax --apply --audit-file <new-protected-audit-path.json>
```

The utility checks revision `c4a9e7120d35` and exact original P4/P5/P10 GSTIN/PAN,
locks the revision/Party tables, exports a timestamped pre-mutation artifact, and
updates only those six tax fields in one transaction. It does not change source
timestamps. A changed/missing record, wrong revision, existing/unwritable artifact,
or DB failure aborts. Repeated apply is deliberately refused.

Artifact creation is exclusive, flushed and fsynced BEFORE the update. Retain it
securely: it contains original business tax values. It records mutation intent,
not proof of commit; an artifact can survive a rolled-back operation. The CLI
reports commit only after the transaction succeeds. No credential-bearing error
or connection URL is printed.

## Future deployment sequence (NOT executed on UAT)

1. Obtain separate approval, verify database destination and backup/recovery readiness.
2. Run dry-run remediation and review the three records.
3. Run explicitly approved apply and retain its artifact.
4. Freeze legacy writes; reconcile against the approved snapshot again.
5. Run the full migration chain with the artifact, using the Alembic interpreter:

```powershell
.\venv\Scripts\python.exe -B -m alembic -x account_tax_audit=<audit-path.json> upgrade head
```

The earlier registry migration is unchanged. Its preflight must succeed before
Phase 1 or Phase 2B can execute. For populated data the new revision requires the
exact artifact contents and stores its SHA-256/timestamp in remediated mappings.

The backfill locks legacy/target/transaction tables, verifies the entire approved
business snapshot and per-identity reference counts, and rejects preexisting
Account targets. PostgreSQL transactional DDL/data roll back together on failure.
Reconciliation verifies all target identities, activities, ledgers, counts, and
unchanged legacy and transaction rows before commit. Expected header totals:
Bill 8; Sales Return 2; Purchase 15; Purchase Return 2; Quotation 2; Rojmel 1.

## Durable map and downgrade

`legacy_account_map` has source/id composite primary key, target Account/role/
ledger IDs, original code, migration revision, timestamp and JSONB snapshot.
Account ID is not unique. Composite foreign keys ensure the target ledger belongs
to exactly the mapped Account/role; deletes/updates are RESTRICT. The extra ledger
unique triple supports that foreign key. Original source fields, at-backfill
fields and target fingerprints are distinguishable. Invalid pre-remediation tax
values remain in the original snapshot and are linked to the audit artifact hash.

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
cover the full chain separately with the approved business baseline and
representative transaction documents matching every reference count.

Deferred: UAT execution; transaction FKs/cutover; Account public API/service;
new-account ledger initialization; frontend state/pending/PAN controls; soft-delete
UI/API; Dashboard migration; registry/legacy-table retirement; simultaneous
SUPPLIER/PURCHASE_VENDOR policy. No commit, push or PR is part of this work.
