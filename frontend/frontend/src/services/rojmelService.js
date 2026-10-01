import api from './api';

// Unlike the other services, /rojmel responses are wrapped in the global
// { success, status_code, message, data } envelope (see api/utils/response.py),
// so every call here unwraps res.data.data instead of res.data.
const ROJMEL_ENDPOINT = '/rojmel/';

// Fetches one page of the ledger. Returns { items, total, page, page_size, total_pages }.
export function fetchRojmels({ search = '', startDate = '', endDate = '', partyId = '', page = 1, pageSize = 20 } = {}) {
  return api
    .get(ROJMEL_ENDPOINT, {
      params: {
        search: search || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        party_id: partyId || undefined,
        page,
        page_size: pageSize,
      },
    })
    .then((res) => res.data.data);
}

// Fetches a single receipt by id.
export function fetchRojmelById(id) {
  return api.get(`${ROJMEL_ENDPOINT}${id}`).then((res) => res.data.data);
}

// Creates a new receipt.
export function createRojmel(payload) {
  return api.post(ROJMEL_ENDPOINT, payload).then((res) => res.data.data);
}

// Partially updates a receipt (PATCH -- only changed fields need to be sent).
export function updateRojmel(id, payload) {
  return api.patch(`${ROJMEL_ENDPOINT}${id}`, payload).then((res) => res.data.data);
}

// Permanently deletes a receipt. There is no undo -- the backend performs a hard delete.
export function deleteRojmel(id) {
  return api.delete(`${ROJMEL_ENDPOINT}${id}`).then((res) => res.data.data);
}

// Fetches total received / paid / net earning across every receipt
// matching the given filters (not just the current page).
export function fetchRojmelSummary({ search = '', startDate = '', endDate = '', partyId = '' } = {}) {
  return api
    .get(`${ROJMEL_ENDPOINT}summary`, {
      params: {
        search: search || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        party_id: partyId || undefined,
      },
    })
    .then((res) => res.data.data);
}
