// Number formatting for the page (pure, en-US, Intl-based). Populations in the corpus are THOUSANDS.

const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const compact2 = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 });

/** Integer with thousands separators: 122427733 → "122,427,733". */
export function fmtInt(n: number): string {
  if (!Number.isFinite(n)) return '—';
  return int.format(Math.round(n));
}

/** Persons from a thousands figure, with separators: 122427.733 → "122,427,733". */
export function fmtPersons(thousands: number): string {
  if (!Number.isFinite(thousands)) return '—';
  return fmtInt(thousands * 1000);
}

/** Compact persons from thousands: 122427.733 → "122.4M"; 108.168 → "108.2K"; 1.2 → "1.2K". */
export function fmtPersonsCompact(thousands: number, digits: 1 | 2 = 1): string {
  if (!Number.isFinite(thousands)) return '—';
  const persons = thousands * 1000;
  return (digits === 2 ? compact2 : compact).format(Math.round(persons));
}

/** Percent from a fraction or a percent value: fmtPct(0.123) → "12.3%"; fmtPct(4.56, 1, true) → "4.6%". */
export function fmtPct(v: number, digits = 1, alreadyPercent = false): string {
  if (!Number.isFinite(v)) return '—';
  const p = alreadyPercent ? v : v * 100;
  return `${p.toFixed(digits)}%`;
}

/** A signed percentage change: 0.0234 → "+2.3%", −0.01 → "−1.0%", 0 → "±0.0%". */
export function fmtSignedPct(fraction: number, digits = 1): string {
  if (!Number.isFinite(fraction)) return '—';
  const p = fraction * 100;
  const r = Number(p.toFixed(digits));
  if (r === 0) return `±${(0).toFixed(digits)}%`;
  return `${r > 0 ? '+' : '−'}${Math.abs(p).toFixed(digits)}%`;
}

/** Years with one decimal: 49.36 → "49.4". */
export function fmtYears(y: number, digits = 1): string {
  if (!Number.isFinite(y)) return '—';
  return y.toFixed(digits);
}

/** Age-band label for bin k (0 → "0–4", 19 → "95–99", 20 → "100+"). */
export function ageLabel(k: number, nBins = 21, width = 5): string {
  const start = k * width;
  return k >= nBins - 1 ? `${start}+` : `${start}–${start + width - 1}`;
}

/** Males per 100 females from two shares; NaN-safe. */
export function sexRatio(male: number, female: number): number {
  return female > 0 ? (male / female) * 100 : NaN;
}

/** "1.06 males per female"-style ratio to two decimals, or "—". */
export function fmtRatio(r: number, digits = 2): string {
  return Number.isFinite(r) ? r.toFixed(digits) : '—';
}
