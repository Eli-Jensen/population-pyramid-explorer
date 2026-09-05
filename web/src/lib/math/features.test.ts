/// <reference types="node" />
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, test } from 'vitest';
import { N_BINS, U16_TOTAL } from '../types.ts';
import { FEATURE_NAMES, NUMERIC_FEATURES, features, medianAge, numericVector, stageOf, type Features } from './features.ts';

/** Twin of tests/test_features.py `pyramid`: an age profile split by `maleShare`. */
function pyramid(profile: number[], maleShare = 0.5): Float64Array {
  const total = profile.reduce((a, b) => a + b, 0);
  const out = new Float64Array(42);
  profile.forEach((p, k) => {
    out[k] = (maleShare * p) / total;
    out[21 + k] = ((1 - maleShare) * p) / total;
  });
  return out;
}
const ones = new Array(N_BINS).fill(1);

describe('features — synthetic pyramids (tests/test_features.py twin)', () => {
  test('names and numeric subset', () => {
    expect(FEATURE_NAMES.length).toBe(16);
    expect(NUMERIC_FEATURES.length).toBe(13);
    expect(NUMERIC_FEATURES[12]).toBe('wa_sex_ratio');
    expect(Object.keys(features(pyramid(ones))).sort()).toEqual([...FEATURE_NAMES].sort());
  });

  test('uniform pyramid: median, mean, shares, dependency, stage', () => {
    const f = features(pyramid(ones));
    expect(f.median_age).toBeCloseTo(52.5, 12);
    expect(f.mean_age).toBeCloseTo(52.5, 12);
    expect(f.u15).toBeCloseTo(3 / 21, 12);
    expect(f.wa).toBeCloseTo(10 / 21, 12);
    expect(f.o65).toBeCloseTo(8 / 21, 12);
    expect(f.o80).toBeCloseTo(5 / 21, 12);
    expect(f.total_dep).toBeCloseTo(11 / 10, 12);
    expect(f.child_dep).toBeCloseTo(3 / 10, 12);
    expect(f.old_dep).toBeCloseTo(8 / 10, 12);
    expect(f.base_slope_20).toBeCloseTo(1, 12);
    expect(f.base_slope_10).toBeCloseTo(1, 12);
    expect(f.wa_sex_ratio).toBeCloseTo(1, 12);
    expect(f.modal_bin).toBe(0); // first on ties
    expect(f.stage).toBe('constrictive');
    expect(f.flag_male_skew).toBe(false);
    expect(f.flag_urn).toBe(false);
  });

  test('median interpolation and the 100+ bin as [100, 105)', () => {
    const top = new Float64Array(N_BINS);
    top[N_BINS - 1] = 1;
    expect(medianAge(top)).toBeCloseTo(102.5, 12);
    const two = new Float64Array(N_BINS);
    two[0] = 0.5;
    two[1] = 0.5;
    expect(medianAge(two)).toBeCloseTo(5, 12); // CDF hits 0.5 exactly at the bin edge
    const first = new Float64Array(N_BINS);
    first[0] = 1;
    expect(medianAge(first)).toBeCloseTo(2.5, 12);
    expect(medianAge(new Float64Array(N_BINS))).toBe(100); // all-zero: k clipped to 20, frac 0
    expect(() => medianAge(new Float64Array(5))).toThrow(/expected 21/);
  });

  test('stage rule and flags', () => {
    const young = features(pyramid(ones.map((_, k) => 0.8 ** k)));
    expect(young.stage).toBe('expansive');
    expect(young.median_age).toBeLessThan(25);
    expect(young.base_slope_20).toBeGreaterThan(1);
    const old = features(pyramid([...new Array(10).fill(1), ...new Array(11).fill(3)]));
    expect(old.stage).toBe('constrictive');
    expect(old.flag_urn).toBe(true);
    expect(old.modal_bin).toBeGreaterThanOrEqual(45);
    const mid = features(pyramid([...new Array(12).fill(1), ...new Array(9).fill(0.1)]));
    expect(mid.stage).toBe('stationary');
    expect(mid.flag_urn).toBe(false);
    const gulf = features(pyramid(ones, 0.75));
    expect(gulf.flag_male_skew).toBe(true);
    expect(gulf.wa_sex_ratio).toBeCloseTo(3, 12);
    expect(stageOf(24.999)).toBe('expansive');
    expect(stageOf(25)).toBe('stationary');
    expect(stageOf(39.999)).toBe('stationary');
    expect(stageOf(40)).toBe('constrictive');
  });

  test('zero denominators give NaN like numpy, and NaN never raises a flag', () => {
    const noWa = new Float64Array(42);
    noWa[0] = 0.5;
    noWa[21] = 0.5; // everyone 0–4
    const f = features(noWa);
    expect(Number.isNaN(f.child_dep)).toBe(true);
    expect(Number.isNaN(f.old_dep)).toBe(true);
    expect(Number.isNaN(f.total_dep)).toBe(true);
    expect(Number.isNaN(f.base_slope_20)).toBe(true);
    expect(Number.isNaN(f.wa_sex_ratio)).toBe(true);
    expect(f.flag_male_skew).toBe(false);
    expect(f.stage).toBe('expansive');
    expect(() => features(new Float64Array(21))).toThrow(/expected 42/);
  });

  test('numericVector follows NUMERIC_FEATURES order', () => {
    const f = features(pyramid(ones, 0.75));
    const v = numericVector(f);
    expect(v.length).toBe(13);
    expect(v[0]).toBe(f.median_age);
    expect(v[12]).toBe(f.wa_sex_ratio);
  });
});

// ------------------------------------------------------------------ parity vs Python (500 sampled rows)

interface FixtureRow {
  row: number;
  id: string;
  year: number;
  pop_total: number;
  u16: number[];
  features: Record<string, number | string | boolean | null>;
}
interface Fixture {
  n_rows: number;
  n_years: number;
  n_dims: number;
  u16_total: number;
  seed: number;
  data_hash: string;
  rows: FixtureRow[];
  spot: FixtureRow[];
}

const fixturePath = fileURLToPath(new URL('../../../../evals/fixtures/parity_500.json', import.meta.url));
let fixture: Fixture | null = null;
try {
  fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as Fixture;
} catch {
  fixture = null;
}

const SHARE_FEATURES = ['u15', 'wa', 'o65', 'o80', 'child_dep', 'old_dep', 'total_dep', 'base_slope_20', 'base_slope_10', 'wa_sex_ratio'] as const;

describe.skipIf(!fixture)('features — parity with src/pyramid_explorer/features.py on parity_500.json', () => {
  const rows = fixture?.rows ?? [];

  test('fixture shape', () => {
    expect(rows.length).toBe(500);
    expect(fixture!.n_dims).toBe(42);
    expect(fixture!.u16_total).toBe(U16_TOTAL);
    expect(fixture!.spot.length).toBeGreaterThanOrEqual(5);
  });

  test('Python quantise round trip: every sampled row sums to exactly 65535', () => {
    for (const r of [...rows, ...fixture!.spot]) {
      expect(r.u16.length).toBe(42);
      expect(r.u16.reduce((a, b) => a + b, 0)).toBe(U16_TOTAL);
    }
  });

  test('share-derived features agree to < 1e-6, median/mean age to < 1e-3, stage/flags exactly', () => {
    let worstShare = 0;
    let worstAge = 0;
    for (const r of rows) {
      const shares = new Float32Array(42);
      for (let k = 0; k < 42; k++) shares[k] = r.u16[k] / U16_TOTAL; // exactly the browser dequantisation
      const f = features(shares);
      const py = r.features;
      for (const name of SHARE_FEATURES) {
        const want = py[name];
        const got = f[name];
        if (want === null) {
          expect(Number.isNaN(got), `${r.id} ${r.year} ${name} should be NaN`).toBe(true);
          continue;
        }
        const d = Math.abs(got - (want as number));
        worstShare = Math.max(worstShare, d);
        expect(d, `${r.id} ${r.year} ${name}: js ${got} vs py ${want}`).toBeLessThan(1e-6);
      }
      for (const name of ['median_age', 'mean_age'] as const) {
        const d = Math.abs(f[name] - (py[name] as number));
        worstAge = Math.max(worstAge, d);
        expect(d, `${r.id} ${r.year} ${name}: js ${f[name]} vs py ${py[name]}`).toBeLessThan(1e-3);
      }
      expect(f.modal_bin, `${r.id} ${r.year} modal_bin`).toBe(py.modal_bin);
      expect(f.stage, `${r.id} ${r.year} stage`).toBe(py.stage);
      expect(f.flag_male_skew, `${r.id} ${r.year} flag_male_skew`).toBe(py.flag_male_skew);
      expect(f.flag_urn, `${r.id} ${r.year} flag_urn`).toBe(py.flag_urn);
    }
    console.log(`features parity over ${rows.length} rows: worst |Δ| shares-derived ${worstShare.toExponential(2)}, ages ${worstAge.toExponential(2)}`);
  });

  test('all three stages and both flags occur in the sample (the parity test is not vacuous)', () => {
    const stages = new Set(rows.map((r) => r.features.stage));
    expect(stages).toEqual(new Set(['expansive', 'stationary', 'constrictive']));
    const feats: Features[] = rows.map((r) => features(new Float32Array(r.u16.map((u) => u / U16_TOTAL))));
    expect(feats.some((f) => f.flag_urn)).toBe(true);
  });
});
