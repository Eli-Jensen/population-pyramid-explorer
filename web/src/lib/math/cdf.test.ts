import { describe, expect, test } from 'vitest';
import { cdfPerSex, cdfTotal, cumsum, normaliseWithinSex, s21 } from './cdf.ts';

const uniform42 = new Float32Array(42).fill(1 / 42);
const skewed = (() => {
  const v = new Float64Array(42);
  for (let k = 0; k < 21; k++) {
    v[k] = 0.6 / 21; // male 60 %
    v[21 + k] = 0.4 / 21; // female 40 %
  }
  return v;
})();

describe('cdf helpers', () => {
  test.each([
    [[1, 2, 3], [1, 3, 6]],
    [[0.5, 0.5], [0.5, 1]],
    [[], []],
  ])('cumsum(%j) = %j', (input, want) => {
    expect(Array.from(cumsum(input))).toEqual(want);
  });

  test('s21 adds male and female per bin', () => {
    const a = s21(skewed);
    expect(a.length).toBe(21);
    for (const x of a) expect(x).toBeCloseTo(1 / 21, 15);
    expect(() => s21(new Float32Array(21))).toThrow(/expected 42/);
  });

  test('cdfPerSex ends at each sex share of the total (metrics.cdf_per_sex twin)', () => {
    const c = cdfPerSex(skewed);
    expect(c.length).toBe(42);
    expect(c[20]).toBeCloseTo(0.6, 12);
    expect(c[41]).toBeCloseTo(0.4, 12);
    expect(c[0]).toBeCloseTo(0.6 / 21, 15);
    expect(c[21]).toBeCloseTo(0.4 / 21, 15);
    // s21 input → plain cumsum
    const a21 = new Array<number>(21).fill(0);
    a21[0] = 0.25;
    a21[1] = 0.25;
    a21[20] = 0.5;
    const c21 = cdfPerSex(a21);
    expect(c21.length).toBe(21);
    expect(Array.from(c21.subarray(0, 3))).toEqual([0.25, 0.5, 0.5]);
    expect(c21[20]).toBe(1);
    expect(() => cdfPerSex(new Float64Array(5))).toThrow(/expected 21 or 42/);
  });

  test('cdfTotal of a valid pyramid ends at ≈ 1', () => {
    const c = cdfTotal(uniform42);
    expect(c.length).toBe(21);
    expect(c[20]).toBeCloseTo(1, 6);
    expect(c[2]).toBeCloseTo(3 / 21, 6);
  });

  test('normaliseWithinSex makes each half sum to 1 and handles an empty sex', () => {
    const n = normaliseWithinSex(skewed);
    let m = 0;
    let f = 0;
    for (let k = 0; k < 21; k++) {
      m += n[k];
      f += n[21 + k];
    }
    expect(m).toBeCloseTo(1, 6);
    expect(f).toBeCloseTo(1, 6);
    const maleOnly = new Float64Array(42);
    maleOnly[3] = 1;
    const o = normaliseWithinSex(maleOnly);
    expect(o[3]).toBe(1);
    expect(Array.from(o.subarray(21))).toEqual(new Array(21).fill(0));
  });
});
