/**
 * Fixed symmetric pyramid axis (PLAN §2, entities.py `_axis_pct`).
 *
 * The axis never moves while scrubbing. Default "fit entity" = the smallest of {10, 12, 14, 17} %
 * covering the entity's max single-sex bin over all 151 years (`entities[].axis_pct`, computed at
 * build). Options: "pin 10 %" (clamp + overflow marker for the rare Gulf bulge) and "never clip"
 * (0–17 %). Result cards / compare use max(focal, candidate) with an "axis widened" caption.
 */

import type { AxisPct } from '../types.ts';

export const AXIS_CHOICES: readonly AxisPct[] = [10, 12, 14, 17];
export const AXIS_MAX: AxisPct = 17;
export const AXIS_PIN: AxisPct = 10;
export type AxisMode = 'fit' | 'pin10' | 'never';

/** Largest single bin, in percent of total population (works on 42-vectors, s21s, any shares). */
export function maxBinPct(shares: ArrayLike<number>): number {
  let m = 0;
  for (let i = 0; i < shares.length; i++) if (shares[i] > m) m = shares[i];
  return m * 100;
}

/**
 * Smallest axis choice covering `maxPct` — identical rule to Python's `_axis_pct` (`share*100 <= p`),
 * except that a value beyond 17 % returns 17 instead of raising (the caller then clips).
 */
export function fitAxis(maxPct: number): AxisPct {
  for (const p of AXIS_CHOICES) if (maxPct <= p) return p;
  return AXIS_MAX;
}

export interface AxisChoice {
  axisPct: AxisPct;
  /** true when some bar exceeds the axis and must be clamped (marker shown). */
  clips: boolean;
}

/**
 * Resolve the axis for a view. `fitPct` is the entity's build-time `axis_pct`; `maxPcts` are the
 * max bin percentages of whatever is actually drawn (focal year, overlay partner, …) — pass them so
 * `clips` is right and "never clip" can widen beyond the entity's own fit.
 */
export function axisFor(mode: AxisMode, fitPct: AxisPct, ...maxPcts: number[]): AxisChoice {
  const drawn = maxPcts.length ? Math.max(...maxPcts) : 0;
  if (mode === 'pin10') return { axisPct: AXIS_PIN, clips: drawn > AXIS_PIN };
  if (mode === 'never') return { axisPct: AXIS_MAX, clips: drawn > AXIS_MAX };
  const axisPct = widen(fitPct, fitAxis(drawn));
  return { axisPct, clips: drawn > axisPct };
}

/** The wider of two axis choices (never per-pyramid autoscale, only widening). */
export function widen(a: AxisPct, b: AxisPct): AxisPct {
  return a >= b ? a : b;
}

export interface PairAxis {
  axisPct: AxisPct;
  /** true when the partner forced a wider axis than the focal entity's own fit ("axis widened"). */
  widened: boolean;
}

/** Axis for a focal/candidate pair (result cards, compare page): max of the two fits. */
export function pairAxis(focal: AxisPct, candidate: AxisPct): PairAxis {
  const axisPct = widen(focal, candidate);
  return { axisPct, widened: axisPct !== focal };
}

export interface ClampedBar {
  pct: number; // value to draw
  overflow: boolean; // true when the real value exceeded the axis
}

/** Clamp one bar to the axis (pin mode); `overflow` drives the `▸14.5%` marker. */
export function clampBar(pct: number, axisPct: number): ClampedBar {
  return pct > axisPct ? { pct: axisPct, overflow: true } : { pct, overflow: false };
}

/** Bar length in px for `pct` on an axis of `axisPct` spanning `halfWidthPx` (one side of the centre). */
export function barLength(pct: number, axisPct: number, halfWidthPx: number): number {
  if (axisPct <= 0 || halfWidthPx <= 0) return 0;
  const clamped = Math.min(Math.max(pct, 0), axisPct);
  return (clamped / axisPct) * halfWidthPx;
}

/** Tick values for a symmetric axis (0 … axisPct, step 2 for ≤ 12 %, else step 4 — 17 % ticks at 0,4,8,12,16). */
export function axisTicks(axisPct: AxisPct): number[] {
  const step = axisPct <= 12 ? 2 : 4;
  const ticks: number[] = [];
  for (let t = 0; t <= axisPct; t += step) ticks.push(t);
  return ticks;
}
