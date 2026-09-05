import { describe, expect, test } from 'vitest';
import { axisFor, axisTicks, barLength, clampBar, fitAxis, maxBinPct, pairAxis, widen } from './scale.ts';

describe('axis fit (PLAN §2)', () => {
  test.each<[number, 10 | 12 | 14 | 17]>([
    [0, 10],
    [9.8, 10],
    [10, 10], // boundary: share*100 <= p covers
    [10.01, 12],
    [12, 12],
    [12.5, 14],
    [14, 14],
    [14.5, 17],
    [17, 17],
    [22, 17], // beyond the largest choice → 17 (the caller clips)
  ])('fitAxis(%f) = %i', (maxPct, want) => {
    expect(fitAxis(maxPct)).toBe(want);
  });

  test('maxBinPct is the largest single bin in percent', () => {
    const s = new Float32Array(42).fill(0.01);
    s[7] = 0.123;
    expect(maxBinPct(s)).toBeCloseTo(12.3, 5);
    expect(maxBinPct([])).toBe(0);
  });

  test.each([
    ['fit', 10, [9.5], 10, false],
    ['fit', 10, [11], 12, false], // drawn partner wider than the entity's fit → widen, not clip
    ['fit', 12, [9], 12, false], // never narrower than the entity's own fit
    ['fit', 17, [18.2], 17, true], // beyond 17 → clipped even in fit
    ['pin10', 12, [9.5], 10, false],
    ['pin10', 12, [11.2], 10, true],
    ['pin10', 17, [], 10, false],
    ['never', 10, [16.9], 17, false],
    ['never', 10, [17.5], 17, true],
  ] as const)('axisFor(%s, fit %i, drawn %j) → %i clips=%s', (mode, fit, drawn, axisPct, clips) => {
    expect(axisFor(mode, fit, ...drawn)).toEqual({ axisPct, clips });
  });

  test('pairAxis widens to the max of the pair and flags it', () => {
    expect(pairAxis(10, 10)).toEqual({ axisPct: 10, widened: false });
    expect(pairAxis(10, 17)).toEqual({ axisPct: 17, widened: true });
    expect(pairAxis(14, 12)).toEqual({ axisPct: 14, widened: false });
    expect(widen(12, 10)).toBe(12);
  });

  test('clampBar and barLength', () => {
    expect(clampBar(14.5, 10)).toEqual({ pct: 10, overflow: true });
    expect(clampBar(4.2, 10)).toEqual({ pct: 4.2, overflow: false });
    expect(barLength(5, 10, 200)).toBe(100);
    expect(barLength(15, 10, 200)).toBe(200); // clamped
    expect(barLength(-1, 10, 200)).toBe(0);
    expect(barLength(5, 0, 200)).toBe(0);
  });

  test.each([
    [10, [0, 2, 4, 6, 8, 10]],
    [12, [0, 2, 4, 6, 8, 10, 12]],
    [14, [0, 4, 8, 12]],
    [17, [0, 4, 8, 12, 16]],
  ] as const)('axisTicks(%i)', (axis, want) => {
    expect(axisTicks(axis)).toEqual([...want]);
  });
});
