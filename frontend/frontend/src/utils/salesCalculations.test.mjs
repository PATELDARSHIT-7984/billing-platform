import test from 'node:test';
import assert from 'node:assert/strict';
import { computeLineAmounts, computeTotals, salesLineFromSnapshot } from './salesCalculations.js';

const line = { quantity: 2, price: 80, disc_percent: 10, cgst: 9, sgst: 9, igst: 0 };

test('custom rate, discount and split GST', () => {
  assert.deepEqual(computeLineAmounts(line), { gross: 160, discountAmount: 16, taxable: 144,
    cgstAmt: 12.96, sgstAmt: 12.96, igstAmt: 0, amount: 169.92 });
});
test('GST off overrides configured rates, including newly selected items', () => {
  assert.equal(computeLineAmounts(line, false).amount, 144);
  assert.equal(computeTotals([line], false).cgstTotal, 0);
});
test('IGST and multiple line totals', () => {
  assert.equal(computeLineAmounts({ ...line, cgst: 0, sgst: 0, igst: 18 }).igstAmt, 25.92);
  assert.equal(computeTotals([line, { ...line, quantity: 1, price: 10.05, disc_percent: 0 }]).grandTotal, 181.77);
});
test('paise rounding agrees with backend examples', () => {
  for (const [price, cgst, expected] of [[1.005, 0, 1.01], [100.5, 0, 100.5], [0.05, 10, 0.06]]) {
    assert.equal(computeLineAmounts({ quantity: 1, price, cgst }).amount, expected);
  }
});
test('edit hydrates transaction inputs and preserves booked amounts', () => {
  const saved = { bill_item_id: 7, quantity: 2, rate: 80, discount_amount: 16,
    taxable_amount: 144, cgst_percent: 9, sgst_percent: 9, igst_percent: 0,
    cgst_amount: 12.96, sgst_amount: 12.96, igst_amount: 0, line_total: 169.92 };
  const edited = { quantity: 2, ...salesLineFromSnapshot(saved) };
  assert.equal(edited.price, 80);
  assert.equal(edited.disc_percent, 10);
  assert.equal(computeTotals([edited]).grandTotal, 169.92);
  assert.equal(computeTotals([{ ...edited, price: 90 }]).grandTotal, 191.16);
  const invoice = { lineIds: [7], subtotal: 160, discount_amount: 16, taxable_amount: 144,
    cgst_amount: 12.96, sgst_amount: 12.96, igst_amount: 0, grand_total: 169.91 };
  assert.equal(computeTotals([edited], true, invoice).grandTotal, 169.91);
  assert.equal(computeTotals([{ ...edited, price: 90 }], true, invoice).grandTotal, 191.16);
});
