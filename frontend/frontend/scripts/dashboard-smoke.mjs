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
let scenario = 'normal';
const summary = () => {
  const data = {start_date:'2026-10-01',end_date:'2026-10-16',balances_as_of:'current',
    customer_receivable:'48500.00',customer_credit:'1200.00',supplier_payable:'21300.00',supplier_advance:'3500.00',
    total_sales:'120000.00',total_purchase:'70000.00',total_sales_return:'5000.00',total_purchase_return:'2000.00',
    net_sales:'115000.00',net_purchase:'68000.00',total_received:'40000.00',total_paid:'25000.00',net_cash_flow:'15000.00',
    sales_return_rate:'4.17',purchase_return_rate:'2.86'};
  if(scenario==='zero') for(const key of Object.keys(data)) if(!['start_date','end_date','balances_as_of'].includes(key)) data[key]='0.00';
  if(scenario==='receivable') data.customer_receivable='9850000.00';
  if(scenario==='payable') {data.supplier_payable='7500000.00';data.customer_credit='85000.00';data.total_paid='90000.00';data.net_cash_flow='-50000.00';}
  if(scenario==='large') for(const key of ['customer_receivable','customer_credit','supplier_payable','supplier_advance','total_sales','total_purchase']) data[key]='123456789012.34';
  return data;
};
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
    let body = {};
    const metric=summary();
    if (url.pathname==='/dashboard/summary') {body=metric; if(scenario==='loading') await pause(1800);}
    if (url.pathname==='/dashboard/trend') body={start_date:'2026-05-01',end_date:'2026-10-16',labels:['May 2026','Jun 2026','Jul 2026','Aug 2026','Sep 2026','Oct 2026'],sales:scenario==='zero'?['0','0','0','0','0','0']:['10000','15000','12000','16000','20000','120000'],purchase:scenario==='zero'?['0','0','0','0','0','0']:['9000','11000','9000','13000','14000','70000']};
    if (url.pathname==='/dashboard/recent-transactions') body=scenario==='zero'?[]:[{id:1,type:'sales',number:'INV-001',name:'Local Customer',amount:'12500.00',date:'2026-10-16'}];
    if (url.pathname==='/dashboard/accounts' || url.pathname==='/dashboard/top-partners') body={items:[],total:0,limit:5,skip:0};
    if(scenario==='error' && url.pathname==='/dashboard/summary') body={detail:'INTERNAL_DATABASE_SECRET'};
    await send('Fetch.fulfillRequest', { requestId, responseCode: scenario==='error' && url.pathname==='/dashboard/summary' ? 500 : 200,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }, { name: 'Access-Control-Allow-Origin', value: '*' },
        { name: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, PATCH, DELETE, OPTIONS' }, { name: 'Access-Control-Allow-Headers', value: '*' }],
      body: Buffer.from(JSON.stringify(body)).toString('base64') }).catch(error => {
        // A date change/navigation can abort an intentionally delayed mock request.
        if (!error.message.includes('Invalid InterceptionId')) throw error;
      });
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
const helpers = `window.q = selector => [...document.querySelectorAll(selector)].find(el=>el.getClientRects().length);`;
const go=async()=>{requests.length=0;await send('Page.navigate',{url:origin+'/'});await pause(100);await evaluate(helpers);};
const ready=()=>waitFor(`document.querySelectorAll('.dashboard__stat').length===4`);
try {
  await send('Fetch.enable',{patterns:[{urlPattern:'*'}]});await send('Page.enable');
  await send('Page.addScriptToEvaluateOnNewDocument',{source:helpers});
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  for(scenario of ['normal','zero','receivable','payable','large']) {
    await go();await ready();await pause(600);
    const expected=summary();
    const {formatINR}=await import('../src/utils/dashboardFormat.js');
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.dashboard__stat-value')].map(e=>e.textContent)`), ['customer_receivable','supplier_payable','total_sales','total_purchase'].map(key=>formatINR(expected[key])));
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.dashboard__credits .dashboard__money')].map(e=>e.textContent)`), ['customer_credit','supplier_advance'].map(key=>formatINR(expected[key])));
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.dashboard__performance-totals .dashboard__money')].map(e=>e.textContent)`), ['total_sales_return','net_sales','total_purchase_return','net_purchase'].map(key=>formatINR(expected[key])));
    assert.equal(await evaluate(`document.querySelector('.dashboard__cash-net .dashboard__money').textContent`),formatINR(expected.net_cash_flow));
    const endpoints=requests.filter(r=>r.url.pathname.startsWith('/dashboard/')).map(r=>r.url.pathname).sort();
    const expectedEndpoints=['accounts','recent-transactions','summary','top-partners','trend'].map(p=>'/dashboard/'+p).sort();
    assert.deepEqual([...new Set(endpoints)],expectedEndpoints,'Only the five existing dashboard endpoints');
    assert.ok(endpoints.length===5 || endpoints.length===10,'Five production requests or StrictMode development replay');
    assert.ok(expectedEndpoints.every(path=>endpoints.filter(p=>p===path).length===endpoints.length/5),'No per-card requests');
    const text=await evaluate(`document.querySelector('.dashboard').textContent`);
    assert.ok(!text.includes('tracking pending'));assert.ok(text.includes('exclude Purchase-type accounts'));
    if(scenario==='zero') {assert.ok(text.includes('No customer payments are pending.'));assert.ok(text.includes('No sales recorded in this period.'));assert.ok(text.includes('Money received and paid are equal.'));}
    if(scenario==='payable') assert.ok(await evaluate(`document.querySelector('.dashboard__cash-net--negative')!==null`));
    if(scenario==='normal') assert.ok(await evaluate(`document.querySelector('.dashboard__cash-net--positive')!==null`));
    for(const width of [1440,1366,1024,768,390]) {
      await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});await pause(100);
      const geometry=await evaluate(`(()=>{const c=document.querySelector('.app-shell__content');return {client:c.clientWidth,scroll:c.scrollWidth,cards:[...document.querySelectorAll('.dashboard__stat')].map(e=>({client:e.clientWidth,scroll:e.scrollWidth}))};})()`);
      assert.ok(geometry.scroll<=geometry.client+1 && geometry.cards.every(c=>c.scroll<=c.client+1),JSON.stringify({scenario,width,geometry}));
      const shot=await send('Page.captureScreenshot',{format:'png'});
      await writeFile(join(tmpdir(),`dashboard-${scenario}-${width}.png`),Buffer.from(shot.data,'base64'));
    }
    console.log(`${scenario}: field mapping, formatting, scope, request count and five viewport checks PASS`);
  }
  scenario='normal';await go();await ready();
  await click('.dashboard__more > summary');
  await evaluate(`document.querySelector('.dashboard__more').scrollIntoView({block:'end'})`);
  const details=await send('Page.captureScreenshot',{format:'png'});
  await writeFile(join(tmpdir(),'dashboard-account-details.png'),Buffer.from(details.data,'base64'));
  await evaluate(`document.querySelector('.dashboard__analytics-grid').scrollIntoView({block:'start'})`);
  const activity=await send('Page.captureScreenshot',{format:'png'});
  await writeFile(join(tmpdir(),'dashboard-monthly-activity.png'),Buffer.from(activity.data,'base64'));
  const links=await evaluate(`[...document.querySelectorAll('.dashboard__detail-link,.dashboard__quick-actions a')].map(e=>e.getAttribute('href'))`);
  assert.deepEqual(links,['/parties?accountType=CUSTOMER','/parties?accountType=SUPPLIER','/sales-history','/purchase-history','/sales-entry','/purchase-entry','/parties?openAdd=1','/items?openAdd=1','/rojmel']);
  await set('[aria-label="Dashboard date filter"]','today');await pause(700);
  for(const path of ['summary','trend','recent-transactions','top-partners']) assert.equal(requests.filter(r=>r.url.pathname==='/dashboard/'+path).at(-1).url.searchParams.get('period'),'today');
  await set('[aria-label="Dashboard date filter"]','custom');await waitFor(`document.querySelector('.dashboard__date-prompt')`);
  await set('[aria-label="Start date"]','2026-10-01');await set('[aria-label="End date"]','2026-10-16');await ready();
  scenario='loading';await go();await waitFor(`document.querySelector('[aria-label="Loading business summary"]')`);await ready();
  scenario='error';await go();await waitFor(`document.querySelector('.dashboard__error')`);
  assert.ok(!(await evaluate('document.body.innerText')).includes('INTERNAL_DATABASE_SECRET'));
  scenario='normal';await click('.dashboard__error button');await ready();
  await evaluate(`document.querySelector('.dashboard__detail-link[href="/parties?accountType=CUSTOMER"]').focus()`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await waitFor(`location.pathname==='/parties' && new URLSearchParams(location.search).get('accountType')==='CUSTOMER'`);
  console.log('Navigation destinations, date filters, loading, safe error and retry PASS');
} finally {await send('Page.navigate',{url:'about:blank'});await send('Fetch.disable');ws.close();}
