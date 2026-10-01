import api from './api';

// Matches the FastAPI /banks router. Used as a dropdown source for Rojmel (Cash/Bank field).

// Fetches every bank.
export function fetchBanks() {
  return api.get('/banks/').then((res) => res.data);
}

// Fetches a single bank by id.
export function fetchBankById(id) {
  return api.get(`/banks/${id}`).then((res) => res.data);
}

// Creates a new bank.
export function createBank(payload) {
  return api.post('/banks/', payload).then((res) => res.data);
}

// Partially updates a bank (PATCH -- backend does exclude_unset partial update).
export function updateBank(id, payload) {
  return api.patch(`/banks/${id}`, payload).then((res) => res.data);
}

// Deactivates a bank (soft delete).
export function deleteBank(id) {
  return api.delete(`/banks/${id}`).then((res) => res.data);
}
