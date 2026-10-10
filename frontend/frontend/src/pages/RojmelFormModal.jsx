import { handleEnterNavigation } from '../utils/enterNavigation';
import AccountSelector from '../components/common/AccountSelector';
import { accountSelectionFields } from '../services/accountService';
import { useEffect, useState } from 'react';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { FormInput, FormSelect, FormTextarea, FormRow } from '../components/common/FormField';
import './RojmelFormModal.css';

const TRANSACTION_TYPES = ['Cr Pay', 'Dr Pay', 'Cash/Bank', 'JV'];

const PAY_MODE_OPTIONS = [
  { value: 'Cash', label: 'Cash' },
  { value: 'Cheque', label: 'Cheque' },
  { value: 'NEFT', label: 'NEFT' },
  { value: 'RTGS', label: 'RTGS' },
  { value: 'UPI', label: 'UPI' },
];

const todayISO = () => new Date().toISOString().slice(0, 10);

const EMPTY_FORM = {
  transaction_type: 'Cash/Bank',
  given_taken_date: todayISO(),
  effective_date: todayISO(),
  party_id: '',
  customer_id: '',
  cash_bank_id: '',
  done_by_id: '',
  pay_mode: 'Cash',
  cheque_txn_no: '',
  amount: '',
  sgst_percent: '0',
  cgst_percent: '0',
  igst_percent: '0',
  payment_for: '',
  remarks: '',
};

// Client-side preview only -- the backend always recalculates and owns
// the authoritative net_amount on save.
function calculateNetAmount(amount, sgst, cgst, igst) {
  const amt = Number(amount) || 0;
  const totalTaxPercent = (Number(sgst) || 0) + (Number(cgst) || 0) + (Number(igst) || 0);
  return amt + (amt * totalTaxPercent) / 100;
}

// Validates the form before submit; returns a { field: message } map.
function validate(form) {
  const errors = {};
  if (!form.effective_date) errors.effective_date = 'Effective date is required.';
  if (!form.given_taken_date) errors.given_taken_date = 'Date is required.';
  if (!form.cash_bank_id) errors.cash_bank_id = 'Select a Cash/Bank account.';
  if (!form.done_by_id) errors.done_by_id = "Select who's doing this entry.";
  if (!form.pay_mode) errors.pay_mode = 'Select a payment mode.';
  if (form.pay_mode === 'Cheque' && !form.cheque_txn_no.trim()) {
    errors.cheque_txn_no = 'Cheque / Txn No. is required for Cheque payments.';
  }
  if (form.amount === '' || Number.isNaN(Number(form.amount)) || Number(form.amount) <= 0) {
    errors.amount = 'Enter a valid amount greater than 0.';
  }
  return errors;
}

export default function RojmelFormModal({
  open,
  mode = 'add',
  initialData = null,
  restoredForm = null,
  banks = [],
  doneByList = [],
  onClose,
  onSubmit,
  onAddParty,
  onAddBank,
  onAddDoneBy,
  submitting,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  // Prefills the form when opening in edit mode, restores a saved draft
  // (returning from a "+ Add Party/Bank/Done By" redirect), or resets it
  // for a plain "add". restoredForm always wins since it represents
  // whatever the user had already typed before leaving this page.
  useEffect(() => {
    if (!open) return;
    if (restoredForm) {
      setForm(restoredForm);
    } else if (mode === 'edit' && initialData) {
      setForm({
        transaction_type: initialData.transaction_type || 'Cash/Bank',
        given_taken_date: initialData.given_taken_date || todayISO(),
        effective_date: initialData.effective_date || todayISO(),
        party_id: initialData.party_id ?? '',
        customer_id: initialData.customer_id ?? '',
        cash_bank_id: initialData.cash_bank_id ?? '',
        done_by_id: initialData.done_by_id ?? '',
        pay_mode: initialData.pay_mode || 'Cash',
        cheque_txn_no: initialData.cheque_txn_no || '',
        amount: initialData.amount ?? '',
        sgst_percent: initialData.sgst_percent ?? '0',
        cgst_percent: initialData.cgst_percent ?? '0',
        igst_percent: initialData.igst_percent ?? '0',
        payment_for: initialData.payment_for || '',
        remarks: initialData.remarks || '',
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [open, mode, initialData, restoredForm]);

  // GST is either intra-state (SGST+CGST) or inter-state (IGST), never
  // both -- entering one side clears and locks out the other.
  const setField = (field) => (value) => {
    setForm((prev) => {
      const next = { ...prev, [field]: value };
      if (field === 'transaction_type' && !['Cr Pay', 'Dr Pay'].includes(value) && prev.customer_id) {
        next.customer_id = ''; next.party_id = ''; next.accountType = 'SUPPLIER';
      }
      if ((field === 'sgst_percent' || field === 'cgst_percent') && Number(value) > 0) {
        next.igst_percent = '0';
      }
      if (field === 'igst_percent' && Number(value) > 0) {
        next.sgst_percent = '0';
        next.cgst_percent = '0';
      }
      return next;
    });
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  // Validates, builds the API payload, and hands it to the parent to save.
  const handleSubmit = (e) => {
    e.preventDefault();
    const validationErrors = validate(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    const payload = {
      transaction_type: form.transaction_type,
      // Required by the schema but always overwritten server-side on create,
      // and never accepted on update -- the real value comes from the backend.
      receipt_no: initialData?.receipt_no || 'AUTO',
      given_taken_date: form.given_taken_date,
      effective_date: form.effective_date,
      party_id: form.party_id ? Number(form.party_id) : null,
      customer_id: form.customer_id ? Number(form.customer_id) : null,
      cash_bank_id: Number(form.cash_bank_id),
      done_by_id: Number(form.done_by_id),
      pay_mode: form.pay_mode,
      cheque_txn_no: form.cheque_txn_no.trim() || null,
      amount: String(form.amount),
      sgst_percent: String(form.sgst_percent || '0'),
      cgst_percent: String(form.cgst_percent || '0'),
      igst_percent: String(form.igst_percent || '0'),
      payment_for: form.payment_for.trim() || null,
      remarks: form.remarks.trim() || null,
    };

    onSubmit(payload);
  };

  const netAmountPreview = calculateNetAmount(form.amount, form.sgst_percent, form.cgst_percent, form.igst_percent);
  const igstDisabled = Number(form.sgst_percent) > 0 || Number(form.cgst_percent) > 0;
  const sgstCgstDisabled = Number(form.igst_percent) > 0;

  const bankOptions = [{ value: '', label: 'Select Cash/Bank' }, ...banks.map((b) => ({ value: String(b.id), label: b.name }))];
  const doneByOptions = [{ value: '', label: 'Select Person' }, ...doneByList.map((d) => ({ value: String(d.id), label: d.name }))];

  return (
    <Modal
      open={open}
      title={mode === 'edit' ? `Edit Receipt ${initialData?.receipt_no || ''}` : 'New Rojmel Entry'}
      onClose={onClose}
      width={760}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Saving...' : mode === 'edit' ? 'Save Changes' : 'Add Entry'}
          </Button>
        </>
      }
    >
      <form data-enter-navigation onKeyDown={handleEnterNavigation} className="rojmel-form" onSubmit={handleSubmit} noValidate>
        <div className="rojmel-radio-field">
          <span className="rojmel-radio-label">Transaction Type <span>*</span></span>
          <div className="rojmel-radio-group">
            {TRANSACTION_TYPES.map((type) => (
              <label key={type} className={`rojmel-radio ${form.transaction_type === type ? 'rojmel-radio--active' : ''}`}>
                <input
                  type="radio"
                  name="transaction_type"
                  value={type}
                  checked={form.transaction_type === type}
                  onChange={() => setField('transaction_type')(type)}
                />
                <span>{type}</span>
              </label>
            ))}
          </div>
        </div>

        <FormRow>
          <FormInput label="Given/Taken Date" name="given_taken_date" type="date" value={form.given_taken_date} onChange={setField('given_taken_date')} required error={errors.given_taken_date} />
          <FormInput label="Effective Date" name="effective_date" type="date" value={form.effective_date} onChange={setField('effective_date')} required error={errors.effective_date} />
        </FormRow>

        <FormRow>
          <div className="gt-with-action">
            <AccountSelector name="rojmel_account" domain={['Cr Pay', 'Dr Pay'].includes(form.transaction_type) ? undefined : 'party'}
              source={form.customer_id ? 'customer' : 'party'} value={form.customer_id || form.party_id}
              defaultType={form.accountType} disabled={submitting}
              onChange={(selection, nextType) => setForm((previous) => ({ ...previous,
                ...accountSelectionFields(selection), accountType: selection?.accountType || nextType,
              }))} />
            <button type="button" className="gt-plus" onClick={() => onAddParty(form)} title="Add new party" aria-label="Add new party">+</button>
          </div>
          <div className="gt-with-action">
            <FormSelect label="Cash / Bank" name="cash_bank_id" value={String(form.cash_bank_id)} onChange={setField('cash_bank_id')} options={bankOptions} required error={errors.cash_bank_id} />
            <button type="button" className="gt-plus" onClick={() => onAddBank(form)} title="Add new bank" aria-label="Add new bank">+</button>
          </div>
          <div className="gt-with-action">
            <FormSelect label="Done By" name="done_by_id" value={String(form.done_by_id)} onChange={setField('done_by_id')} options={doneByOptions} required error={errors.done_by_id} />
            <button type="button" className="gt-plus" onClick={() => onAddDoneBy(form)} title="Add new person" aria-label="Add new person">+</button>
          </div>
        </FormRow>

        <FormRow>
          <FormSelect label="Payment Mode" name="pay_mode" value={form.pay_mode} onChange={setField('pay_mode')} options={PAY_MODE_OPTIONS} required error={errors.pay_mode} />
          <FormInput label="Cheque / Txn No." name="cheque_txn_no" value={form.cheque_txn_no} onChange={setField('cheque_txn_no')} placeholder="Required for Cheque" error={errors.cheque_txn_no} />
        </FormRow>

        <div className="rojmel-amount-card">
          <FormRow>
            <FormInput label="Amount" name="amount" type="number" value={form.amount} onChange={setField('amount')} required error={errors.amount} placeholder="0.00" />
            <FormInput label="SGST %" name="sgst_percent" type="number" value={form.sgst_percent} onChange={setField('sgst_percent')} disabled={sgstCgstDisabled} />
            <FormInput label="CGST %" name="cgst_percent" type="number" value={form.cgst_percent} onChange={setField('cgst_percent')} disabled={sgstCgstDisabled} />
            <FormInput label="IGST %" name="igst_percent" type="number" value={form.igst_percent} onChange={setField('igst_percent')} disabled={igstDisabled} />
          </FormRow>
          <div className="rojmel-net-preview">
            Net Amount: <strong>₹{netAmountPreview.toFixed(2)}</strong>
            <span className="rojmel-net-preview__note">Calculated by the server on save.</span>
          </div>
        </div>

        <FormInput label="Payment For" name="payment_for" value={form.payment_for} onChange={setField('payment_for')} placeholder="e.g. Advance against Purchase Order #123" />
        <FormTextarea label="Remarks" name="remarks" value={form.remarks} onChange={setField('remarks')} rows={2} />
      </form>
    </Modal>
  );
}
