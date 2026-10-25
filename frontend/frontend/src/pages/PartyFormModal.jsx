import { ACCOUNT_TYPES, accountType, buildAccountPayload } from '../services/accountService';
import { validateCustomer } from '../utils/customerValidation';
import { handleEnterNavigation } from '../utils/enterNavigation';
import { useEffect, useState } from 'react';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { FormInput, FormSelect, FormTextarea, FormRow } from '../components/common/FormField';
import './PartyFormModal.css';

const COUNTRY_CODE_OPTIONS = [
  { value: '+91', label: '🇮🇳 +91' },
  { value: '+1', label: '🇺🇸 +1' },
  { value: '+44', label: '🇬🇧 +44' },
  { value: '+61', label: '🇦🇺 +61' },
  { value: '+971', label: '🇦🇪 +971' },
  { value: '+211', label: '🇸🇸 +211' },
];

const STATE_OPTIONS = [
  { value: '', label: 'Select State' },
  { value: 'Andhra Pradesh', label: 'Andhra Pradesh' },
  { value: 'Arunachal Pradesh', label: 'Arunachal Pradesh' },
  { value: 'Assam', label: 'Assam' },
  { value: 'Bihar', label: 'Bihar' },
  { value: 'Chhattisgarh', label: 'Chhattisgarh' },
  { value: 'Goa', label: 'Goa' },
  { value: 'Gujarat', label: 'Gujarat' },
  { value: 'Haryana', label: 'Haryana' },
  { value: 'Himachal Pradesh', label: 'Himachal Pradesh' },
  { value: 'Jharkhand', label: 'Jharkhand' },
  { value: 'Karnataka', label: 'Karnataka' },
  { value: 'Kerala', label: 'Kerala' },
  { value: 'Madhya Pradesh', label: 'Madhya Pradesh' },
  { value: 'Maharashtra', label: 'Maharashtra' },
  { value: 'Manipur', label: 'Manipur' },
  { value: 'Meghalaya', label: 'Meghalaya' },
  { value: 'Mizoram', label: 'Mizoram' },
  { value: 'Nagaland', label: 'Nagaland' },
  { value: 'Odisha', label: 'Odisha' },
  { value: 'Punjab', label: 'Punjab' },
  { value: 'Rajasthan', label: 'Rajasthan' },
  { value: 'Sikkim', label: 'Sikkim' },
  { value: 'Tamil Nadu', label: 'Tamil Nadu' },
  { value: 'Telangana', label: 'Telangana' },
  { value: 'Tripura', label: 'Tripura' },
  { value: 'Uttar Pradesh', label: 'Uttar Pradesh' },
  { value: 'Uttarakhand', label: 'Uttarakhand' },
  { value: 'West Bengal', label: 'West Bengal' },
  { value: 'Andaman and Nicobar Islands', label: 'Andaman and Nicobar Islands' },
  { value: 'Chandigarh', label: 'Chandigarh' },
  { value: 'Dadra and Nagar Haveli and Daman and Diu', label: 'Dadra and Nagar Haveli and Daman and Diu' },
  { value: 'Delhi', label: 'Delhi' },
  { value: 'Jammu and Kashmir', label: 'Jammu and Kashmir' },
  { value: 'Ladakh', label: 'Ladakh' },
  { value: 'Lakshadweep', label: 'Lakshadweep' },
  { value: 'Puducherry', label: 'Puducherry' },
];

const ROLE_OPTIONS = [
  { value: 'CUSTOMER', label: 'Customer (Buyer / Debtor)' },
  { value: 'SUPPLIER', label: 'Supplier (Vendor / Creditor)' },
  { value: 'PURCHASE_VENDOR', label: 'Purchase Account (Direct Vendor)' },
];

const EMPTY_ROLE_ROW = (role = 'CUSTOMER') => ({
  id: Math.random().toString(36).substring(2, 9),
  role,
  opening_balance: '',
  balance_type: 'Credit',
  opening_remark: '',
  isExisting: false,
});

const EMPTY_FORM = {
  name: '',
  accountType: 'SUPPLIER',
  country_code: '+91',
  mobile: '',
  address: '',
  city: '',
  state: '',
  gstin: '',
  pan_card: '',
  remarks: '',
  roles: [EMPTY_ROLE_ROW('CUSTOMER')],
};

function extractPanFromGstin(gstin) {
  const cleanGstin = (gstin || '').trim().toUpperCase();
  return cleanGstin.length >= 12 ? cleanGstin.slice(2, 12) : '';
}

function validate(form, unifiedAccounts) {
  const errors = {};
  const trimmedName = form.name.trim();

  if (!trimmedName) errors.name = 'Name is required.';
  else if (trimmedName.length < 2) errors.name = 'Name must be at least 2 characters.';
  else if (trimmedName.length > 200) errors.name = 'Name must be under 200 characters.';

  if (!form.country_code) errors.country_code = 'Country code is required.';
  if (!form.state) errors.state = 'State is required.';

  if (form.gstin && form.gstin.trim().length !== 15) errors.gstin = 'GSTIN must be exactly 15 characters.';
  if (form.pan_card && form.pan_card.trim().length !== 10) errors.pan_card = 'PAN must be exactly 10 characters.';

  // Role validation
  if (!form.roles || form.roles.length === 0) {
    errors.roles = 'At least one account role is required.';
  } else {
    const roleSet = new Set();
    const roleErrors = [];
    form.roles.forEach((r, idx) => {
      const err = {};
      if (!r.role) err.role = 'Role is required.';
      if (roleSet.has(r.role)) err.role = `Role is duplicated.`;
      roleSet.add(r.role);

      if (r.opening_balance !== '' && Number.isNaN(Number(r.opening_balance))) {
        err.opening_balance = 'Opening balance must be a valid amount.';
      } else if (Number(r.opening_balance) < 0) {
        err.opening_balance = 'Opening balance cannot be negative.';
      }
      if (Object.keys(err).length > 0) {
        roleErrors[idx] = err;
      }
    });
    if (roleErrors.length > 0) {
      errors.roleErrors = roleErrors;
    }
  }

  if (unifiedAccounts && form.roles.some((r) => r.role === 'CUSTOMER')) {
    const customerErrors = validateCustomer({ ...form, customer_name: form.name });
    if (customerErrors.customer_name) {
      customerErrors.name = customerErrors.customer_name;
      delete customerErrors.customer_name;
    }
    Object.assign(errors, customerErrors);
  }
  return errors;
}

export default function PartyFormModal({
  open,
  mode = 'add',
  initialData = null,
  defaultType = 'SUPPLIER',
  unifiedAccounts = false,
  sourceRestriction,
  onClose,
  onSubmit,
  submitting,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && initialData) {
      const existingRoles = Array.isArray(initialData.roles) && initialData.roles.length > 0
        ? initialData.roles.map((r) => ({
            id: String(r.id || Math.random().toString(36).substring(2, 9)),
            role: r.role,
            opening_balance: r.ledger?.opening_balance != null
              ? String(r.ledger.opening_balance)
              : (r.opening_balance != null ? String(r.opening_balance) : ''),
            balance_type: r.ledger?.balance_type || r.balance_type || 'Credit',
            opening_remark: r.ledger?.opening_remark || r.opening_remark || '',
            isExisting: true,
          }))
        : [
            {
              id: 'init-0',
              role: initialData.accountType || (initialData.party_type === 'Customer' ? 'CUSTOMER' : 'SUPPLIER'),
              opening_balance: initialData.opening_balance != null ? String(initialData.opening_balance) : '',
              balance_type: initialData.balance_type || 'Credit',
              opening_remark: initialData.opening_remark || '',
              isExisting: true,
            },
          ];

      setForm({
        name: initialData.account_name || initialData.name || initialData.customer_name || '',
        accountType: initialData.accountType || existingRoles[0]?.role || 'SUPPLIER',
        country_code: initialData.country_code || '+91',
        mobile: initialData.mobile || '',
        address: initialData.address || '',
        city: initialData.city || '',
        state: initialData.state || '',
        gstin: initialData.gstin || '',
        pan_card: initialData.pan_card || '',
        remarks: initialData.remarks || initialData.opening_remark || '',
        roles: existingRoles,
      });
    } else {
      const initRole = (defaultType && defaultType !== 'ALL') ? defaultType : 'CUSTOMER';
      setForm({
        ...EMPTY_FORM,
        accountType: initRole,
        roles: [EMPTY_ROLE_ROW(initRole)],
      });
    }
    setErrors({});
  }, [open, mode, initialData, defaultType]);

  const setField = (field) => (value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const handleGstinChange = (value) => {
    const gstin = value.toUpperCase();
    setForm((prev) => ({ ...prev, gstin, pan_card: extractPanFromGstin(gstin) || prev.pan_card }));
    if (errors.gstin || errors.pan_card) setErrors((prev) => ({ ...prev, gstin: '', pan_card: '' }));
  };

  const handleAddRoleRow = () => {
    const currentRoles = form.roles.map((r) => r.role);
    const available = ['CUSTOMER', 'SUPPLIER', 'PURCHASE_VENDOR'].filter((r) => !currentRoles.includes(r));
    const nextRole = available[0] || 'CUSTOMER';
    setForm((prev) => ({
      ...prev,
      roles: [...prev.roles, EMPTY_ROLE_ROW(nextRole)],
    }));
  };

  const handleRemoveRoleRow = (index) => {
    if (form.roles.length <= 1) return;
    setForm((prev) => ({
      ...prev,
      roles: prev.roles.filter((_, i) => i !== index),
    }));
    if (errors.roleErrors) {
      setErrors((prev) => ({
        ...prev,
        roleErrors: prev.roleErrors ? prev.roleErrors.filter((_, i) => i !== index) : [],
      }));
    }
  };

  const handleRoleFieldChange = (index, field, value) => {
    setForm((prev) => {
      const updated = [...prev.roles];
      updated[index] = { ...updated[index], [field]: value };
      return { ...prev, roles: updated };
    });
    if (errors.roleErrors && errors.roleErrors[index]?.[field]) {
      setErrors((prev) => {
        const nextRoleErrors = [...(prev.roleErrors || [])];
        if (nextRoleErrors[index]) {
          nextRoleErrors[index] = { ...nextRoleErrors[index], [field]: '' };
        }
        return { ...prev, roleErrors: nextRoleErrors };
      });
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const validationErrors = validate(form, unifiedAccounts);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    if (unifiedAccounts) {
      const payload = {
        name: form.name.trim(),
        account_name: form.name.trim(),
        country_code: form.country_code || '+91',
        mobile: form.mobile?.trim() || null,
        address: form.address?.trim() || null,
        city: form.city?.trim() || null,
        state: form.state || null,
        gstin: form.gstin?.trim().toUpperCase() || null,
        pan_card: form.pan_card?.trim().toUpperCase() || null,
        remarks: form.remarks?.trim() || null,
        roles: form.roles.map((r) => {
          const bal = Number(r.opening_balance || 0);
          return {
            role: r.role,
            opening_balance: bal === 0 ? '0.00' : String(r.opening_balance).trim(),
            balance_type: bal > 0 ? (r.balance_type || 'Credit') : null,
            opening_remark: r.opening_remark?.trim() || null,
          };
        }),
        accountType: form.roles[0]?.role || 'SUPPLIER',
        opening_balance: form.roles[0]?.opening_balance ?? '',
        balance_type: form.roles[0]?.balance_type || 'Credit',
        opening_remark: form.roles[0]?.opening_remark || '',
      };
      onSubmit(payload);
    } else {
      const primaryRole = form.roles[0] || {};
      const legacyForm = {
        ...form,
        accountType: primaryRole.role || form.accountType || 'SUPPLIER',
        opening_balance: primaryRole.opening_balance ?? '',
        balance_type: primaryRole.balance_type || 'Credit',
        opening_remark: primaryRole.opening_remark || '',
      };
      onSubmit({
        ...buildAccountPayload('SUPPLIER', legacyForm),
        party_type: accountType(legacyForm.accountType).label,
      });
    }
  };

  return (
    <Modal
      open={open}
      title={
        mode === 'edit'
          ? (unifiedAccounts ? 'Edit Account' : 'Edit Party')
          : (unifiedAccounts ? 'Add New Account' : 'Add New Party')
      }
      onClose={onClose}
      width={760}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Saving...' : mode === 'edit' ? 'Save Changes' : (unifiedAccounts ? 'Add Account' : 'Add Party')}
          </Button>
        </>
      }
    >
      <form data-enter-navigation onKeyDown={handleEnterNavigation} className="party-form" onSubmit={handleSubmit} noValidate>
        {/* Profile Details */}
        <div className="party-section">
          <div className="party-section__title">Basic Profile</div>
          <FormRow>
            <FormInput
              label="Party / Account Name"
              name="name"
              value={form.name}
              onChange={setField('name')}
              required
              error={errors.name}
              autoFocus
              placeholder="Enter full party or business name"
            />
          </FormRow>

          <div className="party-contact-row">
            <div className="party-country-code">
              <FormSelect
                label="Country Code"
                name="country_code"
                value={form.country_code}
                onChange={setField('country_code')}
                options={COUNTRY_CODE_OPTIONS}
                required
                error={errors.country_code}
              />
            </div>
            <div className="party-mobile-field">
              <FormInput
                label="Mobile Number"
                name="mobile"
                value={form.mobile}
                onChange={setField('mobile')}
                placeholder="Enter 10-digit mobile number"
                error={errors.mobile}
              />
            </div>
          </div>

          <FormRow>
            <FormInput
              label="City"
              name="city"
              value={form.city}
              onChange={setField('city')}
              placeholder="Enter city"
              error={errors.city}
            />
            <FormSelect
              label="State"
              name="state"
              value={form.state}
              onChange={setField('state')}
              options={STATE_OPTIONS}
              required
              error={errors.state}
            />
          </FormRow>

          <FormTextarea
            label="Address"
            name="address"
            value={form.address}
            onChange={setField('address')}
            rows={2}
            placeholder="Enter street address, building, or area"
            error={errors.address}
          />

          <FormRow>
            <FormInput
              label="GSTIN"
              name="gstin"
              value={form.gstin}
              onChange={handleGstinChange}
              error={errors.gstin}
              maxLength={15}
              placeholder="15-character GSTIN"
            />
            <FormInput
              label="PAN Card"
              name="pan_card"
              value={form.pan_card}
              onChange={(v) => setField('pan_card')(v.toUpperCase())}
              error={errors.pan_card}
              maxLength={10}
              placeholder="Auto-filled from GSTIN"
            />
          </FormRow>

          <FormTextarea
            label="Account Remarks"
            name="remarks"
            value={form.remarks}
            onChange={setField('remarks')}
            rows={2}
            placeholder="Optional internal notes about this account"
          />
        </div>

        {/* Dynamic Multi-Role Rows */}
        <div className="party-section party-roles-section">
          <div className="party-roles-header">
            <div>
              <div className="party-section__title">Account Roles & Opening Balances</div>
              <div className="party-roles-subtitle">
                An account can hold multiple roles (e.g. Customer & Supplier) with separate opening balances.
              </div>
            </div>
            {form.roles.length < 3 && (
              <button
                type="button"
                className="party-add-role-btn"
                onClick={handleAddRoleRow}
              >
                + Add Another Role
              </button>
            )}
          </div>

          {errors.roles && <div className="party-role-error-banner">{errors.roles}</div>}

          <div className="party-roles-list">
            {form.roles.map((roleEntry, index) => {
              const roleError = errors.roleErrors?.[index] || {};
              const isCustomer = roleEntry.role === 'CUSTOMER';
              const balNum = Number(roleEntry.opening_balance || 0);

              return (
                <div key={roleEntry.id || index} className="party-role-card">
                  <div className="party-role-card__header">
                    <div className="party-role-card__title">
                      <span className="party-role-number">Role #{index + 1}</span>
                      <span className={`party-role-chip party-role-chip--${roleEntry.role.toLowerCase()}`}>
                        {roleEntry.role === 'CUSTOMER' ? 'Customer' : roleEntry.role === 'SUPPLIER' ? 'Supplier' : 'Purchase Vendor'}
                      </span>
                      {roleEntry.isExisting && <span className="party-role-active-tag">Active</span>}
                    </div>
                    {form.roles.length > 1 && !roleEntry.isExisting && (
                      <button
                        type="button"
                        className="party-role-remove-btn"
                        onClick={() => handleRemoveRoleRow(index)}
                        title="Remove this role row"
                      >
                        ✕ Remove
                      </button>
                    )}
                  </div>

                  <div className="party-role-card__body">
                    <FormRow>
                      <div className="party-role-select-wrap">
                        <label className="party-role-label">
                          Role Type <span className="req">*</span>
                        </label>
                        <select
                          className="party-role-select"
                          value={roleEntry.role}
                          onChange={(e) => handleRoleFieldChange(index, 'role', e.target.value)}
                          disabled={roleEntry.isExisting}
                        >
                          {ROLE_OPTIONS.map((opt) => {
                            const isAlreadySelected = form.roles.some((r, i) => i !== index && r.role === opt.value);
                            return (
                              <option key={opt.value} value={opt.value} disabled={isAlreadySelected}>
                                {opt.label} {isAlreadySelected ? '(Already Added)' : ''}
                              </option>
                            );
                          })}
                        </select>
                        {roleError.role && <div className="field-error">{roleError.role}</div>}
                      </div>

                      <FormInput
                        label="Opening Balance (₹)"
                        name={`opening_balance_${index}`}
                        type="number"
                        step="0.01"
                        value={roleEntry.opening_balance}
                        onChange={(v) => handleRoleFieldChange(index, 'opening_balance', v)}
                        error={roleError.opening_balance}
                        placeholder="0.00"
                      />

                      <div className="party-radio-field">
                        <span className="party-radio-label">
                          Direction {balNum > 0 && <span className="req">*</span>}
                        </span>
                        <div className="party-radio-group">
                          {['Credit', 'Debit'].map((type) => (
                            <label
                              key={type}
                              className={`party-radio ${roleEntry.balance_type === type ? 'party-radio--active' : ''}`}
                            >
                              <input
                                type="radio"
                                name={`balance_type_${index}`}
                                value={type}
                                checked={roleEntry.balance_type === type}
                                onChange={() => handleRoleFieldChange(index, 'balance_type', type)}
                              />
                              <span>{type}</span>
                            </label>
                          ))}
                        </div>
                        <div className="party-balance-hint">
                          {isCustomer
                            ? (roleEntry.balance_type === 'Debit' ? 'Dr: Customer owes you' : 'Cr: Customer advance')
                            : (roleEntry.balance_type === 'Credit' ? 'Cr: You owe party' : 'Dr: Advance paid to party')}
                        </div>
                      </div>
                    </FormRow>

                    <FormInput
                      label="Opening Balance Remark"
                      name={`opening_remark_${index}`}
                      value={roleEntry.opening_remark}
                      onChange={(v) => handleRoleFieldChange(index, 'opening_remark', v)}
                      placeholder="Optional remark (e.g. Migration balance, Opening ledger note)"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </form>
    </Modal>
  );
}
