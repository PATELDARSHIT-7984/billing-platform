import api from './api';

// ===================== Customers API (/customers) =====================
const CUSTOMERS_ENDPOINT = '/customers/';

// List is lean (no address/email/pincode/pan_card) -- Sales Entry's
// auto-fill and the Edit modal both call fetchCustomerById() for the rest.
export function fetchCustomers({ search = '', page, pageSize = 20 } = {}) {
  return api
    .get(CUSTOMERS_ENDPOINT, { params: { search: search.trim() || undefined, page, page_size: page === undefined ? undefined : pageSize, limit: page === undefined ? 500 : undefined } })
    .then((res) => res.data);
}

export function fetchCustomerById(id) {
  return api.get(`${CUSTOMERS_ENDPOINT}${id}`).then((res) => res.data);
}

export function createCustomer(payload) {
  return api.post(CUSTOMERS_ENDPOINT, payload).then((res) => res.data);
}

// update_customer() overwrites every field -- always submit the full object.
export function updateCustomer(id, payload) {
  return api.put(`${CUSTOMERS_ENDPOINT}${id}`, payload).then((res) => res.data);
}

export function deleteCustomer(id) {
  return api.delete(`${CUSTOMERS_ENDPOINT}${id}`).then((res) => res.data);
}
