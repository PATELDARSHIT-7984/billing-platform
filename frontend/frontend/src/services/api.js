import axios from 'axios';
import { API_BASE_URL } from '../config/config';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});
export function extractErrorMessage(error) {
  const data = error?.response?.data;
  const detail = data?.detail;

  if (!detail) {
    // The global error envelope (api/utils/response.py) uses `message`
    // instead of FastAPI's default `detail` key -- check that too.
    if (data?.message) return data.message;
    if (error?.message === 'Network Error') {
      return 'Cannot reach the server. Please check your connection or try again.';
    }
    return error?.message || 'Something went wrong. Please try again.';
  }

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'string' ? d : d.msg))
      .filter(Boolean)
      .join(', ');
  }

  return 'Something went wrong. Please try again.';
}

export default api;
