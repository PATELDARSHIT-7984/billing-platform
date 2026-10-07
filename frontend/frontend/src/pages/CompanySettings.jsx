import { handleEnterNavigation } from '../utils/enterNavigation';
import { useEffect, useState } from 'react';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { FormInput, FormTextarea, FormRow } from '../components/common/FormField';
import { useToast } from '../context/ToastContext';
import { useCompany } from '../context/CompanyContext';
import { updateCompanyProfile } from '../services/companyService';
import { extractErrorMessage } from '../services/api';
import '../styles/PurchaseEntry.css';
import '../styles/CompanySettings.css';

const EMPTY_FORM = {
  company_name: '',
  address_line1: '',
  address_line2: '',
  mobile: '',
  email: '',
  gstin: '',
  pan_card: '',
  udyam_no: '',
  bank_account_name: '',
  bank_account_no: '',
  bank_ifsc: '',
  bank_name: '',
  terms_and_conditions: '',
  jurisdiction_note: '',
};

function validate(form) {
  const errors = {};
  if (!form.company_name.trim()) errors.company_name = 'Company name is required.';

  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    errors.email = 'Enter a valid email address.';
  }
  if (form.gstin && !/^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$/.test(form.gstin.trim().toUpperCase())) {
    errors.gstin = 'Invalid GSTIN format.';
  }
  if (form.pan_card && form.pan_card.trim().length !== 10) {
    errors.pan_card = 'PAN must be exactly 10 characters.';
  }
  return errors;
}

export default function CompanySettings() {
  const toast = useToast();
  const { company, loading, refresh } = useCompany();

  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  // Prefill the form once the context finishes its initial load.
  useEffect(() => {
    if (loading) return;
    setForm({
      company_name: company.company_name || '',
      address_line1: company.address_line1 || '',
      address_line2: company.address_line2 || '',
      mobile: company.mobile || '',
      email: company.email || '',
      gstin: company.gstin || '',
      pan_card: company.pan_card || '',
      udyam_no: company.udyam_no || '',
      bank_account_name: company.bank_account_name || '',
      bank_account_no: company.bank_account_no || '',
      bank_ifsc: company.bank_ifsc || '',
      bank_name: company.bank_name || '',
      terms_and_conditions: (company.terms_and_conditions || []).join('\n'),
      jurisdiction_note: company.jurisdiction_note || '',
    });
  }, [loading, company]);

  const setField = (field) => (value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const handleSave = () => {
    const validationErrors = validate(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      toast.error('Please fix the highlighted fields.');
      return;
    }

    const payload = {
      company_name: form.company_name.trim(),
      address_line1: form.address_line1.trim(),
      address_line2: form.address_line2.trim(),
      mobile: form.mobile.trim(),
      email: form.email.trim(),
      gstin: form.gstin.trim().toUpperCase(),
      pan_card: form.pan_card.trim().toUpperCase(),
      udyam_no: form.udyam_no.trim(),
      bank_account_name: form.bank_account_name.trim(),
      bank_account_no: form.bank_account_no.trim(),
      bank_ifsc: form.bank_ifsc.trim(),
      bank_name: form.bank_name.trim(),
      terms_and_conditions: form.terms_and_conditions
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
      jurisdiction_note: form.jurisdiction_note.trim(),
    };

    setSaving(true);
    updateCompanyProfile(payload)
      .then(() => {
        toast.success('Company details saved. New invoices will use these details.');
        return refresh();
      })
      .catch((err) => toast.error(extractErrorMessage(err)))
      .finally(() => setSaving(false));
  };

  if (loading) {
    return (
      <div className="page">
        <div className="company-settings__loading">Loading company details...</div>
      </div>
    );
  }

  return (
    <div className="page" data-enter-navigation onKeyDown={handleEnterNavigation}>
      <div className="purchase-entry__header">
        <div>
          <h1 className="purchase-entry__title">Company Settings</h1>
          <p className="purchase-entry__subtitle">
            These details appear on every invoice you print or download. Set them up once.
          </p>
        </div>
      </div>

      {/* SECTION: IDENTITY */}
      <Card title="Business Identity" className="purchase-entry__section">
        <FormInput
          label="Company Name"
          name="company_name"
          value={form.company_name}
          onChange={setField('company_name')}
          required
          error={errors.company_name}
        />
        <FormRow>
          <FormInput
            label="Address Line 1"
            name="address_line1"
            value={form.address_line1}
            onChange={setField('address_line1')}
            placeholder="Shop no., street, area"
          />
          <FormInput
            label="Address Line 2"
            name="address_line2"
            value={form.address_line2}
            onChange={setField('address_line2')}
            placeholder="City, State"
          />
        </FormRow>
        <FormRow>
          <FormInput label="Mobile" name="mobile" value={form.mobile} onChange={setField('mobile')} />
          <FormInput label="Email" name="email" type="email" value={form.email} onChange={setField('email')} error={errors.email} />
        </FormRow>
      </Card>

      {/* SECTION: TAX DETAILS */}
      <Card title="Tax Details" className="purchase-entry__section">
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
            label="PAN"
            name="pan_card"
            value={form.pan_card}
            onChange={(v) => setField('pan_card')(v.toUpperCase())}
            error={errors.pan_card}
            maxLength={10}
          />
          <FormInput
            label="UDYAM Registration No."
            name="udyam_no"
            value={form.udyam_no}
            onChange={setField('udyam_no')}
            placeholder="e.g. UDYAM-GJ-01-0000000"
          />
        </FormRow>
      </Card>

      {/* SECTION: BANK DETAILS */}
      <Card title="Bank Details" subtitle="Shown in the invoice footer for customer payments." className="purchase-entry__section">
        <FormRow>
          <FormInput label="Account Name" name="bank_account_name" value={form.bank_account_name} onChange={setField('bank_account_name')} />
          <FormInput label="Account Number" name="bank_account_no" value={form.bank_account_no} onChange={setField('bank_account_no')} />
        </FormRow>
        <FormRow>
          <FormInput label="IFSC Code" name="bank_ifsc" value={form.bank_ifsc} onChange={(v) => setField('bank_ifsc')(v.toUpperCase())} />
          <FormInput label="Bank Name" name="bank_name" value={form.bank_name} onChange={setField('bank_name')} />
        </FormRow>
      </Card>

      {/* SECTION: INVOICE FOOTER TEXT */}
      <Card title="Invoice Footer Text" className="purchase-entry__section">
        <FormTextarea
          label="Terms & Conditions"
          name="terms_and_conditions"
          value={form.terms_and_conditions}
          onChange={setField('terms_and_conditions')}
          rows={4}
          placeholder={'One condition per line, e.g.\nGoods once sold will not be taken back or exchanged.'}
        />
        <FormInput
          label="Jurisdiction Note"
          name="jurisdiction_note"
          value={form.jurisdiction_note}
          onChange={setField('jurisdiction_note')}
          placeholder="e.g. Subject to Ahmedabad jurisdiction."
        />
      </Card>

      <div className="purchase-entry__footer-actions">
        <Button variant="primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
