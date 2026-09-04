"""Image embeddings of canonical pyramid renders (CONTRACT §3 `embed.py`, PLAN §4.5).

Two Apache-2.0 encoders, each fed a render whose rows align with its patch grid so the HF processor never
resamples: SigLIP 2 base NaFlex on 336² (21 × 16 px) and DINOv2 base on 294² (21 × 14 px).  `processor_check`
proves that on the first batch (asserted shapes + pixel round trip) and `embed` then uses an equivalent fast
tensor path (asserted equal to the HF processor's output).  `pca64` compresses the L2-normalised embeddings to
64 dims without whitening.  The remaining functions are the evaluation helpers used by
``scripts/embed_images.py``: G1 continuity, rank agreement with the numeric metrics, and the factorial
invariance diagnostic (colour, gap, resolution, aspect) pre-registered in ``evals/image_embeddings.md``.

torch/transformers are imported lazily so the module is importable without the ``embed`` dependency group.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pyramid_explorer import render as R
from pyramid_explorer.paths import EVALS, LAST_OBSERVED_YEAR, N_DIMS

EMB_DIR = EVALS / "embeddings"
MODELS: dict[str, dict[str, Any]] = {
    "siglip2-base-naflex": {
        "hf": "google/siglip2-base-patch16-naflex", "patch": 16, "size": 336, "kind": "canon2", "dim": 768,
        "processor": {"max_num_patches": 441}, "licence": "Apache-2.0",
    },
    "dinov2-base": {
        "hf": "facebook/dinov2-base", "patch": 14, "size": 294, "kind": "canon2", "dim": 768,
        "processor": {"do_resize": False, "do_center_crop": False}, "licence": "Apache-2.0",
    },
}
for _name, _spec in MODELS.items():                      # PLAN §4.5: one exact patch row per age bin
    assert _spec["size"] % 21 == 0 and _spec["size"] // 21 == _spec["patch"], _name
_CACHE: dict[tuple[str, str, str], tuple[Any, Any]] = {}


class RenderedCorpus(Sequence):
    """Lazy ``[n, H, W, 3]`` image source: renders rows on demand so a 12 GB array never has to exist in RAM."""

    def __init__(self, s42: np.ndarray, kind: str = "canon2", size: int | None = None):
        self.s42 = np.asarray(s42, dtype=np.float64)
        self.kind, self.size = kind, R.KINDS[kind] if size is None else int(size)
        self._fn = R.render_canon2 if kind == "canon2" else R.render_canon1
        self.shape = (len(self.s42), self.size, self.size, 3)

    def __len__(self) -> int:
        return len(self.s42)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return np.stack([self._fn(v, self.size) for v in self.s42[i]]) if len(self.s42[i]) else \
                np.zeros((0, self.size, self.size, 3), np.uint8)
        return self._fn(self.s42[i], self.size)


# --------------------------------------------------------------------------------------------- models


def _spec(model: str) -> dict[str, Any]:
    if model not in MODELS:
        raise KeyError(f"unknown model {model!r}; known: {list(MODELS)}")
    return MODELS[model]


def load_processor(model: str, **override) -> Any:
    """The HF image processor pinned to the render size (PIL backend: no torchvision needed)."""
    spec = _spec(model)
    if model.startswith("siglip2"):
        from transformers import Siglip2ImageProcessorPil as P
    else:
        from transformers import BitImageProcessorPil as P
    return P.from_pretrained(spec["hf"], **{**spec["processor"], **override})


def load_model(model: str, device: str = "mps", dtype: str = "float16") -> tuple[Any, Any]:
    """(torch module in eval mode on ``device``, HF processor); cached per (model, device, dtype)."""
    key = (model, device, dtype)
    if key not in _CACHE:
        import torch
        import transformers
        transformers.logging.set_verbosity_error()          # the vision-only load reports the unused text tower
        transformers.logging.disable_progress_bar()
        spec = _spec(model)
        dt = getattr(torch, dtype)
        if model.startswith("siglip2"):
            from transformers import Siglip2VisionModel
            net = Siglip2VisionModel.from_pretrained(spec["hf"], dtype=dt)
        else:
            from transformers import Dinov2Model
            net = Dinov2Model.from_pretrained(spec["hf"], dtype=dt)
        _CACHE[key] = (net.to(device).eval(), load_processor(model))
    return _CACHE[key]


def checkpoint_info(model: str) -> dict[str, str]:
    """HF revision (snapshot commit) and sha256 of ``model.safetensors`` from the local hub cache (no network)."""
    from huggingface_hub import snapshot_download
    path = Path(snapshot_download(_spec(model)["hf"], local_files_only=True))
    weights = path / "model.safetensors"
    blob = os.readlink(weights) if weights.is_symlink() else str(weights)
    return {"hf": _spec(model)["hf"], "revision": path.name, "checkpoint_sha256": Path(blob).name}


# --------------------------------------------------------------------------------------------- preprocessing


def _fast_inputs(model: str, images: np.ndarray, proc: Any, device: str, dtype: Any) -> dict[str, Any]:
    """Tensor-only equivalent of the HF processor for an aligned batch ``[B, H, W, 3]`` uint8 (any patch-multiple size)."""
    import torch
    spec = _spec(model)
    arr = np.ascontiguousarray(images)
    if not arr.flags.writeable:                              # read-only memmap slice: torch wants a writable buffer
        arr = arr.copy()
    x = torch.from_numpy(arr).to(device).to(torch.float32) / 255.0
    mean = torch.tensor(proc.image_mean, device=device).view(1, 1, 1, 3)
    std = torch.tensor(proc.image_std, device=device).view(1, 1, 1, 3)
    x = (x - mean) / std
    B, H, W, _ = x.shape
    p = spec["patch"]
    if H % p or W % p:
        raise ValueError(f"image {H}x{W} is not a multiple of patch {p}")
    if model.startswith("siglip2"):
        h, w = H // p, W // p
        patches = x.view(B, h, p, w, p, 3).permute(0, 1, 3, 2, 4, 5).reshape(B, h * w, p * p * 3)
        return {"pixel_values": patches.to(dtype),
                "pixel_attention_mask": torch.ones(B, h * w, dtype=torch.long, device=device),
                "spatial_shapes": torch.tensor([[h, w]] * B, dtype=torch.long, device=device)}
    return {"pixel_values": x.permute(0, 3, 1, 2).contiguous().to(dtype)}


def _hf_inputs(model: str, images: np.ndarray, proc: Any) -> dict[str, Any]:
    """The HF processor's own output for a batch; ``max_num_patches`` follows the image size for naflex."""
    H, W = images.shape[1:3]
    if model.startswith("siglip2"):
        p = _spec(model)["patch"]
        return dict(proc(images=list(images), return_tensors="pt", max_num_patches=(H // p) * (W // p)))
    return dict(proc(images=list(images), return_tensors="pt"))


def processor_check(model: str, images: np.ndarray) -> dict[str, Any]:
    """Run one batch through the HF processor and assert it saw the render unchanged (PLAN §4.5).

    Refuses (AssertionError) anything but the model's canonical render size; then asserts naflex
    ``spatial_shapes == (21, 21)`` and ``pixel_attention_mask.sum() == 441`` (for the canonical 336² render),
    DINOv2 ``pixel_values.shape[-2:] == (294, 294)``, and that un-patching/un-normalising the
    processor output reproduces the input pixels to ≤ 1/255; also that the fast tensor path used by `embed`
    matches the HF output.  Returns the asserted values for ``*.meta.json``.
    """
    import torch
    spec = _spec(model)
    images = np.array(images)                                # a writable copy (may be a read-only memmap slice)
    if images.ndim == 3:
        images = images[None]
    B, H, W, _ = images.shape
    assert (H, W) == (spec["size"], spec["size"]), f"{model} expects {spec['size']}² canonical renders, got {H}×{W}"
    proc = load_processor(model)
    out = _hf_inputs(model, images, proc)
    mean = torch.tensor(proc.image_mean).view(1, 1, 1, 3)
    std = torch.tensor(proc.image_std).view(1, 1, 1, 3)
    info: dict[str, Any] = {"model": model, "hf_processor": type(proc).__name__, "batch": int(B), "image_hw": [H, W],
                            "processor_config": dict(spec["processor"]),
                            "image_mean": list(map(float, proc.image_mean)), "image_std": list(map(float, proc.image_std))}
    p = spec["patch"]
    if model.startswith("siglip2"):
        pv, mask, ss = out["pixel_values"], out["pixel_attention_mask"], out["spatial_shapes"]
        h, w = H // p, W // p
        assert tuple(ss[0].tolist()) == (h, w), f"spatial_shapes {ss[0].tolist()} != {(h, w)}"
        assert int(mask.sum(1)[0]) == h * w == pv.shape[1], f"mask sum {int(mask.sum(1)[0])} != {h * w}"
        rec = pv.float().view(B, h, w, p, p, 3).permute(0, 1, 3, 2, 4, 5).reshape(B, H, W, 3)
        info.update(spatial_shapes=[h, w], mask_sum=int(mask.sum(1)[0]), pixel_values_shape=list(pv.shape))
    else:
        pv = out["pixel_values"]
        assert tuple(pv.shape[-2:]) == (H, W), f"pixel_values {tuple(pv.shape)} != {(H, W)}"
        rec = pv.float().permute(0, 2, 3, 1)
        info.update(pixel_values_shape=list(pv.shape))
    rec = (rec * std + mean) * 255.0
    diff = float((rec - torch.from_numpy(images).float()).abs().max())
    assert diff <= 1.0 + 1e-6, f"processor resampled the render: max abs pixel diff {diff:.3f} > 1/255"
    fast = _fast_inputs(model, images, proc, "cpu", torch.float32)
    fdiff = float((fast["pixel_values"].float() - pv.float()).abs().max())
    assert fdiff < 1e-4, f"fast path differs from HF processor by {fdiff}"
    info.update(max_abs_pixel_diff_255=diff, fast_path_max_diff=fdiff, ok=True)
    return info


# --------------------------------------------------------------------------------------------- embedding


def embed(model: str, images, *, batch: int = 32, device: str = "mps", dtype: str = "float16",
          progress: bool = False) -> np.ndarray:
    """Pooled image features for ``images`` (``[n, H, W, 3]`` uint8 array, memmap or `RenderedCorpus`) → float32 ``[n, D]`` L2-normalised."""
    import torch
    net, proc = load_model(model, device, dtype)
    dt = getattr(torch, dtype)
    n, out = len(images), []
    with torch.no_grad():
        for i in range(0, n, batch):
            inp = _fast_inputs(model, np.asarray(images[i:i + batch]), proc, device, dt)
            feats = net(**inp).pooler_output
            out.append(torch.nn.functional.normalize(feats.float(), dim=-1).cpu().numpy())
            if progress and (i // batch) % 100 == 0:
                print(f"  {model}: {min(i + batch, n)}/{n}", flush=True)
    return np.concatenate(out).astype(np.float32) if out else np.zeros((0, _spec(model)["dim"]), np.float32)


def pca64(E: np.ndarray, k: int = 64) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PCA to ``k`` components without whitening → (Z float16 [n, k], mean float32 [D], proj float32 [D, k]).

    Deterministic: eigen-decomposition of the covariance, components sorted by variance, each component's sign
    fixed so its largest-magnitude loading is positive.
    """
    X = np.asarray(E, dtype=np.float64)
    mean = X.mean(0)
    Xc = X - mean
    w, V = np.linalg.eigh(Xc.T @ Xc / max(len(X) - 1, 1))
    order = np.argsort(w)[::-1][:k]
    proj = V[:, order]
    proj *= np.sign(proj[np.abs(proj).argmax(0), np.arange(proj.shape[1])])
    Z = Xc @ proj
    return Z.astype(np.float16), mean.astype(np.float32), proj.astype(np.float32)


def explained_variance(E: np.ndarray, ks: Sequence[int] = (16, 64)) -> dict[str, float]:
    """Cumulative explained-variance ratio of the top-k PCs of ``E``."""
    X = np.asarray(E, dtype=np.float64)
    Xc = X - X.mean(0)
    w = np.sort(np.linalg.eigvalsh(Xc.T @ Xc))[::-1]
    c = np.cumsum(w) / w.sum()
    return {str(k): float(c[k - 1]) for k in ks}


# --------------------------------------------------------------------------------------------- evaluation helpers


def _unit(E: np.ndarray) -> np.ndarray:
    E = np.asarray(E, dtype=np.float32)
    return E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-12)


def topk_cosine(E: np.ndarray, k: int = 5, chunk: int = 2048) -> np.ndarray:
    """Indices of the ``k`` nearest rows (cosine, self excluded) for every row → int32 ``[n, k]`` sorted nearest first."""
    E = _unit(E)
    n = len(E)
    out = np.empty((n, k), dtype=np.int32)
    for i in range(0, n, chunk):
        S = E[i:i + chunk] @ E.T
        S[np.arange(S.shape[0]), np.arange(i, i + S.shape[0])] = -np.inf
        part = np.argpartition(-S, k, axis=1)[:, :k]
        rows = np.arange(S.shape[0])[:, None]
        out[i:i + chunk] = part[rows, np.argsort(-S[rows, part], axis=1)]
    return out


def continuity(E: np.ndarray, keys: pd.DataFrame, k: int = 5) -> dict[str, dict[str, float]]:
    """G1 continuity of a cosine space: C1 = P(NN is the same entity within ±1 year), C5 = P(one is in the top-k).

    Split by query year (observed ≤ LAST_OBSERVED_YEAR vs projected) and reported for all rows.
    """
    nn = topk_cosine(E, k)
    ids = keys["id"].to_numpy()
    years = keys["year"].to_numpy()
    hit = (ids[nn] == ids[:, None]) & (np.abs(years[nn] - years[:, None]) <= 1)
    c1, ck = hit[:, 0], hit.any(1)
    obs = years <= LAST_OBSERVED_YEAR
    res = {}
    for name, m in (("all", np.ones_like(obs)), ("observed", obs), ("projected", ~obs)):
        n = int(m.sum())
        res[name] = {"C1": float(c1[m].mean()) if n else float("nan"), f"C{k}": float(ck[m].mean()) if n else float("nan"), "n": n}
    return res


def rank_agreement(E: np.ndarray, s42: np.ndarray, keys: pd.DataFrame, dist_fns: dict[str, Any], *,
                   n_pairs: int = 2000, n_queries: int = 300, k: int = 10, seed: int = 0) -> dict[str, Any]:
    """Spearman of pairwise distances and top-k overlap between a cosine space and numeric metrics.

    ``dist_fns[name](q, X) -> [len(X)]`` numeric distances.  Pairs: random row pairs.  Queries: random rows;
    candidates exclude the query's own entity, once restricted to the query's year (product default) and once
    over every year.
    """
    from scipy.stats import spearmanr
    E = _unit(E)
    rng = np.random.default_rng(seed)
    n = len(E)
    a, b = rng.integers(0, n, n_pairs), rng.integers(0, n, n_pairs)
    keep = a != b
    a, b = a[keep], b[keep]
    cosd = 1.0 - (E[a] * E[b]).sum(1)
    out: dict[str, Any] = {"n_pairs": int(len(a)), "spearman": {}, "overlap_same_year": {}, "overlap_any_year": {}}
    for name, fn in dist_fns.items():
        d = np.array([fn(s42[i], s42[j:j + 1])[0] for i, j in zip(a, b)])
        out["spearman"][name] = float(spearmanr(cosd, d).correlation)
    ids, years = keys["id"].to_numpy(), keys["year"].to_numpy()
    qs = rng.choice(n, n_queries, replace=False)
    for scope in ("same_year", "any_year"):
        acc = {name: [] for name in dist_fns}
        for q in qs:
            cand = np.flatnonzero((ids != ids[q]) & ((years == years[q]) if scope == "same_year" else True))
            top_e = set(cand[np.argsort(-(E[cand] @ E[q]))[:k]].tolist())
            for name, fn in dist_fns.items():
                top_d = set(cand[np.argsort(fn(s42[q], s42[cand]))[:k]].tolist())
                acc[name].append(len(top_e & top_d) / k)
        out[f"overlap_{scope}"] = {name: float(np.mean(v)) for name, v in acc.items()}
    out["n_queries"] = int(n_queries)
    return out


def dynamic_range(E: np.ndarray, n_pairs: int = 20000, seed: int = 0) -> dict[str, float]:
    """p1 / p50 / p99 of cosine similarity over random row pairs (how much of [-1, 1] the space actually uses)."""
    E = _unit(E)
    rng = np.random.default_rng(seed)
    a, b = rng.integers(0, len(E), n_pairs), rng.integers(0, len(E), n_pairs)
    c = (E[a] * E[b]).sum(1)[a != b]
    return {"p1": float(np.percentile(c, 1)), "p50": float(np.percentile(c, 50)), "p99": float(np.percentile(c, 99))}


# --------------------------------------------------------------------------------------------- invariance diagnostic

GREY_PALETTE = ((60, 60, 60), (160, 160, 160))


def diagnostic_rows(keys: pd.DataFrame, n: int = 2000, seed: int = 0, step: int = 10) -> np.ndarray:
    """``n`` corpus rows drawn from the year grid 1950, 1960, … so same-entity samples are ≥ ``step`` years apart."""
    years = keys["year"].to_numpy()
    grid = np.flatnonzero((years - years.min()) % step == 0)
    return np.sort(np.random.default_rng(seed).choice(grid, min(n, len(grid)), replace=False))


def variant_styles(model: str) -> dict[str, dict[str, Any]]:
    """The factorial factors of PLAN §4.5, each alone, as `render_style` kwargs (base first)."""
    spec = _spec(model)
    s, p, kind = spec["size"], spec["patch"], spec["kind"]
    return {
        "base": dict(kind=kind, height=s),
        "colour": dict(kind=kind, height=s, palette=GREY_PALETTE),
        "gap": dict(kind=kind, height=s, gap=2),
        "resolution-": dict(kind=kind, height=s - 2 * p),
        "resolution+": dict(kind=kind, height=s + 2 * p),
        "aspect": dict(kind=kind, height=s, width=s + 7 * p),      # 21 × 28 patches = 4:3
    }


def invariance_diagnostic(model: str, s42: np.ndarray, rows: np.ndarray, *, batch: int = 32, device: str = "mps",
                          dtype: str = "float16", k: int = 10) -> dict[str, dict[str, float]]:
    """Cross-style self-match rank and top-k Jaccard for every factor of `variant_styles` (reported, never gated)."""
    X = np.asarray(s42, dtype=np.float64)[rows]
    styles = variant_styles(model)
    embs = {}
    for name, kw in styles.items():
        imgs = np.stack([R.render_style(v, **kw) for v in X])
        embs[name] = _unit(embed(model, imgs, batch=batch, device=device, dtype=dtype))
    base = embs["base"]
    Gb = base @ base.T
    np.fill_diagonal(Gb, -np.inf)
    nn_base = np.argsort(-Gb, axis=1)[:, :k]
    nearest_other = float(Gb.max(1).mean())
    res: dict[str, dict[str, float]] = {}
    for name, Ev in embs.items():
        if name == "base":
            continue
        S = Ev @ base.T                                   # variant query i vs canonical gallery
        self_sim = np.diag(S).copy()
        rank = 1 + (S > self_sim[:, None]).sum(1)
        Sv = Ev @ Ev.T
        np.fill_diagonal(Sv, -np.inf)
        nn_var = np.argsort(-Sv, axis=1)[:, :k]
        jac = [len(set(a) & set(b)) / len(set(a) | set(b)) for a, b in zip(nn_base, nn_var)]
        res[name] = {"self_cos_mean": float(self_sim.mean()), "nearest_other_cos_mean": nearest_other,
                     "self_rank_median": float(np.median(rank)), "top1": float((rank == 1).mean()),
                     "top10": float((rank <= k).mean()), f"jaccard_top{k}": float(np.mean(jac)),
                     "image_hw": [styles[name]["height"], styles[name].get("width") or styles[name]["height"]]}
    return res
