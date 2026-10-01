import DoneBySelect from '../../components/common/DoneBySelect';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import SearchableSelect from '../../components/common/SearchableSelect';
import {
  FormInput,
  FormSelect,
  FormTextarea,
  FormCheckbox,
} from '../../components/common/FormField';
import PartyFormModal from '../PartyFormModal';
import { useToast } from '../../context/ToastContext';
import { fetchParties, createParty } from '../../services/partyService';
import { fetchItems } from '../../services/itemService';
import { createPurchaseReturn, fetchNextPurchaseReturnNumbers, fetchPurchaseReturnById, updatePurchaseReturn } from '../../services/purchaseReturnService';
import { extractErrorMessage } from '../../services/api';
import { UNIT_OPTIONS } from '../../config/units';
import {
  computeLineAmounts,
  computeTotals,
  formatCurrency,
} from '../../utils/calculations';
import '../../styles/PurchaseEntry.css';

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
  party_id: null,
  return_no: '',
  order_no: '',
  original_bill_no: '',
  return_reason: '',
  return_date: today(),
  due_term: '',
  due_date: '',
  is_gst: true,
  address: '',
  city: '',
  party_state: '',
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
  current_stock: 0,
  disc_percent: 0,
  sgst: 0,
  cgst: 0,
  igst: 0,
});

let rowCounter = 0;

function addDays(dateString, daysValue) {
  if (!dateString || daysValue === '' || Number(daysValue) < 0) return '';

  const date = new Date(`${dateString}T00:00:00`);
  date.setDate(date.getDate() + Number(daysValue));
  return date.toISOString().slice(0, 10);
}

export default function PurchaseReturnEntry() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editId = searchParams.get('edit');
  const loadedEditId = useRef(null);

  const [parties, setParties] = useState([]);
  const [itemRecords, setItemRecords] = useState([]);
  const [details, setDetails] = useState(createEmptyDetails);
  const [itemForm, setItemForm] = useState(createEmptyItem);
  const [items, setItems] = useState([]);
  const [detailErrors, setDetailErrors] = useState({});
  const [itemErrors, setItemErrors] = useState({});
  const [editingIndex, setEditingIndex] = useState(null);
  const [partyModalOpen, setPartyModalOpen] = useState(false);
  const [submittingParty, setSubmittingParty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingPurchase, setLoadingPurchase] = useState(false);

  const loadParties = () => (
    fetchParties({ search: '' })
      .then((data) => setParties(data.filter((party) => party.party_type === 'Supplier')))
      .catch((error) => toast.error(extractErrorMessage(error)))
  );

  const loadItems = () => (
    fetchItems({ search: '' })
      .then((data) => setItemRecords(data.filter((item) => item.is_active !== false)))
      .catch((error) => toast.error(extractErrorMessage(error)))
  );

  useEffect(() => {
    loadParties();
    loadItems();

    if (!editId) {
      fetchNextPurchaseReturnNumbers()
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
    if (!editId || !parties.length || loadedEditId.current === editId) return;

    setLoadingPurchase(true);
    fetchPurchaseReturnById(editId)
      .then((purchaseReturn) => {
        const selectedParty = parties.find((party) => party.id === purchaseReturn.party_id);

        setDetails({
          party_id: purchaseReturn.party_id,
          return_no: purchaseReturn.return_no || '',
          order_no: purchaseReturn.order_no || '',
          original_bill_no: purchaseReturn.original_bill_no || '',
          return_reason: purchaseReturn.return_reason || '',
          return_date: purchaseReturn.return_date || today(),
          due_term: purchaseReturn.due_term ?? '',
          due_date: purchaseReturn.due_date || '',
          is_gst: purchaseReturn.is_gst !== false,
          address: selectedParty?.address || '',
          city: selectedParty?.city || '',
          party_state: selectedParty?.state || '',
          contact_no: purchaseReturn.contact_no || (
            selectedParty
              ? `${selectedParty.country_code || ''} ${selectedParty.mobile || ''}`.trim()
              : ''
          ),
          email: purchaseReturn.email || selectedParty?.email || '',
          done_by: purchaseReturn.done_by || '',
          _savedDoneBy: purchaseReturn.done_by || '',
          brokerage: purchaseReturn.brokerage ?? 0,
          broker_remarks: purchaseReturn.broker_remarks || '',
          delivery_date: purchaseReturn.delivery_date || '',
          ship_to: purchaseReturn.ship_to || '',
          ship_to_address: purchaseReturn.ship_to_address || '',
          ship_state: purchaseReturn.state || '',
          transport: purchaseReturn.transport || '',
          reference: purchaseReturn.reference || '',
          remarks: purchaseReturn.remarks || '',
          show_shipping_address_on_bill: Boolean(purchaseReturn.show_shipping_address_on_bill),
        });

        setItems((purchaseReturn.items || []).map((item) => ({
          ...item,
          current_stock: Number(
            item.available_stock
            ?? item.current_stock
            ?? item.quantity
            ?? 0
          ),
          _rowId: ++rowCounter,
        })));

        loadedEditId.current = editId;
      })
      .catch((error) => {
        toast.error(extractErrorMessage(error));
        navigate('/purchase-return-history');
      })
      .finally(() => setLoadingPurchase(false));
  }, [editId, parties, navigate, toast]);

  const partyOptions = useMemo(
    () => parties.map((party) => ({
      value: party.id,
      label: party.name,
      meta: party.city || party.mobile || '',
      record: party,
    })),
    [parties],
  );

  const itemOptions = useMemo(
    () => itemRecords.map((item) => ({
      value: item.id,
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

  const applySelectedParty = (party) => {
    setDetails((previous) => ({
      ...previous,
      party_id: party?.id || null,
      address: party?.address || '',
      city: party?.city || '',
      party_state: party?.state || '',
      contact_no: party
        ? `${party.country_code || ''} ${party.mobile || ''}`.trim()
        : '',
      email: party?.email || '',

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
    setDetailErrors((previous) => ({
      ...previous,
      party_id: '',
      ship_to: '',
      ship_to_address: '',
      ship_state: '',
    }));
  };

  const selectParty = (option) => {
    const nextParty = option?.record || null;
    const nextPartyId = nextParty?.id || null;

    if (nextPartyId === details.party_id) return;

    applySelectedParty(nextParty);

    if (nextParty) {
      toast.success('Supplier changed. Items and delivery details were cleared.');
    }
  };

  const saveParty = (payload) => {
    setSubmittingParty(true);

    createParty({ ...payload, party_type: 'Supplier' })
      .then((created) => {
        setParties((previous) => [...previous, created]);
        applySelectedParty(created);
        setPartyModalOpen(false);
        toast.success('Supplier added and selected. Items and delivery details were cleared.');
      })
      .catch((error) => toast.error(extractErrorMessage(error)))
      .finally(() => setSubmittingParty(false));
  };

  const selectItem = (option) => {
    if (!option) {
      setItemForm((previous) => ({
        ...previous,
        item_id: null,
        item_name: '',
      }));
      return;
    }

    const item = option.record;

    setItemForm((previous) => ({
      ...previous,
      item_id: item.id,
      item_name: item.name,
      hsn_code: item.hsn_code || '',
      unit: item.unit || previous.unit,
      price: item.purchase_price ?? previous.price,
      current_stock: Number(item.current_stock ?? 0) + (
        editingIndex !== null
        && Number(items[editingIndex]?.item_id) === Number(item.id)
          ? Number(items[editingIndex]?.quantity || 0)
          : 0
      ),
      cgst: item.cgst ?? previous.cgst,
      sgst: item.sgst ?? previous.sgst,
      igst: 0,
    }));

    setItemErrors((previous) => ({
      ...previous,
      item_id: '',
      item_name: '',
      hsn_code: '',
    }));
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

    if (!itemForm.item_id) errors.item_name = 'Select an item from Item Master.';
    if (!itemForm.hsn_code.trim()) errors.hsn_code = 'HSN code is required.';
    if (!itemForm.quantity || Number(itemForm.quantity) <= 0) {
      errors.quantity = 'Enter a valid quantity.';
    }
    if (itemForm.price === '' || Number(itemForm.price) < 0) {
      errors.price = 'Enter a valid price.';
    }


    if (Object.keys(errors).length) {
      setItemErrors(errors);
      return;
    }

    if (editingIndex === null) {
      setItems((previous) => [
        ...previous,
        { ...itemForm, _rowId: ++rowCounter },
      ]);
    } else {
      setItems((previous) => previous.map((row, index) => (
        index === editingIndex
          ? { ...itemForm, _rowId: row._rowId }
          : row
      )));
    }

    setItemForm(createEmptyItem());
    setEditingIndex(null);
    setItemErrors({});
  };

  const clearItemForm = () => {
    setItemForm(createEmptyItem());
    setEditingIndex(null);
    setItemErrors({});
  };

  const clearAll = () => {
    setDetails(createEmptyDetails());
    setItemForm(createEmptyItem());
    setItems([]);
    setEditingIndex(null);
    setDetailErrors({});
    setItemErrors({});
  };

  const validatePurchase = () => {
    const errors = {};

    if (!details.party_id) errors.party_id = 'Supplier is required.';
    if (!details.return_no.trim()) errors.return_no = 'Return number is required.';
    if (!details.return_date) errors.return_date = 'Return date is required.';
    if (!details.return_reason.trim()) {
      errors.return_reason = 'Return reason is required.';
    }

    if (details.show_shipping_address_on_bill) {
      if (!details.ship_to.trim()) errors.ship_to = 'Ship To is required.';
      if (!details.ship_to_address.trim()) {
        errors.ship_to_address = 'Ship To Address is required.';
      }
      if (!details.ship_state) errors.ship_state = 'Shipping state is required.';
    }

    return errors;
  };

  const savePurchaseReturn = () => {
    const errors = validatePurchase();
    setDetailErrors(errors);

    if (Object.keys(errors).length) {
      toast.error('Please complete the required purchase details.');
      return;
    }

    if (!items.length) {
      toast.error('Add at least one item before saving.');
      return;
    }

    const payload = {
      return_no: details.return_no.trim() || null,
      order_no: details.order_no.trim() || null,
      original_bill_no: details.original_bill_no.trim() || null,
      return_date: details.return_date,
      due_term: details.due_term === '' ? null : Number(details.due_term),
      due_date: details.due_date || null,
      party_id: Number(details.party_id),
      is_gst: Boolean(details.is_gst),
      contact_person: null,
      contact_no: details.contact_no.trim() || null,
      email: details.email.trim() || null,
      done_by: details.done_by || null,
      brokerage: Number(details.brokerage) || 0,
      broker_remarks: details.broker_remarks.trim() || null,
      return_reason: details.return_reason.trim(),
      address: details.address.trim() || null,
      city: details.city.trim() || null,
      party_state: details.party_state || null,
      items: items.map((item) => ({
        item_id: Number(item.item_id),
        item_name: item.item_name,
        hsn_code: item.hsn_code.trim(),
        quantity: Number(item.quantity),
        unit: item.unit,
        price: Number(item.price),
        disc_percent: Number(item.disc_percent) || 0,
        sgst: details.is_gst ? Number(item.sgst) || 0 : 0,
        cgst: details.is_gst ? Number(item.cgst) || 0 : 0,
        igst: details.is_gst ? Number(item.igst) || 0 : 0,
      })),
      delivery_date: details.delivery_date || null,
      transport: details.transport.trim() || null,
      ship_to: details.ship_to.trim() || null,
      ship_to_address: details.ship_to_address.trim() || null,
      state: details.ship_state || null,
      reference: details.reference.trim() || null,
      remarks: details.remarks.trim() || null,
      show_shipping_address_on_bill: Boolean(
        details.show_shipping_address_on_bill,
      ),
    };

    setSaving(true);

    const request = editId
      ? updatePurchaseReturn(editId, payload)
      : createPurchaseReturn(payload);

    request
      .then((savedPurchase) => {
        toast.success(
          editId
            ? `Purchase return updated. Return No. ${savedPurchase.return_no}`
            : `Purchase return saved. Return No. ${savedPurchase.return_no}`,
        );

        if (editId) {
          navigate('/purchase-return-history');
        } else {
          clearAll();
          fetchNextPurchaseReturnNumbers()
            .then((numbers) => {
              setDetails((previous) => ({
                ...previous,
                return_no: numbers.return_no || '',
                order_no: numbers.order_no || '',
              }));
            })
            .catch((error) => toast.error(extractErrorMessage(error)));
        }
      })
      .catch((error) => toast.error(extractErrorMessage(error)))
      .finally(() => setSaving(false));
  };

  return (
    <div className="page general-transaction purchase-entry-final">
      <header className="gt-page-header">
        <div>
          <h1>{editId ? 'Update Purchase Return' : 'Purchase Return Entry'}</h1>
          <p>{editId ? 'Update the selected purchase return and its items.' : 'Return purchased items to a supplier and reduce Item Master stock safely.'}</p>
        </div>
        <span className="gt-status">{editId ? 'Edit Return' : 'Purchase Return'}</span>
      </header>

      {loadingPurchase && (
        <div className="gt-loading-note">Loading purchase return details...</div>
      )}

      <Card title="Transaction Details" className="gt-card">
        <div className="gt-details-grid">
          <div className="gt-with-action">
            <SearchableSelect
              label="Supplier"
              name="party_id"
              options={partyOptions}
              value={details.party_id}
              onChange={selectParty}
              placeholder="Search supplier..."
              required
              error={detailErrors.party_id}
              emptyMessage="No supplier found. Use + to add one."
            />
            <button
              type="button"
              className="gt-plus"
              onClick={() => setPartyModalOpen(true)}
              title="Add new supplier"
              aria-label="Add new supplier"
            >
              +
            </button>
          </div>

          <FormInput
            label="Return No."
            value={details.return_no}
            disabled
            required
            error={detailErrors.return_no}
          />

          <FormInput
            label="Order No."
            value={details.order_no}
            disabled
          />

          <FormInput
            label="Original Purchase Bill No."
            value={details.original_bill_no}
            onChange={(value) => changeDetail('original_bill_no', value)}
            placeholder="Optional original bill reference"
          />

          <FormInput
            label="Return Reason"
            value={details.return_reason}
            onChange={(value) => changeDetail('return_reason', value)}
            placeholder="Damaged, wrong item, excess stock..."
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
            placeholder="e.g. 30"
          />

          <FormInput
            label="Due Date"
            type="date"
            value={details.due_date}
            disabled
          />

          <FormTextarea
            label="Address"
            value={details.address}
            onChange={(value) => changeDetail('address', value)}
            rows={2}
          />

          <FormInput
            label="City"
            value={details.city}
            onChange={(value) => changeDetail('city', value)}
          />

          <FormSelect
            label="State"
            value={details.party_state || ''}
            onChange={(value) => changeDetail('party_state', value)}
            options={STATE_OPTIONS}
          />

          <FormInput
            label="Contact No."
            value={details.contact_no}
            onChange={(value) => changeDetail('contact_no', value)}
          />

          <FormInput
            label="Email (Optional)"
            type="email"
            value={details.email}
            onChange={(value) => changeDetail('email', value)}
          />

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

      <Card
        title="Item Entry"
        subtitle="Search an existing item from Item Master and add it to this purchase return."
        className="gt-card"
      >
        <div className="gt-item-top">
          <div className="gt-with-action">
            <SearchableSelect
              label="Item Name"
              name="item_name"
              options={itemOptions}
              value={itemForm.item_id}
              onChange={selectItem}
              placeholder="Search item name..."
              required
              error={itemErrors.item_name}
              emptyMessage="No active item found."
            />
            
          </div>

          <FormInput
            label="HSN Code"
            value={itemForm.hsn_code}
            onChange={(value) => changeItem('hsn_code', value)}
            required
            error={itemErrors.hsn_code}
          />

          <FormSelect
            label="Unit"
            value={itemForm.unit}
            onChange={(value) => changeItem('unit', value)}
            options={UNIT_OPTIONS}
          />
        </div>

        <div className="gt-item-numbers">
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
          <div className="gt-live-amount">
            <span>Available Stock</span>
            <strong>
              {itemForm.item_id
                ? Number(itemForm.current_stock || 0)
                : '—'}
            </strong>
          </div>

          <FormInput
            label="Discount %"
            type="number"
            min="0"
            max="100"
            value={itemForm.disc_percent}
            onChange={(value) => changeItem('disc_percent', value)}
          />

          <FormInput
            label="SGST %"
            type="number"
            min="0"
            max="100"
            value={details.is_gst ? itemForm.sgst : 0}
            onChange={(value) => changeItem('sgst', value)}
            disabled={!details.is_gst || Number(itemForm.igst) > 0}
          />

          <FormInput
            label="CGST %"
            type="number"
            min="0"
            max="100"
            value={details.is_gst ? itemForm.cgst : 0}
            onChange={(value) => changeItem('cgst', value)}
            disabled={!details.is_gst || Number(itemForm.igst) > 0}
          />

          <FormInput
            label="IGST %"
            type="number"
            min="0"
            max="100"
            value={details.is_gst ? itemForm.igst : 0}
            onChange={(value) => changeItem('igst', value)}
            disabled={
              !details.is_gst
              || Number(itemForm.sgst) > 0
              || Number(itemForm.cgst) > 0
            }
          />

          <div className="gt-live-amount">
            <span>Amount</span>
            <strong>{formatCurrency(liveAmount)}</strong>
          </div>
        </div>

        <div className="gt-item-actions">
          <Button variant="secondary" onClick={clearItemForm}>Clear</Button>
          <Button variant="primary" onClick={addItem}>
            {editingIndex === null ? 'Add Item' : 'Update Item'}
          </Button>
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
                <tr>
                  <td colSpan="12" className="gt-empty">
                    No items added yet. Use the item form above.
                  </td>
                </tr>
              ) : items.map((row, index) => (
                <tr key={row._rowId}>
                  <td>{index + 1}</td>
                  <td>{row.item_name}</td>
                  <td>{row.hsn_code}</td>
                  <td>{row.quantity}</td>
                  <td>{row.unit}</td>
                  <td>{formatCurrency(row.price)}</td>
                  <td>{row.disc_percent}%</td>
                  <td>{row.sgst}%</td>
                  <td>{row.cgst}%</td>
                  <td>{row.igst}%</td>
                  <td>{formatCurrency(computeLineAmounts(row).amount)}</td>
                  <td>
                    <button
                      type="button"
                      className="gt-link"
                      onClick={() => {
                        setItemForm({
                          ...row,
                          current_stock: Number(
                            row.current_stock
                            ?? row.available_stock
                            ?? row.quantity
                            ?? 0
                          ),
                        });
                        setEditingIndex(index);
                        setItemErrors({});
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="gt-link gt-link--danger"
                      onClick={() => setItems((previous) => (
                        previous.filter((_, rowIndex) => rowIndex !== index)
                      ))}
                    >
                      Delete
                    </button>
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
            <FormInput
              label="Delivery Date"
              type="date"
              value={details.delivery_date}
              onChange={(value) => changeDetail('delivery_date', value)}
            />

            <FormInput
              label="Ship To"
              value={details.ship_to}
              onChange={(value) => changeDetail('ship_to', value)}
              required={details.show_shipping_address_on_bill}
              error={detailErrors.ship_to}
            />

            <FormInput
              label="Transport"
              value={details.transport}
              onChange={(value) => changeDetail('transport', value)}
            />

            <div className="gt-span-2">
              <FormTextarea
                label="Ship To Address"
                value={details.ship_to_address}
                onChange={(value) => changeDetail('ship_to_address', value)}
                rows={3}
                required={details.show_shipping_address_on_bill}
                error={detailErrors.ship_to_address}
              />
            </div>

            <FormSelect
              label="State"
              value={details.ship_state}
              onChange={(value) => changeDetail('ship_state', value)}
              options={STATE_OPTIONS}
              required={details.show_shipping_address_on_bill}
              error={detailErrors.ship_state}
            />

            <FormInput
              label="Reference"
              value={details.reference}
              onChange={(value) => changeDetail('reference', value)}
            />

            <div className="gt-span-2">
              <FormTextarea
                label="Remarks"
                value={details.remarks}
                onChange={(value) => changeDetail('remarks', value)}
                rows={3}
              />
            </div>
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
        <Button variant="secondary" onClick={clearAll} disabled={saving}>
          Clear
        </Button>
        <Button variant="primary" onClick={savePurchaseReturn} disabled={saving}>
          {saving
          ? (editId ? 'Updating Return...' : 'Saving Return...')
          : (editId ? 'Update Return' : 'Save Return')}
        </Button>
      </div>

      <PartyFormModal
        open={partyModalOpen}
        mode="add"
        submitting={submittingParty}
        onClose={() => setPartyModalOpen(false)}
        onSubmit={saveParty}
      />
    </div>
  );
}
