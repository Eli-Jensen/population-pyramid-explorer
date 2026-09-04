"""Share-vector quantisation (CONTRACT §3, A2).

Each corpus row is 42 shares of total population summing to 1. The web ships them as uint16 with
largest-remainder rounding so that every row sums to exactly ``U16_TOTAL`` (65535); the browser
dequantises with ``u / 65535`` and the row sums to 1 again without any renormalisation.
"""
from __future__ import annotations

import numpy as np

U16_TOTAL = 65535


def shares_to_u16(s42: np.ndarray) -> np.ndarray:
    """Quantise share rows to uint16 with largest-remainder rounding.

    Rows are renormalised to sum to 1 first (guards float drift), scaled by 65535, floored, and the
    per-row shortfall is handed out one unit at a time to the bins with the largest fractional parts,
    so ``out.sum(1) == 65535`` for every row.
    """
    s = np.asarray(s42, dtype=np.float64)
    if s.ndim != 2:
        raise ValueError(f"expected [n, k] shares, got shape {s.shape}")
    if not np.isfinite(s).all() or (s < 0).any():
        raise ValueError("shares must be finite and non-negative")
    s = s / s.sum(axis=1, keepdims=True)
    scaled = s * U16_TOTAL
    base = np.floor(scaled)
    frac = scaled - base
    short = (U16_TOTAL - base.sum(axis=1)).astype(np.int64)  # units still to hand out per row
    # rank fractional parts descending (stable, so ties resolve by lower bin index)
    order = np.argsort(-frac, axis=1, kind="stable")
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.arange(s.shape[1])[None, :].repeat(s.shape[0], 0), axis=1)
    out = (base + (rank < short[:, None])).astype(np.uint16)
    if not np.all(out.sum(axis=1, dtype=np.int64) == U16_TOTAL):
        raise AssertionError("largest-remainder rounding failed to reach 65535 on some row")
    return out


def u16_to_shares(u: np.ndarray) -> np.ndarray:
    """Dequantise exactly as the browser does: ``float32(u) / 65535``."""
    return (np.asarray(u, dtype=np.float32) / np.float32(U16_TOTAL)).astype(np.float32)
