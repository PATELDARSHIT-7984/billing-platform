import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Badge from '../components/common/Badge';
import PartyFormModal from './PartyFormModal';
import { useToast } from '../context/ToastContext';
import { ACCOUNT_TYPES, accountType, fetchAccounts, fetchAccountForEdit, saveAccount, deleteAccount } from '../services/accountService';
import useHistoryPage from '../hooks/useHistoryPage';
import Pagination from '../components/common/Pagination';
import { FormSelect } from '../components/common/FormField';
import { extractErrorMessage } from '../services/api';

const COLUMNS = [
  { key: 'name', label: 'Party Name' },
  {
    key: 'party_type',
    label: 'Type',
    width: 110,
    render: (row) => <Badge tone={row.source === 'customer' ? 'green' : 'blue'}>{accountType(row.accountType).label}</Badge>,
  },
  { key: 'mobile', label: 'Mobile', render: (row) => row.mobile ? `${row.country_code || ''} ${row.mobile}`.trim() : '—' },
  {
    key: 'location',
    label: 'City / State',
    render: (row) => [row.city, row.state].filter(Boolean).join(', ') || '—',
  },
  { key: 'gstin', label: 'GSTIN', render: (row) => row.gstin || '—' },
  { key: 'pan_card', label: 'PAN', render: (row) => row.pan_card || '—' },
  {
    key: 'opening_balance',
    label: 'Opening',
    render: (row) => `${row.balance_type || 'Credit'} ₹${Number(row.opening_balance || 0).toFixed(2)}`,
  },
];

export default function PartyManagement({ legacyCustomer = false }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedType = accountType(legacyCustomer ? 'CUSTOMER' : searchParams.get('accountType')).value;
  // When arriving via a "+ Add Party" link from another page (e.g. Rojmel,
  // Purchase Entry), returnTo tells us where to send the user back to
  // after a successful save, with the new party's id attached.
  const returnTo = searchParams.get('returnTo');
  const shouldOpenAdd = searchParams.get('openAdd') === '1';

  const [search, setSearch] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add'); // 'add' | 'edit'
  const [selectedParty, setSelectedParty] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [partyToDelete, setPartyToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const { items: parties, loading, reload: loadParties, pagination } = useHistoryPage(fetchAccounts, { accountType: selectedType, search });

  const openAddModal = () => {
    setModalMode('add');
    setSelectedParty(null);
    setModalOpen(true);
  };

  // Opens the Add modal automatically if we were sent here via a "+" link.
  useEffect(() => {
    if (shouldOpenAdd) openAddModal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldOpenAdd]);

  const openEditModal = (party) => {
    fetchAccountForEdit(party).then((full) => {
      setModalMode('edit');
      setSelectedParty(full);
      setModalOpen(true);
    }).catch((err) => toast.error(extractErrorMessage(err)));
  };

  const handleFormSubmit = (payload) => {
    setSubmitting(true);
    const request = saveAccount(payload, modalMode === 'edit' ? selectedParty : null);

    request
      .then((savedParty) => {
        toast.success(modalMode === 'edit' ? 'Account updated successfully.' : 'Account added successfully.');
        setModalOpen(false);
        if (savedParty.accountType !== selectedType) {
          setSearchParams((previous) => {
            const next = new URLSearchParams(previous);
            next.set('accountType', savedParty.accountType);
            return next;
          });
        } else loadParties();

        if (modalMode === 'add' && returnTo) {
          const target = new URL(returnTo, window.location.origin);
          if (target.origin === window.location.origin) {
            target.searchParams.set(savedParty.source === 'customer' ? 'newCustomerId' : 'newPartyId', savedParty.id);
            navigate(target.pathname + target.search);
          }
        }
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setSubmitting(false));
  };

  const askDelete = (party) => {
    setPartyToDelete(party);
    setConfirmOpen(true);
  };

  const confirmDelete = () => {
    setDeleting(true);
    deleteAccount(partyToDelete)
      .then(() => {
        toast.success(`"${partyToDelete.name}" deleted successfully.`);
        setConfirmOpen(false);
        setPartyToDelete(null);
        loadParties();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  if (legacyCustomer) {
    const params = new URLSearchParams(searchParams);
    params.set('accountType', 'CUSTOMER');
    return <Navigate replace to={`/parties?${params}`} />;
  }

  return (
    <div className="page">
      <PageHeader
        title="Accounts"
        subtitle="Manage customers, suppliers and purchase accounts with opening balance"
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={selectedType === 'CUSTOMER' ? 'Search by name, code or mobile...' : 'Search by name, mobile, city, GSTIN or PAN...'}
        extraActions={<FormSelect label="Account Type" name="accountFilter" value={selectedType} options={ACCOUNT_TYPES}
          onChange={(value) => setSearchParams((previous) => {
            const next = new URLSearchParams(previous);
            next.set('accountType', value);
            return next;
          })} />}
        onAddClick={openAddModal}
        addLabel="Add Account"
      />

      <DataTable
        columns={COLUMNS}
        rows={parties}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage={search ? `No accounts match "${search}".` : 'No accounts added yet. Click "Add Account" to create one.'}
      />

      <Pagination {...pagination} />

      <PartyFormModal
        unifiedAccounts
        defaultType={selectedType}
        open={modalOpen}
        mode={modalMode}
        initialData={selectedParty}
        submitting={submitting}
        onClose={() => setModalOpen(false)}
        onSubmit={handleFormSubmit}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Delete Account"
        message={`Are you sure you want to delete "${partyToDelete?.name}"? This cannot be undone.`}
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
