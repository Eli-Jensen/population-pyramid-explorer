/**
 * Node-side parity of the search engine with the Python reference on the COMMITTED web data:
 *  - every case of `evals/fixtures/search_cases.json` (scripts/search_fixture.py, float64 from u16/65535) — ids,
 *    years and rankRaw identical, |Δd| < 1e-6 (measured ~1e-12), band labels identical, percentiles < 1e-6;
 *  - the same cases through year-shard views (same/today modes, lag shards, injected query rows) give the same rows;
 *  - div = 0 ≡ strict, isolation values + percentiles, decompose() + feature z-deltas for the fixed pairs;
 *  - explain sentences pinned by snapshot and identical whether reached from the country page (year shard,
 *    any-year corpus result) or the compare page (two corpus rows);
 *  - timings for the full 42k-row scan + dedupe + MMR (the PLAN §8 Worker rule is judged on these, desktop side).
 *    NOTE: vitest runs test code in a Node `vm` context where typed-array access is ~13× slower than plain V8 —
 *    the hand-written blend scan over 42,280 rows takes ≈ 42 ms here and ≈ 3.2 ms in a plain `node` script
 *    (2026-09-04, M4 Max). Treat the numbers below as an upper bound; the browser sees the plain-V8 figure.
 */
/// <reference types="node" />
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, test } from 'vitest';
import { configureData, entities, loadBands, loadCorpus, loadEmbedding, loadEntityShard, loadYearShard, meta, resetData } from './data.ts';
import { decompose, explainPair, featureDeltas } from './explain.ts';
import {
  bestYearPerEntity,
  candidateMask,
  different,
  distances,
  fromCorpus,
  fromYearShards,
  isolation,
  isolationPercentile,
  lagYears,
  similar,
  type FullView,
  type SearchQuery,
  type SearchResult,
} from './search.ts';
import { GRID } from './bands.ts';
import type { Bands, Corpus, Embedding } from './types.ts';


const publicDir = fileURLToPath(new URL('../../public/', import.meta.url));
const fixturePath = fileURLToPath(new URL('../../../evals/fixtures/search_cases.json', import.meta.url));
const haveData = existsSync(publicDir + meta.files.shares_d16z) && existsSync(fixturePath);

interface FxResult {
  id: string;
  year: number;
  row: number;
  d: number;
  rankRaw: number;
  dy: number;
  band: string;
  percentile: number | null;
  table: string | null;
}
interface FxTimeShift {
  id: string;
  bestYear: number;
  d: number;
  dy: number;
  boundaryHit: boolean;
  band: string;
  percentile: number | null;
}
interface FxQuery {
  id: string;
  year: number;
  mode: SearchQuery['mode'];
  n: number;
  from: number | null;
  to: number | null;
  era: 'obs' | 'all';
  scope: 'c' | 'all';
  minpop: number;
  metric: string;
  sex: '2' | '1';
  k: number;
  div: number;
  trend: null | 'motion' | 'path';
  L: number;
  currentYear: number;
}
interface FxCase {
  name: string;
  query: FxQuery;
  effectiveEra: string;
  tableMetric: string;
  nCandidates: number;
  queryRow: number;
  similar: FxResult[];
  different: FxResult[];
  strict: FxResult[];
  timeShift?: { n: number; rows: FxTimeShift[] };
}
interface FxExplain {
  name: string;
  query: FxQuery;
  cand: { id: string; year: number };
  queryRow: number;
  candRow: number;
  decomposeMetric: string;
  decompose: { d: number; l2Part: number; w1Part: number; w1Years: number; topBinsL2: Array<[number, number]>; topBinsW1: Array<[number, number]> };
  referenceYear: number;
  nReference: number;
  features: Array<{ name: string; zq: number; zc: number; rawQ: number; rawC: number }>;
  alike: string[];
  differs: string;
}
interface Fixture {
  _meta: { grid: number[]; current_year: number; last_observed_year: number; data_hash: string; n_rows: number; visual_model: string };
  cases: FxCase[];
  isolation: { year: number; n: number; top3: string[]; rows: Array<{ id: string; isolation: number; percentile: number; rank: number }> };
  explain: FxExplain[];
}

const BASE = '/population-pyramid-explorer/';
function diskFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (!url.startsWith(BASE)) return Promise.resolve(new Response('', { status: 404 }));
  const path = publicDir + url.slice(BASE.length);
  if (!existsSync(path)) return Promise.resolve(new Response('', { status: 404 }));
  const buf = readFileSync(path);
  return Promise.resolve(new Response(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)));
}

function toQuery(f: FxQuery): SearchQuery {
  const visual = f.metric.startsWith('visual:');
  return {
    id: f.id,
    year: f.year,
    mode: f.mode,
    n: f.n,
    from: f.from ?? undefined,
    to: f.to ?? undefined,
    // the Python CLI has no explicit/default era: `obs` on a projected year means "the J8 default" (→ all)
    era: f.era === 'obs' && f.year > f.currentYear ? 'all' : f.era,
    scope: f.scope,
    minpop: f.minpop,
    metric: (visual ? 'visual' : f.metric) as SearchQuery['metric'],
    sex: f.sex,
    k: f.k,
    div: f.div as SearchQuery['div'],
    trend: f.trend,
    L: f.L as SearchQuery['L'],
    currentYear: f.currentYear,
  };
}

const D_TOL = 1e-6;
let maxAbsDd = 0; // largest |Δd| seen across every fixture row (reported with the timings)

function expectRows(got: SearchResult[], want: FxResult[], view: FullView, label: string) {
  expect(got.map((r) => [r.id, r.year, r.rankRaw]), `${label}: ids/years/ranks`).toEqual(want.map((r) => [r.id, r.year, r.rankRaw]));
  got.forEach((r, i) => {
    const w = want[i];
    maxAbsDd = Math.max(maxAbsDd, Math.abs(r.d - w.d));
    expect(Math.abs(r.d - w.d), `${label} #${i} ${r.id} d`).toBeLessThan(D_TOL);
    expect(r.dy, `${label} #${i} dy`).toBe(w.dy);
    expect(view.corpusRow(r.row), `${label} #${i} corpus row`).toBe(w.row);
    expect(r.band, `${label} #${i} ${r.id} band`).toBe(w.band);
    if (w.percentile === null) expect(r.percentile).toBeNull();
    else expect(Math.abs((r.percentile ?? NaN) - w.percentile), `${label} #${i} percentile`).toBeLessThan(1e-6);
  });
}

describe.skipIf(!haveData)('search engine parity with scripts/search_fixture.py (real corpus)', () => {
  let fx: Fixture;
  let corpus: Corpus;
  let view: FullView;
  let bands: Bands;
  let emb: Embedding;
  const sigma = meta.sigma;
  const timings: Record<string, number> = {};
  const now = () => performance.now();

  beforeAll(async () => {
    fx = JSON.parse(readFileSync(fixturePath, 'utf8')) as Fixture;
    configureData({ base: BASE, fetch: diskFetch, gzipStream: typeof DecompressionStream !== 'undefined' });
    const t0 = now();
    [corpus, bands] = await Promise.all([loadCorpus(), loadBands()]);
    timings.loadCorpus_and_bands = +(now() - t0).toFixed(1);
    view = fromCorpus(corpus);
    emb = await loadEmbedding(fx._meta.visual_model);
  }, 60_000);
  afterAll(() => {
    resetData();
    console.log('search timings (ms):', JSON.stringify(timings), 'max |Δd| vs fixture:', maxAbsDd.toExponential(2));
  });

  test('fixture matches this build', () => {
    expect(fx._meta.n_rows).toBe(meta.n_rows);
    expect(fx._meta.grid).toEqual(GRID);
    expect(fx._meta.last_observed_year).toBe(meta.last_observed_year);
    if (meta.verdicts) expect(fx._meta.data_hash).toBe(meta.verdicts.data_hash);
    expect(fx.cases.length).toBeGreaterThanOrEqual(12);
  });

  test('every case: candidate count, twins, opposites (MMR) and the strict strip (corpus view)', () => {
    for (const c of fx.cases) {
      const q = toQuery(c.query);
      const opts = { emb: emb.values, visualModel: fx._meta.visual_model };
      const mask = candidateMask(view, entities, q);
      expect(mask.reduce((a, b) => a + b, 0), `${c.name}: candidates`).toBe(c.nCandidates);
      expect(view.rowOf(q.id, q.year)).toBe(c.queryRow);
      expectRows(similar(view, entities, q, sigma, bands, opts), c.similar, view, `${c.name} similar`);
      const { results, strict } = different(view, entities, q, sigma, bands, opts);
      expectRows(results, c.different, view, `${c.name} different`);
      expectRows(strict, c.strict, view, `${c.name} strict`);
      // strict ≡ MMR at div 0
      expectRows(different(view, entities, { ...q, div: 0 }, sigma, bands, opts).results, c.strict, view, `${c.name} div0`);
    }
  });

  test('time-shift tables (best-year per entity, boundary hits, best-null bands)', () => {
    for (const c of fx.cases) {
      if (!c.timeShift) continue;
      const q = toQuery(c.query);
      const ts = bestYearPerEntity(view, entities, q, sigma, bands);
      expect(ts.length, `${c.name}: entities`).toBe(c.timeShift.n);
      const head = ts.slice(0, c.timeShift.rows.length);
      expect(head.map((r) => [r.id, r.bestYear, r.boundaryHit])).toEqual(c.timeShift.rows.map((r) => [r.id, r.bestYear, r.boundaryHit]));
      head.forEach((r, i) => {
        const w = c.timeShift!.rows[i];
        expect(Math.abs(r.d - w.d)).toBeLessThan(D_TOL);
        expect(r.dy).toBe(w.dy);
        expect(r.band).toBe(w.band);
        expect(Math.abs((r.percentile ?? NaN) - (w.percentile ?? NaN))).toBeLessThan(1e-6);
      });
    }
  });

  test('same/today cases through year-shard views (lag shards, injected query rows) give identical rows', async () => {
    for (const c of fx.cases) {
      const q = toQuery(c.query);
      if (q.mode !== 'same' && q.mode !== 'today') continue;
      const tau = q.mode === 'same' ? q.year : q.currentYear;
      const others = lagYears(tau, q.trend, q.L);
      if (q.metric === 'feat' && q.year !== tau) others.push(q.year);
      const shards = await Promise.all([tau, ...others].map((y) => loadYearShard(y)));
      const sv = fromYearShards(shards[0], shards.slice(1));
      if (q.year !== tau) sv.injectEntityRows(await loadEntityShard(q.id), [q.year, ...lagYears(q.year, q.trend, q.L)]);
      const opts = { emb: emb.values, visualModel: fx._meta.visual_model };
      expectRows(similar(sv, entities, q, sigma, bands, opts), c.similar, sv, `${c.name} shard similar`);
      expectRows(different(sv, entities, q, sigma, bands, opts).results, c.different, sv, `${c.name} shard different`);
      // the same distances, row for row, as the corpus view
      const dCorpus = distances(view, q, sigma, opts);
      const dShard = distances(sv, q, sigma, opts);
      for (let r = 0; r < sv.nRows; r++) {
        const a = dShard[r];
        const b = dCorpus[sv.corpusRow(r)];
        if (Number.isNaN(a) || Number.isNaN(b)) expect(Number.isNaN(a)).toBe(Number.isNaN(b));
        else expect(Math.abs(a - b)).toBeLessThan(1e-12);
      }
    }
  });

  test('isolation ranking and percentiles', () => {
    const iso = isolation(view, entities, fx.isolation.year, 'blend', sigma, '2');
    expect(iso.size).toBe(fx.isolation.n);
    expect([...iso.keys()].slice(0, 3)).toEqual(fx.isolation.top3);
    const order = [...iso.keys()];
    for (const w of fx.isolation.rows) {
      expect(Math.abs((iso.get(w.id) ?? NaN) - w.isolation), w.id).toBeLessThan(D_TOL);
      expect(Math.abs((isolationPercentile(iso, w.id) ?? NaN) - w.percentile), w.id).toBeLessThan(1e-6);
      expect(order.indexOf(w.id) + 1).toBe(w.rank);
    }
  });

  test('decompose() and feature z-deltas for the fixed pairs', () => {
    for (const e of fx.explain) {
      const q = toQuery(e.query);
      expect(view.rowOf(e.cand.id, e.cand.year)).toBe(e.candRow);
      const dec = decompose(view, q, e.queryRow, e.candRow, sigma);
      expect(dec.metric, e.name).toBe(e.decomposeMetric);
      for (const k of ['d', 'l2Part', 'w1Part', 'w1Years'] as const) expect(Math.abs(dec[k] - e.decompose[k]), `${e.name} ${k}`).toBeLessThan(D_TOL);
      expect(dec.topBinsL2.map(([k]) => k), `${e.name} topBinsL2`).toEqual(e.decompose.topBinsL2.map(([k]) => k));
      expect(dec.topBinsW1.map(([k]) => k), `${e.name} topBinsW1`).toEqual(e.decompose.topBinsW1.map(([k]) => k));
      dec.topBinsL2.forEach(([, v], i) => expect(Math.abs(v - e.decompose.topBinsL2[i][1])).toBeLessThan(D_TOL));
      dec.topBinsW1.forEach(([, v], i) => expect(Math.abs(v - e.decompose.topBinsW1[i][1])).toBeLessThan(D_TOL));
      const fd = featureDeltas(view, entities, e.queryRow, e.candRow, e.referenceYear, { scope: q.scope, minpop: q.minpop });
      expect(fd.nReference).toBe(e.nReference);
      for (const w of e.features) {
        const got = fd.all.find((f) => f.name === w.name)!;
        expect(Math.abs(got.zq - w.zq), `${e.name} ${w.name} zq`).toBeLessThan(D_TOL);
        expect(Math.abs(got.zc - w.zc), `${e.name} ${w.name} zc`).toBeLessThan(D_TOL);
        expect(Math.abs(got.rawQ - w.rawQ)).toBeLessThan(D_TOL);
        expect(Math.abs(got.rawC - w.rawC)).toBeLessThan(D_TOL);
      }
      expect(fd.alike.map((f) => f.name), e.name).toEqual(e.alike);
      expect(fd.differs[0].name, e.name).toBe(e.differs);
    }
  });

  test('explain sentences: identical from the country page and the compare page; pinned', async () => {
    // JPN–ITA 2026: card on /japan/2026 (year shard) vs /compare/japan/2026/italy/2026 (corpus rows)
    const shard = await loadYearShard(2026);
    const sv = fromYearShards(shard, []);
    const q = { metric: 'blend', sex: '2', year: 2026 } as const;
    const fromCard = explainPair(sv, q, sv.rowOf('JPN', 2026), sv.rowOf('ITA', 2026), sigma);
    const fromCompare = explainPair(view, q, view.rowOf('JPN', 2026), view.rowOf('ITA', 2026), sigma);
    const text = (x: typeof fromCard) => ({ because: x.because, differsIn: x.differsIn, w1Sentence: x.w1Sentence, decompositionSentence: x.decompositionSentence });
    expect(text(fromCard)).toEqual(text(fromCompare));
    expect(text(fromCard)).toMatchInlineSnapshot(`
      {
        "because": "Alike in working-age sex ratio (1.03 vs 1.02) and base slope (0–4 vs 20–24) (0.63 vs 0.64).",
        "decompositionSentence": "Shape distance 0.34 = bin-by-bin 0.21 + age-shift 0.13; largest bin gaps F 75-79, M 75-79, F 60-64.",
        "differsIn": "Differs most in 65+ share (30.2 % vs 25.6 %).",
        "w1Sentence": "Only 1.93 years of average age movement separate them.",
      }
    `);
    // KOR 2026 ≈ JPN 2008: any-year result on /south-korea/2026 vs /compare/south-korea/2026/japan/2008
    const kq = { metric: 'blend', sex: '2', year: 2026 } as const;
    const res = similar(view, entities, { ...toQuery(fx.cases.find((c) => c.name.startsWith('KOR 2026 any'))!.query), k: 20 }, sigma, bands);
    const jpn = res.find((r) => r.id === 'JPN')!;
    expect(jpn.year).toBe(2008);
    const viaResult = explainPair(view, kq, view.rowOf('KOR', 2026), jpn.row, sigma);
    const viaCompare = explainPair(view, kq, view.rowOf('KOR', 2026), view.rowOf('JPN', 2008), sigma);
    expect(text(viaResult)).toEqual(text(viaCompare));
    expect(text(viaResult)).toMatchInlineSnapshot(`
      {
        "because": "Alike in modal age bin (55–59 vs 55–59) and 65+ share (21.4 % vs 22.3 %).",
        "decompositionSentence": "Shape distance 0.43 = bin-by-bin 0.26 + age-shift 0.17; largest bin gaps M 50-54, M 0-4, F 50-54.",
        "differsIn": "Differs most in base slope (0–4 vs 20–24) (0.48 vs 0.81).",
        "w1Sentence": "2.61 years of average age movement separate them.",
      }
    `);
    expect(viaResult.deltas.referenceYear).toBe(2026);
    expect(viaResult.deltas.nReference).toBe(199); // 2026 countries ≥ 100k incl. Korea
  });

  test('timings: JPN 2026 any-year — full 42k scan, dedupe, MMR, time-shift (desktop, Node)', () => {
    const q = toQuery(fx.cases.find((c) => c.name === 'JPN 2026 any era obs')!.query);
    const rep = 5;
    let t = now();
    for (let i = 0; i < rep; i++) distances(view, q, sigma);
    timings.scan_blend_42k = +((now() - t) / rep).toFixed(2);
    t = now();
    for (let i = 0; i < rep; i++) similar(view, entities, q, sigma, bands);
    timings.similar_any = +((now() - t) / rep).toFixed(2);
    t = now();
    for (let i = 0; i < rep; i++) different(view, entities, q, sigma, bands);
    timings.different_any_mmr = +((now() - t) / rep).toFixed(2);
    t = now();
    for (let i = 0; i < rep; i++) bestYearPerEntity(view, entities, q, sigma, bands);
    timings.timeShift_any = +((now() - t) / rep).toFixed(2);
    t = now();
    for (let i = 0; i < rep; i++) similar(view, entities, { ...q, metric: 'feat' }, sigma, bands);
    timings.similar_any_feat = +((now() - t) / rep).toFixed(2);
    t = now();
    for (let i = 0; i < rep; i++) similar(view, entities, { ...q, trend: 'path', L: 10 }, sigma, bands);
    timings.similar_any_path10 = +((now() - t) / rep).toFixed(2);
    t = now();
    for (let i = 0; i < rep; i++) similar(view, entities, { ...q, mode: 'same' }, sigma, bands);
    timings.similar_same_corpusview = +((now() - t) / rep).toFixed(2);
    t = now();
    isolation(view, entities, 2026, 'blend', sigma);
    timings.isolation_2026 = +(now() - t).toFixed(2);
    expect(timings.similar_any).toBeLessThan(2000);
  });

  test('J8 on the real corpus: an explicit era=obs on a projected query year hides projections; the default (all) keeps them', () => {
    const q = toQuery(fx.cases.find((c) => c.name === 'JPN 2050 any (era flips to all, J8)')!.query);
    expect(q.era).toBe('all'); // the Python CLI's obs-on-2050 is the J8 default
    const dflt = similar(view, entities, q, sigma, bands);
    expect(Math.max(...dflt.map((r) => r.year))).toBeGreaterThan(2026);
    const obs = similar(view, entities, { ...q, era: 'obs' }, sigma, bands);
    expect(obs.length).toBe(q.k);
    expect(Math.max(...obs.map((r) => r.year))).toBeLessThanOrEqual(2026);
    expect(obs.map((r) => r.id).slice(0, 3)).toEqual(['ITA', 'PRT', 'GRC']); // browser-verified 2026-09-04
    const ts = bestYearPerEntity(view, entities, { ...q, era: 'obs' }, sigma, bands);
    expect(Math.max(...ts.map((r) => r.bestYear))).toBeLessThanOrEqual(2026);
  });
});
