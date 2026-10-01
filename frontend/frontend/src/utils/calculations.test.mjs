import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { computeLineAmounts, computeTotals } from './calculations.js';

// The exact same expected values exercise all four backend calculators.
const cases = JSON.parse(readFileSync(new URL(
  '../../../../backend/api/tests/fixtures/financial_rounding.json', import.meta.url), 'utf8'));

for (const example of cases) {
  test(example.name, () => {
    const items = example.items.map((row) => ({ quantity: 1, ...row,
      ...(example.is_gst === false ? { cgst: 0, sgst: 0, igst: 0 } : {}) }));
    const totals = computeTotals(items);
    assert.deepEqual([totals.taxableAmount, totals.sgstTotal, totals.cgstTotal,
      totals.igstTotal, totals.roundOff, totals.grandTotal], example.totals);
    assert.deepEqual(items.map((row) => computeLineAmounts(row).amount), example.amounts);
  });
}
