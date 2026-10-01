import api from './api';

const QUOTATION_ENDPOINT = '/quotations/';

export function fetchQuotations({ page, pageSize = 20, search = '' } = {}) {
  return api.get(QUOTATION_ENDPOINT, {
    params: {
      page,
      page_size: page === undefined ? undefined : pageSize,
      search: search || undefined,
      limit: page === undefined ? 500 : undefined,
    },
  }).then((res) => res.data);
}

export function fetchQuotationById(id) {
  return api.get(`${QUOTATION_ENDPOINT}${id}`).then((res) => res.data);
}

export function createQuotation(payload) {
  return api.post(QUOTATION_ENDPOINT, payload).then((res) => res.data);
}

export function updateQuotation(id, payload) {
  return api.put(`${QUOTATION_ENDPOINT}${id}`, payload).then((res) => res.data);
}

export function deleteQuotation(id) {
  return api.delete(`${QUOTATION_ENDPOINT}${id}`).then((res) => res.data);
}
