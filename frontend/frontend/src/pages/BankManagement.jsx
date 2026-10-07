import { handleEnterNavigation } from '../utils/enterNavigation';
import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Badge from '../components/common/Badge';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { FormInput } from '../components/common/FormField';
import { useToast } from '../context/ToastContext';
import { fetchBanks, createBank, updateBank, deleteBank } from '../services/bankService';
import { extractErrorMessage } from '../services/api';

const COLUMNS = [
  { key: 'name', label: 'Bank Name' },
  {
    key: 'is_active',
    label: 'Status',
    width: 100,
    render: (row) => <Badge tone={row.is_active ? 'green' : 'gray'}>{row.is_active ? 'Active' : 'Inactive'}</Badge>,
  },
];

// Reached only via a "+" button next to a Bank dropdown (e.g. Rojmel) --
// there is deliberately no sidebar entry for this page.
export default function BankManagement() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const shouldOpenAdd = searchParams.get('openAdd') === '1';

  const [banks, setBanks] = useState([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  const [selectedBank, setSelectedBank] = useState(null);
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [bankToDelete, setBankToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadBanks = useCallback(() => {
    setLoading(true);
    fetchBanks()
      .then(setBanks)
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadBanks();
  }, [loadBanks]);

  const openAddModal = () => {
    setModalMode('add');
    setSelectedBank(null);
    setName('');
    setModalOpen(true);
  };

  // Opens the Add modal automatically if we were sent here via a "+" link.
  useEffect(() => {
    if (shouldOpenAdd) openAddModal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldOpenAdd]);

  const openEditModal = (bank) => {
    setModalMode('edit');
    setSelectedBank(bank);
    setName(bank.name);
    setModalOpen(true);
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    setSubmitting(true);
    const request = modalMode === 'edit'
      ? updateBank(selectedBank.id, { name: name.trim() })
      : createBank({ name: name.trim() });

    request
      .then((savedBank) => {
        toast.success(modalMode === 'edit' ? 'Bank updated successfully.' : 'Bank added successfully.');
        setModalOpen(false);
        loadBanks();

        if (modalMode === 'add' && returnTo) {
          navigate(`${returnTo}?newBankId=${savedBank.id}`);
        }
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setSubmitting(false));
  };

  const askDelete = (bank) => {
    setBankToDelete(bank);
    setConfirmOpen(true);
  };

  const confirmDelete = () => {
    setDeleting(true);
    deleteBank(bankToDelete.id)
      .then(() => {
        toast.success(`"${bankToDelete.name}" deactivated successfully.`);
        setConfirmOpen(false);
        setBankToDelete(null);
        loadBanks();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  return (
    <div className="page">
      <PageHeader title="Banks" subtitle="Cash/Bank accounts used for Rojmel entries." onAddClick={openAddModal} addLabel="Add Bank" />

      <DataTable
        columns={COLUMNS}
        rows={banks}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage='No banks added yet. Click "Add Bank" to create one.'
      />

      <Modal
        open={modalOpen}
        title={modalMode === 'edit' ? 'Edit Bank' : 'Add Bank'}
        onClose={() => setModalOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)} disabled={submitting}>Cancel</Button>
            <Button variant="primary" onClick={handleFormSubmit} disabled={submitting}>
              {submitting ? 'Saving...' : 'Save'}
            </Button>
          </>
        }
      >
        <form data-enter-navigation onKeyDown={handleEnterNavigation} onSubmit={handleFormSubmit} noValidate>
          <FormInput label="Bank Name" name="name" value={name} onChange={setName} required autoFocus />
        </form>
      </Modal>

      <ConfirmDialog
        open={confirmOpen}
        title="Deactivate Bank"
        message={`Are you sure you want to deactivate "${bankToDelete?.name}"?`}
        confirmLabel="Deactivate"
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
