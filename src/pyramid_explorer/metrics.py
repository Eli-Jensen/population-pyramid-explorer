"""Distance metrics on share vectors (CONTRACT §3 `metrics.py`, §4 definitions, AMENDMENTS §B).

numpy implements the metrics; every function is vectorised over the candidate matrix ``X [n, 42]``.
``sex="2"`` works on the 42 age×sex shares, ``sex="1"`` on the 21 total-age shares ``s21``.

Snapshot metrics: ``blend`` (default) · ``l2`` · ``w1`` · ``l2s`` · ``hel`` · ``feat`` · ``w1sex`` · ``w1bal`` · ``clr``;
trajectory metrics: ``trend`` (‖Δ_q − Δ_c‖₂ / σ_trend@L) and ``path`` (mean blend over aligned lags);
``visual:<model>`` = cosine distance in an image-embedding space passed as ``emb``.
σ constants come from `fit_sigma` (median over random same-year country pairs ≥ 100k) and live in
``data/processed/sigma.json`` as ``{metric: {"2": σ, "1": σ}}``.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer.features import NUMERIC_FEATURES, features, s21, zscore_vector, zscores
from pyramid_explorer.paths import DATA_PROCESSED, LAST_OBSERVED_YEAR, N_BINS, N_DIMS, N_YEARS

METRICS: list[str] = ["blend", "l2", "w1", "l2s", "hel", "feat", "w1sex", "w1bal", "clr", "trend", "path"]
SNAPSHOT_METRICS: list[str] = METRICS[:9]
SIGMA_METRICS: list[str] = ["l2", "w1", "w1sex", "l2s", "hel", "feat", "w1bal", "clr", "blend"]
TREND_WINDOWS: tuple[int, ...] = (5, 10, 20)
KERNEL = np.array([0.054, 0.242, 0.399, 0.242, 0.054])
BIN_WIDTH = 5.0
W1BAL_LAMBDA = 50.0             # w1bal: w1 + λ·Σ_k ½(s21_a,k + s21_b,k)·|r_a,k − r_b,k|, r = male share of bin (CONTRACT §4)
CLR_EPS = 1e-6
MINPOP_SIGMA = 100.0            # thousands
SIGMA_PATH = DATA_PROCESSED / "sigma.json"
# Fallback constants (measured on the REAL corpus — 280 entities, 42,280 rows — 2026-09-04) used only when no
# sigma.json exists; the build always writes sigma.json, so these matter for unit tests and ad-hoc scripts.
DEFAULT_SIGMA: dict[str, dict[str, float]] = {
    "l2": {"2": 0.0568, "1": 0.0781}, "w1sex": {"2": 7.618, "1": 6.168}, "w1": {"2": 6.168, "1": 6.168},
    "trend@5": {"2": 0.0182, "1": 0.0251}, "trend@10": {"2": 0.0294, "1": 0.0406}, "trend@20": {"2": 0.0396, "1": 0.0544},
}


# --------------------------------------------------------------------------------------------- helpers
def _view(v: np.ndarray, sex: str) -> np.ndarray:
    """The vector the metric runs on: s42 for sex="2", s21 for sex="1"."""
    v = np.asarray(v, dtype=np.float64)
    if sex == "2":
        return v
    if sex == "1":
        return s21(v)
    raise ValueError(f"sex must be '2' or '1', got {sex!r}")


def _sigma(sigma: dict | None, metric: str, sex: str) -> float:
    src = sigma if sigma is not None else DEFAULT_SIGMA
    try:
        return float(src[metric][sex])
    except KeyError as e:
        raise KeyError(f"sigma[{metric!r}][{sex!r}] missing (run fit_sigma)") from e


def cdf_per_sex(v: np.ndarray) -> np.ndarray:
    """Cumulative shares-of-total, per sex for s42 ([…, 42]) or total for s21 ([…, 21])."""
    v = np.asarray(v, dtype=np.float64)
    if v.shape[-1] == N_DIMS:
        return np.concatenate([np.cumsum(v[..., :N_BINS], -1), np.cumsum(v[..., N_BINS:], -1)], -1)
    return np.cumsum(v, -1)


def smooth(v: np.ndarray) -> np.ndarray:
    """Gaussian smoothing along age with KERNEL and nearest padding, per sex (works on s42 or s21)."""
    v = np.atleast_2d(np.asarray(v, dtype=np.float64))
    blocks = [v[:, :N_BINS], v[:, N_BINS:]] if v.shape[1] == N_DIMS else [v]
    out = []
    for b in blocks:
        p = np.pad(b, ((0, 0), (2, 2)), mode="edge")
        out.append(sum(KERNEL[j] * p[:, j:j + N_BINS] for j in range(5)))
    return np.concatenate(out, 1)


def clr(v: np.ndarray) -> np.ndarray:
    lg = np.log(np.asarray(v, dtype=np.float64) + CLR_EPS)
    return lg - lg.mean(-1, keepdims=True)


def _l2(q: np.ndarray, X: np.ndarray) -> np.ndarray:
    return np.sqrt(((X - q) ** 2).sum(1))


def _w1(cq: np.ndarray, CX: np.ndarray) -> np.ndarray:
    return BIN_WIDTH * np.abs(CX - cq).sum(1)


# --------------------------------------------------------------------------------------------- distances
def distances(metric: str, q: np.ndarray, X: np.ndarray, *, sex: str = "2", sigma: dict | None = None,
              feats: pd.DataFrame | None = None, emb: np.ndarray | None = None, q_row: int | None = None,
              L: int = 10, X_prev: np.ndarray | None = None, q_prev: np.ndarray | None = None) -> np.ndarray:
    """Distance from query ``q [42]`` to every row of ``X [n, 42]`` → float32 ``[n]``.

    ``feats``: for ``feat``, a `zscores` frame aligned with X (its attrs standardise ``q`` too); a raw feature
    frame or None is standardised against all rows of X.  ``emb``/``q_row``: for ``visual:<model>``, the
    embedding matrix aligned with X and the row whose embedding is the query.  ``X_prev``/``q_prev``: the
    L-years-earlier counterparts for ``trend`` (``[n, 42]`` / ``[42]``) or, for ``path``, the stacked lags
    5, 10, …, L (``[m, n, 42]`` / ``[m, 42]``); rows whose lag is undefined may be NaN (they come back NaN).
    """
    X = np.asarray(X, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64).reshape(-1)
    if metric.startswith("visual:"):
        if emb is None or q_row is None:
            raise ValueError("visual metrics need emb and q_row")
        E = np.asarray(emb, dtype=np.float64)
        e = E[q_row]
        cos = (E @ e) / (np.linalg.norm(E, axis=1) * np.linalg.norm(e) + 1e-12)
        return (1.0 - cos).astype(np.float32)
    if metric == "trend":
        if X_prev is None or q_prev is None:
            raise ValueError("trend needs X_prev and q_prev")
        Xp = np.asarray(X_prev, dtype=np.float64)
        qp = np.asarray(q_prev, dtype=np.float64)
        if Xp.ndim == 3:
            Xp, qp = Xp[-1], qp[-1]
        dq, dX = _view(q - qp, sex), _view(X - Xp, sex)
        return (_l2(dq, dX) / _sigma(sigma, f"trend@{L}", sex)).astype(np.float32)
    if metric == "path":
        if X_prev is None or q_prev is None or np.ndim(X_prev) != 3:
            raise ValueError("path needs stacked lags X_prev [m,n,42] and q_prev [m,42]")
        acc = distances("blend", q, X, sex=sex, sigma=sigma).astype(np.float64)
        for Xl, ql in zip(X_prev, q_prev):
            acc += distances("blend", ql, Xl, sex=sex, sigma=sigma)
        return (acc / (1 + len(X_prev))).astype(np.float32)

    Xv, qv = _view(X, sex), _view(q, sex)
    if metric == "l2":
        d = _l2(qv, Xv)
    elif metric in ("w1", "w1sex"):
        if metric == "w1" or sex == "1":
            d = _w1(np.cumsum(_view(q, "1")), np.cumsum(_view(X, "1"), 1))
        else:
            d = _w1(cdf_per_sex(qv), cdf_per_sex(Xv))
    elif metric == "blend":
        l2 = _l2(qv, Xv) / _sigma(sigma, "l2", sex)
        if sex == "2":
            w = _w1(cdf_per_sex(qv), cdf_per_sex(Xv)) / _sigma(sigma, "w1sex", "2")
        else:
            w = _w1(np.cumsum(qv), np.cumsum(Xv, 1)) / _sigma(sigma, "w1", "1")
        d = 0.5 * l2 + 0.5 * w
    elif metric == "l2s":
        d = _l2(smooth(qv)[0], smooth(Xv))
    elif metric == "hel":
        d = _l2(np.sqrt(qv), np.sqrt(Xv)) / np.sqrt(2.0)
    elif metric == "clr":
        d = _l2(clr(qv), clr(Xv))
    elif metric == "w1bal":
        # w1 on s21 + λ·Σ_k w_k|r_a,k − r_b,k|; the bin weight is SYMMETRIC, w_k = ½(s21_a,k + s21_b,k), so the
        # metric is a proper distance (same value from either side) — the web twin must use the same weight.
        a21, Q21 = _view(X, "1"), _view(q, "1")
        d = _w1(np.cumsum(Q21), np.cumsum(a21, 1))
        if sex == "2":
            rX = np.divide(X[:, :N_BINS], a21, out=np.full_like(a21, 0.5), where=a21 > 0)
            rq = np.divide(q[:N_BINS], Q21, out=np.full_like(Q21, 0.5), where=Q21 > 0)
            d = d + W1BAL_LAMBDA * (0.5 * (a21 + Q21) * np.abs(rX - rq)).sum(1)
    elif metric == "feat":
        if feats is None or "mu" not in feats.attrs:
            feats = zscores(features(X) if feats is None else feats, np.arange(len(X)))
        zq = zscore_vector(features(q), feats)[0]
        d = _l2(zq, feats[NUMERIC_FEATURES].to_numpy(dtype=np.float64))
    else:
        raise ValueError(f"unknown metric {metric!r}; known: {METRICS} + 'visual:<model>'")
    return d.astype(np.float32)


# --------------------------------------------------------------------------------------------- sigma
def lagged(X: np.ndarray, lag: int, n_years: int = N_YEARS) -> np.ndarray:
    """``X`` shifted ``lag`` rows within each entity (entity-major corpus); undefined rows are NaN."""
    out = np.full_like(X, np.nan, dtype=np.float64)
    out[lag:] = X[:-lag]
    within = (np.arange(len(X)) % n_years) >= lag
    out[~within] = np.nan
    return out


def sample_pairs(keys: pd.DataFrame, entities: list[dict], n_pairs: int, seed: int = 0,
                 minpop: float = MINPOP_SIGMA, min_year: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Random same-year pairs of distinct COUNTRY rows with pop ≥ minpop (years drawn uniformly)."""
    rng = np.random.default_rng(seed)
    country = {e["id"] for e in entities if e["type"] == "country"}
    ok = keys["id"].isin(country).to_numpy() & (keys["pop_total"].to_numpy() >= minpop)
    if min_year is not None:
        ok &= keys["year"].to_numpy() >= min_year
    years = keys["year"].to_numpy()
    groups = {y: np.flatnonzero(ok & (years == y)) for y in np.unique(years[ok])}
    ys = [y for y, g in groups.items() if len(g) >= 2]
    draw = rng.choice(ys, size=n_pairs)
    a, b = np.empty(n_pairs, int), np.empty(n_pairs, int)
    for y in ys:
        pos = np.flatnonzero(draw == y)
        if len(pos) == 0:
            continue
        g = groups[y]
        i = rng.integers(0, len(g), len(pos))
        j = (i + rng.integers(1, len(g), len(pos))) % len(g)      # j ≠ i
        a[pos], b[pos] = g[i], g[j]
    return a, b


def _pair_dist(metric: str, A: np.ndarray, B: np.ndarray, sex: str, **kw) -> np.ndarray:
    """Row-wise distances between paired rows (loops over the query side; fine for 20k pairs)."""
    if metric == "l2":
        return _l2(_view(A, sex), _view(B, sex))
    if metric in ("w1", "w1sex"):
        if metric == "w1" or sex == "1":
            return _w1(np.cumsum(_view(A, "1"), 1), np.cumsum(_view(B, "1"), 1))
        return _w1(cdf_per_sex(A), cdf_per_sex(B))
    if metric == "l2s":
        return _l2(smooth(_view(A, sex)), smooth(_view(B, sex)))
    if metric == "hel":
        return _l2(np.sqrt(_view(A, sex)), np.sqrt(_view(B, sex))) / np.sqrt(2.0)
    if metric == "clr":
        return _l2(clr(_view(A, sex)), clr(_view(B, sex)))
    if metric == "w1bal":
        a21, b21 = _view(A, "1"), _view(B, "1")
        d = _w1(np.cumsum(a21, 1), np.cumsum(b21, 1))
        if sex == "2":
            rA = np.divide(A[:, :N_BINS], a21, out=np.full_like(a21, 0.5), where=a21 > 0)
            rB = np.divide(B[:, :N_BINS], b21, out=np.full_like(b21, 0.5), where=b21 > 0)
            d = d + W1BAL_LAMBDA * (0.5 * (a21 + b21) * np.abs(rA - rB)).sum(1)
        return d
    raise ValueError(metric)


def fit_sigma(X: np.ndarray, keys: pd.DataFrame, entities: list[dict], seed: int = 0, n_pairs: int = 20000,
              *, write: bool = False, path: Path | None = None) -> dict:
    """Median distance over ``n_pairs`` random same-year country pairs ≥ 100k, per metric × sex.

    Keys: every SIGMA_METRICS entry plus ``trend@5/10/20``; each maps to ``{"2": σ, "1": σ}``.
    ``blend`` is derived from the fitted l2 / w1 sigmas (its own median is then reported for reference).
    With ``write=True`` the dict is also written to ``data/processed/sigma.json`` (or ``path``).
    """
    X = np.asarray(X, dtype=np.float64)
    a, b = sample_pairs(keys, entities, n_pairs, seed)
    A, B = X[a], X[b]
    out: dict[str, dict[str, float]] = {}
    for metric in ("l2", "w1", "w1sex", "l2s", "hel", "clr", "w1bal"):
        out[metric] = {sex: float(np.median(_pair_dist(metric, A, B, sex))) for sex in ("2", "1")}
    # feat: z-scored per year against that year's eligible country rows
    feat = features(X)[NUMERIC_FEATURES].to_numpy(dtype=np.float64)
    country = {e["id"] for e in entities if e["type"] == "country"}
    ok = keys["id"].isin(country).to_numpy() & (keys["pop_total"].to_numpy() >= MINPOP_SIGMA)
    years = keys["year"].to_numpy()
    z = np.full_like(feat, np.nan)
    for y in np.unique(years):
        ref = ok & (years == y)
        mu, sd = np.nanmean(feat[ref], 0), np.nanstd(feat[ref], 0)
        sd = np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)
        z[years == y] = (feat[years == y] - mu) / sd
    dfeat = float(np.nanmedian(_l2(z[a], z[b])))
    out["feat"] = {"2": dfeat, "1": dfeat}
    out["blend"] = {}
    for sex in ("2", "1"):
        d = distances_pairs_blend(A, B, sex, out)
        out["blend"][sex] = float(np.median(d))
    for L in TREND_WINDOWS:
        Xl = lagged(X, L)
        al, bl = sample_pairs(keys, entities, n_pairs, seed + L, min_year=int(keys["year"].min()) + L)
        dA, dB = X[al] - Xl[al], X[bl] - Xl[bl]
        out[f"trend@{L}"] = {sex: float(np.median(_l2(_view(dA, sex), _view(dB, sex)))) for sex in ("2", "1")}
    if write:
        p = path or SIGMA_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1))
    return out


def distances_pairs_blend(A: np.ndarray, B: np.ndarray, sex: str, sigma: dict) -> np.ndarray:
    """Row-wise blend distance between paired rows (used by fit_sigma for the reference median)."""
    l2 = _pair_dist("l2", A, B, sex) / _sigma(sigma, "l2", sex)
    w = (_pair_dist("w1sex", A, B, "2") / _sigma(sigma, "w1sex", "2") if sex == "2"
         else _pair_dist("w1", A, B, "1") / _sigma(sigma, "w1", "1"))
    return 0.5 * l2 + 0.5 * w


def blend_balance(X: np.ndarray, keys: pd.DataFrame, entities: list[dict], sigma: dict, *, seed: int = 0,
                  n_pairs: int = 20000, current_year: int = 2026,
                  last_observed_year: int = LAST_OBSERVED_YEAR) -> dict[str, dict[str, float]]:
    """Median share of the W1 term in the blend distance, by era of the (same-year) pair.

    σ is fitted on pairs pooled over 1950–2100, so the two halves of ``blend`` are equal only on the pooled
    sample; σ_w1 grows into the projections, which tilts observed-year pairs towards L2. Returned per sex:
    ``{"obs": ≤ last_observed_year, "nowcast": (last_observed_year, current_year], "proj": > current_year,
    "all": pooled}`` — the documented asymmetry in evals/RESULTS.md and the build report.
    """
    X = np.asarray(X, dtype=np.float64)
    a, b = sample_pairs(keys, entities, n_pairs, seed)
    yr = keys["year"].to_numpy()[a]
    eras = {"obs": yr <= last_observed_year, "nowcast": (yr > last_observed_year) & (yr <= current_year),
            "proj": yr > current_year, "all": np.ones(len(a), bool)}
    out: dict[str, dict[str, float]] = {}
    for sex in ("2", "1"):
        l2 = 0.5 * _pair_dist("l2", X[a], X[b], sex) / _sigma(sigma, "l2", sex)
        w = 0.5 * (_pair_dist("w1sex", X[a], X[b], "2") / _sigma(sigma, "w1sex", "2") if sex == "2"
                   else _pair_dist("w1", X[a], X[b], "1") / _sigma(sigma, "w1", "1"))
        share = w / np.maximum(l2 + w, 1e-12)
        out[sex] = {k: float(np.median(share[m])) for k, m in eras.items() if m.any()}
    return out


def load_sigma(path: Path | None = None) -> dict:
    """``sigma.json`` if present, else the DEFAULT_SIGMA fallback constants."""
    p = path or SIGMA_PATH
    return json.loads(p.read_text()) if p.exists() else dict(DEFAULT_SIGMA)


# --------------------------------------------------------------------------------------------- decompose
def decompose(metric: str, q: np.ndarray, x: np.ndarray, *, sex: str, sigma: dict, top: int = 3) -> dict:
    """Explain one pair: the ranking metric's ``d`` and its blend decomposition.

    Returns ``{"d", "l2_part", "w1_part", "w1_years", "top_bins_l2": [(bin_idx, contribution)…],
    "top_bins_w1": […]}``.  ``l2_part``/``w1_part`` are the two normalised blend terms (they sum to the
    blend distance); for ``l2``/``w1``/``w1sex`` the foreign term is reported as 0.  ``top_bins_l2`` are the
    bins with the largest share of the squared L2 gap (fractions summing to 1 over all bins);
    ``top_bins_w1`` the bins with the largest transport in years (sum = ``w1_years``).  Bin indices refer
    to the 42-vector for sex="2" (0–20 male, 21–41 female) and to s21 for sex="1".
    """
    q, x = np.asarray(q, np.float64).reshape(-1), np.asarray(x, np.float64).reshape(-1)
    qv, xv = _view(q, sex), _view(x, sex)
    sq = (xv - qv) ** 2
    l2 = float(np.sqrt(sq.sum()))
    w1_bins = BIN_WIDTH * np.abs(cdf_per_sex(xv) - cdf_per_sex(qv))
    w1_years = float(w1_bins.sum())
    l2_part = 0.5 * l2 / _sigma(sigma, "l2", sex)
    w1_part = 0.5 * w1_years / _sigma(sigma, "w1sex" if sex == "2" else "w1", sex)
    d = float(distances(metric, q, x[None, :], sex=sex, sigma=sigma)[0]) if metric in SNAPSHOT_METRICS else None
    if metric == "l2":
        l2_part, w1_part = d, 0.0
    elif metric in ("w1", "w1sex"):
        l2_part, w1_part = 0.0, d
    elif metric == "blend":
        d = l2_part + w1_part
    frac = sq / sq.sum() if sq.sum() > 0 else sq
    order_l2, order_w1 = np.argsort(-frac)[:top], np.argsort(-w1_bins)[:top]
    return {"d": d, "l2_part": float(l2_part), "w1_part": float(w1_part), "w1_years": w1_years,
            "top_bins_l2": [(int(k), float(frac[k])) for k in order_l2],
            "top_bins_w1": [(int(k), float(w1_bins[k])) for k in order_w1]}


def bin_label(k: int, sex: str = "2") -> str:
    """Human label for a decomposition bin index, e.g. ``'M 20-24'`` or ``'F 100+'`` (``'20-24'`` for s21)."""
    prefix = "" if sex == "1" else ("M " if k < N_BINS else "F ")
    a = 5 * (k % N_BINS)
    return f"{prefix}{a}+" if a == 100 else f"{prefix}{a}-{a + 4}"
