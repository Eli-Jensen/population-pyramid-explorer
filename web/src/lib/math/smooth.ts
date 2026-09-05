/**
 * Gaussian age-smoothing — twin of `metrics.smooth` (CONTRACT §4, `l2s`).
 *
 * 5-tap kernel `[.054, .242, .399, .242, .054]` applied along age with NEAREST (edge-replicate)
 * padding, per sex. `out[i] = Σ_j K[j] · a[clamp(i + j − 2, 0, n−1)]`, summed j = 0..4 in order,
 * exactly like `sum(KERNEL[j] * np.pad(b, 2, mode='edge')[j:j+21] for j in range(5))`.
 */

import { N_BINS, N_DIMS } from '../types.ts';

export const KERNEL: readonly number[] = [0.054, 0.242, 0.399, 0.242, 0.054];

/** Smooth one age profile of any length with nearest padding. */
export function smooth21(
  a: ArrayLike<number>,
  kernel: readonly number[] = KERNEL,
  out: Float64Array = new Float64Array(a.length),
): Float64Array {
  const n = a.length;
  const half = (kernel.length - 1) >> 1;
  if (kernel.length % 2 !== 1) throw new Error('smooth21: kernel length must be odd');
  for (let i = 0; i < n; i++) {
    let acc = 0;
    for (let j = 0; j < kernel.length; j++) {
      let idx = i + j - half;
      if (idx < 0) idx = 0;
      else if (idx >= n) idx = n - 1;
      acc += kernel[j] * a[idx];
    }
    out[i] = acc;
  }
  return out;
}

/** Smooth a 42-vector per sex (male 0..20 and female 21..41 separately) or an s21 as one profile. */
export function smoothVector(v: ArrayLike<number>, kernel: readonly number[] = KERNEL): Float64Array {
  if (v.length === N_BINS) return smooth21(v, kernel);
  if (v.length !== N_DIMS) throw new Error(`smoothVector: expected ${N_BINS} or ${N_DIMS} values, got ${v.length}`);
  const out = new Float64Array(N_DIMS);
  const male = new Float64Array(N_BINS);
  const female = new Float64Array(N_BINS);
  for (let k = 0; k < N_BINS; k++) {
    male[k] = v[k];
    female[k] = v[N_BINS + k];
  }
  out.set(smooth21(male, kernel), 0);
  out.set(smooth21(female, kernel), N_BINS);
  return out;
}
