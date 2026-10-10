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
  opening_balance: '',
  balance_type: 'Credit',
  opening_remark: '',
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

  if (form.opening_balance !== '' && Number.isNaN(Number(form.opening_balance))) {
    errors.opening_balance = 'Opening balance must be a valid amount.';
  }

  if (unifiedAccounts && form.accountType === 'CUSTOMER') {
    const customerErrors = validateCustomer({ ...form, customer_name: form.name });
    if (customerErrors.customer_name) {
      customerErrors.name = customerErrors.customer_name;
      delete customerErrors.customer_name;
    }
    Object.assign(errors, customerErrors);
  }
  return errors;
}

export default function PartyFormModal({ open, mode = 'add', initialData = null, defaultType = 'SUPPLIER', unifiedAccounts = false, onClose, onSubmit, submitting }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && initialData) {
      setForm({
        name: initialData.name || '',
        accountType: initialData.accountType || (initialData.party_type === 'Customer' ? 'CUSTOMER' : 'SUPPLIER'),
        country_code: initialData.country_code || '+91',
        mobile: initialData.mobile || '',
        address: initialData.address || '',
        city: initialData.city || '',
        state: initialData.state || '',
        gstin: initialData.gstin || '',
        pan_card: initialData.pan_card || '',
        opening_balance: initialData.opening_balance ?? '',
        balance_type: initialData.balance_type || 'Credit',
        opening_remark: initialData.opening_remark || '',
      });
    } else {
      setForm({ ...EMPTY_FORM, accountType: defaultType });
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

  const handleSubmit = (e) => {
    e.preventDefault();
    const validationErrors = validate(form, unifiedAccounts);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    // Transaction pages still consume the original Party payload; only Accounts opts in.
    onSubmit(unifiedAccounts ? form : {
      ...buildAccountPayload('SUPPLIER', form), party_type: accountType(form.accountType).label,
    });
  };

  return (
    <Modal
      open={open}
      title={mode === 'edit' ? (unifiedAccounts ? 'Edit Account' : 'Edit Party') : (unifiedAccounts ? 'Add New Account' : 'Add New Party')}
      onClose={onClose}
      width={700}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Saving...' : mode === 'edit' ? 'Save Changes' : (unifiedAccounts ? 'Add Account' : 'Add Party')}
          </Button>
        </>
      }
    >
      <form data-enter-navigation onKeyDown={handleEnterNavigation} className="party-form" onSubmit={handleSubmit} noValidate>
        <FormRow>
          <FormInput label="Party Name" name="name" value={form.name} onChange={setField('name')} required error={errors.name} autoFocus />
          <FormSelect label={unifiedAccounts ? "Account Type" : "Party Type"} name="accountType" value={form.accountType} onChange={setField('accountType')} options={unifiedAccounts ? ACCOUNT_TYPES : ACCOUNT_TYPES.filter((type) => type.value !== 'PURCHASE_VENDOR').toReversed()} disabled={unifiedAccounts && mode === 'edit'} required />
        </FormRow>

        <div className="party-contact-row">
          <div className="party-country-code">
            <FormSelect label="Country Code" name="country_code" value={form.country_code} onChange={setField('country_code')} options={COUNTRY_CODE_OPTIONS} disabled={unifiedAccounts && form.accountType === 'CUSTOMER'} required error={errors.country_code} />
          </div>
          <div className="party-mobile-field">
            <FormInput label="Mobile Number" name="mobile" value={form.mobile} onChange={setField('mobile')} placeholder="Enter mobile number" required={unifiedAccounts && form.accountType === 'CUSTOMER'} error={errors.mobile} />
          </div>
        </div>

        <FormRow>
          <FormInput label="City" name="city" value={form.city} onChange={setField('city')} placeholder="Enter city" required={unifiedAccounts && form.accountType === 'CUSTOMER'} error={errors.city} />
          <FormSelect label="State" name="state" value={form.state} onChange={setField('state')} options={STATE_OPTIONS} required error={errors.state} />
        </FormRow>

        <FormTextarea label="Address" name="address" value={form.address} onChange={setField('address')} rows={2} placeholder="Enter address" required={unifiedAccounts && form.accountType === 'CUSTOMER'} error={errors.address} />

        <FormRow>
          <FormInput label="GSTIN" name="gstin" value={form.gstin} onChange={handleGstinChange} error={errors.gstin} maxLength={15} placeholder="15-character GSTIN" />
          <FormInput label="PAN Card" name="pan_card" value={form.pan_card} onChange={(v) => setField('pan_card')(v.toUpperCase())} error={errors.pan_card} maxLength={10} placeholder="Auto-filled from GSTIN" />
        </FormRow>

        <div className="party-opening-card">
          <FormRow>
            <FormInput label="Opening Balance" name="opening_balance" type="number" value={form.opening_balance} onChange={setField('opening_balance')} error={errors.opening_balance} placeholder="Enter amount" />
            <div className="party-radio-field">
              <span className="party-radio-label">Balance Type <span>*</span></span>
              <div className="party-radio-group">
                {['Credit', 'Debit'].map((type) => (
                  <label key={type} className={`party-radio ${form.balance_type === type ? 'party-radio--active' : ''}`}>
                    <input type="radio" name="balance_type" value={type} checked={form.balance_type === type} onChange={() => setField('balance_type')(type)} />
                    <span>{type}</span>
                  </label>
                ))}
              </div>
            </div>
          </FormRow>
          <FormTextarea label="Opening Remark" name="opening_remark" value={form.opening_remark} onChange={setField('opening_remark')} rows={2} placeholder="Enter opening remark (optional)" />
        </div>
      </form>
    </Modal>
  );
}
