"""delta.py — modular-delta, byte-transposed, gzip-9 blob: byte-exact round trips."""
from __future__ import annotations

import gzip

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.delta import (
    decode_blob,
    encode_blob,
    layout_sizes,
    modular_deltas,
)
from pyramid_explorer.paths import DATA_PROCESSED
from pyramid_explorer.quantise import shares_to_u16


def _synthetic(n_entities: int = 4, n_years: int = 151, seed: int = 0) -> np.ndarray:
    """Random u16 rows that deliberately contain 0, 65535 and wrap-around deltas."""
    rng = np.random.default_rng(seed)
    u = rng.integers(0, 65536, size=(n_entities * n_years, 42), dtype=np.uint16)
    u[0, :] = 0
    u[1, :] = 65535          # +65535 delta then wraps
    u[2, :] = 0              # −65535 delta (modular 1)
    u[n_years, 0] = 65535    # first row of entity 2 stores its absolute value
    u[n_years + 1, 0] = 0
    return u


def test_round_trip_synthetic_with_extremes():
    u = _synthetic()
    blob = encode_blob(u)
    assert blob[:2] == b"\x1f\x8b"  # gzip magic, no custom header
    back = decode_blob(blob, u.shape[0])
    assert back.dtype == np.uint16 and np.array_equal(back, u)


def test_deltas_are_modular_and_reset_per_entity():
    u = _synthetic(n_entities=2, n_years=3)
    d = modular_deltas(u, n_years=3)
    assert d[0].tolist() == [0] * 42
    assert d[1].tolist() == [65535] * 42                    # 65535 − 0
    assert d[2].tolist() == [1] * 42                        # (0 − 65535) & 0xFFFF
    assert d[3, 0] == 65535 and d[3, 0] == u[3, 0]          # entity 2 row 0 is absolute (prev = 0)
    assert d[4, 0] == 1


def test_byte_transposed_layout():
    u = np.array([[0x0102, 0x0304]] * 2, dtype=np.uint16)  # 1 entity, 2 years, 2 dims
    raw = gzip.decompress(encode_blob(u, n_years=2))
    # deltas: row0 = [0x0102, 0x0304], row1 = [0, 0]; low bytes first then high bytes
    assert raw == bytes([0x02, 0x04, 0, 0, 0x01, 0x03, 0, 0])


def test_deterministic_bytes():
    u = _synthetic()
    assert encode_blob(u) == encode_blob(u)


def test_decode_validates_length():
    u = _synthetic(n_entities=2)
    with pytest.raises(ValueError):
        decode_blob(encode_blob(u), u.shape[0] + 151)


def test_rejects_ragged_rows():
    with pytest.raises(ValueError):
        encode_blob(np.zeros((150, 42), dtype=np.uint16))


def test_layout_sizes_keys_and_ordering():
    u = shares_to_u16(_smooth_shares())
    sizes = layout_sizes(u)
    assert set(sizes) == {"raw_gz", "delta_gz", "zigzag_gz", "delta_transposed_gz"}
    assert all(v > 0 for v in sizes.values())
    assert sizes["delta_transposed_gz"] == len(encode_blob(u))
    assert sizes["delta_gz"] < sizes["raw_gz"]  # smooth trajectories compress better as deltas


def _smooth_shares(n_entities: int = 6, n_years: int = 151) -> np.ndarray:
    rng = np.random.default_rng(1)
    t = np.linspace(0, 1, n_years)[:, None]
    rows = []
    for _ in range(n_entities):
        a = rng.gamma(2, size=42)
        b = rng.gamma(2, size=42)
        s = a * (1 - t) + b * t
        rows.append(s / s.sum(1, keepdims=True))
    return np.concatenate(rows)


@pytest.mark.slow
def test_full_corpus_round_trip_and_sizes():
    path = DATA_PROCESSED / "corpus_s42.npy"
    if not path.exists():
        pytest.skip("provisional corpus absent")
    u = shares_to_u16(np.load(path))
    keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
    assert len(keys) == u.shape[0]
    blob = encode_blob(u)
    assert np.array_equal(decode_blob(blob, u.shape[0]), u)
    sizes = layout_sizes(u)
    print("layout_sizes:", sizes)
    assert sizes["delta_transposed_gz"] <= 2_200_000
