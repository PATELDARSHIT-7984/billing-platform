// Preserve API decimal strings through formatting; Number is only for chart geometry.
const indianInteger = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

export function toPaise(value) {
  if (value == null || !/^-?\d+(\.\d{1,2})?$/.test(String(value))) return null;
  const [whole, fraction = ''] = String(value).replace('-', '').split('.');
  const amount = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  return String(value).startsWith('-') ? -amount : amount;
}

export function formatINR(value, compact = false) {
  const paise = toPaise(value);
  if (paise === null) return '—';
  const absolute = paise < 0n ? -paise : paise;
  const sign = paise < 0n ? '−' : '';
  if (compact && absolute >= 10000000n) {
    const divisor = absolute >= 1000000000n ? 1000000000n : 10000000n;
    const scaled = (absolute * 100n + divisor / 2n) / divisor;
    return `${sign}₹${scaled / 100n}.${String(scaled % 100n).padStart(2, '0')}${divisor === 1000000000n ? 'Cr' : 'L'}`;
  }
  const fraction = String(absolute % 100n).padStart(2, '0');
  return `${sign}₹${indianInteger.format(absolute / 100n)}${compact && fraction === '00' ? '' : `.${fraction}`}`;
}

// Only for chart volume totals/difference, never outstanding balances or profit.
export function chartAmount(values, subtract = []) {
  if ([...values, ...subtract].some((value) => toPaise(value) === null)) return null;
  const total = values.reduce((sum, value) => sum + toPaise(value), 0n)
    - subtract.reduce((sum, value) => sum + toPaise(value), 0n);
  const absolute = total < 0n ? -total : total;
  return `${total < 0n ? '-' : ''}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`;
}

export function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    .format(new Date(`${value}T12:00:00`));
}
