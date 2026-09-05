/**
 * Typed view of `web/src/data/evals.json` — the similarity-evaluation record exported by `scripts/export_evals.py`
 * (the last step of `make build`) from `evals/verdicts.json` + `evals/RESULTS.md` + `evals/image_embeddings.md`.
 * The About page renders every number from here and from `meta.json`; nothing is hardcoded in the copy.
 */

import evalsJson from '../data/evals.json';
import type { Verdict } from './types.ts';

export interface G1Row {
  metric: string;
  c1_obs: number | null;
  c5_obs: number | null;
  c1_proj: number | null;
  c5_proj: number | null;
  gate: boolean;
}
export interface G2Row {
  metric: string;
  kc2006: number | null;
  kc1996: number | null;
  kc2001: number | null;
  hk_family: number | null;
  hk_fine: number | null;
  stage: number | null;
  rieti_best_year: number | null;
  yoshida_hits: string | null;
  yoshida_pass: boolean | null;
  g4_pass: boolean | null;
  gate: boolean | null;
  gates: Record<string, boolean>;
}
export interface Prediction {
  id: string;
  prediction: string;
  gate: string;
  measured_by: string;
}
export interface ScoredPrediction {
  id: string;
  test: string;
  observed: number;
  met: boolean;
}
export interface ImageSpace {
  model: string;
  metric: string;
  verdict: Verdict;
  c1: number | null;
  c5: number | null;
  c1_proj: number | null;
  c1_full_dim: number | null;
  c1_pca64_embed_script: number | null;
  hk_family: number | null;
  kc2006: number | null;
  stage: number | null;
  spearman_vs_blend: number | null;
  spearman_vs_l2: number | null;
  top10_overlap: number | null;
  top10_overlap_anyyear: number | null;
  predictions_scored: ScoredPrediction[];
  expected_verdict: Verdict;
  prediction_met: boolean;
}
export interface Evals {
  built: string;
  git_head: string | null;
  stage: string;
  informational: boolean;
  data_hash: string;
  data_hash_definition: string | null;
  emb_meta_hash: Record<string, string>;
  n_rows: number;
  n_entities: number;
  n_countries: number;
  n_queries: number;
  n_anchors: number;
  seed: number;
  gates: { c1: number; c5: number; kc_agree: number; hk_agree: number; stage_agree: number; lab_c1: number; reject_hk: number };
  prereg: {
    continuity_gate: { c1: number; c5: number; span: string; definition: string };
    image_predictions: Prediction[];
    expected_visual_verdict: Verdict;
    niche: string;
  };
  g1: G1Row[];
  g2: G2Row[];
  /** `verdict` = the evaluation's word; `shipped` = what meta.json hands the menu (null when not in the web set). */
  verdicts: Record<string, { verdict: Verdict; provisional: boolean; shipped: Verdict | null; shipped_note?: string; scope?: string }>;
  verdicts_stale_in_build: boolean | null;
  exposed_visual: { model: string; metric: string; C1_obs: number; alternates: string[]; rule?: string } | null;
  image_spaces: ImageSpace[];
  blend_w1_share: Record<string, Record<string, number>> | null;
  beta_sweep: Array<{ beta: number; jaccard_vs_strict: number; mean_raw_rank: number; mean_regions: number; identical_to_beta2: number; n: number }> | null;
  div_presets: Record<string, number> | null;
  hk_family_counts_2024: Record<string, number> | null;
  labels_sha256: Record<string, string>;
  notes: string[];
}

export const evals = evalsJson as unknown as Evals;

export const g1Of = (metric: string): G1Row | undefined => evals.g1.find((r) => r.metric === metric);
export const g2Of = (metric: string): G2Row | undefined => evals.g2.find((r) => r.metric === metric);
export const imageSpace = (model: string): ImageSpace | undefined => evals.image_spaces.find((s) => s.model === model);

/** A number to `digits` decimals, or an em dash for null/NaN. */
export function fmt(x: number | null | undefined, digits = 3): string {
  return x === null || x === undefined || !Number.isFinite(x) ? '—' : x.toFixed(digits);
}
/** A fraction as a percent with no decimals: 0.302 → '30 %'. */
export function fmtPctOf(x: number | null | undefined): string {
  return x === null || x === undefined || !Number.isFinite(x) ? '—' : `${Math.round(x * 100)} %`;
}

/** How a verdict shows up in the product (PLAN §4.3, as built). */
export const VERDICT_LABEL: Record<Verdict, string> = {
  default: 'default metric',
  menu: 'in the metric menu',
  advanced: 'under “advanced”',
  lab: 'URL-only (?metric=)',
  rejected: 'rejected',
};

/** Metrics ordered the way RESULTS.md lists them; image spaces last. */
export function orderedMetrics(): string[] {
  const numeric = evals.g1.map((r) => r.metric).filter((m) => !m.startsWith('visual:'));
  const visual = evals.g1.map((r) => r.metric).filter((m) => m.startsWith('visual:'));
  return [...numeric, ...visual];
}
