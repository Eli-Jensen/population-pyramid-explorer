"""Canonical renderer: deterministic bytes, row alignment, style-hash stability, hand-checked pixels."""
from __future__ import annotations

import numpy as np
import pytest

from pyramid_explorer import render as R

# A style change must be deliberate: update this constant together with evals/image_embeddings.md §4.
STYLE_HASH = "a7f59032ba03c1b86c52a31f0505a9cb365216b28ac3e4124c0b956470d0a0fb"


def _vec(male: dict[int, float] | None = None, female: dict[int, float] | None = None) -> np.ndarray:
    v = np.zeros(42)
    for k, s in (male or {}).items():
        v[k] = s
    for k, s in (female or {}).items():
        v[21 + k] = s
    return v


@pytest.fixture(scope="module")
def sample() -> np.ndarray:
    rng = np.random.default_rng(0)
    v = rng.random(42) * np.linspace(1, 0.05, 21).repeat(2).reshape(21, 2).T.reshape(-1)
    return v / v.sum()


def test_shapes_dtype_and_background(sample):
    a, b = R.render_canon2(sample), R.render_canon1(sample)
    assert a.shape == (336, 336, 3) and a.dtype == np.uint8
    assert b.shape == (294, 294, 3) and b.dtype == np.uint8
    assert tuple(a[0, 0]) == R.BG and tuple(a[-1, 0]) == R.BG          # corners are always background
    assert R.render_canon2(sample, 210).shape == (210, 210, 3)


def test_deterministic_bytes(sample):
    assert R.render_canon2(sample).tobytes() == R.render_canon2(sample.copy()).tobytes()
    assert R.render_canon1(sample).tobytes() == R.render_canon1(sample.copy()).tobytes()


def test_hand_checked_pixels():
    # male 0–4 = 8.5 % = half the 17 % axis → 84 of the 168 px half-width; female 0–4 = 4.25 % → 42 px.
    img = R.render_canon2(_vec({0: 0.085}, {0: 0.0425}))
    bottom = 335
    assert tuple(img[bottom, 84]) == R.MALE and tuple(img[bottom, 83]) == R.BG
    assert tuple(img[bottom, 167]) == R.MALE and tuple(img[bottom, 168]) == R.FEMALE
    assert tuple(img[bottom, 209]) == R.FEMALE and tuple(img[bottom, 210]) == R.BG
    assert tuple(img[319, 100]) == R.BG and tuple(img[320, 100]) == R.MALE      # bin 0 occupies rows 320..335


def test_row_alignment_and_top_is_100_plus():
    img = R.render_canon2(_vec({20: 0.05, 10: 0.05}))
    filled = (img != 255).any(axis=(1, 2))
    rows = np.flatnonzero(filled)
    assert rows.min() == 0 and rows.max() == 175
    assert set(rows) == set(range(0, 16)) | set(range(160, 176))         # bin 20 → row block 0, bin 10 → block 10
    for edge in (16, 160, 176):
        assert filled[edge - 1] != filled[edge]                           # crisp 16-px row boundaries


def test_canon1_is_symmetric_grey():
    img = R.render_canon1(_vec({3: 0.06}, {3: 0.02}))                    # total 8 % → 4 % per side
    assert np.array_equal(img, img[:, ::-1])
    colours = {tuple(c) for c in img.reshape(-1, 3)}
    assert colours == {R.BG, R.TOTAL}
    half = 147
    assert tuple(img[245, half - 35]) == R.TOTAL and tuple(img[245, half - 36]) == R.BG   # bin 3 → rows 238..251; 0.04/0.17·147 ≈ 34.6 → 35


def test_style_hash_stable_and_pinned():
    assert R.style_hash() == R.style_hash()
    assert len(R.style_hash()) == 64
    assert R.style_hash() == STYLE_HASH


def test_render_style_variants(sample):
    base = R.render_style(sample, kind="canon2", height=336)
    assert np.array_equal(base, R.render_canon2(sample))
    grey = R.render_style(sample, palette=((60, 60, 60), (160, 160, 160)))
    assert (grey != 255).any(axis=2).sum() == (base != 255).any(axis=2).sum()   # same footprint, new colours
    gap = R.render_style(sample, gap=2)
    assert (gap != 255).any(axis=2).sum() < (base != 255).any(axis=2).sum()
    assert not (gap[14:16] != 255).any()                                        # 2 px cut off every row
    assert R.render_style(sample, height=336, width=448).shape == (336, 448, 3)
    assert R.render_style(sample, height=304).shape == (304, 304, 3)


def test_render_corpus_memmap_and_meta(tmp_path, sample):
    X = np.stack([sample, sample[::-1] / sample[::-1].sum(), sample])
    out = tmp_path / "canon2_42.npy"
    arr = R.render_corpus(X, "canon2", 42, out)
    assert arr.shape == (3, 42, 42, 3) and arr.dtype == np.uint8
    assert np.array_equal(arr[0], R.render_canon2(sample, 42)) and np.array_equal(arr[0], arr[2])
    meta = __import__("json").loads(out.with_suffix(".meta.json").read_text())
    assert meta["style_hash"] == R.style_hash() and meta["n"] == 3 and meta["size"] == 42
    with pytest.raises(ValueError):
        R.render_corpus(X, "canon2", 40, tmp_path / "bad.npy")
