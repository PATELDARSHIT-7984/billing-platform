import api from './api';

// Matches your FastAPI /parties router exactly.
// Every function returns response.data directly so pages don't deal with axios internals.

export function fetchParties({ search = '', page, pageSize = 20, party_type } = {}) {
  return api
    .get('/parties/', { params: { search: search.trim() || undefined, page, page_size: page === undefined ? undefined : pageSize, limit: page === undefined ? 500 : undefined, party_type } })
    .then((res) => res.data);
}

export function createParty(payload) {
  return api.post('/parties/', payload).then((res) => res.data);
}

export function fetchPartyById(id) {
  return api.get(`/parties/${id}`).then((res) => res.data);
}

export function updateParty(id, payload) {
  return api.put(`/parties/${id}`, payload).then((res) => res.data);
}

export function deleteParty(id) {
  return api.delete(`/parties/${id}`).then((res) => res.data);
}
