// Vite embeds this public configuration at build time. There is no local fallback.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '');

if (!API_BASE_URL) {
  throw new Error('VITE_API_BASE_URL is required. Set it before starting or building the frontend.');
}

const backendUrl = new URL(API_BASE_URL);
if (!['http:', 'https:'].includes(backendUrl.protocol)
    || backendUrl.username || backendUrl.password || backendUrl.search || backendUrl.hash) {
  throw new Error('VITE_API_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment.');
}
