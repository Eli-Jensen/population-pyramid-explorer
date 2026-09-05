import { describe, expect, test } from 'vitest';
import { GRID, bandFor, bandKind, bandLabel, decadeOf, effectiveEra, percentileOf, tableMetric, tableName } from './bands.ts';
import type { Bands } from './types.ts';

/** A monotone 24-point table q[i] = GRID[i] / 100 (so percentile == 100·d on it). */
const linear = Float64Array.from(GRID, (g) => g / 100);

function bandsOf(tables: Record<string, ArrayLike<number>>): Bands {
  const names = Object.keys(tables);
  const values = new Float32Array(names.length * GRID.length);
  const index: Record<string, [number, number]> = {};
  names.forEach((n, i) => {
    values.set(Float32Array.from(tables[n]), i * GRID.length);
    index[n] = [i * GRID.length, GRID.length];
  });
  return { index, values };
}

describe('bandLabel (bands.band_label twin)', () => {
  test('thresholds in the Python order: extreme ≥ p95 · far ≥ p75 · very_close ≤ p5 · close ≤ p25 · typical', () => {
    expect(bandLabel(0.05, linear)).toBe('very_close'); // == p5
    expect(bandLabel(0.049, linear)).toBe('very_close');
    expect(bandLabel(0.051, linear)).toBe('close');
    expect(bandLabel(0.25, linear)).toBe('close'); // == p25
    expect(bandLabel(0.5, linear)).toBe('typical');
    expect(bandLabel(0.749, linear)).toBe('typical');
    expect(bandLabel(0.75, linear)).toBe('far'); // == p75
    expect(bandLabel(0.95, linear)).toBe('extreme'); // == p95
    expect(bandLabel(5, linear)).toBe('extreme');
    expect(bandLabel(-1, linear)).toBe('very_close');
  });

  test('a degenerate table (all quantiles equal) calls everything at that value extreme, like Python', () => {
    const flat = new Float64Array(GRID.length).fill(0.3);
    expect(bandLabel(0.3, flat)).toBe('extreme');
    expect(bandLabel(0.29, flat)).toBe('very_close');
  });

  test('rejects tables that are not on the 24-point grid', () => {
    expect(() => bandLabel(0.1, new Float32Array(25))).toThrow(/expected 24/);
    expect(() => percentileOf(0.1, new Float32Array(23))).toThrow(/expected 24/);
  });
});

describe('percentileOf (linear interpolation on GRID)', () => {
  test('exact grid points and midpoints', () => {
    for (let i = 0; i < GRID.length; i++) expect(percentileOf(linear[i], linear)).toBeCloseTo(GRID[i], 6);
    expect(percentileOf(0.35, linear)).toBeCloseTo(35, 6); // between p30 and p40
    expect(percentileOf(0.995, linear)).toBeCloseTo(99.5, 5);
  });

  test('clamps outside the table', () => {
    expect(percentileOf(-1, linear)).toBe(0);
    expect(percentileOf(0, linear)).toBe(0);
    expect(percentileOf(1, linear)).toBe(100);
    expect(percentileOf(7, linear)).toBe(100);
  });

  test('plateaus: a value equal to a repeated quantile takes the rightmost grid point of the plateau', () => {
    const q = Float64Array.from(linear);
    q[3] = q[4]; // p5 == p10 == 0.10
    expect(percentileOf(0.1, q)).toBeCloseTo(10, 6);
    expect(percentileOf(0.099, q)).toBeLessThan(5);
    expect(Number.isFinite(percentileOf(0.1000001, q))).toBe(true);
  });
});

describe('table selection (PLAN §3.4a)', () => {
  test('era flip J8 and decade key', () => {
    expect(effectiveEra('obs', 2026, 2026)).toBe('obs');
    expect(effectiveEra('obs', 2050, 2026)).toBe('all');
    expect(effectiveEra('all', 2000, 2026)).toBe('all');
    expect(decadeOf(2026)).toBe(2020);
    expect(decadeOf(1950)).toBe(1950);
    expect(decadeOf(2100)).toBe(2100);
  });

  test('table metric: trend@L for motion, blend proxy for path, visual:<model>, else the metric', () => {
    expect(tableMetric({ metric: 'blend', trend: 'motion', L: 10 })).toBe('trend@10');
    expect(tableMetric({ metric: 'l2', trend: 'path', L: 20 })).toBe('blend');
    expect(tableMetric({ metric: 'visual', trend: null, L: 10 }, 'dinov2-base')).toBe('visual:dinov2-base');
    expect(tableMetric({ metric: 'w1bal', trend: null, L: 10 })).toBe('w1bal');
  });

  test('names by kind', () => {
    expect(tableName('same', 'blend', '2', 2026, 'obs')).toBe('same/blend/2/2026');
    expect(tableName('cross', 'trend@10', '1', 2026, 'all')).toBe('cross/trend@10/1/all/2020');
    expect(tableName('best', 'l2', '2', 1999, 'obs')).toBe('best/l2/2/obs/1990');
    expect(bandKind(0)).toBe('same');
    expect(bandKind(-3)).toBe('cross');
  });

  test('bandFor picks same for Δy = 0, cross otherwise, best on request; Δy overrides a wrong same/cross hint', () => {
    const b = bandsOf({
      'same/blend/2/2026': linear,
      'cross/blend/2/obs/2020': Float32Array.from(linear, (v) => 2 * v),
      'best/blend/2/obs/2020': Float32Array.from(linear, (v) => 4 * v),
    });
    expect(bandFor(b, 'blend', '2', 2026, 2026, 'obs', 0.5)).toEqual({ label: 'typical', percentile: 50, table: 'same/blend/2/2026' });
    expect(bandFor(b, 'blend', '2', 2026, 2020, 'obs', 0.5).table).toBe('cross/blend/2/obs/2020');
    expect(bandFor(b, 'blend', '2', 2026, 2020, 'obs', 0.5).percentile).toBeCloseTo(25, 6);
    expect(bandFor(b, 'blend', '2', 2026, 2026, 'obs', 0.5, 'cross').table).toBe('same/blend/2/2026');
    expect(bandFor(b, 'blend', '2', 2026, 2026, 'obs', 1, 'best')).toEqual({ label: 'close', percentile: 25, table: 'best/blend/2/obs/2020' });
  });

  test('no table (bands not loaded, or the cell is absent) → typical placeholder with null percentile', () => {
    const b = bandsOf({ 'same/blend/2/2026': linear });
    expect(bandFor(null, 'blend', '2', 2026, 2026, 'obs', 0.5)).toEqual({ label: 'typical', percentile: null, table: null });
    expect(bandFor(b, 'l2', '2', 2026, 2026, 'obs', 0.5).table).toBeNull();
    expect(bandFor(b, 'blend', '2', 2026, 2026, 'obs', NaN).percentile).toBeNull();
  });
});
