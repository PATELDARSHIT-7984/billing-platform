import api from './api';

const BILL_ENDPOINT = '/bills/';

export async function fetchBills({ page, pageSize = 20, search = '' } = {}) {
  const { data } = await api.get(BILL_ENDPOINT, {
    params: {
      page,
      page_size: page === undefined ? undefined : pageSize,
      search: search.trim() || undefined,
      limit: page === undefined ? 500 : undefined,
    },
  });

  return data;
}

export async function fetchBillById(id) {
  const { data } = await api.get(
    `${BILL_ENDPOINT}${id}`,
  );

  return data;
}

export async function createBill(payload) {
  const { data } = await api.post(
    BILL_ENDPOINT,
    payload,
  );

  return data;
}

export async function updateBill(id, payload) {
  const { data } = await api.put(
    `${BILL_ENDPOINT}${id}`,
    payload,
  );

  return data;
}

export async function deleteBill(id) {
  const { data } = await api.delete(
    `${BILL_ENDPOINT}${id}`,
  );

  return data;
}