"""HF image processors must see the canonical render unchanged (PLAN §4.5), plus the pure-numpy eval helpers.

The ``embed``-marked tests need torch/transformers and the two checkpoints in the local HF cache; they skip
(never download) when either is missing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer import embed as M
from pyramid_explorer import render as R


def _synthetic(n: int = 64, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.random((n, 42)) * np.tile(np.linspace(1, 0.05, 21), 2)
    return v / v.sum(1, keepdims=True)


def _cached(model: str) -> bool:
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(M.MODELS[model]["hf"], local_files_only=True)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------------------------- no torch needed


def test_registry_is_patch_aligned():
    for name, spec in M.MODELS.items():
        assert spec["size"] // 21 == spec["patch"] and spec["kind"] in R.KINDS, name
    assert M.MODELS["siglip2-base-naflex"]["processor"] == {"max_num_patches": 441}
    assert M.MODELS["dinov2-base"]["processor"] == {"do_resize": False, "do_center_crop": False}


def test_rendered_corpus_is_lazy_and_exact():
    S = _synthetic(5)
    rc = M.RenderedCorpus(S, "canon2", 336)
    assert len(rc) == 5 and rc.shape == (5, 336, 336, 3)
    assert np.array_equal(rc[1:3][1], R.render_canon2(S[2])) and rc[0:0].shape == (0, 336, 336, 3)


def test_pca64_no_whitening_and_deterministic():
    rng = np.random.default_rng(0)
    E = rng.normal(size=(300, 96)) * np.linspace(3, 0.1, 96)
    Z, mean, proj = M.pca64(E)
    assert Z.shape == (300, 64) and Z.dtype == np.float16 and mean.shape == (96,) and proj.shape == (96, 64)
    var = Z.astype(np.float64).var(0)
    assert np.all(np.diff(var) <= 1e-6) and var[0] > 5 * var[-1]          # sorted, NOT equalised
    assert np.allclose(proj.T @ proj, np.eye(64), atol=1e-4)
    Z2, _, proj2 = M.pca64(E)
    assert np.array_equal(Z, Z2) and np.array_equal(proj, proj2)
    ev = M.explained_variance(E)
    assert 0.9 < ev["64"] <= 1.0 and ev["16"] < ev["64"]
    assert np.isclose(ev["64"], Z.astype(np.float64).var(0).sum() / E.var(0).sum(), atol=1e-3)


def test_continuity_on_synthetic_trajectories():
    ids = np.repeat(["A", "B", "C"], 20)
    years = np.tile(np.arange(1950, 1970), 3)
    keys = pd.DataFrame({"id": ids, "year": years})
    rng = np.random.default_rng(0)
    base = rng.normal(size=(3, 8))
    E = np.repeat(base, 20, 0) + np.arange(60)[:, None] * 0.01                  # smooth walk per entity
    c = M.continuity(E, keys)
    assert c["all"]["C1"] == 1.0 and c["observed"]["n"] == 60 and c["projected"]["n"] == 0
    c = M.continuity(rng.permutation(E), keys)
    assert c["all"]["C1"] < 0.5


def test_diagnostic_rows_year_grid():
    keys = pd.DataFrame({"id": np.repeat(["A", "B"], 151), "year": np.tile(np.arange(1950, 2101), 2)})
    rows = M.diagnostic_rows(keys, n=2000, seed=0)
    assert len(rows) == 32 and set(keys["year"].to_numpy()[rows] % 10) == {0}
    assert np.array_equal(rows, M.diagnostic_rows(keys, n=2000, seed=0))


def test_variant_styles_are_patch_multiples():
    for model, spec in M.MODELS.items():
        for name, kw in M.variant_styles(model).items():
            h, w = kw["height"], kw.get("width") or kw["height"]
            assert h % spec["patch"] == 0 and w % spec["patch"] == 0, (model, name)
        assert M.variant_styles(model)["aspect"]["width"] * 3 == M.variant_styles(model)["aspect"]["height"] * 4


# --------------------------------------------------------------------------------------------- embed group


@pytest.mark.embed
@pytest.mark.parametrize("model", list(M.MODELS))
def test_processor_sees_render_unchanged(model):
    pytest.importorskip("torch")
    if not _cached(model):
        pytest.skip(f"{M.MODELS[model]['hf']} not in the local HF cache")
    spec = M.MODELS[model]
    imgs = M.RenderedCorpus(_synthetic(4), spec["kind"], spec["size"])[0:4]
    info = M.processor_check(model, imgs)
    assert info["ok"] and info["max_abs_pixel_diff_255"] <= 1.0 and info["fast_path_max_diff"] < 1e-4
    if model.startswith("siglip2"):
        assert info["spatial_shapes"] == [21, 21] and info["mask_sum"] == 441 and info["pixel_values_shape"] == [4, 441, 768]
    else:
        assert info["pixel_values_shape"][-2:] == [294, 294]
    with pytest.raises(AssertionError):                       # a wrongly sized render must be refused, not resampled
        M.processor_check(model, M.RenderedCorpus(_synthetic(2), spec["kind"], spec["size"] - spec["patch"])[0:2])


@pytest.mark.embed
@pytest.mark.parametrize("model", list(M.MODELS))
def test_fast_path_matches_hf_processor_on_variant_canvases(model):
    """The invariance diagnostic re-pins the processor per canvas; the tensor path must equal HF's output there too."""
    torch = pytest.importorskip("torch")
    if not _cached(model):
        pytest.skip(f"{M.MODELS[model]['hf']} not in the local HF cache")
    proc = M.load_processor(model)
    S = _synthetic(3)
    for name, kw in M.variant_styles(model).items():
        imgs = np.stack([R.render_style(v, **kw) for v in S])
        hf, fast = M._hf_inputs(model, imgs, proc), M._fast_inputs(model, imgs, proc, "cpu", torch.float32)
        assert hf["pixel_values"].shape == fast["pixel_values"].shape, name
        assert float((hf["pixel_values"].float() - fast["pixel_values"]).abs().max()) < 1e-4, name
        if model.startswith("siglip2"):
            assert torch.equal(hf["spatial_shapes"], fast["spatial_shapes"]), name
            assert hf["pixel_attention_mask"].sum(1).tolist() == [fast["pixel_values"].shape[1]] * len(S), name


@pytest.mark.embed
@pytest.mark.parametrize("model", list(M.MODELS))
def test_embed_is_normalised_and_deterministic(model):
    torch = pytest.importorskip("torch")
    if not _cached(model):
        pytest.skip(f"{M.MODELS[model]['hf']} not in the local HF cache")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    spec = M.MODELS[model]
    S = _synthetic(6)
    imgs = M.RenderedCorpus(S, spec["kind"], spec["size"])
    E = M.embed(model, imgs, batch=4, device=device)
    assert E.shape == (6, spec["dim"]) and E.dtype == np.float32
    assert np.allclose(np.linalg.norm(E, axis=1), 1.0, atol=1e-5)
    assert np.array_equal(E, M.embed(model, imgs, batch=4, device=device))
    assert np.array_equal(E[:2], M.embed(model, imgs[0:2], batch=4, device=device))     # batch-independent
    assert (E @ E.T).min() < 0.9999                                                      # different pyramids differ
    info = M.checkpoint_info(model)
    assert len(info["revision"]) == 40 and len(info["checkpoint_sha256"]) == 64
