// Sales rounds monetary components to paise; Purchase keeps its existing rules.
const money = (value) => Math.round((value + Number.EPSILON * Math.max(1, Math.abs(value))) * 100) / 100;

export function salesLineFromSnapshot(row) {
  const gross = Number(row.rate) * Number(row.quantity);
  return {
    bill_item_id: row.bill_item_id,
    price: row.rate,
    disc_percent: gross ? Number(row.discount_amount || 0) * 100 / gross : 0,
    cgst: row.cgst_percent || 0,
    sgst: row.sgst_percent || 0,
    igst: row.igst_percent || 0,
    _savedLine: row,
  };
}

export function computeLineAmounts(line, isGst = true) {
  const quantity = Number(line.quantity) || 0;
  const rate = Number(line.price) || 0;
  const discount = Number(line.disc_percent) || 0;
  const cgst = isGst ? Number(line.cgst) || 0 : 0;
  const sgst = isGst ? Number(line.sgst) || 0 : 0;
  const igst = isGst ? Number(line.igst) || 0 : 0;
  const saved = line._savedLine;
  if (saved && quantity === saved.quantity && rate === saved.rate
      && Math.abs(discount - salesLineFromSnapshot(saved).disc_percent) < 1e-10
      && cgst === saved.cgst_percent && sgst === saved.sgst_percent && igst === saved.igst_percent) {
    return { gross: money(saved.taxable_amount + (saved.discount_amount || 0)),
      discountAmount: saved.discount_amount || 0, taxable: saved.taxable_amount,
      cgstAmt: saved.cgst_amount, sgstAmt: saved.sgst_amount, igstAmt: saved.igst_amount,
      amount: saved.line_total, savedLineId: saved.bill_item_id };
  }
  const gross = money(quantity * rate);
  const discountAmount = money(gross * discount / 100);
  const taxable = money(gross - discountAmount);
  const cgstAmt = money(taxable * cgst / 100);
  const sgstAmt = money(taxable * sgst / 100);
  const igstAmt = money(taxable * igst / 100);
  return { gross, discountAmount, taxable, cgstAmt, sgstAmt, igstAmt,
    amount: money(taxable + cgstAmt + sgstAmt + igstAmt) };
}

export function computeTotals(items, isGst = true, savedInvoice = null) {
  const unchangedIds = items.map((item) => computeLineAmounts(item, isGst).savedLineId).sort((a, b) => a - b);
  if (savedInvoice && JSON.stringify(unchangedIds) === JSON.stringify([...savedInvoice.lineIds].sort((a, b) => a - b))) {
    return { subtotal: savedInvoice.subtotal, discountAmount: savedInvoice.discount_amount,
      taxableAmount: savedInvoice.taxable_amount, cgstTotal: savedInvoice.cgst_amount,
      sgstTotal: savedInvoice.sgst_amount, igstTotal: savedInvoice.igst_amount,
      grandTotal: savedInvoice.grand_total };
  }
  return items.reduce((totals, item) => {
    const line = computeLineAmounts(item, isGst);
    for (const [key, field] of Object.entries({ subtotal: 'gross', discountAmount: 'discountAmount',
      taxableAmount: 'taxable', cgstTotal: 'cgstAmt', sgstTotal: 'sgstAmt', igstTotal: 'igstAmt', grandTotal: 'amount' })) {
      totals[key] = money(totals[key] + line[field]);
    }
    return totals;
  }, { subtotal: 0, discountAmount: 0, taxableAmount: 0, cgstTotal: 0, sgstTotal: 0, igstTotal: 0, grandTotal: 0 });
}
