/**
 * Cumulative shares — twin of `metrics.cdf_per_sex` / `features.s21` (CONTRACT §1, §4).
 *
 * All inputs are shares of TOTAL population (a 42-vector: male 0..20, female 21..41, or an s21
 * 21-vector). Sums run sequentially left-to-right in float64, like `np.cumsum`.
 */

import { N_BINS, N_DIMS } from '../types.ts';

/** Sequential running sum of `a[0..n)` into `out` (new Float64Array by default). */
export function cumsum(a: ArrayLike<number>, out: Float64Array = new Float64Array(a.length)): Float64Array {
  let acc = 0;
  for (let i = 0; i < a.length; i++) {
    acc += a[i];
    out[i] = acc;
  }
  return out;
}

/** Total-only age distribution: male + female share per bin (21 values). */
export function s21(s42: ArrayLike<number>): Float64Array {
  if (s42.length !== N_DIMS) throw new Error(`s21: expected ${N_DIMS} shares, got ${s42.length}`);
  const out = new Float64Array(N_BINS);
  for (let k = 0; k < N_BINS; k++) out[k] = s42[k] + s42[N_BINS + k];
  return out;
}

/**
 * `cdf_per_sex`: cumulative shares-of-total, per sex for a 42-vector (male CDF in 0..20, female CDF
 * in 21..41 — each ends at that sex's share of the population) or plain cumsum for an s21.
 */
export function cdfPerSex(v: ArrayLike<number>): Float64Array {
  if (v.length === N_BINS) return cumsum(v);
  if (v.length !== N_DIMS) throw new Error(`cdfPerSex: expected ${N_BINS} or ${N_DIMS} values, got ${v.length}`);
  const out = new Float64Array(N_DIMS);
  let m = 0;
  let f = 0;
  for (let k = 0; k < N_BINS; k++) {
    m += v[k];
    f += v[N_BINS + k];
    out[k] = m;
    out[N_BINS + k] = f;
  }
  return out;
}

/** CDF of the total-only distribution (cumsum of s21), 21 values ending at ≈ 1. */
export function cdfTotal(s42: ArrayLike<number>): Float64Array {
  return cumsum(s21(s42));
}

/** Per-sex shares renormalised WITHIN each sex (for the "% of sex" view): each half sums to 1. */
export function normaliseWithinSex(s42: ArrayLike<number>): Float32Array {
  if (s42.length !== N_DIMS) throw new Error(`normaliseWithinSex: expected ${N_DIMS} shares, got ${s42.length}`);
  let m = 0;
  let f = 0;
  for (let k = 0; k < N_BINS; k++) {
    m += s42[k];
    f += s42[N_BINS + k];
  }
  const out = new Float32Array(N_DIMS);
  for (let k = 0; k < N_BINS; k++) {
    out[k] = m > 0 ? s42[k] / m : 0;
    out[N_BINS + k] = f > 0 ? s42[N_BINS + k] / f : 0;
  }
  return out;
}
