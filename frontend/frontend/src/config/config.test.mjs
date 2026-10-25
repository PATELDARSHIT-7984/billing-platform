import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import axios from 'axios';

const source = await readFile(new URL('./config.js', import.meta.url), 'utf8');
// Supply the build-time env object when exercising this Vite module in Node.
const loadConfig = (env) => import(`data:text/javascript,${encodeURIComponent(
  source.replaceAll('import.meta.env', JSON.stringify(env)),
)}`);

test('configured cloud URL preserves prefix and Axios endpoint joining', async () => {
  const { API_BASE_URL } = await loadConfig({ VITE_API_BASE_URL: ' https://api.example.com/api/// ' });
  const api = axios.create({ baseURL: API_BASE_URL });
  assert.equal(api.getUri({ url: '/bills/' }), 'https://api.example.com/api/bills/');
  assert.equal(api.getUri({ url: '/company-profile/' }), 'https://api.example.com/api/company-profile/');
});

test('local configuration retains the existing backend port and endpoints', async () => {
  const { API_BASE_URL } = await loadConfig({ VITE_API_BASE_URL: 'http://127.0.0.1:8000' });
  assert.equal(axios.create({ baseURL: API_BASE_URL }).getUri({ url: '/done-by/' }),
    'http://127.0.0.1:8000/done-by/');
});

test('missing or invalid configuration cannot silently use a local fallback', async () => {
  for (const value of ['', '   ', 'ftp://api.example.com', 'https://user:password@api.example.com', 'https://api.example.com?x=1']) {
    await assert.rejects(loadConfig({ VITE_API_BASE_URL: value }));
  }
  await assert.rejects(loadConfig({}), /VITE_API_BASE_URL is required/);
});
