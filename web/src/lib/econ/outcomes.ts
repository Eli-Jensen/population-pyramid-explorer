/**
 * Cohort outcomes (PLAN §7 `CohortOutcomes`): for the pyramids that resembled the focal one — each in its own year —
 * the distribution of what happened to GDP per capita over the following h years, the focal country's own outcome
 * and rank, and an index-return strip restricted to the members that had a US-listed single-country fund at their
 * year (each beside VT over the identical window). Pure over `EconData`; n is always carried so the UI prints it.
 * Never a score, never sorted by return — the strip is ordered by the shape rank the caller passed in.
 */

import { cagr, gdppc, lastGdpYear, marketRow, type EconData, type InstrumentWindow } from '../econ.ts';

export interface Match {
  iso3: string;
  year: number;
}
export interface CohortPoint extends Match {
  rank: number; // 1-based shape rank as passed in
  fromValue: number;
  toYear: number;
  years: number;
  pctPerYear: number;
  clipped: boolean;
}
export interface FundPoint extends Match {
  rank: number;
  ticker: string;
  /** The window shown for that member (y→y+h when year-end levels are shipped, else the precomputed window). */
  window: InstrumentWindow;
  status: 'live' | 'liquidated' | 'liquidating';
}
export interface CohortOutcome {
  h: number;
  minYears: number;
  n: number; // members with a computable window
  nMatches: number; // members passed in
  nNoWindow: number; // members whose window has not elapsed (or no series)
  points: CohortPoint[];
  median: number | null;
  q1: number | null;
  q3: number | null;
  focal: CohortPoint | null;
  /** 1-based rank of the focal outcome among points ∪ focal (1 = highest growth), null without a focal window. */
  focalRank: number | null;
  nWithFund: number;
  funds: FundPoint[];
  /** VT (or proxy) over each fund window is inside `funds[].window.rVt`; this is their plain mean, for the caption. */
  meanFund: number | null;
  meanVt: number | null;
  tooFewFunds: boolean; // nWithFund < minFunds → "n = k with a fund; too few to conclude"
  minFunds: number;
}

/** Linear-interpolated quantile of a sorted array. */
export function quantile(sorted: readonly number[], q: number): number | null {
  if (sorted.length === 0) return null;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo]! + (sorted[hi]! - sorted[lo]!) * (pos - lo);
}

function point(e: EconData, m: Match, rank: number, h: number, minYears: number): CohortPoint | null {
  const y0 = gdppc(e, m.iso3, m.year);
  const last = lastGdpYear(e, m.iso3);
  if (y0 === null || last === null) return null;
  let to = m.year + h;
  let clipped = false;
  if (to > last) {
    to = last;
    clipped = true;
  }
  if (to - m.year < minYears) return null;
  const y1 = gdppc(e, m.iso3, to);
  if (y1 === null) return null;
  return { ...m, rank, fromValue: y0, toYear: to, years: to - m.year, pctPerYear: cagr(y0, y1, to - m.year), clipped };
}

/**
 * Cohort outcomes over `h` years (20 by default). A window shorter than `minYears` (after clipping to the last data
 * year) does not count. `minFunds` is the "too few to conclude" floor (10, PLAN §7).
 */
export function cohortOutcomes(e: EconData, matches: readonly Match[], focal: Match | null, opts: { h?: number; minYears?: number; minFunds?: number } = {}): CohortOutcome {
  const h = opts.h ?? 20;
  const minYears = opts.minYears ?? Math.min(10, h);
  const minFunds = opts.minFunds ?? 10;
  const points: CohortPoint[] = [];
  const funds: FundPoint[] = [];
  matches.forEach((m, i) => {
    const p = point(e, m, i + 1, h, minYears);
    if (p) points.push(p);
    const row = marketRow(e, m.iso3, m.year, h);
    if ((row.kind === 'existed' || row.kind === 'liquidated') && row.instrument && row.window && row.window.y1 <= m.year) {
      funds.push({ ...m, rank: i + 1, ticker: row.instrument.ticker, window: row.window, status: row.instrument.status });
    }
  });
  const sorted = points.map((p) => p.pctPerYear).sort((a, b) => a - b);
  const focalPoint = focal ? point(e, focal, 0, h, minYears) : null;
  let focalRank: number | null = null;
  if (focalPoint) {
    const all = [...sorted, focalPoint.pctPerYear].sort((a, b) => b - a);
    focalRank = all.indexOf(focalPoint.pctPerYear) + 1;
  }
  const fundR = funds.map((f) => f.window.r).filter((r): r is number => r !== null);
  const fundVt = funds.map((f) => f.window.rVt).filter((r): r is number => r !== null);
  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  return {
    h,
    minYears,
    n: points.length,
    nMatches: matches.length,
    nNoWindow: matches.length - points.length,
    points,
    median: quantile(sorted, 0.5),
    q1: quantile(sorted, 0.25),
    q3: quantile(sorted, 0.75),
    focal: focalPoint,
    focalRank,
    nWithFund: funds.length,
    funds,
    meanFund: mean(fundR),
    meanVt: mean(fundVt),
    tooFewFunds: funds.length < minFunds,
    minFunds,
  };
}

/** "n = 3 with a fund; too few to conclude" / "n = 12 with a fund" (PLAN §7 wording). */
export function fundCaption(o: Pick<CohortOutcome, 'nWithFund' | 'tooFewFunds'>): string {
  return o.tooFewFunds ? `n = ${o.nWithFund} with a fund; too few to conclude` : `n = ${o.nWithFund} with a fund`;
}

export { fmtMultiple, fmtPctYr } from './fmt.ts';
