# Dashboard prototype implementation report

Implemented all seven dashboard sections using backend data: 11 summary cards, sales versus purchase chart, account insights, top business partners, cash flow, recent transactions, and business performance. Loading, retryable errors, empty results, responsive layouts, INR formatting, and accessible input labels are included.

## Files

Modified by this task:
- backend/api/main.py — dashboard router registration.
- backend/main.py — dashboard router registration for the legacy entry point.
- frontend/frontend/src/pages/Dashboard.jsx — functional dashboard UI.
- frontend/frontend/src/pages/Dashboard.css — scoped styles using existing design tokens.

Created:
- backend/api/repository/dashboard.py — read-only SQL queries.
- backend/api/services/dashboard.py — date ranges, Decimal calculations, response composition.
- backend/api/schema/dashboard.py — typed response contracts.
- backend/api/router/dashboard.py — five GET endpoints.
- backend/api/tests/test_dashboard.py — focused database and API tests.
- frontend/frontend/src/services/dashboardService.js — existing Axios client integration.
- DASHBOARD_IMPLEMENTATION.md — this report.

The workspace already contained extensive modifications and untracked authoritative source files before this task. Those unrelated changes were preserved. Finalized transaction modules, posting logic, schemas, and migrations were not changed.

## Endpoints and response formats

All endpoints are under /dashboard and return direct typed JSON, consistent with existing non-Rojmel routes. Decimal money and percentages serialize as strings; dates are ISO YYYY-MM-DD.

- GET /summary: start_date, end_date, balances_as_of="current", total_sales, total_purchase, total_sales_return, total_purchase_return, net_sales, net_purchase, supplier_payable, supplier_advance, total_received, total_paid, net_cash_flow, customer_receivable=null, sales_return_rate, purchase_return_rate.
- GET /trend: {start_date, end_date, labels: ["Apr 2026", ...], sales: ["0.00", ...], purchase: ["0.00", ...]}.
- GET /accounts: {items: [{id, name, mobile, address, gstin, is_active, current_balance, balance_type}], total, limit, skip}.
- GET /top-partners: {items: [{id, name, net_amount, rank}], total, limit, skip}.
- GET /recent-transactions: [{id, number, date, name, amount, type}], at most five.

Transaction endpoints accept period=today|week|month|financial_year|custom, with start_date/end_date required for custom. Default is month. Dates are inclusive; presets end today. Invalid, reversed, or custom ranges longer than 3,660 days return 422.

Accounts accepts type=supplier|customer, search, balance_type=all|payable|advance, sort=name_asc|name_desc|balance_asc|balance_desc, limit (default 5, maximum 100), and skip (default 0). Customer balances are unsupported; supplier balance filter/sorts do not apply to customer records.

Top partners accepts type, search, limit, skip and date parameters. Ranking is descending net amount with deterministic name/id ties. Rank positions are within the searched result.

Trend additionally accepts last_six_months=true (default). It shows six calendar months through the selected range end. Setting false uses the exact dashboard range. The UI explicitly labels this separate chart period and displays its dates.

## Search and list behavior

Supplier search uses SQL OR/ILIKE over Party.name, Party.mobile, Party.address, Party.gstin, with party_type exactly Supplier. Customer search uses the independent Customer table: customer_name, mobile, address, gstin. All requested fields exist. Literal %, _ and backslash are escaped. No migration was needed.

The initial lists each load five records. Search runs over the entire database result, never just the loaded page, with 350 ms debounce. View All opens the existing shared Modal and requests 20 records per page using the shared Pagination component. Search, sorting and balance-filter changes reset pagination. Supplier/customer switches reset list state. Superseded requests are aborted.

Account browsing includes inactive records, visibly marked, to keep current supplier totals reconcilable with the list. Supplier totals include all Supplier records regardless of active status, matching the requested formula. Transaction aggregates exclude inactive documents, following transaction repository conventions; historical transactions remain included if their partner is now inactive.

## Accounting and dates

- Supplier payable = SUM Party.current_balance where party_type='Supplier' and current_balance_type='Credit'.
- Supplier advance = SUM Party.current_balance where party_type='Supplier' and current_balance_type='Debit'.
- Current supplier balances are never filtered by historical dates or reconstructed from transactions.
- Net purchase = active Purchase.grand_total minus active PurchaseReturn.grand_total in the period.
- Net sales = active Bill.grand_total minus active SalesReturn.grand_total in the period.
- Top supplier = period purchases minus period purchase returns grouped by party_id. Customer equivalent uses customer_id. Returns are independent unioned movements, preventing join multiplication and preserving return-only or negative-net partners.
- Chart = monthly SQL sums of gross active Bill/Purchase grand_total, with empty months filled with zero. The dependency-free SVG includes tooltips and an expandable exact-value table.
- Cash flow reuses get_rojmel_summary: Cr Pay net_amount is received, Dr Pay net_amount is paid, net flow is received minus paid. Cash/Bank and JV are excluded from cash flow.
- Recent transactions merges at most five SQL-selected rows from each of Purchase, Bill, PurchaseReturn, SalesReturn, Rojmel; sorts by transaction date descending with deterministic id/type ties; returns five. Rojmel types remain visible, including transfer/JV records, without counting those as cash flow.
- Performance uses gross/net amounts and return/gross * 100, returning zero for a zero denominator.
- Legacy Float document totals are cast to Numeric(18,2) before SQL aggregation; service arithmetic uses Decimal. Stored Rojmel net_amount and Party balances are already Numeric.

Date fields: Purchase.bill_date, Bill.bill_date, PurchaseReturn.return_date, SalesReturn.return_date, Rojmel.effective_date. No configured business timezone existed; dashboard presets use India UTC+05:30, consistent with this business context. Weeks start Monday. Financial years start April 1, matching existing Rojmel behavior.

## Limitations and verification

Customer has no current balance fields. Customer browsing/search and safe customer sales ranking are implemented; customer receivable remains null with tracking-pending text. No ledger or accounting behavior was invented.

An existing caveat found during inspection: Party creation does not explicitly copy opening_balance to current_balance. Dashboard honors the stored authoritative current_balance and does not repair/recalculate it.

Deferred: recent-transactions View All, customer running balances, PDF exports, inventory schema work, and production bundle optimization. No new dependencies were added. App routing/navigation already exposed the dashboard and needed no changes.

Validation:
- 30 focused dashboard tests passed, covering the requested accounting/search/ranking/cash-flow/recent/performance cases, date boundaries, endpoint validation, decimal serialization, and SELECT-only reads.
- 43 existing Party and Rojmel balance regression tests passed.
- Frontend production build passed; Vite reports a bundle over 500 kB.
- Targeted ESLint passed for Dashboard.jsx and dashboardService.js.
- Tests used an isolated SQLite database; no live accounting records were modified. Browser visual testing and live PostgreSQL execution were not performed.
