// Run against Vite and headless Edge/Chrome with --remote-debugging-port=9225.
// All XHR is intercepted: this test never writes to a real backend.
import assert from 'node:assert/strict';
import { writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const origin = process.env.ACCOUNT_TEST_ORIGIN || 'http://127.0.0.1:5175';
const pages = await (await fetch('http://127.0.0.1:9225/json')).json();
const ws = new WebSocket(pages[0].webSocketDebuggerUrl);
await new Promise((resolve) => { ws.onopen = resolve; });
let sequence = 0;
const pending = new Map();
const requests = [];
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++sequence;
  pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});
const pause = (ms = 650) => new Promise((resolve) => setTimeout(resolve, ms));
ws.onmessage = async ({ data }) => {
  const message = JSON.parse(data);
  if (message.id) {
    const handler = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) handler.reject(new Error(message.error.message));
    else handler.resolve(message.result);
  }
  if (message.method === 'Fetch.requestPaused') {
    const { requestId, request } = message.params;
    if (message.params.resourceType !== 'XHR' && request.method !== 'OPTIONS') {
      await send('Fetch.continueRequest', { requestId });
      return;
    }
    const url = new URL(request.url);
    const customer = url.pathname.includes('/customers');
    const account = customer || url.pathname.includes('/parties');
    const row = { id: 7, name: 'Vendor', customer_name: 'Buyer', mobile: '9876543210',
      address: 'Road', city: 'Surat', state: 'Gujarat', gstin: null, pan_card: null,
      party_type: url.searchParams.get('party_type') || 'Supplier', opening_balance: '100', balance_type: 'Debit',
      current_balance: '500', current_balance_type: 'Debit', remarks: 'Saved note',
      email: 'buyer@example.com', pincode: '395001', state_code: '24' };
    if (account && request.method !== 'OPTIONS') requests.push({ ...request, url });
    const body = !account ? (url.pathname.includes('company') ? {} : []) : request.method === 'GET' && url.pathname.endsWith('/')
      ? (url.searchParams.has('page') ? { items: [row], page: Number(url.searchParams.get('page')), total: 40, total_pages: 2, page_size: 20 } : [row])
      : { ...row, ...JSON.parse(request.postData || '{}') };
    await send('Fetch.fulfillRequest', { requestId, responseCode: 200,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }, { name: 'Access-Control-Allow-Origin', value: '*' },
        { name: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, DELETE, OPTIONS' }, { name: 'Access-Control-Allow-Headers', value: '*' }],
      body: Buffer.from(JSON.stringify(body)).toString('base64') });
  }
};
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ': ' + result.exceptionDetails.exception?.description);
  return result.result.value;
};
const waitFor = async (expression) => {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await pause(100);
  }
  throw new Error(`Browser condition timed out: ${expression}`);
};
const click = async (selector) => { await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`); await pause(50); };
const set = async (selector, value) => {
  await evaluate(`(() => { const el=document.querySelector(${JSON.stringify(selector)});
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set.call(el, ${JSON.stringify(value)});
    el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true})); })()`);
  await pause(30);
};
const lastWrite = () => requests.filter((request) => ['POST', 'PUT', 'DELETE'].includes(request.method)).at(-1);

try {
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `${origin}/parties?openAdd=1` });
  await waitFor('document.querySelector("#accountType") && document.querySelector(".pagination").getAttribute("aria-busy") === "false"');
  assert.deepEqual(await evaluate('[...document.querySelectorAll("#accountType option")].map(e=>e.textContent)'), ['Customer', 'Supplier', 'Purchase']);
  const layout = await evaluate('[...document.querySelectorAll(".modal, .party-form input, .party-form select, .party-form textarea")].map(e=>({name:e.name==="accountType"?"party_type":e.name||"modal",x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))');
  // Recorded original desktop modal dimensions; retained if the temporary baseline is gone.
  assert.equal(layout[0].w, 700);
  assert.equal(layout[0].h, 738);
  const before = join(tmpdir(), 'account-before-layout.json');
  try { assert.deepEqual(layout, JSON.parse(await readFile(before, 'utf8'))); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const screenshot = await send('Page.captureScreenshot', { format: 'png' });
  await writeFile(join(tmpdir(), 'account-after.png'), Buffer.from(screenshot.data, 'base64'));
  // Native key events run the unchanged delegated Enter handler.
  await evaluate('document.querySelector("#name").focus()');
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  assert.equal(await evaluate('document.activeElement.id'), 'accountType');
  await click('.modal__close');
  assert.equal(await evaluate('[...document.querySelectorAll(".sidebar__link")].some(e=>e.textContent.includes("Customer Management"))'), false);
  assert.equal(await evaluate('[...document.querySelectorAll(".sidebar__link")].some(e=>e.textContent.includes("Accounts"))'), true);

  for (const [type, endpoint, partyType] of [['CUSTOMER', '/customers/', undefined], ['SUPPLIER', '/parties/', 'Supplier'], ['PURCHASE_VENDOR', '/parties/', 'PURCHASE_VENDOR']]) {
    await click('.pagination .btn:last-child');
    await pause();
    assert.equal(requests.at(-1).url.searchParams.get('page'), '2');
    requests.length = 0;
    await set('#accountFilter', type);
    await pause();
    assert.equal(requests.length, 1, `${type}: one request`);
    assert.equal(requests[0].url.pathname, endpoint);
    assert.equal(requests[0].url.searchParams.get('page'), '1');
    assert.equal(requests[0].url.searchParams.get('party_type'), partyType || null);
    await set('.search-bar__input', 'Needle');
    await pause();
    assert.equal(requests.at(-1).url.searchParams.get('search'), 'Needle');
    await set('.search-bar__input', '');
    await pause();

    await click('.page-header .btn--primary');
    assert.equal(await evaluate('document.querySelector("#accountType").value'), type);
    for (const [field, value] of Object.entries({ name: 'Test Account', mobile: '9876543210', city: 'Surat', state: 'Gujarat', address: 'Test road', opening_balance: '125.50' })) await set(`#${field}`, value);
    if (type === 'PURCHASE_VENDOR') {
      await set('#gstin', 'bad');
      const count = requests.length;
      await click('.modal__footer .btn--primary');
      assert.equal(requests.length, count);
      assert.match(await evaluate('document.querySelector(".party-form").textContent'), /GSTIN must be exactly/);
      await set('#gstin', '24ABCDE1234F1Z5');
      assert.equal(await evaluate('document.querySelector("#pan_card").value'), 'ABCDE1234F');
      await set('#gstin', '');
      await set('#pan_card', '');
    }
    await click('.modal__footer .btn--primary');
    await pause();
    assert.equal(lastWrite().method, 'POST');
    assert.equal(lastWrite().url.pathname, endpoint);
    assert.equal(JSON.parse(lastWrite().postData).opening_balance, '125.50');
    assert.equal(JSON.parse(lastWrite().postData).party_type, partyType);
    assert.equal('current_balance' in JSON.parse(lastWrite().postData), false);

    await click('.data-table__action-btn--edit');
    await pause(150);
    assert.equal(await evaluate('document.querySelector("#accountType").disabled'), true);
    await evaluate('document.querySelector("#name").focus()');
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
    assert.equal(await evaluate('document.activeElement.id'), type === 'CUSTOMER' ? 'mobile' : 'country_code');
    await set('#name', 'Renamed');
    await click('.modal__footer .btn--primary');
    await pause();
    assert.equal(lastWrite().method, 'PUT');
    assert.equal(lastWrite().url.pathname, `${endpoint}7`);
    if (type === 'CUSTOMER') assert.equal(JSON.parse(lastWrite().postData).email, 'buyer@example.com');
    await click('.data-table__action-btn--delete');
    await click('.modal__footer .btn--danger');
    await pause();
    assert.equal(lastWrite().method, 'DELETE');
    assert.equal(lastWrite().url.pathname, `${endpoint}7`);
    console.log(`${type}: request count, pagination reset, search, create, edit, delete PASS`);
  }
  requests.length = 0;
  await send('Page.navigate', { url: `${origin}/customers?openAdd=1&returnTo=/sales-entry` });
  await pause(1200);
  assert.equal(await evaluate('location.pathname'), '/parties');
  assert.equal(await evaluate('new URLSearchParams(location.search).get("returnTo")'), '/sales-entry');
  assert.equal(await evaluate('document.querySelector("#accountType").value'), 'CUSTOMER');
  assert.equal(requests.filter((r) => r.method === 'GET').length, 1);
  console.log('Legacy route, sidebar, modal geometry and Enter navigation PASS');

  // Existing transaction callers must retain their old Party payload and options.
  for (const route of ['/purchase-entry', '/purchase-return-entry']) {
    await send('Page.navigate', { url: origin + route });
    await pause(1200);
    await click('[aria-label="Add new supplier"]');
    assert.equal(await evaluate('document.querySelector(".modal__title").textContent'), 'Add New Party');
    assert.deepEqual(await evaluate('[...document.querySelectorAll("#accountType option")].map(e=>e.textContent)'), ['Supplier', 'Customer']);
    await set('.party-form #name', 'Legacy supplier');
    await set('.party-form #state', 'Gujarat');
    await set('.party-form #opening_balance', '321.50');
    await click('.modal__footer .btn--primary');
    await pause();
    const saved = lastWrite();
    assert.equal(saved.method, 'POST');
    assert.equal(saved.url.pathname, '/parties/');
    const payload = JSON.parse(saved.postData);
    assert.equal(payload.name, 'Legacy supplier');
    assert.equal(payload.party_type, 'Supplier');
    assert.equal(payload.opening_balance, '321.50');
    assert.equal(payload.country_code, '+91');
    assert.equal('accountType' in payload, false);
    assert.equal(await evaluate('document.querySelector(".party-form") === null'), true);
    console.log(`${route}: original embedded Party modal and payload PASS`);
  }
} finally {
  await send('Fetch.disable');
  ws.close();
}
