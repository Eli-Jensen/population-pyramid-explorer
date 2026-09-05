// outcomes.ts on synthetic series (no .ecz needed: an EconData is assembled by hand).
import { describe, expect, it } from 'vitest';
import type { EconData, RawInstrument } from '../econ.ts';
import { cohortOutcomes, fmtMultiple, fmtPctYr, fundCaption, quantile } from './outcomes.ts';

const Y0 = 1980;
const Y1 = 2024;
const NY = Y1 - Y0 + 1;
const levels = (from: number, to: number, rate: number) => ({ from_year: from, levels: Array.from({ length: to - from + 1 }, (_, i) => Math.pow(1 + rate, i)) });

/** ids grow at `rates[i]` %/yr from 1000; `lastYear[i]` truncates a series; instruments optional. */
function synth(rates: number[], lastYear: number[] = [], instruments: Record<string, RawInstrument[]> = {}): EconData {
  const ids = rates.map((_, i) => `C${i}`);
  const n = ids.length * NY;
  const gdppc = new Float32Array(n).fill(NaN);
  ids.forEach((_, i) => {
    const last = lastYear[i] ?? Y1;
    for (let y = Y0; y <= last; y++) gdppc[i * NY + (y - Y0)] = 1000 * Math.pow(1 + rates[i]! / 100, y - Y0);
  });
  const header = { version: 1, year_min: Y0, year_max: Y1, ids, instruments, benchmark: { vt: levels(1996, 2024, 0.06), vt_first_bar: '2008-06-24', proxy_until_year: 2008 } };
  return { header, yearMin: Y0, yearMax: Y1, nYears: NY, ids, gdppc, growth: new Float32Array(n).fill(NaN), growth10Shipped: null, tfr: new Float32Array(n).fill(NaN), income: new Uint8Array(n), stage: new Uint8Array(n), index: new Map(ids.map((id, i) => [id, i])) };
}

describe('outcomes.ts', () => {
  it('quantile interpolates', () => {
    expect(quantile([], 0.5)).toBeNull();
    expect(quantile([1], 0.5)).toBe(1);
    expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5);
    expect(quantile([1, 2, 3, 4], 0.25)).toBe(1.75);
  });

  it('20-year CAGR distribution: median / IQR, focal rank, n and the no-window count', () => {
    const e = synth([1, 2, 3, 4, 5]);
    const matches = e.ids.map((iso3) => ({ iso3, year: 1990 }));
    const o = cohortOutcomes(e, matches.slice(0, 4), { iso3: 'C4', year: 1990 });
    expect(o.n).toBe(4);
    expect(o.nMatches).toBe(4);
    expect(o.points.map((p) => Math.round(p.pctPerYear))).toEqual([1, 2, 3, 4]);
    expect(o.median).toBeCloseTo(2.5, 5);
    expect(o.q1).toBeCloseTo(1.75, 5);
    expect(o.q3).toBeCloseTo(3.25, 5);
    expect(o.focal?.pctPerYear).toBeCloseTo(5, 5);
    expect(o.focalRank).toBe(1); // highest growth
    expect(o.points[0]).toMatchObject({ toYear: 2010, years: 20, clipped: false, rank: 1 });
    // a 2010 match has only 14 years of data → clipped; a 2020 match has 4 < minYears → dropped
    const o2 = cohortOutcomes(e, [{ iso3: 'C0', year: 2010 }, { iso3: 'C1', year: 2020 }], null);
    expect(o2.n).toBe(1);
    expect(o2.nNoWindow).toBe(1);
    expect(o2.points[0]).toMatchObject({ clipped: true, years: 14 });
    expect(o2.focal).toBeNull();
    expect(o2.focalRank).toBeNull();
  });

  it('index-return strip only where a fund existed at the match year; the too-few caption below 10', () => {
    const inst: Record<string, RawInstrument[]> = {
      C0: [{ ticker: 'AAA', issuer: 'x', inception: '1996-03-12', status: 'live', delisted: null, annual: levels(1996, 2024, 0.08) }],
      C1: [{ ticker: 'BBB', issuer: 'x', inception: '2013-04-02', status: 'liquidated', delisted: '2024-03-25', annual: levels(2013, 2023, -0.05) }],
    };
    const e = synth([1, 2, 3], [], inst);
    const o = cohortOutcomes(e, [{ iso3: 'C0', year: 2000 }, { iso3: 'C1', year: 2000 }, { iso3: 'C2', year: 2000 }], null);
    expect(o.nWithFund).toBe(1); // BBB did not exist in 2000; C2 has no fund
    expect(o.funds[0]).toMatchObject({ ticker: 'AAA', iso3: 'C0' });
    expect(o.funds[0]!.window).toMatchObject({ y1: 2000, y2: 2020, vt: 'vt_proxy' });
    expect(o.funds[0]!.window.r).toBeCloseTo(8, 5);
    expect(o.funds[0]!.window.rVt).toBeCloseTo(6, 5);
    expect(o.tooFewFunds).toBe(true);
    expect(fundCaption(o)).toBe('n = 1 with a fund; too few to conclude');
    expect(fundCaption({ nWithFund: 12, tooFewFunds: false })).toBe('n = 12 with a fund');
    // the liquidated fund counts once it existed at the match year (window to its last level)
    const o3 = cohortOutcomes(e, [{ iso3: 'C1', year: 2015 }], null, { h: 10 });
    expect(o3.nWithFund).toBe(1);
    expect(o3.funds[0]!.status).toBe('liquidated');
    expect(o3.funds[0]!.window).toMatchObject({ y1: 2015, y2: 2023 });
  });

  it('formatters', () => {
    expect(fmtPctYr(3.14159)).toBe('+3.1 %/yr');
    expect(fmtPctYr(-0.05)).toBe('-0.1 %/yr');
    expect(fmtPctYr(null)).toBe('n/a');
    expect(fmtMultiple(2.44)).toBe('2.4×');
    expect(fmtMultiple(11.1)).toBe('11×');
  });
});
