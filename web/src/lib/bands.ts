/**
 * Percentile bands — twin of `pyramid_explorer.bands.band_label` plus the table-selection rule of PLAN §3.4a.
 *
 * Tables (parsed by `data.parseBands`, names `/`-joined, values on the 24-point `GRID`):
 *   `same/{metric}/{sex}/{year}`            random same-year country pairs ≥ 100k
 *   `cross/{metric}/{sex}/{era}/{decade}`   pairs (q in decade, c in any year the era allows)
 *   `best/{metric}/{sex}/{era}/{decade}`    min_y d(q, c_y) — the null for time-shift rows and `best` matches
 *
 * Selection is by |Δy| and the EFFECTIVE era, never by UI mode: Δy = 0 → `same[query year]`; otherwise
 * `cross[era][decade of the query year]`; time-shift rows → `best[...]`. The effective era is the query's era
 * after the projected-year flip (PLAN §6 J8: `obs` with `year > currentYear` → `all`). The table metric is
 * `trend@L` in trend/motion mode, `visual:<model>` for the Visual metric and — documented proxy — `blend` in
 * path mode (a path distance is a mean of blend distances; no `path` tables are built).
 *
 * Labels (`band_label`, checked in this order): extreme ≥ p95 · far ≥ p75 · very_close ≤ p5 · close ≤ p25 ·
 * typical. The percentile of `d` is linear interpolation on the grid (≤ q[0] → 0, ≥ q[23] → 100); the fixture
 * `evals/fixtures/search_cases.json` pins both against `scripts/search_fixture.py`.
 */

import { bandTable, meta } from './data.ts';
import type { Bands, Sex } from './types.ts';

export type BandLabel = 'very_close' | 'close' | 'typical' | 'far' | 'extreme';
export type BandKind = 'same' | 'cross' | 'best';
export type Era = 'obs' | 'all';

/** The 24 percentile grid points every table is stored on (CONTRACT §3 `bands.GRID`). */
export const GRID: readonly number[] = [0, 1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 97, 98, 99, 99.5, 99.9, 100];
const P = { 5: GRID.indexOf(5), 25: GRID.indexOf(25), 75: GRID.indexOf(75), 95: GRID.indexOf(95) } as const;

export interface BandResult {
  label: BandLabel;
  /** Percentile of `d` among the table's random pairs (0–100), or null when no table exists. */
  percentile: number | null;
  /** The table that was used, or null when it is absent (label is then the neutral placeholder 'typical'). */
  table: string | null;
}

/** `'very_close' ≤ p5 · 'close' ≤ p25 · 'typical' · 'far' ≥ p75 · 'extreme' ≥ p95` (Python `band_label`). */
export function bandLabel(d: number, quantiles: ArrayLike<number>): BandLabel {
  if (quantiles.length !== GRID.length) throw new Error(`bandLabel: expected ${GRID.length} quantiles, got ${quantiles.length}`);
  if (d >= quantiles[P[95]]) return 'extreme';
  if (d >= quantiles[P[75]]) return 'far';
  if (d <= quantiles[P[5]]) return 'very_close';
  if (d <= quantiles[P[25]]) return 'close';
  return 'typical';
}

/** Percentile of `d` by linear interpolation between grid quantiles (`scripts/search_fixture.py::percentile_of`). */
export function percentileOf(d: number, quantiles: ArrayLike<number>): number {
  const n = quantiles.length;
  if (n !== GRID.length) throw new Error(`percentileOf: expected ${GRID.length} quantiles, got ${n}`);
  if (d <= quantiles[0]) return 0;
  if (d >= quantiles[n - 1]) return 100;
  // i = (number of quantiles ≤ d) − 1, so q[i] ≤ d < q[i+1] and the segment has positive width
  let i = 0;
  while (i + 1 < n && quantiles[i + 1] <= d) i++;
  const lo = quantiles[i];
  const hi = quantiles[i + 1];
  return GRID[i] + ((d - lo) / (hi - lo)) * (GRID[i + 1] - GRID[i]);
}

/** J8 default for a caller holding an UNRESOLVED era: `obs` stays only while the query year is not a projection
 *  (`search.ts` takes `q.era` as already resolved — see `candidateMask`). */
export function effectiveEra(era: Era, queryYear: number, currentYear: number): Era {
  return era === 'obs' && queryYear > currentYear ? 'all' : era;
}

/** Decade key of a query year (`1950 … 2100`). */
export function decadeOf(year: number): number {
  return Math.floor(year / 10) * 10;
}

/** The image model whose tables/embedding the `visual` metric uses (`meta.verdicts.exposed_visual`). */
export function exposedVisualModel(): string {
  const m = meta.verdicts?.exposed_visual?.model ?? Object.keys(meta.files.emb)[0];
  if (!m) throw new Error('no visual model is shipped (meta.files.emb is empty)');
  return m;
}

/**
 * Metric name used in table names: `trend@L` (motion), `blend` (path — proxy), `visual:<model>`, else the metric.
 */
export function tableMetric(q: { metric: string; trend: null | 'motion' | 'path'; L: number }, visualModel?: string): string {
  if (q.trend === 'motion') return `trend@${q.L}`;
  if (q.trend === 'path') return 'blend';
  if (q.metric === 'visual') return `visual:${visualModel ?? exposedVisualModel()}`;
  return q.metric;
}

/** Which family a (query, candidate) pair reads from: same year → `same`, otherwise `cross`. */
export function bandKind(dy: number): BandKind {
  return dy === 0 ? 'same' : 'cross';
}

/** `/`-joined table name for a lookup (era must already be the effective era). */
export function tableName(kind: BandKind, metric: string, sex: Sex, queryYear: number, era: Era): string {
  if (kind === 'same') return `same/${metric}/${sex}/${queryYear}`;
  return `${kind}/${metric}/${sex}/${era}/${decadeOf(queryYear)}`;
}

/**
 * Band + percentile of a distance. `metric` is the TABLE metric (see `tableMetric`); `era` the effective era;
 * `kind` 'best' for time-shift rows, otherwise it is derived from `candYear − queryYear` (a 'same'/'cross'
 * argument is accepted and honoured only when consistent with Δy — Δy decides, per PLAN §3.4a).
 * Without a table (bands not loaded, or the cell is absent) the label is 'typical' and `percentile`/`table` null.
 */
export function bandFor(
  bands: Bands | null | undefined,
  metric: string,
  sex: Sex,
  queryYear: number,
  candYear: number,
  era: Era,
  d: number,
  kind: BandKind = bandKind(candYear - queryYear),
): BandResult {
  const k: BandKind = kind === 'best' ? 'best' : bandKind(candYear - queryYear);
  const name = tableName(k, metric, sex, queryYear, era);
  const t = bands ? bandTable(bands, name) : undefined;
  if (!t || t.length !== GRID.length || !Number.isFinite(d)) return { label: 'typical', percentile: null, table: null };
  return { label: bandLabel(d, t), percentile: percentileOf(d, t), table: name };
}
