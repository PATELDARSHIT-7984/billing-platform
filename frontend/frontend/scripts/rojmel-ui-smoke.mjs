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
    if (request.method !== 'OPTIONS') requests.push({ ...request, url });
    const search = url.searchParams.get('search');
    let body = [];
    if (url.pathname.includes('parties')) body = [{ id: 8, name: 'Local Vendor', party_type: 'Supplier', is_active: true }];
    if (url.pathname.includes('banks')) body = [{ id: 1, name: 'Main Bank', is_active: true }];
    if (url.pathname.includes('done-by')) body = [{ id: 1, name: 'Darshit', is_active: true }];
    if (url.pathname.startsWith('/rojmel')) {
      if (url.pathname.endsWith('summary')) body = { total_received: '10300.00', total_paid: search === 'negative' ? '12300.00' : search === 'zero' ? '10300.00' : '2000.00', net_earning: search === 'negative' ? '-2000.00' : search === 'zero' ? '0.00' : '8300.00' };
      else {
        const page = Number(url.searchParams.get('page') || 1), size = Number(url.searchParams.get('page_size') || 20);
        body = { items: search === 'empty' ? [] : Array.from({ length: Math.min(size, 40 - (page - 1) * size) }, (_, i) => ({
          id: 55 + i, receipt_no: `R-${String((page - 1) * size + i + 1).padStart(4, '0')}`,
          transaction_type: ['Cr Pay', 'Dr Pay', 'Cash/Bank', 'JV'][i % 4], party_id: 8, customer_id: null,
          amount: 10300, net_amount: 10300, cash_bank_id: 1, done_by_id: 1, pay_mode: 'Cash',
          given_taken_date: '2026-10-10', effective_date: '2026-10-10', remarks: 'Saved note',
        })), page, page_size: size, total: search === 'empty' ? 0 : 40, total_pages: Math.ceil(40 / size) };
        if (request.method === 'GET') await pause(250);
      }
      body = { data: body };
    }
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
const click = async (selector) => { await evaluate(`window.q(${JSON.stringify(selector)}).click()`); await pause(50); };
const set = async (selector, value) => {
  await evaluate(`(() => { const el=window.q(${JSON.stringify(selector)});
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set.call(el, ${JSON.stringify(value)});
    el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true})); })()`);
  await pause(30);
};
const helpers = `window.q = selector => [...document.querySelectorAll(selector)].find(el => el.getClientRects().length);`;
try {
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Page.enable');
  await send('Page.addScriptToEvaluateOnNewDocument', { source: helpers });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: origin + '/rojmel' });
  await waitFor(`document.querySelector('.rojmel-amount')`);
  await evaluate(helpers);
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.rojmel-summary__value')].map(el=>el.textContent)`), ['\u20b910,300.00', '\u20b92,000.00', '\u20b98,300.00']);
  assert.match(await evaluate(`document.querySelector('tbody').textContent`), /Local Vendor.*Main Bank.*Darshit.*\u20b910,300.00/);
  assert.equal(await evaluate(`document.querySelectorAll('thead th').length`), 9);
  assert.equal(requests.some(r=>/\/(parties|banks|done-by)\/\d+/.test(r.url.pathname)), false, 'No per-row lookups');
  console.log('Summary, currency, all columns and no per-row requests PASS');

  for (const width of [1440, 1200, 1024, 768, 390]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: false });
    if (width === 390) await click('.sidebar__toggle'); // Existing app supports manual collapse.
    await pause(100);
    const geometry = await evaluate(`(() => {const content=document.querySelector('.app-shell__content');return {viewport:innerWidth,content:content.clientWidth,scroll:content.scrollWidth,fields:[...document.querySelectorAll('.rojmel-filters input,.rojmel-filters select')].map(e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))};})()`);
    assert.ok(geometry.scroll <= geometry.content + 1, JSON.stringify(geometry));
    assert.ok(geometry.fields.every(f=>f.left>=0 && f.right<=width), JSON.stringify(geometry));
    const screenshot=await send('Page.captureScreenshot',{format:'png'});
    await writeFile(join(tmpdir(),`rojmel-ui-${width}.png`),Buffer.from(screenshot.data,'base64'));
    await evaluate(`document.querySelector('.pagination').scrollIntoView({block:'end'}); document.querySelector('.data-table-wrap').scrollLeft=9999;`);
    assert.ok(await evaluate(`document.querySelector('.data-table__actions-col').getBoundingClientRect().right <= innerWidth`), 'Actions reachable by table scrolling');
    const bottom=await send('Page.captureScreenshot',{format:'png'});
    await writeFile(join(tmpdir(),`rojmel-ui-${width}-pagination.png`),Buffer.from(bottom.data,'base64'));
    await evaluate(`document.querySelector('.app-shell__content').scrollTop=0; document.querySelector('.data-table-wrap').scrollLeft=0;`);
    console.log(`${width}px layout and screenshot PASS`);
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await click('.sidebar__toggle');
  const summaries=requests.filter(r=>r.url.pathname.endsWith('summary')).length;
  await click('[aria-label="Page 2"]');
  await waitFor(`document.querySelector('.data-table__state')?.textContent.includes('Loading records')`);
  await waitFor(`document.querySelector('.rojmel-receipt')?.textContent==='R-0021'`);
  assert.equal(requests.filter(r=>r.url.pathname.endsWith('summary')).length,summaries,'Pagination does not refetch summary');
  await set('.pagination__size select','50');
  await waitFor(`document.querySelectorAll('.rojmel-receipt').length===40`);
  await set('#start_date','2026-10-01'); await set('#end_date','2026-10-31'); await set('#party_filter','8');
  await pause(800);
  const latest=requests.filter(r=>r.url.pathname==='/rojmel/' && r.method==='GET').at(-1).url.searchParams;
  assert.equal(latest.get('start_date'),'2026-10-01'); assert.equal(latest.get('end_date'),'2026-10-31'); assert.equal(latest.get('party_id'),'8');
  for (const [search,tone,text] of [['negative','negative','Negative'],['zero','neutral','Zero']]) {
    await set('#rojmel_search',search);
    await waitFor(`document.querySelector('.rojmel-summary__card--net .rojmel-summary__hint').textContent.startsWith('${text}')`);
    assert.ok(await evaluate(`document.querySelector('.rojmel-summary__card--net .rojmel-summary__value--${tone}')!==null`));
  }
  await set('#rojmel_search','empty');
  await waitFor(`document.querySelector('.rojmel-empty')`);
  await click('[aria-label="Clear search"]');
  await waitFor(`document.querySelector('.rojmel-receipt')`);
  console.log('Pagination, rows per page, filters, negative/zero net, empty state and clear search PASS');

  await click('.page-header .btn--primary');
  await waitFor(`document.querySelector('.modal')`);
  assert.ok(await evaluate(`document.querySelector('[aria-label="Add new Account"]')!==null`));
  await evaluate(`document.querySelector('#payment_for').focus()`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  assert.equal(await evaluate(`document.activeElement.id`),'remarks');
  await set('#cash_bank_id','1'); await set('#done_by_id','1'); await set('#amount','100');
  await click('.modal__footer .btn--primary'); await pause(800);
  assert.ok(requests.some(r=>r.method==='POST' && r.url.pathname==='/rojmel/'));
  await waitFor(`!document.querySelector('.modal')`);
  await click('.data-table__action-btn--edit'); await pause(500);
  await set('#remarks','Presentation regression'); await click('.modal__footer .btn--primary'); await pause(800);
  assert.ok(requests.some(r=>r.method==='PATCH' && r.url.pathname==='/rojmel/55'));
  await click('.data-table__action-btn--delete'); await click('.modal__footer .btn--danger'); await pause(800);
  assert.ok(requests.some(r=>r.method==='DELETE' && r.url.pathname==='/rojmel/55'));
  console.log('New Entry, Enter navigation, edit and delete PASS');
} finally {
  await send('Page.navigate',{url:'about:blank'});
  await send('Fetch.disable');
  ws.close();
}
