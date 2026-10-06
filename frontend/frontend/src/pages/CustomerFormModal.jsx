import { handleEnterNavigation } from '../utils/enterNavigation';
import { useEffect, useState } from 'react';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { FormInput, FormTextarea, FormRow } from '../components/common/FormField';

const EMPTY_FORM = {
  customer_name: '',
  mobile: '',
  email: '',
  address: '',
  city: '',
  state: '',
  pincode: '',
  gstin: '',
  pan_card: '',
  state_code: '',
  remarks: '',
};

// Mirrors CustomerCreate/CustomerUpdate validation from customer_schema.py
function validate(form) {
  const errors = {};

  const trimmedName = form.customer_name.trim();
  if (!trimmedName) errors.customer_name = 'Customer name is required.';
  else if (trimmedName.length < 2 || trimmedName.length > 100) {
    errors.customer_name = 'Name must be between 2 and 100 characters.';
  }

  if (!/^[6-9]\d{9}$/.test(form.mobile.trim())) {
    errors.mobile = 'Enter a valid 10-digit mobile number (starting 6-9).';
  }

  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    errors.email = 'Enter a valid email address.';
  }

  // address/city/state are required — Bill snapshots these onto every
  // invoice as NOT NULL columns, so an incomplete customer would crash
  // Sales Entry at billing time rather than here.
  if (!form.address.trim()) errors.address = 'Address is required (needed to print invoices).';
  if (!form.city.trim()) errors.city = 'City is required.';
  if (!form.state.trim()) errors.state = 'State is required.';

  if (form.gstin && !/^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$/.test(form.gstin.trim().toUpperCase())) {
    errors.gstin = 'Invalid GSTIN format.';
  }

  if (form.pan_card && form.pan_card.trim().length !== 10) {
    errors.pan_card = 'PAN must be exactly 10 characters.';
  }

  if (form.state_code && form.state_code.trim().length !== 2) {
    errors.state_code = 'State code must be exactly 2 digits (e.g. 24 for Gujarat).';
  }

  return errors;
}

export default function CustomerFormModal({ open, mode = 'add', initialData = null, onClose, onSubmit, submitting }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && initialData) {
      setForm({
        customer_name: initialData.customer_name || '',
        mobile: initialData.mobile || '',
        email: initialData.email || '',
        address: initialData.address || '',
        city: initialData.city || '',
        state: initialData.state || '',
        pincode: initialData.pincode || '',
        gstin: initialData.gstin || '',
        pan_card: initialData.pan_card || '',
        state_code: initialData.state_code || '',
        remarks: initialData.remarks || '',
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [open, mode, initialData]);

  const setField = (field) => (value) => {
    setForm((prev) => {
      const next = { ...prev, [field]: value };

      // Live preview of the backend's auto-derive: characters 3-12 of a
      // valid GSTIN are always the PAN. Only fills PAN in automatically —
      // never overwrites something the user already typed themselves.
      if (field === 'gstin' && value.trim().length === 15 && !prev.pan_card) {
        next.pan_card = value.trim().slice(2, 12).toUpperCase();
      }

      return next;
    });
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const validationErrors = validate(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    // Full object on edit too — update_customer() overwrites every field.
    const payload = {
      customer_name: form.customer_name.trim(),
      mobile: form.mobile.trim(),
      email: form.email.trim() || null,
      address: form.address.trim(),
      city: form.city.trim(),
      state: form.state.trim(),
      pincode: form.pincode.trim() || null,
      gstin: form.gstin.trim() ? form.gstin.trim().toUpperCase() : null,
      pan_card: form.pan_card.trim() ? form.pan_card.trim().toUpperCase() : null,
      state_code: form.state_code.trim() || null,
      remarks: form.remarks.trim() || null,
    };
    if (mode === 'edit') payload.is_active = true;

    onSubmit(payload);
  };

  return (
    <Modal
      open={open}
      title={mode === 'edit' ? 'Edit Customer' : 'Add New Customer'}
      onClose={onClose}
      width={640}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Saving...' : mode === 'edit' ? 'Save Changes' : 'Add Customer'}
          </Button>
        </>
      }
    >
      <form data-enter-navigation onKeyDown={handleEnterNavigation} onSubmit={handleSubmit} noValidate>
        <FormRow>
          <FormInput
            label="Customer Name"
            name="customer_name"
            value={form.customer_name}
            onChange={setField('customer_name')}
            required
            error={errors.customer_name}
            autoFocus
          />
          <FormInput
            label="Mobile Number"
            name="mobile"
            value={form.mobile}
            onChange={setField('mobile')}
            required
            error={errors.mobile}
            maxLength={10}
            placeholder="10-digit mobile"
          />
        </FormRow>

        <FormRow>
          <FormInput
            label="Email"
            name="email"
            type="email"
            value={form.email}
            onChange={setField('email')}
            error={errors.email}
          />
          <FormInput
            label="Pincode"
            name="pincode"
            value={form.pincode}
            onChange={setField('pincode')}
          />
        </FormRow>

        <FormTextarea
          label="Address"
          name="address"
          value={form.address}
          onChange={setField('address')}
          required
          error={errors.address}
          rows={2}
        />

        <FormRow>
          <FormInput
            label="City"
            name="city"
            value={form.city}
            onChange={setField('city')}
            required
            error={errors.city}
          />
          <FormInput
            label="State"
            name="state"
            value={form.state}
            onChange={setField('state')}
            required
            error={errors.state}
          />
          <FormInput
            label="State Code"
            name="state_code"
            value={form.state_code}
            onChange={setField('state_code')}
            error={errors.state_code}
            maxLength={2}
            placeholder="e.g. 24"
          />
        </FormRow>

        <FormRow>
          <FormInput
            label="GSTIN"
            name="gstin"
            value={form.gstin}
            onChange={(v) => setField('gstin')(v.toUpperCase())}
            error={errors.gstin}
            maxLength={15}
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
          label="Remarks"
          name="remarks"
          value={form.remarks}
          onChange={setField('remarks')}
          rows={2}
        />
      </form>
    </Modal>
  );
}
