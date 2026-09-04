"""quantise.py — largest-remainder rounding to exactly 65535 per row."""
from __future__ import annotations

import numpy as np
import pytest

from pyramid_explorer.paths import DATA_PROCESSED
from pyramid_explorer.quantise import U16_TOTAL, shares_to_u16, u16_to_shares


def _random_shares(n: int, k: int = 42, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    s = rng.gamma(0.7, size=(n, k))
    return s / s.sum(1, keepdims=True)


def test_rows_sum_exactly_and_dtype():
    u = shares_to_u16(_random_shares(500))
    assert u.dtype == np.uint16 and u.shape == (500, 42)
    assert np.all(u.sum(1, dtype=np.int64) == U16_TOTAL)


def test_rounding_error_bounded_by_one_unit():
    s = _random_shares(300)
    u = shares_to_u16(s)
    assert np.abs(u.astype(np.float64) - s * U16_TOTAL).max() < 1.0


def test_degenerate_rows():
    one_hot = np.zeros((3, 42))
    one_hot[0, 0] = 1
    one_hot[1, 41] = 1
    one_hot[2, :] = 1 / 42
    u = shares_to_u16(one_hot)
    assert u[0, 0] == U16_TOTAL and u[1, 41] == U16_TOTAL
    assert np.all(u.sum(1, dtype=np.int64) == U16_TOTAL)
    assert u[2].max() - u[2].min() == 1  # 65535 = 42*1560 + 15 → fifteen bins get the extra unit


def test_ties_resolve_to_lower_bin_first():
    u = shares_to_u16(np.full((1, 42), 1 / 42))
    assert np.all(u[0, :15] == 1561) and np.all(u[0, 15:] == 1560)


def test_renormalises_drifted_rows():
    s = _random_shares(10) * (1 + 1e-9)
    assert np.all(shares_to_u16(s).sum(1, dtype=np.int64) == U16_TOTAL)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        shares_to_u16(np.array([[0.5, -0.5, 1.0]]))
    with pytest.raises(ValueError):
        shares_to_u16(np.ones(42))


def test_u16_to_shares_matches_browser_dequantisation():
    u = shares_to_u16(_random_shares(20))
    f = u16_to_shares(u)
    assert f.dtype == np.float32
    assert np.allclose(f.sum(1), 1, atol=1e-5)
    assert np.array_equal(f, (u.astype(np.float32) / np.float32(65535)).astype(np.float32))


@pytest.mark.slow
def test_full_provisional_corpus_sums():
    path = DATA_PROCESSED / "corpus_s42.npy"
    if not path.exists():
        pytest.skip("provisional corpus absent")
    u = shares_to_u16(np.load(path))
    assert np.all(u.sum(1, dtype=np.int64) == U16_TOTAL)
