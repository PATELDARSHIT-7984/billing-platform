import AccountSelector from '../../components/common/AccountSelector';
import { fetchAccountRecord } from '../../services/accountService';
import { handleEnterNavigation } from '../../utils/enterNavigation';
import DoneBySelect from '../../components/common/DoneBySelect';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import Button from '../../components/common/Button';
import Card from '../../components/common/Card';
import SearchableSelect from '../../components/common/SearchableSelect';
import {
  FormCheckbox,
  FormInput,
  FormSelect,
  FormTextarea,
} from '../../components/common/FormField';

import PartyFormModal from '../PartyFormModal';

import { useToast } from '../../context/ToastContext';
import { createParty } from '../../services/partyService';
import { fetchItems } from '../../services/itemService';
import {
  createPurchase,
  fetchPurchaseById,
  updatePurchase,
} from '../../services/purchaseService';
import { extractErrorMessage } from '../../services/api';

import { UNIT_OPTIONS } from '../../config/units';
import {
  computeLineAmounts,
  computeTotals,
  formatCurrency,
} from '../../utils/calculations';

import '../../styles/PurchaseEntry.css';

const STATES = [
  '',
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chhattisgarh',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
  'Andaman and Nicobar Islands',
  'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi',
  'Jammu and Kashmir',
  'Ladakh',
  'Lakshadweep',
  'Puducherry',
];

const STATE_OPTIONS = STATES.map((value) => ({
  value,
  label: value || 'Select State',
}));


const today = () => new Date().toISOString().slice(0, 10);

const emptyDetails = () => ({
  party_id: null,
  bill_no: '',
  order_no: '',
  bill_date: today(),
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

const emptyItem = () => ({
  item_id: null,
  item_name: '',
  hsn_code: '',
  quantity: '',
  unit: UNIT_OPTIONS[0]?.value || 'Box',
  price: '',
  disc_percent: 0,
  sgst: 0,
  cgst: 0,
  igst: 0,
});

let rowCounter = 0;

function cleanText(value) {
  const text = String(value ?? '').trim();
  return text || null;
}

function addDays(dateString, daysValue) {
  if (
    !dateString
    || daysValue === ''
    || daysValue === null
    || Number(daysValue) < 0
  ) {
    return '';
  }

  const date = new Date(`${dateString}T00:00:00`);
  date.setDate(date.getDate() + Number(daysValue));

  return date.toISOString().slice(0, 10);
}

function mapPurchaseToDetails(purchase, selectedParty) {
  return {
    _account: selectedParty,
    party_id: purchase.party_id,
    bill_no: purchase.bill_no || '',
    order_no: purchase.order_no || '',
    bill_date: purchase.bill_date || today(),
    due_term: purchase.due_term ?? '',
    due_date: purchase.due_date || '',
    is_gst: purchase.is_gst !== false,

    address: selectedParty?.address || '',
    city: selectedParty?.city || '',
    party_state: selectedParty?.state || '',

    contact_no:
      purchase.contact_no
      || (
        selectedParty
          ? `${selectedParty.country_code || ''} ${selectedParty.mobile || ''}`.trim()
          : ''
      ),

    email: purchase.email || selectedParty?.email || '',
    done_by: purchase.done_by || '',
    _savedDoneBy: purchase.done_by || '',
    brokerage: purchase.brokerage ?? 0,
    broker_remarks: purchase.broker_remarks || '',

    delivery_date: purchase.delivery_date || '',
    ship_to: purchase.ship_to || '',
    ship_to_address: purchase.ship_to_address || '',
    ship_state: purchase.state || '',
    transport: purchase.transport || '',
    reference: purchase.reference || '',
    remarks: purchase.remarks || '',

    show_shipping_address_on_bill: Boolean(
      purchase.show_shipping_address_on_bill,
    ),
  };
}

function mapPurchaseItems(items = []) {
  return items.map((item) => ({
    ...item,
    _rowId: ++rowCounter,
  }));
}

function validatePurchaseDetails(details) {
  const errors = {};

  if (!details.party_id) {
    errors.party_id = 'Supplier is required.';
  }

  if (!details.bill_no.trim()) {
    errors.bill_no = 'Bill number is required.';
  }

  if (!details.bill_date) {
    errors.bill_date = 'Bill date is required.';
  }

  if (details.show_shipping_address_on_bill) {
    if (!details.ship_to.trim()) {
      errors.ship_to = 'Ship To is required.';
    }

    if (!details.ship_to_address.trim()) {
      errors.ship_to_address = 'Ship To Address is required.';
    }

    if (!details.ship_state) {
      errors.ship_state = 'Shipping state is required.';
    }
  }

  return errors;
}

function validateItem(itemForm) {
  const errors = {};

  if (!itemForm.item_name.trim()) {
    errors.item_name = 'Item name is required.';
  }

  if (!itemForm.hsn_code.trim()) {
    errors.hsn_code = 'HSN code is required.';
  }

  if (!itemForm.quantity || Number(itemForm.quantity) <= 0) {
    errors.quantity = 'Enter a valid quantity.';
  }

  if (itemForm.price === '' || Number(itemForm.price) < 0) {
    errors.price = 'Enter a valid price.';
  }

  return errors;
}

function buildPurchasePayload(details, items) {
  return {
    bill_no: details.bill_no.trim(),
    order_no: cleanText(details.order_no),
    bill_date: details.bill_date,

    due_term:
      details.due_term === ''
        ? null
        : Number(details.due_term),

    due_date: details.due_date || null,
    party_id: Number(details.party_id),
    is_gst: Boolean(details.is_gst),

    contact_person: null,
    contact_no: cleanText(details.contact_no),
    email: cleanText(details.email),

    done_by: details.done_by || null,
    brokerage: Number(details.brokerage) || 0,
    broker_remarks: cleanText(details.broker_remarks),

    items: items.map((item) => ({
      item_id: (
        item.item_id
        && Number(item.item_id) > 0
        && Number.isInteger(Number(item.item_id))
          ? Number(item.item_id)
          : null
      ),
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
    transport: cleanText(details.transport),
    ship_to: cleanText(details.ship_to),
    ship_to_address: cleanText(details.ship_to_address),
    state: details.ship_state || null,
    reference: cleanText(details.reference),
    remarks: cleanText(details.remarks),

    show_shipping_address_on_bill: Boolean(
      details.show_shipping_address_on_bill,
    ),

  };
}

export default function PurchaseEntry() {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const editId = searchParams.get('edit');
  const loadedEditId = useRef(null);

  const [itemRecords, setItemRecords] = useState([]);

  const [details, setDetails] = useState(emptyDetails);
  const [items, setItems] = useState([]);
  const [itemForm, setItemForm] = useState(emptyItem);

  const [detailErrors, setDetailErrors] = useState({});
  const [itemErrors, setItemErrors] = useState({});
  const [editingIndex, setEditingIndex] = useState(null);

  const [partyModalOpen, setPartyModalOpen] = useState(false);

  const [submittingParty, setSubmittingParty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingPurchase, setLoadingPurchase] = useState(false);

  const totals = useMemo(
    () => computeTotals(items),
    [items],
  );

  const liveAmount = useMemo(
    () => computeLineAmounts(itemForm).amount,
    [itemForm],
  );

  const itemOptions = useMemo(
    () => itemRecords.map((item) => ({
      value: item.id,
      label: item.name,
      meta: item.hsn_code
        ? `HSN ${item.hsn_code}`
        : 'HSN not set',
      record: item,
    })),
    [itemRecords],
  );


  useEffect(() => {
    async function loadReferenceData() {
      try {
        const itemData = await fetchItems({ search: '' });

        setItemRecords(
          itemData.filter(
            (item) => item.is_active !== false,
          ),
        );
      } catch (error) {
        toast.error(extractErrorMessage(error));
      }
    }

    loadReferenceData();
  }, [toast]);

  useEffect(() => {
    if (
      !editId
      || loadedEditId.current === editId
    ) {
      return;
    }

    async function loadPurchase() {
      setLoadingPurchase(true);

      try {
        const purchase = await fetchPurchaseById(editId);

        const selectedParty = await fetchAccountRecord('party', purchase.party_id, purchase);

        setDetails(
          mapPurchaseToDetails(
            purchase,
            selectedParty,
          ),
        );

        setItems(
          mapPurchaseItems(
            purchase.items,
          ),
        );

        loadedEditId.current = editId;
      } catch (error) {
        toast.error(extractErrorMessage(error));
        navigate('/purchase-history');
      } finally {
        setLoadingPurchase(false);
      }
    }

    loadPurchase();
  }, [editId, navigate, toast]);

  function clearItemForm() {
    setItemForm(emptyItem());
    setEditingIndex(null);
    setItemErrors({});
  }

  function clearAll() {
    setDetails(emptyDetails());
    setItems([]);
    clearItemForm();
    setDetailErrors({});
  }

  function changeDetail(field, value) {
    if (field === 'is_gst' && !value) {
      setItemForm((previous) => ({
        ...previous,
        sgst: 0,
        cgst: 0,
        igst: 0,
      }));

      setItems((previous) => (
        previous.map((item) => ({
          ...item,
          sgst: 0,
          cgst: 0,
          igst: 0,
        }))
      ));
    }

    setDetails((previous) => {
      const next = {
        ...previous,
        [field]: value,
      };

      if (
        field === 'bill_date'
        || field === 'due_term'
      ) {
        next.due_date = addDays(
          field === 'bill_date'
            ? value
            : previous.bill_date,

          field === 'due_term'
            ? value
            : previous.due_term,
        );
      }

      return next;
    });

    setDetailErrors((previous) => ({
      ...previous,
      [field]: '',
    }));
  }

  function applySelectedParty(party) {
    setDetails((previous) => ({
      ...previous,

      _account: party,
      party_id: party?.id || null,
      address: party?.address || '',
      city: party?.city || '',
      party_state: party?.state || '',

      contact_no: party
        ? `${party.country_code || ''} ${party.mobile || ''}`.trim()
        : '',

      email: party?.email || '',

      // Supplier-dependent values are reset.
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
    clearItemForm();

    setDetailErrors((previous) => ({
      ...previous,
      party_id: '',
      ship_to: '',
      ship_to_address: '',
      ship_state: '',
    }));
  }

  function selectParty(option) {
    const selectedParty = option?.record || null;
    const selectedPartyId = selectedParty?.id || null;

    if (selectedPartyId === details.party_id) {
      return;
    }

    applySelectedParty(selectedParty);

    if (selectedParty) {
      toast.success(
        'Supplier changed. Items and delivery details were cleared.',
      );
    }
  }

  async function saveParty(payload) {
    setSubmittingParty(true);

    try {
      const created = await createParty({
        ...payload,
        party_type: 'Supplier',
      });

      applySelectedParty(created);
      setPartyModalOpen(false);

      toast.success(
        'Supplier added and selected. Items and delivery details were cleared.',
      );
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setSubmittingParty(false);
    }
  }

  function selectItem(option) {
    if (!option) {
      setItemForm((previous) => ({
        ...previous,
        item_id: null,
        item_name: '',
      }));
      return;
    }

    if (option.isCustom) {
      setItemForm((previous) => ({
        ...previous,
        item_id: option.value,
        item_name: option.label,
        hsn_code: '',
        price: '',
        sgst: 0,
        cgst: 0,
        igst: 0,
      }));

      setItemErrors((previous) => ({
        ...previous,
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
      cgst: item.cgst ?? previous.cgst,
      sgst: item.sgst ?? previous.sgst,
      igst: 0,
    }));

    setItemErrors((previous) => ({
      ...previous,
      item_name: '',
      hsn_code: '',
    }));
  }

  function changeItem(field, value) {
    setItemForm((previous) => {
      const next = {
        ...previous,
        [field]: value,
      };

      if (
        (field === 'sgst' || field === 'cgst')
        && Number(value) > 0
      ) {
        next.igst = 0;
      }

      if (
        field === 'igst'
        && Number(value) > 0
      ) {
        next.sgst = 0;
        next.cgst = 0;
      }

      return next;
    });

    setItemErrors((previous) => ({
      ...previous,
      [field]: '',
    }));
  }

  function addItem() {
    const errors = validateItem(itemForm);
    setItemErrors(errors);

    if (Object.keys(errors).length) {
      return;
    }

    if (editingIndex === null) {
      setItems((previous) => [
        ...previous,
        {
          ...itemForm,
          _rowId: ++rowCounter,
        },
      ]);
    } else {
      setItems((previous) => (
        previous.map((row, index) => (
          index === editingIndex
            ? {
              ...itemForm,
              _rowId: row._rowId,
            }
            : row
        ))
      ));
    }

    clearItemForm();
  }

  function removeItem(indexToRemove) {
    setItems((previous) => (
      previous.filter(
        (_, index) => index !== indexToRemove,
      )
    ));

    if (editingIndex === indexToRemove) {
      clearItemForm();
    }
  }

  async function savePurchase() {
    const errors = validatePurchaseDetails(details);
    setDetailErrors(errors);

    if (Object.keys(errors).length) {
      toast.error(
        'Please complete the required purchase details.',
      );
      return;
    }

    if (!items.length) {
      toast.error(
        'Add at least one item before saving.',
      );
      return;
    }

    const payload = buildPurchasePayload(
      details,
      items,
    );

    setSaving(true);

    try {
      const savedPurchase = editId
        ? await updatePurchase(editId, payload)
        : await createPurchase(payload);

      toast.success(
        editId
          ? `Purchase updated successfully. Bill No. ${savedPurchase.bill_no}`
          : `Purchase saved successfully. Bill No. ${savedPurchase.bill_no}`,
      );

      if (editId) {
        navigate('/purchase-history');
      } else {
        clearAll();
      }
    } catch (error) {
      toast.error(
        extractErrorMessage(error),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page general-transaction purchase-entry-final" data-enter-navigation onKeyDown={handleEnterNavigation}>
      <header className="gt-page-header">
        <div>
          <h1>
            {editId
              ? 'Update Purchase'
              : 'Purchase Entry'}
          </h1>

          <p>
            {editId
              ? 'Update the selected purchase bill and its transaction items.'
              : 'Create and save a supplier purchase bill using the verified transaction layout.'}
          </p>
        </div>

        <span className="gt-status">
          {editId
            ? 'Edit Purchase'
            : 'Purchase'}
        </span>
      </header>

      {loadingPurchase && (
        <div className="gt-loading-note">
          Loading purchase details...
        </div>
      )}

      <Card
        title="Transaction Details"
        className="gt-card"
      >
        <div className="gt-details-grid">
          <div className="gt-with-action">
            <AccountSelector domain="party" record={details._account}
              name="party_id"
              value={details.party_id}
              onChange={selectParty}
              required
              error={detailErrors.party_id}
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
            label="Bill No."
            value={details.bill_no}
            onChange={(value) => changeDetail('bill_no', value)}
            placeholder="Enter supplier bill number"
            required
            error={detailErrors.bill_no}
          />

          <FormInput
            label="Order No."
            value={details.order_no}
            onChange={(value) => changeDetail('order_no', value)}
            placeholder="Enter order number"
          />

          <FormInput
            label="Bill Date"
            type="date"
            value={details.bill_date}
            onChange={(value) => changeDetail('bill_date', value)}
            required
            error={detailErrors.bill_date}
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
        subtitle="Search an existing item or add a new item without leaving this purchase."
        className="gt-card"
      >
        <div className="gt-item-top">
          <SearchableSelect
            label="Item Name"
            name="item_name"
            options={itemOptions}
            value={itemForm.item_id}
            onChange={selectItem}
            placeholder="Search or type a new item..."
            required
            error={itemErrors.item_name}
            allowCustom
            emptyMessage="No matching item found."
          />

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
            disabled={
              !details.is_gst
              || Number(itemForm.igst) > 0
            }
          />

          <FormInput
            label="CGST %"
            type="number"
            min="0"
            max="100"
            value={details.is_gst ? itemForm.cgst : 0}
            onChange={(value) => changeItem('cgst', value)}
            disabled={
              !details.is_gst
              || Number(itemForm.igst) > 0
            }
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
            <strong>
              {formatCurrency(liveAmount)}
            </strong>
          </div>
        </div>

        <div className="gt-item-actions">
          <Button
            variant="secondary"
            onClick={clearItemForm}
          >
            Clear
          </Button>

          <Button
            variant="primary"
            onClick={addItem}
          >
            {editingIndex === null
              ? 'Add Item'
              : 'Update Item'}
          </Button>
        </div>
      </Card>

      <Card
        title="Transaction Items"
        className="gt-card"
      >
        <div className="gt-table-wrap">
          <table className="gt-table">
            <thead>
              <tr>
                <th>Sr.</th>
                <th>Item</th>
                <th>HSN</th>
                <th>Qty</th>
                <th>Unit</th>
                <th>Price</th>
                <th>Disc.</th>
                <th>SGST</th>
                <th>CGST</th>
                <th>IGST</th>
                <th>Amount</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {!items.length ? (
                <tr>
                  <td
                    colSpan="12"
                    className="gt-empty"
                  >
                    No items added yet. Use the item form above.
                  </td>
                </tr>
              ) : (
                items.map((row, index) => (
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

                    <td>
                      {formatCurrency(
                        computeLineAmounts(row).amount,
                      )}
                    </td>

                    <td>
                      <button
                        type="button"
                        className="gt-link"
                        onClick={() => {
                          setItemForm(row);
                          setEditingIndex(index);
                        }}
                      >
                        Edit
                      </button>

                      <button
                        type="button"
                        className="gt-link gt-link--danger"
                        onClick={() => removeItem(index)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="gt-bottom-grid">
        <Card
          title="Extra Address & Delivery Details"
          className="gt-card"
        >
          <FormCheckbox
            label="Show this shipping address on bill"
            checked={details.show_shipping_address_on_bill}
            onChange={(value) => (
              changeDetail(
                'show_shipping_address_on_bill',
                value,
              )
            )}
          />

          <div className="gt-delivery-grid">
            <FormInput
              label="Delivery Date"
              type="date"
              value={details.delivery_date}
              onChange={(value) => (
                changeDetail(
                  'delivery_date',
                  value,
                )
              )}
            />

            <FormInput
              label="Ship To"
              value={details.ship_to}
              onChange={(value) => (
                changeDetail(
                  'ship_to',
                  value,
                )
              )}
              required={
                details.show_shipping_address_on_bill
              }
              error={detailErrors.ship_to}
            />

            <FormInput
              label="Transport"
              value={details.transport}
              onChange={(value) => (
                changeDetail(
                  'transport',
                  value,
                )
              )}
            />

            <div className="gt-span-2">
              <FormTextarea
                label="Ship To Address"
                value={details.ship_to_address}
                onChange={(value) => (
                  changeDetail(
                    'ship_to_address',
                    value,
                  )
                )}
                rows={3}
                required={
                  details.show_shipping_address_on_bill
                }
                error={
                  detailErrors.ship_to_address
                }
              />
            </div>

            <FormSelect
              label="State"
              value={details.ship_state}
              onChange={(value) => (
                changeDetail(
                  'ship_state',
                  value,
                )
              )}
              options={STATE_OPTIONS}
              required={
                details.show_shipping_address_on_bill
              }
              error={detailErrors.ship_state}
            />

            <FormInput
              label="Reference"
              value={details.reference}
              onChange={(value) => (
                changeDetail(
                  'reference',
                  value,
                )
              )}
            />

            <div className="gt-span-2">
              <FormTextarea
                label="Remarks"
                value={details.remarks}
                onChange={(value) => (
                  changeDetail(
                    'remarks',
                    value,
                  )
                )}
                rows={3}
              />
            </div>
          </div>
        </Card>

        <Card
          title="Total Summary"
          className="gt-card gt-summary"
        >
          <div>
            <span>Taxable Amount</span>
            <strong>
              {formatCurrency(
                totals.taxableAmount,
              )}
            </strong>
          </div>

          <div>
            <span>SGST Total</span>
            <strong>
              {formatCurrency(
                totals.sgstTotal,
              )}
            </strong>
          </div>

          <div>
            <span>CGST Total</span>
            <strong>
              {formatCurrency(
                totals.cgstTotal,
              )}
            </strong>
          </div>

          <div>
            <span>IGST Total</span>
            <strong>
              {formatCurrency(
                totals.igstTotal,
              )}
            </strong>
          </div>

          <div className="gt-grand">
            <span>Grand Total</span>
            <strong>
              {formatCurrency(
                totals.grandTotal,
              )}
            </strong>
          </div>
        </Card>
      </div>

      <div className="gt-footer-actions">
        <Button
          variant="secondary"
          onClick={clearAll}
          disabled={saving}
        >
          Clear
        </Button>

        <Button
          variant="primary"
          onClick={savePurchase}
          disabled={saving}
        >
          {saving
            ? (
              editId
                ? 'Updating Purchase...'
                : 'Saving Purchase...'
            )
            : (
              editId
                ? 'Update Purchase'
                : 'Save Purchase'
            )}
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
