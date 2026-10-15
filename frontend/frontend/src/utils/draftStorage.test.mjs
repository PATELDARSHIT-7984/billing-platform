import assert from 'node:assert/strict';
import test, { beforeEach } from 'node:test';
import { MANAGED_ENTITIES, safeOrigin, saveDraft, loadDraft, clearDraft, completeDraft, createContext } from './draftStorage.js';

const memory = () => { const values = new Map(); return {
  getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key),
}; };
beforeEach(() => { globalThis.sessionStorage = memory(); });
const form = { details: { party_id: 7, bill_date: '2026-10-10', remarks: 'Unfinished', brokerage: '2.50', is_gst: false },
  items: [{ item_id: 4, quantity: '2.5', price: '37.45', discount: '4' }], itemForm: { quantity: '3' }, editingIndex: 0 };

test('managed entities reuse existing routes', () => {
  assert.deepEqual(Object.values(MANAGED_ENTITIES).map((entry) => entry.route), ['/parties', '/items', '/done-by', '/banks']);
});
test('draft is saved synchronously in session storage, with exact form data', () => {
  const key = saveDraft('/purchase-entry?edit=42', 'item', form);
  assert.deepEqual(loadDraft(key).data, form);
  assert.equal(loadDraft(key).origin, '/purchase-entry?edit=42');
});
test('keys are namespaced, unique across repeated forms and routes', () => {
  const keys = [saveDraft('/purchase-entry', 'item', form), saveDraft('/purchase-entry', 'item', form), saveDraft('/sales-entry', 'item', form)];
  assert.equal(new Set(keys).size, 3); assert.ok(keys.every((key) => key.startsWith('billing:draft:')));
});
test('draft content is not encoded in routing metadata', () => {
  const key = saveDraft('/purchase-entry', 'item', form);
  assert.ok(!key.includes('Unfinished')); assert.equal(loadDraft(key).origin, '/purchase-entry');
});
test('external, protocol-relative and unrelated origins are rejected', () => {
  for (const path of ['https://evil.test', '//evil.test', 'javascript:alert(1)', '/\\evil.test', '/items', '/unknown', null]) {
    assert.equal(safeOrigin(path), false); assert.throws(() => saveDraft(path, 'item', form));
  }
});
test('account type and source restriction survive the detour', () => {
  const key = saveDraft('/purchase-entry', 'account', form, { accountType: 'PURCHASE_VENDOR', source: 'party' });
  assert.deepEqual(createContext({ pathname: '/parties', state: { managedCreate: key } }).context, { accountType: 'PURCHASE_VENDOR', source: 'party' });
});
test('successful creation retains original draft and minimum option data', () => {
  const key = saveDraft('/sales-entry', 'item', form);
  assert.equal(completeDraft(key, 'item', { id: 99, name: 'New', unit: 'Box', sale_price: 10, authorization: 'not copied' }), '/sales-entry');
  assert.deepEqual(loadDraft(key).data, form);
  assert.deepEqual(loadDraft(key).created, { id: 99, name: 'New', unit: 'Box', sale_price: 10 });
});
test('cancel returns safely without deleting the draft', () => {
  const key = saveDraft('/quotation-entry', 'item', form);
  assert.equal(completeDraft(key, 'item', null), '/quotation-entry'); assert.deepEqual(loadDraft(key).data, form);
});
test('wrong form and wrong entity cannot consume a draft', () => {
  const key = saveDraft('/purchase-entry?edit=42', 'item', form);
  assert.equal(loadDraft(key, '/purchase-entry'), null);
  assert.equal(createContext({ pathname: '/parties', state: { managedCreate: key } }), null);
  assert.throws(() => completeDraft(key, 'account', { id: 1 }));
});
test('storage failure throws before a caller can navigate', () => {
  sessionStorage.setItem = () => { throw new Error('Quota exceeded'); };
  let navigated = false;
  assert.throws(() => { saveDraft('/purchase-entry', 'item', form); navigated = true; });
  assert.equal(navigated, false);
});
test('nonserializable values, files, cycles and nonfinite numbers fail safely', () => {
  const cycle = {}; cycle.self = cycle;
  for (const data of [cycle, { file: new Blob(['data']) }, { fn: () => {} }, { quantity: Infinity }, { value: 1n }]) {
    assert.throws(() => saveDraft('/purchase-entry', 'item', data));
  }
});
test('authentication and secret fields are rejected, not persisted', () => {
  for (const key of ['password', 'access_token', 'authorization', 'headers', 'credentials', 'secret']) {
    assert.throws(() => saveDraft('/sales-entry', 'account', { nested: { [key]: 'private' } }));
  }
});
test('session storage isolates tabs', () => {
  const key = saveDraft('/purchase-entry', 'item', form);
  globalThis.sessionStorage = memory(); assert.equal(loadDraft(key), null);
});
test('consumed or corrupted drafts are not restored', () => {
  const key = saveDraft('/purchase-entry', 'item', form); clearDraft(key); assert.equal(loadDraft(key), null);
  sessionStorage.setItem(key, 'broken json'); assert.equal(loadDraft(key), null);
});
