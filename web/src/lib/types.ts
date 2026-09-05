/**
 * Shared types for the web data layer.
 *
 * Mirrors CONTRACT.md §1 (corpus conventions), §2 (entity dict), §5 (binary formats) and the
 * as-built AMENDMENTS §F/§G, plus the shape of `web/src/data/meta.json` / `entities.json`.
 * Nothing here touches the DOM; every consumer (state, search, components) imports from this file.
 */

/** Corpus constants (CONTRACT §1). Derived quantities such as n_entities / n_rows come from `meta.json`. */
export const YEAR_MIN = 1950;
export const YEAR_MAX = 2100;
export const N_YEARS = YEAR_MAX - YEAR_MIN + 1; // 151
export const N_BINS = 21; // 0-4 … 95-99, 100+
export const N_DIMS = 2 * N_BINS; // 42 = 21 male + 21 female shares of TOTAL population
export const BIN_WIDTH = 5;
export const U16_TOTAL = 65535; // every quantised row sums to exactly this
export const AGE_STARTS: readonly number[] = Array.from({ length: N_BINS }, (_, k) => k * BIN_WIDTH);
/** Bytes per corpus row in `shares.*.d16z` / `shares.*.u16` (42 × Uint16). */
export const ROW_BYTES = N_DIMS * 2; // 84

export type EntityType = 'country' | 'aggregate';
export type AggKind = 'world' | 'region' | 'subregion' | 'sdg' | 'income' | 'dev';
/** Fixed symmetric axis choices (PLAN §2): smallest covering the entity's max single-sex bin over all years. */
export type AxisPct = 10 | 12 | 14 | 17;

/** One row of `entities.json`, in corpus order (countries by ISO3, then aggregates `agg-{locid}`). */
export interface Entity {
  id: string; // ISO3 or `agg-{locid}`
  locid: number;
  iso2: string | null; // null for aggregates (no flag emoji)
  name: string; // UN name (subtitle)
  short_name: string; // display name ("Taiwan", "Kosovo", …)
  slug: string; // canonical URL slug
  aliases: string[]; // lower-case; includes iso3, iso2, un-name slug, names.yaml extras
  type: EntityType;
  subregion_locid: number | null;
  region_locid: number | null;
  sdg_region_locid: number | null;
  income_group: string | null; // HIC | UMIC | LMIC | LIC | null
  dev_group: string | null; // more | less | least | null
  pop_2026: number; // thousands (patched frame; equals the shipped 2026 total)
  is_micro: boolean; // pop_2026 < 100 (thousands)
  axis_pct: AxisPct;
  notes: string[]; // UN footnote ids
  // aggregates only
  agg_kind?: AggKind;
  parent_locid?: number;
  members?: string[]; // ISO3 ids
}

/** '2' = two-sex 42-vector, '1' = total-only s21 (CONTRACT §4). */
export type Sex = '1' | '2';
/** metric → sex → σ (median random same-year country-pair distance, AMENDMENTS §F). */
export type SigmaTable = Record<string, Record<Sex, number>>;

export type Verdict = 'default' | 'advanced' | 'menu' | 'lab' | 'rejected';
export interface MetricVerdict {
  verdict: Verdict;
  provisional: boolean;
  scope?: string; // e.g. 'trend-mode'
}
export interface ExposedVisual {
  model: string;
  metric: string; // `visual:${model}`
  C1_obs: number;
  alternates: string[];
  rule?: string;
}
/** `meta.verdicts` (AMENDMENTS §F/§G): merged from evals/verdicts.json by build_data.py. */
export interface Verdicts {
  data_hash: string;
  emb_meta_hash: Record<string, string>;
  stale: boolean;
  metrics: Record<string, MetricVerdict>;
  exposed_visual?: ExposedVisual | null;
}

export interface Patch {
  id: string;
  source_id: string;
  applied: boolean;
  locids: number[];
  recomputed_aggregates: number[];
  recomputed_non_entities?: number[];
  note: string;
}

/** `meta.files`: logical name → path relative to the site root (already includes `data/wpp2024/…`). */
export interface MetaFiles {
  years: string; // directory: `${years}/${year}.u16`
  pyramids: string; // directory: `${pyramids}/${id}.u16`
  shares_d16z: string;
  shares_u16: string;
  totals: string;
  bands: string;
  bands_default: string;
  emb: Record<string, string>; // model → `emb/{model}.{sha8}.f16`
  notice: string;
}

export interface MetaSizes {
  year_shard_max: number;
  entity_shard_max: number;
  shares_d16z: number;
  shares_u16: number;
  totals: number;
  bands: number;
  bands_default: number;
  emb: Record<string, number>;
  entities_json: number;
  entities_gz: number;
  meta_gz?: number;
  first_paint?: number;
  layouts: Record<string, number>;
  bands_tables: Record<string, { tables: number; bytes: number }>;
  dir_total: number;
  dir_total_with_emb?: number;
}

/** `web/src/data/meta.json` (CONTRACT §5 + AMENDMENTS §F). */
export interface Meta {
  revision: string; // 'wpp2024'
  patches: Patch[];
  built: string; // ISO timestamp
  last_observed_year: number; // 2023
  n_entities: number;
  n_countries: number;
  n_rows: number; // n_entities × n_years
  n_years: number; // 151
  files: MetaFiles;
  sigma: SigmaTable;
  kernel: number[]; // 5-tap smoothing kernel (l2s)
  budgets: Record<string, number>;
  sizes: MetaSizes;
  attribution: string[];
  bands_grid: number[]; // 24 percentile grid points
  bands_format: string;
  verdicts?: Verdicts;
}

/** One pyramid: 42 shares of TOTAL population (sum ≈ 1, male 0..20, female 21..41) + total in thousands. */
export interface Pyramid {
  shares: Float32Array; // length 42
  total: number; // thousands
}

/** `years.{sha8}/{year}.u16`: n_entities × 42 Uint16 (entity order) then n_entities Float32 totals. */
export interface YearShard {
  year: number;
  n: number; // n_entities
  u16: Uint16Array; // n × 42
  totals: Float32Array; // n
}

/** `pyramids.{sha8}/{id}.u16`: 151 × 42 Uint16 (1950..2100) then 151 Float32 totals. */
export interface EntityShard {
  id: string;
  u16: Uint16Array; // 151 × 42
  totals: Float32Array; // 151
}

/** Which decode branch tier 3 took (surfaced for SMOKE.md's console check). */
export type CorpusPath = 'gzip-stream' | 'inflated-body' | 'u16-fallback';

/** The whole corpus: row = entity_idx × n_years + (year − 1950). */
export interface Corpus {
  nRows: number;
  nEntities: number;
  nYears: number;
  u16: Uint16Array; // nRows × 42
  totals: Float32Array; // nRows (thousands)
  source: { path: CorpusPath; decodeMs: number; fetchMs: number };
}

/** Parsed `bands*.bin`: `/`-joined names → [offset, count] into float32 values (AMENDMENTS §F). */
export interface Bands {
  index: Record<string, [number, number]>;
  values: Float32Array;
}

/** Parsed `emb/{model}.{sha8}.f16`: nRows × dim Float16 decoded to Float32. */
export interface Embedding {
  model: string;
  nRows: number;
  dim: number; // 64
  values: Float32Array; // nRows × dim, row-major
}
