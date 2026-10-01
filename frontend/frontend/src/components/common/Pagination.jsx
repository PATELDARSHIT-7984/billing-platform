import Button from './Button';
import { pageNumbers } from '../../utils/pagination';
import './Pagination.css';

export default function Pagination({ page, totalPages, total, pageSize, onPageChange, onPageSizeChange, loading = false }) {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <nav className="pagination" aria-label="Table pagination" aria-busy={loading}>
      <span className="pagination__summary" aria-live="polite">
        {loading ? 'Loading records…' : `Showing ${from}–${to} of ${total} records`}
      </span>
      <div className="pagination__controls">
        <Button variant="secondary" size="sm" disabled={loading || page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        {pageNumbers(page, totalPages).map((number, index) => number === '…'
          ? <span key={`gap-${index}`} aria-hidden="true">…</span>
          : <Button key={number} variant="secondary" size="sm" aria-label={`Page ${number}`} aria-current={number === page ? 'page' : undefined} disabled={loading || number === page} onClick={() => onPageChange(number)}>{number}</Button>)}
        <Button variant="secondary" size="sm" disabled={loading || page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
      {onPageSizeChange && <label className="pagination__size">
        Rows per page: <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
          {[20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
        </select>
      </label>}
    </nav>
  );
}
