import { describe, expect, it } from 'vitest';
import { N_BINS, N_DIMS } from './types.ts';
import { barLabel, barPath, rowY, sideValues, tickLabel } from './bars.ts';

/** 42 shares: males 0.6 spread evenly, females 0.4 spread evenly. */
function shares(): Float32Array {
  const s = new Float32Array(N_DIMS);
  for (let k = 0; k < N_BINS; k++) {
    s[k] = 0.6 / N_BINS;
    s[N_BINS + k] = 0.4 / N_BINS;
  }
  return s;
}

describe('sideValues', () => {
  const total = 1000; // thousands → 1,000,000 people
  it('pct: geometry and value are the same share of total', () => {
    const v = sideValues(shares(), total, 'pct');
    expect(v.maleShare).toBeCloseTo(0.6, 5);
    expect(v.femaleShare).toBeCloseTo(0.4, 5);
    expect(v.male[0].pctTotal).toBeCloseTo((0.6 / 21) * 100, 4);
    expect(v.male[0].value).toBeCloseTo(v.male[0].pctTotal, 6);
  });
  it('abs: value is persons; geometry unchanged', () => {
    const v = sideValues(shares(), total, 'abs');
    expect(v.female[3].value).toBeCloseTo((0.4 / 21) * 1_000_000, 0);
    expect(v.female[3].pctTotal).toBeCloseTo((0.4 / 21) * 100, 4);
  });
  it('pctsex: each side sums to 100', () => {
    const v = sideValues(shares(), total, 'pctsex');
    const sum = (a: { value: number }[]) => a.reduce((acc, b) => acc + b.value, 0);
    expect(sum(v.male)).toBeCloseTo(100, 3);
    expect(sum(v.female)).toBeCloseTo(100, 3);
  });
  it('pctsex with an empty sex does not divide by zero', () => {
    const s = new Float32Array(N_DIMS);
    s[0] = 1;
    const v = sideValues(s, 1, 'pctsex');
    expect(v.female.every((b) => b.value === 0)).toBe(true);
    expect(v.male[0].value).toBe(100);
  });
  it('rejects the wrong length', () => {
    expect(() => sideValues(new Float32Array(21), 1, 'pct')).toThrow();
  });
});

describe('labels', () => {
  it.each<[number, 'pct' | 'abs' | 'pctsex', string]>([
    [4.56, 'pct', '4.6%'],
    [4.56, 'pctsex', '4.6%'],
    [1_234_567, 'abs', '1.23M'],
    [12_345, 'abs', '12.3K'],
  ])('barLabel(%s, %s) → %s', (v, u, want) => expect(barLabel(v, u)).toBe(want));

  it('tickLabel per unit', () => {
    expect(tickLabel(0, 'pct', 1000, 0.5)).toBe('0');
    expect(tickLabel(4, 'pct', 1000, 0.5)).toBe('4%');
    expect(tickLabel(4, 'abs', 1000, 0.5)).toBe('40K'); // 4 % of 1,000,000
    expect(tickLabel(4, 'pctsex', 1000, 0.5)).toBe('8%'); // 4 % of total = 8 % of a 50 % sex
    expect(tickLabel(4, 'pctsex', 1000, 0)).toBe('—');
  });
});

describe('geometry', () => {
  it('barPath: right bar starts at x0 and ends at x0+w with a rounded data end', () => {
    const p = barPath(100, 10, 50, 16, 'right');
    expect(p.startsWith('M100 10H146')).toBe(true);
    expect(p).toContain('a4 4 0 0 1 4 4');
    expect(p.endsWith('H100Z')).toBe(true);
  });
  it('barPath: left bar mirrors', () => {
    const p = barPath(100, 10, 50, 16, 'left');
    expect(p.startsWith('M100 10H54')).toBe(true);
    expect(p).toContain('a4 4 0 0 0 -4 4');
  });
  it('barPath: radius shrinks for tiny bars and vanishes for zero width', () => {
    expect(barPath(100, 10, 2, 16, 'right')).toContain('a2 2 0 0 1 2 2');
    expect(barPath(100, 10, 0, 16, 'right')).toBe('');
  });
  it('rowY puts bin 0 at the bottom', () => {
    expect(rowY(0, 10, 20)).toBe(10 + 20 * 20);
    expect(rowY(20, 10, 20)).toBe(10);
  });
});
