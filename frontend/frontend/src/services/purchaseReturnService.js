import api from './api';

const ENDPOINT = '/purchase-returns/';

export async function fetchPurchaseReturns({ page, pageSize = 20, search = '' } = {}) {
  const { data } = await api.get(ENDPOINT, {
    params: {
      page,
      page_size: page === undefined ? undefined : pageSize,
      search: search.trim() || undefined,
      limit: page === undefined ? 500 : undefined,
    },
  });

  return data;
}

export async function fetchNextPurchaseReturnNumbers() {
  const { data } = await api.get(
    `${ENDPOINT}next-numbers`,
  );

  return data;
}

export async function fetchPurchaseReturnById(id) {
  const { data } = await api.get(
    `${ENDPOINT}${id}`,
  );

  return data;
}

export async function createPurchaseReturn(payload) {
  const { data } = await api.post(
    ENDPOINT,
    payload,
  );

  return data;
}

export async function updatePurchaseReturn(id, payload) {
  const { data } = await api.put(
    `${ENDPOINT}${id}`,
    payload,
  );

  return data;
}

export async function deletePurchaseReturn(id) {
  const { data } = await api.delete(
    `${ENDPOINT}${id}`,
  );

  return data;
}