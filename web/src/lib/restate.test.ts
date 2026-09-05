import { describe, expect, it } from 'vitest';
import { countryQuery, DEFAULT_SEARCH } from './router.ts';
import {
  anyYearLabel,
  cardTitle,
  dyLabel,
  eraChip,
  fmtMinpop,
  fmtPercentile,
  isolationText,
  nonDefaultControls,
  oppositesHeadline,
  restateQuery,
  strictStrip,
  trendReason,
  yearWindow,
} from './restate.ts';
import type { Features } from './math/features.ts';

const ctx = { name: 'Japan', currentYear: 2026, lastObserved: 2023 };
const q = (year: number, opts: Parameters<typeof countryQuery>[2] = {}) => countryQuery('JPN', year, opts, 2026);

describe('restateQuery', () => {
  it.each([
    [q(2026), '5 most similar and 5 most different pyramids of 2026 · countries ≥ 100k · excluding Japan · Shape'],
    [q(2026, { mode: 'near' }), '5 most similar and 5 most different pyramids of 2016–2026 · countries ≥ 100k · excluding Japan · Shape'],
    [q(2026, { mode: 'near', era: 'all' }), '5 most similar and 5 most different pyramids of 2016–2036 · countries ≥ 100k · excluding Japan · Shape · projections included'],
    [q(2026, { mode: 'any' }), '5 most similar and 5 most different pyramids of any year (1950–2026) · countries ≥ 100k · excluding Japan · Shape'],
    [q(2050, { mode: 'any' }), '5 most similar and 5 most different pyramids of any year (1950–2100) · countries ≥ 100k · excluding Japan · Shape · projections included'],
    [q(2050, { mode: 'any', era: 'obs' }), '5 most similar and 5 most different pyramids of any year (1950–2026) · countries ≥ 100k · excluding Japan · Shape · observed years only'],
    [q(1990, { mode: 'today' }), '5 most similar and 5 most different pyramids of 2026 (today) · countries ≥ 100k · excluding Japan · Shape'],
    [q(2026, { mode: 'range', from: 1990, to: 2000 }), '5 most similar and 5 most different pyramids of 1990–2000 · countries ≥ 100k · excluding Japan · Shape'],
    [q(2026, { scope: 'all', minpop: 0, k: 10, metric: 'w1', sex: '1', div: 2 }), '10 most similar and 10 most different pyramids of 2026 · countries and regions, no population floor · excluding Japan · Age-shift (years) · total only · spread opposites'],
    [q(2026, { trend: 'motion', L: 20, minpop: 1_000_000 }), '5 most similar and 5 most different pyramids of 2026 · countries ≥ 1M · excluding Japan · trend (motion, 20 y)'],
  ])('%o', (query, want) => {
    expect(restateQuery(query, ctx)).toBe(want);
  });
});

describe('yearWindow / anyYearLabel', () => {
  it('caps near/range/any at the era edge for non-projected queries only', () => {
    expect(yearWindow(q(2026, { mode: 'near' }), 2026, 2023)).toMatchObject({ lo: 2016, hi: 2026 });
    expect(yearWindow(q(2050, { mode: 'near' }), 2026, 2023)).toMatchObject({ lo: 2040, hi: 2060 });
    expect(yearWindow(q(2026, { mode: 'range', from: 1990, to: 2100 }), 2026, 2023)).toMatchObject({ lo: 1990, hi: 2026 });
    expect(yearWindow(q(2026, { mode: 'range', from: 1990, to: 2100, era: 'all' }), 2026, 2023)).toMatchObject({ lo: 1990, hi: 2100 });
    expect(yearWindow(q(2026), 2026, 2023)).toEqual({ lo: 2026, hi: 2026, label: '2026' });
  });
  it('the any-year label follows the effective era (J8)', () => {
    expect(anyYearLabel({ year: 2026, era: null }, 2026, 2023)).toBe('Any year (1950–2026)');
    expect(anyYearLabel({ year: 2026, era: 'all' }, 2026, 2023)).toBe('Any year (1950–2100)');
    expect(anyYearLabel({ year: 2050, era: null }, 2026, 2023)).toBe('Any year (1950–2100)');
    expect(anyYearLabel({ year: 2050, era: 'obs' }, 2026, 2023)).toBe('Any year (1950–2026)'); // explicit observed-only on a projected query
    expect(anyYearLabel({ year: 2020, era: null }, 2027, 2023)).toBe('Any year (1950–2027)');
  });
});

describe('eraChip (J8)', () => {
  it('is absent in same-year mode', () => {
    expect(eraChip({ mode: 'same', year: 2026, era: null }, 2026)).toBeNull();
  });
  it('reads "projections hidden (74 years) · include" for an observed query', () => {
    expect(eraChip({ mode: 'any', year: 2026, era: null }, 2026)).toEqual({ text: 'projections hidden (74 years)', action: 'include', target: 'all' });
  });
  it('inverts for a projected query', () => {
    expect(eraChip({ mode: 'any', year: 2050, era: null }, 2026)).toEqual({
      text: 'projections included (query is a projection)',
      action: 'observed only',
      target: 'obs',
    });
    expect(eraChip({ mode: 'any', year: 2050, era: 'obs' }, 2026)).toMatchObject({ text: 'projections hidden (74 years)', target: 'all' });
  });
  it('an observed query that opted in can hide them again', () => {
    expect(eraChip({ mode: 'near', year: 2026, era: 'all' }, 2026)).toEqual({ text: 'projections included', action: 'hide', target: 'obs' });
  });
});

describe('small formatters', () => {
  it('fmtMinpop', () => {
    expect(fmtMinpop(0)).toBe('no floor');
    expect(fmtMinpop(10_000)).toBe('10k');
    expect(fmtMinpop(100_000)).toBe('100k');
    expect(fmtMinpop(1_000_000)).toBe('1M');
    expect(fmtMinpop(2500)).toBe('2,500');
  });
  it('dyLabel / cardTitle', () => {
    expect(dyLabel(0)).toBe('');
    expect(dyLabel(14)).toBe('(+14 y)');
    expect(dyLabel(-21)).toBe('(−21 y)');
    expect(cardTitle('Germany', 2040, 14)).toBe('Germany 2040 (+14 y)');
    expect(cardTitle('Italy', 2026, 0)).toBe('Italy 2026');
  });
  it('fmtPercentile keeps a decimal only in the tails', () => {
    expect(fmtPercentile(99.63)).toBe('99.6 %');
    expect(fmtPercentile(62.4)).toBe('62 %');
    expect(fmtPercentile(0.42)).toBe('0.4 %');
  });
  it('oppositesHeadline / isolationText / strictStrip', () => {
    expect(oppositesHeadline({ name: 'Japan', year: 2026 }, { name: 'Central African Republic', year: 2026 }, 99.6, 198)).toBe(
      'Japan 2026 vs Central African Republic 2026: farther than 99.6 % of random pairs',
    );
    expect(oppositesHeadline({ name: 'Japan', year: 2026 }, { name: 'Niger', year: 2026 }, null, 198)).toBe('Japan 2026 vs Niger 2026: the farthest of 198 candidates');
    expect(isolationText(91.2)).toBe('more isolated than 91 % of countries this year');
    expect(strictStrip(['CAF', 'QAT'], ['CAF', 'QAT'])).toBeNull();
    expect(strictStrip(['CAF', 'QAT', 'OMN'], ['CAF', 'QAT', 'TCD'])).toBe('strictly farthest: CAF, QAT, TCD');
    expect(strictStrip([], [])).toBeNull();
  });
  it('nonDefaultControls lists the deviating keys', () => {
    expect(nonDefaultControls(DEFAULT_SEARCH, DEFAULT_SEARCH)).toEqual([]);
    expect(nonDefaultControls({ ...DEFAULT_SEARCH, k: 10, era: 'all' }, DEFAULT_SEARCH).sort()).toEqual(['era', 'k']);
  });
});

describe('trendReason', () => {
  const f = (u15: number, o65: number, median: number, sr: number): Features => ({
    median_age: median, mean_age: 0, u15, wa: 0, o65, o80: 0, child_dep: 0, old_dep: 0, total_dep: 0,
    base_slope_20: 0, base_slope_10: 0, modal_bin: 0, wa_sex_ratio: sr, stage: 'stationary', flag_male_skew: false, flag_urn: false,
  });
  it('reproduces the CLI line for China 1980→1990 vs Ethiopia 2016→2026', () => {
    const qp = { prev: f(0.353, 0.045, 21.6, 1.05), now: f(0.28, 0.054, 24.7, 1.04) };
    const cp = { prev: f(0.418, 0.031, 17.9, 1.0), now: f(0.38, 0.035, 19.9, 1.0) };
    expect(trendReason(qp, cp)).toBe('U15 −7.3 vs −3.8 pts · 65+ +0.9 vs +0.4 pts · median age +3.1 vs +2.0 y · WA sex ratio −0.01 vs ±0.00');
  });
});
