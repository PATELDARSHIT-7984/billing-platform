# Project review: CRUD APIs and business logic

Review date: 2026-09-12. This is a review, not a code fix.

Scope: backend entry points, all 12 API modules and their service flows, relevant schemas/repositories/models, migrations, existing tests, frontend routes, API clients, transaction forms, calculations, and dashboard/report implementation. This is not an exhaustive visual or browser interaction audit.

Validation used an isolated SQLite in-memory database with `api.main.app` and a dependency override. The configured PostgreSQL billing database was not accessed. Concurrency and fresh PostgreSQL migration behavior were assessed from code, not reproduced against PostgreSQL.

## Project map

- Frontend: React + Vite, React Router, Axios, reusable form/table components, local draft storage, PDF generation.
- Backend: FastAPI routes -> Pydantic schemas -> services and validation -> SQLAlchemy repositories -> PostgreSQL. Repositories generally flush; services commit.
- Master records: customers, supplier parties, inventory items, banks, done-by people, company settings.
- Transactions: sales bills, purchases, sales returns, purchase returns, quotations, Rojmel receipts.
- Dashboard values are hardcoded and Reports is a placeholder; they are not working financial reports.

## Main business logic

| Operation | Current stock effect | Other behavior |
| --- | --- | --- |
| Create sale | Subtract sold quantity | Uses current ItemMaster sale price and tax percentages |
| Update sale | Add old quantity, subtract new quantity | Rebuilds lines and snapshots using current master data |
| Delete sale | Restore sold quantity | Soft delete |
| Create purchase | Add purchased quantity | Can create an item; overwrites purchase price and last purchase date |
| Update purchase | Subtract old quantity, add new quantity | Rejects resulting negative stock |
| Delete purchase | No exposed endpoint | Service explicitly prohibits deactivation |
| Create sales return | Add returned quantity | Does not verify original sales transaction |
| Update/delete sales return | Apply difference / remove returned stock | Checks whether stock is available to reverse |
| Create purchase return | Subtract returned quantity | Checks stock, but not the original purchase |
| Update/delete purchase return | Apply difference / restore returned stock | Soft delete |
| Quotation CRUD | No stock effect | Computes discounted totals; deletion is permanent |
| Rojmel CRUD | No inventory effect | Computes net amount and summary; deletion is permanent |

Duplicate item quantities are grouped for several stock checks, and updates generally apply stock differences. These are useful safeguards for sequential requests. They do not prevent concurrent updates from overwriting one another.

## Findings, ordered by impact

### 1. High: bill detail and update response contracts are broken — reproduced

APIs: `GET /bills/{bill_id}`, `PUT /bills/{bill_id}`.

The GET route declares `BillResponse`, but its service returns `{bill, items}`. The PUT route declares `BillDetailResponse`, but its service returns a bare Bill object. Both returned HTTP 500 for valid existing bills. The PUT committed its changes before response validation failed: a changed remark was present in the database despite HTTP 500. This causes misleading save failures and prevents normal detail/edit/PDF flows.

Evidence: `backend/api/router/bill.py:15`, `:23`; `backend/api/services/bill.py:1077`, `:1105`, `:1545`; `frontend/frontend/src/pages/SalesEntry.jsx:156`.

Fix: agree on a single detail response shape, return it consistently, and test actual HTTP serialization plus persisted state.

### 2. High: sales form prices, discounts, and GST switch are silently ignored — reproduced

APIs: `POST /bills/`, `PUT /bills/{bill_id}`.

SalesEntry sends `is_gst`, item `rate`, `disc_percent`, and tax percentages. Bill schemas accept only item ID/quantity plus the interstate flag; unknown fields are silently ignored. The service always uses ItemMaster prices/taxes and sets discount to zero. A request with GST off, price 50, and a 10% discount saved a total of 118 when the master price was 100 with 18% tax. The UI's expected total would be 45.

Updates also reprice historical invoices using today's master price, even if the intended change was only a remark. Shipping uses frontend `ship_state` versus backend `shipping_state`, so that value is also dropped.

Evidence: `frontend/frontend/src/pages/SalesEntry.jsx:421`; `backend/api/schema/bill_item.py:4`; `backend/api/schema/bill.py:8`; `backend/api/services/bill.py:231`, `:1105`.

Fix: define the supported pricing/discount/GST contract, preserve historical line values on unrelated edits, and reject unsupported fields rather than silently discarding them.

### 3. High: Rojmel net amounts can be overwritten independently — reproduced

API: `PATCH /rojmel/{rojmel_id}`; affected output: `GET /rojmel/summary`.

`net_amount` is writable in the update schema. The service copies it directly and only recalculates when amount or tax percentages change. `{"net_amount":"99999.00"}` returned 200 and changed a receipt with amount 100 and zero tax to net amount 99999. Summary aggregation uses the stored net amount.

Evidence: `backend/api/schema/rojmel.py:62`; `backend/api/services/rojmel.py:104`; `backend/api/repository/rojmel.py:92`.

Fix: make net amount output-only and always derive financial totals on the server.

### 4. High: returns are not linked to original transactions — sales return reproduced

APIs: POST and PUT on `/sales-returns/` and `/purchase-returns/` (PUT uses `/{id}`); related original bill/purchase edits and sale deletion.

Original invoice/bill numbers are optional strings. Validation checks customer/party and item existence, not document ownership, original item quantities, historical price/tax, or cumulative returned quantity. A sales return for 100 units against `NONEXISTENT` was accepted and increased stock from 9 to 109. Purchase returns similarly rely on available inventory, so inventory bought from another supplier can satisfy the check.

There is no enforceable dependency preventing changes to the original transaction after returns. If unlinked legacy returns are intentional, they need a separately defined adjustment workflow and controls.

Evidence: `backend/api/services/sales_return.py:398`, `:566`; `backend/api/services/purchase_return.py:577`; corresponding validation modules and original-document schema fields.

Fix: link returns to original document lines; enforce remaining returnable quantity, ownership, and applicable historical amounts within the same transaction.

### 5. High: concurrent stock changes can overwrite each other — code finding

APIs: stock-changing POST/PUT/DELETE operations on bills and both return modules, and POST/PUT purchases.

Services read `current_stock`, calculate a Python value, and assign it. There is no row locking, optimistic version check, or conditional atomic stock deduction. Two requests can validate the same available stock, both succeed, and persist a final stock value reflecting only one operation. Concurrent deletes can also pass the active-record check before either commits.

Evidence: `backend/api/services/bill.py:562`, `:1105`; `backend/api/services/purchase.py:291`; `backend/api/services/sales_return.py:862`; `backend/api/services/purchase_return.py:844`; item repository lookups.

Fix: lock affected items and transaction records consistently or use atomic guarded updates, keeping validation and writes in one transaction. Add PostgreSQL concurrency tests.

### 6. High: party current balances are disconnected from transactions — reproduced at creation

APIs: `POST /parties/`, `PUT /parties/{party_id}`, `GET /parties/`, `GET /parties/{party_id}`, purchase/return writes and Rojmel CRUD.

A new party with opening balance 500 Debit returned current balance 0 Credit. Creation never initializes current balance from opening balance. The migration backfills existing parties only. The repository's `set_party_current_balance` has no service callers, and purchase, return, and receipt flows do not update it.

Evidence: `backend/api/services/party.py:47`; `backend/api/model/party.py`; `backend/api/repository/party.py:95`; migration `7414692a3849_add_party_current_balance_fields.py:44`.

Fix: define signed debit/credit posting rules and derive balances from a ledger, or maintain them transactionally on create/update/reversal. Cover changes of party and opening balance.

### 7. High if the API is reachable by others: no application authentication or authorization

APIs: all business endpoints, including deletes and company/bank settings.

Neither backend application nor route dependencies implement user identity or permission checks. The only common dependency is database access. The isolated API accepted all demonstrated requests without credentials. CORS is not an access-control substitute. An external gateway could add access protection, but none is defined in this project.

Evidence: `backend/api/main.py:26`; `backend/api/dependencies/dependencies.py`; all router modules.

Fix: authenticate callers and authorize financial mutations and administrative operations before exposing the application beyond a trusted local environment.

### 8. Medium: GST-only edits leave line amounts inconsistent — reproduced for sales return

APIs: `PUT /purchases/{purchase_id}`, `PUT /sales-returns/{sales_return_id}`, `PUT /purchase-returns/{record_id}`.

Changing only `is_gst` recalculates header totals but discards recalculated line results. A return changed to non-GST returned grand total 10000 while its line amount remained 11800. Purchases and purchase returns use the same pattern. Non-GST creation also saves zero tax rates, so enabling GST later cannot reconstruct the intended original rates without a line payload.

Evidence: `backend/api/services/purchase.py:794`; `backend/api/services/sales_return.py:1419`; `backend/api/services/purchase_return.py:1371`.

Fix: update line amounts and applied tax fields together with header totals; explicitly define how rates are supplied when enabling GST.

### 9. Medium: customer updates bypass create validation — existing tests fail

API: `PUT /customers/{customer_id}`.

CustomerUpdate lacks the mobile/GSTIN/PAN validators used on create, and the update service skips uniqueness validation. Tests showed invalid mobile, GSTIN, and PAN values accepted with 200; duplicate GSTIN/PAN updates raised database IntegrityError instead of a controlled validation response. In the full app, the generic handler turns those exceptions into HTTP 500.

Evidence: `backend/api/schema/customer.py:51`; `backend/api/services/customer.py:88`; failing customer tests.

Fix: share field validation between create/update and check uniqueness excluding the current customer; handle database conflicts as well.

### 10. Medium: list routes silently ignore search and pagination

APIs: `GET /bills/`, `GET /customers/`, `GET /item-master/`.

These route functions declare no search/skip/limit inputs and call services with defaults. Frontend clients send search and limit=500, but the backend ignores them and returns the default first 100 records. A nonexistent bill search returned an existing bill. Customer search/pagination tests also failed. Items/customers past the first page can be unavailable in transaction selectors.

Evidence: `backend/api/router/bill.py:19`; `backend/api/router/customer.py:19`; `backend/api/router/item_master.py:22`; frontend bill/customer/item services.

Fix: expose validated query parameters and implement a consistent page/count contract, including frontend pagination or remote lookup.

### 11. Medium: Rojmel numeric and null validation is incomplete

APIs: `POST /rojmel/`, `PATCH /rojmel/{rojmel_id}`.

Amount and tax percentage fields have decimal-place constraints but no nonnegative/range constraints. Update accepts explicit nulls for required database values and calculation inputs. Those values are copied before calculations/flush, allowing negative receipt totals or causing server errors. Creation also requires `receipt_no` even though the server discards and generates it.

Evidence: `backend/api/schema/rojmel.py:16`, `:43`; `backend/api/services/rojmel.py:52`, `:104`.

Fix: define allowed amount signs per transaction type, bound percentages, disallow nulls for required fields, and remove generated fields from input schemas.

### 12. Medium: generated document numbers are not concurrency-safe

APIs: `POST /bills/`, `POST /quotations/`, `POST /sales-returns/`, `POST /purchase-returns/`, `POST /rojmel/`.

Number generation reads existing rows and increments a value. Concurrent creates can select the same number; unique constraints may prevent duplicates, but a caller then receives a server error rather than a reliable allocation. Bill creation scans all invoice numbers. Rojmel permanently deletes receipts and generates from the last surviving row, so deleting the latest receipt permits number reuse. Changing effective date does not update or validate the financial year embedded in the receipt number.

Evidence: `backend/api/services/bill.py:193`; `backend/api/services/quotation.py:12`; return `_next_number` functions; `backend/api/services/rojmel.py:19`, `:104`, `:137`; `backend/api/repository/rojmel.py:28`.

Fix: use transactional number allocation, retain cancelled numbers, and define document-date/number immutability.

### 13. Medium: frontend and backend rounding differ

APIs: POST/PUT purchases, quotations, and both return types; frontend previews also affect sales.

Frontend `Math.round` and backend Python `round` disagree at even-number-plus-0.5 boundaries: a non-taxable total 100.50 previews as 101 but backend computes 100. The active SalesEntry uses the purchase-style whole-rupee calculator while bill services retain two decimals. Monetary values also use float across most transaction services/models.

Evidence: `frontend/frontend/src/utils/calculations.js:43`; `frontend/frontend/src/pages/SalesEntry.jsx:245`; `backend/api/services/purchase.py:18`; quotation/return total functions; bill total function.

Fix: choose one explicit monetary rounding policy, use decimal arithmetic server-side, and test shared boundary examples against frontend previews.

### 14. Medium: older purchase edits overwrite latest item purchase metadata

APIs: `POST /purchases/`, `PUT /purchases/{purchase_id}`.

Every submitted line overwrites ItemMaster purchase_price and last_purchase_date. Editing an older purchase after a newer purchase therefore makes the master represent the older transaction. Removing an item from an edited purchase does not rebuild its latest purchase metadata; date-only edits do not update it either.

Evidence: `backend/api/services/purchase.py:459`, `:775`.

Fix: derive latest purchase metadata from the latest eligible transaction, or explicitly define it as last-edited data rather than latest purchase data.

### 15. Medium: backend startup and database provisioning are inconsistent

Affected availability: bank, done-by, Rojmel, and company-profile APIs; fresh deployment generally.

`backend/main.py` and `backend/api/main.py` define different FastAPI apps. The former omits four routers and runs create_all against the configured database at import time. Starting `main:app` versus `api.main:app` therefore changes API availability.

The initial Alembic upgrade creates Rojmel with a foreign key to parties but does not create parties. The subsequent migration alters existing business tables rather than establishing the missing baseline. Customer/party services call PostgreSQL sequences whose creation is absent from the migrations. A preconfigured local database can hide these provisioning gaps. This finding is static; no migrations were run against your database.

The database connection credentials are also hardcoded in source.

Evidence: `backend/main.py:32`; `backend/api/main.py:46`; `backend/alembic/versions/1e7ac6ee08ff_initial_database_schema.py:66`; `backend/alembic/versions/0adace7af290_sync_models_with_database.py`; customer/party repository sequence functions; `backend/api/config/database.py:4`.

Fix: establish one documented entry point, repair a fresh-database migration path including sequences, and load deployment configuration from the environment.

## Coverage and remaining product gaps

- Existing pytest run: **84 passed, 7 failed, 91 collected**. Failures are three invalid customer update fields, two search/pagination cases, and two duplicate identifier updates.
- Frontend production build: **passed** using `npm.cmd run build`; Vite reported a bundle-size warning.
- Of 58 `test_*.py` files, **46 contain no test functions**. Bill, inventory, purchase, return, quotation, and company test filenames mostly represent placeholders, not executed coverage.
- Existing test app mounts customer and party routes only and does not use the production exception handlers. The additional audit reproductions used the full `api.main.app` with SQLite dependency substitution.
- No PostgreSQL concurrency test or fresh PostgreSQL migration test was performed.
- Dashboard is hardcoded; Reports is a placeholder. No dashboard/report backend exists in the mounted router set.
- There is no inventory movement ledger or document revision history in the reviewed models. Stock updates are stored on ItemMaster, while edits replace child lines. Rojmel receipts are permanently deleted. Historical reconciliation and accountability need a defined design.
- The purchase API intentionally has no DELETE endpoint; that absence is not classified as an accidental CRUD bug.

## Suggested repair order

1. Repair bill HTTP response contracts and align SalesEntry pricing/GST fields with backend behavior.
2. Make Rojmel calculated fields output-only and enforce original-document return rules.
3. Implement stock concurrency protection and party ledger/balance posting.
4. Repair customer update validation, list query parameters, and GST-only recalculation.
5. Standardize rounding, document numbering, audit history, and deployment migrations.
6. Add real integration tests for transaction modules and PostgreSQL concurrency tests; connect dashboard/reporting to reconciled data.
