import { fetchCustomers, fetchCustomerById, createCustomer, updateCustomer, deleteCustomer } from './customerService';
import { fetchParties, fetchPartyById, createParty, updateParty, deleteParty } from './partyService';

export const ACCOUNT_TYPES = [
  { value: 'CUSTOMER', label: 'Customer', source: 'customer' },
  { value: 'SUPPLIER', label: 'Supplier', source: 'party', party_type: 'Supplier' },
  { value: 'PURCHASE_VENDOR', label: 'Purchase', source: 'party', party_type: 'PURCHASE_VENDOR' },
];

export const accountType = (value) => ACCOUNT_TYPES.find((type) => type.value === value) || ACCOUNT_TYPES[1];

const services = {
  customer: { get: fetchCustomerById, list: fetchCustomers, create: createCustomer, update: updateCustomer, delete: deleteCustomer },
  party: { get: fetchPartyById, list: fetchParties, create: createParty, update: updateParty, delete: deleteParty },
};

function accountRow(row, type) {
  return { ...row, source: type.source, accountType: type.value,
    name: type.source === 'customer' ? row.customer_name : row.name,
    opening_remark: type.source === 'customer' ? row.remarks : row.opening_remark };
}

export async function fetchAccounts({ accountType: value, ...params }) {
  const type = accountType(value);
  const page = await services[type.source].list({ ...params, party_type: type.party_type });
  return { ...page, items: page.items.map((row) => accountRow(row, type)) };
}

export async function fetchAccountForEdit(row) {
  return row.source === 'customer'
    ? accountRow(await fetchCustomerById(row.id), accountType(row.accountType)) : row;
}

export function buildAccountPayload(value, form, existing = null) {
  const type = accountType(value);
  const common = {
    mobile: form.mobile.trim() || null, address: form.address.trim() || null,
    city: form.city.trim() || null, state: form.state || null,
    gstin: form.gstin.trim().toUpperCase() || null, pan_card: form.pan_card.trim().toUpperCase() || null,
    opening_balance: form.opening_balance === '' ? '0.00' : String(form.opening_balance),
    balance_type: form.balance_type,
  };
  if (type.source === 'customer') {
    // Customer PUT replaces these fields even though this modal doesn't expose them.
    return { ...common, customer_name: form.name.trim(), remarks: form.opening_remark.trim() || null,
      email: existing?.email ?? null, pincode: existing?.pincode ?? null, state_code: existing?.state_code ?? null };
  }
  return { ...common, name: form.name.trim(), party_type: type.party_type,
    country_code: form.country_code || '+91', opening_remark: form.opening_remark.trim() || null };
}

export async function saveAccount(form, existing = null) {
  const type = accountType(existing?.accountType || form.accountType);
  if (existing && existing.source !== type.source) throw new Error('Account source cannot be changed.');
  const payload = buildAccountPayload(type.value, form, existing);
  const api = services[existing?.source || type.source];
  const saved = existing ? await api.update(existing.id, payload) : await api.create(payload);
  return accountRow(saved, type);
}

export function deleteAccount(row) {
  return services[row.source].delete(row.id);
}

// Source restrictions reflect transaction FKs, not separate per-page type lists.
export const accountTypesForSource = (source) => ACCOUNT_TYPES.filter((type) => !source || type.source === source);

export function accountTypeForRecord(source, record) {
  return ACCOUNT_TYPES.find((type) => type.source === source
    && (source === 'customer' || type.party_type === record?.party_type));
}

export async function fetchAccountRecord(source, id, snapshot = null) {
  try {
    return normalizeAccountRecord(source, await services[source].get(id));
  } catch (error) {
    // Active-only detail APIs must not prevent opening an existing transaction.
    if (!snapshot || error.response?.status !== 404) throw error;
    const name = snapshot.customer_name || snapshot.party_name || `Saved account #${id}`;
    return normalizeAccountRecord(source, { id, name, customer_name: name, unavailable: true });
  }
}

export function normalizeAccountRecord(source, row) {
  const type = accountTypeForRecord(source, row);
  // Legacy Party Customer records retain their identity without becoming Customers.
  return type ? accountRow(row, type) : { ...row, source, accountType: null };
}

export function accountSelectionFields(selection) {
  // Rojmel PATCH needs explicit null to clear the previous source on a switch.
  return { customer_id: selection?.source === 'customer' ? Number(selection.value) : null,
    party_id: selection?.source === 'party' ? Number(selection.value) : null };
}
