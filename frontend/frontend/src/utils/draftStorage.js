// Temporary, per-tab create-and-return drafts. No backend or URL payloads.
export const MANAGED_ENTITIES = Object.freeze({
  account: { route: '/parties', label: 'Account' },
  item: { route: '/items', label: 'Item' },
  doneBy: { route: '/done-by', label: 'Done By' },
  bank: { route: '/banks', label: 'Cash/Bank' },
});
const ORIGINS = new Set(['/purchase-entry', '/purchase-return-entry', '/sales-entry', '/sales-return-entry', '/quotation-entry', '/rojmel']);
const PREFIX = 'billing:draft:';

export function safeOrigin(path) {
  if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return false;
  const url = new URL(path, 'https://billing.invalid');
  return url.origin === 'https://billing.invalid' && ORIGINS.has(url.pathname);
}

function serialize(data) {
  return JSON.stringify(data, (key, value) => {
    if (/^(password|token|access_token|refresh_token|authorization|headers|credentials|secret)$/i.test(key)) throw new Error('Secrets cannot be stored in a transaction draft.');
    if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Finish invalid numeric fields before adding a record.');
    if (value && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) !== Object.prototype) throw new Error('This draft contains an unsupported file or value.');
    if (['function', 'symbol', 'bigint'].includes(typeof value)) throw new Error('This draft cannot be safely stored.');
    return value;
  });
}

export function saveDraft(origin, entity, data, context = {}) {
  if (!safeOrigin(origin) || !MANAGED_ENTITIES[entity]) throw new Error('Invalid create-and-return destination.');
  const key = PREFIX + crypto.randomUUID();
  sessionStorage.setItem(key, serialize({ origin, entity, data, context }));
  return key;
}

export function loadDraft(key, origin) {
  if (typeof key !== 'string' || !key.startsWith(PREFIX)) return null;
  try {
    const draft = JSON.parse(sessionStorage.getItem(key));
    return draft && safeOrigin(draft.origin) && MANAGED_ENTITIES[draft.entity]
      && (!origin || draft.origin === origin) ? draft : null;
  } catch { return null; }
}

export function clearDraft(key) { sessionStorage.removeItem(key); }

export function completeDraft(key, entity, record) {
  const draft = loadDraft(key);
  if (!draft || draft.entity !== entity) throw new Error('The originating draft is unavailable.');
  if (record) {
    // Keep only fields used by existing selection/autofill paths, never the transport response.
    const fields = entity === 'account'
      ? ['id', 'source', 'accountType', 'party_type', 'name', 'customer_name', 'address', 'city', 'state', 'mobile', 'email']
      : entity === 'item'
        ? ['id', 'name', 'hsn_code', 'unit', 'purchase_price', 'sale_price', 'current_stock', 'cgst', 'sgst', 'igst', 'is_active']
        : ['id', 'name', 'is_active'];
    draft.created = Object.fromEntries(fields.filter((field) => record[field] !== undefined).map((field) => [field, record[field]]));
  }
  sessionStorage.setItem(key, serialize(draft));
  return draft.origin;
}

export function createContext(location) {
  const key = location.state?.managedCreate;
  const draft = loadDraft(key);
  return draft && MANAGED_ENTITIES[draft.entity].route === location.pathname ? { key, ...draft } : null;
}
