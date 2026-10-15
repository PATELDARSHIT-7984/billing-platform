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
let emptyDoneBy = false;
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
    if (request.method !== 'OPTIONS') requests.push({ ...request, url });
    let body = account ? { ...row, ...JSON.parse(request.postData || '{}') } : [];
    if (account && request.method === 'GET' && url.pathname.endsWith('/')) body = url.searchParams.has('page')
      ? { items: [row], page: 1, total: 1, total_pages: 1, page_size: 20 } : [row];
    if (request.method === 'GET' && url.pathname.includes('item-master')) body = [{ id: 1, name: 'Tile', hsn_code: '1234', unit: 'Box', sale_price: 100, current_stock: 100 }];
    if (request.method === 'GET' && (url.pathname.includes('done-by') || url.pathname.includes('banks'))) body = [{ id: 1, name: 'Operator', is_active: true }];
    if (emptyDoneBy && request.method === 'GET' && url.pathname.includes('done-by')) body = [];
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
    if (request.method === 'POST') body = { id: 91, is_active: true, ...JSON.parse(request.postData || '{}') };
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
const click = async (selector) => { await evaluate(`window.q(${JSON.stringify(selector)}).click()`); await pause(50); };
const set = async (selector, value) => {
  await evaluate(`(() => { const el=window.q(${JSON.stringify(selector)});
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set.call(el, ${JSON.stringify(value)});
    el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true})); })()`);
  await pause(30);
};
const lastWrite = () => requests.filter((request) => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method)).at(-1);

const helpers = String.raw`window.q = (selector) => [...document.querySelectorAll(selector)].find(el=>el.getClientRects().length);
window.field = (label) => [...document.querySelectorAll('.form-field')].find(el=>el.getClientRects().length && el.querySelector('label')?.textContent.trim().replace(/\s*\*$/, '')===label)?.querySelector('input,select,textarea');`;
const setField = async (label, value) => {
  await evaluate(`(()=>{const el=window.field(${JSON.stringify(label)}); if(!el) throw new Error('Missing field '+${JSON.stringify(label)});
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value').set.call(el,${JSON.stringify(value)});
    el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));})()`); await pause(40);
};
const chooseItem = async () => {
  await evaluate(`window.field('Item Name').focus()`); await pause(50);
  await click('.gt-item-top .searchable-select__option');
};
const go = async (path) => {
  await send('Page.navigate', { url: origin + path }); await pause(400); await evaluate(helpers);
  await waitFor(`typeof window.q === 'function' && window.q('.account-selector')`); await pause(1000);
};
const draft = () => evaluate(`JSON.parse(sessionStorage.getItem(history.state.usr.managedCreate))`);
const start = async (entity) => {
  const labels = { account: 'Account', item: 'Item', doneBy: 'Done By', bank: 'Cash/Bank' };
  await click(`[aria-label="Add new ${labels[entity]}"]`);
  await waitFor(`window.q('.modal') && history.state?.usr?.managedCreate`);
  await pause(700);
  assert.equal(await evaluate(`document.querySelectorAll('#root > div[hidden]').length`), 1, 'Exactly one retained origin');
  assert.equal(await evaluate(`document.querySelectorAll('.app-shell').length`), 2, 'Only origin and destination mounted');
  return draft();
};
const finish = async (path) => {
  const before = requests.length;
  await click('.modal__footer .btn--primary');
  await waitFor(`location.pathname+location.search === ${JSON.stringify(path)} && !history.state?.usr?.draftToken`);
  await pause(600);
  assert.equal(await evaluate(`document.querySelectorAll('.app-shell').length`), 1, 'Destination unmounted after return');
  assert.equal(requests.slice(before).filter(r=>r.method==='GET').length, 0, 'No return-time lookup or master refresh');
  assert.equal(await evaluate(`Object.keys(sessionStorage).filter(k=>k.startsWith('billing:draft:')).length`),0);
};
const preserved = (before, after, entity) => {
  assert.deepEqual(after.items,before.items);
  const a=structuredClone(after.details), b=structuredClone(before.details);
  if(entity==='account') for(const key of ['_account','_accountType','party_id','customer_id']) { delete a[key];delete b[key]; }
  if(entity==='doneBy') for(const key of ['_doneBy','done_by']) { delete a[key];delete b[key]; }
  assert.deepEqual(a,b);
  if(entity!=='item') assert.deepEqual(after.itemForm,before.itemForm);
  else for(const key of ['quantity','discount']) assert.equal(after.itemForm[key],before.itemForm[key]);
  assert.equal(after.editingIndex,before.editingIndex);
};
const probe = async () => {
  const state=await start('doneBy'); await click('.modal__close');
  await waitFor(`!history.state?.usr?.draftToken && !history.state?.usr?.managedCreate`); await pause(100);
  return state.data;
};
try {
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Page.enable');
  await send('Page.addScriptToEvaluateOnNewDocument', { source: helpers });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  for (const [path,party] of [['/purchase-entry',true],['/sales-entry',false],['/purchase-return-entry',true],['/sales-return-entry',false],['/quotation-entry',false]]) {
    await go(path);
    if (party) await set('.account-selector select','PURCHASE_VENDOR');
    await pause(); await evaluate(`window.q('.account-selector input').focus()`); await pause(30); await click('.account-selector .searchable-select__option');
    await setField('Address','Draft address'); await setField('Brokerage','2.50'); await setField("Broker's Remarks",'Keep this draft');
    await chooseItem(); await setField('Quantity','2'); await setField('Price','25');
    await evaluate(`[...document.querySelectorAll('button')].find(el=>el.getClientRects().length && el.textContent.trim()==='Add Item').click()`); await pause(100);
    await setField('Quantity','3');
    const accountDraft = await start('account');
    assert.equal(accountDraft.data.items.length,1,'Existing item row must be preserved');
    assert.equal(accountDraft.context.accountType,party?'PURCHASE_VENDOR':'CUSTOMER');
    assert.equal(await evaluate(`window.q('#accountType').value`),party?'PURCHASE_VENDOR':'CUSTOMER');
    await set('#name','Created Account'); await set('#mobile','9876543210'); await set('#city','Surat'); await set('#state','Gujarat'); await set('#address','Account address');
    await finish(path);
    assert.equal(await evaluate(`window.q('.account-selector input').value`),'Created Account');
    preserved(accountDraft.data,await probe(),'account');
    const itemDraft = await start('item');
    await set('#name','Created Tile'); await set('#hsn_code','5555');
    await evaluate(`window.field('Unit').focus()`); await setField('Unit','Box');
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    await set('#purchase_price','30'); await set('#sale_price','40');
    await finish(path);
    assert.equal(await evaluate(`window.field('Item Name').value`),'Created Tile');
    preserved(itemDraft.data,await probe(),'item');
    const personDraft=await start('doneBy'); await set('#name','Created Person'); await finish(path);
    assert.equal(await evaluate(`window.field('Done By').value`),'Created Person');
    preserved(personDraft.data,await probe(),'doneBy');
    const shot=await send('Page.captureScreenshot',{format:'png'});
    await writeFile(join(tmpdir(),path.slice(1)+'-managed-create.png'),Buffer.from(shot.data,'base64'));
    console.log(path+': Account, Item, Done By create, exact draft preservation, cancel and zero return GETs PASS');
  }
  await go('/purchase-entry?edit=88');
  await waitFor(`window.q('.account-selector input')?.value==='Local Vendor'`);
  await setField("Broker's Remarks",'Unsaved edit');
  const edit=await start('doneBy'); assert.equal(edit.origin,'/purchase-entry?edit=88');
  await set('#name','Edit Person'); await finish('/purchase-entry?edit=88');
  assert.equal(await evaluate(`window.field("Broker's Remarks").value`),'Unsaved edit');
  console.log('Edit identity and unsaved edit state PASS');
  // Storage failure must leave the edit form and its state untouched.
  await evaluate(`window.originalSetItem=Storage.prototype.setItem; Storage.prototype.setItem=function(){throw new Error('Storage full')}`);
  const requestsBeforeFailure=requests.length;
  await click('[aria-label="Add new Item"]'); await pause(200);
  assert.equal(await evaluate('location.pathname+location.search'),'/purchase-entry?edit=88');
  assert.equal(await evaluate(`window.field("Broker's Remarks").value`),'Unsaved edit');
  assert.equal(requests.length,requestsBeforeFailure);
  assert.equal(await evaluate(`document.body.innerText.includes('Cannot leave this form')`),true);
  await evaluate('Storage.prototype.setItem=window.originalSetItem');
  // Refresh while on the management screen must restore the unsaved edit, not refetch its booked transaction.
  await start('doneBy');
  await send('Page.reload'); await pause(1300); await evaluate(helpers);
  await waitFor(`window.q('.modal__close')`); await click('.modal__close');
  await waitFor(`location.pathname+location.search==='/purchase-entry?edit=88' && !history.state?.usr?.draftToken`);
  assert.equal(await evaluate(`window.field("Broker's Remarks").value`),'Unsaved edit');
  // Browser Back restores the draft; Forward doesn't reopen a consumed create flow.
  await start('doneBy');
  await evaluate('history.back()');
  await waitFor(`location.pathname==='/purchase-entry' && !history.state?.usr?.draftToken`);
  assert.equal(await evaluate(`window.field("Broker's Remarks").value`),'Unsaved edit');
  await evaluate('history.forward()'); await pause(700);
  assert.equal(await evaluate('location.pathname'),'/done-by');
  assert.equal(await evaluate(`Boolean(window.q('.modal'))`),false);
  console.log('Storage failure, management refresh, browser Back/Forward and consumed-draft protection PASS');

  await send('Page.navigate',{url:origin+'/rojmel'});await pause(1000);await evaluate(helpers);await click('.page-header .btn--primary');await pause(500);
  await set('#amount','123.45');await set('#remarks','Keep Rojmel');
  for (const [entity,label] of [['account','Created Rojmel Account'],['bank','Created Bank'],['doneBy','Created Rojmel Person']]) {
    const before=await start(entity);await set('#name',label);
    if(entity==='account') await set('#state','Gujarat');
    await finish('/rojmel');
    assert.equal(await evaluate(`window.q('#amount').value`),'123.45');assert.equal(await evaluate(`window.q('#remarks').value`),'Keep Rojmel');
    const selector=entity==='account'?'.account-selector input':entity==='bank'?'#cash_bank_id':'#done_by_id';
    assert.equal(await evaluate(`window.q(${JSON.stringify(selector)}).value`),entity==='account'?label:'91');
    assert.equal(before.data.form.amount,'123.45');
  }
  const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(join(tmpdir(),'rojmel-managed-create.png'),Buffer.from(shot.data,'base64'));
  console.log('Rojmel account/bank/person creation and preserved form PASS');

  // Compare each button with its control, not fixed page coordinates.
  for (const path of ['/purchase-entry', '/sales-entry', '/purchase-return-entry', '/sales-return-entry', '/quotation-entry', '/rojmel']) {
    for (emptyDoneBy of [false, true]) {
      await send('Page.navigate', { url: origin + path }); await pause(1200); await evaluate(helpers);
      if (path === '/rojmel') { await click('.page-header .btn--primary'); await pause(300); }
      if (emptyDoneBy && path === '/rojmel') await click('.modal__footer .btn--primary');
      if (emptyDoneBy) assert.ok(await evaluate(`Boolean(window.q('.form-field__error'))`), 'Real empty-list or validation message visible');
      for (const width of [1440, 1366, 1024, 768, 390]) {
        await send('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: false });
        await pause(50);
        const controls = await evaluate(`[...document.querySelectorAll('.gt-plus')].filter(b=>b.getClientRects().length).map(button=>{
          const row=button.parentElement, control=row.querySelector('input,select');
          const b=button.getBoundingClientRect(), c=control?.getBoundingClientRect(), r=row.getBoundingClientRect();
          return {label:button.getAttribute('aria-label'),row:row.classList.contains('form-control-row'),
            aligned:!!c && Math.abs(b.top-c.top)<1 && Math.abs(b.bottom-c.bottom)<1,
            contained:b.right<=r.right+1 && c.left>=r.left-1, messageInside:!!row.querySelector('.form-field__error')};
        })`);
        assert.equal(controls.length, 3, `${path}: all managed controls present`);
        assert.ok(controls.every(c=>c.row && c.aligned && c.contained && !c.messageInside), JSON.stringify({path,width,emptyDoneBy,controls}));
      }
    }
    console.log(`${path}: control-row alignment with/without messages at five widths PASS`);
  }
} finally { await send('Fetch.disable'); ws.close(); }
