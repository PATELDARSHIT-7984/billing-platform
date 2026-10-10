// Run against Vite and headless Edge/Chrome with --remote-debugging-port=9225.
// All XHR is intercepted: this test never writes to a real backend.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
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
    const vendor = url.searchParams.get('party_type') === 'PURCHASE_VENDOR' || url.pathname.endsWith('/8');
    const row = { id: vendor ? 8 : 7, name: vendor ? 'Local Vendor' : 'Supplier ABC', customer_name: 'Customer XYZ',
      mobile: '9876543210', address: 'Road', city: 'Surat', state: 'Gujarat', is_active: true,
      party_type: vendor ? 'PURCHASE_VENDOR' : 'Supplier', opening_balance: '100', balance_type: 'Credit' };
    if ((account || url.pathname.includes('/rojmel')) && request.method !== 'OPTIONS') requests.push({ ...request, url });
    let body = account ? { ...row, ...JSON.parse(request.postData || '{}') } : [];
    if (account && request.method === 'GET' && url.pathname.endsWith('/')) body = url.searchParams.has('page')
      ? { items: [row], page: 1, total: 1, total_pages: 1, page_size: 20 } : [row];
    if (url.pathname.includes('item-master')) body = [{ id: 1, name: 'Tile', hsn_code: '1234', unit: 'Box', sale_price: 100, current_stock: 100 }];
    if (url.pathname.includes('done-by') || url.pathname.includes('banks')) body = [{ id: 1, name: 'Operator' }];
    if (url.pathname === '/rojmel/') body = { items: [{ id: 55, receipt_no: 'R55', transaction_type: 'Dr Pay', party_id: 8, customer_id: null,
      amount: 100, cash_bank_id: 1, done_by_id: 1, pay_mode: 'Cash', given_taken_date: '2026-10-10', effective_date: '2026-10-10', net_amount: 100 }], total: 1, total_pages: 1, page: 1 };
    if (url.pathname.endsWith('/summary')) body = { total_received: 0, total_paid: 0, net_earning: 0 };
    if (request.method === 'GET' && /\/(88|89)$/.test(url.pathname)) {
      const doc = { id: 88, party_id: url.pathname.endsWith('/89') ? 7 : 8, customer_id: 7, bill_id: 88, invoice_no: 'INV-88', bill_no: 'PUR-88', return_no: 'RET-88', quotation_no: 'QUO-88',
        bill_date: '2026-10-10', return_date: '2026-10-10', quotation_date: '2026-10-10', items: [], is_gst: false, subtotal: 0, taxable_amount: 0, grand_total: 0 };
      body = url.pathname.startsWith('/bills/') ? { bill: doc, items: [] } : doc;
    }
    if (url.searchParams.get('search') === 'slow') { body.items[0].name = 'STALE SUPPLIER'; await pause(1400); }
    if (url.pathname.includes('/rojmel') && request.method === 'POST') await pause(700);
    if (url.pathname.includes('/rojmel')) body = { data: body };
    await send('Fetch.fulfillRequest', { requestId, responseCode: 200,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }, { name: 'Access-Control-Allow-Origin', value: '*' },
        { name: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, PATCH, DELETE, OPTIONS' }, { name: 'Access-Control-Allow-Headers', value: '*' }],
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
    if (await evaluate(`Boolean(${expression})`)) return;
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
const lastWrite = () => requests.filter((request) => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method)).at(-1);

try {
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  for (const [path, party] of [['/purchase-entry', true], ['/purchase-return-entry', true], ['/sales-entry', false], ['/sales-return-entry', false], ['/quotation-entry', false]]) {
    requests.length = 0;
    await send('Page.navigate', { url: origin + path });
    await waitFor('document.querySelector(".account-selector input")'); await pause(900);
    assert.equal(await evaluate('document.querySelector(".account-selector select").value'), party ? 'SUPPLIER' : 'CUSTOMER');
    assert.deepEqual(await evaluate('[...document.querySelectorAll(".account-selector select option")].map(e=>e.textContent)'), party ? ['Supplier', 'Purchase'] : ['Customer']);
    const lookups = requests.filter(r=>r.method==='GET' && r.url.pathname.endsWith('/'));
    assert.equal(lookups.length, 1); assert.equal(lookups[0].url.searchParams.get('page_size'), '20');
    assert.equal(await evaluate('(()=>{const [a,b]=document.querySelectorAll(".account-selector > .form-field");return a.getBoundingClientRect().y===b.getBoundingClientRect().y && a.getBoundingClientRect().x<b.getBoundingClientRect().x})()'), true);
    await evaluate('document.querySelector(".account-selector input").focus()'); await pause(50); await click('.account-selector .searchable-select__option');
    assert.equal(await evaluate('document.querySelector(".account-selector input").value'), party ? 'Supplier ABC' : 'Customer XYZ');
    await set('.account-selector input', 'mobile search'); await pause();
    assert.equal(requests.at(-1).url.searchParams.get('search'), 'mobile search');
    assert.equal(await evaluate('document.querySelector(".account-selector input").value'), 'mobile search');
    if (party) {
      await set('.account-selector input', 'slow'); await pause(450);
      await set('.account-selector select', 'PURCHASE_VENDOR');
      assert.equal(await evaluate('document.querySelector(".account-selector input").value'), '');
      await pause(1600); await evaluate('document.querySelector(".account-selector input").focus()'); await pause(50);
      assert.equal(await evaluate('document.querySelector(".account-selector").textContent.includes("STALE SUPPLIER")'), false);
      assert.equal(await evaluate('document.querySelector(".account-selector").textContent.includes("Local Vendor")'), true);
      await evaluate('document.querySelector(".account-selector input").focus()');
      for (const key of ['ArrowDown','Enter']) await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: key==='Enter'?13:40 });
      assert.equal(await evaluate('document.querySelector(".account-selector input").value'), 'Local Vendor');
    }
    await evaluate('document.activeElement.blur()');
    const screenshot = await send('Page.captureScreenshot', { format: 'png' });
    await writeFile(join(tmpdir(), `${path.slice(1)}-account-selector.png`), Buffer.from(screenshot.data, 'base64'));
    await send('Page.navigate', { url: origin + path + '?edit=88' });
    await waitFor(`document.querySelector('.account-selector input')?.value === '${party ? 'Local Vendor' : 'Customer XYZ'}'`);
    assert.equal(await evaluate('document.querySelector(".account-selector select").value'), party ? 'PURCHASE_VENDOR' : 'CUSTOMER');
    console.log(`${path}: default, allowed types, bounded source lookup, search, layout, selection and edit PASS`);
  }
  await send('Page.navigate', { url: origin + '/purchase-entry?edit=89' });
  await waitFor('document.querySelector(".account-selector input")?.value === "Supplier ABC"');
  assert.equal(await evaluate('document.querySelector(".account-selector select").value'), 'SUPPLIER');
  console.log('Existing Supplier edit initialization PASS');
  await send('Page.navigate', { url: origin + '/rojmel' });
  await waitFor('document.querySelector(".page-header .btn--primary")'); await pause();
  await click('.page-header .btn--primary'); await waitFor('document.querySelector(".account-selector")');
  assert.deepEqual(await evaluate('[...document.querySelectorAll(".account-selector select option")].map(e=>e.textContent)'), ['Supplier','Purchase']);
  await click('input[value="Cr Pay"]');
  assert.deepEqual(await evaluate('[...document.querySelectorAll(".account-selector select option")].map(e=>e.textContent)'), ['Customer','Supplier','Purchase']);
  await set('.account-selector select','CUSTOMER'); await pause();
  await evaluate('document.querySelector(".account-selector input").focus()'); await pause(50); await click('.account-selector .searchable-select__option:last-child');
  await set('#cash_bank_id','1'); await set('#done_by_id','1'); await set('#amount','100');
  const screenshot = await send('Page.captureScreenshot', { format: 'png' });
  await writeFile(join(tmpdir(), 'rojmel-account-selector.png'), Buffer.from(screenshot.data, 'base64'));
  await click('.modal__footer .btn--primary');
  assert.equal(await evaluate('document.querySelector(".account-selector select").disabled'), true);
  await pause(1100);
  assert.equal(JSON.parse(lastWrite().postData).customer_id, 7); assert.equal(JSON.parse(lastWrite().postData).party_id, null);
  await click('.data-table__action-btn--edit');
  await waitFor('document.querySelector(".account-selector input")?.value === "Local Vendor"');
  assert.equal(await evaluate('document.querySelector(".account-selector select").value'), 'PURCHASE_VENDOR');
  await set('.account-selector select','CUSTOMER'); await pause();
  await evaluate('document.querySelector(".account-selector input").focus()'); await pause(50); await click('.account-selector .searchable-select__option:last-child');
  await click('input[value="JV"]');
  assert.equal(await evaluate('document.querySelector(".account-selector input").value'), '');
  await click('.modal__footer .btn--primary'); await pause();
  assert.equal(JSON.parse(lastWrite().postData).customer_id, null); assert.equal(JSON.parse(lastWrite().postData).party_id, null);
  console.log('Rojmel: types, Customer payload, disabled state, Vendor edit and unsupported-source clearing PASS');
} finally {
  await send('Fetch.disable'); ws.close();
}

