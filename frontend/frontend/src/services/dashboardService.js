import api from './api';

export function fetchDashboard(section, params, signal) {
  return api.get(`/dashboard/${section}`, { params, signal }).then((response) => response.data);
}
