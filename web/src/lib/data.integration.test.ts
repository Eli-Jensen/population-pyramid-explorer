/**
 * Node-side integration test on the COMMITTED web data (`web/public/data/wpp2024/*`):
 *  - reads `shares.*.d16z` from disk, inflates with node:zlib, decodes with math/delta.ts and checks
 *    the spot rows exported by scripts/parity_fixture.py from data/processed/corpus_u16.npy;
 *  - when `DecompressionStream` exists (Node ≥ 18) also runs the real `loadCorpus()` through a
 *    disk-backed fetch and asserts the gzip-stream branch produced identical rows;
 *  - cross-checks year shards, entity shards, totals, bands and one embedding against the corpus.
 * Prints decode timings (the numbers M1's Worker rule is judged on, desktop side).
 */
/// <reference types="node" />
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { gunzipSync } from 'node:zlib';
import { afterAll, beforeAll, describe, expect, test } from 'vitest';
import {
  bandTable,
  configureData,
  corpusPyramid,
  entities,
  entityIndex,
  entityShardPyramid,
  loadBands,
  loadBandsDefault,
  loadCorpus,
  loadEmbedding,
  loadEntityShard,
  loadYearShard,
  meta,
  resetData,
  rowOf,
  yearShardPyramid,
} from './data.ts';
import { decodeBlob } from './math/delta.ts';
import { N_DIMS, ROW_BYTES, U16_TOTAL } from './types.ts';

const publicDir = fileURLToPath(new URL('../../public/', import.meta.url));
const fixturePath = fileURLToPath(new URL('../../../evals/fixtures/parity_500.json', import.meta.url));
const blobPath = publicDir + meta.files.shares_d16z;
const haveData = existsSync(blobPath) && existsSync(fixturePath);

interface SpotRow {
  row: number;
  id: string;
  year: number;
  pop_total: number;
  u16: number[];
}
interface Fixture {
  n_rows: number;
  n_years: number;
  data_hash: string;
  spot: SpotRow[];
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

describe.skipIf(!haveData)('committed web data (Node, from disk)', () => {
  let fixture: Fixture;
  let corpusU16: Uint16Array;
  const timings: Record<string, number> = {};

  beforeAll(() => {
    fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as Fixture;
    configureData({ base: BASE, fetch: diskFetch, gzipStream: typeof DecompressionStream !== 'undefined' });
  });
  afterAll(() => {
    resetData();
    console.log('decode timings (ms):', JSON.stringify(timings));
  });

  test('meta is self-consistent and the fixture was built from the same corpus', () => {
    expect(meta.n_rows).toBe(meta.n_entities * meta.n_years);
    expect(entities.length).toBe(meta.n_entities);
    expect(entities.filter((e) => e.type === 'country').length).toBe(meta.n_countries);
    expect(fixture.n_rows).toBe(meta.n_rows);
    expect(fixture.n_years).toBe(meta.n_years);
    if (meta.verdicts) expect(fixture.data_hash).toBe(meta.verdicts.data_hash);
  });

  test('shares.d16z: gzip magic, zlib inflate, delta decode; spot rows equal corpus_u16.npy', () => {
    const file = readFileSync(blobPath);
    expect(file[0]).toBe(0x1f);
    expect(file[1]).toBe(0x8b);
    expect(file.length).toBeLessThanOrEqual(meta.budgets.shares_d16z ?? Infinity);

    const t0 = performance.now();
    const inflated = gunzipSync(file);
    const t1 = performance.now();
    expect(inflated.length).toBe(meta.n_rows * ROW_BYTES);
    corpusU16 = decodeBlob(new Uint8Array(inflated.buffer, inflated.byteOffset, inflated.length), meta.n_rows, meta.n_years, N_DIMS);
    const t2 = performance.now();
    timings.zlib_gunzip = +(t1 - t0).toFixed(1);
    timings.delta_decode = +(t2 - t1).toFixed(1);

    expect(fixture.spot.length).toBeGreaterThanOrEqual(5);
    for (const s of fixture.spot) {
      const idx = entityIndex(s.id);
      expect(idx, `entity ${s.id}`).toBeGreaterThanOrEqual(0);
      expect(rowOf(idx, s.year)).toBe(s.row);
      const got = Array.from(corpusU16.subarray(s.row * N_DIMS, (s.row + 1) * N_DIMS));
      expect(got, `${s.id} ${s.year} (row ${s.row})`).toEqual(s.u16);
    }
    // every row sums to 65535 (largest-remainder quantisation survived the codec)
    let bad = 0;
    for (let r = 0; r < meta.n_rows; r++) {
      let sum = 0;
      for (let k = 0; k < N_DIMS; k++) sum += corpusU16[r * N_DIMS + k];
      if (sum !== U16_TOTAL) bad++;
    }
    expect(bad).toBe(0);
  });

  test('loadCorpus() through the real fetch/sniff/DecompressionStream path yields the same rows', async () => {
    const t0 = performance.now();
    const c = await loadCorpus();
    timings.loadCorpus_total = +(performance.now() - t0).toFixed(1);
    timings.loadCorpus_decode = +c.source.decodeMs.toFixed(1);
    timings.loadCorpus_path = c.source.path as unknown as number;
    expect(c.source.path).toBe(typeof DecompressionStream === 'undefined' ? 'u16-fallback' : 'gzip-stream');
    expect(c.u16.length).toBe(corpusU16.length);
    expect(c.u16).toEqual(corpusU16);
    expect(c.totals.length).toBe(meta.n_rows);
    for (const s of fixture.spot) expect(c.totals[s.row]).toBeCloseTo(s.pop_total, 2);
  });

  test('shares.u16 fallback file holds the identical rows', () => {
    const raw = readFileSync(publicDir + meta.files.shares_u16);
    expect(raw.length).toBe(meta.n_rows * ROW_BYTES);
    for (const s of fixture.spot) {
      const got = Array.from(new Uint16Array(raw.buffer.slice(raw.byteOffset + s.row * ROW_BYTES, raw.byteOffset + (s.row + 1) * ROW_BYTES)));
      expect(got).toEqual(s.u16);
    }
  });

  test('year shards and entity shards agree with the corpus (spot cells + JPN 2026)', async () => {
    const c = await loadCorpus();
    const cells = [...fixture.spot.map((s) => ({ id: s.id, year: s.year })), { id: 'JPN', year: 2026 }];
    for (const { id, year } of cells) {
      const [ys, es] = await Promise.all([loadYearShard(year), loadEntityShard(id)]);
      expect(ys.n).toBe(meta.n_entities);
      const idx = entityIndex(id);
      const a = yearShardPyramid(ys, idx);
      const b = entityShardPyramid(es, year);
      const k = corpusPyramid(c, idx, year);
      expect(a.shares).toEqual(b.shares);
      expect(a.shares).toEqual(k.shares);
      expect(a.total).toBe(b.total);
      expect(a.total).toBe(k.total);
      expect(a.shares.reduce((x, y) => x + y, 0)).toBeCloseTo(1, 5);
    }
    // entities.pop_2026 (rounded to 3 dp) equals the shipped 2026 total (AMENDMENTS §G) for every
    // entity, within float32 precision of the total (half an ulp ≈ total × 6e-8; World ≈ 8.2e6 → 0.5)
    const ys2026 = await loadYearShard(2026);
    entities.forEach((e, i) => {
      const got = ys2026.totals[i];
      expect(Math.abs(got - e.pop_2026), `${e.id}: shard ${got} vs entities.json ${e.pop_2026}`).toBeLessThanOrEqual(0.0005 + e.pop_2026 * 1.2e-7);
    });
  });

  test('bands: default has same/blend/2/{year} for every year on the 24-point grid; full has more', async () => {
    const [bd, b] = await Promise.all([loadBandsDefault(), loadBands()]);
    const grid = meta.bands_grid.length;
    expect(grid).toBe(24);
    for (let y = 1950; y <= 2100; y++) {
      const t = bandTable(bd, `same/blend/2/${y}`);
      expect(t, `same/blend/2/${y}`).toBeDefined();
      expect(t!.length).toBe(grid);
      for (let i = 1; i < grid; i++) expect(t![i]).toBeGreaterThanOrEqual(t![i - 1]); // quantiles are monotone
    }
    expect(Object.keys(b.index).length).toBeGreaterThan(Object.keys(bd.index).length);
    expect(bandTable(b, 'same/blend/2/2026')).toEqual(bandTable(bd, 'same/blend/2/2026'));
    expect(bandTable(b, 'cross/l2/2/obs/2020')).toBeDefined();
    expect(bandTable(b, 'same/w1/1/2026')).toEqual(bandTable(b, 'same/w1/2/2026')); // sex-blind alias
  });

  test('embedding f16 decodes to finite, roughly unit-norm rows', async () => {
    const model = Object.keys(meta.files.emb)[0];
    if (!model) return;
    const t0 = performance.now();
    const e = await loadEmbedding(model);
    timings[`emb_${model}`] = +(performance.now() - t0).toFixed(1);
    expect(e.values.length).toBe(meta.n_rows * 64);
    for (const row of [0, 1000, meta.n_rows - 1]) {
      let norm = 0;
      for (let k = 0; k < 64; k++) {
        const v = e.values[row * 64 + k];
        expect(Number.isFinite(v)).toBe(true);
        norm += v * v;
      }
      expect(norm).toBeGreaterThan(0);
      expect(norm).toBeLessThan(4); // PCA-64 of an L2-normalised embedding: ≤ 1 up to half-precision noise
    }
  });
});
