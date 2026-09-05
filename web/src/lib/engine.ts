/**
 * The search engine seam (M2). This is the ONLY module that imports X1's `search.ts` / `bands.ts` /
 * `explain.ts`; the store (`state.svelte.ts`) and the components code against the `Engine` interface below,
 * and the store's tests inject a fake. Types are re-exported from X1's modules so there is one definition.
 *
 * Binding rules: `entities` and `meta.sigma` are build constants, so they are bound here once; the query's
 * `minpop` is in THOUSANDS (the URL carries persons — the store divides); `currentYear` rides on the query
 * because the era mask depends on it (PLAN §6 J8); `bands` may be null (no percentile → 'typical', null).
 */

import { entities, meta } from './entities.ts';
import type { Bands, Corpus, EntityShard, YearShard } from './types.ts';
import type { Metric, Sex } from './router.ts';
import {
  bestYearPerEntity as x1BestYear,
  candidateMask as x1CandidateMask,
  different as x1Different,
  distances as x1Distances,
  featureStats as x1FeatureStats,
  fromCorpus as x1FromCorpus,
  fromYearShards as x1FromYearShards,
  isolation as x1Isolation,
  isolationPercentile as x1IsolationPercentile,
  lagYears as x1LagYears,
  search as x1Search,
  similar as x1Similar,
  type CorpusView,
  type FeatureStats,
  type SearchBoth,
  type SearchOpts,
  type SearchQuery,
  type SearchResult,
  type TimeShiftRow,
  type TrendKind,
  type TrendWindow,
} from './search.ts';
import { bandFor as x1BandFor, tableMetric as x1TableMetric, type BandKind, type BandLabel, type BandResult, type Era } from './bands.ts';
import { explainPair as x1ExplainPair, type Decomposition, type Explanation, type FeatureDeltas } from './explain.ts';

export type { BandKind, BandLabel, BandResult, CorpusView, Decomposition, Explanation, FeatureDeltas, FeatureStats, SearchBoth, SearchOpts, SearchQuery, SearchResult, TimeShiftRow, TrendKind, TrendWindow };

/** The query's own rows a year-shard view must carry besides the candidate shard (today mode / trend lags). */
export interface Inject {
  shard: EntityShard;
  years: readonly number[];
}

export interface Engine {
  /** View over the whole corpus (tier 3): rows are corpus rows, every year of every entity is a candidate. */
  fromCorpus(corpus: Corpus): CorpusView;
  /** View over year shards (tier 1): `main` holds the candidates, `others` back lags / the reference year, `inject` adds the query's own rows. */
  fromShards(main: YearShard, others: readonly YearShard[], inject?: Inject | null): CorpusView;
  /** Years a trend query needs besides τ: τ − L (motion) or τ − 5 … τ − L (path). */
  lagYears(tau: number, trend: TrendKind, L: TrendWindow): number[];
  /** Uint8 row mask: year mode ∧ era ∧ scope ∧ floor ∧ not own entity (∧ trend window). */
  candidateMask(view: CorpusView, q: SearchQuery): Uint8Array;
  /** Distances from the query row to every candidate row (`[0, nRows)`). */
  distances(view: CorpusView, q: SearchQuery, opts: SearchOpts): Float64Array;
  /** Twins + opposites + strict strip + the raw distance vector from one scan (what the page runs per query). */
  search(view: CorpusView, q: SearchQuery, bands: Bands | null, opts: SearchOpts): SearchBoth;
  similar(view: CorpusView, q: SearchQuery, bands: Bands | null, opts: SearchOpts): SearchResult[];
  different(view: CorpusView, q: SearchQuery, bands: Bands | null, opts: SearchOpts): { results: SearchResult[]; strict: SearchResult[] };
  bestYearPerEntity(view: CorpusView, q: SearchQuery, bands: Bands | null, opts: SearchOpts): TimeShiftRow[];
  /** id → mean distance to the 5 nearest same-year countries ≥ 100k (most isolated first). */
  isolation(view: CorpusView, year: number, metric: Metric, sex: Sex, opts: SearchOpts): Map<string, number>;
  /** Share of the other countries less isolated than `id` (0–100). */
  isolationPercentile(iso: Map<string, number>, id: string): number | null;
  /** Metric key inside the bands file for a query (`trend@10`, `visual:<model>`, …). */
  tableMetric(q: SearchQuery): string;
  bandFor(bands: Bands | null, metric: string, sex: Sex, queryYear: number, candYear: number, era: Era, d: number, kind: BandKind): BandResult;
  /** z-score reference for `explain` (the focal year's set in scope), computed once per search and reused per card. */
  featureStats(view: CorpusView, year: number, scope: 'c' | 'all', minpop: number): FeatureStats;
  /** Decomposition + feature deltas + the three sentences for one (query, candidate) pair. */
  explain(view: CorpusView, q: SearchQuery, queryRow: number, candRow: number, stats?: FeatureStats): Explanation;
}

const sigma = meta.sigma;
const lastObservedYear = meta.last_observed_year;

/** Production engine: X1's pure functions with the build constants bound. */
export const engine: Engine = {
  fromCorpus: (corpus) => x1FromCorpus(corpus, entities),
  fromShards: (main, others, inject) => {
    const v = x1FromYearShards(main, others, entities);
    return inject ? v.injectEntityRows(inject.shard, inject.years) : v;
  },
  lagYears: x1LagYears,
  candidateMask: (view, q) => x1CandidateMask(view, entities, q, lastObservedYear),
  distances: (view, q, opts) => x1Distances(view, q, sigma, { ...opts, lastObservedYear }),
  search: (view, q, bands, opts) => x1Search(view, entities, q, sigma, bands, { ...opts, lastObservedYear }),
  similar: (view, q, bands, opts) => x1Similar(view, entities, q, sigma, bands, { ...opts, lastObservedYear }),
  different: (view, q, bands, opts) => x1Different(view, entities, q, sigma, bands, { ...opts, lastObservedYear }),
  bestYearPerEntity: (view, q, bands, opts) => x1BestYear(view, entities, q, sigma, bands, { ...opts, lastObservedYear }),
  isolation: (view, year, metric, sex, opts) => x1Isolation(view, entities, year, metric, sigma, sex, opts),
  isolationPercentile: x1IsolationPercentile,
  tableMetric: (q) => x1TableMetric(q, meta.verdicts?.exposed_visual?.model),
  bandFor: (bands, metric, sex, qy, cy, era, d, kind) => x1BandFor(bands, metric, sex, qy, cy, era, d, kind),
  featureStats: (view, year, scope, minpop) => x1FeatureStats(view, entities, year, scope, minpop),
  explain: (view, q, queryRow, candRow, stats) => x1ExplainPair(view, q, queryRow, candRow, sigma, { ents: entities, stats }),
};
