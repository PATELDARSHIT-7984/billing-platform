import PdfDownloadActions from '../components/common/PdfDownloadActions';
import Pagination from '../components/common/Pagination';
import useHistoryPage from '../hooks/useHistoryPage';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import QuotationDetailModal from './QuotationDetailModal';
import { useToast } from '../context/ToastContext';
import { deleteQuotation, fetchQuotationById, fetchQuotations } from '../services/quotationService';
import { extractErrorMessage } from '../services/api';
import { formatCurrency } from '../utils/calculations';
import './PurchaseHistory.css';

function compact(values = []) {
  const list = values.filter(Boolean);
  if (!list.length) return '—';
  return list.length === 1 ? String(list[0]) : `${list[0]} (+${list.length - 1} more)`;
}

export default function QuotationHistory() {
  const toast = useToast();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const { items: records, loading, reload: load, pagination } = useHistoryPage(fetchQuotations, { search });

  const openDetail = (row) => {
    setDetailOpen(true); setDetailLoading(true);
    fetchQuotationById(row.id).then(setDetailData).catch((e) => { toast.error(extractErrorMessage(e)); setDetailOpen(false); }).finally(() => setDetailLoading(false));
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;
    setDeleting(true);
    deleteQuotation(deleteTarget.id).then(() => { toast.success('Quotation deleted successfully.'); setDeleteTarget(null); load(); }).catch((e) => toast.error(extractErrorMessage(e))).finally(() => setDeleting(false));
  };

  const columns = [
    { key: 'pdf', label: 'Download PDF', render: (row) => (
      <PdfDownloadActions type="quotation" loadDetail={() => fetchQuotationById(row.id)} />
    ) },
    { key: 'quotation_no', label: 'Quotation No.', render: (row) => <span className="purchase-history__bill-no">#{row.quotation_no}</span> },
    { key: 'quotation_date', label: 'Date', render: (row) => row.quotation_date ? new Date(row.quotation_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—' },
    { key: 'customer_name', label: 'Customer', render: (row) => row.customer_name || '—' },
    { key: 'item_names', label: 'Item Name', render: (row) => compact(row.item_names) },
    { key: 'hsn_codes', label: 'HSN Code', render: (row) => compact(row.hsn_codes) },
    { key: 'total_boxes', label: 'Total Boxes', align: 'right', render: (row) => row.total_boxes ?? 0 },
    { key: 'grand_total', label: 'Grand Total', align: 'right', render: (row) => <strong>{formatCurrency(row.grand_total || 0)}</strong> },
  ];

  return <div className="page">
    <PageHeader title="Quotation History" subtitle="View, update, or delete saved customer quotations." searchValue={search} onSearchChange={setSearch} searchPlaceholder="Search by quotation number or customer..." />
    <DataTable columns={columns} rows={records} loading={loading} onRowClick={openDetail} onEdit={(row) => navigate(`/quotation-entry?edit=${row.id}`)} onDelete={setDeleteTarget} emptyMessage="No quotations found." />
    <Pagination {...pagination} />
    <QuotationDetailModal open={detailOpen} loading={detailLoading} quotation={detailData} onClose={() => setDetailOpen(false)} />
    <ConfirmDialog open={Boolean(deleteTarget)} title="Delete Quotation" message={`Delete quotation ${deleteTarget?.quotation_no || ''}? This will not affect Sales or stock.`} confirmLabel="Delete" loading={deleting} onConfirm={confirmDelete} onCancel={() => !deleting && setDeleteTarget(null)} />
  </div>;
}
