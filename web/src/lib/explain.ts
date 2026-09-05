/**
 * Explanations for one (query, candidate) pair — twin of `metrics.decompose` and query.py's `snapshot_reason`
 * (PLAN §4.4). Everything is a pure function of two view rows, so the country-page card and the compare page
 * reach the identical sentence through `explainPair` (pinned by a snapshot test in search.integration.test.ts).
 *
 *  1. `decompose` — the ranking metric's d and its blend split: `l2Part = ½·l2/σ_l2`, `w1Part = ½·w1s/σ_w1s`
 *     (they sum to the blend distance; for `l2` / `w1` / `w1sex` the foreign term is 0), `w1Years`, the 3 bins
 *     with the largest share of the squared L2 gap and the 3 bins with the most transport in years. Metrics
 *     without an L2/W1 split (l2s, hel, feat, w1bal, visual, trend) are explained through `blend`.
 *  2. `featureDeltas` — z-scores of both members against the FOCAL (query) year's country set in scope
 *     (PLAN §3.3; the candidate's own year is never the reference), "alike" = the 2 smallest |Δz| among the six
 *     EXPLAIN features, "differs" = the largest.
 *  3. `explainSentence` — templates from `explain.templates.ts`.
 */

import { N_BINS, N_DIMS, BIN_WIDTH, type Entity, type Sex, type SigmaTable } from './types.ts';
import { cdfPerSex, s21 } from './math/cdf.ts';
import { features, NUMERIC_FEATURES } from './math/features.ts';
import { entities as allEntities } from './data.ts';
import { featureStats, vectorAt, zFeatures, type CorpusView, type FeatureStats, type Metric, type SearchQuery, type TrendKind } from './search.ts';
import {
  EXPLAIN_FEATURES,
  becauseSentence,
  decompositionSentence,
  differsSentence,
  w1Sentence,
  type ExplainFeature,
  type FeaturePair,
} from './explain.templates.ts';

export type DecomposeMetric = 'blend' | 'l2' | 'w1' | 'w1sex';

export interface Decomposition {
  /** Metric the decomposition is stated for (the query metric when it has a split, else `blend`). */
  metric: DecomposeMetric;
  sex: Sex;
  d: number;
  l2Part: number;
  w1Part: number;
  w1Years: number;
  /** [bin index, fraction of the squared L2 gap] — indices into the 42-vector (sex '2') or s21 (sex '1'). */
  topBinsL2: Array<[number, number]>;
  /** [bin index, transport in years] */
  topBinsW1: Array<[number, number]>;
}

/** The metric `decompose` reports for a query: its own when decomposable, otherwise blend (query.py `own`). */
export function decomposeMetric(metric: Metric, trend: TrendKind = null): DecomposeMetric {
  if (trend === null && (metric === 'blend' || metric === 'l2' || metric === 'w1' || metric === 'w1sex')) return metric;
  return 'blend';
}

function topK(values: ArrayLike<number>, k: number): Array<[number, number]> {
  const idx = Array.from({ length: values.length }, (_, i) => i);
  idx.sort((a, b) => values[b] - values[a] || a - b);
  return idx.slice(0, k).map((i) => [i, values[i]]);
}

function l2(a: ArrayLike<number>, b: ArrayLike<number>): number {
  let s = 0;
  for (let k = 0; k < a.length; k++) s += (a[k] - b[k]) ** 2;
  return Math.sqrt(s);
}

/** `metrics.decompose(metric, q, x, sex, sigma, top=3)` on two view rows. */
export function decompose(
  view: CorpusView,
  q: { metric: Metric; sex: Sex; trend?: TrendKind },
  queryRow: number,
  candRow: number,
  sigma: SigmaTable,
  top = 3,
): Decomposition {
  const metric = decomposeMetric(q.metric, q.trend ?? null);
  const sex = q.sex;
  const qv42 = vectorAt(view, queryRow);
  const xv42 = vectorAt(view, candRow);
  const qv = sex === '2' ? qv42 : s21(qv42);
  const xv = sex === '2' ? xv42 : s21(xv42);
  const n = qv.length;
  const sq = new Float64Array(n);
  let sqSum = 0;
  for (let k = 0; k < n; k++) {
    sq[k] = (xv[k] - qv[k]) ** 2;
    sqSum += sq[k];
  }
  const l2d = Math.sqrt(sqSum);
  const cq = cdfPerSex(qv);
  const cx = cdfPerSex(xv);
  const w1Bins = new Float64Array(n);
  let w1Years = 0;
  for (let k = 0; k < n; k++) {
    w1Bins[k] = BIN_WIDTH * Math.abs(cx[k] - cq[k]);
    w1Years += w1Bins[k];
  }
  let l2Part = (0.5 * l2d) / sigma.l2[sex];
  let w1Part = (0.5 * w1Years) / (sex === '2' ? sigma.w1sex['2'] : sigma.w1['1']);
  let d: number;
  if (metric === 'l2') {
    d = l2d;
    l2Part = d;
    w1Part = 0;
  } else if (metric === 'w1' || (metric === 'w1sex' && sex === '1')) {
    // w1 is the total-only transport (sex-blind), whatever `sex` says
    const cq21 = cdfPerSex(s21(qv42));
    const cx21 = cdfPerSex(s21(xv42));
    let s = 0;
    for (let k = 0; k < N_BINS; k++) s += Math.abs(cx21[k] - cq21[k]);
    d = BIN_WIDTH * s;
    l2Part = 0;
    w1Part = d;
  } else if (metric === 'w1sex') {
    d = w1Years;
    l2Part = 0;
    w1Part = d;
  } else {
    d = l2Part + w1Part;
  }
  const frac = new Float64Array(n);
  if (sqSum > 0) for (let k = 0; k < n; k++) frac[k] = sq[k] / sqSum;
  return { metric, sex, d, l2Part, w1Part, w1Years, topBinsL2: topK(frac, top), topBinsW1: topK(w1Bins, top) };
}

export interface FeatureDelta {
  name: ExplainFeature;
  zq: number;
  zc: number;
  rawQ: number;
  rawC: number;
  /** |zq − zc| (NaN when either side is undefined). */
  dz: number;
}

export interface FeatureDeltas {
  referenceYear: number;
  nReference: number;
  /** The six EXPLAIN features, sorted by |Δz| ascending (ties keep EXPLAIN order). */
  all: FeatureDelta[];
  alike: FeatureDelta[]; // 2 smallest |Δz|
  differs: FeatureDelta[]; // 1 largest |Δz|
}

/**
 * z-scored feature deltas of a pair against the focal-year country set (PLAN §3.3). Pass `stats` from
 * `featureStats(view, ents, referenceYear, scope, minpop)` to reuse it across many candidates; otherwise it is
 * computed here (the view must hold the reference year's rows — inject that year shard in `today` mode).
 */
export function featureDeltas(
  view: CorpusView,
  ents: readonly Entity[],
  queryRow: number,
  candRow: number,
  referenceYear: number,
  opts: { scope?: 'c' | 'all'; minpop?: number; stats?: FeatureStats } = {},
): FeatureDeltas {
  const stats = opts.stats ?? featureStats(view, ents, referenceYear, opts.scope ?? 'c', opts.minpop ?? 100);
  if (stats.year !== referenceYear) throw new Error(`featureDeltas: stats are for ${stats.year}, not ${referenceYear}`);
  const v = new Float64Array(N_DIMS);
  const zq = zFeatures(view, queryRow, stats, v);
  const zc = zFeatures(view, candRow, stats, v);
  const fq = features(vectorAt(view, queryRow, v));
  const fc = features(vectorAt(view, candRow, v));
  const all: FeatureDelta[] = EXPLAIN_FEATURES.map((name) => {
    const j = NUMERIC_FEATURES.indexOf(name);
    return { name, zq: zq[j], zc: zc[j], rawQ: fq[name], rawC: fc[name], dz: Math.abs(zq[j] - zc[j]) };
  });
  const order = EXPLAIN_FEATURES.map((_, i) => i);
  // NaN deltas sort last (undefined features never make "alike"); ties keep EXPLAIN order
  order.sort((a, b) => {
    const da = all[a].dz;
    const db = all[b].dz;
    if (Number.isNaN(da) && Number.isNaN(db)) return a - b;
    if (Number.isNaN(da)) return 1;
    if (Number.isNaN(db)) return -1;
    return da - db || a - b;
  });
  const sorted = order.map((i) => all[i]);
  return { referenceYear, nReference: stats.rows.length, all: sorted, alike: sorted.slice(0, 2), differs: sorted.slice(-1) };
}

export interface Explanation {
  decomposition: Decomposition;
  deltas: FeatureDeltas;
  /** "Alike in median age (47.3 vs 44.6) and 65+ share (21.4 % vs 22.3 %)." */
  because: string;
  /** "Differs most in base slope (0–4 vs 20–24) (0.48 vs 0.81)." */
  differsIn: string;
  /** "Only 1.90 years of average age movement separate them." */
  w1Sentence: string;
  /** "Shape distance 0.43 = bin-by-bin 0.26 + age-shift 0.17; largest bin gaps …" */
  decompositionSentence: string;
}

const toPair = (f: FeatureDelta): FeaturePair => ({ name: f.name, rawQ: f.rawQ, rawC: f.rawC });

/** Sentences from an already computed decomposition + deltas (`explain.templates.ts`); `_q` is accepted for callers that pass the query. */
export function explainSentence(decomposition: Decomposition, deltas: FeatureDeltas, _q?: unknown): Pick<Explanation, 'because' | 'differsIn' | 'w1Sentence' | 'decompositionSentence'> {
  return {
    because: becauseSentence(deltas.alike.map(toPair)),
    differsIn: differsSentence(deltas.differs.map(toPair)),
    w1Sentence: w1Sentence(decomposition.w1Years),
    decompositionSentence: decompositionSentence({
      metric: decomposition.metric,
      d: decomposition.d,
      l2Part: decomposition.l2Part,
      w1Part: decomposition.w1Part,
      w1Years: decomposition.w1Years,
      topBinsL2: decomposition.topBinsL2.map(([k]) => k),
      topBinsW1: decomposition.topBinsW1.map(([k]) => k),
      sex: decomposition.sex,
    }),
  };
}

/**
 * THE explanation entry point — country-page cards and the compare page both call this with the query's
 * (metric, sex, scope, minpop, year) and two view rows; the reference year is the query year.
 */
export function explainPair(
  view: CorpusView,
  q: Pick<SearchQuery, 'metric' | 'sex' | 'year'> & Partial<Pick<SearchQuery, 'scope' | 'minpop' | 'trend'>>,
  queryRow: number,
  candRow: number,
  sigma: SigmaTable,
  opts: { ents?: readonly Entity[]; stats?: FeatureStats } = {},
): Explanation {
  const decomposition = decompose(view, { metric: q.metric, sex: q.sex, trend: q.trend ?? null }, queryRow, candRow, sigma);
  const deltas = featureDeltas(view, opts.ents ?? allEntities, queryRow, candRow, q.year, { scope: q.scope ?? 'c', minpop: q.minpop ?? 100, stats: opts.stats });
  return { decomposition, deltas, ...explainSentence(decomposition, deltas) };
}
