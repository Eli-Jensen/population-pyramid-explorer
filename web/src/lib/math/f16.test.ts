import { describe, expect, test } from 'vitest';
import { decodeF16, f16ToF32, f32ToF16 } from './f16.ts';

describe('float16 decode', () => {
  test.each<[number, number]>([
    [0x0000, 0],
    [0x3c00, 1],
    [0xbc00, -1],
    [0x4000, 2],
    [0xc000, -2],
    [0x3555, 0.333251953125], // nearest half to 1/3
    [0x3e00, 1.5],
    [0x7bff, 65504], // max finite
    [0xfbff, -65504],
    [0x0400, 6.103515625e-5], // smallest normal 2^-14
    [0x03ff, 6.097555160522461e-5], // largest subnormal 1023 × 2^-24
    [0x0001, 5.960464477539063e-8], // smallest subnormal 2^-24
    [0x8001, -5.960464477539063e-8],
    [0x0200, 3.0517578125e-5], // subnormal 2^-15
    [0x4248, 3.140625], // pi rounded to half
    [0x5640, 100],
    [0x2e66, 0.0999755859375], // ≈ 0.1 (exact half value)
  ])('0x%s decodes to %f', (bits, want) => {
    expect(f16ToF32(bits)).toBeCloseTo(want, 12);
  });

  test('negative zero keeps its sign', () => {
    expect(Object.is(f16ToF32(0x8000), -0)).toBe(true);
    expect(Object.is(f16ToF32(0x0000), 0)).toBe(true);
  });

  test('infinities and NaN', () => {
    expect(f16ToF32(0x7c00)).toBe(Infinity);
    expect(f16ToF32(0xfc00)).toBe(-Infinity);
    expect(Number.isNaN(f16ToF32(0x7e00))).toBe(true);
    expect(Number.isNaN(f16ToF32(0x7c01))).toBe(true);
  });

  test('every finite pattern round-trips through the encoder', () => {
    for (let h = 0; h < 0x10000; h++) {
      if (((h >> 10) & 0x1f) === 31) continue; // Inf/NaN handled separately
      const x = f16ToF32(h);
      const back = f32ToF16(x);
      if (h === 0x8000) expect(back).toBe(0x8000);
      else expect(back).toBe(h);
    }
  });

  test('encoder rounds to nearest even and agrees with Math.f16round when available', () => {
    expect(f16ToF32(f32ToF16(1 / 3))).toBeCloseTo(0.333251953125, 12);
    expect(f32ToF16(70000)).toBe(0x7c00); // overflow → +Inf
    expect(f32ToF16(1e-9)).toBe(0x0000); // underflow → +0
    const f16round = (Math as unknown as { f16round?: (x: number) => number }).f16round;
    if (f16round) {
      let s = 7;
      for (let i = 0; i < 2000; i++) {
        s = (s * 1103515245 + 12345) >>> 0;
        const x = ((s / 2 ** 32) * 2 - 1) * 10 ** ((s % 9) - 4);
        expect(f16ToF32(f32ToF16(x))).toBe(f16round(x));
      }
    }
  });

  test('decodeF16 reads little-endian pairs at any offset', () => {
    const bytes = new Uint8Array([0xff, 0x00, 0x3c, 0x00, 0xc0, 0xff, 0x7b]); // offset 1: 0x3c00, 0xc000, 0x7bff
    const out = decodeF16(bytes, 1, 3);
    expect(Array.from(out)).toEqual([1, -2, 65504]);
    expect(out).toBeInstanceOf(Float32Array);
    expect(decodeF16(new Uint8Array([0x00, 0x3c, 0x00, 0x40]).buffer)).toEqual(new Float32Array([1, 2]));
    expect(() => decodeF16(bytes, 0, 10)).toThrow(/available/);
  });
});
