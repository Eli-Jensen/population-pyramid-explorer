/**
 * Copy templates for `explain.ts` (PLAN §4.4). Pure string builders — no data access, no DOM — so the same
 * sentence is produced wherever a pair is explained (country-page card or compare page). Wording avoids
 * finance vocabulary and stays descriptive ("alike in", "differs most in", "years of age movement").
 */

import { N_BINS } from './types.ts';
import type { Sex } from './types.ts';
import type { BandLabel } from './bands.ts';
import type { Metric } from './search.ts';

/** The six features an explanation sentence may name (query.py `EXPLAIN`). */
export const EXPLAIN_FEATURES = ['median_age', 'o65', 'u15', 'base_slope_20', 'wa_sex_ratio', 'modal_bin'] as const;
export type ExplainFeature = (typeof EXPLAIN_FEATURES)[number];

export const FEATURE_LABELS: Record<ExplainFeature, string> = {
  median_age: 'median age',
  o65: '65+ share',
  u15: 'under-15 share',
  base_slope_20: 'base slope (0–4 vs 20–24)',
  wa_sex_ratio: 'working-age sex ratio',
  modal_bin: 'modal age bin',
};

export const BAND_TEXT: Record<BandLabel, string> = {
  very_close: 'very close',
  close: 'close',
  typical: 'typical',
  far: 'far',
  extreme: 'extreme',
};

export const METRIC_LABELS: Record<Metric, string> = {
  blend: 'Shape',
  l2: 'Bin-by-bin',
  w1: 'Age-shift (years)',
  l2s: 'Shift-tolerant',
  hel: 'Elderly-tail weighted',
  feat: 'Summary statistics',
  w1sex: 'Per-sex age-shift (years)',
  w1bal: 'Balanced age-shift (years)',
  visual: 'Visual (experimental)',
};

const NBSP = ' '; // plain space between a number and its unit (kept ASCII so snapshots and greps stay honest)

/** Format one feature value the way query.py's `FMT` does (percent shares, 1–2 decimals, bin as an age range). */
export function formatFeature(name: ExplainFeature, value: number): string {
  if (!Number.isFinite(value)) return 'n/a';
  switch (name) {
    case 'median_age':
      return value.toFixed(1);
    case 'o65':
    case 'u15':
      return `${(100 * value).toFixed(1)}${NBSP}%`;
    case 'base_slope_20':
    case 'wa_sex_ratio':
      return value.toFixed(2);
    case 'modal_bin':
      return value >= 100 ? '100+' : `${value.toFixed(0)}–${(value + 4).toFixed(0)}`;
  }
}

/** Human label of a decomposition bin index: `M 20-24`, `F 100+`; `20-24` for s21 (`metrics.bin_label`). */
export function binLabel(k: number, sex: Sex = '2'): string {
  const prefix = sex === '1' ? '' : k < N_BINS ? 'M ' : 'F ';
  const a = 5 * (k % N_BINS);
  return a === 100 ? `${prefix}100+` : `${prefix}${a}-${a + 4}`;
}

export function joinList(items: string[]): string {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

export interface FeaturePair {
  name: ExplainFeature;
  rawQ: number;
  rawC: number;
}

const pair = (f: FeaturePair) => `${FEATURE_LABELS[f.name]} (${formatFeature(f.name, f.rawQ)} vs ${formatFeature(f.name, f.rawC)})`;

/** "Alike in median age (47.3 vs 44.6) and 65+ share (21.4 % vs 22.3 %)." */
export function becauseSentence(alike: FeaturePair[]): string {
  if (alike.length === 0) return '';
  return `Alike in ${joinList(alike.map(pair))}.`;
}

/** "Differs most in base slope (0–4 vs 20–24) (0.48 vs 0.81)." */
export function differsSentence(differs: FeaturePair[]): string {
  if (differs.length === 0) return '';
  return `Differs most in ${joinList(differs.map(pair))}.`;
}

/** "Only 1.90 years of average age movement separate them." (`Only` below two years). */
export function w1Sentence(years: number): string {
  const y = years.toFixed(2);
  return years < 2 ? `Only ${y} years of average age movement separate them.` : `${y} years of average age movement separate them.`;
}

export interface DecompositionParts {
  metric: 'blend' | 'l2' | 'w1' | 'w1sex';
  d: number;
  l2Part: number;
  w1Part: number;
  w1Years: number;
  topBinsL2: number[]; // bin indices, largest contribution first
  topBinsW1: number[];
  sex: Sex;
}

/**
 * One sentence on the metric that did the ranking:
 * blend → "Shape distance 0.43 = bin-by-bin 0.26 + age-shift 0.17; largest bin gaps M 50-54, M 0-4, F 50-54."
 * l2 → "Bin-by-bin distance 0.024; largest bin gaps …"; w1/w1sex → "Age-shift distance 1.90 years; most movement at …".
 */
export function decompositionSentence(p: DecompositionParts): string {
  const bins = (ks: number[]) => ks.map((k) => binLabel(k, p.sex)).join(', ');
  if (p.metric === 'blend') {
    return `Shape distance ${p.d.toFixed(2)} = bin-by-bin ${p.l2Part.toFixed(2)} + age-shift ${p.w1Part.toFixed(2)}; largest bin gaps ${bins(p.topBinsL2)}.`;
  }
  if (p.metric === 'l2') return `Bin-by-bin distance ${p.d.toFixed(3)}; largest bin gaps ${bins(p.topBinsL2)}.`;
  return `Age-shift distance ${p.d.toFixed(2)} years; most movement at ${bins(p.topBinsW1)}.`;
}

/** "farther than 99.6 % of random pairs" / "closer than 93 % of best-year matches" — percentile in the headline. */
export function percentileClause(percentile: number | null, closer: boolean, population: 'random pairs' | 'best-year matches' = 'random pairs'): string {
  if (percentile === null) return '';
  const p = closer ? 100 - percentile : percentile;
  const shown = p >= 99 || p <= 1 ? p.toFixed(1) : p.toFixed(0);
  return `${closer ? 'closer' : 'farther'} than ${shown}${NBSP}% of ${population}`;
}
