import { useManagedOrigin } from '../hooks/useManagedCreate';
import { accountSelectionFields } from '../services/accountService';
import useHistoryPage from '../hooks/useHistoryPage';
import { useEffect, useState, useMemo } from 'react';
import PageHeader from '../components/common/PageHeader';
import Card from '../components/common/Card';
import DataTable from '../components/common/DataTable';
import Pagination from '../components/common/Pagination';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Badge from '../components/common/Badge';
import { FormInput, FormSelect } from '../components/common/FormField';
import RojmelFormModal from './RojmelFormModal';
import { useToast } from '../context/ToastContext';
import { fetchRojmels, createRojmel, updateRojmel, deleteRojmel, fetchRojmelSummary } from '../services/rojmelService';
import { fetchParties } from '../services/partyService';
import { fetchBanks } from '../services/bankService';
import { fetchDoneByList } from '../services/doneByService';
import { extractErrorMessage } from '../services/api';
import { formatCurrency } from '../utils/calculations';
import './RojmelManagement.css';

const TXN_TYPE_TONE = { 'Cr Pay': 'green', 'Dr Pay': 'red', 'Cash/Bank': 'blue', JV: 'gray' };

export default function RojmelManagement() {
  const toast = useToast();
  const [summary, setSummary] = useState(null);

  const [parties, setParties] = useState([]);
  const [banks, setBanks] = useState([]);
  const [doneByList, setDoneByList] = useState([]);

  const [search, setSearch] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [partyFilter, setPartyFilter] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  const [selectedRojmel, setSelectedRojmel] = useState(null);
  const [restoredForm, setRestoredForm] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [rojmelToDelete, setRojmelToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Loads the dropdown/lookup lists once. Bank and Done By have no
  // management pages of their own yet, so these come straight from
  // their existing backend endpoints.
  useEffect(() => {
    fetchParties({}).then(setParties).catch(() => setParties([]));
    fetchBanks().then(setBanks).catch(() => setBanks([]));
    fetchDoneByList().then(setDoneByList).catch(() => setDoneByList([]));
  }, []);

  const partyMap = useMemo(() => Object.fromEntries(parties.map((p) => [p.id, p.name])), [parties]);
  const bankMap = useMemo(() => Object.fromEntries(banks.map((b) => [b.id, b.name])), [banks]);
  const doneByMap = useMemo(() => Object.fromEntries(doneByList.map((d) => [d.id, d.name])), [doneByList]);

  const { items: rojmels, loading, reload: loadRojmels, pagination } = useHistoryPage(
    fetchRojmels, { search, startDate, endDate, partyId: partyFilter },
  );

  // Totals cover every matching receipt, not just the current page, so
  // this only needs to refetch on filter changes -- not on page changes.
  useEffect(() => {
    fetchRojmelSummary({ search, startDate, endDate, partyId: partyFilter })
      .then(setSummary)
      .catch((err) => toast.error(extractErrorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, startDate, endDate, partyFilter]);

  const openAddModal = () => {
    setModalMode('add');
    setSelectedRojmel(null);
    setRestoredForm(null);
    setModalOpen(true);
  };

  const openEditModal = (rojmel) => {
    setModalMode('edit');
    setSelectedRojmel(rojmel);
    setRestoredForm(null);
    setModalOpen(true);
  };

  const managed = useManagedOrigin(
    () => null,
    (draft) => {
      setModalMode(draft.mode); setSelectedRojmel(draft.selectedRojmel);
      setRestoredForm(draft.form); setModalOpen(true);
    },
    (entity, record) => {
      if (entity === 'account') setRestoredForm((form) => ({ ...form,
        ...accountSelectionFields({ source: record.source, value: record.id }),
        accountType: record.accountType, _account: record,
      }));
      if (entity === 'bank') {
        setBanks((rows) => [...rows, record]);
        setRestoredForm((form) => ({ ...form, cash_bank_id: record.id }));
      }
      if (entity === 'doneBy') {
        setDoneByList((rows) => [...rows, record]);
        setRestoredForm((form) => ({ ...form, done_by_id: record.id }));
      }
    },
  );
  const addRelated = (entity, form) => managed.begin(entity,
    { accountType: form.accountType, source: ['Cr Pay', 'Dr Pay'].includes(form.transaction_type) ? undefined : 'party' },
    { mode: modalMode, selectedRojmel, form });

  const refreshSummary = () => {
    fetchRojmelSummary({ search, startDate, endDate, partyId: partyFilter })
      .then(setSummary)
      .catch((err) => toast.error(extractErrorMessage(err)));
  };

  // Creates or updates a receipt depending on the modal mode, then reloads the current page.
  const handleFormSubmit = (payload) => {
    setSubmitting(true);
    const request = modalMode === 'edit' ? updateRojmel(selectedRojmel.id, payload) : createRojmel(payload);

    request
      .then(() => {
        toast.success(modalMode === 'edit' ? 'Receipt updated successfully.' : 'Receipt added successfully.');
        setModalOpen(false);
        setRestoredForm(null);
        loadRojmels();
        refreshSummary();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setSubmitting(false));
  };

  const askDelete = (rojmel) => {
    setRojmelToDelete(rojmel);
    setConfirmOpen(true);
  };

  // Permanently deletes the receipt (hard delete -- no undo) and reloads the current page.
  const confirmDelete = () => {
    setDeleting(true);
    deleteRojmel(rojmelToDelete.id)
      .then(() => {
        toast.success(`Receipt ${rojmelToDelete.receipt_no} permanently deleted.`);
        setConfirmOpen(false);
        setRojmelToDelete(null);
        loadRojmels();
        refreshSummary();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  const partyFilterOptions = [{ value: '', label: 'All Parties' }, ...parties.map((p) => ({ value: String(p.id), label: p.name }))];

  const columns = [
    { key: 'receipt_no', label: 'Receipt No.', width: 140, render: (row) => <strong className="rojmel-receipt">{row.receipt_no}</strong> },
    { key: 'effective_date', label: 'Date', width: 110 },
    { key: 'transaction_type', label: 'Type', width: 100, render: (row) => <Badge tone={TXN_TYPE_TONE[row.transaction_type] || 'gray'}>{row.transaction_type}</Badge> },
    { key: 'party', label: 'Party', render: (row) => (row.party_id ? partyMap[row.party_id] || `#${row.party_id}` : '—') },
    { key: 'cash_bank', label: 'Cash/Bank', render: (row) => bankMap[row.cash_bank_id] || `#${row.cash_bank_id}` },
    { key: 'done_by', label: 'Done By', render: (row) => doneByMap[row.done_by_id] || `#${row.done_by_id}` },
    { key: 'pay_mode', label: 'Mode', width: 90 },
    { key: 'net_amount', label: 'Net Amount', align: 'right', width: 120, render: (row) => <strong className="rojmel-amount">{formatCurrency(row.net_amount)}</strong> },
  ];

  const net = Number(summary?.net_earning);
  const netTone = net > 0 ? 'positive' : net < 0 ? 'negative' : 'neutral';

  return (
    <div className="page rojmel-page">
      <PageHeader
        title="Rojmel"
        subtitle="Daily cash/bank ledger of receipts and payments"
        onAddClick={openAddModal}
        addLabel="New Entry"
      />

      {summary && (
        <section className="rojmel-summary" aria-label="Financial summary for all matching entries">
          <Card className="rojmel-summary__card">
            <span className="rojmel-summary__label">Total Received</span>
            <strong className="rojmel-summary__value rojmel-summary__value--positive">{formatCurrency(summary.total_received)}</strong>
            <span className="rojmel-summary__hint">Receipts · Cr Pay</span>
          </Card>
          <Card className="rojmel-summary__card">
            <span className="rojmel-summary__label">Total Paid</span>
            <strong className="rojmel-summary__value rojmel-summary__value--negative">{formatCurrency(summary.total_paid)}</strong>
            <span className="rojmel-summary__hint">Payments · Dr Pay</span>
          </Card>
          <Card className="rojmel-summary__card rojmel-summary__card--net">
            <span className="rojmel-summary__label">Net Cash Flow</span>
            <strong className={`rojmel-summary__value rojmel-summary__value--${netTone}`}>{formatCurrency(summary.net_earning)}</strong>
            <span className="rojmel-summary__hint">{net > 0 ? 'Positive' : net < 0 ? 'Negative' : 'Zero'} · Received minus paid</span>
          </Card>
        </section>
      )}

      <Card className="rojmel-filters">
        <div className="rojmel-filters__search">
          <FormInput label="Search" name="rojmel_search" value={search} onChange={setSearch} placeholder="Receipt no., payment for, remarks…" />
          {search && <button type="button" className="rojmel-filters__clear" onClick={() => setSearch('')} aria-label="Clear search">×</button>}
        </div>
        <FormInput label="From date" name="start_date" type="date" value={startDate} onChange={setStartDate} />
        <FormInput label="To date" name="end_date" type="date" value={endDate} onChange={setEndDate} />
        <FormSelect label="Party" name="party_filter" value={partyFilter} onChange={setPartyFilter} options={partyFilterOptions} />
      </Card>

      <div className="rojmel-transactions-heading">
        <h2>Transactions</h2>
        <p>Summary totals cover all matching entries.</p>
      </div>
      <DataTable
        columns={columns}
        rows={rojmels}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage={<div className="rojmel-empty"><strong>No Rojmel entries found.</strong><span>Try changing your search or filters.</span></div>}
      />

      <Pagination {...pagination} />

      <RojmelFormModal
        open={modalOpen}
        mode={modalMode}
        initialData={selectedRojmel}
        restoredForm={restoredForm}
        banks={banks}
        doneByList={doneByList}
        submitting={submitting}
        onClose={() => {
          setModalOpen(false);
          setRestoredForm(null);
        }}
        onSubmit={handleFormSubmit}
        onAddParty={(form) => addRelated('account', form)}
        onAddBank={(form) => addRelated('bank', form)}
        onAddDoneBy={(form) => addRelated('doneBy', form)}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Delete Receipt Permanently"
        message={`This will permanently delete receipt "${rojmelToDelete?.receipt_no}". This cannot be undone.`}
        confirmLabel="Delete Permanently"
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
