/**
 * Copy for the constraint bar and result cards (PLAN §5–§6): the restated-query sentence, control labels,
 * the era chip, band words, the opposites headline, the distinctiveness chip and the trend reason.
 * Pure functions over the query object — no DOM, table-tested.
 */

import { YEAR_MAX, YEAR_MIN } from './types.ts';
import type { Features } from './math/features.ts';
import { effectiveEra, type CountryQuery, type Div, type EraMode, type Metric, type SearchOptions, type StoredYearMode, type Trend } from './router.ts';
import type { BandLabel } from './engine.ts';

// ---- labels ----------------------------------------------------------------------------------------------

export const METRIC_LABEL: Record<Metric, string> = {
  blend: 'Shape',
  w1: 'Age-shift (years)',
  l2: 'Bin-by-bin',
  l2s: 'Shift-tolerant',
  hel: 'Elderly-tail emphasis',
  feat: 'Summary statistics',
  w1sex: 'Age-shift per sex',
  w1bal: 'Balanced sex-aware',
  visual: 'Visual (experimental: what a vision model thinks looks alike)',
};
export const METRIC_HINT: Record<Metric, string> = {
  blend: 'Half bin-by-bin distance, half per-sex age-shift distance, each scaled by its typical same-year value.',
  w1: 'Years of average age movement between the two total age distributions; ≈ |Δ mean age|, sex-blind.',
  l2: 'Euclidean distance over the 42 age × sex shares.',
  l2s: 'Bin-by-bin after Gaussian smoothing along age (σ = 1 bin) — tolerates a bulge that sits one band off.',
  hel: 'Hellinger distance — weights the sparsely populated elderly bins more than plain bin-by-bin.',
  feat: 'Euclidean distance over z-scored summary statistics (median age, 65+, U15, …) of the focal year.',
  w1sex: 'The per-sex age-shift term alone (years); surplus mass is parked at 100+, so a male bulge pays more than an elderly female one.',
  w1bal: 'Age-shift on the total distribution plus a sex-ratio term weighted by bin share.',
  visual: 'Cosine distance between PCA-64 image embeddings of canonical renders; rejected in evaluation, kept for comparison.',
};
export const MODE_LABEL: Record<StoredYearMode | 'today', string> = {
  same: 'Same year',
  today: 'Today',
  near: 'Within ±N',
  range: 'Range',
  any: 'Any year',
};
export const SEX_LABEL = { '2': 'Two-sex', '1': 'Total only' } as const;
export const DIV_LABEL: Record<string, string> = { '0': 'strict', '0.5': 'balanced', '2': 'spread' };
export const DIV_HINT: Record<string, string> = {
  '0': 'Plain farthest-k.',
  '0.5': 'Farthest-k, nudged apart so two near-identical opposites do not both appear.',
  '2': 'Spread widely across the farthest quartile; raw ranks drift into the tens.',
};
export const TREND_LABEL: Record<Trend, string> = { motion: 'motion', path: 'path' };
export const TREND_HINT: Record<Trend, string> = {
  motion: 'Who is moving the same way: distance between the two L-year changes of the shares (size- and level-free).',
  path: 'Who is at the same place and moving the same way: mean Shape distance over the aligned L-year path.',
};
export const BAND_LABEL: Record<BandLabel, string> = {
  very_close: 'very close',
  close: 'close',
  typical: 'typical',
  far: 'far',
  extreme: 'extreme',
};
export const BAND_HINT: Record<BandLabel, string> = {
  very_close: 'closer than 95 % of random pairs of this kind',
  close: 'closer than 75 % of random pairs',
  typical: 'between the 25th and 75th percentile of random pairs',
  far: 'farther than 75 % of random pairs',
  extreme: 'farther than 95 % of random pairs',
};

export function divLabel(div: Div): string {
  return DIV_LABEL[String(div)] ?? String(div);
}

/** '100k' · '1M' · '10k' · 'no floor' — population floor in persons. */
export function fmtMinpop(persons: number): string {
  if (persons <= 0) return 'no floor';
  if (persons >= 1_000_000 && persons % 1_000_000 === 0) return `${persons / 1_000_000}M`;
  if (persons >= 1_000 && persons % 1_000 === 0) return `${persons / 1_000}k`;
  return persons.toLocaleString('en-US');
}

/** '(+14 y)' · '(−21 y)' · '' for Δy = 0. */
export function dyLabel(dy: number): string {
  if (dy === 0) return '';
  return `(${dy > 0 ? '+' : '−'}${Math.abs(dy)} y)`;
}

/** Percentile as copy: 99.6 → '99.6 %', 62 → '62 %'. */
export function fmtPercentile(p: number): string {
  const r = p >= 99 || p <= 1 ? Math.round(p * 10) / 10 : Math.round(p);
  return `${r} %`;
}

// ---- year window --------------------------------------------------------------------------------------------

export interface YearWindow {
  lo: number;
  hi: number;
  label: string; // '2026' · '2016–2036' · 'any year (1950–2026)' · '2026 (today)'
}

/** Upper edge of the candidate years under an era (obs = ≤ max(last observed, current year)). */
export function eraEdge(era: EraMode, currentYear: number, lastObserved: number): number {
  return era === 'all' ? YEAR_MAX : Math.max(lastObserved, currentYear);
}

/** The effective candidate-year window after the era cap (mirrors `candidate_mask` in search.py). */
export function yearWindow(q: CountryQuery, currentYear: number, lastObserved: number): YearWindow {
  // An explicit `era=obs` caps a projected query too (PLAN §6 J8: the inverted chip writes it on purpose).
  const cap = eraEdge(effectiveEra(q, currentYear), currentYear, lastObserved);
  let lo = YEAR_MIN;
  let hi = YEAR_MAX;
  switch (q.mode) {
    case 'same':
      return { lo: q.year, hi: q.year, label: String(q.year) };
    case 'near':
      lo = Math.max(YEAR_MIN, q.year - q.n);
      hi = Math.min(YEAR_MAX, q.year + q.n);
      break;
    case 'range':
      lo = q.from ?? YEAR_MIN;
      hi = q.to ?? YEAR_MAX;
      if (q.via === 'today') return { lo, hi, label: `${lo} (today)` };
      break;
    case 'any':
      break;
  }
  hi = Math.min(hi, cap);
  if (hi < lo) hi = lo;
  if (q.mode === 'any') return { lo, hi, label: `any year (${lo}–${hi})` };
  return { lo, hi, label: lo === hi ? String(lo) : `${lo}–${hi}` };
}

/** 'Any year (1950–2026)' / '(1950–2100)' — the segmented-control label follows the effective era (J8). */
export function anyYearLabel(q: Pick<CountryQuery, 'year' | 'era'>, currentYear: number, lastObserved: number): string {
  return `Any year (${YEAR_MIN}–${eraEdge(effectiveEra(q, currentYear), currentYear, lastObserved)})`;
}

// ---- the restated query -----------------------------------------------------------------------------------

export interface RestateContext {
  name: string; // focal short name
  currentYear: number;
  lastObserved: number;
}

/**
 * "5 most similar and 5 most different pyramids of 2026 · countries ≥ 100k · excluding Japan · Shape".
 * Non-default constraints append themselves: '· total only', '· projections included', '· trend (motion, 10 y)'.
 */
export function restateQuery(q: CountryQuery, ctx: RestateContext): string {
  const w = yearWindow(q, ctx.currentYear, ctx.lastObserved);
  const parts: string[] = [];
  parts.push(`${q.k} most similar and ${q.k} most different pyramids of ${w.label}`);
  const who = q.scope === 'all' ? 'countries and regions' : 'countries';
  parts.push(q.minpop > 0 ? `${who} ≥ ${fmtMinpop(q.minpop)}` : `${who}, no population floor`);
  parts.push(`excluding ${ctx.name}`);
  parts.push(q.trend ? `trend (${TREND_LABEL[q.trend]}, ${q.L} y)` : shortMetric(q.metric));
  if (q.sex === '1') parts.push('total only');
  if (q.mode !== 'same') {
    const era = effectiveEra(q, ctx.currentYear);
    if (era === 'all') parts.push('projections included');
    else if (q.year > ctx.currentYear) parts.push('observed years only');
  }
  if (q.div !== 0.5) parts.push(`${divLabel(q.div)} opposites`);
  return parts.join(' · ');
}

function shortMetric(m: Metric): string {
  return m === 'visual' ? 'Visual (experimental)' : METRIC_LABEL[m];
}

// ---- era chip (J8) ------------------------------------------------------------------------------------------

export interface EraChip {
  text: string; // 'projections hidden (74 years)' | 'projections included (query is a projection)' | 'projections included'
  action: string; // 'include' | 'observed only' | 'hide'
  target: EraMode; // era to write when the action is clicked (may equal the default → elided)
}

/** The count chip beside cross-year results; null in same-year mode (candidates are the query's own year). */
export function eraChip(q: Pick<CountryQuery, 'mode' | 'year' | 'era'>, currentYear: number): EraChip | null {
  if (q.mode === 'same') return null;
  const era = effectiveEra(q, currentYear);
  const projected = q.year > currentYear;
  if (era === 'obs') {
    return { text: `projections hidden (${YEAR_MAX - currentYear} years)`, action: 'include', target: 'all' };
  }
  return projected
    ? { text: 'projections included (query is a projection)', action: 'observed only', target: 'obs' }
    : { text: 'projections included', action: 'hide', target: 'obs' };
}

/** Which controls deviate from their defaults (drives the "More" auto-open and the Reset button). */
export function nonDefaultControls(s: SearchOptions, dflt: SearchOptions): Array<keyof SearchOptions> {
  return (Object.keys(dflt) as Array<keyof SearchOptions>).filter((k) => s[k] !== dflt[k]);
}

// ---- headlines --------------------------------------------------------------------------------------------

/** "Japan 2026 vs Central African Republic 2026: farther than 99.6 % of random pairs". */
export function oppositesHeadline(
  q: { name: string; year: number },
  c: { name: string; year: number },
  percentile: number | null,
  nCandidates: number,
): string {
  const head = `${q.name} ${q.year} vs ${c.name} ${c.year}`;
  if (percentile === null) return `${head}: the farthest of ${nCandidates} candidates`;
  return `${head}: farther than ${fmtPercentile(percentile)} of random pairs`;
}

/** 'more isolated than 91 % of countries this year' (percentile of the focal isolation among same-year countries). */
export function isolationText(percentile: number): string {
  return `more isolated than ${Math.round(percentile)} % of countries this year`;
}

/** Cross-year card title: 'Germany 2040 (+14 y)'. */
export function cardTitle(name: string, year: number, dy: number): string {
  const l = dyLabel(dy);
  return l ? `${name} ${year} ${l}` : `${name} ${year}`;
}

/** 'strictly farthest: QAT, CAF, NER, SOM, TCD' — only when the diversified list differs. */
export function strictStrip(diversified: string[], strict: string[]): string | null {
  if (strict.length === 0) return null;
  const same = diversified.length === strict.length && diversified.every((id, i) => id === strict[i]);
  return same ? null : `strictly farthest: ${strict.join(', ')}`;
}

// ---- trend reason (PLAN §4 trend spec: "base fell 3.1 pts vs 2.9 pts") ---------------------------------------

export interface FeaturePair {
  now: Features;
  prev: Features;
}

const signed = (v: number, digits: number, unit: string) =>
  `${v > 0 ? '+' : v < 0 ? '−' : '±'}${Math.abs(v).toFixed(digits)}${unit}`;

/**
 * "U15 −7.3 vs −3.8 pts · 65+ +0.9 vs +0.4 pts · median age +3.1 vs +2.0 y · WA sex ratio −0.01 vs +0.00"
 * — the query's and the candidate's L-year movements side by side (mirrors `trend_reason` in scripts/query.py).
 */
export function trendReason(q: FeaturePair, c: FeaturePair): string {
  const d = (p: FeaturePair, f: 'u15' | 'o65' | 'median_age' | 'wa_sex_ratio') => p.now[f] - p.prev[f];
  return [
    `U15 ${signed(d(q, 'u15') * 100, 1, '')} vs ${signed(d(c, 'u15') * 100, 1, '')} pts`,
    `65+ ${signed(d(q, 'o65') * 100, 1, '')} vs ${signed(d(c, 'o65') * 100, 1, '')} pts`,
    `median age ${signed(d(q, 'median_age'), 1, '')} vs ${signed(d(c, 'median_age'), 1, '')} y`,
    `WA sex ratio ${signed(d(q, 'wa_sex_ratio'), 2, '')} vs ${signed(d(c, 'wa_sex_ratio'), 2, '')}`,
  ].join(' · ');
}
