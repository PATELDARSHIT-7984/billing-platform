import { useEffect, useMemo, useState } from 'react';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { FormInput, FormTextarea, FormRow } from '../components/common/FormField';
import SearchableSelect from '../components/common/SearchableSelect';
import { UNIT_OPTIONS } from '../config/units';
import './ItemFormModal.css';

const EMPTY_FORM = {
  name: '',
  code: '',
  hsn_code: '',
  unit: '',
  category: '',
  brand: '',
  current_stock: '0',
  purchase_price: '0',
  sale_price: '0',
  mrp: '0',
  cgst: '9',
  sgst: '9',
  description: '',
  // Not editable here — these are set automatically by Purchase/Sales Entry.
  // Kept in state (read from the fetched record) purely so Edit submits can
  // send them back unchanged; see the note in itemService.updateItem.
  last_purchase_date: null,
  last_sale_date: null,
};

// Mirrors ItemMasterCreate/ItemMasterUpdate's Field(ge=0) constraints so the
// user gets instant feedback instead of a failed API call.
function validate(form) {
  const errors = {};

  const trimmedName = form.name.trim();
  if (!trimmedName) errors.name = 'Item name is required.';
  else if (trimmedName.length < 2) errors.name = 'Name must be at least 2 characters.';

  if (!form.unit || !String(form.unit).trim()) errors.unit = 'Unit is required.';

 const numericFields = [
  ['current_stock', 'Current stock'],
  ['purchase_price', 'Purchase price'],
  ['sale_price', 'Sale price'],
  ['mrp', 'MRP'],
  ['cgst', 'CGST'],
  ['sgst', 'SGST'],
];
  numericFields.forEach(([field, label]) => {
    if (form[field] !== '' && Number(form[field]) < 0) {
      errors[field] = `${label} cannot be negative.`;
    }
  });

  return errors;
}

function formatDate(value) {
  if (!value) return '—';
  // value arrives as "YYYY-MM-DD" from the API (Pydantic `date`); display as-is.
  return value;
}

export default function ItemFormModal({
  open,
  mode = 'add', // 'add' | 'edit'
  initialData = null, // full ItemMasterResponse, fetched by the parent before opening in edit mode
  categoryOptions = [],
  brandOptions = [],
  submitting,
  onClose,
  onSubmit,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && initialData) {
      setForm({
        name: initialData.name || '',
        code: initialData.code || '',
        hsn_code: initialData.hsn_code || '',
        unit: initialData.unit || '',
        category: initialData.category || '',
        brand: initialData.brand || '',
        current_stock: String(initialData.current_stock ?? 0),
        purchase_price: String(initialData.purchase_price ?? 0),
        sale_price: String(initialData.sale_price ?? 0),
        mrp: String(initialData.mrp ?? 0),
        cgst: String(initialData.cgst ?? 9),
        sgst: String(initialData.sgst ?? 9),
        description: initialData.description || '',
        last_purchase_date: initialData.last_purchase_date || null,
        last_sale_date: initialData.last_sale_date || null,
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [open, mode, initialData]);

  const setField = (field) => (value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const handleUnitSelect = (option) => {
    setField('unit')(option ? option.value : '');
  };

  const handleCategorySelect = (option) => {
    setField('category')(option ? option.value : '');
  };

  const handleBrandSelect = (option) => {
    setField('brand')(option ? option.value : '');
  };

  const unitValue = useMemo(
    () => (form.unit ? { value: form.unit, label: form.unit } : null),
    [form.unit]
  );
  const categoryValue = useMemo(
    () => (form.category ? { value: form.category, label: form.category } : null),
    [form.category]
  );
  const brandValue = useMemo(
    () => (form.brand ? { value: form.brand, label: form.brand } : null),
    [form.brand]
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    const validationErrors = validate(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    // Send the complete object every time, edit included — update_item()
    // overwrites every column from the payload with no partial-merge, so a
    // trimmed-down payload would null out anything left out (see
    // itemService.updateItem for the backend detail).
    const payload = {
      name: form.name.trim(),
      code: form.code.trim() || null,
      hsn_code: form.hsn_code.trim() || null,
      unit: String(form.unit).trim(),
      category: form.category.trim() || null,
      brand: form.brand.trim() || null,
      current_stock: Number(form.current_stock) || 0,
      purchase_price: Number(form.purchase_price) || 0,
      sale_price: Number(form.sale_price) || 0,
      mrp: Number(form.mrp) || 0,
      cgst: Number(form.cgst) || 0,
      sgst: Number(form.sgst) || 0,
      description: form.description.trim() || null,
      last_purchase_date: form.last_purchase_date,
      last_sale_date: form.last_sale_date,
    };

    onSubmit(payload);
  };

  return (
    <Modal
      open={open}
      title={mode === 'edit' ? 'Edit Item' : 'Add New Item'}
      onClose={onClose}
      width={680}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Saving...' : mode === 'edit' ? 'Save Changes' : 'Add Item'}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate>
        <FormRow>
          <FormInput
            label="Item Name"
            name="name"
            value={form.name}
            onChange={setField('name')}
            required
            error={errors.name}
            autoFocus
          />
          <FormInput
            label="Item Code"
            name="code"
            value={form.code}
            onChange={setField('code')}
            placeholder="Optional, must be unique"
          />
        </FormRow>

        <FormRow>
          <FormInput
            label="HSN Code"
            name="hsn_code"
            value={form.hsn_code}
            onChange={setField('hsn_code')}
          />
          <SearchableSelect
            label="Unit"
            name="unit"
            placeholder="Search or type a unit..."
            options={UNIT_OPTIONS}
            value={unitValue?.value ?? ''}
            onChange={handleUnitSelect}
            allowCustom
            required
            error={errors.unit}
            emptyMessage="No matches. Type to use a custom unit."
          />
        </FormRow>

        <FormRow>
          <SearchableSelect
            label="Category"
            name="category"
            placeholder="Search or type a category..."
            options={categoryOptions}
            value={categoryValue?.value ?? ''}
            onChange={handleCategorySelect}
            allowCustom
            emptyMessage="Type to add a new category."
          />
          <SearchableSelect
            label="Brand"
            name="brand"
            placeholder="Search or type a brand..."
            options={brandOptions}
            value={brandValue?.value ?? ''}
            onChange={handleBrandSelect}
            allowCustom
            emptyMessage="Type to add a new brand."
          />
        </FormRow>

        <FormRow>
          <FormInput
            label="Current Stock"
            name="current_stock"
            type="number"
            value={form.current_stock}
            onChange={setField('current_stock')}
            error={errors.current_stock}
            disabled={mode === 'edit'}
          />
          <FormInput
            label="CGST Rate %"
            name="cgst"
            type="number"
            value={form.cgst}
            onChange={setField('cgst')}
            error={errors.cgst}
          />
          <FormInput
            label="SGST Rate %"
            name="sgst"
            type="number"
            value={form.sgst}
            onChange={setField('sgst')}
            error={errors.sgst}
          />
        </FormRow>

        <FormRow>
          <FormInput
            label="Purchase Price"
            name="purchase_price"
            type="number"
            value={form.purchase_price}
            onChange={setField('purchase_price')}
            error={errors.purchase_price}
          />
          <FormInput
            label="Sale Price"
            name="sale_price"
            type="number"
            value={form.sale_price}
            onChange={setField('sale_price')}
            error={errors.sale_price}
          />
        </FormRow>

        <FormRow>
          <FormInput
            label="MRP"
            name="mrp"
            type="number"
            value={form.mrp}
            onChange={setField('mrp')}
            error={errors.mrp}
          />
        </FormRow>

        <FormTextarea
          label="Description"
          name="description"
          value={form.description}
          onChange={setField('description')}
          rows={2}
        />

        {mode === 'edit' && (
          <div className="item-form-modal__meta">
            <span>
              Last Purchase Date: <strong>{formatDate(form.last_purchase_date)}</strong>
            </span>
            <span>
              Last Sale Date: <strong>{formatDate(form.last_sale_date)}</strong>
            </span>
          </div>
        )}
      </form>
    </Modal>
  );
}
