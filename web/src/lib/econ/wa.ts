// Working-age share (15–64, both sexes) per year of an entity shard and its peak year — the "dividend window" line of
// the then-what disclosure (PLAN §7 J10). Pure over the u16 rows; no DOM.

import { N_BINS, N_DIMS, U16_TOTAL, YEAR_MIN, type EntityShard } from '../types.ts';

/** Bins 15–19 … 60–64 = indices 3..12 of each sex. */
export const WA_LO = 3;
export const WA_HI = 12;

/** Working-age share of one 42-vector row (fraction of the total). */
export function waShareRow(u16: Uint16Array, offset: number): number {
  let s = 0;
  for (let k = WA_LO; k <= WA_HI; k++) s += u16[offset + k]! + u16[offset + N_BINS + k]!;
  return s / U16_TOTAL;
}

export interface WaPeak {
  year: number;
  share: number;
  /** The share in the focal year, for the caption. */
  shareAt: number;
  /** Whether the peak lies after the last year the caller treats as observed / nowcast. */
  projected: boolean;
}

/** Peak working-age share over the shard (1950–2100) and the share in `year`; `edge` marks projected peaks. */
export function waPeak(shard: EntityShard, year: number, edge: number): WaPeak {
  const nYears = shard.u16.length / N_DIMS;
  let best = -1;
  let bestYear = YEAR_MIN;
  for (let i = 0; i < nYears; i++) {
    const v = waShareRow(shard.u16, i * N_DIMS);
    if (v > best) {
      best = v;
      bestYear = YEAR_MIN + i;
    }
  }
  return { year: bestYear, share: best, shareAt: waShareRow(shard.u16, (year - YEAR_MIN) * N_DIMS), projected: bestYear > edge };
}
