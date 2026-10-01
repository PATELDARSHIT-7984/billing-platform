import PdfDownloadActions from '../components/common/PdfDownloadActions';
import Pagination from '../components/common/Pagination';
import useHistoryPage from '../hooks/useHistoryPage';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import SalesReturnDetailModal from './SalesReturnDetailModal';

import { useToast } from '../context/ToastContext';
import {
  deleteSalesReturn,
  fetchSalesReturnById,
  fetchSalesReturns,
} from '../services/salesReturnService';
import { extractErrorMessage } from '../services/api';
import { formatCurrency } from '../utils/calculations';

import './PurchaseHistory.css';

function compactValues(values = [], fallback = '—') {
  const cleaned = values.filter(
    (value) => (
      value !== null
      && value !== undefined
      && value !== ''
    ),
  );

  if (!cleaned.length) return fallback;
  if (cleaned.length === 1) return String(cleaned[0]);

  return `${cleaned[0]} (+${cleaned.length - 1} more)`;
}

export default function SalesReturnHistory() {
  const toast = useToast();
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const { items: records, loading, reload: loadRecords, pagination } = useHistoryPage(fetchSalesReturns, { search });

  async function openDetail(row) {
    setDetailLoading(true);
    setDetailOpen(true);

    try {
      const data = await fetchSalesReturnById(row.id);
      setDetailData(data);
    } catch (error) {
      toast.error(extractErrorMessage(error));
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  }

  function handleEdit(row) {
    navigate(`/sales-return-entry?edit=${row.id}`);
  }

  async function handleDelete(row) {
    const confirmed = window.confirm(
      `Delete sales return ${row.return_no || row.id}?`,
    );

    if (!confirmed) return;

    setDeletingId(row.id);

    try {
      await deleteSalesReturn(row.id);

      if (detailData?.id === row.id) {
        setDetailOpen(false);
        setDetailData(null);
      }

      toast.success(
        `Sales return ${row.return_no || row.id} deleted successfully.`,
      );

      await loadRecords();
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setDeletingId(null);
    }
  }

  const columns = [
    { key: 'pdf', label: 'Download PDF', render: (row) => (
      <PdfDownloadActions type="salesReturn" loadDetail={() => fetchSalesReturnById(row.id)} />
    ) },
    {
      key: 'return_no',
      label: 'Return No.',
      render: (row) => (
        <span className="purchase-history__bill-no">
          #{row.return_no}
        </span>
      ),
    },
    {
      key: 'return_date',
      label: 'Return Date',
      render: (row) => (
        row.return_date
          ? new Date(row.return_date).toLocaleDateString('en-IN', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            })
          : '—'
      ),
    },
    {
      key: 'customer_name',
      label: 'Customer',
      render: (row) => row.customer_name || '—',
    },
    {
      key: 'original_invoice_no',
      label: 'Original Invoice',
      render: (row) => row.original_invoice_no || '—',
    },
    {
      key: 'item_name',
      label: 'Item Name',
      render: (row) => compactValues(row.item_names || []),
    },
    {
      key: 'hsn_code',
      label: 'HSN Code',
      render: (row) => compactValues(row.hsn_codes || []),
    },
    {
      key: 'total_boxes',
      label: 'Total Boxes',
      align: 'right',
      render: (row) => row.total_boxes ?? 0,
    },
    {
      key: 'return_reason',
      label: 'Reason',
      render: (row) => row.return_reason || '—',
    },
    {
      key: 'grand_total',
      label: 'Grand Total',
      align: 'right',
      render: (row) => (
        <strong>{formatCurrency(row.grand_total || 0)}</strong>
      ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Sales Return History"
        subtitle="View, update, or delete customer sales returns."
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by return no., invoice, or customer..."
      />

      <DataTable
        columns={columns}
        rows={records}
        loading={loading || deletingId !== null}
        onRowClick={openDetail}
        onEdit={handleEdit}
        onDelete={handleDelete}
        emptyMessage={
          search
            ? `No sales returns match "${search}".`
            : 'No sales returns recorded yet.'
        }
      />
      <Pagination {...pagination} />

      <SalesReturnDetailModal
        open={detailOpen}
        loading={detailLoading}
        salesReturn={detailData}
        onClose={() => {
          setDetailOpen(false);
          setDetailData(null);
        }}
      />
    </div>
  );
}
