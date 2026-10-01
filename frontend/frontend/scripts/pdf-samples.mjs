import { mkdirSync, writeFileSync } from 'node:fs';
import { generateInvoicePDF } from '../src/utils/pdfGenerator.js';
import { documentPdfData } from '../src/utils/documentPdfData.js';
import { company, invoice, quotation } from '../src/utils/pdfFixtures.mjs';

const target = new URL('../../../pdf-review/', import.meta.url);
mkdirSync(target, { recursive: true });
for (const [name, detail] of [
  ['invoice', invoice], ['quotation', documentPdfData('quotation', quotation)],
  ['invoice-multipage', { bill: { ...invoice.bill, taxable_amount: 43875,
    cgst_amount: 3948.75, sgst_amount: 3948.75, grand_total: 51773,
    amount_in_words: 'Rupees Fifty One Thousand Seven Hundred Seventy Three Only' },
    items: Array.from({ length: 65 }, (_, i) => ({ ...invoice.items[0], item_name: `LED Bulb ${i + 1}` })) }],
]) {
  for (const includeLetterhead of [true, false]) {
    const doc = generateInvoicePDF(detail, company, { includeLetterhead });
    const filename = `${name}-${includeLetterhead ? 'with' : 'without'}-letterhead.pdf`;
    writeFileSync(new URL(filename, target), Buffer.from(doc.output('arraybuffer')));
    console.log(`${filename}: ${doc.getNumberOfPages()} A4 page(s)`);
  }
}
