"""Corpus blob codec (CONTRACT §3/§5, A2): modular Uint16 deltas, byte-transposed, gzip-9.

Layout of ``shares.{sha8}.d16z``: for every entity (``n_years`` consecutive rows, entity-major)
``d[0] = u[0]`` and ``d[r] = (u[r] - u[r-1]) & 0xFFFF``; the ``[n_rows, 42]`` delta matrix is
serialised little-endian, then byte-transposed (all low bytes, then all high bytes) and gzipped at
level 9. There is no custom header: the file starts with gzip's own magic ``1f 8b``. Decoding is a
modular running sum in uint16, so no signed type is needed and 0/65535 round-trip exactly.
"""
from __future__ import annotations

import gzip

import numpy as np

from pyramid_explorer.paths import N_YEARS

_LE_U16 = np.dtype("<u2")


def _as_entity_major(u16: np.ndarray, n_years: int) -> np.ndarray:
    u = np.ascontiguousarray(np.asarray(u16, dtype=np.uint16))
    if u.ndim != 2 or u.shape[0] % n_years:
        raise ValueError(f"u16 must be [n_rows, k] with n_rows % {n_years} == 0, got {u.shape}")
    return u.reshape(-1, n_years, u.shape[1])


def modular_deltas(u16: np.ndarray, n_years: int = N_YEARS) -> np.ndarray:
    """``[n_rows, k]`` uint16 deltas within each entity, prev = 0 on each entity's first row."""
    u = _as_entity_major(u16, n_years).astype(np.int32)
    d = u.copy()
    d[:, 1:] = (u[:, 1:] - u[:, :-1]) & 0xFFFF
    return d.reshape(-1, u.shape[2]).astype(np.uint16)


def _gz(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)  # mtime=0 keeps the bytes deterministic


def _transpose_bytes(a: np.ndarray) -> bytes:
    b = np.ascontiguousarray(a, dtype=_LE_U16).view(np.uint8).reshape(-1, 2)
    return b[:, 0].tobytes() + b[:, 1].tobytes()


def encode_blob(u16: np.ndarray, n_years: int = N_YEARS) -> bytes:
    """Encode ``[n_rows, k]`` uint16 rows (entity-major) as the ``.d16z`` gzip stream."""
    return _gz(_transpose_bytes(modular_deltas(u16, n_years)))


def decode_blob(blob: bytes, n_rows: int, n_years: int = N_YEARS, n_dims: int = 42) -> np.ndarray:
    """Exact inverse of :func:`encode_blob`; validates the inflated length ``== n_rows * n_dims * 2``."""
    raw = gzip.decompress(blob)
    n = n_rows * n_dims
    if len(raw) != 2 * n:
        raise ValueError(f"inflated length {len(raw)} != {2 * n} (n_rows={n_rows}, n_dims={n_dims})")
    lo = np.frombuffer(raw, dtype=np.uint8, count=n)
    hi = np.frombuffer(raw, dtype=np.uint8, count=n, offset=n)
    d = (lo.astype(np.uint16) | (hi.astype(np.uint16) << 8)).reshape(-1, n_years, n_dims)
    return np.cumsum(d, axis=1, dtype=np.uint16).reshape(n_rows, n_dims)  # modular running sum


def layout_sizes(u16: np.ndarray, n_years: int = N_YEARS) -> dict[str, int]:
    """Compressed byte counts of the four candidate blob layouts (for the build report).

    ``raw_gz`` gzip of the plain LE uint16 rows · ``delta_gz`` modular deltas, not transposed ·
    ``zigzag_gz`` zigzag-mapped signed deltas, not transposed · ``delta_transposed_gz`` the
    adopted layout (``encode_blob``).
    """
    u = np.ascontiguousarray(np.asarray(u16, dtype=np.uint16))
    d = modular_deltas(u, n_years)
    signed = d.astype(np.int32)
    signed[signed > 0x7FFF] -= 0x10000  # back to the signed delta
    zigzag = ((signed << 1) ^ (signed >> 31)).astype(np.uint16)
    return {
        "raw_gz": len(_gz(u.astype(_LE_U16).tobytes())),
        "delta_gz": len(_gz(d.astype(_LE_U16).tobytes())),
        "zigzag_gz": len(_gz(zigzag.astype(_LE_U16).tobytes())),
        "delta_transposed_gz": len(encode_blob(u, n_years)),
    }
