// Purchase, returns and quotation use whole-rupee totals. Sales has its own
// component-to-paise policy in salesCalculations.js.
function roundHalfUp(value, places = 2) {
  // Same binary-noise compensation and half-away-from-zero rule as the backend.
  const magnitude = Math.abs(value);
  const scale = 10 ** places;
  const rounded = Math.floor((magnitude + Number.EPSILON * Math.max(1, magnitude)) * scale + 0.5) / scale;
  return rounded ? Math.sign(value) * rounded : 0;
}

export function computeLineAmounts({ quantity, price, disc_percent, sgst, cgst, igst }) {
  const qty = Number(quantity) || 0;
  const rate = Number(price) || 0;
  const disc = Number(disc_percent) || 0;
  const sgstPct = Number(sgst) || 0;
  const cgstPct = Number(cgst) || 0;
  const igstPct = Number(igst) || 0;

  const gross = qty * rate;
  const taxable = gross - gross * disc / 100;
  const sgstAmt = (taxable * sgstPct) / 100;
  const cgstAmt = (taxable * cgstPct) / 100;
  const igstAmt = (taxable * igstPct) / 100;
  const amount = taxable + sgstAmt + cgstAmt + igstAmt;

  return { taxable, sgstAmt, cgstAmt, igstAmt, amount: roundHalfUp(amount) };
}

// Round-off is no longer a manual field the user types into -- the backend
// always rounds the net total to the nearest whole rupee (599.99 -> 600,
// 451.65 -> 452) and computes round_off as just the adjustment that
// produced it. This mirrors that exact rule client-side so the on-screen
// total matches what gets saved, without waiting for a round trip.
export function computeTotals(items) {
  const totals = items.reduce(
    (acc, item) => {
      const { taxable, sgstAmt, cgstAmt, igstAmt } = computeLineAmounts(item);
      acc.taxableAmount += taxable;
      acc.sgstTotal += sgstAmt;
      acc.cgstTotal += cgstAmt;
      acc.igstTotal += igstAmt;
      return acc;
    },
    { taxableAmount: 0, sgstTotal: 0, cgstTotal: 0, igstTotal: 0 }
  );

  const netTotal = totals.taxableAmount + totals.sgstTotal + totals.cgstTotal + totals.igstTotal;
  const grandTotal = roundHalfUp(netTotal, 0);
  const roundOff = roundHalfUp(grandTotal - netTotal);

  return { taxableAmount: roundHalfUp(totals.taxableAmount),
    sgstTotal: roundHalfUp(totals.sgstTotal), cgstTotal: roundHalfUp(totals.cgstTotal),
    igstTotal: roundHalfUp(totals.igstTotal), roundOff, grandTotal };
}

export function formatCurrency(value) {
  const num = Number(value) || 0;
  return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Small +/- signed version for the Round Off line specifically, so it
// reads like an adjustment ("+ ₹0.35") rather than a currency amount.
export function formatSignedCurrency(value) {
  const num = Number(value) || 0;
  const sign = num > 0 ? '+ ' : num < 0 ? '- ' : '';
  return `${sign}${formatCurrency(Math.abs(num))}`;
}
