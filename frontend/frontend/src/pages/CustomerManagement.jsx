import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Badge from '../components/common/Badge';
import CustomerFormModal from './CustomerFormModal';
import { useToast } from '../context/ToastContext';
import { fetchCustomers, fetchCustomerById, createCustomer, updateCustomer, deleteCustomer } from '../services/customerService';
import { extractErrorMessage } from '../services/api';

const COLUMNS = [
  { key: 'customer_name', label: 'Customer Name' },
  { key: 'mobile', label: 'Mobile' },
  {
    key: 'location',
    label: 'City / State',
    render: (row) => [row.city, row.state].filter(Boolean).join(', ') || '—',
  },
  { key: 'gstin', label: 'GSTIN', render: (row) => row.gstin || '—' },
  {
    key: 'is_active',
    label: 'Status',
    width: 100,
    render: (row) => <Badge tone={row.is_active ? 'green' : 'gray'}>{row.is_active ? 'Active' : 'Inactive'}</Badge>,
  },
];

export default function CustomerManagement() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const shouldOpenAdd = searchParams.get('openAdd') === '1';

  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [customerToDelete, setCustomerToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadCustomers = useCallback((searchTerm) => {
    setLoading(true);
    fetchCustomers({ search: searchTerm })
      .then(setCustomers)
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadCustomers('');
  }, [loadCustomers]);

  useEffect(() => {
    if (shouldOpenAdd) openAddModal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldOpenAdd]);

  useEffect(() => {
    const timer = setTimeout(() => loadCustomers(search), 350);
    return () => clearTimeout(timer);
  }, [search, loadCustomers]);

  const openAddModal = () => {
    setModalMode('add');
    setSelectedCustomer(null);
    setModalOpen(true);
  };

  // The Customer Management table uses the lean CustomerListResponse
  // (no address/pincode/pan/etc.), so Edit fetches the full record by id
  // first rather than trying to edit from the row's partial data.
  const openEditModal = (row) => {
    fetchCustomerById(row.id)
      .then((full) => {
        setModalMode('edit');
        setSelectedCustomer(full);
        setModalOpen(true);
      })
      .catch((err) => toast.error(extractErrorMessage(err)));
  };

  const handleFormSubmit = (payload) => {
    setSubmitting(true);
    const request = modalMode === 'edit'
      ? updateCustomer(selectedCustomer.id, payload)
      : createCustomer(payload);

    request
      .then((savedCustomer) => {
        toast.success(modalMode === 'edit' ? 'Customer updated successfully.' : 'Customer added successfully.');
        setModalOpen(false);
        loadCustomers(search);

        if (modalMode === 'add' && returnTo) {
          navigate(`${returnTo}?newCustomerId=${savedCustomer.id}`);
        }
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setSubmitting(false));
  };

  const askDelete = (customer) => {
    setCustomerToDelete(customer);
    setConfirmOpen(true);
  };

  const confirmDelete = () => {
    setDeleting(true);
    deleteCustomer(customerToDelete.id)
      .then(() => {
        toast.success(`"${customerToDelete.customer_name}" deleted successfully.`);
        setConfirmOpen(false);
        setCustomerToDelete(null);
        loadCustomers(search);
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  return (
    <div className="page">
      <PageHeader
        title="Customer Management"
        subtitle="Manage the customers you sell to."
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by name or mobile..."
        onAddClick={openAddModal}
        addLabel="Add Customer"
      />

      <DataTable
        columns={COLUMNS}
        rows={customers}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage={search ? `No customers match "${search}".` : 'No customers added yet. Click "Add Customer" to create one.'}
      />

      <CustomerFormModal
        open={modalOpen}
        mode={modalMode}
        initialData={selectedCustomer}
        submitting={submitting}
        onClose={() => setModalOpen(false)}
        onSubmit={handleFormSubmit}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Delete Customer"
        message={`Are you sure you want to delete "${customerToDelete?.customer_name}"? This cannot be undone.`}
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
