import { describe, expect, it } from 'vitest';
import { N_DIMS, N_YEARS, U16_TOTAL, YEAR_MIN } from './types.ts';
import { parseEntityShard } from './data.ts';
import { entitySeries, tenYearChange } from './series.ts';

/** Synthetic entity shard: year r puts everything in bin (r % 21) of the male side. */
function shard(totalFor: (r: number) => number) {
  const buf = new ArrayBuffer(N_YEARS * (N_DIMS * 2 + 4));
  const u16 = new Uint16Array(buf, 0, N_YEARS * N_DIMS);
  const totals = new Float32Array(buf, N_YEARS * N_DIMS * 2, N_YEARS);
  for (let r = 0; r < N_YEARS; r++) {
    u16[r * N_DIMS + (r % 21)] = U16_TOTAL;
    totals[r] = totalFor(r);
  }
  return parseEntityShard(buf, 'X');
}

describe('entitySeries', () => {
  const s = entitySeries(shard((r) => 100 + r));
  it('has one point per year', () => {
    expect(s.years.length).toBe(N_YEARS);
    expect(s.years[0]).toBe(YEAR_MIN);
    expect(s.years[N_YEARS - 1]).toBe(2100);
  });
  it('age shares follow the single occupied bin', () => {
    // r=0 → bin 0 (0–4) → u15 = 1; r=5 → bin 5 (25–29) → wa = 1; r=15 → bin 15 (75–79) → o65 = 1
    expect(s.u15[0]).toBeCloseTo(1, 6);
    expect(s.wa[5]).toBeCloseTo(1, 6);
    expect(s.o65[15]).toBeCloseTo(1, 6);
    expect(s.u15[5] + s.o65[5]).toBeCloseTo(0, 6);
  });
  it('median age lands mid-bin of the occupied bin', () => {
    expect(s.median[0]).toBeCloseTo(2.5, 5);
    expect(s.median[7]).toBeCloseTo(37.5, 5);
  });
  it('totals are the shard totals', () => {
    expect(s.totals[10]).toBe(110);
  });
});

describe('tenYearChange', () => {
  const totals = Float32Array.from({ length: N_YEARS }, (_, r) => 100 * 1.01 ** r);
  it('looks back ten years when possible', () => {
    const c = tenYearChange(totals, 2000)!;
    expect(c.from).toBe(1990);
    expect(c.to).toBe(2000);
    expect(c.fraction).toBeCloseTo(1.01 ** 10 - 1, 5);
  });
  it('looks forward in the first decade', () => {
    const c = tenYearChange(totals, 1955)!;
    expect(c).toMatchObject({ from: 1955, to: 1965 });
    expect(c.fraction).toBeCloseTo(1.01 ** 10 - 1, 5);
  });
  it('null on a zero base or when neither direction fits', () => {
    expect(tenYearChange(new Float32Array(N_YEARS), 2000)).toBeNull();
    expect(tenYearChange(new Float32Array(5), 1952, 10)).toBeNull();
  });
});
