import { safeOrigin } from '../utils/draftStorage';
import { useManagedDestination } from '../hooks/useManagedCreate';
import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Badge from '../components/common/Badge';
import PartyFormModal from './PartyFormModal';
import AccountSettlementModal from './AccountSettlementModal';
import { useToast } from '../context/ToastContext';
import {
  fetchUnifiedAccounts,
  fetchUnifiedAccountById,
  saveUnifiedAccount,
  deleteUnifiedAccount,
} from '../services/unifiedAccountService';
import useHistoryPage from '../hooks/useHistoryPage';
import Pagination from '../components/common/Pagination';
import { FormSelect } from '../components/common/FormField';
import { extractErrorMessage } from '../services/api';
import { formatPhoneNumber } from '../utils/calculations';
import './PartyManagement.css';

const ACCOUNT_FILTER_OPTIONS = [
  { value: 'ALL', label: 'All Accounts' },
  { value: 'CUSTOMER', label: 'Customers' },
  { value: 'SUPPLIER', label: 'Suppliers' },
  { value: 'PURCHASE_VENDOR', label: 'Purchase Accounts' },
];

export default function PartyManagement({ legacyCustomer = false }) {
  const managedCreate = useManagedDestination('account');
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Resolve selected filter
  const rawParam = searchParams.get('accountType');
  const selectedType = managedCreate.context.accountType || (legacyCustomer ? 'CUSTOMER' : rawParam || 'ALL');

  const returnTo = safeOrigin(searchParams.get('returnTo')) ? searchParams.get('returnTo') : null;
  const shouldOpenAdd = managedCreate.active || searchParams.get('openAdd') === '1';

  const [search, setSearch] = useState('');

  // Modals state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add'); // 'add' | 'edit'
  const [selectedParty, setSelectedParty] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [settlementOpen, setSettlementOpen] = useState(false);
  const [settlementAccount, setSettlementAccount] = useState(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [partyToDelete, setPartyToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Fetch accounts with pagination and search
  const { items: accounts, loading, reload: loadAccounts, pagination } = useHistoryPage(
    fetchUnifiedAccounts,
    {
      role: selectedType === 'ALL' ? undefined : selectedType,
      search,
    }
  );

  const openAddModal = () => {
    setModalMode('add');
    setSelectedParty(null);
    setModalOpen(true);
  };

  useEffect(() => {
    if (shouldOpenAdd) openAddModal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldOpenAdd]);

  const openEditModal = (account) => {
    fetchUnifiedAccountById(account.id)
      .then((full) => {
        setModalMode('edit');
        setSelectedParty(full);
        setModalOpen(true);
      })
      .catch((err) => toast.error(extractErrorMessage(err)));
  };

  const openSettlement = (account) => {
    setSettlementAccount(account);
    setSettlementOpen(true);
  };

  const handleFormSubmit = (payload) => {
    setSubmitting(true);
    saveUnifiedAccount(payload, modalMode === 'edit' ? selectedParty : null)
      .then((savedParty) => {
        toast.success(modalMode === 'edit' ? 'Account updated successfully.' : 'Account added successfully.');
        if (modalMode === 'add' && managedCreate.finish(savedParty)) return;
        setModalOpen(false);
        loadAccounts();

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
    deleteUnifiedAccount(partyToDelete.id)
      .then(() => {
        toast.success(`"${partyToDelete.account_name || partyToDelete.name}" deleted successfully.`);
        setConfirmOpen(false);
        setPartyToDelete(null);
        loadAccounts();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setDeleting(false));
  };

  if (legacyCustomer) {
    const params = new URLSearchParams(searchParams);
    params.set('accountType', 'CUSTOMER');
    return <Navigate replace to={`/parties?${params}`} />;
  }

  // Count dual-role accounts on current page
  const dualRoleCount = accounts.filter((acc) => (acc.roles || []).length > 1).length;
  // Count accounts with active ledger balances
  const accountsWithBalance = accounts.filter((acc) =>
    (acc.roles || []).some((r) => Number(r.ledger?.current_balance ?? r.opening_balance ?? 0) > 0)
  ).length;

  const COLUMNS = [
    {
      key: 'name',
      label: 'Account / Party',
      render: (row) => {
        const roles = row.roles || [];
        return (
          <div className="account-name-cell">
            <div className="account-primary-name">{row.account_name || row.name}</div>
            <div className="account-badges-row">
              {row.account_code && <span className="account-code-chip">{row.account_code}</span>}
              {roles.map((r, i) => (
                <span
                  key={i}
                  className={`account-role-tag account-role-tag--${(r.role || '').toLowerCase()}`}
                >
                  {r.role === 'CUSTOMER' ? 'Customer' : r.role === 'SUPPLIER' ? 'Supplier' : 'Purchase'}
                </span>
              ))}
            </div>
          </div>
        );
      },
    },
    {
      key: 'mobile',
      label: 'Mobile',
      width: 160,
      render: (row) => formatPhoneNumber(row.mobile, row.country_code),
    },
    {
      key: 'location',
      label: 'Location',
      render: (row) => (
        <div className="account-location-cell">
          <div className="account-city-state">{[row.city, row.state].filter(Boolean).join(', ') || '—'}</div>
          {row.address && <div className="account-address-sub" title={row.address}>{row.address}</div>}
        </div>
      ),
    },
    {
      key: 'tax_ids',
      label: 'GSTIN / PAN',
      render: (row) => (
        <div className="account-tax-cell">
          {row.gstin ? <span className="account-gstin">{row.gstin}</span> : <span>—</span>}
          {row.pan_card && <span className="account-pan">PAN: {row.pan_card}</span>}
        </div>
      ),
    },
    {
      key: 'balances',
      label: 'Ledger Balances',
      render: (row) => {
        const roles = row.roles || [];
        if (roles.length === 0) {
          const bal = Number(row.opening_balance || 0);
          return (
            <span className="acc-bal-badge acc-bal-badge--zero">
              ₹{bal.toFixed(2)}
            </span>
          );
        }

        let totalRec = 0;
        let totalPay = 0;

        return (
          <div className="account-balances-cell">
            {roles.map((r, i) => {
              const ledger = r.ledger;
              const bal = Number(ledger?.current_balance ?? r.opening_balance ?? 0);
              const dir = ledger?.current_balance_type || r.balance_type;
              const isCust = r.role === 'CUSTOMER';

              if (isCust && dir === 'Debit') totalRec += bal;
              if (!isCust && dir === 'Credit') totalPay += bal;

              let toneClass = 'acc-bal-badge--zero';
              let dirText = 'Settled';

              if (bal > 0) {
                if (isCust) {
                  toneClass = dir === 'Debit' ? 'acc-bal-badge--receivable' : 'acc-bal-badge--advance';
                  dirText = dir === 'Debit' ? 'Receivable' : 'Advance';
                } else {
                  toneClass = dir === 'Credit' ? 'acc-bal-badge--payable' : 'acc-bal-badge--advance';
                  dirText = dir === 'Credit' ? 'Payable' : 'Advance';
                }
              }

              return (
                <div key={i} className="acc-bal-row">
                  <span className="acc-bal-role">{r.role === 'CUSTOMER' ? 'Cust:' : 'Supp:'}</span>
                  <span className={`acc-bal-badge ${toneClass}`}>
                    ₹{bal.toLocaleString('en-IN', { minimumFractionDigits: 2 })} {dir || ''} ({dirText})
                  </span>
                </div>
              );
            })}

            {roles.length > 1 && totalRec > 0 && totalPay > 0 && (
              <div className="acc-net-position-tag">
                ⚖️ Net: ₹{Math.abs(totalRec - totalPay).toLocaleString('en-IN', { minimumFractionDigits: 2 })}{' '}
                {totalRec > totalPay ? 'Receivable' : totalPay > totalRec ? 'Payable' : 'Settled'}
              </div>
            )}
          </div>
        );
      },
    },
    {
      key: 'settlement',
      label: 'Settlement',
      width: 120,
      render: (row) => {
        const isMulti = (row.roles || []).length > 1;
        return (
          <button
            type="button"
            className={`settlement-btn ${isMulti ? 'settlement-btn--highlight' : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              openSettlement(row);
            }}
            title="View consolidated settlement and apply contra offset"
          >
            ⚖️ Settlement
          </button>
        );
      },
    },
  ];

  return (
    <div className="page accounts-page">
      <PageHeader
        title="Accounts"
        subtitle="Manage customers, suppliers, and purchase vendors with unified ledgers and net settlement"
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Global search by party name, code (ACC-XXXX), city, address, mobile, or GSTIN..."
        extraActions={
          <FormSelect
            label="Account Filter"
            name="accountFilter"
            value={selectedType}
            options={ACCOUNT_FILTER_OPTIONS}
            onChange={(value) =>
              setSearchParams((previous) => {
                const next = new URLSearchParams(previous);
                if (value === 'ALL') next.delete('accountType');
                else next.set('accountType', value);
                return next;
              })
            }
          />
        }
        onAddClick={openAddModal}
        addLabel="Add Account"
      />

      {/* KPI Overview Ribbon */}
      <div className="accounts-kpi-ribbon">
        <div className="accounts-kpi-card">
          <div className="accounts-kpi-card__icon accounts-kpi-card__icon--total">📁</div>
          <div className="accounts-kpi-card__info">
            <span className="accounts-kpi-card__label">Total Accounts</span>
            <span className="accounts-kpi-card__value">{pagination.total}</span>
            <span className="accounts-kpi-card__sub">Across all categories</span>
          </div>
        </div>

        <div className="accounts-kpi-card">
          <div className="accounts-kpi-card__icon accounts-kpi-card__icon--customers">👤</div>
          <div className="accounts-kpi-card__info">
            <span className="accounts-kpi-card__label">Active Filter</span>
            <span className="accounts-kpi-card__value">
              {ACCOUNT_FILTER_OPTIONS.find((o) => o.value === selectedType)?.label || 'All'}
            </span>
            <span className="accounts-kpi-card__sub">Filtered view</span>
          </div>
        </div>

        <div className="accounts-kpi-card">
          <div className="accounts-kpi-card__icon accounts-kpi-card__icon--contra">⚖️</div>
          <div className="accounts-kpi-card__info">
            <span className="accounts-kpi-card__label">Dual Role Accounts</span>
            <span className="accounts-kpi-card__value">{dualRoleCount}</span>
            <span className="accounts-kpi-card__sub">Eligible for contra offset</span>
          </div>
        </div>

        <div className="accounts-kpi-card">
          <div className="accounts-kpi-card__icon accounts-kpi-card__icon--suppliers">💰</div>
          <div className="accounts-kpi-card__info">
            <span className="accounts-kpi-card__label">Active Balances</span>
            <span className="accounts-kpi-card__value">{accountsWithBalance}</span>
            <span className="accounts-kpi-card__sub">Accounts with dues / payables</span>
          </div>
        </div>
      </div>

      <DataTable
        columns={COLUMNS}
        rows={accounts}
        loading={loading}
        onEdit={openEditModal}
        onDelete={askDelete}
        emptyMessage={
          search
            ? `No accounts match "${search}". Try searching by party name, code, address, city, mobile, or GSTIN.`
            : 'No accounts found in this category. Click "+ Add Account" to create one.'
        }
      />

      <Pagination {...pagination} />

      {/* Multi-Role Account Create / Edit Modal */}
      <PartyFormModal
        unifiedAccounts
        sourceRestriction={managedCreate.context.source}
        defaultType={selectedType}
        open={modalOpen}
        mode={modalMode}
        initialData={selectedParty}
        submitting={submitting}
        onClose={() => {
          if (!managedCreate.finish()) setModalOpen(false);
        }}
        onSubmit={handleFormSubmit}
      />

      {/* Account Settlement & Contra Offset Modal */}
      <AccountSettlementModal
        open={settlementOpen}
        account={settlementAccount}
        onClose={() => {
          setSettlementOpen(false);
          setSettlementAccount(null);
        }}
        onSettlementApplied={() => {
          loadAccounts();
        }}
      />

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        title="Delete Account"
        message={`Are you sure you want to delete "${partyToDelete?.account_name || partyToDelete?.name}"? All associated ledgers and roles will be removed.`}
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
