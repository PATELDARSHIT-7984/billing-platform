# Account Management backend foundation

Customer and Party retain their existing tables, IDs, foreign keys, validation,
and soft-delete behavior. Customer running balances now include Bills, Sales
Returns and explicitly Customer-linked Rojmel receipts/refunds.

## Customer balances

Create accepts `opening_balance` (nonnegative Decimal, at most 18 digits with
two decimal places) and `balance_type` (`Credit` or `Debit`). Defaults are zero
and Credit. Responses include those fields plus `current_balance` and
`current_balance_type`; current fields are output-only. Following existing
Pydantic behavior, extra input keys are ignored and cannot overwrite them.

Amounts use `Numeric(18, 2)`, with direction stored separately, just like Party:
Credit is positive, Debit is negative. Zero current balance uses Credit.

Create sets current amount to opening amount. An opening edit computes:

```text
new signed current = old signed current + new signed opening - old signed opening
```

For example, 1000 Credit opening and 1500 Credit current become 1200 Credit
opening and 1700 Credit current when opening is changed to 1200 Credit.

The existing Customer PUT still requires its normal customer fields. Newly
introduced opening fields are only applied when supplied: older clients cannot
accidentally reset balances by omitting them. Null/negative/non-finite amounts
and invalid directions are rejected.

## Transaction posting

Customer Debit means receivable (To Take); Credit means advance/amount owed to
the Customer (To Pay). Posting uses persisted backend totals, rounded to cents:

| Transaction | Signed Customer effect |
|---|---|
| Active Bill | Negative grand total |
| Active Sales Return | Positive grand total |
| Customer Rojmel Cr Pay | Positive net amount (receipt) |
| Customer Rojmel Dr Pay | Negative net amount (refund/payment out) |
| Quotation | Zero |

Updates replace the old effect with the new effect, combining them into one
delta per Customer. Switching Customer reverses the old account and posts the
new account. Unchanged totals/accounts cause no balance write. Delete reverses
once, using existing document deletion rules. These writes flush inside the
existing transaction; document, stock and account changes commit or roll back
together. Existing stock, tax and saved-price calculations are unchanged.

Rojmel retains optional `party_id` and gains optional `customer_id`, with a real
foreign key. They are mutually exclusive (service validation and DB constraint);
neither is still allowed. Customer linkage accepts only Cr Pay/Dr Pay. New or
switched Customer links require an active Customer; historical adjustments and
reversals can reach inactive Customers. To switch account sources, explicitly
clear the old ID as well as setting the new ID. Party Dr Pay subtracts net amount
for both Supplier and PURCHASE_VENDOR; other Party Rojmel directions retain
their existing non-posting behavior.

Supplier and Purchase Vendor share Party opening/current balances, Purchase
positive-total posting, Purchase Return negative-total posting, update deltas
and reassignment. Purchase deletion remains unavailable for both types;
Purchase Return and Rojmel deletion reverse once. Blank Vendor GSTIN is valid;
supplied GSTIN retains existing Party validation. A read-only local audit at
hardening found zero Purchase Vendor records/payments requiring reconciliation.

Dashboard `/dashboard/summary` now supplies numeric `customer_receivable`
(Debit balances) and new `customer_credit` (Credit balances). SQL SUM/GROUP BY
includes inactive Customers, matching Party obligations. Zero contributes
nothing. These are current balances, independent of the dashboard date range.
Recent Rojmel activity also resolves Customer names with a SQL join.

Example: 1000 Debit opening, 5000 Sale, 1500 return, 2000 receipt and 3000
receipt produce 6000 Debit, 4500 Debit, 2500 Debit, then 500 Credit.

## Classification and listing

Party `party_type` accepts:

| Wire/storage value | Future UI label | Source |
|---|---|---|
| `Supplier` | Supplier | Party |
| `PURCHASE_VENDOR` | Purchase | Party |
| `Customer` | Legacy compatibility only | Party |

Keep the existing `Supplier` spelling for compatibility. No Party row is
rewritten. Existing clients can continue their legacy Customer-type Party CRUD;
the future unified flow must create Customers through `/customers/`, never by
using the legacy Party classification.

GSTIN remains optional for Party, including Purchase Vendor. Supplied values
reuse existing normalization, length validation and uniqueness across active
and inactive Parties. Customer retains its stricter GSTIN format/PAN rules.

```text
GET /customers/?search=Patel&page=1&page_size=20
GET /parties/?party_type=Supplier&search=Traders&page=1&page_size=20
GET /parties/?party_type=PURCHASE_VENDOR&page=1&page_size=20
```

With `page`, the existing `HistoryPage` envelope contains `items`, `total`,
`page`, `page_size`, `total_pages`. Without `page`, responses remain arrays and
accept `skip`/`limit`. Page size is 1–200; limit is 1–500; skip is nonnegative.
`page` overrides skip/limit for fetching. An omitted Party type includes all
active classifications, preserving transaction callers.

Both repositories filter in SQL before count/offset/limit. Customer orders by
name then ID; Party by descending ID. Array listing uses one query; metadata
listing uses count plus page (two queries), with no per-row lookups. No new
index was added: a standalone low-cardinality type index lacks measured benefit.

## Migration

Revision `b8f2d9a73106`, following frozen baseline `7414692a3849`, adds four
Customer columns: `opening_balance`, `current_balance`, `balance_type`, and
`current_balance_type`. Non-null server defaults backfill zero/Credit and keep
older inserts valid. Party classification needs no column change or backfill.

Revision `c4a9e7120d35` follows `b8f2d9a73106`. It adds the Rojmel Customer
foreign key and exclusive-account constraint, then adds existing active Bill
and Sales Return effects to Customer balances using SQL. Inactive documents
are excluded; inactive Customers retain their obligations. Historical unlinked
receipts cannot be inferred and require reconciliation before relying on the
result as a settled receivable. Re-running `upgrade head` does not post twice.

The full chain is `7414692a3849 -> b8f2d9a73106 -> c4a9e7120d35`.
The frozen baseline is unchanged. Downgrading the posting revision reverses
document effects, but refuses to proceed while Customer-linked Rojmel records
exist, preventing loss of payment attribution.

From backend, with the intended DATABASE_URL configured:

```sh
alembic upgrade head
```

Apply this migration before running the new application against an existing
database. Development data was audited read-only, not migrated by this task.
Downgrade removes the new balance columns and therefore discards their values;
its round trip was checked only on a disposable database.

## Phase 2

Future UI constants can map CUSTOMER to the Customer API, SUPPLIER to Party's
`Supplier`, and PURCHASE_VENDOR to Party's `PURCHASE_VENDOR`. Retain source and
ID explicitly. Customer/Party IDs are separate identities. No frontend changes
are included.

## Performance and limitations

Posting adds one Customer lookup and one UPDATE per nonzero affected account
(up to two on account switches). Rojmel also validates its Customer relation.
Dashboard totals add one grouped aggregate query; no per-Customer queries or
full-table Python filtering are used. No dependencies were added.

Balance mutations and opening edits now fetch the affected account by primary
key with PostgreSQL `FOR NO KEY UPDATE` (SQLAlchemy
`with_for_update(key_share=True)`). This serializes balance writers while
remaining compatible with document foreign-key checks. `populate_existing()`
refreshes previously cached values after the lock is acquired. Locks last until
the existing transaction commits or rolls back; no separate connection or
manual unlock is used.

Account switches lock IDs in ascending order within each table; mixed Rojmel
switches always process Customers before Parties. Locked SELECT replaces the
existing lookup, adding no query per posting. Party opening edits also avoid
the old second balance lookup. No table-level locking is introduced.

Separate PostgreSQL connections verify actual blocking, fresh values after
waiting, both posting effects, opening edits, and rollback release for Customer,
Supplier and Purchase Vendor. SQLite regression tests do not prove row locks.
This protects account balances; it does not add document/stock concurrency
control or retries for unrelated database deadlocks. Simultaneous edits of the
same transaction document still require document-level concurrency control.

## Verification

From the repository root:

```powershell
python -B -m pytest backend/api/tests -q -p no:cacheprovider --tb=short
```

The opt-in migration round trip creates and drops its own disposable PostgreSQL
database. It never migrates the configured development database:

```powershell
$env:BILLING_ACCOUNT_MIGRATION_TEST = '1'
$env:BILLING_ALEMBIC_PYTHON = (Resolve-Path 'backend/venv/Scripts/python.exe').Path
python -B -m pytest backend/api/tests/test_customer_accounting_migration.py -q -p no:cacheprovider --tb=short
```

Run the concurrency checks separately (they create/drop their own database):

```powershell
$env:BILLING_BALANCE_CONCURRENCY_TEST = '1'
$env:BILLING_ALEMBIC_PYTHON = (Resolve-Path 'backend/venv/Scripts/python.exe').Path
python -B -m pytest backend/api/tests/test_balance_concurrency.py -q -p no:cacheprovider --tb=short
```

Concurrency verification: 12 passed. Accounting migration and migrated-
application bootstrap were run separately on disposable PostgreSQL databases:
one passed each. Backup/restore was not rerun in this hardening task. No
development migration was executed.

Final full backend: 801 passed, 0 failed, 15 opt-in skips (the 12 concurrency
cases plus migration, bootstrap and backup checks). This preserves the previous
793 passing tests and adds eight Supplier/Purchase Vendor parity cases. The full
run includes Customer accounting (34), Account Foundation (38), Dashboard (39),
Purchase/returns, Party/Rojmel, and the shop workflow.
