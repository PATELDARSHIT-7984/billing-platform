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
import { fetchDoneByList, createDoneBy, updateDoneBy, deleteDoneBy } from '../services/doneByService';
import { extractErrorMessage } from '../services/api';

const COLUMNS = [
  { key: 'name', label: 'Name' },
  {
    key: 'is_active',
    label: 'Status',
    width: 100,
    render: (row) => <Badge tone={row.is_active ? 'green' : 'gray'}>{row.is_active ? 'Active' : 'Inactive'}</Badge>,
  },
];

// Reached only via a "+" button next to a Done By dropdown (e.g. Rojmel) --
// there is deliberately no sidebar entry for this page.
export default function DoneByManagement() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const shouldOpenAdd = searchParams.get('openAdd') === '1';

  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [personToDelete, setPersonToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadPeople = useCallback(() => {
    setLoading(true);
    fetchDoneByList()
      .then(setPeople)
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadPeople();
  }, [loadPeople]);

  const openAddModal = () => {
    setModalMode('add');
    setSelectedPerson(null);
    setName('');
    setModalOpen(true);
  };

  // Opens the Add modal automatically if we were sent here via a "+" link.
  useEffect(() => {
    if (shouldOpenAdd) openAddModal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldOpenAdd]);

  const openEditModal = (person) => {
    setModalMode('edit');
    setSelectedPerson(person);
    setName(person.name);
    setModalOpen(true);
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    setSubmitting(true);
    const request = modalMode === 'edit'
      ? updateDoneBy(selectedPerson.id, { name: name.trim() })
      : createDoneBy({ name: name.trim() });

    request
      .then((savedPerson) => {
        toast.success(modalMode === 'edit' ? 'Updated successfully.' : 'Added successfully.');
        setModalOpen(false);
        loadPeople();

        if (modalMode === 'add' && returnTo) {
          navigate(`${returnTo}?newDoneById=${savedPerson.id}`);
        }
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setSubmitting(false));
  };

  const askDelete = (person) => {
    setPersonToDelete(person);
    setConfirmOpen(true);
  };

  const confirmDelete = () => {
    setDeleting(true);
    deleteDoneBy(personToDelete.id)
      .then(() => {
        toast.success(`"${personToDelete.name}" deactivated successfully.`);
        setConfirmOpen(false);
        setPersonToDelete(null);
        loadPeople();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  return (
    <div className="page">
      <PageHeader title="Done By" subtitle="People who can be recorded as handling a Rojmel entry." onAddClick={openAddModal} addLabel="Add Person" />

      <DataTable
        columns={COLUMNS}
        rows={people}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage='No entries yet. Click "Add Person" to create one.'
      />

      <Modal
        open={modalOpen}
        title={modalMode === 'edit' ? 'Edit Person' : 'Add Person'}
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
        <form onSubmit={handleFormSubmit} noValidate>
          <FormInput label="Name" name="name" value={name} onChange={setName} required autoFocus />
        </form>
      </Modal>

      <ConfirmDialog
        open={confirmOpen}
        title="Deactivate Person"
        message={`Are you sure you want to deactivate "${personToDelete?.name}"?`}
        confirmLabel="Deactivate"
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
