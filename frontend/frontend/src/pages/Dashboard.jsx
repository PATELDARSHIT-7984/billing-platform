import { useEffect, useRef, useState } from 'react';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import { SalesIcon, PurchaseIcon, PartyIcon, RojmelIcon, BillHistoryIcon, PurchaseHistoryIcon, ReportsIcon } from '../components/layout/icons';
import { fetchDashboard } from '../services/dashboardService';
import { extractErrorMessage } from '../services/api';
import { formatINR, formatDate } from '../utils/dashboardFormat';
import DashboardTrend from './DashboardTrend';
import './Dashboard.css';

const TRANSACTIONS = {
  purchase: ['Purchase', PurchaseIcon], sales: ['Sale', SalesIcon],
  purchase_return: ['Purchase Return', PurchaseHistoryIcon], sales_return: ['Sales Return', BillHistoryIcon],
  'Dr Pay': ['Payment', PurchaseIcon], 'Cr Pay': ['Receipt', RojmelIcon],
  'Cash/Bank': ['Cash / Bank Transfer', RojmelIcon], JV: ['Journal Entry', BillHistoryIcon],
};

function useDashboard(section, params) {
  const key = JSON.stringify(params);
  const [state, setState] = useState({ key: '', data: null, error: '', loading: true });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetchDashboard(section, JSON.parse(key), controller.signal).then(
      (data) => { if (!controller.signal.aborted) setState({ key, data, error: '', loading: false }); },
      (error) => { if (!controller.signal.aborted) setState({ key, data: null, error: extractErrorMessage(error), loading: false }); },
    );
    return () => controller.abort();
  }, [section, key, retry]);
  return { ...(state.key === key ? state : { data: null, error: '', loading: true }), retry: () => { setState({ key: '', data: null, error: '', loading: true }); setRetry((n) => n + 1); } };
}

function Status({ request, children, name = 'data', shape = 'rows' }) {
  if (request.loading) return <div className={`dashboard__skeleton dashboard__skeleton--${shape}`} role="status" aria-label={`Loading ${name}`}>
    {Array.from({ length: shape === 'chart' ? 1 : 4 }, (_, i) => <div key={i}><i /><span /><span /></div>)}
  </div>;
  if (request.error) return <div className="dashboard__error" role="alert"><div><strong>Unable to load {name}.</strong><p>{request.error}</p></div><Button size="sm" variant="secondary" onClick={request.retry}>Retry</Button></div>;
  return children;
}

function Money({ value, compact = false, className = '' }) {
  return <span className={`dashboard__money ${className}`} title={formatINR(value)} aria-label={compact ? formatINR(value) : undefined}>{formatINR(value, compact)}</span>;
}

function Heading({ title, subtitle, children }) {
  return <div className="dashboard__section-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{children}</div>;
}

function Empty({ title, hint = 'Try a different date range.' }) {
  return <div className="dashboard__empty"><span className="dashboard__empty-icon" aria-hidden="true"><ReportsIcon /></span><strong>{title}</strong><span>{hint}</span></div>;
}

function SummaryCard({ label, value, icon: Icon, tone, children }) {
  return <article className={`dashboard__stat dashboard__stat--${tone}`}>
    <div className="dashboard__stat-label"><span>{label}</span><span className="dashboard__stat-icon" aria-hidden="true"><Icon /></span></div>
    <Money value={value} compact className="dashboard__stat-value" />
    <div className="dashboard__stat-support">{children}</div>
  </article>;
}

function Summary({ request }) {
  const data = request.data;
  return <Status request={request} name="summary" shape="cards">{data && <>
    <div className="dashboard__stats">
      <SummaryCard label="Net Sales" value={data.net_sales} icon={SalesIcon} tone="blue">Gross sales <Money value={data.total_sales} compact /></SummaryCard>
      <SummaryCard label="Net Purchase" value={data.net_purchase} icon={PurchaseIcon} tone="teal">Gross purchase <Money value={data.total_purchase} compact /></SummaryCard>
      <SummaryCard label="Supplier Payable" value={data.supplier_payable} icon={PartyIcon} tone="amber">Current outstanding</SummaryCard>
      <SummaryCard label="Net Cash Flow" value={data.net_cash_flow} icon={RojmelIcon} tone="navy">{Number(data.net_cash_flow) > 0 ? 'Positive cash flow' : Number(data.net_cash_flow) < 0 ? 'Payments exceed receipts' : 'Receipts and payments are balanced'}</SummaryCard>
    </div>
    <div className="dashboard__secondary">
      {[
        ['Total Sales', data.total_sales, SalesIcon], ['Total Purchase', data.total_purchase, PurchaseIcon],
        ['Supplier Advance', data.supplier_advance, PartyIcon], ['Total Received', data.total_received, RojmelIcon], ['Total Paid', data.total_paid, BillHistoryIcon],
      ].map(([label, value, Icon]) => <div key={label}><span className="dashboard__secondary-icon" aria-hidden="true"><Icon /></span><div><span>{label}</span><Money value={value} compact /></div></div>)}
    </div>
    <p className="dashboard__period-note">{formatDate(data.start_date)} – {formatDate(data.end_date)}<span>Supplier balances are current outstanding values.</span></p>
  </>}</Status>;
}

// Add focus containment locally without changing the shared modal.
function ModalContent({ children }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const dialog = ref.current.closest('[role="dialog"]');
    const focusable = () => [...dialog.querySelectorAll('button:not(:disabled), input, select, summary, [tabindex="0"]')];
    focusable()[0]?.focus();
    const trap = (event) => {
      if (event.key !== 'Tab') return;
      const elements = focusable();
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    dialog.addEventListener('keydown', trap);
    return () => { dialog.removeEventListener('keydown', trap); previous?.focus(); };
  }, []);
  return <div ref={ref} className="dashboard dashboard__modal-content">{children}</div>;
}

function ViewAll({ type: initialType, ranking, dates, search }) {
  const [type, setType] = useState(initialType);
  return <ModalContent>
    <Heading title={ranking ? 'Business partner ranking' : 'Browse accounts'} subtitle={ranking ? `Ranked by net ${type === 'supplier' ? 'purchase' : 'sales'}` : 'Search across all accounts, including inactive records.'}>
      <select aria-label="View all account type" value={type} onChange={(e) => setType(e.target.value)}><option value="supplier">Supplier</option><option value="customer">Customer</option></select>
    </Heading>
    {!ranking && type === 'customer' && <p className="dashboard__pending">Receivable tracking pending. Contact details are available below.</p>}
    <AccountList key={type} type={type} ranking={ranking} dates={dates} expanded initialSearch={search} />
  </ModalContent>;
}

function AccountList({ type, ranking = false, dates, expanded = false, initialSearch = '' }) {
  const [search, setSearch] = useState(initialSearch);
  const [debounced, setDebounced] = useState(initialSearch);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('name_asc');
  const [balance, setBalance] = useState('all');
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => { setDebounced(search); setPage(1); }, 400);
    return () => clearTimeout(timer);
  }, [search]);
  const limit = expanded ? 20 : 5;
  const request = useDashboard(ranking ? 'top-partners' : 'accounts', {
    ...(ranking ? dates : {}), type, search: debounced, limit, skip: (page - 1) * limit,
    ...(!ranking ? { sort, balance_type: balance } : {}),
  });
  const noun = type === 'supplier' ? 'suppliers' : 'customers';
  const rows = request.data?.items || [];
  const maximum = Math.max(1, ...rows.map((row) => Math.abs(Number(row.net_amount || 0))));
  const pending = search !== debounced;
  return <>
    <div className="dashboard__tools">
      <label className="dashboard__search"><span className="dashboard__sr-only">Search {noun}</span><SearchBar placeholder={`Search ${noun}…`} value={search} onChange={setSearch} /></label>
      {expanded && !ranking && <>
        <select aria-label="Sort accounts" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
          <option value="name_asc">Name A–Z</option><option value="name_desc">Name Z–A</option>
          {type === 'supplier' && <><option value="balance_desc">Highest Amount</option><option value="balance_asc">Lowest Amount</option></>}
        </select>
        {type === 'supplier' && <select aria-label="Balance filter" value={balance} onChange={(e) => { setBalance(e.target.value); setPage(1); }}><option value="all">All balances</option><option value="payable">Payable</option><option value="advance">Advance</option></select>}
      </>}
    </div>
    <p className="dashboard__note">Search by name, mobile, address or GSTIN</p>
    <Status request={pending ? { loading: true } : request} name={ranking ? 'business partners' : 'accounts'}>
      {rows.length ? <div className="dashboard__account-rows">{rows.map((row) => <div className={`dashboard__account-row ${ranking ? 'dashboard__account-row--ranked' : ''}`} key={row.id}>
        <span className={ranking ? 'dashboard__rank' : 'dashboard__avatar'} aria-hidden="true">{ranking ? `#${row.rank}` : row.name?.trim().slice(0, 2).toUpperCase()}</span>
        <div className="dashboard__account-info"><strong title={row.name}>{row.name}</strong>
          {ranking ? <><span className="dashboard__note">Net {type === 'supplier' ? 'purchase' : 'sales'}</span><div className="dashboard__ranking-bar"><i className={Number(row.net_amount) < 0 ? 'is-negative' : ''} style={{ width: `${Math.abs(Number(row.net_amount)) / maximum * 100}%` }} /></div></> : <>
            <span className="dashboard__contact">{row.mobile || 'No mobile'} <span>·</span> {row.gstin || 'No GSTIN'}</span>
            <span className="dashboard__address" title={row.address || ''}>{row.address || 'No address'}</span>
            {row.is_active === false && <span className="dashboard__inactive">Inactive account</span>}
          </>}
        </div>
        {(ranking || type === 'supplier') && <div className="dashboard__account-amount"><Money value={ranking ? row.net_amount : row.current_balance} compact={ranking && !expanded} />
          {!ranking && row.current_balance != null && <span className={`dashboard__badge dashboard__badge--${row.balance_type === 'Credit' ? 'payable' : 'advance'}`}>{row.balance_type === 'Credit' ? 'Payable' : 'Advance'}</span>}
        </div>}
      </div>)}</div> : <Empty title={ranking ? 'No business partners found' : `No ${noun} found`} hint="Try a different name, phone, address or GSTIN." />}
      {expanded && <Pagination page={page} totalPages={Math.ceil((request.data?.total || 0) / limit)} total={request.data?.total || 0} pageSize={limit} onPageChange={setPage} />}
    </Status>
    {!expanded && <div className="dashboard__list-footer"><span>{request.loading || pending ? 'Searching accounts' : `${Math.min(5, request.data?.total || 0)} of ${request.data?.total || 0} ${noun}`}</span><Button variant="ghost" size="sm" className="dashboard__view-all" onClick={() => setOpen(true)}>View All <span aria-hidden="true">→</span></Button></div>}
    {!expanded && <Modal open={open} title={ranking ? 'Top Business Partners' : 'Account Insights'} width={940} onClose={() => setOpen(false)}>
      {open && <ViewAll type={type} ranking={ranking} dates={dates} search={search} />}
    </Modal>}
  </>;
}

function PartnerSection({ ranking = false, dates, summary }) {
  const [type, setType] = useState('supplier');
  return <section className="dashboard__panel">
    <Heading title={ranking ? 'Top Business Partners' : 'Account Insights'} subtitle={ranking ? `Ranked by net ${type === 'supplier' ? 'purchase' : 'sales'}` : 'A clear view of your business accounts'}>
      <select aria-label={ranking ? 'Business partner type' : 'Account type'} value={type} onChange={(e) => setType(e.target.value)}><option value="supplier">Supplier</option><option value="customer">Customer</option></select>
    </Heading>
    {!ranking && (type === 'supplier' ? <div className="dashboard__account-summary"><div><span>Total Payable</span><Money value={summary?.supplier_payable} /></div><div><span>Total Advance</span><Money value={summary?.supplier_advance} /></div></div> : <p className="dashboard__pending">Receivable tracking pending. Browse customer details below.</p>)}
    <AccountList key={ranking ? `${type}-${JSON.stringify(dates)}` : type} type={type} ranking={ranking} dates={dates} />
  </section>;
}

function CashFlow({ request }) {
  const data = request.data;
  const maximum = data ? Math.max(1, Number(data.total_received), Number(data.total_paid)) : 1;
  return <section className="dashboard__panel dashboard__cash"><Heading title="Cash Flow" subtitle="Money in and money out" />
    <Status request={request} name="cash flow">{data && <>
      <div className="dashboard__cash-net"><span>Net Cash Flow</span><Money value={data.net_cash_flow} compact /><small>{Number(data.net_cash_flow) >= 0 ? 'Receipts cover payments' : 'Payments exceed receipts'}</small></div>
      {[
        ['Received', data.total_received, 'teal'], ['Paid', data.total_paid, 'blue'],
      ].map(([label, value, tone]) => <div className="dashboard__comparison" key={label}><div><span>{label}</span><Money value={value} /></div><div className={`dashboard__bar dashboard__bar--${tone}`}><i style={{ width: `${Math.max(0, Number(value)) / maximum * 100}%` }} /></div></div>)}
      <p className="dashboard__note">Selected period · Cash / Bank transfers and journal adjustments excluded.</p>
    </>}</Status>
  </section>;
}

function Performance({ request }) {
  const data = request.data;
  return <section className="dashboard__panel"><Heading title="Business Performance" subtitle="Gross volume, net volume and returns" />
    <Status request={request} name="business performance">{data && <>
      <dl className="dashboard__performance-totals">{[['Gross Sales', 'total_sales'], ['Net Sales', 'net_sales'], ['Gross Purchase', 'total_purchase'], ['Net Purchase', 'net_purchase']].map(([label, key]) => <div key={key}><dt>{label}</dt><dd><Money value={data[key]} /></dd></div>)}</dl>
      {['sales', 'purchase'].map((kind) => <div className="dashboard__return" key={kind}>
        <div><span>{kind === 'sales' ? 'Sales' : 'Purchase'} Return Rate <abbr title={`${kind === 'sales' ? 'Sales' : 'Purchase'} Return ÷ Gross ${kind === 'sales' ? 'Sales' : 'Purchase'} × 100`}>ⓘ</abbr></span><strong>{data[`${kind}_return_rate`]}%</strong></div>
        <div className={`dashboard__bar dashboard__bar--${kind === 'sales' ? 'blue' : 'teal'}`} role="meter" aria-label={`${kind} return rate`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, Math.max(0, Number(data[`${kind}_return_rate`])))} aria-valuetext={`${data[`${kind}_return_rate`]} percent`}><i style={{ width: `${Math.min(100, Math.max(0, Number(data[`${kind}_return_rate`])))}%` }} /></div>
        <small>Returns <Money value={data[`total_${kind}_return`]} />{Number(data[`${kind}_return_rate`]) > 100 ? ' · Rate exceeds 100%; bar capped at full width.' : ''}</small>
      </div>)}
    </>}</Status>
  </section>;
}

function RecentTransactions({ request }) {
  return <section className="dashboard__panel"><Heading title="Recent Transactions" subtitle="Latest five transactions in the selected period"><span className="dashboard__subtle-tag">Activity</span></Heading>
    <Status request={request} name="recent transactions">{request.data?.length ? <div className="dashboard__table-wrap"><table className="dashboard__transactions"><thead><tr><th>Transaction</th><th>Account</th><th>Date</th><th className="dashboard__numeric">Amount</th></tr></thead><tbody>{request.data.map((row) => {
      const [label, Icon] = TRANSACTIONS[row.type] || [row.type, BillHistoryIcon];
      return <tr key={`${row.type}-${row.id}`}><td><div className="dashboard__transaction-label"><span className="dashboard__transaction-icon" aria-hidden="true"><Icon /></span><div><strong>{label}</strong><small>{row.number}</small></div></div></td><td>{row.name || '—'}</td><td className="dashboard__date">{formatDate(row.date)}</td><td className="dashboard__numeric"><Money value={row.amount} /></td></tr>;
    })}</tbody></table></div> : <Empty title="No transactions in this date range" />}</Status>
  </section>;
}

function Overview({ dates }) {
  const summary = useDashboard('summary', dates);
  const trend = useDashboard('trend', dates);
  const recent = useDashboard('recent-transactions', dates);
  return <>
    <Summary request={summary} />
    <div className="dashboard__analytics-grid"><section className="dashboard__panel"><Heading title="Sales vs Purchase" subtitle="Business transaction trend"><span className="dashboard__subtle-tag">{dates.period ? 'Selected period' : 'Last 6 months'}</span></Heading><Status request={trend} name="trend data" shape="chart">{trend.data && <DashboardTrend key={JSON.stringify(dates)} data={trend.data} />}</Status></section><CashFlow request={summary} /></div>
    <div className="dashboard__accounts-grid"><PartnerSection dates={dates} summary={summary.data} /><PartnerSection ranking dates={dates} /></div>
    <div className="dashboard__analytics-grid"><RecentTransactions request={recent} /><Performance request={summary} /></div>
  </>;
}

export default function Dashboard() {
  const [period, setPeriod] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const valid = period !== 'custom' || (start && end && start <= end && (Date.parse(end) - Date.parse(start)) / 86400000 <= 3660);
  const dates = period ? { period, ...(period === 'custom' ? { start_date: start, end_date: end } : {}) } : {};
  return <div className="page"><div className="dashboard">
    <header className="dashboard__header"><div><span className="dashboard__eyebrow">BUSINESS INTELLIGENCE</span><h1>Dashboard</h1><p>Business overview and financial performance</p></div><div className="dashboard__date-controls"><label><span>Reporting period</span><select aria-label="Dashboard date filter" value={period} onChange={(e) => setPeriod(e.target.value)}><option value="">Overview · This month</option><option value="today">Today</option><option value="week">This Week</option><option value="month">This Month</option><option value="financial_year">This Financial Year</option><option value="custom">Custom Range</option></select></label>{period === 'custom' && <><label><span>From</span><input aria-label="Start date" type="date" value={start} max={end || undefined} onChange={(e) => setStart(e.target.value)} /></label><label><span>To</span><input aria-label="End date" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label></>}</div></header>
    {valid ? <Overview dates={dates} /> : <div className="dashboard__panel dashboard__date-prompt" role="status">Select a valid start and end date, up to ten years apart, to view this period.</div>}
  </div></div>;
}
