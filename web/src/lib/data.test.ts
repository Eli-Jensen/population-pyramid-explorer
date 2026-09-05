/**
 * Unit tests for the three-tier loader against an in-memory synthetic dataset served by a fake
 * fetch: URL construction under BASE_URL, memoisation, shard parsing, the gzip magic-byte sniff,
 * the pre-inflated body branch, the inflated-length check and the `shares.u16` fallback.
 */
/// <reference types="node" />
import { gzipSync } from 'node:zlib';
import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import {
  bandTable,
  configureData,
  corpusPyramid,
  dataUrl,
  entityIndex,
  entityShardPyramid,
  isGzip,
  loadBands,
  loadBandsDefault,
  loadCorpus,
  loadEmbedding,
  loadEntityShard,
  loadFirstPaint,
  loadYearShard,
  parseBands,
  resetData,
  rowOf,
  sharesAt,
  yearShardPyramid,
} from './data.ts';
import { encodeBlobRaw } from './math/delta.ts';
import { f32ToF16 } from './math/f16.ts';
import { N_DIMS, U16_TOTAL, type Entity, type Meta } from './types.ts';

// ------------------------------------------------------------------------------ synthetic dataset

const N_ENT = 3;
const N_Y = 4; // years 1950..1953 (n_years is read from meta, never hardcoded to 151)
const N_ROWS = N_ENT * N_Y;

function u16Row(seed: number): number[] {
  // deterministic row summing to exactly 65535
  const raw = Array.from({ length: N_DIMS }, (_, k) => ((seed * 7919 + k * 104729) % 1000) + 1);
  const sum = raw.reduce((a, b) => a + b, 0);
  const scaled = raw.map((x) => Math.floor((x / sum) * U16_TOTAL));
  let short = U16_TOTAL - scaled.reduce((a, b) => a + b, 0);
  for (let k = 0; short > 0; k = (k + 1) % N_DIMS, short--) scaled[k]++;
  return scaled;
}

const corpusU16 = new Uint16Array(N_ROWS * N_DIMS);
const totals = new Float32Array(N_ROWS);
for (let r = 0; r < N_ROWS; r++) {
  corpusU16.set(u16Row(r + 1), r * N_DIMS);
  totals[r] = 1000 + r * 10.5;
}
corpusU16.fill(0, 0, N_DIMS); // row 0 has zeros …
corpusU16[0] = U16_TOTAL; // … and a 65535, to exercise the modular wrap in the blob

function le16(u: Uint16Array): Uint8Array {
  const out = new Uint8Array(u.length * 2);
  const dv = new DataView(out.buffer);
  u.forEach((v, i) => dv.setUint16(2 * i, v, true));
  return out;
}
function lef32(f: Float32Array): Uint8Array {
  const out = new Uint8Array(f.length * 4);
  const dv = new DataView(out.buffer);
  f.forEach((v, i) => dv.setFloat32(4 * i, v, true));
  return out;
}
function concat(...parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}
function bandsFile(index: Record<string, [number, number]>, values: number[]): Uint8Array {
  const js = new TextEncoder().encode(JSON.stringify(index));
  const head = new Uint8Array(4);
  new DataView(head.buffer).setUint32(0, js.length, true);
  return concat(head, js, lef32(new Float32Array(values)));
}

const yearShardBytes = (year: number) => {
  const rows = Array.from({ length: N_ENT }, (_, e) => rowOf(e, year, N_Y));
  const u = new Uint16Array(N_ENT * N_DIMS);
  const t = new Float32Array(N_ENT);
  rows.forEach((r, i) => {
    u.set(corpusU16.subarray(r * N_DIMS, (r + 1) * N_DIMS), i * N_DIMS);
    t[i] = totals[r];
  });
  return concat(le16(u), lef32(t));
};
const entityShardBytes = (e: number) =>
  concat(le16(corpusU16.subarray(e * N_Y * N_DIMS, (e + 1) * N_Y * N_DIMS)), lef32(totals.subarray(e * N_Y, (e + 1) * N_Y)));

const rawBlob = encodeBlobRaw(corpusU16, N_Y, N_DIMS);
const gzBlob = new Uint8Array(gzipSync(rawBlob));
const embValues = Array.from({ length: N_ROWS * 64 }, (_, i) => Math.sin(i) * 0.5);
const embBytes = le16(new Uint16Array(embValues.map(f32ToF16)));

const files: Record<string, Uint8Array> = {
  'data/x/shares.d16z': gzBlob,
  'data/x/shares.u16': le16(corpusU16),
  'data/x/totals.f32': lef32(totals),
  'data/x/bands.bin': bandsFile({ 'same/blend/2/1950': [0, 3], 'cross/l2/2/obs/1950': [3, 2], 'cross/l2/1/obs/1950': [3, 2] }, [0.1, 0.2, 0.3, 1, 2]),
  'data/x/bands_default.bin': bandsFile({ 'same/blend/2/1950': [0, 2] }, [0.5, 0.75]),
  'data/x/emb/m.f16': embBytes,
};
for (let y = 0; y < N_Y; y++) files[`data/x/years/${1950 + y}.u16`] = yearShardBytes(1950 + y);
['AAA', 'BBB', 'agg-1'].forEach((id, e) => (files[`data/x/pyramids/${id}.u16`] = entityShardBytes(e)));

const fakeEntities = ['AAA', 'BBB', 'agg-1'].map(
  (id, i): Entity => ({
    id,
    locid: i,
    iso2: id.length === 3 ? id.slice(0, 2) : null,
    name: id,
    short_name: id,
    slug: id.toLowerCase(),
    aliases: [id.toLowerCase()],
    type: id.startsWith('agg') ? 'aggregate' : 'country',
    subregion_locid: null,
    region_locid: null,
    sdg_region_locid: null,
    income_group: null,
    dev_group: null,
    pop_2026: 1000,
    is_micro: false,
    axis_pct: 10,
    notes: [],
  }),
);

const fakeMeta = {
  revision: 'test',
  patches: [],
  built: '',
  last_observed_year: 1951,
  n_entities: N_ENT,
  n_countries: 2,
  n_rows: N_ROWS,
  n_years: N_Y,
  files: {
    years: 'data/x/years',
    pyramids: 'data/x/pyramids',
    shares_d16z: 'data/x/shares.d16z',
    shares_u16: 'data/x/shares.u16',
    totals: 'data/x/totals.f32',
    bands: 'data/x/bands.bin',
    bands_default: 'data/x/bands_default.bin',
    emb: { m: 'data/x/emb/m.f16' },
    notice: 'data/x/NOTICE',
  },
  sigma: {},
  kernel: [0.054, 0.242, 0.399, 0.242, 0.054],
  budgets: {},
  sizes: {},
  attribution: [],
  bands_grid: [],
  bands_format: '',
} as unknown as Meta;

const BASE = '/population-pyramid-explorer/';
let requests: string[] = [];
let override: Record<string, Uint8Array | number> = {}; // path → bytes or HTTP status

function fakeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  requests.push(url);
  if (!url.startsWith(BASE)) return Promise.resolve(new Response('bad base', { status: 404 }));
  const rel = url.slice(BASE.length);
  const o = override[rel];
  if (typeof o === 'number') return Promise.resolve(new Response('', { status: o }));
  const body = o ?? files[rel];
  if (!body) return Promise.resolve(new Response('missing', { status: 404 }));
  return Promise.resolve(new Response(body.slice().buffer));
}

beforeEach(() => {
  requests = [];
  override = {};
  configureData({ base: BASE, fetch: fakeFetch, meta: fakeMeta, entities: fakeEntities, gzipStream: true });
});
afterEach(() => resetData());

// ------------------------------------------------------------------------------ tests

describe('URLs and indexes', () => {
  test('dataUrl joins BASE_URL and the meta.files path, normalising slashes', () => {
    expect(dataUrl('data/x/shares.d16z')).toBe(`${BASE}data/x/shares.d16z`);
    expect(dataUrl('/data/x/shares.d16z')).toBe(`${BASE}data/x/shares.d16z`);
    configureData({ base: '/' });
    expect(dataUrl('data/a')).toBe('/data/a');
    configureData({ base: '/no-slash' });
    expect(dataUrl('data/a')).toBe('/no-slash/data/a');
  });

  test('entityIndex follows corpus order; rowOf uses meta.n_years', () => {
    expect(entityIndex('AAA')).toBe(0);
    expect(entityIndex('agg-1')).toBe(2);
    expect(entityIndex('ZZZ')).toBe(-1);
    expect(rowOf(2, 1953)).toBe(2 * N_Y + 3);
    expect(rowOf(1, 1960, 151)).toBe(151 + 10);
  });
});

describe('tier 1', () => {
  test('entity shard parses rows and totals; pyramids dequantise to shares summing to 1', async () => {
    const shard = await loadEntityShard('BBB');
    expect(requests).toEqual([`${BASE}data/x/pyramids/BBB.u16`]);
    expect(shard.u16.length).toBe(N_Y * N_DIMS);
    expect(shard.totals.length).toBe(N_Y);
    const p = entityShardPyramid(shard, 1952);
    const row = rowOf(1, 1952, N_Y);
    expect(p.total).toBeCloseTo(totals[row], 5);
    expect(Array.from(p.shares)).toEqual(Array.from(sharesAt(corpusU16, row * N_DIMS)));
    expect(p.shares.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 5);
    expect(() => entityShardPyramid(shard, 1949)).toThrow(RangeError);
  });

  test('year shard is in entity order and matches the entity shard for the same cell', async () => {
    const [ys, es] = await Promise.all([loadYearShard(1951), loadEntityShard('agg-1')]);
    expect(ys.n).toBe(N_ENT);
    const a = yearShardPyramid(ys, 2);
    const b = entityShardPyramid(es, 1951);
    expect(a.shares).toEqual(b.shares);
    expect(a.total).toBe(b.total);
    expect(() => yearShardPyramid(ys, 3)).toThrow(RangeError);
    await expect(loadYearShard(2101)).rejects.toThrow(RangeError);
  });

  test('loadFirstPaint fetches the three files in parallel and memoises them', async () => {
    const [es, ys, bd] = await loadFirstPaint('AAA', 1950);
    expect(requests.length).toBe(3);
    expect(es.id).toBe('AAA');
    expect(ys.year).toBe(1950);
    expect(Array.from(bandTable(bd, 'same/blend/2/1950')!)).toEqual([0.5, 0.75]);
    await loadFirstPaint('AAA', 1950);
    expect(requests.length).toBe(3); // no refetch
    expect(await loadEntityShard('AAA')).toBe(es); // same object
  });

  test('unknown entity, HTTP errors and wrong lengths reject — and a rejection is not cached', async () => {
    await expect(loadEntityShard('ZZZ')).rejects.toThrow(/unknown entity/);
    override['data/x/pyramids/AAA.u16'] = 500;
    await expect(loadEntityShard('AAA')).rejects.toThrow(/HTTP 500/);
    override = {};
    await expect(loadEntityShard('AAA')).resolves.toMatchObject({ id: 'AAA' }); // retry succeeds
    override['data/x/years/1950.u16'] = new Uint8Array(10);
    await expect(loadYearShard(1950)).rejects.toThrow(/10 bytes, expected/);
  });
});

describe('bands', () => {
  test('parseBands reads the u32 index, aliases share one slot, out-of-range tables reject', async () => {
    const b = await loadBands();
    expect(Array.from(bandTable(b, 'same/blend/2/1950')!)).toEqual(new Array<number>().concat([0.1, 0.2, 0.3]).map((x) => Math.fround(x)));
    expect(bandTable(b, 'cross/l2/1/obs/1950')).toEqual(bandTable(b, 'cross/l2/2/obs/1950')); // sex-blind alias
    expect(bandTable(b, 'nope')).toBeUndefined();
    expect(() => parseBands(bandsFile({ a: [0, 9] }, [1, 2]).slice().buffer)).toThrow(/out of range/);
    expect(() => parseBands(new Uint8Array([1, 0, 0]).buffer)).toThrow(/truncated/);
  });

  test('values need not be 4-byte aligned after the JSON index', () => {
    const b = parseBands(bandsFile({ x: [0, 1] }, [42]).slice().buffer); // JSON length 11 → offset 15
    expect(Array.from(bandTable(b, 'x')!)).toEqual([42]);
  });
});

describe('tier 3 — corpus blob', () => {
  test('gzip magic → DecompressionStream path; rows equal the source u16 and totals align', async () => {
    const c = await loadCorpus();
    expect(c.source.path).toBe('gzip-stream');
    expect(c.nRows).toBe(N_ROWS);
    expect(c.u16).toEqual(corpusU16);
    expect(c.totals).toEqual(totals);
    const p = corpusPyramid(c, 1, 1953);
    const es = await loadEntityShard('BBB');
    expect(p.shares).toEqual(entityShardPyramid(es, 1953).shares);
    expect(requests.filter((u) => u.endsWith('shares.d16z')).length).toBe(1);
    expect(requests.filter((u) => u.endsWith('totals.f32')).length).toBe(1);
    expect(await loadCorpus()).toBe(c); // memoised
    expect(requests.filter((u) => u.endsWith('shares.d16z')).length).toBe(1);
  });

  test('a body without gzip magic is taken as already inflated (proxy decompressed it)', async () => {
    override['data/x/shares.d16z'] = rawBlob;
    const c = await loadCorpus();
    expect(c.source.path).toBe('inflated-body');
    expect(c.u16).toEqual(corpusU16);
  });

  test('inflated length must equal n_rows × 84', async () => {
    override['data/x/shares.d16z'] = rawBlob.slice(0, rawBlob.length - 2);
    await expect(loadCorpus()).rejects.toThrow(/inflated \(inflated-body\): \d+ bytes, expected/);
    override['data/x/shares.d16z'] = new Uint8Array(gzipSync(rawBlob.slice(0, rawBlob.length - 84)));
    await expect(loadCorpus()).rejects.toThrow(/inflated \(gzip-stream\)/);
  });

  test('falls back to shares.u16 when DecompressionStream is unavailable', async () => {
    configureData({ gzipStream: false });
    const c = await loadCorpus();
    expect(c.source.path).toBe('u16-fallback');
    expect(c.u16).toEqual(corpusU16);
    expect(requests.some((u) => u.endsWith('shares.u16'))).toBe(true);
    expect(requests.some((u) => u.endsWith('shares.d16z'))).toBe(false);
  });

  test('isGzip sniff', () => {
    expect(isGzip(new Uint8Array([0x1f, 0x8b, 0x08]))).toBe(true);
    expect(isGzip(new Uint8Array([0x1f]))).toBe(false);
    expect(isGzip(new Uint8Array([0x00, 0x8b]))).toBe(false);
  });

  test('embeddings decode float16 rows', async () => {
    const e = await loadEmbedding('m');
    expect(e.nRows).toBe(N_ROWS);
    expect(e.dim).toBe(64);
    expect(e.values.length).toBe(N_ROWS * 64);
    for (let i = 0; i < 50; i++) expect(e.values[i]).toBeCloseTo(embValues[i], 3); // half precision
    await expect(loadEmbedding('nope')).rejects.toThrow(/no embedding/);
  });
});
