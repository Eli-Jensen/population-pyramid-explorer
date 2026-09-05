// Per-year series derived from an entity shard (151 rows) for the age-shares chart, the median-age
// sparkline and the 10-year change callout. Pure; uses the same math twins as the Python pipeline.

import { N_BINS, N_DIMS, YEAR_MIN, type EntityShard } from './types.ts';
import { medianAge } from './math/features.ts';
import { sharesAt } from './data.ts';

export interface EntitySeries {
  years: Int16Array; // 1950 … 2100
  u15: Float32Array; // share aged 0–14 (0..1)
  wa: Float32Array; // 15–64
  o65: Float32Array; // 65+
  median: Float32Array; // median age in years
  totals: Float32Array; // thousands (view into the shard)
}

/** Age-share + median-age series for every year of an entity shard. */
export function entitySeries(shard: EntityShard): EntitySeries {
  const n = shard.totals.length;
  const years = new Int16Array(n);
  const u15 = new Float32Array(n);
  const wa = new Float32Array(n);
  const o65 = new Float32Array(n);
  const median = new Float32Array(n);
  const s42 = new Float32Array(N_DIMS);
  const a21 = new Float64Array(N_BINS);
  for (let r = 0; r < n; r++) {
    years[r] = YEAR_MIN + r;
    sharesAt(shard.u16, r * N_DIMS, s42);
    let a = 0;
    let b = 0;
    let c = 0;
    for (let k = 0; k < N_BINS; k++) {
      const v = s42[k] + s42[N_BINS + k];
      a21[k] = v;
      if (k < 3) a += v;
      else if (k < 13) b += v;
      else c += v;
    }
    u15[r] = a;
    wa[r] = b;
    o65[r] = c;
    median[r] = medianAge(a21);
  }
  return { years, u15, wa, o65, median, totals: shard.totals };
}

export interface Change {
  from: number; // year compared against
  to: number;
  fraction: number; // (to − from) / from
}

/**
 * Ten-year change of the total ending at `year` (`year−10 → year`); for the first decade of the corpus,
 * where no earlier year exists, the change is looked forward (`year → year+10`). Null if impossible.
 */
export function tenYearChange(totals: ArrayLike<number>, year: number, span = 10, yearMin = YEAR_MIN): Change | null {
  const n = totals.length;
  const yearMax = yearMin + n - 1;
  const back = year - span;
  const fwd = year + span;
  if (back >= yearMin) {
    const a = totals[back - yearMin];
    const b = totals[year - yearMin];
    return a > 0 ? { from: back, to: year, fraction: (b - a) / a } : null;
  }
  if (fwd <= yearMax) {
    const a = totals[year - yearMin];
    const b = totals[fwd - yearMin];
    return a > 0 ? { from: year, to: fwd, fraction: (b - a) / a } : null;
  }
  return null;
}
