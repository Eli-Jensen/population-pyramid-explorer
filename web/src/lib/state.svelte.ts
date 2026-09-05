// App store (PLAN §7/§8): one class with $state runes, in Eli's retiremap style.
// Owns the route/query, the current-year clock, the tier-1 shards (entity shard + year shard) and the
// derived pyramid/features/axis. Pure math lives in lib/math/*, fetching in lib/data.ts. History semantics:
// replaceState while dragging the year slider, one pushState on release (Back returns to the pre-drag
// year); pushState on entity change; replaceState for display-option tweaks, constraint changes and
// canonicalising redirects.
//
// M2 (PLAN §5–§6): the search constraints ride on the query (router.SearchOptions). Data flow —
//   · same-year / today / trend searches run over a year-shard view (`engine.fromShards`: the candidate year τ,
//     the query year when it differs, and the τ−L / year−L lag shards for trend) — no blob;
//   · near / range / any and the time-shift panel load the whole corpus (tier 3) once;
//   · `bands_default` covers same/blend/two-sex; any other metric / mode / the time-shift panel loads `bands`;
//   · the Visual metric loads the exposed image embedding lazily.
// Results are a `$derived.by` over the engine seam (lib/engine.ts) keyed on `searchYear`, a copy of the year
// that trails the slider by 30 ms while dragging (`setYear(commit:false)` schedules it), so a drag costs one
// scan per 30 ms, not one per input event.
//
// M3 (PLAN §7 J4/J5): the compare route `/compare/{a}/{ya}/{b}/{yb|best}` rides on the same store. Both pyramids
// paint from their ENTITY shards (scrubbing either side needs no fetch); the pair card (d, band, explanation, feature
// table) is computed on a view that holds A's year (the z-score reference) and B's row — the corpus when it is loaded,
// otherwise the two YEAR shards (yb as candidates, ya as reference), keyed on `pairYears`, the debounced copy of the
// two years. `best` is resolved client-side: the corpus (tier 3) is fetched once, `y* = argmin_y d(A_ya, B_y)` over
// the allowed era (the time-shift table's rule, lib/compare.ts), then the URL is replaceState'd to the concrete year
// + `?from=best` so the button stays lit and Copy-link never emits `best` (J6).

import {
  byId,
  currentYear as clockYear,
  eraOf,
  idxOf,
  meta,
  N_DIMS,
  YEAR_MAX,
  YEAR_MIN,
  clampYear,
  systemClock,
  type Clock,
  type Entity,
  type Era,
} from './entities.ts';
import {
  entityShardPyramid,
  loadBands,
  loadBandsDefault,
  loadCorpus,
  loadEmbedding,
  loadEntityShard,
  loadYearShard,
  sharesAt,
  yearShardPyramid,
} from './data.ts';
import { features as computeFeatures, type Features } from './math/features.ts';
import { axisFor, maxBinPct, type AxisChoice, type AxisMode } from './math/scale.ts';
import {
  compareQuery,
  countryQuery,
  DEFAULT_SEARCH,
  effectiveEra,
  isCompare,
  isCountry,
  visualExposed,
  type Axis,
  type CompareInput,
  type CompareQuery,
  type CountryQuery,
  type DisplayOptions,
  type EraMode,
  type Query,
  type Route,
  type SearchInput,
  type SearchOptions,
} from './router.ts';
import {
  bestYearFor,
  bestYearWindow,
  compareAxis,
  compareBandsDefaultSuffice,
  isConcrete,
  nextYears,
  pairData,
  pairSearchQuery,
  swapQuery,
  type BestYear,
  type CompareAxis,
  type PairData,
} from './compare.ts';
import {
  engine as productionEngine,
  type BandResult,
  type CorpusView,
  type Engine,
  type Explanation,
  type FeatureStats,
  type SearchQuery,
  type SearchResult,
  type TimeShiftRow,
} from './engine.ts';
import { eraEdge, trendReason } from './restate.ts';
import type { Bands, Corpus, Embedding, EntityShard, Pyramid, YearShard } from './types.ts';
import { currentHref, currentRoute, navigate, navigateTo, onPopState, type Env } from './url.ts';

export type { EntityShard, Features, Pyramid, YearShard };

/** The pyramid on screen: `Pyramid` (42 shares of total + total in thousands) plus provenance. */
export interface PyramidView extends Pyramid {
  id: string;
  year: number;
  u16: Uint16Array; // the quantised row (view into the shard), Σ = 65535
  source: 'entity' | 'year'; // which shard it came from
}

export function pyramidFromEntityShard(shard: EntityShard, year: number): PyramidView {
  const row = year - YEAR_MIN;
  return {
    ...entityShardPyramid(shard, year),
    id: shard.id,
    year,
    u16: shard.u16.subarray(row * N_DIMS, (row + 1) * N_DIMS),
    source: 'entity',
  };
}
export function pyramidFromYearShard(shard: YearShard, id: string): PyramidView | null {
  const row = idxOf(id);
  if (row < 0 || row >= shard.n) return null;
  return {
    ...yearShardPyramid(shard, row),
    id,
    year: shard.year,
    u16: shard.u16.subarray(row * N_DIMS, (row + 1) * N_DIMS),
    source: 'year',
  };
}

/** URL axis vocabulary (router) → math/scale.ts mode. */
export function toAxisMode(axis: Axis): AxisMode {
  return axis === 'noclip' ? 'never' : axis;
}

// ---- search result views --------------------------------------------------------------------------------

/** One result card's worth of data (ResultCard.svelte renders it; nothing here touches the engine again). */
export interface CardData {
  result: SearchResult;
  entity: Entity;
  shares: Float32Array; // candidate's 42 shares
  delta: Float32Array; // candidate − query per bin (DiffBars)
  projected: boolean; // candidate year > current year
  explanation: Explanation | null; // decomposition + 'similar because …' / 'differs in …' / W1 sentence (null for trend)
  trend: string | null; // side-by-side L-year movements (trend mode)
}

export interface OwnTrajectory {
  year: number;
  dy: number;
  d: number;
  band: BandResult;
  shares: Float32Array;
}

export interface SearchOutput {
  q: SearchQuery;
  nCandidates: number;
  twins: CardData[];
  opposites: CardData[];
  strict: SearchResult[]; // plain farthest-k, for the 'strictly farthest' strip
  own: OwnTrajectory | null;
  ms: number; // wall time of the scan + explanations (SMOKE)
  source: 'shards' | 'corpus';
}

export type CorpusStatus = 'idle' | 'loading' | 'ready' | 'error';

/** True when `bands_default` (same/blend/two-sex) is enough for this query. */
export function defaultBandsSuffice(s: Pick<SearchOptions, 'mode' | 'metric' | 'sex' | 'trend'>): boolean {
  return s.mode === 'same' && s.metric === 'blend' && s.sex === '2' && !s.trend;
}

// ---- injectable collaborators ------------------------------------------------------------------------

export interface DataSource {
  entityShard(id: string): Promise<EntityShard>;
  yearShard(year: number): Promise<YearShard>;
  // M2 tiers (optional so M1-style fakes still type-check; the store treats a missing loader as "unavailable")
  bandsDefault?(): Promise<Bands>;
  bands?(): Promise<Bands>;
  corpus?(): Promise<Corpus>;
  embedding?(model: string): Promise<Embedding>;
}
/** Production source: lib/data.ts loaders (memoised, BASE_URL-aware). */
export const dataSource: DataSource = {
  entityShard: loadEntityShard,
  yearShard: loadYearShard,
  bandsDefault: loadBandsDefault,
  bands: loadBands,
  corpus: loadCorpus,
  embedding: (model) => loadEmbedding(model),
};

export type FeaturesFn = (shares: Float32Array) => Features;

export interface AppStateOptions {
  clock?: Clock;
  data?: DataSource;
  env?: Env; // history/location/popstate-target/base injection for tests
  features?: FeaturesFn; // defaults to math/features.ts
  engine?: Engine | null; // null = no search (M1 behaviour); defaults to the production engine
  debounceMs?: number; // slider → search delay (30)
}

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

// ---- store ----------------------------------------------------------------------------------------------

export class AppState {
  route = $state<Route>({ kind: 'home' });
  currentYear = $state(clockYear());
  entityShard = $state<EntityShard | null>(null);
  yearShard = $state<YearShard | null>(null);
  loading = $state(false);
  error = $state<string | null>(null);

  // M2 data tiers
  /** Debounced copy of `year` that the search follows (trails the slider by `debounceMs` while dragging). */
  searchYear = $state(clockYear());
  shardsVersion = $state(0); // bumped whenever a year shard lands in the cache
  corpus = $state.raw<Corpus | null>(null);
  corpusStatus = $state<CorpusStatus>('idle');
  corpusError = $state<string | null>(null);
  bandsDefault = $state.raw<Bands | null>(null);
  bandsAll = $state.raw<Bands | null>(null);
  embedding = $state.raw<Embedding | null>(null);
  embeddingStatus = $state<CorpusStatus>('idle');
  timeShiftOpen = $state(false);

  // M3 compare
  shardA = $state<EntityShard | null>(null);
  shardB = $state<EntityShard | null>(null);
  /** Debounced copy of the compare years the pair card follows (null while `yb` is still `best`). */
  pairYears = $state<{ ya: number; yb: number } | null>(null);
  /** Lock-offset toggle of the two scrubbers (UI state, not in the URL). */
  lockOffset = $state(false);

  readonly lastObservedYear = meta.last_observed_year;
  readonly visualModel: string | null = meta.verdicts?.exposed_visual?.model ?? null;

  // collaborators (declared before the $derived fields that read them)
  private clock: Clock = systemClock;
  private data: DataSource = dataSource;
  private env: Env = {};
  private featuresFn: FeaturesFn = computeFeatures;
  private engine: Engine | null = productionEngine;
  private debounceMs = 30;
  private entityCache = new Map<string, EntityShard>();
  private yearCache = new Map<number, YearShard>();
  private pendingYears = new Map<number, Promise<YearShard>>(); // in-flight year-shard fetches (deduped across load paths)
  private isolationCache = new Map<string, Map<string, number>>();
  private gen = 0; // staleness token for in-flight loads
  private dragFrom: string | null = null; // href before the current slider drag
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private unsub: (() => void) | null = null;

  query = $derived<CountryQuery | null>(isCountry(this.route) ? this.route : null);
  entity = $derived<Entity | null>(this.query ? (byId(this.query.id) ?? null) : null);
  year = $derived(this.query?.year ?? this.currentYear);
  options = $derived<DisplayOptions>({ axis: this.query?.axis ?? 'fit', unit: this.query?.unit ?? 'pct' });
  era = $derived<Era>(eraOf(this.year, this.currentYear, this.lastObservedYear));
  isProjected = $derived(this.year > this.currentYear);

  /** The pyramid on screen: entity shard first (scrubbing needs no fetch), year shard as a fallback. */
  pyramid = $derived.by<PyramidView | null>(() => {
    const q = this.query;
    if (!q) return null;
    if (this.entityShard?.id === q.id) return pyramidFromEntityShard(this.entityShard, q.year);
    if (this.yearShard?.year === q.year) return pyramidFromYearShard(this.yearShard, q.id);
    return null;
  });
  features = $derived<Features | null>(this.pyramid ? this.featuresFn(this.pyramid.shares) : null);

  axisMode = $derived<AxisMode>(toAxisMode(this.options.axis));
  /** Fixed symmetric axis (PLAN §2): fit → entities[].axis_pct (widened only if the drawn year overflows),
   *  pin10 → 10 % with a clip marker, never → 17 %. `clips` tells the chart to draw the ▸ marker. */
  axis = $derived<AxisChoice>(
    axisFor(this.axisMode, this.entity?.axis_pct ?? 10, this.pyramid ? maxBinPct(this.pyramid.shares) : 0),
  );
  axisPct = $derived(this.axis.axisPct);

  // ---- M2 derived: constraints → data needs → results ---------------------------------------------------

  /** The search constraints of the current query (defaults when off the country page). */
  search = $derived<SearchOptions>(this.query ? pickSearch(this.query) : DEFAULT_SEARCH);
  /** The era the search uses: the explicit URL value or the J8 default. */
  searchEra = $derived<EraMode>(this.query ? effectiveEra(this.query, this.currentYear) : 'obs');
  /** The single candidate year of a shard-only search (same / today); null when the search spans years. */
  singleYear = $derived.by<number | null>(() => {
    const s = this.search;
    if (s.mode === 'same') return this.searchYear;
    if (s.mode === 'range' && s.from !== null && s.from === s.to) return s.from;
    return null;
  });
  /** Whether the whole corpus is required (cross-year modes, or the open time-shift panel). */
  needsCorpus = $derived(this.singleYear === null || this.timeShiftOpen);
  /** Year shards a shard-only search needs: τ (candidates), the query year (`feat` reference, today's query row) and
   *  the trend lags of both — a handful of 24 KB shards, no entity-shard dependency. */
  requiredYears = $derived.by<number[]>(() => {
    const tau = this.singleYear;
    if (tau === null || !this.engine) return [];
    const s = this.search;
    const ys = new Set<number>([tau, this.searchYear]);
    for (const y of [...this.engine.lagYears(tau, s.trend, s.L), ...this.engine.lagYears(this.searchYear, s.trend, s.L)]) ys.add(y);
    return [...ys].filter((y) => y >= YEAR_MIN && y <= YEAR_MAX).sort((a, b) => a - b);
  });
  needsAllBands = $derived(!defaultBandsSuffice(this.search) || this.timeShiftOpen);
  needsEmbedding = $derived(this.search.metric === 'visual' && this.visualModel !== null);

  /** The engine's query (minpop in thousands, era resolved, debounced year). */
  searchQuery = $derived.by<SearchQuery | null>(() => {
    const q = this.query;
    if (!q || !this.engine) return null;
    const s = this.search;
    return {
      id: q.id,
      year: this.searchYear,
      mode: s.mode,
      n: s.n,
      from: s.mode === 'range' ? (s.from ?? YEAR_MIN) : undefined,
      to: s.mode === 'range' ? (s.to ?? YEAR_MAX) : undefined,
      era: effectiveEra({ year: this.searchYear, era: q.era }, this.currentYear),
      scope: s.scope,
      minpop: s.minpop / 1000,
      metric: s.metric,
      sex: s.sex,
      k: s.k,
      div: s.div,
      trend: s.trend,
      L: s.L,
      currentYear: this.currentYear,
    };
  });

  /** Bands table to hand the engine: the full file when loaded, else the first-paint default. */
  bands = $derived<Bands | null>(this.bandsAll ?? this.bandsDefault);
  /** Whether the percentile tables the current query needs are in hand. */
  bandsReady = $derived(this.needsAllBands ? this.bandsAll !== null : this.bandsDefault !== null);

  /** The rows the search runs over, or null while data is missing. Corpus when loaded; year shards otherwise. */
  view = $derived.by<CorpusView | null>(() => {
    const q = this.searchQuery;
    const tau = this.singleYear;
    if (!q || !this.engine) return null;
    if (this.corpus) return this.engine.fromCorpus(this.corpus);
    if (this.needsCorpus || tau === null) return null;
    void this.shardsVersion; // re-derive as shards land
    const shards = this.requiredYears.map((y) => this.yearCache.get(y));
    if (shards.some((s) => !s)) return null;
    const main = this.yearCache.get(tau)!;
    return this.engine.fromShards(main, shards.filter((s): s is YearShard => !!s && s.year !== tau));
  });
  viewSource = $derived<'shards' | 'corpus'>(this.corpus ? 'corpus' : 'shards');

  /** Twins, opposites, strict strip and own-trajectory row for the current query (plus the engine error, if any). */
  private searchRun = $derived.by<{ output: SearchOutput | null; error: string | null }>(() => {
    const q = this.searchQuery;
    const view = this.view;
    const eng = this.engine;
    if (!q || !view || !eng) return { output: null, error: null };
    if (this.needsEmbedding && !this.embedding) return { output: null, error: null };
    const queryRow = view.rowOf(q.id, q.year);
    if (queryRow < 0) return { output: null, error: null };
    const opts = { queryRow, emb: this.needsEmbedding ? this.embedding!.values : undefined };
    const bands = this.bands;
    const t0 = now();
    try {
      const { similar: twins, different: opposites, strict, d, nCandidates } = eng.search(view, q, bands, opts);
      const own = this.corpus ? this.ownTrajectory(view, q, d, bands) : null;
      const stats = q.trend ? undefined : eng.featureStats(view, q.year, q.scope, q.minpop);
      const cards = (rs: SearchResult[]) => rs.map((r) => this.card(view, q, queryRow, r, stats));
      const out: SearchOutput = { q, nCandidates, twins: cards(twins), opposites: cards(opposites), strict, own, ms: 0, source: this.viewSource };
      out.ms = now() - t0;
      return { output: out, error: null };
    } catch (e) {
      return { output: null, error: e instanceof Error ? e.message : String(e) };
    }
  });
  results = $derived<SearchOutput | null>(this.searchRun.output);
  searchError = $derived<string | null>(this.searchRun.error);

  /** Time-shift table (PLAN §6): best year per other entity over the allowed era, sorted by d. Corpus only. */
  timeShift = $derived.by<TimeShiftRow[] | null>(() => {
    const q = this.searchQuery;
    const eng = this.engine;
    if (!this.timeShiftOpen || !q || !eng || !this.corpus) return null;
    if (this.needsEmbedding && !this.embedding) return null;
    const view = eng.fromCorpus(this.corpus);
    const queryRow = view.rowOf(q.id, q.year);
    if (queryRow < 0) return null;
    try {
      return eng.bestYearPerEntity(view, { ...q, mode: 'any' }, this.bandsAll, { queryRow, emb: this.needsEmbedding ? this.embedding!.values : undefined });
    } catch {
      return null;
    }
  });

  /** Distinctiveness: percentile of the focal country's isolation among same-year countries ≥ 100k (PLAN §5).
   *  Runs over the focal year's shard alone (198 × 198 distances), memoised per (year, metric, sex, trend). */
  isolationPercentile = $derived.by<number | null>(() => {
    const q = this.searchQuery;
    const eng = this.engine;
    const e = this.entity;
    if (!q || !eng || !e || e.type !== 'country') return null;
    if (this.needsEmbedding && !this.embedding) return null;
    void this.shardsVersion;
    const year = q.year;
    const key = `${year}|${q.metric}|${q.sex}|${q.trend ?? ''}|${q.L}`;
    let iso = this.isolationCache.get(key);
    if (!iso) {
      const main = this.yearCache.get(year);
      if (!main) return null;
      const lags = eng.lagYears(year, q.trend, q.L).map((y) => this.yearCache.get(y));
      if (lags.some((s) => !s)) return null;
      try {
        const view = eng.fromShards(main, lags as YearShard[]);
        iso = eng.isolation(view, year, q.metric, q.sex, { emb: this.needsEmbedding ? this.embedding!.values : undefined });
      } catch {
        return null;
      }
      this.isolationCache.set(key, iso);
    }
    return eng.isolationPercentile(iso, e.id);
  });

  // ---- M3 derived: compare page --------------------------------------------------------------------------

  compare = $derived<CompareQuery | null>(isCompare(this.route) ? this.route : null);
  entityA = $derived<Entity | null>(this.compare ? (byId(this.compare.a) ?? null) : null);
  entityB = $derived<Entity | null>(this.compare ? (byId(this.compare.b) ?? null) : null);
  /** A's pyramid at ya: entity shard first (scrubbing), the ya year shard as a first-paint fallback. */
  pyramidA = $derived.by<PyramidView | null>(() => {
    const c = this.compare;
    if (!c) return null;
    if (this.shardA?.id === c.a) return pyramidFromEntityShard(this.shardA, c.ya);
    void this.shardsVersion;
    const ys = this.yearCache.get(c.ya);
    return ys ? pyramidFromYearShard(ys, c.a) : null;
  });
  /** B's pyramid at yb (null while `best` is unresolved). */
  pyramidB = $derived.by<PyramidView | null>(() => {
    const c = this.compare;
    if (!c || c.yb === 'best') return null;
    if (this.shardB?.id === c.b) return pyramidFromEntityShard(this.shardB, c.yb);
    void this.shardsVersion;
    const ys = this.yearCache.get(c.yb);
    return ys ? pyramidFromYearShard(ys, c.b) : null;
  });
  /** Axis = max of the pair's fits, widened only if a drawn year overflows (caption reads `widened`). */
  pairAxis = $derived<CompareAxis | null>(
    this.compare
      ? compareAxis(toAxisMode(this.compare.axis), this.entityA?.axis_pct ?? 10, this.entityB?.axis_pct ?? 10, this.pyramidA?.shares ?? null, this.pyramidB?.shares ?? null)
      : null,
  );
  /** The corpus is needed to resolve `best` (and to confirm a pasted `from=best`). */
  compareNeedsCorpus = $derived(!!this.compare && (this.compare.yb === 'best' || this.compare.from === 'best'));
  compareNeedsAllBands = $derived(!!this.compare && !compareBandsDefaultSuffice(this.compare));
  compareNeedsEmbedding = $derived(this.compare?.metric === 'visual' && this.visualModel !== null);
  compareBandsReady = $derived(this.compareNeedsAllBands ? this.bandsAll !== null : this.bandsDefault !== null);

  /** View for the pair card: the corpus when loaded, else year shards (yb = candidates, ya = reference). */
  pairView = $derived.by<CorpusView | null>(() => {
    const c = this.compare;
    const ys = this.pairYears;
    const eng = this.engine;
    if (!c || !ys || !eng) return null;
    if (this.corpus) return eng.fromCorpus(this.corpus);
    void this.shardsVersion;
    const main = this.yearCache.get(ys.yb);
    const ref = this.yearCache.get(ys.ya);
    if (!main || !ref) return null;
    return eng.fromShards(main, main.year === ref.year ? [] : [ref]);
  });

  private pairRun = $derived.by<{ pair: PairData | null; error: string | null }>(() => {
    const c = this.compare;
    const ys = this.pairYears;
    const view = this.pairView;
    const eng = this.engine;
    if (!c || !ys || !view || !eng) return { pair: null, error: null };
    if (this.compareNeedsEmbedding && !this.embedding) return { pair: null, error: null };
    const q = { ...c, ya: ys.ya, yb: ys.yb };
    try {
      const pair = pairData(eng, view, q, this.bands, {
        currentYear: this.currentYear,
        lastObserved: this.lastObservedYear,
        emb: this.compareNeedsEmbedding ? this.embedding!.values : undefined,
        visualModel: this.visualModel ?? undefined,
      });
      return { pair, error: null };
    } catch (e) {
      return { pair: null, error: e instanceof Error ? e.message : String(e) };
    }
  });
  /** d, band, explanation, feature table for (A_ya, B_yb) — trails the scrubbers by `debounceMs`. */
  pair = $derived<PairData | null>(this.pairRun.pair);
  pairError = $derived<string | null>(this.pairRun.error);

  /** B's best year for A's current year (corpus only): drives the `best` resolution and the button's lit state. */
  bestB = $derived.by<BestYear | null>(() => {
    const c = this.compare;
    const eng = this.engine;
    if (!c || !eng || !this.corpus || !this.compareNeedsCorpus) return null;
    if (this.compareNeedsEmbedding && !this.embedding) return null;
    const view = eng.fromCorpus(this.corpus);
    const rowA = view.rowOf(c.a, c.ya);
    if (rowA < 0) return null;
    try {
      const sq = pairSearchQuery(c, this.currentYear);
      const d = eng.distances(view, sq, { queryRow: rowA, emb: this.compareNeedsEmbedding ? this.embedding!.values : undefined, visualModel: this.visualModel ?? undefined });
      return bestYearFor(d, view, c.b, c.ya, bestYearWindow(c.ya, c.era, this.currentYear, this.lastObservedYear));
    } catch {
      return null;
    }
  });
  /** "B → best year" stays lit while the URL says `from=best` and the resolved year (once known) matches. */
  bestLit = $derived(!!this.compare && this.compare.from === 'best' && (this.bestB === null || this.bestB.year === this.compare.yb));

  constructor(opts: AppStateOptions = {}) {
    this.clock = opts.clock ?? systemClock;
    this.data = opts.data ?? dataSource;
    this.env = opts.env ?? {};
    this.featuresFn = opts.features ?? computeFeatures;
    this.engine = opts.engine === undefined ? productionEngine : opts.engine;
    this.debounceMs = opts.debounceMs ?? 30;
    this.currentYear = clockYear(this.clock);
    this.searchYear = this.currentYear;
  }

  /** Read the current location, canonicalise it, subscribe to Back/Forward and start loading. */
  init(): () => void {
    this.applyRoute(currentRoute(this.env, { clock: this.clock }));
    this.unsub?.();
    this.unsub = onPopState((r) => this.applyRoute(r, { fromHistory: true }), {
      ...this.env,
      parseOpts: { clock: this.clock },
    });
    return () => this.dispose();
  }

  dispose() {
    this.unsub?.();
    this.unsub = null;
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = null;
    this.gen++;
  }

  /** Adopt a parsed route. Redirects are applied with replaceState (aliases, case, hub year, defaults). */
  applyRoute(r: Route, { fromHistory = false }: { fromHistory?: boolean } = {}) {
    if (r.kind === 'redirect') {
      navigateTo(r.to, { replace: true, ...this.env });
      r = r.query;
    }
    this.route = r;
    this.dragFrom = null;
    if (!fromHistory) this.currentYear = clockYear(this.clock); // a long-lived tab crossing New Year
    this.syncSearchYear();
    void this.load();
  }

  /**
   * Set the year. `commit: false` while dragging → replaceState only, the search follows after `debounceMs`
   * (fetching that year's shard if needed); `commit: true` (release, keyboard step, play tick) → one pushState
   * relative to the pre-drag URL, then the shards load.
   */
  setYear(y: number, { commit = true }: { commit?: boolean } = {}) {
    const q = this.query;
    if (!q) return;
    const year = clampYear(y);
    const next = countryQuery(q.id, year, q, this.currentYear);
    if (!commit) {
      this.dragFrom ??= currentHref(this.env);
      this.route = next;
      navigate(next, { replace: true, ...this.env });
      this.scheduleSearchYear();
      return;
    }
    this.route = next;
    if (this.dragFrom !== null) {
      // rewind the replaceState trail so Back lands on the pre-drag year, then push the final one
      navigateTo(this.dragFrom, { replace: true, ...this.env });
      this.dragFrom = null;
    }
    navigate(next, { ...this.env });
    this.syncSearchYear();
    void this.load();
  }

  /** Switch entity, keeping year and options (pushState). Unknown ids are ignored. */
  setEntity(id: string) {
    const e = byId(id);
    if (!e) return;
    const q = this.query;
    const next = countryQuery(e.id, q?.year ?? this.currentYear, q ?? {}, this.currentYear);
    this.dragFrom = null;
    this.route = next;
    navigate(next, { ...this.env });
    this.syncSearchYear();
    void this.load();
  }

  /** Change a display option or a search constraint (replaceState — a view tweak, not a navigation step). */
  setOptions(o: Partial<DisplayOptions> & SearchInput) {
    const q = this.query;
    if (!q) return;
    const next = countryQuery(q.id, q.year, { ...q, ...o }, this.currentYear);
    this.route = next;
    navigate(next, { replace: true, ...this.env });
    this.syncSearchYear();
    void this.load();
  }

  /** Back to the default constraints (display options kept). */
  resetSearch() {
    this.setOptions({ ...DEFAULT_SEARCH });
  }

  /** Open / close the time-shift panel; opening fetches the corpus + bands (tier 3 / tier 2) once. */
  setTimeShiftOpen(open: boolean) {
    this.timeShiftOpen = open;
    if (open) void this.loadSearchData();
  }

  // ---- M3 compare actions ----------------------------------------------------------------------------------

  /**
   * Move one scrubber of the compare page. Lock-offset moves the other side too (Δ kept). Any year change drops
   * `from=best` (the resolved year is no longer the best for the new A). History as `setYear`: replaceState while
   * dragging, one pushState on release relative to the pre-drag URL.
   */
  setCompareYear(side: 'a' | 'b', y: number, { commit = true }: { commit?: boolean } = {}) {
    const c = this.compare;
    if (!c) return;
    const ybConcrete = c.yb === 'best' ? null : c.yb;
    let ya = c.ya;
    let yb: number | 'best' = c.yb;
    if (ybConcrete === null) {
      // B still unresolved: only A can move; keep resolving for the new A
      if (side === 'b') return;
      ya = clampYear(y);
    } else {
      const ys = nextYears({ ya: c.ya, yb: ybConcrete }, side, y, this.lockOffset);
      ya = ys.ya;
      yb = ys.yb;
    }
    const next = compareQuery(c.a, ya, c.b, yb, { ...c, from: null }, this.currentYear);
    if (!commit) {
      this.dragFrom ??= currentHref(this.env);
      this.route = next;
      navigate(next, { replace: true, ...this.env });
      this.scheduleSearchYear();
      return;
    }
    this.route = next;
    if (this.dragFrom !== null) {
      navigateTo(this.dragFrom, { replace: true, ...this.env });
      this.dragFrom = null;
    }
    navigate(next, { ...this.env });
    this.syncSearchYear();
    void this.load();
  }

  /** View / display option / metric tweak on the compare page (replaceState). Metric, sex or era changes drop `from=best`. */
  setCompareOptions(o: Partial<DisplayOptions> & CompareInput) {
    const c = this.compare;
    if (!c) return;
    const invalidatesBest = (o.metric !== undefined && o.metric !== c.metric) || (o.sex !== undefined && o.sex !== c.sex) || (o.era !== undefined && o.era !== c.era);
    const next = compareQuery(c.a, c.ya, c.b, c.yb, { ...c, ...o, from: invalidatesBest ? null : (o.from ?? c.from) }, this.currentYear);
    this.dragFrom = null;
    this.route = next;
    navigate(next, { replace: true, ...this.env });
    this.syncSearchYear();
    void this.load();
  }

  /** A ↔ B (pushState). No-op while `yb` is `best`. */
  swapCompare() {
    const c = this.compare;
    if (!c) return;
    const next = swapQuery(c, this.currentYear);
    if (!next) return;
    this.go(next);
  }

  /** "B → best year": push `/…/{b}/best`, then resolve to the concrete year + `?from=best` (replaceState). */
  compareBest() {
    const c = this.compare;
    if (!c) return;
    this.go(compareQuery(c.a, c.ya, c.b, 'best', { ...c, from: null }, this.currentYear));
  }

  setLockOffset(on: boolean) {
    this.lockOffset = on;
  }

  /** Replace one side of the pair (picker), keeping its year (pushState). */
  setCompareEntity(side: 'a' | 'b', id: string) {
    const c = this.compare;
    const e = byId(id);
    if (!c || !e) return;
    const next = side === 'a' ? compareQuery(e.id, c.ya, c.b, c.yb, { ...c, from: null }, this.currentYear) : compareQuery(c.a, c.ya, e.id, c.yb, { ...c, from: null }, this.currentYear);
    this.go(next);
  }

  /** Navigate to any query (pushState) — for the picker / links handled in-app. */
  go(q: Query) {
    this.dragFrom = null;
    this.route = q;
    navigate(q, { ...this.env });
    this.syncSearchYear();
    void this.load();
  }

  // ---- internals ------------------------------------------------------------------------------------------

  private syncSearchYear() {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = null;
    this.searchYear = this.year;
    this.syncPairYears();
  }

  private syncPairYears() {
    const c = this.compare;
    this.pairYears = c && c.yb !== 'best' ? { ya: c.ya, yb: c.yb } : null;
  }

  private scheduleSearchYear() {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      this.searchYear = this.year;
      this.syncPairYears();
      if (this.compare) void this.loadCompareData();
      else void this.loadSearchData();
    }, this.debounceMs);
  }

  private cacheYear(s: YearShard) {
    if (this.yearCache.has(s.year)) return;
    this.yearCache.set(s.year, s);
    this.shardsVersion++;
  }

  /** One year shard, fetched at most once even when the paint path and the search path ask together. */
  private fetchYear(y: number): Promise<YearShard> {
    const cached = this.yearCache.get(y);
    if (cached) return Promise.resolve(cached);
    let p = this.pendingYears.get(y);
    if (!p) {
      p = this.data
        .yearShard(y)
        .then((s) => {
          this.cacheYear(s);
          return s;
        })
        .finally(() => this.pendingYears.delete(y));
      this.pendingYears.set(y, p);
    }
    return p;
  }

  /** Tier-1 loads for the current query: entity shard (paint + scrubbing) and year shard (same-year set). */
  private async load(): Promise<void> {
    const q = this.query;
    const gen = ++this.gen;
    if (this.compare) return this.loadCompareData(gen);
    if (!q) {
      this.loading = false;
      return;
    }
    void this.loadSearchData();
    const cachedE = this.entityCache.get(q.id);
    const cachedY = this.yearCache.get(q.year);
    if (cachedE) this.entityShard = cachedE;
    if (cachedY) this.yearShard = cachedY;
    if (cachedE && cachedY) {
      this.loading = false;
      this.error = null;
      return;
    }
    this.loading = !cachedE; // the page can paint from either shard; report loading only until one lands
    this.error = null;
    const tasks: Promise<void>[] = [];
    if (!cachedE) {
      tasks.push(
        this.data.entityShard(q.id).then((s) => {
          this.entityCache.set(q.id, s);
          if (gen === this.gen) {
            this.entityShard = s;
            this.loading = false;
          }
        }),
      );
    }
    if (!cachedY) {
      tasks.push(
        this.fetchYear(q.year).then((s) => {
          if (gen === this.gen) {
            this.yearShard = s;
            this.loading = false;
          }
        }),
      );
    }
    const results = await Promise.allSettled(tasks);
    if (gen !== this.gen) return;
    const failed = results.find((r): r is PromiseRejectedResult => r.status === 'rejected');
    if (failed && !this.pyramid) {
      this.error = failed.reason instanceof Error ? failed.reason.message : String(failed.reason);
      this.loading = false;
    }
  }

  /** M2 tiers for the current constraints: extra year shards, bands, the corpus, the embedding. Idempotent. */
  private async loadSearchData(): Promise<void> {
    if (!this.engine || !this.query) return;
    const tasks: Promise<unknown>[] = [];
    // year shards for a shard-only search (τ, τ−L)
    for (const y of this.requiredYears) if (!this.yearCache.has(y)) tasks.push(this.fetchYear(y));
    // bands: the default table always (tier 1); the full file on the first non-default metric / mode
    if (!this.bandsDefault && this.data.bandsDefault) {
      tasks.push(this.data.bandsDefault().then((b) => (this.bandsDefault = b)));
    }
    if (this.needsAllBands && !this.bandsAll && this.data.bands) {
      tasks.push(this.data.bands().then((b) => (this.bandsAll = b)));
    }
    // corpus (tier 3), once
    if (this.needsCorpus && !this.corpus && this.corpusStatus !== 'loading' && this.data.corpus) {
      this.corpusStatus = 'loading';
      this.corpusError = null;
      tasks.push(
        this.data.corpus().then(
          (c) => {
            this.corpus = c;
            this.corpusStatus = 'ready';
          },
          (e: unknown) => {
            this.corpusStatus = 'error';
            this.corpusError = e instanceof Error ? e.message : String(e);
          },
        ),
      );
    }
    // image embedding for the Visual metric
    if (this.needsEmbedding && !this.embedding && this.embeddingStatus !== 'loading' && this.data.embedding && this.visualModel) {
      this.embeddingStatus = 'loading';
      tasks.push(
        this.data.embedding(this.visualModel).then(
          (e) => {
            this.embedding = e;
            this.embeddingStatus = 'ready';
          },
          () => (this.embeddingStatus = 'error'),
        ),
      );
    }
    await Promise.allSettled(tasks);
  }

  /**
   * M3: everything the compare page needs — both entity shards (paint + scrubbing), the two year shards (pair card
   * without the corpus), bands, and the corpus / embedding when `best` must be resolved (or the metric is Visual).
   * Idempotent; `best` is resolved as soon as the corpus is in hand.
   */
  private async loadCompareData(gen: number = this.gen): Promise<void> {
    const c = this.compare;
    if (!c) return;
    const cachedA = this.entityCache.get(c.a);
    const cachedB = this.entityCache.get(c.b);
    if (cachedA) this.shardA = cachedA;
    if (cachedB) this.shardB = cachedB;
    this.loading = !cachedA;
    this.error = null;
    const tasks: Promise<unknown>[] = [];
    const shard = (id: string, side: 'a' | 'b') =>
      this.data.entityShard(id).then((s) => {
        this.entityCache.set(id, s);
        if (gen !== this.gen) return;
        if (side === 'a') {
          this.shardA = s;
          this.loading = false;
        } else this.shardB = s;
      });
    if (!cachedA) tasks.push(shard(c.a, 'a'));
    if (!cachedB && c.b !== c.a) tasks.push(shard(c.b, 'b'));
    else if (c.b === c.a && cachedA) this.shardB = cachedA;
    if (c.b === c.a && !cachedA) tasks.push(this.data.entityShard(c.a).then((s) => gen === this.gen && (this.shardB = s)));
    // year shards for the pair view (skipped once the corpus is loaded)
    const ys = this.pairYears;
    if (ys && !this.corpus) for (const y of new Set([ys.ya, ys.yb])) if (!this.yearCache.has(y)) tasks.push(this.fetchYear(y));
    if (!this.bandsDefault && this.data.bandsDefault) tasks.push(this.data.bandsDefault().then((b) => (this.bandsDefault = b)));
    if (this.compareNeedsAllBands && !this.bandsAll && this.data.bands) tasks.push(this.data.bands().then((b) => (this.bandsAll = b)));
    if (this.compareNeedsCorpus && !this.corpus && this.corpusStatus !== 'loading' && this.data.corpus) {
      this.corpusStatus = 'loading';
      this.corpusError = null;
      tasks.push(
        this.data.corpus().then(
          (co) => {
            this.corpus = co;
            this.corpusStatus = 'ready';
          },
          (e: unknown) => {
            this.corpusStatus = 'error';
            this.corpusError = e instanceof Error ? e.message : String(e);
          },
        ),
      );
    }
    if (this.compareNeedsEmbedding && !this.embedding && this.embeddingStatus !== 'loading' && this.data.embedding && this.visualModel) {
      this.embeddingStatus = 'loading';
      tasks.push(
        this.data.embedding(this.visualModel).then(
          (e) => {
            this.embedding = e;
            this.embeddingStatus = 'ready';
          },
          () => (this.embeddingStatus = 'error'),
        ),
      );
    }
    const results = await Promise.allSettled(tasks);
    if (gen !== this.gen) return;
    const failed = results.find((r): r is PromiseRejectedResult => r.status === 'rejected');
    if (failed && !this.pyramidA) {
      this.error = failed.reason instanceof Error ? failed.reason.message : String(failed.reason);
      this.loading = false;
    }
    this.resolveBest();
  }

  /**
   * `best` → the concrete year + `?from=best` (replaceState, J5/J6); a pasted `from=best` whose year is NOT the
   * best for A drops the flag (replaceState). Needs the corpus; a no-op until it lands.
   */
  private resolveBest() {
    const c = this.compare;
    if (!c || !this.corpus) return;
    const best = this.bestB;
    if (c.yb === 'best') {
      if (!best) return; // no allowed year of B — the page explains
      const next = compareQuery(c.a, c.ya, c.b, best.year, { ...c, from: 'best' }, this.currentYear);
      this.route = next;
      navigate(next, { replace: true, ...this.env });
      this.syncPairYears();
      void this.loadCompareData();
    } else if (c.from === 'best' && best && best.year !== c.yb) {
      const next = compareQuery(c.a, c.ya, c.b, c.yb, { ...c, from: null }, this.currentYear);
      this.route = next;
      navigate(next, { replace: true, ...this.env });
    }
  }

  /** Card data for one result: shares, per-bin delta, decomposition + sentences (or the trend reason). */
  private card(view: CorpusView, q: SearchQuery, queryRow: number, r: SearchResult, stats?: FeatureStats): CardData {
    const eng = this.engine!;
    const entity = byId(r.id)!;
    const shares = sharesAt(view.u16, r.row * N_DIMS);
    const qShares = sharesAt(view.u16, queryRow * N_DIMS);
    const delta = new Float32Array(N_DIMS);
    for (let k = 0; k < N_DIMS; k++) delta[k] = shares[k] - qShares[k];
    let explanation: Explanation | null = null;
    let trend: string | null = null;
    if (q.trend) {
      const prevQ = view.rowOf(q.id, q.year - q.L);
      const prevC = view.rowOf(r.id, r.year - q.L);
      if (prevQ >= 0 && prevC >= 0) {
        const f = (row: number) => this.featuresFn(sharesAt(view.u16, row * N_DIMS));
        trend = trendReason({ now: f(queryRow), prev: f(prevQ) }, { now: f(r.row), prev: f(prevC) });
      }
    } else {
      explanation = eng.explain(view, q, queryRow, r.row, stats);
    }
    return { result: r, entity, shares, delta, projected: r.year > this.currentYear, explanation, trend };
  }

  /** The entity's closest other year (PLAN §6 own-trajectory row): argmin over |Δy| ≥ 5 inside the era, read off the
   *  search's own distance vector `d` (it covers every view row, own entity included). Needs the corpus view — a
   *  year-shard view holds no other year of the entity. */
  private ownTrajectory(view: CorpusView, q: SearchQuery, d: Float64Array, bands: Bands | null): OwnTrajectory | null {
    const eng = this.engine!;
    const hi = eraEdge(q.era, q.currentYear, this.lastObservedYear);
    const lo = q.trend ? YEAR_MIN + q.L : YEAR_MIN;
    let best = -1;
    let bestD = Infinity;
    for (let y = lo; y <= hi; y++) {
      if (Math.abs(y - q.year) < 5) continue;
      const row = view.rowOf(q.id, y);
      if (row < 0 || row >= d.length) continue;
      const v = d[row];
      if (Number.isFinite(v) && v < bestD) {
        bestD = v;
        best = y;
      }
    }
    if (best < 0) return null;
    const band = eng.bandFor(bands, eng.tableMetric(q), q.sex, q.year, best, q.era, bestD, 'cross');
    return { year: best, dy: best - q.year, d: bestD, band, shares: sharesAt(view.u16, view.rowOf(q.id, best) * N_DIMS) };
  }
}

function pickSearch(q: CountryQuery): SearchOptions {
  return {
    mode: q.mode,
    n: q.n,
    from: q.from,
    to: q.to,
    via: q.via,
    era: q.era,
    scope: q.scope,
    minpop: q.minpop,
    metric: q.metric,
    sex: q.sex,
    k: q.k,
    div: q.div,
    trend: q.trend,
    L: q.L,
  };
}

export { visualExposed };

/** Singleton for the app; tests construct their own `new AppState({...})`. */
export const app = new AppState();
