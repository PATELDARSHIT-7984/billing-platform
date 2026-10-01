import DoneBySelect from '../components/common/DoneBySelect';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import SearchableSelect from '../components/common/SearchableSelect';
import {
  FormCheckbox,
  FormInput,
  FormSelect,
  FormTextarea,
} from '../components/common/FormField';
import { useToast } from '../context/ToastContext';
import { fetchCustomers, fetchCustomerById } from '../services/customerService';
import { fetchItems } from '../services/itemService';
import {
  createSalesReturn,
  fetchSalesReturnById,
  fetchNextSalesReturnNumbers,
  updateSalesReturn,
} from '../services/salesReturnService';
import { extractErrorMessage } from '../services/api';
import { saveDraft, loadDraft, clearDraft } from '../utils/draftStorage';
import { UNIT_OPTIONS } from '../config/units';
import {
  computeLineAmounts,
  computeTotals,
  formatCurrency,
} from '../utils/calculations';
import '../styles/PurchaseEntry.css';
import '../styles/SalesEntry.css';

const today = () => new Date().toISOString().slice(0, 10);

const STATES = [
  '',
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
  'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
  'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
  'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
  'Andaman and Nicobar Islands', 'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Jammu and Kashmir',
  'Ladakh', 'Lakshadweep', 'Puducherry',
];

const STATE_OPTIONS = STATES.map((value) => ({
  value,
  label: value || 'Select State',
}));


const createEmptyDetails = () => ({
  customer_id: null,
  return_no: '',
  order_no: '',
  original_invoice_no: '',
  return_reason: '',
  return_date: today(),
  due_term: '',
  due_date: '',
  is_gst: true,
  address: '',
  city: '',
  customer_state: '',
  contact_no: '',
  email: '',
  done_by: '',
  brokerage: 0,
  broker_remarks: '',
  delivery_date: '',
  ship_to: '',
  ship_to_address: '',
  ship_state: '',
  transport: '',
  reference: '',
  remarks: '',
  show_shipping_address_on_bill: false,
});

const createEmptyItem = () => ({
  item_id: null,
  item_name: '',
  hsn_code: '',
  quantity: '',
  unit: UNIT_OPTIONS[0]?.value || 'Box',
  price: '',
  current_stock: '',
  disc_percent: 0,
  sgst: 0,
  cgst: 0,
  igst: 0,
});

const getCustomerId = (customer) => customer?.id ?? customer?.customer_id ?? null;
const getItemId = (item) => item?.id ?? item?.item_id ?? null;

let rowCounter = 0;

function addDays(dateString, daysValue) {
  if (!dateString || daysValue === '' || Number(daysValue) < 0) return '';
  const date = new Date(`${dateString}T00:00:00`);
  date.setDate(date.getDate() + Number(daysValue));
  return date.toISOString().slice(0, 10);
}

export default function SalesReturnEntry() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const newCustomerId = searchParams.get('newCustomerId');
  const editId = searchParams.get('edit');
  const loadedEditId = useRef(null);
  const DRAFT_KEY = 'sales-return-entry';

  const [customers, setCustomers] = useState([]);
  const [itemRecords, setItemRecords] = useState([]);
  const [details, setDetails] = useState(createEmptyDetails);
  const [itemForm, setItemForm] = useState(createEmptyItem);
  const [items, setItems] = useState([]);
  const [detailErrors, setDetailErrors] = useState({});
  const [itemErrors, setItemErrors] = useState({});
  const [editingIndex, setEditingIndex] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loadingSalesReturn, setLoadingSalesReturn] = useState(false);

  const loadCustomers = () => fetchCustomers({ search: '' })
    .then((data) => setCustomers(data.filter((customer) => customer.is_active !== false)))
    .catch((error) => toast.error(extractErrorMessage(error)));

  const loadItems = () => fetchItems({ search: '' })
    .then((data) => setItemRecords(data.filter((item) => item.is_active !== false)))
    .catch((error) => toast.error(extractErrorMessage(error)));

  useEffect(() => {
    loadCustomers();
    loadItems();

    const restoringDraft = !editId && Boolean(loadDraft(DRAFT_KEY));

    if (!editId && !restoringDraft) {
      fetchNextSalesReturnNumbers()
        .then((numbers) => {
          setDetails((previous) => ({
            ...previous,
            return_no: numbers.return_no || '',
            order_no: numbers.order_no || '',
          }));
        })
        .catch((error) => toast.error(extractErrorMessage(error)));
    }

  }, [editId]);

  useEffect(() => {
    if (editId) return;
    const draft = loadDraft(DRAFT_KEY);
    if (!draft) return;
    setDetails(draft.details);
    setItems(draft.items);
    setItemForm(draft.itemForm);
    clearDraft(DRAFT_KEY);
  }, []);

  useEffect(() => {
    if (!newCustomerId || !customers.length) return;
    const customer = customers.find((row) => Number(row.id) === Number(newCustomerId));
    if (!customer) return;

    fetchCustomerById(getCustomerId(customer))
      .then((full) => {
        setDetails((previous) => ({
          ...previous,
          customer_id: getCustomerId(full),
          address: full?.address || '',
          city: full?.city || '',
          customer_state: full?.state || '',
          contact_no: full?.mobile || '',
          email: full?.email || '',
        }));
      })
      .catch((error) => toast.error(extractErrorMessage(error)));
  }, [newCustomerId, customers]);


  useEffect(() => {
    if (
      !editId
      || !customers.length
      || !itemRecords.length
      || loadedEditId.current === editId
    ) return;

    loadedEditId.current = editId;
    setLoadingSalesReturn(true);

    fetchSalesReturnById(editId)
      .then((salesReturn) => {
        const customer = customers.find(
          (row) => Number(row.id) === Number(salesReturn.customer_id),
        );

        setDetails({
          customer_id: salesReturn.customer_id ?? null,
          return_no: salesReturn.return_no || '',
          order_no: salesReturn.order_no || '',
          original_invoice_no: salesReturn.original_invoice_no || '',
          return_reason: salesReturn.return_reason || '',
          return_date: salesReturn.return_date || today(),
          due_term: salesReturn.due_term ?? '',
          due_date: salesReturn.due_date || '',
          is_gst: salesReturn.is_gst !== false,
          address: salesReturn.address || customer?.address || '',
          city: salesReturn.city || customer?.city || '',
          customer_state: salesReturn.customer_state || salesReturn.state || customer?.state || '',
          contact_no: salesReturn.contact_no || customer?.mobile || '',
          email: salesReturn.email || customer?.email || '',
          done_by: salesReturn.done_by || '',
          _savedDoneBy: salesReturn.done_by || '',
          brokerage: salesReturn.brokerage ?? 0,
          broker_remarks: salesReturn.broker_remarks || '',
          delivery_date: salesReturn.delivery_date || '',
          ship_to: salesReturn.ship_to || '',
          ship_to_address: salesReturn.ship_to_address || '',
          ship_state: salesReturn.shipping_state || salesReturn.state || '',
          transport: salesReturn.transport || '',
          reference: salesReturn.reference || '',
          remarks: salesReturn.remarks || '',
          show_shipping_address_on_bill: Boolean(
            salesReturn.show_shipping_address_on_bill,
          ),
        });

        setItems((salesReturn.items || []).map((row) => {
          const master = itemRecords.find(
            (item) => Number(item.id) === Number(row.item_id),
          );

          return {
            _rowId: ++rowCounter,
            item_id: row.item_id,
            item_name: row.item_name || master?.name || '',
            hsn_code: row.hsn_code || master?.hsn_code || '',
            quantity: row.quantity ?? '',
            unit: row.unit || master?.unit || UNIT_OPTIONS[0]?.value || 'Box',
            price: row.rate ?? row.price ?? master?.sale_price ?? '',
            current_stock: master?.current_stock ?? row.current_stock ?? 0,
            disc_percent: row.disc_percent ?? 0,
            sgst: row.sgst ?? 0,
            cgst: row.cgst ?? 0,
            igst: row.igst ?? 0,
          };
        }));
      })
      .catch((error) => {
        toast.error(extractErrorMessage(error));
        navigate('/sales-return-history');
      })
      .finally(() => setLoadingSalesReturn(false));
  }, [editId, customers, itemRecords, navigate, toast]);

  const customerOptions = useMemo(
    () => customers.map((customer) => ({
      value: getCustomerId(customer),
      label: customer.customer_name || customer.name || 'Unnamed Customer',
      meta: customer.city || customer.mobile || '',
      record: customer,
    })),
    [customers],
  );

  const itemOptions = useMemo(
    () => itemRecords.map((item) => ({
      value: getItemId(item),
      label: item.name,
      meta: item.hsn_code ? `HSN ${item.hsn_code}` : 'HSN not set',
      record: item,
    })),
    [itemRecords],
  );

  const totals = useMemo(() => computeTotals(items), [items]);
  const liveAmount = useMemo(() => computeLineAmounts(itemForm).amount, [itemForm]);

  const changeDetail = (field, value) => {
    if (field === 'is_gst' && !value) {
      setItemForm((previous) => ({ ...previous, sgst: 0, cgst: 0, igst: 0 }));
      setItems((previous) => previous.map((item) => ({ ...item, sgst: 0, cgst: 0, igst: 0 })));
    }

    setDetails((previous) => {
      const next = { ...previous, [field]: value };
      if (field === 'return_date' || field === 'due_term') {
        next.due_date = addDays(
          field === 'return_date' ? value : previous.return_date,
          field === 'due_term' ? value : previous.due_term,
        );
      }
      return next;
    });

    setDetailErrors((previous) => ({ ...previous, [field]: '' }));
  };

  const applySelectedCustomer = (customer) => {
    setDetails((previous) => ({
      ...previous,
      customer_id: getCustomerId(customer),
      address: customer?.address || '',
      city: customer?.city || '',
      customer_state: customer?.state || '',
      contact_no: customer?.mobile || '',
      email: customer?.email || '',
      delivery_date: '',
      ship_to: '',
      ship_to_address: '',
      ship_state: '',
      transport: '',
      reference: '',
      remarks: '',
      show_shipping_address_on_bill: false,
    }));

    setItems([]);
    setItemForm(createEmptyItem());
    setEditingIndex(null);
    setItemErrors({});
  };

  const selectCustomer = (option) => {
    const nextId = option?.value ?? null;
    const currentId = details.customer_id ?? null;

    if (String(nextId ?? '') === String(currentId ?? '')) return;

    if (nextId == null || nextId === '') {
      applySelectedCustomer(null);
      return;
    }

    fetchCustomerById(nextId)
      .then((customer) => {
        applySelectedCustomer(customer);
        toast.success('Customer changed. Items and delivery details were cleared.');
      })
      .catch((error) => toast.error(extractErrorMessage(error)));
  };

  const selectItem = (option) => {
    if (!option) {
      setItemForm(createEmptyItem());
      return;
    }

    const item = option.record;
    setItemForm((previous) => ({
      ...previous,
      item_id: getItemId(item),
      item_name: item.name,
      hsn_code: item.hsn_code || '',
      unit: item.unit || previous.unit,
      price: item.sale_price ?? previous.price,
      current_stock: item.current_stock ?? 0,
      cgst: item.cgst ?? 0,
      sgst: item.sgst ?? 0,
      igst: 0,
    }));

    setItemErrors({});
  };

  const changeItem = (field, value) => {
    setItemForm((previous) => {
      const next = { ...previous, [field]: value };
      if ((field === 'sgst' || field === 'cgst') && Number(value) > 0) {
        next.igst = 0;
      }
      if (field === 'igst' && Number(value) > 0) {
        next.sgst = 0;
        next.cgst = 0;
      }
      return next;
    });
    setItemErrors((previous) => ({ ...previous, [field]: '' }));
  };

  const addItem = () => {
    const errors = {};
    if (!itemForm.item_id) errors.item_name = 'Select an item.';
    if (!itemForm.hsn_code.trim()) errors.hsn_code = 'HSN code is required.';
    if (!itemForm.quantity || Number(itemForm.quantity) <= 0) errors.quantity = 'Enter a valid quantity.';
    if (itemForm.price === '' || Number(itemForm.price) < 0) errors.price = 'Enter a valid price.';

    if (Object.keys(errors).length) {
      setItemErrors(errors);
      return;
    }

    if (editingIndex === null) {
      setItems((previous) => {
        const duplicateIndex = previous.findIndex(
          (row) => Number(row.item_id) === Number(itemForm.item_id),
        );

        if (duplicateIndex === -1) {
          return [...previous, { ...itemForm, _rowId: ++rowCounter }];
        }

        return previous.map((row, index) => (
          index === duplicateIndex
            ? { ...itemForm, _rowId: row._rowId }
            : row
        ));
      });
    } else {
      setItems((previous) => previous.map((row, index) => (
        index === editingIndex ? { ...itemForm, _rowId: row._rowId } : row
      )));
    }

    setItemForm(createEmptyItem());
    setEditingIndex(null);
    setItemErrors({});
  };

  const clearAll = () => {
    const numbers = {
      return_no: details.return_no,
      order_no: details.order_no,
    };
    setDetails({ ...createEmptyDetails(), ...numbers });
    setItemForm(createEmptyItem());
    setItems([]);
    setEditingIndex(null);
    setDetailErrors({});
    setItemErrors({});
  };

  const saveSalesReturn = () => {
    const errors = {};
    if (!details.customer_id) errors.customer_id = 'Customer is required.';
    if (!details.return_date) errors.return_date = 'Return date is required.';
    if (!details.return_reason.trim()) {
      errors.return_reason = 'Return reason is required.';
    }

    if (details.show_shipping_address_on_bill) {
      if (!details.ship_to.trim()) errors.ship_to = 'Ship To is required.';
      if (!details.ship_to_address.trim()) errors.ship_to_address = 'Ship To Address is required.';
      if (!details.ship_state) errors.ship_state = 'Shipping state is required.';
    }

    setDetailErrors(errors);
    if (Object.keys(errors).length) {
      toast.error('Please complete the required sales return details.');
      return;
    }
    if (!items.length) {
      toast.error('Add at least one item before saving.');
      return;
    }

    const payload = {
      return_no: details.return_no || null,
      order_no: details.order_no || null,
      original_invoice_no: details.original_invoice_no.trim() || null,
      return_date: details.return_date,
      customer_id: Number(details.customer_id),
      due_term: details.due_term === '' ? null : Number(details.due_term),
      due_date: details.due_date || null,
      is_gst: Boolean(details.is_gst),
            done_by: details.done_by || null,
      brokerage: Number(details.brokerage) || 0,
      broker_remarks: details.broker_remarks.trim() || null,
      return_reason: details.return_reason.trim(),
      address: details.address.trim() || null,
      city: details.city.trim() || null,
      state: details.customer_state || null,
      contact_no: details.contact_no.trim() || null,
      email: details.email.trim() || null,
      items: items.map((item) => ({
        item_id: Number(item.item_id),
        item_name: item.item_name,
        hsn_code: item.hsn_code,
        quantity: Number(item.quantity),
        unit: item.unit,
        price: Number(item.price),
        disc_percent: Number(item.disc_percent) || 0,
        sgst: details.is_gst ? Number(item.sgst) || 0 : 0,
        cgst: details.is_gst ? Number(item.cgst) || 0 : 0,
        igst: details.is_gst ? Number(item.igst) || 0 : 0,
      })),
      delivery_date: details.delivery_date || null,
      ship_to: details.ship_to.trim() || null,
      ship_to_address: details.ship_to_address.trim() || null,
      shipping_state: details.ship_state || null,
      transport: details.transport.trim() || null,
      reference: details.reference.trim() || null,
      remarks: details.remarks.trim() || null,
      show_shipping_address_on_bill: Boolean(details.show_shipping_address_on_bill),
    };

    setSaving(true);

    const request = editId
      ? updateSalesReturn(editId, payload)
      : createSalesReturn(payload);

    request
      .then((saved) => {
        if (editId) {
          toast.success(`Sales return updated. Return No. ${saved.return_no}`);
          navigate('/sales-return-history');
          return null;
        }

        toast.success(`Sales return saved. Return No. ${saved.return_no}`);
        clearAll();
        return fetchNextSalesReturnNumbers();
      })
      .then((numbers) => {
        if (!numbers) return;

        setDetails((previous) => ({
          ...previous,
          return_no: numbers.return_no,
          order_no: numbers.order_no,
        }));
      })
      .catch((error) => toast.error(extractErrorMessage(error)))
      .finally(() => setSaving(false));
  };

  return (
    <div className="page general-transaction purchase-entry-final">
      <header className="gt-page-header">
        <div>
          <h1>{editId ? 'Update Sales Return' : 'Sales Return Entry'}</h1>
          <p>{editId ? 'Update the selected sales return and its items.' : 'Create a customer sales return. Returned quantity is added back to stock.'}</p>
        </div>
        <span className="gt-status">{editId ? 'Edit Return' : 'Sales Return'}</span>
      </header>

      {loadingSalesReturn && (
        <div className="gt-loading-note">Loading sales return details...</div>
      )}

      <Card title="Transaction Details" className="gt-card">
        <div className="gt-details-grid">
          <div className="gt-with-action">
            <SearchableSelect
              label="Customer"
              options={customerOptions}
              value={details.customer_id}
              onChange={selectCustomer}
              placeholder="Search customer..."
              required
              error={detailErrors.customer_id}
            />
            <button
              type="button"
              className="gt-plus"
              onClick={() => {
                saveDraft(DRAFT_KEY, { details, items, itemForm });
                navigate('/customers?openAdd=1&returnTo=/sales-return-entry');
              }}
              title="Add new customer"
              aria-label="Add new customer"
            >
              +
            </button>
          </div>

          <FormInput label="Return No." value={details.return_no} disabled />
          <FormInput label="Order No." value={details.order_no} disabled />
          <FormInput
            label="Original Invoice No."
            value={details.original_invoice_no}
            onChange={(value) => changeDetail('original_invoice_no', value)}
            placeholder="Optional original sales invoice"
          />
          <FormInput
            label="Return Reason"
            value={details.return_reason}
            onChange={(value) => changeDetail('return_reason', value)}
            placeholder="Damaged, wrong item, customer return..."
            required
            error={detailErrors.return_reason}
          />
          <FormInput
            label="Return Date"
            type="date"
            value={details.return_date}
            onChange={(value) => changeDetail('return_date', value)}
            required
            error={detailErrors.return_date}
          />
          <FormInput
            label="Due Term (Days)"
            type="number"
            min="0"
            value={details.due_term}
            onChange={(value) => changeDetail('due_term', value)}
          />
          <FormInput label="Due Date" type="date" value={details.due_date} disabled />

          <FormTextarea label="Address" value={details.address} onChange={() => {}} rows={2} disabled />
          <FormInput label="City" value={details.city} onChange={() => {}} disabled />
          <FormSelect
            label="State"
            value={details.customer_state || ''}
            onChange={(value) => changeDetail('customer_state', value)}
            options={STATE_OPTIONS}
          />
          <FormInput label="Contact No." value={details.contact_no} onChange={() => {}} disabled />
          <FormInput label="Email" value={details.email} onChange={() => {}} disabled />
          <DoneBySelect
            label="Done By"
            value={details.done_by}
            onChange={(value) => changeDetail('done_by', value)}
            savedValue={details._savedDoneBy}
          />
          <FormCheckbox
            label="GST Applicable"
            checked={details.is_gst}
            onChange={(value) => changeDetail('is_gst', value)}
          />
          <FormInput
            label="Brokerage"
            type="number"
            min="0"
            value={details.brokerage}
            onChange={(value) => changeDetail('brokerage', value)}
          />
          <div className="gt-span-2">
            <FormInput
              label="Broker's Remarks"
              value={details.broker_remarks}
              onChange={(value) => changeDetail('broker_remarks', value)}
            />
          </div>
        </div>
      </Card>

      <Card title="Item Entry" className="gt-card">
        <div className="gt-item-top">
          <SearchableSelect
            label="Item Name"
            options={itemOptions}
            value={itemForm.item_id}
            onChange={selectItem}
            placeholder="Search existing Item Master item..."
            required
            error={itemErrors.item_name}
            emptyMessage="No active Item Master item found."
          />
          <FormInput label="HSN Code" value={itemForm.hsn_code} onChange={() => {}} disabled required />
          <FormSelect label="Unit" value={itemForm.unit} onChange={(value) => changeItem('unit', value)} options={UNIT_OPTIONS} />
        </div>

        <div className="gt-item-numbers sales-entry__item-numbers">
          <FormInput
            label="Quantity"
            type="number"
            min="0"
            value={itemForm.quantity}
            onChange={(value) => changeItem('quantity', value)}
            required
            error={itemErrors.quantity}
          />
          <FormInput
            label="Price"
            type="number"
            min="0"
            value={itemForm.price}
            onChange={(value) => changeItem('price', value)}
            required
            error={itemErrors.price}
          />
          <div className="sales-stock-box">
            <span>Stock</span>
            <strong>{itemForm.item_id ? itemForm.current_stock : '—'}</strong>
          </div>
          <FormInput label="Discount %" type="number" min="0" max="100" value={itemForm.disc_percent} onChange={(value) => changeItem('disc_percent', value)} />
          <FormInput label="SGST %" type="number" min="0" max="100" value={details.is_gst ? itemForm.sgst : 0} onChange={(value) => changeItem('sgst', value)} disabled={!details.is_gst || Number(itemForm.igst) > 0} />
          <FormInput label="CGST %" type="number" min="0" max="100" value={details.is_gst ? itemForm.cgst : 0} onChange={(value) => changeItem('cgst', value)} disabled={!details.is_gst || Number(itemForm.igst) > 0} />
          <FormInput label="IGST %" type="number" min="0" max="100" value={details.is_gst ? itemForm.igst : 0} onChange={(value) => changeItem('igst', value)} disabled={!details.is_gst || Number(itemForm.sgst) > 0 || Number(itemForm.cgst) > 0} />
          <div className="gt-live-amount"><span>Amount</span><strong>{formatCurrency(liveAmount)}</strong></div>
        </div>

        <div className="gt-item-actions">
          <Button variant="secondary" onClick={() => { setItemForm(createEmptyItem()); setEditingIndex(null); }}>Clear</Button>
          <Button variant="primary" onClick={addItem}>{editingIndex === null ? 'Add Item' : 'Update Item'}</Button>
        </div>
      </Card>

      <Card title="Transaction Items" className="gt-card">
        <div className="gt-table-wrap">
          <table className="gt-table">
            <thead>
              <tr>
                <th>Sr.</th><th>Item</th><th>HSN</th><th>Qty</th><th>Unit</th>
                <th>Price</th><th>Disc.</th><th>SGST</th><th>CGST</th><th>IGST</th>
                <th>Amount</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!items.length ? (
                <tr><td colSpan="12" className="gt-empty">No items added yet.</td></tr>
              ) : items.map((row, index) => (
                <tr key={row._rowId}>
                  <td>{index + 1}</td><td>{row.item_name}</td><td>{row.hsn_code}</td>
                  <td>{row.quantity}</td><td>{row.unit}</td><td>{formatCurrency(row.price)}</td>
                  <td>{row.disc_percent}%</td><td>{row.sgst}%</td><td>{row.cgst}%</td><td>{row.igst}%</td>
                  <td>{formatCurrency(computeLineAmounts(row).amount)}</td>
                  <td>
                    <button type="button" className="gt-link" onClick={() => { setItemForm(row); setEditingIndex(index); }}>Edit</button>
                    <button type="button" className="gt-link gt-link--danger" onClick={() => setItems((previous) => previous.filter((_, rowIndex) => rowIndex !== index))}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="gt-bottom-grid">
        <Card title="Extra Address & Delivery Details" className="gt-card">
          <FormCheckbox
            label="Show this shipping address on bill"
            checked={details.show_shipping_address_on_bill}
            onChange={(value) => changeDetail('show_shipping_address_on_bill', value)}
          />
          <div className="gt-delivery-grid">
            <FormInput label="Delivery Date" type="date" value={details.delivery_date} onChange={(value) => changeDetail('delivery_date', value)} />
            <FormInput label="Ship To" value={details.ship_to} onChange={(value) => changeDetail('ship_to', value)} required={details.show_shipping_address_on_bill} error={detailErrors.ship_to} />
            <FormInput label="Transport" value={details.transport} onChange={(value) => changeDetail('transport', value)} />
            <div className="gt-span-2">
              <FormTextarea label="Ship To Address" value={details.ship_to_address} onChange={(value) => changeDetail('ship_to_address', value)} rows={3} required={details.show_shipping_address_on_bill} error={detailErrors.ship_to_address} />
            </div>
            <FormSelect label="State" value={details.ship_state} onChange={(value) => changeDetail('ship_state', value)} options={STATE_OPTIONS} required={details.show_shipping_address_on_bill} error={detailErrors.ship_state} />
            <FormInput label="Reference" value={details.reference} onChange={(value) => changeDetail('reference', value)} />
            <div className="gt-span-2"><FormTextarea label="Remarks" value={details.remarks} onChange={(value) => changeDetail('remarks', value)} rows={3} /></div>
          </div>
        </Card>

        <Card title="Total Summary" className="gt-card gt-summary">
          <div><span>Taxable Amount</span><strong>{formatCurrency(totals.taxableAmount)}</strong></div>
          <div><span>SGST Total</span><strong>{formatCurrency(totals.sgstTotal)}</strong></div>
          <div><span>CGST Total</span><strong>{formatCurrency(totals.cgstTotal)}</strong></div>
          <div><span>IGST Total</span><strong>{formatCurrency(totals.igstTotal)}</strong></div>
          <div className="gt-grand"><span>Grand Total</span><strong>{formatCurrency(totals.grandTotal)}</strong></div>
        </Card>
      </div>

      <div className="gt-footer-actions">
        <Button variant="secondary" onClick={clearAll} disabled={saving}>Clear</Button>
        <Button variant="primary" onClick={saveSalesReturn} disabled={saving}>{saving
          ? (editId ? 'Updating Return...' : 'Saving Return...')
          : (editId ? 'Update Return' : 'Save Return')}</Button>
      </div>
    </div>
  );
}
