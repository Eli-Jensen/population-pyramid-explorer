/**
 * IEEE 754 binary16 (half precision) ↔ binary32 — for `emb/{model}.{sha8}.f16` (CONTRACT §5).
 *
 * Pure bit manipulation (no `Float16Array` dependency, which pre-2025 Safari lacks): sign, a 5-bit
 * exponent (bias 15) and a 10-bit mantissa are re-packed into the float32 layout (bias 127, 23-bit
 * mantissa). Subnormals are normalised, ±Inf and NaN pass through, −0 is preserved.
 */

const u32 = new Uint32Array(1);
const f32 = new Float32Array(u32.buffer);

/** Decode one 16-bit pattern (0..65535) to the exactly-equal float32 (returned as a JS number). */
export function f16ToF32(h: number): number {
  const sign = (h & 0x8000) << 16;
  let exp = (h >> 10) & 0x1f;
  let man = h & 0x3ff;
  if (exp === 0) {
    if (man === 0) {
      u32[0] = sign; // ±0
      return f32[0];
    }
    // subnormal: value = man × 2^-24; normalise so the implicit bit sits at position 10
    let shift = 0;
    while ((man & 0x400) === 0) {
      man <<= 1;
      shift++;
    }
    man &= 0x3ff;
    exp = 1 - shift; // unbiased exponent (e − 15) becomes (1 − shift) − 15
  } else if (exp === 31) {
    u32[0] = sign | 0x7f800000 | (man << 13); // ±Inf (man = 0) or NaN (payload kept)
    return f32[0];
  }
  u32[0] = sign | ((exp + 112) << 23) | (man << 13); // 112 = 127 − 15
  return f32[0];
}

/** Encode a number to the nearest binary16 pattern (round-to-nearest-even). Encoder twin for tests. */
export function f32ToF16(x: number): number {
  f32[0] = x;
  const b = u32[0];
  const sign = (b >>> 16) & 0x8000;
  const exp = (b >>> 23) & 0xff;
  const man = b & 0x7fffff;
  if (exp === 0xff) return sign | 0x7c00 | (man ? 0x200 : 0); // Inf / NaN (quiet)
  const e = exp - 127 + 15; // rebias
  if (e >= 31) return sign | 0x7c00; // overflow → Inf
  if (e <= 0) {
    if (e < -10) return sign; // underflow → ±0
    // subnormal: shift the full 24-bit mantissa right by (1 − e) + 13 with rounding
    const full = man | 0x800000;
    const shift = 14 - e;
    let half = full >>> shift;
    const rem = full & ((1 << shift) - 1);
    const mid = 1 << (shift - 1);
    if (rem > mid || (rem === mid && (half & 1))) half++;
    return sign | half;
  }
  let half = (e << 10) | (man >>> 13);
  const rem = man & 0x1fff;
  if (rem > 0x1000 || (rem === 0x1000 && (half & 1))) half++; // may carry into the exponent — that is correct
  return sign | half;
}

/**
 * Decode `count` little-endian binary16 values starting at `byteOffset` into a new Float32Array.
 * Works on any alignment (reads byte pairs), so it accepts a raw response buffer directly.
 */
export function decodeF16(buf: ArrayBuffer | Uint8Array, byteOffset = 0, count?: number): Float32Array {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  const avail = (bytes.length - byteOffset) >> 1;
  const n = count ?? avail;
  if (n < 0 || n > avail) throw new Error(`decodeF16: ${n} values requested, ${avail} available`);
  const out = new Float32Array(n);
  let p = byteOffset;
  for (let i = 0; i < n; i++, p += 2) out[i] = f16ToF32(bytes[p] | (bytes[p + 1] << 8));
  return out;
}
