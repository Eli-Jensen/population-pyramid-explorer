/**
 * Unit tests for the search engine on a SYNTHETIC corpus (6 entities × 151 years, deterministic shapes):
 * mask semantics (tests/test_search.py twin), dedupe + self-exclusion, MMR div = 0 ≡ strict, the trend mask,
 * shard views (lag shards, injected query rows) matching the corpus view. Parity with the Python fixture on the
 * real corpus lives in search.integration.test.ts.
 */
import { describe, expect, test } from 'vitest';
import { meta } from './data.ts';
import {
  DIV_PRESETS,
  ShardView,
  bestYearPerEntity,
  candidateMask,
  defaultQuery,
  different,
  distances,
  featureStats,
  fromCorpus,
  fromYearShard,
  fromYearShards,
  isolation,
  isolationPercentile,
  lagYears,
  similar,
  vectorAt,
  type FullView,
  type SearchQuery,
  search,
} from './search.ts';
import { N_BINS, N_DIMS, N_YEARS, U16_TOTAL, YEAR_MIN, type Corpus, type Entity, type EntityShard, type YearShard } from './types.ts';

// ------------------------------------------------------------------------------------------- synthetic corpus

const IDS = ['E00', 'E01', 'E02', 'E03', 'E04', 'agg-1'];
const ents: Entity[] = IDS.map(
  (id) =>
    ({ id, type: id.startsWith('agg') ? 'aggregate' : 'country', short_name: id, name: id, slug: id.toLowerCase(), aliases: [], pop_2026: 1000 }) as unknown as Entity,
);

/** Smooth age profile whose steepness moves with (entity, year); male share drifts with the entity. Sums to 65535. */
function u16Row(e: number, y: number): Uint16Array {
  const decay = 0.02 + 0.015 * e + 0.0004 * (y - YEAR_MIN);
  const male = 0.48 + 0.01 * e;
  const w = new Float64Array(N_DIMS);
  let s = 0;
  for (let k = 0; k < N_BINS; k++) {
    const a = Math.exp(-decay * k * 5) * (1 + 0.1 * Math.sin(k + e));
    w[k] = male * a;
    w[N_BINS + k] = (1 - male) * a;
    s += w[k] + w[N_BINS + k];
  }
  const out = new Uint16Array(N_DIMS);
  let used = 0;
  const rem: Array<[number, number]> = [];
  for (let k = 0; k < N_DIMS; k++) {
    const v = (w[k] / s) * U16_TOTAL;
    out[k] = Math.floor(v);
    used += out[k];
    rem.push([v - out[k], k]);
  }
  rem.sort((a, b) => b[0] - a[0]);
  for (let i = 0; i < U16_TOTAL - used; i++) out[rem[i][1]]++;
  return out;
}

function synthCorpus(): Corpus {
  const nRows = IDS.length * N_YEARS;
  const u16 = new Uint16Array(nRows * N_DIMS);
  const totals = new Float32Array(nRows);
  for (let e = 0; e < IDS.length; e++) {
    for (let i = 0; i < N_YEARS; i++) {
      const r = e * N_YEARS + i;
      u16.set(u16Row(e, YEAR_MIN + i), r * N_DIMS);
      totals[r] = e === IDS.length - 1 ? 50000 : 1000 + 100 * e; // aggregate big; countries 1000, 1100, …, 1400
    }
  }
  return { nRows, nEntities: IDS.length, nYears: N_YEARS, u16, totals, source: { path: 'u16-fallback', decodeMs: 0, fetchMs: 0 } };
}

function yearShard(c: Corpus, year: number): YearShard {
  const n = c.nEntities;
  const u16 = new Uint16Array(n * N_DIMS);
  const totals = new Float32Array(n);
  for (let e = 0; e < n; e++) {
    const r = e * c.nYears + (year - YEAR_MIN);
    u16.set(c.u16.subarray(r * N_DIMS, (r + 1) * N_DIMS), e * N_DIMS);
    totals[e] = c.totals[r];
  }
  return { year, n, u16, totals };
}

function entityShard(c: Corpus, id: string): EntityShard {
  const e = IDS.indexOf(id);
  return { id, u16: c.u16.slice(e * c.nYears * N_DIMS, (e + 1) * c.nYears * N_DIMS), totals: c.totals.slice(e * c.nYears, (e + 1) * c.nYears) };
}

const corpus = synthCorpus();
const view = fromCorpus(corpus, ents);
const sigma = meta.sigma;
const Q = (id: string, year: number, p: Partial<SearchQuery> = {}) => defaultQuery(id, year, 2026, p);
const yearsOf = (v: FullView, m: Uint8Array) => Array.from(m).flatMap((b, r) => (b ? [v.yearOfRow(r)] : []));
const idsOf = (rs: Array<{ id: string }>) => rs.map((r) => r.id);

// ------------------------------------------------------------------------------------------- views

describe('views', () => {
  test('fromCorpus maps rows ↔ (entity, year) and lags', () => {
    expect(view.nRows).toBe(6 * N_YEARS);
    expect(view.rowOf('E02', 1960)).toBe(2 * N_YEARS + 10);
    expect(view.entityOfRow(2 * N_YEARS + 10)).toBe(2);
    expect(view.yearOfRow(2 * N_YEARS + 10)).toBe(1960);
    expect(view.corpusRow(77)).toBe(77);
    expect(view.lagRow(2 * N_YEARS + 10, 10)).toBe(2 * N_YEARS);
    expect(view.lagRow(2 * N_YEARS + 10, 11)).toBe(-1);
    expect(view.rowOf('nope', 1960)).toBe(-1);
    expect(view.rowOf('E02', 1949)).toBe(-1);
    const v = vectorAt(view, 5);
    expect(v.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 12);
    expect(v[3]).toBe(corpus.u16[5 * N_DIMS + 3] / U16_TOTAL);
  });

  test('ShardView: main shard rows are the candidates, lag shards back lagRow, corpusRow maps back', () => {
    const sv = fromYearShards(yearShard(corpus, 2026), [yearShard(corpus, 2016)], ents);
    expect(sv.nRows).toBe(6);
    expect(sv.years()).toEqual([2026, 2016]);
    expect(sv.rowOf('E03', 2026)).toBe(3);
    expect(sv.rowOf('E03', 2016)).toBe(6 + 3);
    expect(sv.rowOf('E03', 2000)).toBe(-1);
    expect(sv.lagRow(3, 10)).toBe(9);
    expect(sv.lagRow(3, 5)).toBe(-1);
    expect(sv.corpusRow(3)).toBe(view.rowOf('E03', 2026));
    expect(sv.corpusRow(9)).toBe(view.rowOf('E03', 2016));
    expect(vectorAt(sv, 9)).toEqual(vectorAt(view, view.rowOf('E03', 2016)));
    expect(() => fromYearShard(yearShard(corpus, 2026), 2025, ents)).toThrow(/is for 2026/);
    expect(() => new ShardView({ ...yearShard(corpus, 2026), n: 5 }, [], ents)).toThrow(/5 rows for 6 entities/);
  });

  test('injectEntityRows appends missing years of one entity and is idempotent', () => {
    const sv = fromYearShards(yearShard(corpus, 2026), [], ents);
    const es = entityShard(corpus, 'E01');
    sv.injectEntityRows(es, [1990, 1980, 2026]); // 2026 already present → skipped
    expect(sv.u16.length / N_DIMS).toBe(6 + 2);
    expect(sv.rowOf('E01', 1990)).toBe(6);
    expect(sv.rowOf('E01', 1980)).toBe(7);
    expect(sv.lagRow(6, 10)).toBe(7);
    expect(sv.yearOfRow(7)).toBe(1980);
    expect(sv.entityOfRow(7)).toBe(1);
    expect(sv.totals[6]).toBe(corpus.totals[view.rowOf('E01', 1990)]);
    expect(vectorAt(sv, 6)).toEqual(vectorAt(view, view.rowOf('E01', 1990)));
    sv.injectEntityRows(es, [1990]);
    expect(sv.u16.length / N_DIMS).toBe(8);
    expect(() => sv.injectEntityRows({ ...es, id: 'ZZZ' }, [1990])).toThrow(/unknown entity/);
  });

  test('lagYears', () => {
    expect(lagYears(2026, null, 10)).toEqual([]);
    expect(lagYears(2026, 'motion', 10)).toEqual([2016]);
    expect(lagYears(2026, 'path', 20)).toEqual([2021, 2016, 2011, 2006]);
  });
});

// ------------------------------------------------------------------------------------------- mask

describe('candidateMask (tests/test_search.py::test_mask_year_modes_era_scope_minpop_own twin)', () => {
  test('year modes, era, scope, minpop, own entity', () => {
    const m = candidateMask(view, ents, Q('E00', 2026));
    expect(m.reduce((a, b) => a + b, 0)).toBe(4); // 5 countries − own
    expect(new Set(yearsOf(view, m))).toEqual(new Set([2026]));
    expect(Array.from(m).some((b, r) => b && view.entityOfRow(r) === 0)).toBe(false);
    expect(candidateMask(view, ents, Q('E00', 2026, { scope: 'all' })).reduce((a, b) => a + b, 0)).toBe(5);
    expect(candidateMask(view, ents, Q('E00', 2026, { minpop: 1150 })).reduce((a, b) => a + b, 0)).toBe(3); // 1200, 1300, 1400
    expect(candidateMask(view, ents, Q('E00', 2026, { minpop: 1200 })).reduce((a, b) => a + b, 0)).toBe(3); // ≥ is inclusive
    expect(new Set(yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'today' }))))).toEqual(new Set([2026]));
    const near = yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'near', n: 3 })));
    expect(new Set(near)).toEqual(new Set([1997, 1998, 1999, 2000, 2001, 2002, 2003]));
    const rng = yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'range', from: 1960, to: 1962 })));
    expect(new Set(rng)).toEqual(new Set([1960, 1961, 1962]));
    expect(Math.max(...yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'any' }))))).toBe(2026);
    expect(Math.max(...yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'any', era: 'all' }))))).toBe(2100);
    expect(Math.max(...yearsOf(view, candidateMask(view, ents, Q('E00', 2050, { mode: 'any' }))))).toBe(2100); // J8 default: era all
    expect(Q('E00', 2050).era).toBe('all');
    expect(Math.max(...yearsOf(view, candidateMask(view, ents, Q('E00', 2050, { mode: 'any', era: 'obs' }))))).toBe(2026); // explicit obs is honoured
    expect(candidateMask(view, ents, Q('E00', 2050)).reduce((a, b) => a + b, 0)).toBe(4);
    expect(Math.max(...yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'any', currentYear: 2030 }))))).toBe(2030);
    expect(candidateMask(view, ents, Q('E00', 2000, { mode: 'range', from: 2040, to: 2050 })).reduce((a, b) => a + b, 0)).toBe(0);
    // lastObservedYear above currentYear caps by the larger of the two
    expect(Math.max(...yearsOf(view, candidateMask(view, ents, Q('E00', 2000, { mode: 'any' }), 2040)))).toBe(2040);
  });

  test('trend needs year − L ≥ 1950; invalid queries throw', () => {
    const t = candidateMask(view, ents, Q('E00', 2000, { mode: 'any', trend: 'motion', L: 20 }));
    expect(Math.min(...yearsOf(view, t))).toBe(1970);
    expect(() => candidateMask(view, ents, Q('E00', 2000, { mode: 'bogus' as never }))).toThrow(/mode/);
    expect(() => candidateMask(view, ents, Q('E00', 2000, { era: 'x' as never }))).toThrow(/era/);
    expect(() => candidateMask(view, ents, Q('E00', 1955, { trend: 'motion', L: 10 }))).toThrow(/before 1950/);
    expect(() => candidateMask(view, ents, Q('E00', 2000, { trend: 'path', L: 7 as never }))).toThrow(/L must be/);
  });
});

// ------------------------------------------------------------------------------------------- queries

describe('similar / different / bestYearPerEntity on the synthetic corpus', () => {
  test('similar dedupes per entity, excludes own, sorts by d with rankRaw 1..n', () => {
    const res = similar(view, ents, Q('E00', 2000, { mode: 'any', era: 'all', k: 10 }), sigma);
    expect(res.length).toBe(4);
    expect(new Set(idsOf(res)).size).toBe(4);
    expect(idsOf(res)).not.toContain('E00');
    expect(res.map((r) => r.d)).toEqual([...res.map((r) => r.d)].sort((a, b) => a - b));
    expect(res.map((r) => r.rankRaw)).toEqual([1, 2, 3, 4]);
    for (const r of res) {
      expect(r.dy).toBe(r.year - 2000);
      expect(view.yearOfRow(r.row)).toBe(r.year);
      expect(ents[view.entityOfRow(r.row)].id).toBe(r.id);
      expect(r.band).toBe('typical'); // no bands passed → placeholder
      expect(r.percentile).toBeNull();
    }
  });

  test('k caps the twins; a candidate set smaller than k returns all of it', () => {
    expect(similar(view, ents, Q('E00', 2000, { k: 2 }), sigma).length).toBe(2);
    expect(similar(view, ents, Q('E00', 2000, { k: 9 }), sigma).length).toBe(4);
  });

  test('different: div = 0 equals the strict farthest-k; the plain ordering is d descending', () => {
    const q = Q('E00', 2000, { mode: 'any', era: 'all', k: 3, div: 0 });
    const { results, strict } = different(view, ents, q, sigma);
    expect(results).toEqual(strict);
    expect(results.map((r) => r.rankRaw)).toEqual([1, 2, 3]);
    expect(results.map((r) => r.d)).toEqual([...results.map((r) => r.d)].sort((a, b) => b - a));
    // brute force: farthest per entity over the mask
    const d = distances(view, q, sigma, { ents });
    const m = candidateMask(view, ents, q);
    const best = new Map<string, number>();
    for (let r = 0; r < view.nRows; r++) if (m[r]) best.set(ents[view.entityOfRow(r)].id, Math.max(best.get(ents[view.entityOfRow(r)].id) ?? -Infinity, d[r]));
    const expected = [...best.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
    expect(idsOf(results)).toEqual(expected.map((e) => e[0]));
    expect(results.map((r) => r.d)).toEqual(expected.map((e) => e[1]));
  });

  test('different: with diversity the first pick is still the farthest and rankRaw is the plain rank', () => {
    for (const div of Object.values(DIV_PRESETS)) {
      const { results, strict } = different(view, ents, Q('E00', 2000, { mode: 'any', era: 'all', k: 3, div }), sigma);
      expect(results[0]).toEqual(strict[0]);
      expect(results.length).toBe(3);
      expect(new Set(idsOf(results)).size).toBe(3);
      results.forEach((r, i) => expect(r.rankRaw).toBeGreaterThanOrEqual(i + 1));
      expect(results.map((r) => r.rankRaw)).toEqual([...results.map((r) => r.rankRaw)].sort((a, b) => a - b));
    }
    expect(different(view, ents, Q('E00', 2000, { mode: 'range', from: 2040, to: 2050, k: 3 }), sigma).results).toEqual([]);
  });

  test('bestYearPerEntity: one row per other entity, sorted by d, boundaryHit on the era edges', () => {
    const ts = bestYearPerEntity(view, ents, Q('E00', 2000, { era: 'all' }), sigma);
    expect(ts.length).toBe(4);
    expect(ts.map((r) => r.d)).toEqual([...ts.map((r) => r.d)].sort((a, b) => a - b));
    for (const r of ts) {
      expect(r.boundaryHit).toBe(r.bestYear === 1950 || r.bestYear === 2100);
      expect(r.dy).toBe(r.bestYear - 2000);
    }
    // era obs caps the allowed years at 2026, so the edge moves
    const obs = bestYearPerEntity(view, ents, Q('E00', 2000), sigma);
    for (const r of obs) expect(r.boundaryHit).toBe(r.bestYear === 1950 || r.bestYear === 2026);
  });

  test('isolation: mean distance to the k nearest same-year countries ≥ minpop, most isolated first', () => {
    const iso = isolation(view, ents, 2026, 'blend', sigma, '2', { k: 2 });
    expect([...iso.keys()].sort()).toEqual(['E00', 'E01', 'E02', 'E03', 'E04']);
    const vals = [...iso.values()];
    expect(vals).toEqual([...vals].sort((a, b) => b - a));
    const first = [...iso.keys()][0];
    expect(isolationPercentile(iso, first)).toBe(100);
    expect(isolationPercentile(iso, [...iso.keys()][4])).toBe(0);
    expect(isolationPercentile(iso, 'nope')).toBeNull();
    // brute force for E02
    const q = Q('', 2026, { mode: 'same', scope: 'c', era: 'all' });
    const d = distances(view, q, sigma, { ents, queryRow: view.rowOf('E02', 2026) });
    const others = [0, 1, 3, 4].map((e) => d[view.rowOf(IDS[e], 2026)]).sort((a, b) => a - b);
    expect(iso.get('E02')).toBeCloseTo((others[0] + others[1]) / 2, 12);
    expect(isolation(view, ents, 2026, 'l2', sigma, '2', { minpop: 1250 }).size).toBe(2);
  });
});

// ------------------------------------------------------------------------------------------- metrics

describe('distances', () => {
  const qrow = view.rowOf('E00', 2000);

  test('every metric is zero on the query row, finite elsewhere, and sex=1 changes two-sex metrics', () => {
    for (const metric of ['blend', 'l2', 'w1', 'l2s', 'hel', 'feat', 'w1sex', 'w1bal'] as const) {
      const d2 = distances(view, Q('E00', 2000, { metric, mode: 'any', era: 'all' }), sigma, { ents });
      expect(d2.length).toBe(view.nRows);
      expect(d2[qrow]).toBeCloseTo(0, 12);
      expect(Array.from(d2).every(Number.isFinite)).toBe(true);
      const d1 = distances(view, Q('E00', 2000, { metric, mode: 'any', era: 'all', sex: '1' }), sigma, { ents });
      if (metric === 'w1' || metric === 'feat') expect(d1).toEqual(d2);
      else expect(d1[view.rowOf('E03', 2000)]).not.toBeCloseTo(d2[view.rowOf('E03', 2000)], 6);
    }
  });

  test('closed forms: l2, w1 (years), hel, blend = ½ l2/σ + ½ w1s/σ', () => {
    const a = vectorAt(view, qrow);
    const crow = view.rowOf('E03', 2000);
    const b = vectorAt(view, crow);
    let l2 = 0;
    for (let k = 0; k < N_DIMS; k++) l2 += (a[k] - b[k]) ** 2;
    l2 = Math.sqrt(l2);
    let w1s = 0;
    let cm = 0;
    let cf = 0;
    let cmb = 0;
    let cfb = 0;
    for (let k = 0; k < N_BINS; k++) {
      cm += a[k];
      cf += a[N_BINS + k];
      cmb += b[k];
      cfb += b[N_BINS + k];
      w1s += Math.abs(cm - cmb) + Math.abs(cf - cfb);
    }
    w1s *= 5;
    const at = (metric: SearchQuery['metric'], sex: SearchQuery['sex'] = '2') => distances(view, Q('E00', 2000, { metric, sex }), sigma, { ents })[crow];
    expect(at('l2')).toBeCloseTo(l2, 12);
    expect(at('w1sex')).toBeCloseTo(w1s, 12);
    expect(at('blend')).toBeCloseTo(0.5 * (l2 / sigma.l2['2']) + 0.5 * (w1s / sigma.w1sex['2']), 12);
    let hel = 0;
    for (let k = 0; k < N_DIMS; k++) hel += (Math.sqrt(a[k]) - Math.sqrt(b[k])) ** 2;
    expect(at('hel')).toBeCloseTo(Math.sqrt(hel) / Math.SQRT2, 12);
    // w1bal reduces to w1 on s21 when sex = 1 and adds the balance term for sex = 2
    expect(at('w1bal', '1')).toBeCloseTo(at('w1', '1'), 12);
    expect(at('w1bal')).toBeGreaterThan(at('w1'));
  });

  test('trend: Δ over L years; rows whose lag is undefined are NaN; path averages blend over the lags', () => {
    const q = Q('E00', 2000, { mode: 'any', era: 'all', trend: 'motion', L: 10 });
    const d = distances(view, q, sigma, { ents });
    expect(d[qrow]).toBeCloseTo(0, 12);
    expect(Number.isNaN(d[view.rowOf('E03', 1955)])).toBe(true);
    expect(Number.isFinite(d[view.rowOf('E03', 1960)])).toBe(true);
    // closed form for one candidate
    const c = view.rowOf('E03', 1990);
    const dq = vectorAt(view, qrow).map((v, k) => v - vectorAt(view, qrow - 10)[k]);
    const dc = vectorAt(view, c).map((v, k) => v - vectorAt(view, c - 10)[k]);
    let s = 0;
    for (let k = 0; k < N_DIMS; k++) s += (dq[k] - dc[k]) ** 2;
    expect(d[c]).toBeCloseTo(Math.sqrt(s) / sigma['trend@10']['2'], 12);
    // path = mean of blend at lags 0, 5, 10
    const p = distances(view, Q('E00', 2000, { mode: 'any', era: 'all', trend: 'path', L: 10 }), sigma, { ents });
    const blend = (qr: number, cr: number) => distances(view, Q('E00', 2000, { mode: 'any', era: 'all' }), sigma, { ents, queryRow: qr })[cr];
    expect(p[c]).toBeCloseTo((blend(qrow, c) + blend(qrow - 5, c - 5) + blend(qrow - 10, c - 10)) / 3, 12);
    expect(Number.isNaN(p[view.rowOf('E03', 1957)])).toBe(true);
    // similar() with trend never returns a masked / NaN row
    const res = similar(view, ents, Q('E00', 2000, { mode: 'any', era: 'all', trend: 'motion', L: 20, k: 10 }), sigma);
    expect(res.length).toBe(4);
    for (const r of res) expect(r.year).toBeGreaterThanOrEqual(1970);
  });

  test('feat: z-scores against the query year country set (own included); visual needs an embedding', () => {
    const st = featureStats(view, ents, 2000, 'c', 100);
    expect(st.rows.length).toBe(5);
    expect(st.mu.length).toBe(13);
    expect(Array.from(st.sd).every((s) => s > 0)).toBe(true);
    expect(() => featureStats(fromYearShard(yearShard(corpus, 2026), 2026, ents), ents, 2000)).toThrow(/no 2000 shard/);
    expect(() => distances(view, Q('E00', 2000, { metric: 'visual' }), sigma, { ents })).toThrow(/opts.emb/);
    // an embedding equal to the first 64 dims of a padded share vector: cosine distance 0 to itself
    const emb = new Float32Array(view.nRows * 64);
    for (let r = 0; r < view.nRows; r++) for (let k = 0; k < N_DIMS; k++) emb[r * 64 + k] = corpus.u16[r * N_DIMS + k];
    const dv = distances(view, Q('E00', 2000, { metric: 'visual' }), sigma, { ents, emb });
    expect(dv[qrow]).toBeCloseTo(0, 9);
    expect(dv[view.rowOf('E03', 2000)]).toBeGreaterThan(0);
  });
});

// ------------------------------------------------------------------------------------------- shard ≡ corpus

describe('year-shard views reproduce the corpus view', () => {
  const same = (a: Array<{ id: string; year: number; d: number; rankRaw: number }>, b: typeof a) => {
    expect(a.map((r) => [r.id, r.year, r.rankRaw])).toEqual(b.map((r) => [r.id, r.year, r.rankRaw]));
    a.forEach((r, i) => expect(r.d).toBeCloseTo(b[i].d, 12));
  };

  test('same year, every snapshot metric', () => {
    const sv = fromYearShard(yearShard(corpus, 2000), 2000, ents);
    for (const metric of ['blend', 'l2', 'w1', 'l2s', 'hel', 'feat', 'w1sex', 'w1bal'] as const) {
      const q = Q('E00', 2000, { metric, k: 4, div: 2 });
      same(similar(sv, ents, q, sigma), similar(view, ents, q, sigma));
      same(different(sv, ents, q, sigma).results, different(view, ents, q, sigma).results);
    }
  });

  test('trend motion / path with lag shards', () => {
    for (const trend of ['motion', 'path'] as const) {
      const q = Q('E01', 2000, { trend, L: 10, k: 4 });
      const sv = fromYearShards(yearShard(corpus, 2000), lagYears(2000, trend, 10).map((y) => yearShard(corpus, y)), ents);
      same(similar(sv, ents, q, sigma), similar(view, ents, q, sigma));
      same(different(sv, ents, q, sigma).results, different(view, ents, q, sigma).results);
    }
    // a missing lag shard is reported, not silently NaN'd
    const noLag = fromYearShard(yearShard(corpus, 2000), 2000, ents);
    expect(() => similar(noLag, ents, Q('E01', 2000, { trend: 'motion', L: 10 }), sigma)).toThrow(/1990 row of the query/);
  });

  test("today mode from another year: the query's own rows are injected from its entity shard", () => {
    const q = Q('E02', 1990, { mode: 'today', trend: 'motion', L: 10, k: 4 });
    const sv = fromYearShards(yearShard(corpus, 2026), [yearShard(corpus, 2016)], ents);
    expect(() => similar(sv, ents, q, sigma)).toThrow(/not in the view/);
    sv.injectEntityRows(entityShard(corpus, 'E02'), [1990, ...lagYears(1990, 'motion', 10)]);
    same(similar(sv, ents, q, sigma), similar(view, ents, q, sigma));
    const snap = Q('E02', 1990, { mode: 'today', k: 4 });
    same(similar(sv, ents, snap, sigma), similar(view, ents, snap, sigma));
    // feat in today mode needs the reference (query) year as a whole shard
    expect(() => similar(sv, ents, Q('E02', 1990, { mode: 'today', metric: 'feat' }), sigma)).toThrow(/no 1990 shard/);
    const sv2 = fromYearShards(yearShard(corpus, 2026), [yearShard(corpus, 1990)], ents);
    same(similar(sv2, ents, Q('E02', 1990, { mode: 'today', metric: 'feat', k: 4 }), sigma), similar(view, ents, Q('E02', 1990, { mode: 'today', metric: 'feat', k: 4 }), sigma));
  });
});

describe('search (one scan)', () => {
  test('equals similar() + different() + distances() for every mode', () => {
    for (const q of [Q('E00', 2000, { mode: 'any', k: 3 }), Q('E00', 2026), Q('E01', 2000, { mode: 'near', n: 3, k: 2, div: 2 }), Q('E00', 2000, { mode: 'any', k: 3, sex: '1', metric: 'w1' })]) {
      const both = search(view, ents, q, sigma);
      expect(both.similar).toEqual(similar(view, ents, q, sigma));
      const diff = different(view, ents, q, sigma);
      expect(both.different).toEqual(diff.results);
      expect(both.strict).toEqual(diff.strict);
      expect(both.d).toEqual(distances(view, q, sigma, { ents }));
      expect(both.nCandidates).toBe(candidateMask(view, ents, q).reduce((a, b) => a + b, 0));
    }
  });
});
