import useHistoryPage from '../hooks/useHistoryPage';
import { useEffect, useState, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
import { saveDraft, loadDraft, clearDraft } from '../utils/draftStorage';
import './RojmelManagement.css';

const TXN_TYPE_TONE = { 'Cr Pay': 'green', 'Dr Pay': 'red', 'Cash/Bank': 'blue', JV: 'gray' };
const DRAFT_KEY = 'rojmel-entry';

export default function RojmelManagement() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Present when we've just been redirected back from "+ Add Party/Bank/
  // Done By" -- tells us which field to fill with the newly created id.
  const newPartyId = searchParams.get('newPartyId');
  const newCustomerId = searchParams.get('newCustomerId');
  const newBankId = searchParams.get('newBankId');
  const newDoneById = searchParams.get('newDoneById');

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

  // Reopens the modal with whatever was already typed when we redirected
  // to Party/Bank/Done By's own "+" entry page, plus the newly created id
  // dropped into the right field -- so the user never has to retype the
  // rest of the receipt.
  useEffect(() => {
    const newId = newPartyId || newCustomerId || newBankId || newDoneById;
    if (!newId) return;

    const draft = loadDraft(DRAFT_KEY);
    if (!draft) return;

    const form = { ...draft.form };
    if (newPartyId) { form.party_id = newPartyId; form.customer_id = ''; }
    if (newCustomerId) { form.customer_id = newCustomerId; form.party_id = ''; }
    if (newBankId) form.cash_bank_id = newBankId;
    if (newDoneById) form.done_by_id = newDoneById;

    setModalMode(draft.mode || 'add');
    setSelectedRojmel(draft.selectedRojmel || null);
    setRestoredForm(form);
    setModalOpen(true);
    clearDraft(DRAFT_KEY);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newPartyId, newCustomerId, newBankId, newDoneById]);

  // Saves the modal's current form plus enough context to reopen it
  // correctly (add vs. edit, and which receipt if editing), then sends
  // the user to the target entity's own entry page.
  const goAddRelated = (path, currentForm) => {
    saveDraft(DRAFT_KEY, { mode: modalMode, selectedRojmel, form: currentForm });
    const params = new URLSearchParams({ openAdd: '1', returnTo: '/rojmel' });
    if (path === '/parties' && currentForm.accountType) params.set('accountType', currentForm.accountType);
    navigate(`${path}?${params}`);
  };

  const handleAddParty = (currentForm) => goAddRelated('/parties', currentForm);
  const handleAddBank = (currentForm) => goAddRelated('/banks', currentForm);
  const handleAddDoneBy = (currentForm) => goAddRelated('/done-by', currentForm);


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
    { key: 'receipt_no', label: 'Receipt No.', width: 140 },
    { key: 'effective_date', label: 'Date', width: 110 },
    { key: 'transaction_type', label: 'Type', width: 100, render: (row) => <Badge tone={TXN_TYPE_TONE[row.transaction_type] || 'gray'}>{row.transaction_type}</Badge> },
    { key: 'party', label: 'Party', render: (row) => (row.party_id ? partyMap[row.party_id] || `#${row.party_id}` : '—') },
    { key: 'cash_bank', label: 'Cash/Bank', render: (row) => bankMap[row.cash_bank_id] || `#${row.cash_bank_id}` },
    { key: 'done_by', label: 'Done By', render: (row) => doneByMap[row.done_by_id] || `#${row.done_by_id}` },
    { key: 'pay_mode', label: 'Mode', width: 90 },
    { key: 'net_amount', label: 'Net Amount', align: 'right', width: 120, render: (row) => `₹${Number(row.net_amount || 0).toFixed(2)}` },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Rojmel"
        subtitle="Daily cash/bank ledger of receipts and payments"
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by receipt no, payment for, remarks..."
        onAddClick={openAddModal}
        addLabel="New Entry"
        extraActions={
          <div className="rojmel-filters">
            <FormInput name="start_date" type="date" value={startDate} onChange={setStartDate} placeholder="From" />
            <FormInput name="end_date" type="date" value={endDate} onChange={setEndDate} placeholder="To" />
            <FormSelect name="party_filter" value={partyFilter} onChange={setPartyFilter} options={partyFilterOptions} />
          </div>
        }
      />

      {summary && (
        <Card className="rojmel-summary">
          <div className="rojmel-summary__item">
            <span className="rojmel-summary__label">Total Received</span>
            <span className="rojmel-summary__value rojmel-summary__value--positive">₹{Number(summary.total_received).toFixed(2)}</span>
          </div>
          <div className="rojmel-summary__item">
            <span className="rojmel-summary__label">Total Paid</span>
            <span className="rojmel-summary__value rojmel-summary__value--negative">₹{Number(summary.total_paid).toFixed(2)}</span>
          </div>
          <div className="rojmel-summary__item rojmel-summary__item--net">
            <span className="rojmel-summary__label">Net Earning So Far</span>
            <span className={`rojmel-summary__value ${Number(summary.net_earning) >= 0 ? 'rojmel-summary__value--positive' : 'rojmel-summary__value--negative'}`}>
              ₹{Number(summary.net_earning).toFixed(2)}
            </span>
          </div>
        </Card>
      )}

      <DataTable
        columns={columns}
        rows={rojmels}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage="No rojmel entries match your filters."
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
        onAddParty={handleAddParty}
        onAddBank={handleAddBank}
        onAddDoneBy={handleAddDoneBy}
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
