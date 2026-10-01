import { useEffect, useRef, useState } from 'react';
import { chartAmount, formatDate, formatINR } from '../utils/dashboardFormat';

export default function DashboardTrend({ data }) {
  const [active, setActive] = useState(null);
  const container = useRef(null);
  const [width, setWidth] = useState(770);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const sales = data.sales.map(Number);
  const purchase = data.purchase.map(Number);
  const maximum = Math.max(1, ...sales, ...purchase) * 1.15;
  const x = (index) => data.labels.length === 1 ? (width + 46) / 2 : 66 + index * (width - 86) / (data.labels.length - 1);
  const y = (value) => 224 - value / maximum * 190;
  const path = (values) => values.map((value, i) => `${i ? 'L' : 'M'}${x(i)},${y(value)}`).join(' ');
  const selected = active == null ? null : Math.min(active, data.labels.length - 1);
  const hasData = [...sales, ...purchase].some((value) => value !== 0);
  const labelEvery = Math.max(1, Math.ceil(data.labels.length / Math.max(2, Math.floor(width / 110))));
  return <div ref={container}>
    <div className="dashboard__chart-stats">
      {[
        ['Sales', chartAmount(data.sales), 'blue'],
        ['Purchase', chartAmount(data.purchase), 'teal'],
        ['Sales − Purchase', chartAmount(data.sales, data.purchase), 'neutral'],
      ].map(([label, amount, tone]) => <div key={label}><span><i className={`dashboard__dot dashboard__dot--${tone}`} />{label}</span><strong title={formatINR(amount)}>{formatINR(amount, true)}</strong></div>)}
    </div>
    <p className="dashboard__note">{formatDate(data.start_date)} – {formatDate(data.end_date)} · Gross transaction volume</p>
    {!hasData ? <div className="dashboard__empty"><strong>No chart data available</strong><span>No sales or purchases in this date range.</span></div> : <div className="dashboard__chart">
      <div className="dashboard__chart-tooltip" aria-live="polite">
        {selected == null ? <span>Hover or focus a month to compare exact amounts</span> : <><strong>{data.labels[selected]}</strong><span>Sales {formatINR(data.sales[selected])}</span><span>Purchase {formatINR(data.purchase[selected])}</span></>}
      </div>
      <svg viewBox={`0 0 ${width} 260`} role="group" aria-label="Monthly sales and purchase trend" onMouseLeave={() => setActive(null)}>
        {[0, 1, 2, 3, 4].map((tick) => { const value = maximum * tick / 4; return <g key={tick}>
          <line x1="66" x2={width - 20} y1={y(value)} y2={y(value)} className="dashboard__gridline" />
          <text x="56" y={y(value) + 4} textAnchor="end" className="dashboard__axis">{formatINR(value.toFixed(2), true)}</text>
        </g>; })}
        {data.labels.length > 1 && <path d={`${path(sales)} L${x(sales.length - 1)},224 L${x(0)},224 Z`} fill="var(--color-primary)" opacity=".055" />}
        <path d={path(sales)} className="dashboard__line dashboard__line--sales" />
        <path d={path(purchase)} className="dashboard__line dashboard__line--purchase" />
        {selected != null && <line x1={x(selected)} x2={x(selected)} y1="28" y2="224" className="dashboard__crosshair" />}
        {data.labels.map((label, i) => <g key={label}>
          {(i % labelEvery === 0 || i === data.labels.length - 1) && <text x={x(i)} y="250" textAnchor={i === data.labels.length - 1 ? 'end' : 'middle'} className="dashboard__axis">{label}</text>}
          <circle cx={x(i)} cy={y(sales[i])} r={selected === i ? 5 : 3} className="dashboard__point dashboard__point--sales" />
          <circle cx={x(i)} cy={y(purchase[i])} r={selected === i ? 5 : 3} className="dashboard__point dashboard__point--purchase" />
          <rect x={x(i) - Math.min(20, (width - 86) / data.labels.length / 2)} y="20" width={Math.min(40, (width - 86) / data.labels.length)} height="210" fill="transparent" tabIndex="0" role="button"
            aria-label={`${label}: Sales ${formatINR(data.sales[i])}, Purchase ${formatINR(data.purchase[i])}`}
            onMouseEnter={() => setActive(i)} onFocus={() => setActive(i)} onBlur={() => setActive(null)} onClick={() => setActive(i)}
            onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setActive(i); } }} />
        </g>)}
      </svg>
    </div>}
    <details className="dashboard__chart-details"><summary>View exact monthly amounts</summary><div className="dashboard__table-wrap"><table><thead><tr><th>Month</th><th>Sales</th><th>Purchase</th></tr></thead><tbody>{data.labels.map((label, i) => <tr key={label}><td>{label}</td><td>{formatINR(data.sales[i])}</td><td>{formatINR(data.purchase[i])}</td></tr>)}</tbody></table></div></details>
  </div>;
}
