// Number formatting shared by the econ chunk AND the first-paint table cells (TimeShiftTable, PairCard) — kept free of
// any econ.ts import so the entry chunk never statically reaches into the lazy econ chunk (PLAN §8 budget).

/** Signed %/yr with one decimal, ASCII minus. */
export function fmtPctYr(v: number | null, digits = 1): string {
  if (v === null || !Number.isFinite(v)) return 'n/a';
  const s = v.toFixed(digits);
  return (v >= 0 && !s.startsWith('-') ? '+' : '') + s + ' %/yr';
}

/** "2.4×" style multiple. */
export function fmtMultiple(m: number | null): string {
  if (m === null || !Number.isFinite(m)) return 'n/a';
  return `${m.toFixed(m >= 10 ? 0 : 1)}×`;
}
