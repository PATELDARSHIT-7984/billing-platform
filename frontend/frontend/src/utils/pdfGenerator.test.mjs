import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { generateInvoicePDF, LETTERHEAD_HEIGHT } from './pdfGenerator.js';
import { documentPdfData, PDF_MODES } from './documentPdfData.js';
import { company, invoice, quotation } from './pdfFixtures.mjs';

function content(doc) {
  return doc.internal.pages.slice(1).map((page) => page.join('\n')).join('\n');
}
function texts(doc) {
  return [...content(doc).matchAll(/\(([^\n]*?)\) Tj/g)].map((match) => match[1]);
}

for (const type of ['sale', 'purchase', 'quotation', 'purchaseReturn', 'salesReturn']) {
  test(`${type}: both modes preserve all document content and values`, () => {
    const data = type === 'sale' ? invoice : { ...quotation, bill_no: 'PUR-001',
      return_no: 'RET-001', return_date: '2026-09-28', original_invoice_no: 'INV-ORIGINAL' };
    const detail = documentPdfData(type, data);
    const before = JSON.stringify(detail);
    const withHeader = texts(generateInvoicePDF(detail, company));
    const withoutHeader = texts(generateInvoicePDF(detail, company, { includeLetterhead: false }));
    // Header precedes the title. Everything from the title onward must be identical.
    const title = detail.bill.document_title || 'SALES INVOICE';
    assert.deepEqual(withHeader.slice(withHeader.indexOf(title)), withoutHeader);
    assert.ok(withHeader.some((text) => text.includes('12 Market Road')));
    assert.ok(!withoutHeader.some((text) => text.includes('12 Market Road')));
    for (const value of [detail.bill.invoice_no, detail.bill.customer_name, 'LED Bulb 9W', '797.00', '796.50', '60.75', '0.50']) {
      assert.ok(withoutHeader.some((text) => text.includes(value)), value);
    }
    assert.equal(JSON.stringify(detail), before);
  });
}

test('without letterhead leaves the entire first-page reserved area blank', () => {
  const doc = generateInvoicePDF(invoice, company, { includeLetterhead: false });
  const page = doc.internal.pages[1].join('\n');
  const positions = [...page.matchAll(/([\d.]+) ([\d.]+) Td/g)].map((match) => 297 - Number(match[2]) / doc.internal.scaleFactor);
  assert.ok(positions.length > 5);
  assert.ok(Math.min(...positions) >= 12 + LETTERHEAD_HEIGHT);
});

test('missing optional company values and default arguments are safe', () => {
  for (const profile of [undefined, null, {}, { company_name: 'Only Name', terms_and_conditions: null }]) {
    assert.ok(generateInvoicePDF(invoice, profile).output().startsWith('%PDF'));
  }
});

test('multi-page invoice repeats table headings and retains totals and terms', () => {
  const detail = { bill: invoice.bill, items: Array.from({ length: 65 }, (_, i) => ({ ...invoice.items[0], item_name: `LED Bulb ${i + 1}` })) };
  for (const includeLetterhead of [true, false]) {
    const doc = generateInvoicePDF(detail, company, { includeLetterhead });
    assert.ok(doc.getNumberOfPages() >= 3);
    assert.ok(doc.internal.pages[2].join('\n').includes('(DESCRIPTION)'));
    assert.ok(texts(doc).includes('LED Bulb 65'));
    assert.ok(texts(doc).includes('NET AMOUNT'));
    assert.ok(texts(doc).some((text) => text.includes('Payment due within 30 days')));
  }
});

test('history actions use both mode flags and the existing shared Company context', () => {
  assert.deepEqual(PDF_MODES.map((mode) => mode.includeLetterhead), [true, false]);
  const component = readFileSync(new URL('../components/common/PdfDownloadActions.jsx', import.meta.url), 'utf8');
  assert.ok(component.includes('onClick={() => download(includeLetterhead)}'));
  assert.ok(component.includes('downloadDocumentPDF(type, detail, company, { includeLetterhead })'));
  for (const page of ['SalesHistory', 'BillHistory', 'PurchaseHistory', 'QuotationHistory', 'PurchaseReturnHistory', 'SalesReturnHistory']) {
    const source = readFileSync(new URL(`../pages/${page}.jsx`, import.meta.url), 'utf8');
    assert.ok(source.includes('<PdfDownloadActions'), page);
  }
});

test('long terms continue onto new pages without clipping text or dropping totals', () => {
  const profile = { ...company, terms_and_conditions: Array.from({ length: 90 }, (_, i) => `Term ${i + 1}: Please retain this document for your records.`) };
  const doc = generateInvoicePDF(invoice, profile, { includeLetterhead: false });
  assert.ok(doc.getNumberOfPages() > 1);
  assert.ok(texts(doc).some((text) => text.includes('Term 90')));
  assert.ok(texts(doc).includes('NET AMOUNT'));
  for (const match of content(doc).matchAll(/([\d.]+) ([\d.]+) Td/g)) {
    const y = 297 - Number(match[2]) / doc.internal.scaleFactor;
    assert.ok(y >= 12 && y <= 285, `Text outside print margins: ${y}`);
  }
});
