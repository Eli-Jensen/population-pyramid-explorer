/**
 * Corpus blob codec — TS twin of `src/pyramid_explorer/delta.py` (CONTRACT §3/§5, PLAN §3.4).
 *
 * `shares.{sha8}.d16z` = gzip-9 of the BYTE-TRANSPOSED modular deltas: for every entity
 * (`nYears` consecutive rows, entity-major) `d[0] = u[0]` and `d[r] = (u[r] − u[r−1]) & 0xFFFF`;
 * the `[nRows, 42]` Uint16 delta matrix is written little-endian, then all low bytes precede all
 * high bytes. No header — the file starts with gzip's own `1f 8b`. Decoding is a modular running
 * sum in a `Uint16Array` (assignment wraps mod 2^16), so 0 and 65535 round-trip exactly and no
 * signed type is needed. Inflation (gzip) is the caller's job (`lib/data.ts`); this module is pure.
 */

import { N_DIMS, N_YEARS } from '../types.ts';

/** Inverse of the byte transpose: `bytes` = n low bytes then n high bytes → n Uint16 values. */
export function untransposeBytes(bytes: Uint8Array, n: number): Uint16Array {
  if (bytes.length !== 2 * n) {
    throw new Error(`untransposeBytes: expected ${2 * n} bytes for ${n} values, got ${bytes.length}`);
  }
  const out = new Uint16Array(n);
  for (let i = 0; i < n; i++) out[i] = bytes[i] | (bytes[n + i] << 8);
  return out;
}

/** Byte transpose (encoder side): n Uint16 → n low bytes followed by n high bytes. */
export function transposeBytes(u: Uint16Array): Uint8Array {
  const n = u.length;
  const out = new Uint8Array(2 * n);
  for (let i = 0; i < n; i++) {
    out[i] = u[i] & 0xff;
    out[n + i] = u[i] >>> 8;
  }
  return out;
}

/**
 * Modular running sum within each entity, in place. `d` is `[nRows, nDims]` entity-major with
 * `nRows % nYears === 0`; row 0 of every entity is already absolute (prev = 0).
 */
export function modularCumsumInPlace(d: Uint16Array, nYears: number, nDims: number): Uint16Array {
  const nRows = d.length / nDims;
  if (!Number.isInteger(nRows) || nRows % nYears !== 0) {
    throw new Error(`modularCumsumInPlace: ${d.length} values is not [k×${nYears}, ${nDims}]`);
  }
  for (let r = 0; r < nRows; r++) {
    if (r % nYears === 0) continue; // entity's first row stores the absolute value
    const cur = r * nDims;
    const prev = cur - nDims;
    for (let k = 0; k < nDims; k++) d[cur + k] = d[cur + k] + d[prev + k]; // Uint16Array wraps mod 65536
  }
  return d;
}

/** Encoder twin of `delta.modular_deltas`: `(u[r] − u[r−1]) & 0xFFFF` within an entity, prev = 0 per entity. */
export function modularDeltas(u16: Uint16Array, nYears = N_YEARS, nDims = N_DIMS): Uint16Array {
  const nRows = u16.length / nDims;
  if (!Number.isInteger(nRows) || nRows % nYears !== 0) {
    throw new Error(`modularDeltas: ${u16.length} values is not [k×${nYears}, ${nDims}]`);
  }
  const d = new Uint16Array(u16.length);
  for (let r = 0; r < nRows; r++) {
    const cur = r * nDims;
    if (r % nYears === 0) {
      for (let k = 0; k < nDims; k++) d[cur + k] = u16[cur + k];
    } else {
      const prev = cur - nDims;
      for (let k = 0; k < nDims; k++) d[cur + k] = u16[cur + k] - u16[prev + k]; // wraps mod 65536
    }
  }
  return d;
}

/**
 * Decode the INFLATED blob bytes (after gzip) to `[nRows, nDims]` Uint16 shares.
 * Validates `inflated.length === nRows × nDims × 2` first (CONTRACT §3 `decode_blob`).
 */
export function decodeBlob(inflated: Uint8Array, nRows: number, nYears = N_YEARS, nDims = N_DIMS): Uint16Array {
  const n = nRows * nDims;
  if (inflated.length !== 2 * n) {
    throw new Error(`decodeBlob: inflated length ${inflated.length} != ${2 * n} (nRows=${nRows}, nDims=${nDims})`);
  }
  if (nRows % nYears !== 0) throw new Error(`decodeBlob: nRows=${nRows} is not a multiple of nYears=${nYears}`);
  return modularCumsumInPlace(untransposeBytes(inflated, n), nYears, nDims);
}

/** The pre-gzip bytes of `encode_blob` (deltas + byte transpose) — for round-trip tests and fixtures. */
export function encodeBlobRaw(u16: Uint16Array, nYears = N_YEARS, nDims = N_DIMS): Uint8Array {
  return transposeBytes(modularDeltas(u16, nYears, nDims));
}
