import api from './api';

const SALES_RETURN_ENDPOINT = '/sales-returns/';

export async function fetchSalesReturns({ page, pageSize = 20, search = '' } = {}) {
  const { data } = await api.get(
    SALES_RETURN_ENDPOINT,
    {
      params: {
        page,
        page_size: page === undefined ? undefined : pageSize,
        search: search.trim() || undefined,
        limit: page === undefined ? 500 : undefined,
      },
    },
  );

  return data;
}

export async function fetchNextSalesReturnNumbers() {
  const { data } = await api.get(
    `${SALES_RETURN_ENDPOINT}next-numbers`,
  );

  return data;
}

export async function fetchSalesReturnById(id) {
  const { data } = await api.get(
    `${SALES_RETURN_ENDPOINT}${id}`,
  );

  return data;
}

export async function createSalesReturn(payload) {
  const { data } = await api.post(
    SALES_RETURN_ENDPOINT,
    payload,
  );

  return data;
}

export async function updateSalesReturn(id, payload) {
  const { data } = await api.put(
    `${SALES_RETURN_ENDPOINT}${id}`,
    payload,
  );

  return data;
}

export async function deleteSalesReturn(id) {
  const { data } = await api.delete(
    `${SALES_RETURN_ENDPOINT}${id}`,
  );

  return data;
}
