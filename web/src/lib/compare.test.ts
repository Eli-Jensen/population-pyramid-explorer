import { describe, expect, it } from 'vitest';
import { entities, idxOf } from './entities.ts';
import { N_DIMS, U16_TOTAL, YEAR_MAX, YEAR_MIN, type Bands } from './types.ts';
import { featureStats, type CorpusView } from './search.ts';
import { compareQuery } from './router.ts';
import { engine } from './engine.ts';
import {
  isConcrete,
  type ConcreteCompare,
  bestYearFor,
  bestYearWindow,
  compareAxis,
  compareBandsDefaultSuffice,
  dyText,
  featureTable,
  formatTableFeature,
  formatZ,
  lockedYears,
  nextYears,
  pairData,
  pairHeadline,
  swapQuery,
  TABLE_FEATURES,
} from './compare.ts';

describe('lockedYears / nextYears', () => {
  it.each([
    ['a', 2026, -18, { ya: 2026, yb: 2008 }],
    ['b', 2008, -18, { ya: 2026, yb: 2008 }],
    ['a', 2030, -18, { ya: 2030, yb: 2012 }],
    ['b', 2000, -18, { ya: 2018, yb: 2000 }],
    ['a', 1950, -18, { ya: 1968, yb: 1950 }], // B would fall below 1950 → both shift, Δ kept
    ['b', 2100, -18, { ya: 2100, yb: 2082 }], // A would pass 2100
    ['a', 2100, 14, { ya: 2086, yb: 2100 }],
    ['b', 1950, 14, { ya: 1950, yb: 1964 }],
    ['a', 1990, 0, { ya: 1990, yb: 1990 }],
    ['a', 2100, -150, { ya: 2100, yb: 1950 }],
    ['b', 2100, -150, { ya: 2100, yb: 1950 }],
  ] as const)('%s → %i with Δ %i', (side, y, offset, want) => {
    const got = lockedYears(side, y, offset);
    expect(got).toEqual(want);
    expect(got.yb - got.ya).toBe(offset);
    expect(got.ya).toBeGreaterThanOrEqual(YEAR_MIN);
    expect(got.yb).toBeLessThanOrEqual(YEAR_MAX);
  });

  it('nextYears: lock off moves one side and clamps; lock on keeps Δ', () => {
    expect(nextYears({ ya: 2026, yb: 2008 }, 'a', 2030, false)).toEqual({ ya: 2030, yb: 2008 });
    expect(nextYears({ ya: 2026, yb: 2008 }, 'b', 2200, false)).toEqual({ ya: 2026, yb: 2100 });
    expect(nextYears({ ya: 2026, yb: 2008 }, 'a', 2030, true)).toEqual({ ya: 2030, yb: 2012 });
    expect(nextYears({ ya: 2026, yb: 2008 }, 'b', 1940.4, true)).toEqual({ ya: 1968, yb: 1950 });
  });
});

describe('compareAxis', () => {
  const flat = new Float32Array(N_DIMS).fill(1 / N_DIMS); // max bin 2.4 %
  it('fit = max of the two fits; widened when B is wider than A', () => {
    expect(compareAxis('fit', 10, 10, flat, flat)).toMatchObject({ axisPct: 10, widened: false, clips: false, aFit: 10 });
    expect(compareAxis('fit', 10, 17, flat, flat)).toMatchObject({ axisPct: 17, widened: true });
    expect(compareAxis('fit', 14, 10, flat, flat)).toMatchObject({ axisPct: 14, widened: false });
  });
  it('a drawn year that overflows widens the fit; pin10 clips instead; never = 17', () => {
    const bulge = new Float32Array(N_DIMS);
    bulge[4] = 0.15; // 15 % in one bin
    expect(compareAxis('fit', 10, 10, bulge, flat)).toMatchObject({ axisPct: 17, widened: true, clips: false });
    expect(compareAxis('pin10', 10, 17, bulge, flat)).toMatchObject({ axisPct: 10, clips: true, widened: false });
    expect(compareAxis('never', 10, 10, flat, flat)).toMatchObject({ axisPct: 17, clips: false, widened: false });
    expect(compareAxis('fit', 10, 10, null, null)).toMatchObject({ axisPct: 10, widened: false });
  });
});

/** Synthetic corpus-shaped view: 3 entities × 151 years, distances supplied by the test. */
function syntheticView(nEnt = 3): CorpusView & { ids: string[] } {
  const nYears = YEAR_MAX - YEAR_MIN + 1;
  const ids = ['A', 'B', 'C'].slice(0, nEnt);
  const nRows = nEnt * nYears;
  const u16 = new Uint16Array(nRows * N_DIMS);
  const totals = new Float32Array(nRows).fill(1000);
  for (let r = 0; r < nRows; r++) u16[r * N_DIMS + (r % N_DIMS)] = U16_TOTAL;
  return {
    ids,
    u16,
    totals,
    nRows,
    nYears,
    entityIdx: (id) => ids.indexOf(id),
    rowOf: (id, year) => {
      const e = ids.indexOf(id);
      return e < 0 || year < YEAR_MIN || year > YEAR_MAX ? -1 : e * nYears + (year - YEAR_MIN);
    },
  };
}

describe('bestYearFor', () => {
  it('argmin over B\'s rows inside the window; boundary flagged; ties by |Δy| then year', () => {
    const view = syntheticView();
    const d = new Float64Array(view.nRows).fill(5);
    const rowB = (y: number) => view.rowOf('B', y);
    d[rowB(2008)] = 0.4346;
    d[rowB(1990)] = 0.9;
    d[rowB(2040)] = 0.1; // a projection — outside the observed window
    const wObs = bestYearWindow(2026, null, 2026, 2023); // → 1950..2026
    expect(wObs).toEqual({ lo: 1950, hi: 2026, minpop: 100 });
    expect(bestYearFor(d, view, 'B', 2026, wObs)).toEqual({ year: 2008, d: 0.4346, dy: -18, boundaryHit: false });
    const wAll = bestYearWindow(2026, 'all', 2026, 2023);
    expect(bestYearFor(d, view, 'B', 2026, wAll)).toMatchObject({ year: 2040, dy: 14, boundaryHit: false });
    // J8: a projected A-year defaults to `all`
    expect(bestYearWindow(2050, null, 2026, 2023).hi).toBe(2100);
    // boundary: the best sits on the era edge
    d[rowB(2026)] = 0.01;
    expect(bestYearFor(d, view, 'B', 2026, wObs)).toMatchObject({ year: 2026, boundaryHit: true });
    // ties: equal d → nearer |Δy| wins, then the earlier year
    const d2 = new Float64Array(view.nRows).fill(5);
    d2[rowB(2000)] = 1;
    d2[rowB(2010)] = 1; // |Δy| 16 vs 26 → 2010
    expect(bestYearFor(d2, view, 'B', 2026, wObs)?.year).toBe(2010);
    d2[rowB(2042)] = 1; // |Δy| 16 too, but outside obs; with `all` the earlier year (2010) wins the tie
    expect(bestYearFor(d2, view, 'B', 2026, wAll)?.year).toBe(2010);
  });
  it('the population floor and non-finite distances exclude years; nothing left → null', () => {
    const view = syntheticView();
    const d = new Float64Array(view.nRows).fill(1);
    view.totals.fill(50); // below the 100k floor
    expect(bestYearFor(d, view, 'B', 2026, bestYearWindow(2026, null, 2026, 2023))).toBeNull();
    view.totals[view.rowOf('B', 1975)] = 500;
    expect(bestYearFor(d, view, 'B', 2026, bestYearWindow(2026, null, 2026, 2023))).toMatchObject({ year: 1975, boundaryHit: true });
    expect(bestYearFor(d, view, 'Z', 2026, bestYearWindow(2026, null, 2026, 2023))).toBeNull();
  });
});

/** A small view over real entities (so `engine.featureStats` finds the reference set): every country of `year` gets a
 *  plausible pyramid; the two members differ by a controlled bulge. */
function realEntitiesView(year: number, extra: Array<{ id: string; year: number; bulge: number }>): CorpusView {
  const nE = entities.length;
  const rows = nE + extra.length;
  const u16 = new Uint16Array(rows * N_DIMS);
  const totals = new Float32Array(rows).fill(50_000);
  const ent = new Int32Array(rows);
  const yr = new Int32Array(rows);
  const fill = (r: number, bulge: number, seed: number) => {
    // 21 bins per sex: a declining profile with a bulge at bin `bulge`; seed shifts the slope a little
    const w = new Float64Array(N_DIMS);
    let s = 0;
    for (let k = 0; k < 21; k++) {
      const v = Math.exp(-k / (6 + (seed % 5))) * (k === bulge ? 1.8 : 1);
      w[k] = v;
      w[21 + k] = v * 1.02;
      s += w[k] + w[21 + k];
    }
    let acc = 0;
    for (let k = 0; k < N_DIMS; k++) {
      const q = Math.round((w[k] / s) * U16_TOTAL);
      u16[r * N_DIMS + k] = q;
      acc += q;
    }
    u16[r * N_DIMS] += U16_TOTAL - acc; // exact sum
  };
  entities.forEach((_, i) => {
    fill(i, 3 + (i % 9), i);
    ent[i] = i;
    yr[i] = year;
  });
  extra.forEach((x, j) => {
    const r = nE + j;
    fill(r, x.bulge, 7);
    ent[r] = idxOf(x.id);
    yr[r] = x.year;
  });
  const key = (e: number, y: number) => `${e}:${y}`;
  const index = new Map<string, number>();
  for (let r = 0; r < rows; r++) index.set(key(ent[r], yr[r]), r);
  return {
    u16,
    totals,
    nRows: nE,
    nYears: 151,
    entityIdx: (id) => idxOf(id),
    rowOf: (id, y) => index.get(key(idxOf(id), y)) ?? -1,
    entityOfRow: (r) => ent[r],
    yearOfRow: (r) => yr[r],
    lagRow: () => -1,
    corpusRow: (r) => ent[r] * 151 + (yr[r] - YEAR_MIN),
  };
}

const concrete = (q: ReturnType<typeof compareQuery>): ConcreteCompare => {
  if (!isConcrete(q)) throw new Error('unresolved best');
  return q;
};

describe('featureTable / pairData (synthetic view, real engine)', () => {
  const view = realEntitiesView(2026, [{ id: 'JPN', year: 2008, bulge: 11 }]);
  const stats = featureStats(view, entities, 2026, 'c', 100);
  const rowA = view.rowOf('KOR', 2026);
  const rowB = view.rowOf('JPN', 2008);

  it('eight rows, z-scores against A\'s year, raw values from each row', () => {
    const t = featureTable(view, rowA, rowB, stats);
    expect(t.map((r) => r.name)).toEqual([...TABLE_FEATURES]);
    for (const r of t) {
      expect(Number.isFinite(r.rawA)).toBe(true);
      expect(Number.isFinite(r.rawB)).toBe(true);
      expect(r.dz).toBeCloseTo(Math.abs(r.zA - r.zB), 12);
    }
    // A's own z-score is its (raw − mean) / sd over the 2026 reference set
    const med = t.find((r) => r.name === 'median_age')!;
    const j = 0; // median_age is NUMERIC_FEATURES[0]
    expect(med.zA).toBeCloseTo((med.rawA - stats.mu[j]) / stats.sd[j], 12);
    // z-scoring both members against the same reference: identical rows → identical z
    const same = featureTable(view, rowA, rowA, stats);
    for (const r of same) expect(r.dz).toBe(0);
  });

  it('pairData: d, band kind by Δy / from=best, explanation identical to engine.explain, delta = B − A', () => {
    const q = concrete(compareQuery('KOR', 2026, 'JPN', 2008, {}, 2026));
    const p = pairData(engine, view, q, null, { currentYear: 2026, lastObserved: 2023 })!;
    expect(p).not.toBeNull();
    expect(p.dy).toBe(-18);
    expect(p.bandKind).toBe('cross');
    expect(p.band).toEqual({ label: 'typical', percentile: null, table: null }); // no bands passed
    expect(Number.isFinite(p.d)).toBe(true);
    expect(p.d).toBeGreaterThan(0);
    // the country-page card's sentences come from the same entry point
    const sq = { id: 'KOR', year: 2026, mode: 'any', era: 'obs', scope: 'all', minpop: 0, metric: 'blend', sex: '2', k: 5, div: 0.5, trend: null, L: 10, currentYear: 2026 } as const;
    const fromCard = engine.explain(view, sq, rowA, rowB, stats);
    expect(p.explanation.because).toBe(fromCard.because);
    expect(p.explanation.differsIn).toBe(fromCard.differsIn);
    expect(p.explanation.w1Sentence).toBe(fromCard.w1Sentence);
    expect(p.explanation.decompositionSentence).toBe(fromCard.decompositionSentence);
    // blend d equals the decomposition's d (the metric is decomposable)
    expect(p.d).toBeCloseTo(p.explanation.decomposition.d, 9);
    expect(p.referenceYear).toBe(2026);
    expect(p.nReference).toBe(stats.rows.length);
    // delta
    expect(p.delta.length).toBe(N_DIMS);
    let sum = 0;
    for (let k = 0; k < N_DIMS; k++) sum += p.delta[k];
    expect(Math.abs(sum)).toBeLessThan(1e-5);
    // from=best → banded against the best null; same year → 'same'
    const pb = pairData(engine, view, { ...q, from: 'best' }, null, { currentYear: 2026, lastObserved: 2023 })!;
    expect(pb.bandKind).toBe('best');
    const ps = pairData(engine, view, concrete(compareQuery('KOR', 2026, 'ITA', 2026, {}, 2026)), null, { currentYear: 2026, lastObserved: 2023 })!;
    expect(ps.bandKind).toBe('same');
    expect(ps.dy).toBe(0);
    // a row the view does not hold → null
    expect(pairData(engine, view, concrete(compareQuery('KOR', 2026, 'ITA', 1990, {}, 2026)), null, { currentYear: 2026, lastObserved: 2023 })).toBeNull();
  });

  it('bands: a same-year blend pair reads its table when present', () => {
    const grid = Float32Array.from({ length: 24 }, (_, i) => i * 0.1); // quantiles 0 … 2.3
    const bands: Bands = { index: { 'same/blend/2/2026': [0, 24] }, values: grid };
    const q = concrete(compareQuery('KOR', 2026, 'ITA', 2026, {}, 2026));
    const p = pairData(engine, view, q, bands, { currentYear: 2026, lastObserved: 2023 })!;
    expect(p.band.table).toBe('same/blend/2/2026');
    expect(p.band.percentile).not.toBeNull();
  });
});

describe('copy + query helpers', () => {
  it('headline uses ≈ for close bands and names the null', () => {
    expect(pairHeadline({ name: 'South Korea', year: 2026 }, { name: 'Japan', year: 2008 }, { label: 'close', percentile: 7, table: 't' }, 'best')).toBe(
      'South Korea 2026 ≈ Japan 2008 (−18 y), closer than 93 % of best-year matches',
    );
    expect(pairHeadline({ name: 'Japan', year: 2026 }, { name: 'Niger', year: 2026 }, { label: 'extreme', percentile: 99.6, table: 't' }, 'same')).toBe(
      'Japan 2026 vs Niger 2026, farther than 99.6 % of random pairs',
    );
    expect(pairHeadline({ name: 'Japan', year: 2026 }, { name: 'Italy', year: 2026 }, { label: 'typical', percentile: null, table: null }, 'same')).toBe('Japan 2026 vs Italy 2026');
    expect(pairHeadline({ name: 'South Korea', year: 2026 }, { name: 'Japan', year: 2008 }, { label: 'typical', percentile: 36, table: 't' }, 'best')).toBe(
      'South Korea 2026 vs Japan 2008 (−18 y), closer than 64 % of best-year matches',
    );
    expect(pairHeadline({ name: 'Japan', year: 2026 }, { name: 'Italy', year: 2026 }, { label: 'typical', percentile: 60, table: 't' }, 'same')).toBe('Japan 2026 vs Italy 2026, farther than 60 % of random pairs');
    expect(dyText(0)).toBe('');
    expect(dyText(14)).toBe('(+14 y)');
  });
  it('swapQuery flips sides and drops from; null while best is unresolved', () => {
    const q = compareQuery('KOR', 2026, 'JPN', 2008, { from: 'best', view: 'diff', unit: 'abs' }, 2026);
    expect(swapQuery(q, 2026)).toMatchObject({ a: 'JPN', ya: 2008, b: 'KOR', yb: 2026, from: null, view: 'diff', unit: 'abs' });
    expect(swapQuery(compareQuery('KOR', 2026, 'JPN', 'best', {}, 2026), 2026)).toBeNull();
  });
  it('compareBandsDefaultSuffice only for same-year blend two-sex pairs not banded against best', () => {
    expect(compareBandsDefaultSuffice({ metric: 'blend', sex: '2', ya: 2026, yb: 2026, from: null })).toBe(true);
    expect(compareBandsDefaultSuffice({ metric: 'blend', sex: '2', ya: 2026, yb: 2008, from: null })).toBe(false);
    expect(compareBandsDefaultSuffice({ metric: 'blend', sex: '2', ya: 2026, yb: 2026, from: 'best' })).toBe(false);
    expect(compareBandsDefaultSuffice({ metric: 'l2', sex: '2', ya: 2026, yb: 2026, from: null })).toBe(false);
    expect(compareBandsDefaultSuffice({ metric: 'blend', sex: '2', ya: 2026, yb: 'best', from: null })).toBe(false);
  });
  it('formatting', () => {
    expect(formatTableFeature('median_age', 47.34)).toBe('47.3 y');
    expect(formatTableFeature('o65', 0.2142)).toBe('21.4 %');
    expect(formatTableFeature('modal_bin', 55)).toBe('55–59');
    expect(formatTableFeature('modal_bin', 100)).toBe('100+');
    expect(formatTableFeature('wa_sex_ratio', NaN)).toBe('n/a');
    expect(formatZ(1.26)).toBe('+1.3σ');
    expect(formatZ(-0.44)).toBe('−0.4σ');
    expect(formatZ(0.02)).toBe('±0.0σ');
    expect(formatZ(NaN)).toBe('n/a');
  });
});
