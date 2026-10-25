import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { validateCustomer } from './customerValidation.js';
import { historyPosition } from './pagination.js';

// Exercise the real service chain with a transport double, without Vite/browser globals.
const calls = [];
let response;
globalThis.accountTestApi = Object.fromEntries(['get', 'post', 'put', 'delete'].map((method) => [method,
  async (...args) => { calls.push({ method, args }); if (response instanceof Error) throw response; return { data: response }; }]));
const url = (source) => `data:text/javascript,${encodeURIComponent(source)}`;
const transport = url('export default globalThis.accountTestApi;');
let source = await readFile(new URL('../services/accountService.js', import.meta.url), 'utf8');
for (const name of ['customerService', 'partyService']) {
  const service = await readFile(new URL(`../services/${name}.js`, import.meta.url), 'utf8');
  source = source.replace(`'./${name}'`, JSON.stringify(url(service.replace("'./api'", JSON.stringify(transport)))));
}
const accounts = await import(url(source));
const form = { name: ' Buyer ', mobile: '9876543210', address: 'Road', city: 'Surat', state: 'Gujarat',
  gstin: '', pan_card: '', country_code: '+91', opening_balance: '123.45', balance_type: 'Debit', opening_remark: 'Note' };

test('one canonical account option list', () => {
  assert.deepEqual(accounts.ACCOUNT_TYPES.map(({ label }) => label), ['Customer', 'Supplier', 'Purchase']);
});

for (const type of accounts.ACCOUNT_TYPES) {
  test(`${type.label}: one filtered page request, normalized explicit source`, async () => {
    calls.length = 0;
    response = { items: [{ id: 1, customer_name: 'Buyer', name: 'Vendor', opening_balance: '123.45' }], total: 21, total_pages: 2 };
    const page = await accounts.fetchAccounts({ accountType: type.value, search: ' Tile ', page: 2, pageSize: 20 });
    assert.equal(calls.length, 1);
    assert.equal(calls[0].args[0], type.source === 'customer' ? '/customers/' : '/parties/');
    const params = calls[0].args[1].params;
    assert.equal(params.search, 'Tile');
    assert.equal(params.page, 2);
    assert.equal(params.page_size, 20);
    assert.equal(params.limit, undefined);
    assert.equal(params.party_type, type.party_type);
    assert.equal(page.items[0].source, type.source);
    assert.equal(page.items[0].accountType, type.value);
    assert.equal(page.total, 21);
  });

  test(`${type.label}: create/edit/delete routing and managed-balance protection`, async () => {
    calls.length = 0;
    response = { id: 1, name: 'Vendor', customer_name: 'Buyer' };
    const values = { ...form, accountType: type.value, current_balance: '99999', current_balance_type: 'Credit' };
    const saved = await accounts.saveAccount(values);
    const payload = calls[0].args[1];
    assert.equal(payload.opening_balance, '123.45');
    assert.equal(payload.balance_type, 'Debit');
    assert.equal(payload.gstin, null);
    assert.equal(payload.party_type, type.party_type);
    assert.equal('current_balance' in payload, false);
    assert.equal('current_balance_type' in payload, false);
    if (type.source === 'customer') {
      assert.equal(payload.customer_name, 'Buyer');
      assert.equal('name' in payload, false);
      assert.equal('country_code' in payload, false);
    }
    // Even a changed form type cannot migrate an existing record to another table.
    await accounts.saveAccount({ ...values, accountType: 'CUSTOMER' }, saved);
    await accounts.deleteAccount(saved);
    const endpoint = type.source === 'customer' ? '/customers/' : '/parties/';
    assert.deepEqual(calls.map((call) => [call.method, call.args[0]]),
      [['post', endpoint], ['put', `${endpoint}1`], ['delete', `${endpoint}1`]]);
  });
}

test('Customer full edit preserves fields outside the existing Party modal', async () => {
  response = { id: 1, customer_name: 'Buyer', email: 'buyer@example.com', pincode: '395001', state_code: '24', remarks: 'Saved note' };
  const full = await accounts.fetchAccountForEdit({ id: 1, source: 'customer', accountType: 'CUSTOMER' });
  assert.equal(full.opening_remark, 'Saved note');
  const payload = accounts.buildAccountPayload('CUSTOMER', form, full);
  assert.equal(payload.email, response.email);
  assert.equal(payload.pincode, response.pincode);
  assert.equal(payload.state_code, response.state_code);
  assert.equal(payload.remarks, 'Note');
});

test('Customer validation retains mobile/address/GSTIN rules', () => {
  assert.deepEqual(validateCustomer({ ...form, customer_name: form.name }), {});
  const errors = validateCustomer({ ...form, customer_name: 'X', mobile: '123', address: '', gstin: 'bad' });
  for (const field of ['customer_name', 'mobile', 'address', 'gstin']) assert.ok(errors[field]);
});

test('account filters reset pagination through the existing reducer', () => {
  const next = historyPosition({ filterKey: 'SUPPLIER', page: 5, pageSize: 20 }, { type: 'filters', value: 'CUSTOMER' });
  assert.equal(next.page, 1);
  assert.equal(next.pageSize, 20);
});

test('transaction restrictions derive from registry source, without local type arrays', () => {
  assert.deepEqual(accounts.accountTypesForSource('customer').map((type) => type.value), ['CUSTOMER']);
  assert.deepEqual(accounts.accountTypesForSource('party').map((type) => type.value), ['SUPPLIER', 'PURCHASE_VENDOR']);
  assert.deepEqual(accounts.accountTypesForSource(), accounts.ACCOUNT_TYPES);
});

for (const type of accounts.ACCOUNT_TYPES) {
  test(`${type.label}: saved account resolves its real type through the correct detail endpoint`, async () => {
    calls.length = 0;
    response = { id: 999, name: 'Vendor', customer_name: 'Buyer', party_type: type.party_type };
    const saved = await accounts.fetchAccountRecord(type.source, 999);
    assert.equal(saved.accountType, type.value);
    assert.equal(saved.source, type.source);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].args[0], type.source === 'customer' ? '/customers/999' : '/parties/999');
  });
}

test('same numeric IDs remain distinct sources and clearing removes both Rojmel links', () => {
  assert.deepEqual(accounts.accountSelectionFields({ source: 'customer', value: 7 }), { customer_id: 7, party_id: null });
  assert.deepEqual(accounts.accountSelectionFields({ source: 'party', value: 7 }), { customer_id: null, party_id: 7 });
  assert.deepEqual(accounts.accountSelectionFields(null), { customer_id: null, party_id: null });
});

test('legacy Party Customer is never inferred to be a Customer-table record', () => {
  const saved = accounts.normalizeAccountRecord('party', { id: 7, name: 'Legacy', party_type: 'Customer' });
  assert.equal(saved.source, 'party');
  assert.equal(saved.accountType, null);
});

test('unavailable historical account keeps its source and ID without guessing Party type', async () => {
  response = Object.assign(new Error('Not found'), { response: { status: 404 } });
  const saved = await accounts.fetchAccountRecord('party', 77, { party_name: 'Former vendor' });
  assert.equal(saved.id, 77); assert.equal(saved.source, 'party');
  assert.equal(saved.accountType, null); assert.equal(saved.name, 'Former vendor');
  await assert.rejects(accounts.fetchAccountRecord('party', 77));
  response = new Error('Network unavailable');
  await assert.rejects(accounts.fetchAccountRecord('party', 77, {}));
});
