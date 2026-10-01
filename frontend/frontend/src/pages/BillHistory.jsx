import PdfDownloadActions from '../components/common/PdfDownloadActions';
import { useCallback, useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import BillDetailModal from './BillDetailModal';
import { useToast } from '../context/ToastContext';
import { fetchBills, fetchBillById, deleteBill } from '../services/billService';
import { extractErrorMessage } from '../services/api';
import { formatCurrency } from '../utils/calculations';
import './PurchaseHistory.css';

export default function BillHistory() {
  const toast = useToast();

  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [billToDelete, setBillToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadBills = useCallback((searchTerm) => {
    setLoading(true);
    fetchBills({ search: searchTerm })
      .then(setBills)
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadBills('');
  }, [loadBills]);

  useEffect(() => {
    const timer = setTimeout(() => loadBills(search), 350);
    return () => clearTimeout(timer);
  }, [search, loadBills]);

  const COLUMNS = [
    {
      key: 'invoice_no',
      label: 'Invoice No.',
      render: (row) => <span className="purchase-history__bill-no">#{row.invoice_no}</span>,
    },
    {
      key: 'bill_date',
      label: 'Bill Date',
      render: (row) => new Date(row.bill_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
    },
    { key: 'customer_name', label: 'Customer', render: (row) => row.customer_name || '—' },
    { key: 'total_boxes', label: 'Total Boxes', align: 'right', render: (row) => row.total_boxes },
    {
      key: 'grand_total',
      label: 'Grand Total',
      align: 'right',
      render: (row) => <strong>{formatCurrency(row.grand_total)}</strong>,
    },
    { key: 'pdf', label: 'Download PDF', render: (row) => (
      <PdfDownloadActions type="sale" loadDetail={() => fetchBillById(row.bill_id ?? row.id)} />
    ) },
  ];

  const openDetail = (row) => {
    setDetailLoading(true);
    setDetailOpen(true);
    fetchBillById(row.bill_id)
      .then(setDetailData)
      .catch((err) => {
        toast.error(extractErrorMessage(err));
        setDetailOpen(false);
      })
      .finally(() => setDetailLoading(false));
  };

  const askDelete = (row) => {
    setBillToDelete(row);
    setConfirmOpen(true);
  };

  const confirmDelete = () => {
    setDeleting(true);
    deleteBill(billToDelete.bill_id)
      .then(() => {
        toast.success(`Invoice #${billToDelete.invoice_no} deleted successfully.`);
        setConfirmOpen(false);
        setBillToDelete(null);
        loadBills(search);
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  return (
    <div className="page">
      <PageHeader
        title="Sales History"
        subtitle="Every sales invoice you've recorded — click a row to see the full breakdown."
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by invoice number or customer..."
      />

      <DataTable
        columns={COLUMNS}
        rows={bills}
        loading={loading}
        onRowClick={openDetail}
        onDelete={askDelete}
        emptyMessage={search ? `No sales match "${search}".` : 'No sales recorded yet. Create one from Sales Entry.'}
      />

      <BillDetailModal
        open={detailOpen}
        loading={detailLoading}
        billDetail={detailData}
        onClose={() => setDetailOpen(false)}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Delete Sale"
        message={`Are you sure you want to delete Invoice #${billToDelete?.invoice_no}? This will restore the stock it had deducted from Item Master. This cannot be undone.`}
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
