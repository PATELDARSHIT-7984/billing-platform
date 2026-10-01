import api from './api';

const PURCHASES_ENDPOINT = '/purchases';

const purchaseUrl = (id = '') => (
  id ? `${PURCHASES_ENDPOINT}/${id}` : `${PURCHASES_ENDPOINT}/`
);

/**
 * GET /purchases/
 * Returns a legacy list, or history metadata when page is supplied.
 */
export async function fetchPurchases({ page, pageSize = 20, search = '', limit = 500 } = {}) {
  const { data } = await api.get(purchaseUrl(), {
    params: {
      page,
      page_size: page === undefined ? undefined : pageSize,
      search: search.trim() || undefined,
      limit: page === undefined ? limit : undefined,
    },
  });

  return data;
}

/**
 * GET /purchases/{id}
 * Returns full PurchaseResponse including items.
 */
export async function fetchPurchaseById(id) {
  const { data } = await api.get(purchaseUrl(id));

  return data;
}

/**
 * POST /purchases/
 * Creates a new Purchase.
 */
export async function createPurchase(payload) {
  const { data } = await api.post(
    purchaseUrl(),
    payload,
  );

  return data;
}

/**
 * PUT /purchases/{id}
 * Updates an existing Purchase.
 */
export async function updatePurchase(id, payload) {
  const { data } = await api.put(
    purchaseUrl(id),
    payload,
  );

  return data;
}
