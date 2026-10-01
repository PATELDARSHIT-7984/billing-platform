import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Badge from '../components/common/Badge';
import PartyFormModal from './PartyFormModal';
import { useToast } from '../context/ToastContext';
import { fetchParties, createParty, updateParty, deleteParty } from '../services/partyService';
import { extractErrorMessage } from '../services/api';

const COLUMNS = [
  { key: 'name', label: 'Party Name' },
  {
    key: 'party_type',
    label: 'Type',
    width: 110,
    render: (row) => <Badge tone={row.party_type === 'Customer' ? 'green' : 'blue'}>{row.party_type}</Badge>,
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

export default function PartyManagement() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // When arriving via a "+ Add Party" link from another page (e.g. Rojmel,
  // Purchase Entry), returnTo tells us where to send the user back to
  // after a successful save, with the new party's id attached.
  const returnTo = searchParams.get('returnTo');
  const shouldOpenAdd = searchParams.get('openAdd') === '1';

  const [parties, setParties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add'); // 'add' | 'edit'
  const [selectedParty, setSelectedParty] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [partyToDelete, setPartyToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadParties = useCallback((searchTerm) => {
    setLoading(true);
    fetchParties({ search: searchTerm })
      .then(setParties)
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initial load
  useEffect(() => {
    loadParties('');
  }, [loadParties]);

  // Debounced search — refetches from the backend's `search` query param
  useEffect(() => {
    const timer = setTimeout(() => loadParties(search), 350);
    return () => clearTimeout(timer);
  }, [search, loadParties]);

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
    setModalMode('edit');
    setSelectedParty(party);
    setModalOpen(true);
  };

  const handleFormSubmit = (payload) => {
    setSubmitting(true);
    const request = modalMode === 'edit'
      ? updateParty(selectedParty.id, payload)
      : createParty(payload);

    request
      .then((savedParty) => {
        toast.success(modalMode === 'edit' ? 'Party updated successfully.' : 'Party added successfully.');
        setModalOpen(false);
        loadParties(search);

        if (modalMode === 'add' && returnTo) {
          navigate(`${returnTo}?newPartyId=${savedParty.id}`);
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
    deleteParty(partyToDelete.id)
      .then(() => {
        toast.success(`"${partyToDelete.name}" deleted successfully.`);
        setConfirmOpen(false);
        setPartyToDelete(null);
        loadParties(search);
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  return (
    <div className="page">
      <PageHeader
        title="Accounts"
        subtitle="Manage suppliers and customers with opening balance"
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by name, mobile, city, GSTIN or PAN..."
        onAddClick={openAddModal}
        addLabel="Add Party"
      />

      <DataTable
        columns={COLUMNS}
        rows={parties}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage={search ? `No parties match "${search}".` : 'No parties added yet. Click "Add Party" to create one.'}
      />

      <PartyFormModal
        open={modalOpen}
        mode={modalMode}
        initialData={selectedParty}
        submitting={submitting}
        onClose={() => setModalOpen(false)}
        onSubmit={handleFormSubmit}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Delete Party"
        message={`Are you sure you want to delete "${partyToDelete?.name}"? This cannot be undone.`}
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
