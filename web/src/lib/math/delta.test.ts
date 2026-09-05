import { describe, expect, test } from 'vitest';
import { decodeBlob, encodeBlobRaw, modularCumsumInPlace, modularDeltas, transposeBytes, untransposeBytes } from './delta.ts';

/** Twin of tests/test_delta.py `_synthetic`: rows that contain 0, 65535 and wrap-around deltas. */
function synthetic(nEntities = 4, nYears = 151, nDims = 42, seed = 12345): Uint16Array {
  let s = seed >>> 0;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) >>> 16) & 0xffff; // LCG, 0..65535
  const u = new Uint16Array(nEntities * nYears * nDims);
  for (let i = 0; i < u.length; i++) u[i] = rnd();
  u.fill(0, 0, nDims); // row 0: all zeros
  u.fill(65535, nDims, 2 * nDims); // row 1: +65535 delta then wraps
  u.fill(0, 2 * nDims, 3 * nDims); // row 2: −65535 delta (modular 1)
  u[nYears * nDims] = 65535; // first row of entity 2 stores its absolute value
  u[(nYears + 1) * nDims] = 0;
  return u;
}

describe('delta codec', () => {
  test('round-trips a synthetic set with 0, 65535 and wrap-around deltas', () => {
    const u = synthetic();
    const raw = encodeBlobRaw(u);
    expect(raw.length).toBe(u.length * 2);
    const back = decodeBlob(raw, u.length / 42);
    expect(back).toEqual(u);
  });

  test.each([
    [1, 3],
    [2, 3],
    [3, 151],
    [7, 5],
  ])('round-trips %i entities × %i years', (nEntities, nYears) => {
    const u = synthetic(nEntities, nYears, 42, nEntities * 31 + nYears);
    expect(decodeBlob(encodeBlobRaw(u, nYears), nEntities * nYears, nYears)).toEqual(u);
  });

  test('deltas are modular and reset per entity (tests/test_delta.py twin)', () => {
    const u = synthetic(2, 3);
    const d = modularDeltas(u, 3);
    expect(Array.from(d.subarray(0, 42))).toEqual(new Array(42).fill(0));
    expect(Array.from(d.subarray(42, 84))).toEqual(new Array(42).fill(65535)); // 65535 − 0
    expect(Array.from(d.subarray(84, 126))).toEqual(new Array(42).fill(1)); // (0 − 65535) & 0xFFFF
    expect(d[3 * 42]).toBe(65535); // entity 2 row 0 is absolute (prev = 0)
    expect(d[3 * 42]).toBe(u[3 * 42]);
    expect(d[4 * 42]).toBe(1);
  });

  test('byte-transposed layout: low bytes then high bytes (Python test twin)', () => {
    // 1 entity, 2 years, 2 dims: rows [0x0102, 0x0304] × 2 → deltas row0 = [0x0102, 0x0304], row1 = [0, 0]
    const u = new Uint16Array([0x0102, 0x0304, 0x0102, 0x0304]);
    const raw = encodeBlobRaw(u, 2, 2);
    expect(Array.from(raw)).toEqual([0x02, 0x04, 0, 0, 0x01, 0x03, 0, 0]);
    expect(decodeBlob(raw, 2, 2, 2)).toEqual(u);
  });

  test('untranspose/transpose are inverses and reject bad lengths', () => {
    const u = new Uint16Array([0, 1, 255, 256, 65535, 0x1234]);
    expect(untransposeBytes(transposeBytes(u), u.length)).toEqual(u);
    expect(() => untransposeBytes(new Uint8Array(5), 3)).toThrow(/expected 6 bytes/);
  });

  test('modular cumsum wraps in Uint16 without a signed type', () => {
    const d = new Uint16Array([65535, 1, 65535, 2]); // 1 entity, 2 years, 2 dims
    modularCumsumInPlace(d, 2, 2);
    expect(Array.from(d)).toEqual([65535, 1, 65534, 3]); // (65535 + 65535) & 0xFFFF = 65534
  });

  test('decodeBlob validates the inflated length and the entity multiple', () => {
    expect(() => decodeBlob(new Uint8Array(83), 1)).toThrow(/inflated length 83 != 84/);
    expect(() => decodeBlob(new Uint8Array(84 * 2), 2, 3)).toThrow(/not a multiple/);
  });
});
