/**
 * Pure helpers for the compare page (PLAN §7 J4 overlay / J5 time-shift `best`). No DOM, no globals — the store
 * (`state.svelte.ts`) and the components call these; vitest drives them on synthetic views.
 *
 *  - `lockedYears`        lock-offset arithmetic for the two scrubbers (move both years, keep Δ, clamp as a pair);
 *  - `compareAxis`        axis = max of the pair's `axis_pct` (fit) with a "widened" flag for the caption;
 *  - `bestYearFor`        `y* = argmin_y d(A_ya, B_y)` over B's rows in the allowed window — the SAME rule as the
 *                         time-shift table (era cap, candidate's own-year population floor, ties by |Δy| then year);
 *  - `featureTable`       both members z-scored against A's year country set (`FeatureStats` from `engine.featureStats`);
 *  - `pairData`           d under the pair's metric, band by |Δy| (or the `best` null), the identical explanation the
 *                         country-page card shows (`engine.explain` → `explain.explainPair`), feature table, B − A deltas;
 *  - `swapQuery`, `pairHeadline`, `compareBandsDefaultSuffice`. (CSV / PNG / SVG export live in lib/export.ts.)
 */

import { N_DIMS, YEAR_MAX, YEAR_MIN, type AxisPct, type Bands, type Entity, type Sex } from './types.ts';
import { axisFor, maxBinPct, pairAxis, type AxisChoice, type AxisMode } from './math/scale.ts';
import { features, NUMERIC_FEATURES, type Features, type NumericFeatureName } from './math/features.ts';
import { vectorAt, zFeatures, type CorpusView, type FeatureStats } from './search.ts';
import type { BandKind, BandResult, Engine, Explanation, SearchQuery } from './engine.ts';
import { compareQuery, defaultEra, type CompareQuery, type EraMode, type Metric } from './router.ts';
import { eraEdge } from './restate.ts';
import { BAND_TEXT, percentileClause } from './explain.templates.ts';
import { ageLabel } from './format.ts';

// ---- years --------------------------------------------------------------------------------------------------

export interface PairYears {
  ya: number;
  yb: number;
}

/** yb − ya. */
export const offsetOf = (ya: number, yb: number): number => yb - ya;

/**
 * Lock-offset: one scrubber moved to `y`, the other follows so `yb − ya === offset` stays; when the pair would leave
 * 1950–2100 both are shifted back together (Δ is never broken — |Δ| ≤ 150 always fits).
 */
export function lockedYears(side: 'a' | 'b', y: number, offset: number): PairYears {
  let ya = side === 'a' ? y : y - offset;
  let yb = ya + offset;
  if (yb > YEAR_MAX) {
    ya -= yb - YEAR_MAX;
    yb = YEAR_MAX;
  }
  if (ya > YEAR_MAX) {
    yb -= ya - YEAR_MAX;
    ya = YEAR_MAX;
  }
  if (yb < YEAR_MIN) {
    ya += YEAR_MIN - yb;
    yb = YEAR_MIN;
  }
  if (ya < YEAR_MIN) {
    yb += YEAR_MIN - ya;
    ya = YEAR_MIN;
  }
  return { ya, yb };
}

/** Years the two scrubbers end on after `side` moves to `y` (lock on → keep Δ; lock off → the other side stays). */
export function nextYears(cur: PairYears, side: 'a' | 'b', y: number, lock: boolean): PairYears {
  const c = Math.min(YEAR_MAX, Math.max(YEAR_MIN, Math.round(y)));
  if (lock) return lockedYears(side, c, offsetOf(cur.ya, cur.yb));
  return side === 'a' ? { ya: c, yb: cur.yb } : { ya: cur.ya, yb: c };
}

// ---- axis ---------------------------------------------------------------------------------------------------

export interface CompareAxis extends AxisChoice {
  /** A's own fit (`entities[].axis_pct`) — what the caption compares against. */
  aFit: AxisPct;
  /** true when B (or the drawn years) forced an axis wider than A's fit → caption "axis widened to N %". */
  widened: boolean;
}

/** Axis for the pair: fit → max(A fit, B fit), widened again only if a drawn year overflows; pin10 / never as on the country page. */
export function compareAxis(mode: AxisMode, aFit: AxisPct, bFit: AxisPct, sharesA: ArrayLike<number> | null, sharesB: ArrayLike<number> | null): CompareAxis {
  const pair = pairAxis(aFit, bFit);
  const maxes = [sharesA ? maxBinPct(sharesA) : 0, sharesB ? maxBinPct(sharesB) : 0];
  const choice = axisFor(mode, pair.axisPct, ...maxes);
  return { ...choice, aFit, widened: mode === 'fit' && choice.axisPct !== aFit };
}

// ---- best year ----------------------------------------------------------------------------------------------

export interface BestYear {
  year: number;
  d: number;
  dy: number; // year − ya
  /** y* is the first or last allowed year of B (the true best may lie beyond the era edge). */
  boundaryHit: boolean;
}

export interface BestYearWindow {
  lo: number;
  hi: number;
  minpop: number; // thousands (candidate's own-year total)
}

/** The years the best-year search may use for A's year: 1950 … the era edge (`obs` = ≤ max(last observed, today)). */
export function bestYearWindow(ya: number, era: EraMode | null, currentYear: number, lastObserved: number, minpop = 100): BestYearWindow {
  const e = era ?? defaultEra(ya, currentYear);
  return { lo: YEAR_MIN, hi: eraEdge(e, currentYear, lastObserved), minpop };
}

/**
 * `argmin_y d(A, B_y)` over B's rows in `[lo, hi]` with `totals ≥ minpop` — the time-shift table's rule for one entity
 * (`search.bestYearPerEntity`: d asc, ties by |Δy| asc, then year asc). `d` is indexed by VIEW row (`engine.distances`).
 */
export function bestYearFor(d: ArrayLike<number>, view: Pick<CorpusView, 'rowOf' | 'totals'>, bId: string, ya: number, w: BestYearWindow): BestYear | null {
  let best: BestYear | null = null;
  let first = -1;
  let last = -1;
  for (let y = w.lo; y <= w.hi; y++) {
    const row = view.rowOf(bId, y);
    if (row < 0 || row >= d.length) continue;
    if (!(view.totals[row] >= w.minpop)) continue;
    const v = d[row];
    if (!Number.isFinite(v)) continue;
    if (first < 0) first = y;
    last = y;
    if (best === null || v < best.d || (v === best.d && (Math.abs(y - ya) < Math.abs(best.dy) || (Math.abs(y - ya) === Math.abs(best.dy) && y < best.year)))) {
      best = { year: y, d: v, dy: y - ya, boundaryHit: false };
    }
  }
  if (best) best.boundaryHit = best.year === first || best.year === last;
  return best;
}

// ---- feature table ------------------------------------------------------------------------------------------

export const TABLE_FEATURES = ['median_age', 'u15', 'wa', 'o65', 'total_dep', 'base_slope_20', 'wa_sex_ratio', 'modal_bin'] as const satisfies readonly NumericFeatureName[];
export type TableFeature = (typeof TABLE_FEATURES)[number];

export const TABLE_LABELS: Record<TableFeature, string> = {
  median_age: 'median age',
  u15: 'under 15',
  wa: 'working age (15–64)',
  o65: '65 and over',
  total_dep: 'dependency ratio',
  base_slope_20: 'base slope (0–4 vs 20–24)',
  wa_sex_ratio: 'working-age sex ratio',
  modal_bin: 'modal age bin',
};

export interface FeatureRow {
  name: TableFeature;
  label: string;
  rawA: number;
  rawB: number;
  zA: number;
  zB: number;
  /** |zA − zB| (NaN when either side is undefined). */
  dz: number;
}

/** The eight features formatted like the explanation sentences (shares as %, ratios to 2 dp, bin as an age range). */
export function formatTableFeature(name: TableFeature, v: number): string {
  if (!Number.isFinite(v)) return 'n/a';
  switch (name) {
    case 'median_age':
      return `${v.toFixed(1)} y`;
    case 'u15':
    case 'wa':
    case 'o65':
      return `${(100 * v).toFixed(1)} %`;
    case 'total_dep':
    case 'base_slope_20':
    case 'wa_sex_ratio':
      return v.toFixed(2);
    case 'modal_bin':
      return ageLabel(v / 5);
  }
}

/** z as copy: '+1.2σ' / '−0.4σ' / 'n/a'. */
export function formatZ(z: number): string {
  if (!Number.isFinite(z)) return 'n/a';
  const r = Math.round(z * 10) / 10;
  return `${r > 0 ? '+' : r < 0 ? '−' : '±'}${Math.abs(r).toFixed(1)}σ`;
}

/** Both members z-scored against `stats` (A's year country set in scope, PLAN §3.3) with their raw values. */
export function featureTable(view: CorpusView, rowA: number, rowB: number, stats: FeatureStats): FeatureRow[] {
  const v = new Float64Array(N_DIMS);
  const zA = zFeatures(view, rowA, stats, v);
  const zB = zFeatures(view, rowB, stats, v);
  const fA: Features = features(vectorAt(view, rowA, v));
  const fB: Features = features(vectorAt(view, rowB, v));
  return TABLE_FEATURES.map((name) => {
    const j = NUMERIC_FEATURES.indexOf(name);
    return { name, label: TABLE_LABELS[name], rawA: fA[name], rawB: fB[name], zA: zA[j], zB: zB[j], dz: Math.abs(zA[j] - zB[j]) };
  });
}

// ---- pair -----------------------------------------------------------------------------------------------------

/** A compare query whose `yb` is a concrete year. */
export type ConcreteCompare = CompareQuery & { yb: number };
export const isConcrete = (q: CompareQuery | null): q is ConcreteCompare => q !== null && q.yb !== 'best';

export interface PairData {
  metric: Metric;
  sex: Sex;
  /** Distance under `metric` (the metric the country page ranked with when the pair came from a card). */
  d: number;
  dy: number;
  /** `best` when the pair came from the best-year resolution (PLAN §3.4a null), else same/cross by Δy. */
  bandKind: BandKind;
  band: BandResult;
  explanation: Explanation;
  features: FeatureRow[];
  /** B − A per bin (42 shares of total) — the diff view / decomposition sparkline. */
  delta: Float32Array;
  referenceYear: number;
  nReference: number;
}

export interface PairOpts {
  currentYear: number;
  lastObserved: number;
  emb?: Float32Array;
  visualModel?: string;
  /** Reference set for the z-scores (default: countries ≥ 100k of A's year). */
  minpop?: number;
}

/** The engine query the pair distance / explanation are stated under (mode `any` — no candidate filtering here). */
export function pairSearchQuery(q: Pick<CompareQuery, 'a' | 'ya' | 'era' | 'metric' | 'sex'>, currentYear: number): SearchQuery {
  return {
    id: q.a,
    year: q.ya,
    mode: 'any',
    n: 10,
    era: q.era ?? defaultEra(q.ya, currentYear),
    scope: 'all',
    minpop: 0,
    metric: q.metric,
    sex: q.sex,
    k: 5,
    div: 0.5,
    trend: null,
    L: 10,
    currentYear,
  };
}

/**
 * Everything the pair card shows for (A_ya, B_yb) on a view that holds both rows AND A's year (the z-score reference).
 * B's row must be a candidate row (`< view.nRows`) for `d` under a non-decomposable metric; otherwise `d` falls back to
 * the blend decomposition. Throws what the engine throws (the store catches and shows it).
 */
export function pairData(engine: Engine, view: CorpusView, q: ConcreteCompare, bands: Bands | null, opts: PairOpts): PairData | null {
  const rowA = view.rowOf(q.a, q.ya);
  const rowB = view.rowOf(q.b, q.yb);
  if (rowA < 0 || rowB < 0) return null;
  const sq = pairSearchQuery(q, opts.currentYear);
  const stats = engine.featureStats(view, q.ya, 'c', opts.minpop ?? 100);
  const explanation = engine.explain(view, sq, rowA, rowB, stats);
  let d: number;
  if (rowB < view.nRows) {
    d = engine.distances(view, sq, { queryRow: rowA, emb: opts.emb, visualModel: opts.visualModel })[rowB];
  } else {
    d = explanation.decomposition.d;
  }
  const dy = q.yb - q.ya;
  const bandKind: BandKind = q.from === 'best' ? 'best' : dy === 0 ? 'same' : 'cross';
  const band = engine.bandFor(bands, engine.tableMetric(sq), q.sex, q.ya, q.yb, sq.era, d, bandKind);
  const a = vectorAt(view, rowA);
  const b = vectorAt(view, rowB);
  const delta = new Float32Array(N_DIMS);
  for (let k = 0; k < N_DIMS; k++) delta[k] = b[k] - a[k];
  return {
    metric: q.metric,
    sex: q.sex,
    d,
    dy,
    bandKind,
    band,
    explanation,
    features: featureTable(view, rowA, rowB, stats),
    delta,
    referenceYear: explanation.deltas.referenceYear,
    nReference: explanation.deltas.nReference,
  };
}

/** `bands_default` (same/blend/two-sex tables) is enough only for a same-year blend pair not banded against `best`. */
export function compareBandsDefaultSuffice(q: Pick<CompareQuery, 'metric' | 'sex' | 'ya' | 'yb' | 'from'>): boolean {
  return q.metric === 'blend' && q.sex === '2' && q.yb === q.ya && q.from !== 'best';
}

// ---- copy ---------------------------------------------------------------------------------------------------

/** '(−18 y)' / '(+14 y)' / '' */
export function dyText(dy: number): string {
  return dy === 0 ? '' : `(${dy > 0 ? '+' : '−'}${Math.abs(dy)} y)`;
}

/**
 * "South Korea 2026 ≈ Japan 2008 (−18 y), closer than 93 % of best-year matches" (J5). `≈` for close bands, `vs`
 * otherwise; the clause reads "closer than" in the lower half of the null and "farther than" in the upper half,
 * and names the null the band came from.
 */
export function pairHeadline(a: { name: string; year: number }, b: { name: string; year: number }, band: BandResult, kind: BandKind): string {
  const close = band.label === 'very_close' || band.label === 'close';
  const dy = dyText(b.year - a.year);
  const head = `${a.name} ${a.year} ${close ? '≈' : 'vs'} ${b.name} ${b.year}${dy ? ' ' + dy : ''}`;
  const closer = band.percentile !== null && band.percentile <= 50;
  const clause = percentileClause(band.percentile, closer, kind === 'best' ? 'best-year matches' : 'random pairs');
  return clause ? `${head}, ${clause}` : head;
}

/** 'close · 7 %' style chip text plus its title. */
export function bandChip(band: BandResult, kind: BandKind): { text: string; title: string } {
  const pop = kind === 'best' ? 'best-year matches for this decade' : kind === 'same' ? 'random same-year country pairs' : 'random cross-year country pairs';
  if (band.percentile === null) return { text: BAND_TEXT[band.label], title: `no percentile table for this pair (${pop})` };
  const p = band.percentile;
  const shown = p >= 99 || p <= 1 ? p.toFixed(1) : p.toFixed(0);
  return { text: `${BAND_TEXT[band.label]} · p${shown}`, title: `distance at the ${shown}th percentile of ${pop}` };
}

/** A ↔ B (years too); `from` is directional and dropped. Null while `yb` is still `best`. */
export function swapQuery(q: CompareQuery, currentYear: number): CompareQuery | null {
  if (q.yb === 'best') return null;
  return compareQuery(q.b, q.yb, q.a, q.ya, { ...q, from: null }, currentYear);
}

/** Short display name helper shared by the page and the export footer. */
export const entityName = (e: Entity | undefined, id: string): string => e?.short_name ?? id;
