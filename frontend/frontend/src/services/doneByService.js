import api from './api';

// Matches the FastAPI /done-by router. Used as a dropdown source for Rojmel (Done By field).

// Fetches every active person.
export function fetchDoneByList() {
  return api.get('/done-by/').then((res) => res.data);
}

// Fetches a single person by id.
export function fetchDoneById(id) {
  return api.get(`/done-by/${id}`).then((res) => res.data);
}

// Creates a new person.
export function createDoneBy(payload) {
  return api.post('/done-by/', payload).then((res) => res.data);
}

// Partially updates a person (PATCH -- backend does exclude_unset partial update).
export function updateDoneBy(id, payload) {
  return api.patch(`/done-by/${id}`, payload).then((res) => res.data);
}

// Deactivates a person (soft delete).
export function deleteDoneBy(id) {
  return api.delete(`/done-by/${id}`).then((res) => res.data);
}
