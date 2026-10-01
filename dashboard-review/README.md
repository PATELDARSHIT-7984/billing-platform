# Dashboard frontend review

The dashboard now has four highlighted metrics, a five-metric secondary strip, a sales/purchase trend alongside cash flow, account insights and business partner rankings, and recent transactions alongside business performance.

## Files

Changed: `frontend/frontend/src/pages/Dashboard.jsx`, `frontend/frontend/src/pages/Dashboard.css`.

Created: `frontend/frontend/src/pages/DashboardTrend.jsx`, `frontend/frontend/src/utils/dashboardFormat.js`.

Review artifacts: this report and desktop/mobile screenshots in `dashboard-review/`. Screenshots show intercepted test responses, not actual business records. The application itself uses the existing real Dashboard APIs.

Reused unchanged: Button, Modal, Pagination, SearchBar, local SVG navigation icons, dashboardService and the Axios client. No packages were added. No backend, shared component, routing, navigation configuration, or finalized accounting code was edited. Backend Python file hashes were compared before/after and are identical.

## Behavior

- **Summary:** Net Sales, Net Purchase, Supplier Payable and Net Cash Flow have highlighted cards. Total Sales, Total Purchase, Supplier Advance, Total Received and Total Paid form the secondary strip. All authoritative values come directly from summary fields. Sales/purchase returns remain visible in Business Performance.
- **Amounts:** Compact lakh/crore values on cards; full Indian-grouped INR values in titles, tables and account detail. Decimal strings are formatted with integer paise, preserving large amounts and cents without conversion to floating-point numbers. Null/invalid values render a dash. Chart geometry alone uses approximate numeric coordinates.
- **Dates:** Initial summary uses the backend month default and initial trend uses a bare request for six months. Choosing Today, This Week, This Month, Financial Year or Custom sends the explicit period to transaction endpoints, including trend, without a six-month override. Custom dates must both exist, be ordered and fit the backend range limit before requests are made. Accounts remain independent of transaction dates.
- **Trend:** Dependency-free SVG line/area visualization with sales and purchase legend, INR axis labels, hover/focus exact values, responsive geometry and an expandable exact-value table. Single-month results show points correctly. Empty data shows an empty state. Chart totals and the clearly named Sales − Purchase indicator use the returned chart period; they are not presented as profit.
- **Accounts:** Supplier/customer modes reuse the same layout. Supplier summaries show current payable and advance, with Credit → Payable and Debit → Advance badges. Contact, GSTIN, address and inactive status are visible. Customer amounts are hidden with a receivable-tracking-pending note.
- **Global search:** Existing backend search covers name, mobile, address and GSTIN for both suppliers and customers. Search uses 400 ms debounce, section-local skeletons and AbortController cancellation. It never filters just the five loaded rows or refetches summary/chart on account input.
- **View All:** Existing large Modal with a local keyboard focus trap and focus restoration. Includes supplier/customer switching, global search, supplier balance filtering, name and amount sorts, and shared Pagination. API paging uses limit=20 and skip. Type/filter/sort changes reset paging; debounced search and page reset are applied together. Unsupported customer balance filters are hidden.
- **Top partners:** Five initial records, rank badges, net purchase/net sales subtitles, compact amounts and proportional bars. Negative net amounts retain their sign. View All supports global search, mode switching and pagination.
- **Cash flow:** Backend Total Received, Total Paid and Net Cash Flow with proportional comparison bars. No invented categories or derived accounting values.
- **Recent transactions:** Five backend records, muted local icons, full INR amounts and formatted dates. Friendly labels include Sale, Payment and Receipt; transfer/JV labels remain distinct.
- **Performance:** Backend gross/net sales and purchase values, exact backend return percentages, progress bars and formula hints. Rates over 100% remain numerically visible while the bar is capped and labeled.
- **Loading/errors:** Local card, chart and row skeletons. Individual failures show section-specific messages and Retry. Empty account, chart, partner and transaction results have concise hints.
- **Responsive/accessibility:** Desktop multi-column layout, tablet two-column metrics, mobile stacked sections. On the mobile dashboard only, scoped CSS turns existing navigation into an icon rail while retaining accessible link labels. Tables scroll within their panels. Chart geometry adapts to its container. Modal has focus containment, Escape/close-button support and focus restoration. Reduced-motion preferences are respected.

## Validation

- `npm.cmd run build`: passed. Existing bundle-size warning remains (main bundle approximately 889 kB uncompressed).
- Targeted ESLint for all three changed/created JavaScript/JSX files: passed.
- Eight exact amount-formatting checks: passed, covering lakh/crore, Indian grouping, large decimal strings, zero, null, negative amounts and exact visualization-only subtraction.
- Headless Chrome checks with intercepted fixtures: passed for initial bare trend; explicit date request; one-month chart; empty chart; null customer balance; modal next page; search debounce; search page reset; no summary refetch during search; empty results; invalid custom range suppression; valid custom request; account error/retry; no horizontal content overflow at 390 px; mobile modal containment; no runtime exceptions.
- Desktop and mobile screenshots were visually inspected, including mobile chart and modal. Test data included long names, full GSTINs and long addresses.
- No existing frontend test command or test suite was configured. No production data was inserted or modified.

## Deferred

No customer receivable accounting, new backend fields, PDF export, recent-transactions View All, new dependencies or application-wide navigation redesign. The SVG uses precise line segments rather than interpolating artificial intermediate financial values. Wider application bundle optimization remains outside this dashboard task.
