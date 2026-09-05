/**
 * Engineered demographic features — TS twin of `src/pyramid_explorer/features.py` (CONTRACT §3).
 *
 * Every feature is a pure function of the 42 shares (male 0..20, female 21..41, summing to 1).
 * Ages are 5-year bins with `age_start = 5k`; the last bin (100+) is treated as [100, 105) for the
 * median / mean interpolation. Arithmetic is float64 and follows numpy's evaluation order so the
 * parity fixture (`evals/fixtures/parity_500.json`) matches to < 1e-6 on shares-derived values.
 *
 * Stage rule (documented median-age thresholds): expansive < 25 ≤ stationary < 40 ≤ constrictive.
 * Flags: `flag_male_skew` = working-age (20–59) sex ratio > 1.3; `flag_urn` = modal bin starts ≥ 45.
 * Undefined ratios (zero denominators) are NaN, exactly like the Python `np.divide(..., where=)`.
 */

import { BIN_WIDTH, N_BINS, N_DIMS } from '../types.ts';
import { s21 } from './cdf.ts';

export const FEATURE_NAMES = [
  'median_age',
  'mean_age',
  'u15',
  'wa',
  'o65',
  'o80',
  'child_dep',
  'old_dep',
  'total_dep',
  'base_slope_20',
  'base_slope_10',
  'modal_bin',
  'wa_sex_ratio',
  'stage',
  'flag_male_skew',
  'flag_urn',
] as const;
export type FeatureName = (typeof FEATURE_NAMES)[number];
export const NUMERIC_FEATURES = FEATURE_NAMES.slice(0, 13) as readonly NumericFeatureName[];
export type NumericFeatureName = Exclude<FeatureName, 'stage' | 'flag_male_skew' | 'flag_urn'>;

export const MEDIAN_THRESHOLDS: readonly [number, number] = [25, 40];
export const MALE_SKEW_RATIO = 1.3;
export const URN_MODAL_AGE = 45;

export type Stage = 'expansive' | 'stationary' | 'constrictive';

export interface Features {
  median_age: number;
  mean_age: number;
  u15: number; // share aged 0–14
  wa: number; // share aged 15–64
  o65: number; // share aged 65+
  o80: number; // share aged 80+
  child_dep: number; // u15 / wa
  old_dep: number; // o65 / wa
  total_dep: number; // (u15 + o65) / wa
  base_slope_20: number; // s21[0] / s21[4]  (0–4 vs 20–24)
  base_slope_10: number; // s21[0] / s21[2]  (0–4 vs 10–14)
  modal_bin: number; // age_start of the largest s21 bin (first on ties)
  wa_sex_ratio: number; // male / female shares aged 20–59
  stage: Stage;
  flag_male_skew: boolean;
  flag_urn: boolean;
}

/** `median_age`: linear interpolation inside the bin where the CDF first reaches 0.5 (100+ as [100,105)). */
export function medianAge(a21: ArrayLike<number>): number {
  if (a21.length !== N_BINS) throw new Error(`medianAge: expected ${N_BINS} bins, got ${a21.length}`);
  // k = number of bins whose running CDF is strictly below 0.5 (np.cumsum then (cdf < 0.5).sum()),
  // clipped to the last bin; `below` = CDF just before bin k.
  let cdf = 0;
  let k = 0;
  let below = 0;
  for (let i = 0; i < N_BINS; i++) {
    cdf += a21[i];
    if (cdf < 0.5) {
      k++;
      below = cdf;
    }
  }
  if (k > N_BINS - 1) {
    k = N_BINS - 1;
    // Python: below = cdf[k−1] for the clipped k (the CDF through bin 19).
    below = 0;
    for (let i = 0; i < k; i++) below += a21[i];
  }
  const width = a21[k];
  let frac = width > 0 ? (0.5 - below) / width : 0;
  if (frac < 0) frac = 0;
  else if (frac > 1) frac = 1;
  return BIN_WIDTH * k + BIN_WIDTH * frac;
}

/** Stage from the median age (`expansive` < 25, `constrictive` ≥ 40, else `stationary`). */
export function stageOf(median: number): Stage {
  if (median < MEDIAN_THRESHOLDS[0]) return 'expansive';
  if (median >= MEDIAN_THRESHOLDS[1]) return 'constrictive';
  return 'stationary';
}

function ratio(num: number, den: number): number {
  return den > 0 ? num / den : NaN;
}

function sumRange(a: ArrayLike<number>, from: number, to: number): number {
  let acc = 0;
  for (let i = from; i < to; i++) acc += a[i];
  return acc;
}

/** All features of one 42-share pyramid (Float32Array from a shard/corpus, or any number array). */
export function features(s42: ArrayLike<number>): Features {
  if (s42.length !== N_DIMS) throw new Error(`features: expected ${N_DIMS} shares, got ${s42.length}`);
  const a = s21(s42);
  const u15 = sumRange(a, 0, 3);
  const wa = sumRange(a, 3, 13);
  const o65 = sumRange(a, 13, N_BINS);
  const o80 = sumRange(a, 16, N_BINS);
  const safeWa = wa > 0 ? wa : NaN;

  const median_age = medianAge(a);
  let mean_age = 0;
  let modal = 0;
  let modalVal = a[0];
  for (let k = 0; k < N_BINS; k++) {
    mean_age += a[k] * (BIN_WIDTH * k + BIN_WIDTH / 2); // midpoints 2.5, 7.5, …, 102.5
    if (a[k] > modalVal) {
      modalVal = a[k];
      modal = k;
    }
  }
  const modal_bin = BIN_WIDTH * modal;
  // working-age sex ratio over bins 4..11 (ages 20–59)
  const wa_sex_ratio = ratio(sumRange(s42, 4, 12), sumRange(s42, N_BINS + 4, N_BINS + 12));

  return {
    median_age,
    mean_age,
    u15,
    wa,
    o65,
    o80,
    child_dep: u15 / safeWa,
    old_dep: o65 / safeWa,
    total_dep: (u15 + o65) / safeWa,
    base_slope_20: ratio(a[0], a[4]),
    base_slope_10: ratio(a[0], a[2]),
    modal_bin,
    wa_sex_ratio,
    stage: stageOf(median_age),
    flag_male_skew: wa_sex_ratio > MALE_SKEW_RATIO, // NaN → false, like numpy
    flag_urn: modal_bin >= URN_MODAL_AGE,
  };
}

/** The 13 numeric features as a vector in `NUMERIC_FEATURES` order (for z-scoring / the `feat` metric). */
export function numericVector(f: Features): Float64Array {
  const out = new Float64Array(NUMERIC_FEATURES.length);
  for (let i = 0; i < NUMERIC_FEATURES.length; i++) out[i] = f[NUMERIC_FEATURES[i]];
  return out;
}
