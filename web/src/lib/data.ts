/**
 * Three-tier data layer (PLAN §8; CONTRACT §5 + AMENDMENTS §F/§G).
 *
 *  tier 1  `loadEntityShard(id)`, `loadYearShard(year)`, `loadBandsDefault()` — the first-paint set
 *          (fetched in parallel by `loadFirstPaint`), plus the imported `entities` / `meta`.
 *  tier 2  `loadBands()` — every percentile table, on the first non-default metric / mode.
 *  tier 3  `loadCorpus()` — the whole corpus for cross-year search: `shares.*.d16z` is fetched, the
 *          first two bytes are sniffed (`1f 8b` → `DecompressionStream('gzip')`, anything else →
 *          the body is taken as already inflated by a proxy), the inflated length is checked
 *          against `n_rows × 84`, then `math/delta.ts` un-transposes and modular-cumsums into a
 *          `Uint16Array`. Falls back to `shares.*.u16` when `DecompressionStream` is undefined.
 *          `loadEmbedding(model)` decodes `emb/*.f16` the same way (lazy, Visual metric only).
 *
 * Every loader returns a Promise, is memoised (a rejected promise is evicted so a retry can
 * succeed), touches no DOM, and builds URLs from `meta.files` + Vite's `BASE_URL` so the GitHub
 * Pages project path is respected. `configureData` injects fetch / meta / base for tests.
 */

import metaJson from '../data/meta.json';
import entitiesJson from '../data/entities.json';
import { decodeBlob } from './math/delta.ts';
import { gunzip, isGzip } from './math/gz.ts';
import { decodeEcon, type EconData } from './econ.ts';
import { decodeF16 } from './math/f16.ts';
import {
  N_DIMS,
  ROW_BYTES,
  U16_TOTAL,
  YEAR_MAX,
  YEAR_MIN,
  type Bands,
  type Corpus,
  type CorpusPath,
  type Embedding,
  type Entity,
  type EntityShard,
  type Meta,
  type Pyramid,
  type YearShard,
} from './types.ts';

export const meta = metaJson as unknown as Meta;
export const entities = entitiesJson as unknown as Entity[];

// ---------------------------------------------------------------------------------------- config

export interface DataConfig {
  /** Site base path, always ending in '/'. Defaults to `import.meta.env.BASE_URL`. */
  base: string;
  fetch: typeof globalThis.fetch;
  meta: Meta;
  entities: Entity[];
  /** Whether `DecompressionStream('gzip')` is usable (feature-detected; tests override). */
  gzipStream: boolean;
}

function defaultBase(): string {
  const env = (import.meta as unknown as { env?: { BASE_URL?: string } }).env;
  return normaliseBase(env?.BASE_URL ?? '/');
}

function normaliseBase(b: string): string {
  return b.endsWith('/') ? b : b + '/';
}

function detectGzipStream(): boolean {
  if (typeof DecompressionStream === 'undefined') return false;
  try {
    new DecompressionStream('gzip');
    return true;
  } catch {
    return false;
  }
}

function defaults(): DataConfig {
  return {
    base: defaultBase(),
    fetch: (...args) => globalThis.fetch(...args),
    meta,
    entities,
    gzipStream: detectGzipStream(),
  };
}

let cfg: DataConfig = defaults();
const cache = new Map<string, Promise<unknown>>();
let entityIdx: Map<string, number> | null = null;

/** Override parts of the configuration (tests, a custom base). Clears every memoised load. */
export function configureData(partial: Partial<DataConfig>): DataConfig {
  cfg = { ...cfg, ...partial };
  if (partial.base !== undefined) cfg.base = normaliseBase(partial.base);
  resetDataCache();
  return cfg;
}

/** Restore the production configuration and drop every cached load. */
export function resetData(): void {
  cfg = defaults();
  resetDataCache();
}

/** Drop memoised loads (the config stays). */
export function resetDataCache(): void {
  cache.clear();
  entityIdx = null;
}

export function dataConfig(): Readonly<DataConfig> {
  return cfg;
}

/** Absolute URL path of a `meta.files` entry (or any site-relative path) under the current base. */
export function dataUrl(rel: string): string {
  return cfg.base + rel.replace(/^\/+/, '');
}

function memo<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = cache.get(key);
  if (hit) return hit as Promise<T>;
  const p = load();
  cache.set(key, p);
  p.catch(() => {
    if (cache.get(key) === p) cache.delete(key);
  });
  return p;
}

// --------------------------------------------------------------------------------- entities index

/** id → corpus index (entity order), built from the configured entities. */
export function entityIndexMap(): Map<string, number> {
  if (!entityIdx) entityIdx = new Map(cfg.entities.map((e, i) => [e.id, i]));
  return entityIdx;
}

/** Corpus index of an entity id, or −1. */
export function entityIndex(id: string): number {
  return entityIndexMap().get(id) ?? -1;
}

/** Corpus row of (entity index, year): `row = entity_idx × n_years + (year − 1950)`. */
export function rowOf(entityIdx: number, year: number, nYears: number = cfg.meta.n_years): number {
  return entityIdx * nYears + (year - YEAR_MIN);
}

function assertYear(year: number): void {
  if (!Number.isInteger(year) || year < YEAR_MIN || year > YEAR_MAX) {
    throw new RangeError(`year ${year} outside ${YEAR_MIN}..${YEAR_MAX}`);
  }
}

// --------------------------------------------------------------------------------- byte helpers

const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

/** `length` little-endian Uint16 at `byteOffset` — a zero-copy view when aligned on a LE host. */
export function u16View(buf: ArrayBuffer, byteOffset: number, length: number): Uint16Array {
  if (byteOffset + 2 * length > buf.byteLength) throw new Error('u16View: out of range');
  if (LITTLE_ENDIAN && byteOffset % 2 === 0) return new Uint16Array(buf, byteOffset, length);
  const dv = new DataView(buf);
  const out = new Uint16Array(length);
  for (let i = 0; i < length; i++) out[i] = dv.getUint16(byteOffset + 2 * i, true);
  return out;
}

/** `length` little-endian Float32 at `byteOffset` — a zero-copy view when aligned on a LE host. */
export function f32View(buf: ArrayBuffer, byteOffset: number, length: number): Float32Array {
  if (byteOffset + 4 * length > buf.byteLength) throw new Error('f32View: out of range');
  if (LITTLE_ENDIAN && byteOffset % 4 === 0) return new Float32Array(buf, byteOffset, length);
  const dv = new DataView(buf);
  const out = new Float32Array(length);
  for (let i = 0; i < length; i++) out[i] = dv.getFloat32(byteOffset + 4 * i, true);
  return out;
}

async function fetchBytes(rel: string): Promise<ArrayBuffer> {
  const url = dataUrl(rel);
  const res = await cfg.fetch(url);
  if (!res.ok) throw new Error(`fetch ${url}: HTTP ${res.status}`);
  return res.arrayBuffer();
}

function expectLength(what: string, got: number, want: number): void {
  if (got !== want) throw new Error(`${what}: ${got} bytes, expected ${want}`);
}

// --------------------------------------------------------------------------------- dequantise

/** Dequantise 42 Uint16 at `offset` into a fresh Float32Array (`u / 65535`, float32 like Python). */
export function sharesAt(u16: Uint16Array, offset: number, out: Float32Array = new Float32Array(N_DIMS)): Float32Array {
  for (let k = 0; k < N_DIMS; k++) out[k] = u16[offset + k] / U16_TOTAL;
  return out;
}

/** One pyramid from a shard-like `(u16, totals)` pair at row `i`. */
function pyramidRow(u16: Uint16Array, totals: Float32Array, i: number): Pyramid {
  return { shares: sharesAt(u16, i * N_DIMS), total: totals[i] };
}

/** Pyramid of the `i`-th entity (corpus order) in a year shard. */
export function yearShardPyramid(shard: YearShard, i: number): Pyramid {
  if (i < 0 || i >= shard.n) throw new RangeError(`entity index ${i} outside 0..${shard.n - 1}`);
  return pyramidRow(shard.u16, shard.totals, i);
}

/** Pyramid of `year` in an entity shard. */
export function entityShardPyramid(shard: EntityShard, year: number): Pyramid {
  assertYear(year);
  return pyramidRow(shard.u16, shard.totals, year - YEAR_MIN);
}

/** Pyramid of (entity index, year) from the full corpus. */
export function corpusPyramid(corpus: Corpus, entityIdx: number, year: number): Pyramid {
  assertYear(year);
  if (entityIdx < 0 || entityIdx >= corpus.nEntities) throw new RangeError(`entity index ${entityIdx} out of range`);
  return pyramidRow(corpus.u16, corpus.totals, rowOf(entityIdx, year, corpus.nYears));
}

// --------------------------------------------------------------------------------- parsers

/** Parse a year shard: n × 42 Uint16 then n Float32 totals (CONTRACT §5). */
export function parseYearShard(buf: ArrayBuffer, year: number, n: number = cfg.meta.n_entities): YearShard {
  expectLength(`year shard ${year}`, buf.byteLength, n * (ROW_BYTES + 4));
  return { year, n, u16: u16View(buf, 0, n * N_DIMS), totals: f32View(buf, n * ROW_BYTES, n) };
}

/** Parse an entity shard: 151 × 42 Uint16 then 151 Float32 totals. */
export function parseEntityShard(buf: ArrayBuffer, id: string, nYears: number = cfg.meta.n_years): EntityShard {
  expectLength(`entity shard ${id}`, buf.byteLength, nYears * (ROW_BYTES + 4));
  return { id, u16: u16View(buf, 0, nYears * N_DIMS), totals: f32View(buf, nYears * ROW_BYTES, nYears) };
}

/** Parse `bands*.bin`: u32 LE JSON length + JSON `{name: [offset, count]}` + float32 LE values. */
export function parseBands(buf: ArrayBuffer): Bands {
  if (buf.byteLength < 4) throw new Error('bands: truncated header');
  const jsonLen = new DataView(buf).getUint32(0, true);
  if (4 + jsonLen > buf.byteLength) throw new Error('bands: index length exceeds file');
  const index = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, jsonLen))) as Record<string, [number, number]>;
  const valuesOff = 4 + jsonLen;
  const rest = buf.byteLength - valuesOff;
  if (rest % 4 !== 0) throw new Error(`bands: values section (${rest} bytes) is not float32-aligned`);
  const values = f32View(buf, valuesOff, rest / 4);
  for (const [name, [off, cnt]] of Object.entries(index)) {
    if (off < 0 || cnt < 0 || off + cnt > values.length) throw new Error(`bands: table ${name} out of range`);
  }
  return { index, values };
}

/** One table (24 grid values) by `/`-joined name, e.g. `same/blend/2/1990`; undefined if absent. */
export function bandTable(bands: Bands, name: string): Float32Array | undefined {
  const e = bands.index[name];
  return e ? bands.values.subarray(e[0], e[0] + e[1]) : undefined;
}

export { gunzip, isGzip };

// --------------------------------------------------------------------------------- tier 1

/** `pyramids.{sha8}/{id}.u16` — 151 years of one entity; the first-paint shard. */
export function loadEntityShard(id: string): Promise<EntityShard> {
  return memo(`entity:${id}`, async () => {
    if (entityIndex(id) < 0) throw new Error(`unknown entity id ${id}`);
    const buf = await fetchBytes(`${cfg.meta.files.pyramids}/${id}.u16`);
    return parseEntityShard(buf, id);
  });
}

/** `years.{sha8}/{year}.u16` — every entity in one year (same-year twins without the blob). */
export function loadYearShard(year: number): Promise<YearShard> {
  return memo(`year:${year}`, async () => {
    assertYear(year);
    const buf = await fetchBytes(`${cfg.meta.files.years}/${year}.u16`);
    return parseYearShard(buf, year);
  });
}

/** `bands_default.{sha8}.bin` — `same/blend/2/{year}` only; the fourth first-paint fetch. */
export function loadBandsDefault(): Promise<Bands> {
  return memo('bands_default', async () => parseBands(await fetchBytes(cfg.meta.files.bands_default)));
}

/** The first-paint set, fetched in parallel. */
export function loadFirstPaint(id: string, year: number): Promise<[EntityShard, YearShard, Bands]> {
  return Promise.all([loadEntityShard(id), loadYearShard(year), loadBandsDefault()]);
}

// --------------------------------------------------------------------------------- tier 2

/** `bands.{sha8}.bin` — every metric × sex × table. */
export function loadBands(): Promise<Bands> {
  return memo('bands', async () => parseBands(await fetchBytes(cfg.meta.files.bands)));
}

// --------------------------------------------------------------------------------- tier 3

async function loadCorpusShares(): Promise<{ u16: Uint16Array; path: CorpusPath; decodeMs: number; fetchMs: number }> {
  const { n_rows: nRows, n_years: nYears, files } = cfg.meta;
  const want = nRows * ROW_BYTES;
  const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

  if (!cfg.gzipStream) {
    const t0 = now();
    const buf = await fetchBytes(files.shares_u16);
    const fetchMs = now() - t0;
    expectLength('shares.u16', buf.byteLength, want);
    return { u16: u16View(buf, 0, nRows * N_DIMS), path: 'u16-fallback', decodeMs: 0, fetchMs };
  }

  const t0 = now();
  const buf = await fetchBytes(files.shares_d16z);
  const fetchMs = now() - t0;
  const t1 = now();
  const head = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
  let inflated: Uint8Array;
  let path: CorpusPath;
  if (isGzip(head)) {
    inflated = await gunzip(buf);
    path = 'gzip-stream';
  } else {
    inflated = new Uint8Array(buf); // a proxy already inflated it
    path = 'inflated-body';
  }
  expectLength(`shares.d16z inflated (${path})`, inflated.length, want);
  const u16 = decodeBlob(inflated, nRows, nYears, N_DIMS);
  return { u16, path, decodeMs: now() - t1, fetchMs };
}

/** `totals.{sha8}.f32` — n_rows Float32 (thousands), fetched with the blob. */
export function loadTotals(): Promise<Float32Array> {
  return memo('totals', async () => {
    const buf = await fetchBytes(cfg.meta.files.totals);
    expectLength('totals.f32', buf.byteLength, cfg.meta.n_rows * 4);
    return f32View(buf, 0, cfg.meta.n_rows);
  });
}

/** The whole corpus (shares + totals), decoded once. Row = `rowOf(entityIdx, year)`. */
export function loadCorpus(): Promise<Corpus> {
  return memo('corpus', async () => {
    const [shares, totals] = await Promise.all([loadCorpusShares(), loadTotals()]);
    const { n_rows: nRows, n_entities: nEntities, n_years: nYears } = cfg.meta;
    if (nRows !== nEntities * nYears) throw new Error(`meta: n_rows ${nRows} != ${nEntities} × ${nYears}`);
    return {
      nRows,
      nEntities,
      nYears,
      u16: shares.u16,
      totals,
      source: { path: shares.path, decodeMs: shares.decodeMs, fetchMs: shares.fetchMs },
    };
  });
}

// --------------------------------------------------------------------------------- tier 2b (econ)

/**
 * `econ.{sha8}.ecz` — the economic-lens file (PLAN §7), fetched AFTER the first paint and never in the first-paint
 * set (the decoder itself is ~4 KB gz and rides in the entry; the econ COMPONENTS are the lazy chunk).
 * Resolves to null when the build shipped no econ file (`meta.files.econ` absent) — the UI shows its "no econ data"
 * state instead of failing.
 */
export function loadEcon(): Promise<EconData | null> {
  return memo('econ', async () => {
    const rel = cfg.meta.files.econ;
    if (!rel) return null;
    return decodeEcon(await fetchBytes(rel));
  });
}

/** `emb/{model}.{sha8}.f16` — n_rows × 64 Float16 → Float32 (lazy; Visual metric only). */
export function loadEmbedding(model: string, dim = 64): Promise<Embedding> {
  return memo(`emb:${model}`, async () => {
    const rel = cfg.meta.files.emb[model];
    if (!rel) throw new Error(`no embedding shipped for model ${model}`);
    const buf = await fetchBytes(rel);
    expectLength(`emb ${model}`, buf.byteLength, cfg.meta.n_rows * dim * 2);
    return { model, nRows: cfg.meta.n_rows, dim, values: decodeF16(buf) };
  });
}
