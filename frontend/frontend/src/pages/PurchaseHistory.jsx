import PdfDownloadActions from '../components/common/PdfDownloadActions';
import Pagination from '../components/common/Pagination';
import useHistoryPage from '../hooks/useHistoryPage';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import DataTable from '../components/common/DataTable';
import PageHeader from '../components/common/PageHeader';
import PurchaseDetailModal from './PurchaseDetailModal';

import { useToast } from '../context/ToastContext';
import {
  fetchPurchaseById,
  fetchPurchases,
} from '../services/purchaseService';
import { extractErrorMessage } from '../services/api';
import { formatCurrency } from '../utils/calculations';

import './PurchaseHistory.css';


function formatDate(value) {
  if (!value) return '—';

  return new Date(`${value}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function CompactList({ values, formatter = (value) => value }) {
  const safeValues = Array.isArray(values) ? values : [];

  if (!safeValues.length) {
    return <span className="purchase-history__muted">—</span>;
  }

  const visibleValues = safeValues.slice(0, 2);
  const remainingCount = safeValues.length - visibleValues.length;

  return (
    <div className="purchase-history__list">
      {visibleValues.map((value, index) => (
        <span key={`${value}-${index}`}>
          {formatter(value)}
        </span>
      ))}

      {remainingCount > 0 && (
        <span className="purchase-history__more">
          +{remainingCount} more
        </span>
      )}
    </div>
  );
}

export default function PurchaseHistory() {
  const navigate = useNavigate();
  const toast = useToast();

  const [search, setSearch] = useState('');

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const { items: purchases, loading, pagination } = useHistoryPage(fetchPurchases, { search });

  const openDetail = async (row) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailData(null);

    try {
      const data = await fetchPurchaseById(row.id);
      setDetailData(data);
    } catch (error) {
      toast.error(extractErrorMessage(error));
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const editPurchase = (row) => {
    navigate(`/purchase-entry?edit=${row.id}`);
  };

  const columns = [
    { key: 'pdf', label: 'Download PDF', render: (row) => (
      <PdfDownloadActions type="purchase" loadDetail={() => fetchPurchaseById(row.id)} />
    ) },
    {
      key: 'bill_no',
      label: 'Bill No.',
      render: (row) => (
        <span className="purchase-history__bill-no">
          #{row.bill_no}
        </span>
      ),
    },
    {
      key: 'bill_date',
      label: 'Bill Date',
      render: (row) => formatDate(row.bill_date),
    },
    {
      key: 'party_name',
      label: 'Supplier',
      render: (row) => row.party_name || '—',
    },
    {
      key: 'item_names',
      label: 'Item Name',
      render: (row) => (
        <CompactList values={row.item_names} />
      ),
    },
    {
      key: 'hsn_codes',
      label: 'HSN Code',
      render: (row) => (
        <CompactList values={row.hsn_codes} />
      ),
    },
    {
      key: 'purchase_prices',
      label: 'Purchase Price',
      align: 'right',
      render: (row) => (
        <CompactList
          values={row.purchase_prices}
          formatter={formatCurrency}
        />
      ),
    },
    {
      key: 'grand_total',
      label: 'Grand Total',
      align: 'right',
      render: (row) => (
        <strong>{formatCurrency(row.grand_total)}</strong>
      ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Purchase History"
        subtitle="Review every purchase bill, open its complete breakdown, or update an existing entry."
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by bill number, order number or supplier..."
      />

      <DataTable
        columns={columns}
        rows={purchases}
        loading={loading}
        onRowClick={openDetail}
        onEdit={editPurchase}
        emptyMessage={
          search
            ? `No purchases match "${search}".`
            : 'No purchases recorded yet. Create one from Purchase Entry.'
        }
      />
      <Pagination {...pagination} />

      <PurchaseDetailModal
        open={detailOpen}
        loading={detailLoading}
        purchase={detailData}
        onClose={() => setDetailOpen(false)}
      />
    </div>
  );
}
