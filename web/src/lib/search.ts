/**
 * Twins, opposites, time-shift and isolation — TS twin of `src/pyramid_explorer/{metrics,search}.py`
 * (CONTRACT §4 + AMENDMENTS §B/§F/§G, PLAN §4–§6). Pure functions over typed arrays; no DOM, no d3.
 *
 * Arithmetic: every share is `u16 / 65535` in float64 and every distance is float64, so results match
 * `evals/fixtures/search_cases.json` (written by `scripts/search_fixture.py` from the same numbers) to ~1e-9 and
 * ties are broken on identical values. Metrics (`sex='2'` on the 42-vector, `'1'` on s21):
 *   l2 · w1 (total-only CDF, years; sex-blind) · w1sex (per-sex CDF; sex='1' → w1) · blend = ½·l2/σ_l2 + ½·w1s/σ
 *   · l2s (5-tap smoothing) · hel (Hellinger) · feat (L2 on z-scored features, reference = the QUERY year's
 *   country set in scope, own entity included) · w1bal (w1 + 50·Σ ½(a+b)|r_a−r_b|) · visual (cosine on PCA-64)
 *   · trend/motion: ‖Δ_q − Δ_c‖₂ / σ_trend@L with Δ = s(row) − s(row − L) · trend/path: mean blend over lags 0,5,…,L.
 *
 * `CorpusView` abstracts where the rows come from: `fromCorpus` (tier 3 blob, cross-year modes) or
 * `fromYearShards` (one year shard for same/today modes; extra year shards back trend lags / the `feat`
 * reference year; `injectEntityRows` appends a query's own rows from its entity shard when the query year is not
 * the shard year, e.g. `today` from 1990). Rows `[0, nRows)` are the candidates; rows beyond may only back lags
 * and injected queries. `corpusRow(row)` maps any view row to the corpus row (`emb/*.f16` and fixtures index by it).
 *
 * Semantics mirrored line by line from search.py: mask = year mode ∧ era (obs ⇒ year ≤ max(lastObserved,
 * currentYear)) ∧ scope ∧ minpop on the candidate's own-year total ∧ not own
 * entity ∧ (trend ⇒ year − L ≥ 1950); non-finite distances are dropped; dedupe = one row per entity, best d, ties by
 * |Δy| then year; MMR pool = min(max(⌈0.25·n⌉, k), 2000) farthest, greedy argmax d(q,x) + div·min_s d(x,s), first
 * index wins ties; `rankRaw` = 1-based position in the plain ordering.
 */

import { bandFor, tableMetric, type BandLabel, type BandResult, type Era } from './bands.ts';
import { entities as allEntities, meta } from './data.ts';
import { NUMERIC_FEATURES, features, numericVector } from './math/features.ts';
import { KERNEL } from './math/smooth.ts';
import {
  BIN_WIDTH,
  N_BINS,
  N_DIMS,
  U16_TOTAL,
  YEAR_MAX,
  YEAR_MIN,
  type Bands,
  type Corpus,
  type Entity,
  type EntityShard,
  type Sex,
  type SigmaTable,
  type YearShard,
} from './types.ts';

export type { BandLabel } from './bands.ts';

// ------------------------------------------------------------------------------------------------ query

export type YearMode = 'same' | 'near' | 'range' | 'any' | 'today';
export type Metric = 'blend' | 'l2' | 'w1' | 'l2s' | 'hel' | 'feat' | 'w1sex' | 'w1bal' | 'visual';
export type TrendKind = null | 'motion' | 'path';
export type TrendWindow = 5 | 10 | 20;

export const METRICS: readonly Metric[] = ['blend', 'l2', 'w1', 'l2s', 'hel', 'feat', 'w1sex', 'w1bal', 'visual'];
export const YEAR_MODES: readonly YearMode[] = ['same', 'near', 'range', 'any', 'today'];
export const TREND_WINDOWS: readonly TrendWindow[] = [5, 10, 20];
/** MMR diversity presets (PLAN §5, re-calibrated: `search.DIV_PRESETS`). */
export const DIV_PRESETS = { strict: 0, balanced: 0.5, spread: 2 } as const;
export const MAX_POOL = 2000;
export const POOL_FRAC = 0.25;
export const W1BAL_LAMBDA = 50;
export const MINPOP_DEFAULT = 100; // thousands

export interface SearchQuery {
  id: string;
  year: number;
  mode: YearMode;
  n?: number; // half-width for `near` (default 10)
  from?: number; // inclusive bounds for `range` (default 1950 / 2100)
  to?: number;
  era: Era;
  scope: 'c' | 'all';
  minpop: number; // thousands; candidate's own-year total
  metric: Metric;
  sex: Sex;
  k: number;
  div: 0 | 0.5 | 2;
  trend: TrendKind;
  L: TrendWindow;
  currentYear: number;
}

/** A query with the PLAN §6 defaults (same year · era obs · countries ≥ 100k · blend · two-sex · 5 · balanced). */
export function defaultQuery(id: string, year: number, currentYear: number, partial: Partial<SearchQuery> = {}): SearchQuery {
  return {
    id,
    year,
    mode: 'same',
    n: 10,
    era: year > currentYear ? 'all' : 'obs', // J8 default (PLAN §6); pass `era` to override it explicitly
    scope: 'c',
    minpop: MINPOP_DEFAULT,
    metric: 'blend',
    sex: '2',
    k: 5,
    div: DIV_PRESETS.balanced,
    trend: null,
    L: 10,
    currentYear,
    ...partial,
  };
}

export interface SearchResult {
  id: string;
  year: number;
  /** Row in the VIEW that produced it (use `view.corpusRow(row)` for embeddings / fixtures). */
  row: number;
  d: number;
  /** 1-based position in the plain (undiversified) ordering. */
  rankRaw: number;
  /** year − query year */
  dy: number;
  band: BandLabel;
  percentile: number | null;
}

export interface TimeShiftRow {
  id: string;
  bestYear: number;
  row: number;
  d: number;
  dy: number;
  /** y* sits on an edge of the entity's allowed years (consumers may suppress it when bestYear === query year). */
  boundaryHit: boolean;
  band: BandLabel;
  percentile: number | null;
}

export interface SearchOpts {
  /** PCA-64 embedding aligned with CORPUS rows (`loadEmbedding(model).values`); required for `metric: 'visual'`. */
  emb?: Float32Array;
  /** Image model whose bands/embedding `visual` uses (default `meta.verdicts.exposed_visual.model`). */
  visualModel?: string;
  /** Override of `meta.last_observed_year` (2023). */
  lastObservedYear?: number;
  /** Row of the query in the view (default `view.rowOf(q.id, q.year)`). */
  queryRow?: number;
}

// ------------------------------------------------------------------------------------------------ views

export interface CorpusView {
  /** ≥ nRows × 42 Uint16 shares; rows ≥ nRows (if any) back lags and injected query rows. */
  u16: Uint16Array;
  /** One float32 total (thousands) per row of `u16`. */
  totals: Float32Array;
  /** Candidate rows are `[0, nRows)`. */
  nRows: number;
  nYears: number;
  entityIdx(id: string): number;
  /** Row of (id, year) in this view, or −1 when the view does not hold it. */
  rowOf(id: string, year: number): number;
  // The four row-geometry members are optional so a plain corpus-shaped object (row = entity_idx × nYears +
  // year − 1950, the shared-interface minimum) is a valid view; `withGeometry` fills the corpus defaults.
  entityOfRow?(row: number): number;
  yearOfRow?(row: number): number;
  /** Row holding the same entity `L` years earlier, or −1 when unavailable (year − L < 1950 or not loaded). */
  lagRow?(row: number, L: number): number;
  /** Corpus row `entity_idx × n_years + (year − 1950)` of a view row. */
  corpusRow?(row: number): number;
}

/** A view with every geometry member present (corpus defaults when a plain object was passed). */
export type FullView = Required<CorpusView>;

/** Complete a view: shard views and `fromCorpus` views already are; a bare corpus-shaped object gets row arithmetic. */
export function withGeometry(view: CorpusView): FullView {
  if (view.entityOfRow && view.yearOfRow && view.lagRow && view.corpusRow) return view as FullView;
  const nYears = view.nYears;
  return {
    ...view,
    entityIdx: (id) => view.entityIdx(id),
    rowOf: (id, year) => view.rowOf(id, year),
    entityOfRow: view.entityOfRow?.bind(view) ?? ((row) => Math.floor(row / nYears)),
    yearOfRow: view.yearOfRow?.bind(view) ?? ((row) => YEAR_MIN + (row % nYears)),
    lagRow: view.lagRow?.bind(view) ?? ((row, L) => (row % nYears >= L ? row - L : -1)),
    corpusRow: view.corpusRow?.bind(view) ?? ((row) => row),
  };
}

function idIndex(ents: readonly Entity[]): Map<string, number> {
  return new Map(ents.map((e, i) => [e.id, i]));
}

/** View over the whole corpus (tier 3): view rows ARE corpus rows. */
export function fromCorpus(corpus: Corpus, ents: readonly Entity[] = allEntities): FullView {
  const idx = idIndex(ents);
  const nYears = corpus.nYears;
  if (corpus.nRows !== ents.length * nYears) throw new Error(`fromCorpus: ${corpus.nRows} rows for ${ents.length} entities × ${nYears} years`);
  return {
    u16: corpus.u16,
    totals: corpus.totals,
    nRows: corpus.nRows,
    nYears,
    entityIdx: (id) => idx.get(id) ?? -1,
    rowOf(id, year) {
      const e = idx.get(id);
      if (e === undefined || year < YEAR_MIN || year > YEAR_MIN + nYears - 1) return -1;
      return e * nYears + (year - YEAR_MIN);
    },
    entityOfRow: (row) => Math.floor(row / nYears),
    yearOfRow: (row) => YEAR_MIN + (row % nYears),
    lagRow: (row, L) => (row % nYears >= L ? row - L : -1),
    corpusRow: (row) => row,
  };
}

/**
 * View over year shards (tier 1): rows `[0, n)` are the main shard's entities (candidates); further shards
 * (τ − L for trend lags, the query year for `feat` in `today` mode) and injected entity rows follow.
 */
export class ShardView implements CorpusView {
  u16: Uint16Array;
  totals: Float32Array;
  readonly nRows: number;
  readonly nYears: number;
  private readonly idx: Map<string, number>;
  private ent: Int32Array;
  private yr: Int32Array;
  private readonly shardBase = new Map<number, number>();
  private readonly extra = new Map<string, number>();
  private count: number;

  constructor(main: YearShard, others: readonly YearShard[] = [], ents: readonly Entity[] = allEntities) {
    if (main.n !== ents.length) throw new Error(`ShardView: shard has ${main.n} rows for ${ents.length} entities`);
    this.idx = idIndex(ents);
    this.nRows = main.n;
    this.nYears = meta.n_years;
    const shards = [main, ...others.filter((s) => s.year !== main.year)];
    const rows = shards.length * main.n;
    this.u16 = new Uint16Array(rows * N_DIMS);
    this.totals = new Float32Array(rows);
    this.ent = new Int32Array(rows);
    this.yr = new Int32Array(rows);
    this.count = 0;
    for (const s of shards) {
      if (s.n !== main.n) throw new Error(`ShardView: shard ${s.year} has ${s.n} rows, main has ${main.n}`);
      if (this.shardBase.has(s.year)) continue;
      this.shardBase.set(s.year, this.count);
      this.u16.set(s.u16.subarray(0, s.n * N_DIMS), this.count * N_DIMS);
      this.totals.set(s.totals.subarray(0, s.n), this.count);
      for (let i = 0; i < s.n; i++) {
        this.ent[this.count + i] = i;
        this.yr[this.count + i] = s.year;
      }
      this.count += s.n;
    }
  }

  /** Years this view holds as whole shards (main first). */
  years(): number[] {
    return [...this.shardBase.keys()];
  }

  entityIdx(id: string): number {
    return this.idx.get(id) ?? -1;
  }

  private rowOfIdx(e: number, year: number): number {
    const base = this.shardBase.get(year);
    if (base !== undefined) return base + e;
    return this.extra.get(`${e}:${year}`) ?? -1;
  }

  rowOf(id: string, year: number): number {
    const e = this.idx.get(id);
    return e === undefined ? -1 : this.rowOfIdx(e, year);
  }

  entityOfRow(row: number): number {
    return this.ent[row];
  }

  yearOfRow(row: number): number {
    return this.yr[row];
  }

  lagRow(row: number, L: number): number {
    const y = this.yr[row] - L;
    return y < YEAR_MIN ? -1 : this.rowOfIdx(this.ent[row], y);
  }

  corpusRow(row: number): number {
    return this.ent[row] * this.nYears + (this.yr[row] - YEAR_MIN);
  }

  /**
   * Append the given years of one entity from its entity shard (a query whose year differs from the shard year,
   * and its trend lags). Rows already present are skipped; returns the view for chaining.
   */
  injectEntityRows(shard: EntityShard, years: readonly number[]): this {
    const e = this.idx.get(shard.id);
    if (e === undefined) throw new Error(`injectEntityRows: unknown entity ${shard.id}`);
    const missing = years.filter((y) => this.rowOfIdx(e, y) < 0);
    if (missing.length === 0) return this;
    const rows = this.count + missing.length;
    const u16 = new Uint16Array(rows * N_DIMS);
    u16.set(this.u16.subarray(0, this.count * N_DIMS));
    const totals = new Float32Array(rows);
    totals.set(this.totals.subarray(0, this.count));
    const ent = new Int32Array(rows);
    ent.set(this.ent.subarray(0, this.count));
    const yr = new Int32Array(rows);
    yr.set(this.yr.subarray(0, this.count));
    for (const y of missing) {
      if (y < YEAR_MIN || y > YEAR_MAX) throw new RangeError(`injectEntityRows: year ${y} outside ${YEAR_MIN}..${YEAR_MAX}`);
      const src = y - YEAR_MIN;
      u16.set(shard.u16.subarray(src * N_DIMS, (src + 1) * N_DIMS), this.count * N_DIMS);
      totals[this.count] = shard.totals[src];
      ent[this.count] = e;
      yr[this.count] = y;
      this.extra.set(`${e}:${y}`, this.count);
      this.count++;
    }
    this.u16 = u16;
    this.totals = totals;
    this.ent = ent;
    this.yr = yr;
    return this;
  }
}

/** Year-shard view for same/today modes; `others` = lag shards (τ − 5, …, τ − L) and/or the `feat` reference year. */
export function fromYearShards(main: YearShard, others: readonly YearShard[] = [], ents: readonly Entity[] = allEntities): ShardView {
  return new ShardView(main, others, ents);
}

/** `fromYearShard(shard, year)` — the shard's own year must be `year`. */
export function fromYearShard(shard: YearShard, year: number = shard.year, ents: readonly Entity[] = allEntities): ShardView {
  if (shard.year !== year) throw new Error(`fromYearShard: shard is for ${shard.year}, not ${year}`);
  return new ShardView(shard, [], ents);
}

/** Years a trend query needs besides the target year τ: τ − L (motion) or τ − 5, …, τ − L (path). */
export function lagYears(tau: number, trend: TrendKind, L: TrendWindow): number[] {
  if (trend === null) return [];
  const lags = trend === 'motion' ? [L] : Array.from({ length: L / 5 }, (_, i) => 5 * (i + 1));
  return lags.map((s) => tau - s);
}

/** Dequantised float64 share vector of a view row (fresh or into `out`). */
export function vectorAt(view: CorpusView, row: number, out: Float64Array = new Float64Array(N_DIMS)): Float64Array {
  const o = row * N_DIMS;
  for (let k = 0; k < N_DIMS; k++) out[k] = view.u16[o + k] / U16_TOTAL;
  return out;
}

// ------------------------------------------------------------------------------------------------ mask

function checkQuery(q: SearchQuery): void {
  if (!YEAR_MODES.includes(q.mode)) throw new Error(`mode must be one of ${YEAR_MODES.join('|')}, got ${q.mode}`);
  if (q.era !== 'obs' && q.era !== 'all') throw new Error(`era must be obs|all, got ${q.era}`);
  if (q.scope !== 'c' && q.scope !== 'all') throw new Error(`scope must be c|all, got ${q.scope}`);
  if (q.sex !== '2' && q.sex !== '1') throw new Error(`sex must be '2'|'1', got ${q.sex}`);
  if (!METRICS.includes(q.metric)) throw new Error(`unknown metric ${q.metric}`);
  if (q.trend !== null && q.trend !== 'motion' && q.trend !== 'path') throw new Error(`trend must be motion|path|null, got ${q.trend}`);
  if (q.trend !== null) {
    if (!TREND_WINDOWS.includes(q.L)) throw new Error(`L must be one of ${TREND_WINDOWS.join('|')}, got ${q.L}`);
    if (q.year - q.L < YEAR_MIN) throw new Error(`trend window ${q.L} y reaches before ${YEAR_MIN} for ${q.id} ${q.year}`);
    if (q.trend === 'path' && q.L % 5) throw new Error('path needs L to be a multiple of 5');
  }
}

/**
 * Uint8 candidate mask over `[0, view.nRows)` — `search.candidate_mask`: year mode ∧ era ∧ scope ∧ minpop
 * (candidate's own-year total) ∧ not own entity ∧ (trend: year − L ≥ 1950). Era `obs` keeps
 * `year ≤ max(lastObservedYear, currentYear)`. `q.era` is the RESOLVED era: the J8 default (`all` when the query
 * year is a projection) is the caller's job — `defaultQuery()` and `router.effectiveEra()` apply it — so an explicit
 * `era=obs` on `/japan/2050` really hides projections (PLAN §6 J8: the inverted chip writes it on purpose). The
 * Python CLI has no explicit/default distinction and flips `obs` → `all` inside `candidate_mask` instead.
 */
export function candidateMask(view0: CorpusView, ents: readonly Entity[], q: SearchQuery, lastObservedYear: number = meta.last_observed_year): Uint8Array {
  checkQuery(q);
  const view = withGeometry(view0);
  const own = view.entityIdx(q.id);
  const m = new Uint8Array(view.nRows);
  const eraCap = q.era === 'obs' ? Math.max(lastObservedYear, q.currentYear) : Infinity;
  const lo = q.mode === 'range' ? (q.from ?? YEAR_MIN) : -Infinity;
  const hi = q.mode === 'range' ? (q.to ?? YEAR_MAX) : Infinity;
  const n = q.n ?? 10;
  for (let r = 0; r < view.nRows; r++) {
    const y = view.yearOfRow(r);
    let ok: boolean;
    switch (q.mode) {
      case 'same':
        ok = y === q.year;
        break;
      case 'today':
        ok = y === q.currentYear;
        break;
      case 'near':
        ok = Math.abs(y - q.year) <= n;
        break;
      case 'range':
        ok = y >= lo && y <= hi;
        break;
      default:
        ok = true;
    }
    if (!ok || y > eraCap) continue;
    const e = view.entityOfRow(r);
    if (q.scope === 'c' && ents[e].type !== 'country') continue;
    if (!(view.totals[r] >= q.minpop)) continue;
    if (e === own) continue;
    if (q.trend !== null && y - q.L < YEAR_MIN) continue;
    m[r] = 1;
  }
  return m;
}

// ------------------------------------------------------------------------------------------------ features

export interface FeatureStats {
  year: number;
  /** Rows of the reference set (in the view). */
  rows: Int32Array;
  mu: Float64Array;
  sd: Float64Array;
}

/**
 * Reference statistics for `feat` z-scores and explanations (PLAN §3.3): the focal year's entity set in scope
 * with total ≥ minpop, own entity INCLUDED (`candidate_mask(mode='same', id='')`). nanmean / nanstd (ddof 0);
 * a zero or undefined spread becomes 1. Throws when the view does not hold that year.
 */
export function featureStats(view0: CorpusView, ents: readonly Entity[], year: number, scope: 'c' | 'all' = 'c', minpop: number = MINPOP_DEFAULT): FeatureStats {
  const view = withGeometry(view0);
  if (view0 instanceof ShardView && !view0.years().includes(year)) {
    throw new Error(`featureStats: the view holds no ${year} shard (injected rows are not a reference set) — load the ${year} year shard`);
  }
  const rows: number[] = [];
  const rowSpan = view.u16.length / N_DIMS;
  for (let r = 0; r < rowSpan; r++) {
    if (view.yearOfRow(r) !== year) continue;
    if (scope === 'c' && ents[view.entityOfRow(r)].type !== 'country') continue;
    if (!(view.totals[r] >= minpop)) continue;
    rows.push(r);
  }
  if (rows.length === 0) throw new Error(`featureStats: the view holds no ${year} rows (scope ${scope}, minpop ${minpop})`);
  const nf = NUMERIC_FEATURES.length;
  const F = new Float64Array(rows.length * nf);
  const v = new Float64Array(N_DIMS);
  rows.forEach((r, i) => F.set(numericVector(features(vectorAt(view, r, v))), i * nf));
  const mu = new Float64Array(nf);
  const sd = new Float64Array(nf);
  for (let j = 0; j < nf; j++) {
    let s = 0;
    let n = 0;
    for (let i = 0; i < rows.length; i++) {
      const x = F[i * nf + j];
      if (!Number.isNaN(x)) {
        s += x;
        n++;
      }
    }
    const m = n ? s / n : NaN;
    let ss = 0;
    for (let i = 0; i < rows.length; i++) {
      const x = F[i * nf + j];
      if (!Number.isNaN(x)) ss += (x - m) * (x - m);
    }
    const dev = n ? Math.sqrt(ss / n) : NaN;
    mu[j] = m;
    sd[j] = Number.isFinite(dev) && dev > 0 ? dev : 1;
  }
  return { year, rows: Int32Array.from(rows), mu, sd };
}

/** z-scored numeric features of one row against `stats` (NaN where the raw feature is undefined). */
export function zFeatures(view: CorpusView, row: number, stats: FeatureStats, v: Float64Array = new Float64Array(N_DIMS)): Float64Array {
  const f = numericVector(features(vectorAt(view, row, v)));
  for (let j = 0; j < f.length; j++) f[j] = (f[j] - stats.mu[j]) / stats.sd[j];
  return f;
}

// ------------------------------------------------------------------------------------------------ distances

function sigmaOf(sigma: SigmaTable, metric: string, sex: Sex): number {
  const v = sigma[metric]?.[sex];
  if (v === undefined) throw new Error(`sigma[${metric}][${sex}] missing`);
  return v;
}

function l2(a: ArrayLike<number>, b: ArrayLike<number>): number {
  let s = 0;
  for (let k = 0; k < a.length; k++) {
    const t = a[k] - b[k];
    s += t * t;
  }
  return Math.sqrt(s);
}

function w1(ca: ArrayLike<number>, cb: ArrayLike<number>): number {
  let s = 0;
  for (let k = 0; k < ca.length; k++) s += Math.abs(ca[k] - cb[k]);
  return BIN_WIDTH * s;
}

/** Δ = a − b, then the sex view (42 for sex '2', s21 for sex '1'), into `out`. */
function deltaView(a: Float64Array, b: Float64Array, sex: Sex, out: Float64Array): Float64Array {
  if (sex === '2') for (let k = 0; k < N_DIMS; k++) out[k] = a[k] - b[k];
  else for (let k = 0; k < N_BINS; k++) out[k] = a[k] - b[k] + (a[N_BINS + k] - b[N_BINS + k]);
  return out;
}

/** Per-row transforms of one snapshot vector, held in reusable buffers (one set per side; refilled per row). */
interface Prepared {
  v: Float64Array; // s42 (42)
  x: Float64Array; // the sex view: aliases `v` for sex '2', an s21 buffer for sex '1'
  cdf: Float64Array; // w1 side: per-sex CDF (42) or total CDF (21)
  aux: Float64Array | null; // smoothed x / √x / z-features / s21 for w1 & w1bal
}

const N_FEAT = NUMERIC_FEATURES.length;

/** Gaussian smoothing of one age profile into `out` (nearest padding), `metrics.smooth` per block. */
function smoothInto(x: Float64Array, off: number, n: number, out: Float64Array): void {
  for (let i = 0; i < n; i++) {
    let acc = 0;
    for (let j = 0; j < KERNEL.length; j++) {
      let idx = i + j - 2;
      if (idx < 0) idx = 0;
      else if (idx >= n) idx = n - 1;
      acc += KERNEL[j] * x[off + idx];
    }
    out[off + i] = acc;
  }
}

class Space {
  readonly metric: Metric | 'trend' | 'path';
  private readonly stats: FeatureStats | null;
  private readonly emb: Float32Array | null;
  private readonly lags: number[];
  private readonly sigL2: number;
  private readonly sigW1: number;
  private readonly sigTrend: number;

  constructor(
    readonly view: FullView,
    ents: readonly Entity[],
    readonly q: SearchQuery,
    readonly sigma: SigmaTable,
    opts: SearchOpts,
  ) {
    checkQuery(q);
    this.metric = q.trend === 'motion' ? 'trend' : q.trend === 'path' ? 'path' : q.metric;
    this.lags = q.trend === 'motion' ? [q.L] : q.trend === 'path' ? Array.from({ length: q.L / 5 }, (_, i) => 5 * (i + 1)) : [];
    this.emb = opts.emb ?? null;
    if (this.metric === 'visual' && !this.emb) throw new Error("metric 'visual' needs opts.emb (loadEmbedding(model).values)");
    this.stats = this.metric === 'feat' ? featureStats(view, ents, q.year, q.scope, q.minpop) : null;
    const needBlend = this.metric === 'blend' || this.metric === 'path';
    this.sigL2 = needBlend ? sigmaOf(sigma, 'l2', q.sex) : 1;
    this.sigW1 = needBlend ? (q.sex === '2' ? sigmaOf(sigma, 'w1sex', '2') : sigmaOf(sigma, 'w1', '1')) : 1;
    this.sigTrend = this.metric === 'trend' ? sigmaOf(sigma, `trend@${q.L}`, q.sex) : 1;
  }

  /** Buffers for one side, sized for this metric × sex. */
  private newPrepared(): Prepared {
    const v = new Float64Array(N_DIMS);
    const two = this.q.sex === '2';
    const x = two ? v : new Float64Array(N_BINS);
    const m = this.metric;
    let cdf = new Float64Array(0);
    let aux: Float64Array | null = null;
    if (m === 'blend' || m === 'path' || m === 'w1sex') cdf = new Float64Array(two ? N_DIMS : N_BINS);
    else if (m === 'w1' || m === 'w1bal') {
      cdf = new Float64Array(N_BINS);
      aux = two ? new Float64Array(N_BINS) : x; // s21 (already `x` for sex '1')
    } else if (m === 'l2s' || m === 'hel') aux = new Float64Array(x.length);
    else if (m === 'feat') aux = new Float64Array(N_FEAT);
    return { v, x, cdf, aux };
  }

  /** Fill `p` with the transforms of `row` (no allocation except for `feat`, whose features() builds an object). */
  private prepare(row: number, p: Prepared = this.newPrepared()): Prepared {
    const { v, x, cdf, aux } = p;
    vectorAt(this.view, row, v);
    const two = this.q.sex === '2';
    if (!two) for (let k = 0; k < N_BINS; k++) x[k] = v[k] + v[N_BINS + k];
    const m = this.metric;
    if (m === 'blend' || m === 'path' || m === 'w1sex') {
      if (two) {
        let cm = 0;
        let cf = 0;
        for (let k = 0; k < N_BINS; k++) {
          cm += v[k];
          cf += v[N_BINS + k];
          cdf[k] = cm;
          cdf[N_BINS + k] = cf;
        }
      } else {
        let c = 0;
        for (let k = 0; k < N_BINS; k++) {
          c += x[k];
          cdf[k] = c;
        }
      }
    } else if (m === 'w1' || m === 'w1bal') {
      const a = aux!;
      if (two) for (let k = 0; k < N_BINS; k++) a[k] = v[k] + v[N_BINS + k];
      let c = 0;
      for (let k = 0; k < N_BINS; k++) {
        c += a[k];
        cdf[k] = c;
      }
    } else if (m === 'l2s') {
      if (two) {
        smoothInto(x, 0, N_BINS, aux!);
        smoothInto(x, N_BINS, N_BINS, aux!);
      } else smoothInto(x, 0, N_BINS, aux!);
    } else if (m === 'hel') {
      const a = aux!;
      for (let k = 0; k < x.length; k++) a[k] = Math.sqrt(x[k]);
    } else if (m === 'feat') {
      const f = numericVector(features(v));
      const st = this.stats!;
      for (let j = 0; j < N_FEAT; j++) aux![j] = (f[j] - st.mu[j]) / st.sd[j];
    }
    return p;
  }

  private blend(a: Prepared, b: Prepared): number {
    return 0.5 * (l2(a.x, b.x) / this.sigL2) + 0.5 * (w1(a.cdf, b.cdf) / this.sigW1);
  }

  private snapshot(a: Prepared, b: Prepared, rowA: number, rowB: number): number {
    switch (this.metric) {
      case 'blend':
        return this.blend(a, b);
      case 'l2':
        return l2(a.x, b.x);
      case 'w1':
        return w1(a.cdf, b.cdf);
      case 'w1sex':
        return w1(a.cdf, b.cdf);
      case 'l2s':
        return l2(a.aux!, b.aux!);
      case 'hel':
        return l2(a.aux!, b.aux!) / Math.SQRT2;
      case 'feat':
        return l2(a.aux!, b.aux!);
      case 'w1bal': {
        let d = w1(a.cdf, b.cdf);
        if (this.q.sex === '2') {
          const a21 = a.aux!;
          const b21 = b.aux!;
          let s = 0;
          for (let k = 0; k < N_BINS; k++) {
            const ra = a21[k] > 0 ? a.v[k] / a21[k] : 0.5;
            const rb = b21[k] > 0 ? b.v[k] / b21[k] : 0.5;
            s += 0.5 * (a21[k] + b21[k]) * Math.abs(ra - rb);
          }
          d += W1BAL_LAMBDA * s;
        }
        return d;
      }
      case 'visual': {
        const E = this.emb!;
        const oa = this.view.corpusRow(rowA) * 64;
        const ob = this.view.corpusRow(rowB) * 64;
        let dot = 0;
        let na = 0;
        let nb = 0;
        for (let k = 0; k < 64; k++) {
          const x = E[oa + k];
          const y = E[ob + k];
          dot += x * y;
          na += x * x;
          nb += y * y;
        }
        return 1 - dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-12);
      }
      default:
        throw new Error(`snapshot() called for ${this.metric}`);
    }
  }

  /**
   * Distances from `fromRow` to `targets` (default: every candidate row `[0, nRows)`), as a Float64Array aligned
   * with `targets`. Undefined lags give NaN, like the NaN-padded `lagged` matrix in Python.
   */
  fromRow(fromRow: number, targets?: Int32Array | null): Float64Array {
    const view = this.view;
    const n = targets ? targets.length : view.nRows;
    const out = new Float64Array(n);
    const at = (i: number) => (targets ? targets[i] : i);
    if (this.metric === 'trend') {
      const L = this.q.L;
      const qp = view.lagRow(fromRow, L);
      if (qp < 0) throw new Error(`trend: the ${view.yearOfRow(fromRow) - L} row of the query is not in the view`);
      const nd = this.q.sex === '2' ? N_DIMS : N_BINS;
      const dq = deltaView(vectorAt(view, fromRow), vectorAt(view, qp), this.q.sex, new Float64Array(nd));
      const dc = new Float64Array(nd);
      const cv = new Float64Array(N_DIMS);
      const pv = new Float64Array(N_DIMS);
      for (let i = 0; i < n; i++) {
        const r = at(i);
        const rp = view.lagRow(r, L);
        if (rp < 0) {
          out[i] = NaN;
          continue;
        }
        deltaView(vectorAt(view, r, cv), vectorAt(view, rp, pv), this.q.sex, dc);
        out[i] = l2(dq, dc) / this.sigTrend;
      }
      return out;
    }
    if (this.metric === 'path') {
      const qs = [this.prepare(fromRow)];
      for (const s of this.lags) {
        const qp = view.lagRow(fromRow, s);
        if (qp < 0) throw new Error(`path: the ${view.yearOfRow(fromRow) - s} row of the query is not in the view`);
        qs.push(this.prepare(qp));
      }
      const c = this.newPrepared();
      for (let i = 0; i < n; i++) {
        const r = at(i);
        let acc = this.blend(qs[0], this.prepare(r, c));
        let ok = true;
        for (let j = 0; j < this.lags.length; j++) {
          const rp = view.lagRow(r, this.lags[j]);
          if (rp < 0) {
            ok = false;
            break;
          }
          acc += this.blend(qs[j + 1], this.prepare(rp, c));
        }
        out[i] = ok ? acc / (1 + this.lags.length) : NaN;
      }
      return out;
    }
    const qp = this.prepare(fromRow);
    const c = this.newPrepared();
    for (let i = 0; i < n; i++) {
      const r = at(i);
      out[i] = this.snapshot(qp, this.prepare(r, c), fromRow, r);
    }
    return out;
  }
}

function queryRowOf(view: CorpusView, q: SearchQuery, opts: SearchOpts): number {
  const r = opts.queryRow ?? view.rowOf(q.id, q.year);
  if (r < 0) throw new Error(`(${q.id}, ${q.year}) is not in the view — inject it from the entity shard`);
  return r;
}

/**
 * Distances from the query row to every candidate row under the query's metric (`metrics.distances` semantics,
 * float64). `opts.queryRow` defaults to `view.rowOf(q.id, q.year)`; trend lags come from `view.lagRow`.
 */
export function distances(view0: CorpusView, q: SearchQuery, sigma: SigmaTable, opts: SearchOpts & { ents?: readonly Entity[] } = {}): Float64Array {
  const view = withGeometry(view0);
  const sp = new Space(view, opts.ents ?? allEntities, q, sigma, opts);
  return sp.fromRow(queryRowOf(view, q, opts));
}

// ------------------------------------------------------------------------------------------------ table + dedupe

interface Row {
  row: number;
  id: string;
  year: number;
  d: number;
  dy: number;
}

function table(sp: Space, ents: readonly Entity[], mask: Uint8Array, d: Float64Array): Row[] {
  const out: Row[] = [];
  const view = sp.view;
  for (let r = 0; r < view.nRows; r++) {
    if (!mask[r] || !Number.isFinite(d[r])) continue;
    const year = view.yearOfRow(r);
    out.push({ row: r, id: ents[view.entityOfRow(r)].id, year, d: d[r], dy: year - sp.q.year });
  }
  return out;
}

/** Sort key of `_dedupe`: d (asc, or desc when farthest), then |dy| asc, then year asc. */
function better(a: Row, b: Row, farthest: boolean): boolean {
  if (a.d !== b.d) return farthest ? a.d > b.d : a.d < b.d;
  const aa = Math.abs(a.dy);
  const ab = Math.abs(b.dy);
  if (aa !== ab) return aa < ab;
  return a.year < b.year;
}

/** One row per entity (best d, ties by year proximity), sorted the same way (`search._dedupe`). */
function dedupe(rows: Row[], farthest: boolean): Row[] {
  const best = new Map<string, Row>();
  for (const r of rows) {
    const cur = best.get(r.id);
    if (!cur || better(r, cur, farthest)) best.set(r.id, r);
  }
  return [...best.values()].sort((a, b) => (a === b ? 0 : better(a, b, farthest) ? -1 : 1));
}

function toResults(sp: Space, rows: Row[], ranks: number[], bands: Bands | null | undefined, opts: SearchOpts, kind: 'auto' | 'best' = 'auto'): SearchResult[] {
  const q = sp.q;
  const tm = tableMetric(q, opts.visualModel);
  const era = q.era; // resolved by the caller (see candidateMask)
  return rows.map((r, i) => {
    const b: BandResult = bandFor(bands, tm, q.sex, q.year, r.year, era, r.d, kind === 'best' ? 'best' : undefined);
    return { id: r.id, year: r.year, row: r.row, d: r.d, rankRaw: ranks[i], dy: r.dy, band: b.label, percentile: b.percentile };
  });
}

// ------------------------------------------------------------------------------------------------ queries

/** The `k` nearest entities (best year each) under the query's metric, sorted by d; own entity excluded. */
export function similar(view0: CorpusView, ents: readonly Entity[], q: SearchQuery, sigma: SigmaTable, bands?: Bands | null, opts: SearchOpts = {}): SearchResult[] {
  const view = withGeometry(view0);
  const sp = new Space(view, ents, q, sigma, opts);
  const mask = candidateMask(view, ents, q, opts.lastObservedYear);
  const rows = dedupe(table(sp, ents, mask, sp.fromRow(queryRowOf(view, q, opts))), false).slice(0, q.k);
  return toResults(sp, rows, rows.map((_, i) => i + 1), bands, opts);
}

/**
 * MMR over the farthest-first deduped table `t` (PLAN §5): pool = min(max(⌈0.25·n⌉, k), 2000) farthest; greedy
 * argmax d(q,x) + div·min_{s∈S} d(x,s), first index wins ties; div = 0 reproduces the strict order. Returns the picks
 * sorted by d descending with their plain farthest ranks.
 */
function diversify(sp: Space, t: Row[], q: SearchQuery): { rows: Row[]; ranks: number[] } {
  if (t.length === 0) return { rows: [], ranks: [] };
  const pool = t.slice(0, Math.min(Math.max(Math.ceil(POOL_FRAC * t.length), q.k), MAX_POOL));
  const prow = Int32Array.from(pool, (r) => r.row);
  const chosen = [0];
  const picked = new Uint8Array(pool.length);
  picked[0] = 1;
  const minDs = new Float64Array(pool.length).fill(Infinity);
  const want = Math.min(q.k, pool.length);
  while (chosen.length < want) {
    const s = chosen[chosen.length - 1];
    const ds = sp.fromRow(prow[s], prow);
    let bestI = -1;
    let bestScore = -Infinity;
    for (let i = 0; i < pool.length; i++) {
      if (ds[i] < minDs[i]) minDs[i] = ds[i];
      if (picked[i]) continue;
      const score = pool[i].d + q.div * minDs[i];
      if (score > bestScore) {
        bestScore = score;
        bestI = i;
      }
    }
    if (bestI < 0) break; // every remaining score is NaN/−∞ (cannot happen with finite pool distances)
    picked[bestI] = 1;
    chosen.push(bestI);
  }
  const sel = [...chosen].sort((a, b) => a - b); // pool is sorted by d desc ⇒ ascending index = descending d
  return { rows: sel.map((i) => pool[i]), ranks: sel.map((i) => i + 1) };
}

/**
 * Diversified farthest-k (MMR) + the strict farthest-k strip. Sorted by d descending; `rankRaw` = plain farthest rank.
 */
export function different(view0: CorpusView, ents: readonly Entity[], q: SearchQuery, sigma: SigmaTable, bands?: Bands | null, opts: SearchOpts = {}): { results: SearchResult[]; strict: SearchResult[] } {
  const view = withGeometry(view0);
  const sp = new Space(view, ents, q, sigma, opts);
  const mask = candidateMask(view, ents, q, opts.lastObservedYear);
  const t = dedupe(table(sp, ents, mask, sp.fromRow(queryRowOf(view, q, opts))), true);
  const strictRows = t.slice(0, q.k);
  const strict = toResults(sp, strictRows, strictRows.map((_, i) => i + 1), bands, opts);
  const { rows, ranks } = diversify(sp, t, q);
  return { results: toResults(sp, rows, ranks, bands, opts), strict };
}

/** `similar` + `different` + the raw distance vector from ONE scan — what the page runs per query. */
export interface SearchBoth {
  similar: SearchResult[];
  different: SearchResult[];
  strict: SearchResult[];
  /** d(query, row) for every view row `[0, nRows)` (own entity's rows included — the own-trajectory row reads them). */
  d: Float64Array;
  nCandidates: number;
}

/**
 * One scan for the whole results section: identical to `similar()` and `different()` called separately (same
 * Space, mask, table and dedupe), but the 42k-row distance pass runs once instead of three times (the store used to
 * call `similar`, `different` and `distances` for the own-trajectory row).
 */
export function search(view0: CorpusView, ents: readonly Entity[], q: SearchQuery, sigma: SigmaTable, bands?: Bands | null, opts: SearchOpts = {}): SearchBoth {
  const view = withGeometry(view0);
  const sp = new Space(view, ents, q, sigma, opts);
  const mask = candidateMask(view, ents, q, opts.lastObservedYear);
  const d = sp.fromRow(queryRowOf(view, q, opts));
  const rows = table(sp, ents, mask, d);
  const near = dedupe(rows, false).slice(0, q.k);
  const far = dedupe(rows, true);
  const strictRows = far.slice(0, q.k);
  const mm = diversify(sp, far, q);
  let nCandidates = 0;
  for (let r = 0; r < mask.length; r++) if (mask[r]) nCandidates++;
  return {
    similar: toResults(sp, near, near.map((_, i) => i + 1), bands, opts),
    different: toResults(sp, mm.rows, mm.ranks, bands, opts),
    strict: toResults(sp, strictRows, strictRows.map((_, i) => i + 1), bands, opts),
    d,
    nCandidates,
  };
}

/**
 * Time-shift table: for every other entity in scope, `y* = argmin_y d(q, c_y)` over the allowed era (mode forced
 * to `any`, everything else as in `q`), sorted by d; `boundaryHit` when y* is the first or last allowed year of that
 * entity. Banded against the `best` null. Needs a corpus view (all years).
 */
export function bestYearPerEntity(view0: CorpusView, ents: readonly Entity[], q: SearchQuery, sigma: SigmaTable, bands?: Bands | null, opts: SearchOpts = {}): TimeShiftRow[] {
  const view = withGeometry(view0);
  const qa: SearchQuery = { ...q, mode: 'any' };
  const sp = new Space(view, ents, qa, sigma, opts);
  const mask = candidateMask(view, ents, qa, opts.lastObservedYear);
  const rows = table(sp, ents, mask, sp.fromRow(queryRowOf(view, qa, opts)));
  const edges = new Map<string, [number, number]>();
  for (const r of rows) {
    const e = edges.get(r.id);
    if (!e) edges.set(r.id, [r.year, r.year]);
    else {
      if (r.year < e[0]) e[0] = r.year;
      if (r.year > e[1]) e[1] = r.year;
    }
  }
  const best = dedupe(rows, false);
  const tm = tableMetric(qa, opts.visualModel);
  const era = qa.era;
  return best.map((r) => {
    const [lo, hi] = edges.get(r.id)!;
    const b = bandFor(bands, tm, qa.sex, qa.year, r.year, era, r.d, 'best');
    return { id: r.id, bestYear: r.year, row: r.row, d: r.d, dy: r.dy, boundaryHit: r.year === lo || r.year === hi, band: b.label, percentile: b.percentile };
  });
}

/**
 * Isolation of every country of `year` with total ≥ minpop: mean distance to its `k` nearest same-year countries
 * (`search.isolation`; `feat` z-scores against that same set). Map id → isolation, insertion order = most isolated first.
 */
export function isolation(
  view0: CorpusView,
  ents: readonly Entity[],
  year: number,
  metric: Metric,
  sigma: SigmaTable,
  sex: Sex = '2',
  opts: SearchOpts & { k?: number; minpop?: number } = {},
): Map<string, number> {
  const view = withGeometry(view0);
  const k = opts.k ?? 5;
  const minpop = opts.minpop ?? MINPOP_DEFAULT;
  const rows: number[] = [];
  for (let r = 0; r < view.nRows; r++) {
    if (view.yearOfRow(r) === year && ents[view.entityOfRow(r)].type === 'country' && view.totals[r] >= minpop) rows.push(r);
  }
  const q = defaultQuery('', year, year, { metric, sex, minpop, scope: 'c', era: 'all' });
  const sp = new Space(view, ents, q, sigma, opts);
  const targets = Int32Array.from(rows);
  const out: Array<[string, number]> = [];
  for (let i = 0; i < rows.length; i++) {
    const d = sp.fromRow(rows[i], targets);
    d[i] = Infinity;
    const sorted = Array.from(d).sort((a, b) => a - b).slice(0, k);
    out.push([ents[view.entityOfRow(rows[i])].id, sorted.reduce((a, b) => a + b, 0) / sorted.length]);
  }
  out.sort((a, b) => b[1] - a[1]);
  return new Map(out);
}

/** Share of the OTHER countries less isolated than `id` (0–100): "more isolated than 91 % of countries this year". */
export function isolationPercentile(iso: Map<string, number>, id: string): number | null {
  const own = iso.get(id);
  if (own === undefined || iso.size < 2) return null;
  let below = 0;
  for (const [k, v] of iso) if (k !== id && v < own) below++;
  return (100 * below) / (iso.size - 1);
}
