/**
 * Typed view of `web/src/data/evidence.json` (scripts/export_econ_ui.py ← evals/evidence.yaml + evals/econ/*.json) —
 * everything pages/Evidence.svelte renders. Nothing on that page is typed by hand: a re-run of the backtest rewrites it.
 * Loaded only by the Evidence chunk.
 */

import evidenceJson from '../../data/evidence.json';

export interface Finding {
  claim: string;
  effect: string | null;
  sample: string | null;
  citation: string | null;
  url: string | null;
  verified: boolean | null;
  companion_url?: string | null;
  companion_verified?: boolean | null;
}
export interface Link {
  id: string;
  title: string;
  direction: string | null;
  strength: string | null;
  summary: string;
  findings: Finding[];
}
export interface ChinaRow {
  label: string;
  wa_pct: number;
  dependency: number;
  median_age: number;
  tfr: number;
  gdppc_ppp_2021usd: number;
  note?: string;
}
export interface DisconnectRow {
  iso3: string;
  year: number;
  kind: 'history' | 'now';
  name: string;
  pyramid: { median_age: number; u15: number; wa: number; o65: number; s0_s20: number; tfr: number | null };
  distance: { d_blend_chn1990: number; pct_same_year: number | null; pct_band: string; n_same_year: number };
  /** `source` names the level series behind y_t (PWT 11.0 rgdpe/pop, 2017 PPP $ — or Maddison 2023, 2011 $), from tables/gdp_pc.parquet. */
  levels: { y_t: number | null; multiples: Record<string, number> | null; y_last_year: number | null; mult_last: number | null; state: string | null; source: string | null };
  msci: {
    state: string | null;
    index_name: string | null;
    since: string | null;
    clipped_to_index_history: boolean | null;
    ann_pct_gross_since: number | null;
    ann_pct_net_since: number | null;
    net_since: string | null;
    max_drawdown_pct_gross: number | null;
    max_drawdown_period_gross: [string, string] | null;
    url_gross: string | null;
    url_net: string | null;
    accessed: string | null;
    as_of: string | null;
  };
  fund: {
    state: string | null;
    ticker: string | null;
    name: string | null;
    issuer: string | null;
    inception: string | null;
    delisted: string | null;
    entry_used: string | null;
    exit_used: string | null;
    window_years: number | null;
    ann_log_return: number | null;
    cagr: number | null;
    total_return: number | null;
    too_short_to_annualise: boolean | null;
    max_dd: number | null;
    status: string | null;
    /** Fund total log return over the span (for windows too short to annualise). */
    total_log_return: number | null;
    cagr_pct: number | null;
    /** VT / SPY / EEM over the identical window: annualised log (fraction), CAGR %/yr, total log over the span. */
    vt: number | null;
    vt_cagr_pct: number | null;
    vt_total_log: number | null;
    vt_total_pct: number | null;
    vt_benchmark: string | null;
    spy: number | null;
    spy_cagr_pct: number | null;
    spy_total_log: number | null;
    eem: number | null;
    eem_cagr_pct: number | null;
    eem_total_log: number | null;
  };
}
export interface GrowthPerT {
  T: number;
  n: number;
  mean_excess: number;
  hit_rate: number;
  median_g: number;
  n_candidates: number;
  partial: boolean;
  members: { iso3: string; eg: number; g: number; src: string }[];
}
export interface GrowthRow {
  key: string;
  query_name: string;
  k: number;
  h: number;
  n: number;
  n_partial: number;
  n_eff: number;
  hit_rate: number;
  top_quartile_rate: number;
  mean_excess: number;
  ci_headline: [number, number];
  ci_country_cluster: [number, number];
  ci_block_T: [number, number];
  ci_block_T_degenerate: boolean;
  hh_p: number | null;
  nw2_p: number | null;
  nw4_p: number | null;
  cluster_p: number | null;
  bootstrap_B: number | null;
  nulls: {
    N1: { p: number; share: number; null_mean: number; B: number };
    N2: { p: number; share: number; null_mean: number; B: number; caliper: number | null };
    N4: { p: number; mean_excess_N4: number; delta: number; ci: [number, number] };
  };
  per_T: GrowthPerT[];
}
/** A lookalike's fund window in both units: `*_pp` annualised log (pp/yr, RESULTS §4), `*_cagr` %/yr (the L0.vs_vt unit). */
export interface ReturnsPick {
  iso3: string;
  status: string;
  ticker: string | null;
  r_pp: number | null;
  r_vt_pp: number | null;
  er_pp: number | null;
  r_cagr: number | null;
  r_vt_cagr: number | null;
  inception: string | null;
  /** The frozen universe file's liquidation date and the etf_manual.yaml (SEC filings) last trading day the arithmetic used. */
  delisted_universe: string | null;
  last_trading_day: string | null;
}
export interface ReturnsPerT {
  T: number;
  benchmark: string;
  r_vt: number; // pp/yr log
  r_vt_cagr: number; // %/yr
  r_ew: number; // pp/yr log
  r_ew_cagr: number; // %/yr
  ew_n: number;
  investable_share: number;
  investable_candidates: number;
  n_candidates: number;
  status_counts: Record<string, number>;
  members: ReturnsPick[];
}
export interface ReturnsRow {
  key: string;
  query_name: string;
  k: number;
  h: number;
  n: number;
  n_eff: number;
  hit_rate: number;
  mean_excess_vs_vt: number;
  mean_r: number | null;
  ci_headline: [number, number];
  ci_degenerate: boolean;
  status_counts: Record<string, number>;
  ladder_incomplete: { T: number; iso3: string; ticker: string; status: string; spans: string }[];
  vs: Record<string, { n: number; mean_excess: number; ci_headline: [number, number] }>;
  oos_block_T_ge_2010: { n: number; mean_excess_vs_vt: number; same_sign_as_pooled: boolean };
  nulls: { N1_investable: { p: number; null_mean: number; B: number }; N4_investable: { p: number | null; mean_excess_N4: number | null } };
  per_T: ReturnsPerT[];
}
export interface Benchmark {
  T: number;
  r_vt_ann: number; // annualised log, fraction
  r_vt_cagr: number; // %/yr
  r_vt_log: number;
  benchmark: string;
  entry: string;
  exit: string;
  legs: { from: string; to: string; weights: Record<string, number> }[];
  ew: { r_ann: number; r_cagr: number; n: number; n_liquidated: number | null; incomplete: string[] };
  spy: number | null;
  efa: number | null;
  eem: number | null;
  spy_cagr: number | null;
  efa_cagr: number | null;
  eem_cagr: number | null;
}
export interface VintageRow {
  T: number;
  revision: number;
  query: string;
  k: number;
  wpp2024: string[];
  archive: string[];
  common: number;
  jaccard: number;
  met: boolean | null;
  rho: number | null;
}
export interface InvestabilityRow {
  ticker: string;
  iso3: string | null;
  role: string;
  name: string | null;
  issuer: string | null;
  inception: string | null;
  inception_verified: string | null;
  status: string | null;
  delisted_universe: string | null;
  last_trading_day: string | null;
  liquidation_date: string | null;
  status_url: string | null;
  liquidation_source_url: string | null;
  source_url: string | null;
  msci_class: string | null;
}
export interface Evidence {
  version: number;
  built: string;
  backtest_git_rev: string;
  prereg_commit: string;
  transcribed: string | null;
  source_doc: string | null;
  question: string;
  links: Link[];
  china: { source: string | null; columns: string[]; rows: ChinaRow[]; reading: string; row: DisconnectRow | null };
  disconnect: { meta: Record<string, unknown>; rows: DisconnectRow[] };
  backtest: {
    T_grid: number[];
    returns_T: number[];
    minpop_thousands: number;
    B: number;
    seed: number;
    prototype_rule: { decile: number; max_per_country: number; min_gap_years: number };
    no_etf_rows: Record<string, string>;
    /** RESULTS §1's parenthetical on the partial T = 2015 windows ("PWT h = 8 → 2023, Maddison h = 7 → 2022"). */
    partial_note: string | null;
    growth: GrowthRow;
    growth_20: GrowthRow;
    returns: ReturnsRow;
    n3: { delta: number; ci_headline: [number, number]; p_one_sided: number; mean_excess_42: number; mean_excess_3band: number; B: number };
    benchmarks: Benchmark[];
    ew_minus_vt: Record<string, number> | null;
    predictions: Record<string, { statement: string; met: boolean }>;
  };
  decision: {
    levels_granted: string[];
    levels: Record<string, { name: string; granted: boolean; requires: string[]; failed: string[]; unavailable: string[]; note: string | null }>;
    conditions: Record<string, { value: unknown; ok: boolean; available: boolean; detail: string }>;
    allowed_sentence_ids: string[];
    rendered: Record<string, string[]>;
    /** Frozen rendered sentences whose liquidation date etf_manual.yaml corrected from SEC filings (RESULTS §10). */
    rendered_notes: { sentence: string; ticker: string; universe_date: string; last_trading_day: string }[];
  };
  units_note: string;
  vintage: {
    expectation: string;
    threshold: number;
    cells: number;
    cells_met: number;
    not_met: string[];
    B_k10_met_at_every_T: boolean;
    revision_rule: string;
    self_check_passed: boolean;
    /** Range of the per-query Spearman ρ between the WPP 2024 and archive selection statistics (rank continuity). */
    spearman: { min: number; max: number; n: number } | null;
    sources: Record<string, { revision: number; zip: string; url: string; zip_sha256: string }>;
    rows: VintageRow[];
    caveats: string[];
  };
  investability: { as_of: string | null; n: number; rows: InvestabilityRow[]; manual_deviations: string[] };
  deviations: string[];
  data_vintages: { source: string; family: string; vintage: string; licence: string; shipped: string; fetched: string; sha256: string }[];
  data_vintages_note: string | null;
  licences: {
    shipped: { name: string; licence: string; cite: string; url: string }[];
    cited_only: { name: string; terms: string }[];
  };
  never_does: string[];
  notice: string;
}

export const evidence = evidenceJson as unknown as Evidence;

// ------------------------------------------------------------------------------------------------ formatting

/** Signed pp/yr or %/yr with one decimal, ASCII minus. */
export function pp(v: number | null | undefined, digits = 1, unit = ''): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/a';
  const s = v.toFixed(digits);
  return `${v >= 0 && !s.startsWith('-') ? '+' : ''}${s}${unit}`;
}
/** Annualised log return (fraction) → %/yr CAGR: 100·(e^r − 1). */
export function logToCagr(r: number | null | undefined): number | null {
  return r === null || r === undefined || !Number.isFinite(r) ? null : 100 * (Math.exp(r) - 1);
}
/** Total log return over a span → total simple return as a fraction, e^r − 1 (for `pct()`). */
export function logToTotal(r: number | null | undefined): number | null {
  return r === null || r === undefined || !Number.isFinite(r) ? null : Math.exp(r) - 1;
}
/** "includes 0" / "excludes 0" for a CI, derived rather than typed. */
export function ciCovers0(c: [number, number] | null | undefined): string {
  if (!c) return 'n/a';
  return c[0] <= 0 && c[1] >= 0 ? 'includes 0' : 'excludes 0';
}
/** "top decile" for 0.9, else "top 5 %"-style, from the prototype rule's decile. */
export function topShare(decile: number | null | undefined): string {
  if (decile === null || decile === undefined || !Number.isFinite(decile)) return 'top-share';
  const share = Math.round(100 * (1 - decile));
  return share === 10 ? 'top-decile' : share === 25 ? 'top-quartile' : `top-${share} %`;
}
export function ci(c: [number, number] | null | undefined, digits = 2): string {
  if (!c) return 'n/a';
  return `[${pp(c[0], digits)}, ${pp(c[1], digits)}]`;
}
export function pct(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined || !Number.isFinite(v) ? 'n/a' : `${(100 * v).toFixed(digits)} %`;
}
export function p(v: number | null | undefined): string {
  return v === null || v === undefined || !Number.isFinite(v) ? 'n/a' : v.toFixed(3);
}
export function num(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || !Number.isFinite(v) ? 'n/a' : v.toFixed(digits);
}
export function multiple(v: number | null | undefined): string {
  return v === null || v === undefined || !Number.isFinite(v) ? 'n/a' : `${v.toFixed(v >= 10 ? 0 : 1)}×`;
}
export const STATUS_LABEL: Record<string, string> = {
  no_fund_ever: 'no US-listed fund, ever',
  no_fund_at_entry: 'no fund at entry',
  liquidated_in_window: 'liquidated inside the window',
  investable: 'fund at entry',
  ok: 'fund at entry',
};
