// Pure geometry + value helpers for Pyramid.svelte (PLAN §2: bars are sex-bin shares of TOTAL population,
// 42 bars sum to 100 %, male left, female right, youngest at the bottom, fixed symmetric axis).
//
// The GEOMETRY of a bar is always its share of total on the fixed axis, whatever the unit toggle says —
// so the shape never changes when the reader switches % of total / absolute / % of sex; only the labels do.

import { N_BINS, N_DIMS } from './types.ts';
import type { Unit } from './router.ts';
import { fmtPct, fmtPersonsCompact } from './format.ts';

export interface BarValue {
  /** Geometry: share of TOTAL population in percent (0–100). */
  pctTotal: number;
  /** Label value in the chosen unit: % of total, persons, or % of own sex. */
  value: number;
}

export interface SideValues {
  male: BarValue[]; // 21, bin 0 first
  female: BarValue[];
  maleShare: number; // Σ male shares of total (0..1)
  femaleShare: number;
}

/** Per-bin values for both sides. `total` is in THOUSANDS. */
export function sideValues(shares: ArrayLike<number>, total: number, unit: Unit): SideValues {
  if (shares.length !== N_DIMS) throw new Error(`sideValues: expected ${N_DIMS} shares, got ${shares.length}`);
  let maleShare = 0;
  let femaleShare = 0;
  for (let k = 0; k < N_BINS; k++) {
    maleShare += shares[k];
    femaleShare += shares[N_BINS + k];
  }
  const conv = (s: number, sexShare: number): number => {
    switch (unit) {
      case 'abs':
        return s * total * 1000;
      case 'pctsex':
        return sexShare > 0 ? (s / sexShare) * 100 : 0;
      default:
        return s * 100;
    }
  };
  const male: BarValue[] = [];
  const female: BarValue[] = [];
  for (let k = 0; k < N_BINS; k++) {
    male.push({ pctTotal: shares[k] * 100, value: conv(shares[k], maleShare) });
    female.push({ pctTotal: shares[N_BINS + k] * 100, value: conv(shares[N_BINS + k], femaleShare) });
  }
  return { male, female, maleShare, femaleShare };
}

/** Bar-end label for a value in the given unit. */
export function barLabel(value: number, unit: Unit): string {
  if (unit === 'abs') return fmtPersonsCompact(value / 1000, value >= 1_000_000 ? 2 : 1);
  return fmtPct(value, 1, true);
}

/** Axis tick label: ticks live in % of total; abs/pctsex re-express them for the reader. */
export function tickLabel(tickPct: number, unit: Unit, total: number, sexShare: number): string {
  if (tickPct === 0) return '0';
  if (unit === 'abs') return fmtPersonsCompact((tickPct / 100) * total);
  if (unit === 'pctsex') return sexShare > 0 ? `${((tickPct / 100 / sexShare) * 100).toFixed(0)}%` : '—';
  return `${tickPct}%`;
}

export const UNIT_LABEL: Record<Unit, string> = { pct: '% of total', abs: 'people', pctsex: '% of sex' };

/**
 * SVG path for a horizontal bar with a 4 px rounded DATA end and a square baseline end (dataviz spec).
 * `side` 'left' grows from x0 leftwards (male), 'right' grows rightwards (female). Zero width → ''.
 */
export function barPath(x0: number, y: number, w: number, h: number, side: 'left' | 'right', r = 4): string {
  if (w <= 0 || h <= 0) return '';
  const rr = Math.min(r, w, h / 2);
  const f = (n: number) => Number(n.toFixed(2));
  if (side === 'right') {
    const x1 = x0 + w;
    return [
      `M${f(x0)} ${f(y)}`,
      `H${f(x1 - rr)}`,
      `a${rr} ${rr} 0 0 1 ${rr} ${rr}`,
      `V${f(y + h - rr)}`,
      `a${rr} ${rr} 0 0 1 -${rr} ${rr}`,
      `H${f(x0)}`,
      'Z',
    ].join('');
  }
  const x1 = x0 - w;
  return [
    `M${f(x0)} ${f(y)}`,
    `H${f(x1 + rr)}`,
    `a${rr} ${rr} 0 0 0 -${rr} ${rr}`,
    `V${f(y + h - rr)}`,
    `a${rr} ${rr} 0 0 0 ${rr} ${rr}`,
    `H${f(x0)}`,
    'Z',
  ].join('');
}

/** Row → y (youngest at the BOTTOM): bin 0 sits in the last row. */
export function rowY(k: number, top: number, rowH: number, nBins = N_BINS): number {
  return top + (nBins - 1 - k) * rowH;
}
