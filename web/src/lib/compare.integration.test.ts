/**
 * Compare page on the COMMITTED web data (skipped when `web/public/data` is absent):
 *  - `/compare/south-korea/2026/japan/best` resolves to Japan 2008 (−18 y) with d 0.4346 — the Python CLI's time-shift
 *    row (`uv run python scripts/query.py KOR 2026 --mode any` → "Japan  best 2008 (-18 y)  d=0.435");
 *  - the pair card's "similar because / differs in" sentences are IDENTICAL whether the pair is reached from the
 *    country page (any-year result on /south-korea/2026, corpus view) or the compare page — on the corpus view AND on
 *    the year-shard view the store builds before the corpus is loaded (yb shard as candidates + ya shard as reference);
 *  - the best-year rule matches `bestYearPerEntity` for every country (same argmin, same tie-breaks).
 */
/// <reference types="node" />
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, test } from 'vitest';
import { configureData, entities, loadBands, loadCorpus, loadYearShard, meta, resetData } from './data.ts';
import { engine } from './engine.ts';
import { explainPair } from './explain.ts';
import { bestYearFor, bestYearWindow, isConcrete, pairData, pairSearchQuery, type ConcreteCompare } from './compare.ts';
import { compareQuery } from './router.ts';
import type { Bands, Corpus } from './types.ts';
import type { CorpusView } from './search.ts';

const publicDir = fileURLToPath(new URL('../../public/', import.meta.url));
const haveData = existsSync(publicDir + meta.files.shares_d16z);
const BASE = '/population-pyramid-explorer/';
function diskFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (!url.startsWith(BASE)) return Promise.resolve(new Response('', { status: 404 }));
  const path = publicDir + url.slice(BASE.length);
  if (!existsSync(path)) return Promise.resolve(new Response('', { status: 404 }));
  const buf = readFileSync(path);
  return Promise.resolve(new Response(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)));
}

const CUR = 2026;
const LAST = meta.last_observed_year;
const sentences = (x: { because: string; differsIn: string; w1Sentence: string; decompositionSentence: string }) => ({
  because: x.because,
  differsIn: x.differsIn,
  w1Sentence: x.w1Sentence,
  decompositionSentence: x.decompositionSentence,
});
const concrete = (q: ReturnType<typeof compareQuery>): ConcreteCompare => {
  if (!isConcrete(q)) throw new Error('unresolved best');
  return q;
};

describe.skipIf(!haveData)('compare page on the committed data', () => {
  let corpus: Corpus;
  let view: CorpusView;
  let bands: Bands;

  beforeAll(async () => {
    configureData({ base: BASE, fetch: diskFetch, gzipStream: false });
    [corpus, bands] = await Promise.all([loadCorpus(), loadBands()]);
    view = engine.fromCorpus(corpus);
  }, 60_000);
  afterAll(() => resetData());

  test('/compare/south-korea/2026/japan/best → Japan 2008 (−18 y), d 0.4346', () => {
    const q = compareQuery('KOR', 2026, 'JPN', 'best', {}, CUR);
    const rowA = view.rowOf('KOR', 2026);
    const d = engine.distances(view, pairSearchQuery(q, CUR), { queryRow: rowA });
    const best = bestYearFor(d, view, 'JPN', 2026, bestYearWindow(2026, q.era, CUR, LAST));
    expect(best).not.toBeNull();
    expect(best!.year).toBe(2008);
    expect(best!.dy).toBe(-18);
    expect(best!.d).toBeCloseTo(0.4346, 4);
    expect(best!.boundaryHit).toBe(false);
    // the resolved URL the store writes
    const resolved = compareQuery('KOR', 2026, 'JPN', best!.year, { ...q, from: 'best' }, CUR);
    expect(resolved).toMatchObject({ yb: 2008, from: 'best' });
  });

  test('best-year rule ≡ the time-shift table for every country (argmin, ties, boundary)', () => {
    const q = compareQuery('KOR', 2026, 'JPN', 'best', {}, CUR);
    const sq = pairSearchQuery(q, CUR);
    const rowA = view.rowOf('KOR', 2026);
    const d = engine.distances(view, sq, { queryRow: rowA });
    const table = engine.bestYearPerEntity(view, { ...sq, scope: 'c', minpop: 100 }, bands, { queryRow: rowA });
    expect(table.length).toBeGreaterThan(150);
    const w = bestYearWindow(2026, q.era, CUR, LAST);
    for (const row of table) {
      const mine = bestYearFor(d, view, row.id, 2026, w)!;
      expect(mine, row.id).not.toBeNull();
      expect([mine.year, mine.dy, mine.boundaryHit], row.id).toEqual([row.bestYear, row.dy, row.boundaryHit]);
      expect(Math.abs(mine.d - row.d), row.id).toBeLessThan(1e-12);
    }
    // era=all admits projections
    const wAll = bestYearWindow(2026, 'all', CUR, LAST);
    const tableAll = engine.bestYearPerEntity(view, { ...sq, era: 'all', scope: 'c', minpop: 100 }, bands, { queryRow: rowA });
    const deu = tableAll.find((r) => r.id === 'DEU')!;
    expect(bestYearFor(d, view, 'DEU', 2026, wAll)!.year).toBe(deu.bestYear);
  });

  test('pair sentences: country page (any-year result) ≡ compare page (corpus) ≡ compare page (year shards)', async () => {
    const q = concrete(compareQuery('KOR', 2026, 'JPN', 2008, { from: 'best' }, CUR));
    const opts = { currentYear: CUR, lastObserved: LAST };
    // country page: the any-year result card explains (KOR 2026, JPN 2008) on the corpus view via explainPair
    const card = explainPair(view, { metric: 'blend', sex: '2', year: 2026 }, view.rowOf('KOR', 2026), view.rowOf('JPN', 2008), meta.sigma);
    // compare page with the corpus loaded
    const onCorpus = pairData(engine, view, q, bands, opts)!;
    expect(sentences(onCorpus.explanation)).toEqual(sentences(card));
    // compare page before the corpus: yb shard = candidates, ya shard = z-score reference (what the store builds)
    const [s2008, s2026] = await Promise.all([loadYearShard(2008), loadYearShard(2026)]);
    const shardView = engine.fromShards(s2008, [s2026]);
    const onShards = pairData(engine, shardView, q, bands, opts)!;
    expect(sentences(onShards.explanation)).toEqual(sentences(card));
    expect(sentences(onShards.explanation)).toMatchInlineSnapshot(`
      {
        "because": "Alike in modal age bin (55–59 vs 55–59) and 65+ share (21.4 % vs 22.3 %).",
        "decompositionSentence": "Shape distance 0.43 = bin-by-bin 0.26 + age-shift 0.17; largest bin gaps M 50-54, M 0-4, F 50-54.",
        "differsIn": "Differs most in base slope (0–4 vs 20–24) (0.48 vs 0.81).",
        "w1Sentence": "2.61 years of average age movement separate them.",
      }
    `);
    // d, Δy, band from the best-year null; z-scores against the 2026 country set (199 incl. Korea) on both views
    for (const p of [onCorpus, onShards]) {
      expect(p.d).toBeCloseTo(0.4346, 4);
      expect(p.dy).toBe(-18);
      expect(p.bandKind).toBe('best');
      expect(p.band.table).toBe('best/blend/2/obs/2020');
      expect(p.band.percentile).not.toBeNull();
      expect(p.referenceYear).toBe(2026);
      expect(p.nReference).toBe(199);
      expect(p.features.map((f) => f.name)).toEqual(['median_age', 'u15', 'wa', 'o65', 'total_dep', 'base_slope_20', 'wa_sex_ratio', 'modal_bin']);
    }
    expect(onShards.d).toBeCloseTo(onCorpus.d, 12);
    for (let i = 0; i < onCorpus.features.length; i++) {
      expect(onShards.features[i].zA).toBeCloseTo(onCorpus.features[i].zA, 10);
      expect(onShards.features[i].zB).toBeCloseTo(onCorpus.features[i].zB, 10);
    }
    // the feature table carries the sentence's raw values (median age 47.3 vs 44.6 as on the country card)
    const med = onCorpus.features.find((f) => f.name === 'median_age')!;
    expect(med.rawA).toBeCloseTo(47.3, 1);
    expect(med.rawB).toBeCloseTo(44.6, 1);
    // same-year pair reads the same-year table (bands_default territory)
    const ita = pairData(engine, view, concrete(compareQuery('JPN', 2026, 'ITA', 2026, {}, CUR)), bands, opts)!;
    expect(ita.bandKind).toBe('same');
    expect(ita.band.table).toBe('same/blend/2/2026');
    expect(ita.explanation.because).toBe('Alike in working-age sex ratio (1.03 vs 1.02) and base slope (0–4 vs 20–24) (0.63 vs 0.64).');
  });

  test('a non-decomposable metric states d under that metric and the split under blend', () => {
    const q = concrete(compareQuery('KOR', 2026, 'JPN', 2008, { metric: 'hel' }, CUR));
    const p = pairData(engine, view, q, bands, { currentYear: CUR, lastObserved: LAST })!;
    expect(p.metric).toBe('hel');
    expect(p.explanation.decomposition.metric).toBe('blend');
    expect(p.d).not.toBeCloseTo(p.explanation.decomposition.d, 3);
    expect(p.band.table).toBe('cross/hel/2/obs/2020');
    expect(entities.find((e) => e.id === 'JPN')!.slug).toBe('japan');
  });
});
