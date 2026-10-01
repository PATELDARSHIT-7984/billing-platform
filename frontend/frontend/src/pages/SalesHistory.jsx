import PdfDownloadActions from '../components/common/PdfDownloadActions';
import Pagination from '../components/common/Pagination';
import useHistoryPage from '../hooks/useHistoryPage';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import BillDetailModal from './BillDetailModal';

import { useToast } from '../context/ToastContext';

import {
  deleteBill,
  fetchBillById,
  fetchBills,
} from '../services/billService';
import { extractErrorMessage } from '../services/api';

import { formatCurrency } from '../utils/calculations';

import './PurchaseHistory.css';

function compactValues(values = [], fallback = '—') {
  const cleaned = values.filter(
    (value) => value !== null && value !== undefined && value !== '',
  );

  if (!cleaned.length) {
    return fallback;
  }

  if (cleaned.length === 1) {
    return String(cleaned[0]);
  }

  return `${cleaned[0]} (+${cleaned.length - 1} more)`;
}

export default function SalesHistory() {
  const toast = useToast();
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const { items: bills, loading, reload: loadBills, pagination } = useHistoryPage(fetchBills, { search });

  async function openDetail(row) {
    const id = row.bill_id ?? row.id;

    setDetailLoading(true);
    setDetailOpen(true);

    try {
      const detail = await fetchBillById(id);
      setDetailData(detail);
    } catch (error) {
      toast.error(extractErrorMessage(error));
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  }

  function handleEdit(row) {
    const id = row.bill_id ?? row.id;
    navigate(`/sales-entry?edit=${id}`);
  }

  async function handleDelete(row) {
    const id = row.bill_id ?? row.id;
    const invoiceNo = row.invoice_no || id;

    const confirmed = window.confirm(
      `Delete sales invoice ${invoiceNo}?`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingId(id);

    try {
      await deleteBill(id);

      if (detailData?.bill?.id === id || detailData?.bill?.bill_id === id) {
        setDetailOpen(false);
        setDetailData(null);
      }

      toast.success(
        `Sales invoice ${invoiceNo} deleted successfully.`,
      );

      await loadBills();
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setDeletingId(null);
    }
  }

  const columns = [
    {
      key: 'invoice_no',
      label: 'Invoice No.',
      render: (row) => (
        <span className="purchase-history__bill-no">
          #{row.invoice_no}
        </span>
      ),
    },
    {
      key: 'bill_date',
      label: 'Bill Date',
      render: (row) => (
        row.bill_date
          ? new Date(row.bill_date).toLocaleDateString(
              'en-IN',
              {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
              },
            )
          : '—'
      ),
    },
    {
      key: 'customer_name',
      label: 'Customer',
      render: (row) => (
        row.customer_name
        || row.party_name
        || '—'
      ),
    },
    {
      key: 'item_name',
      label: 'Item Name',
      render: (row) => compactValues(
        row.item_names
        || row.items?.map((item) => item.item_name)
        || [],
      ),
    },
    {
      key: 'hsn_code',
      label: 'HSN Code',
      render: (row) => compactValues(
        row.hsn_codes
        || row.items?.map((item) => item.hsn_code)
        || [],
      ),
    },
    {
      key: 'total_boxes',
      label: 'Total Boxes',
      align: 'right',
      render: (row) => (
        row.total_boxes
        ?? row.item_count
        ?? 0
      ),
    },
    {
      key: 'grand_total',
      label: 'Grand Total',
      align: 'right',
      render: (row) => (
        <strong>
          {formatCurrency(row.grand_total || 0)}
        </strong>
      ),
    },
    { key: 'pdf', label: 'Download PDF', render: (row) => (
      <PdfDownloadActions type="sale" loadDetail={() => fetchBillById(row.bill_id ?? row.id)} />
    ) },
  ];

  const rows = bills.map((row) => ({
    ...row,
    id: row.id ?? row.bill_id,
  }));

  return (
    <div className="page">
      <PageHeader
        title="Sales History"
        subtitle="View, update, download, or delete sales invoices."
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by invoice number or customer..."
      />

      <DataTable
        columns={columns}
        rows={rows}
        loading={loading || deletingId !== null}
        onRowClick={openDetail}
        onEdit={handleEdit}
        onDelete={handleDelete}
        emptyMessage={
          search
            ? `No sales match "${search}".`
            : 'No sales recorded yet. Create one from Sales Entry.'
        }
      />
      <Pagination {...pagination} />

      <BillDetailModal
        open={detailOpen}
        loading={detailLoading}
        billDetail={detailData}
        onClose={() => {
          setDetailOpen(false);
          setDetailData(null);
        }}
      />
    </div>
  );
}
