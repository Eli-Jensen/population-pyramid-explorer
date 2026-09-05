import { describe, expect, test } from 'vitest';
import { KERNEL, smooth21, smoothVector } from './smooth.ts';

describe('5-tap smoothing with nearest padding', () => {
  test('kernel matches meta.kernel and sums to ≈ 1', () => {
    expect(KERNEL).toEqual([0.054, 0.242, 0.399, 0.242, 0.054]);
    expect(KERNEL.reduce((a, b) => a + b, 0)).toBeCloseTo(0.991, 12);
  });

  test('a constant profile stays constant × kernel sum (edge padding replicates the edge)', () => {
    const out = smooth21(new Float64Array(21).fill(2));
    for (const x of out) expect(x).toBeCloseTo(2 * 0.991, 12);
  });

  test.each<[number[], number[]]>([
    // impulse in the middle spreads as the kernel
    [[0, 0, 1, 0, 0], [0.054, 0.242, 0.399, 0.242, 0.054]],
    // impulse at the left edge: pad copies a[0] = 1 twice → out[0] = .054+.242+.399, out[1] = .054+.242, …
    [[1, 0, 0, 0, 0], [0.695, 0.296, 0.054, 0, 0]],
    // impulse at the right edge mirrors it
    [[0, 0, 0, 0, 1], [0, 0, 0.054, 0.296, 0.695]],
  ])('smooth21(%j) = %j', (input, want) => {
    const out = smooth21(input);
    want.forEach((w, i) => expect(out[i]).toBeCloseTo(w, 12));
  });

  test('matches an explicit np.pad(mode="edge") evaluation on a random profile', () => {
    const a = Array.from({ length: 21 }, (_, i) => Math.sin(i * 0.7) ** 2 + 0.1);
    const padded = [a[0], a[0], ...a, a[20], a[20]];
    const want = a.map((_, i) => KERNEL.reduce((acc, k, j) => acc + k * padded[i + j], 0));
    const out = smooth21(a);
    want.forEach((w, i) => expect(out[i]).toBeCloseTo(w, 14));
  });

  test('smoothVector smooths each sex separately and never mixes them', () => {
    const v = new Float64Array(42);
    v[20] = 1; // male 100+
    v[21] = 1; // female 0-4
    const out = smoothVector(v);
    expect(out[20]).toBeCloseTo(0.695, 12);
    expect(out[19]).toBeCloseTo(0.296, 12);
    expect(out[21]).toBeCloseTo(0.695, 12);
    expect(out[22]).toBeCloseTo(0.296, 12);
    expect(out[0]).toBe(0);
    expect(out[41]).toBe(0);
    expect(smoothVector(new Float64Array(21).fill(1))[10]).toBeCloseTo(0.991, 12);
    expect(() => smoothVector(new Float64Array(7))).toThrow(/expected 21 or 42/);
    expect(() => smooth21([1, 2], [0.5, 0.5])).toThrow(/odd/);
  });
});
