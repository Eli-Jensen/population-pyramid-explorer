"""Standard errors for overlapping-window panels (PREREG.md §3.6–3.7, §4) — pure numpy/pandas.

Every estimator here is written out rather than imported: Hansen–Hodrick (uniform kernel), Newey–West
(Bartlett), country-cluster HAC, the two block-bootstrap schemes whose wider CI is the pre-registered
headline, Driscoll–Kraay and two-way cluster OLS, the exact sign test, and ``N_eff``. statsmodels is
only ever an optional cross-check inside the tests (import-guarded there, never imported here).

Conventions: a residual series ``u`` is one value per T (the T-aggregated per-T means, ordered by T);
panels are long frames with columns ``iso3, T, e`` (or ``u``); ``T`` is in years on a regular grid.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as _sps

# ------------------------------------------------------------------------------------------------ kernels
def _autocov(u: np.ndarray, j: int) -> float:
    """Sample autocovariance at lag ``j`` (divisor n, demeaned)."""
    u = np.asarray(u, dtype=float)
    n = len(u)
    d = u - u.mean()
    return float(np.dot(d[j:], d[: n - j]) / n) if j < n else 0.0


def long_run_variance(u: np.ndarray, L: int, kernel: str = "bartlett") -> float:
    """γ₀ + 2 Σ_{j=1}^{L} w_j γ_j with ``w_j = 1`` (uniform / Hansen–Hodrick) or ``1 − j/(L+1)``
    (Bartlett / Newey–West). ``L`` is clipped to ``n − 1``."""
    n = len(u)
    L = int(min(max(L, 0), max(n - 1, 0)))
    lrv = _autocov(u, 0)
    for j in range(1, L + 1):
        w = 1.0 if kernel == "uniform" else 1.0 - j / (L + 1)
        lrv += 2.0 * w * _autocov(u, j)
    return float(lrv)


def hansen_hodrick_se(u: np.ndarray, L: int, *, fallback: str = "bartlett") -> float:
    """Hansen–Hodrick SE of the mean of ``u`` (uniform kernel, truncation ``L``). The uniform kernel is
    not positive semi-definite: when the long-run variance comes out ≤ 0 the Bartlett estimate with
    the same ``L`` is returned instead (``fallback='bartlett'``) or NaN (``fallback='nan'``)."""
    u = np.asarray(u, dtype=float)
    n = len(u)
    if n < 2:
        return float("nan")
    lrv = long_run_variance(u, L, "uniform")
    if lrv <= 0:
        if fallback == "nan":
            return float("nan")
        lrv = long_run_variance(u, L, "bartlett")
    return math.sqrt(lrv / n)


def newey_west_se(u: np.ndarray, L: int) -> float:
    """Newey–West (Bartlett kernel, truncation ``L``) SE of the mean of ``u``. Equals statsmodels'
    ``OLS(u, 1).fit(cov_type='HAC', cov_kwds={'maxlags': L, 'use_correction': False})`` SE."""
    u = np.asarray(u, dtype=float)
    n = len(u)
    if n < 2:
        return float("nan")
    return math.sqrt(max(long_run_variance(u, L, "bartlett"), 0.0) / n)


def naive_se(e: np.ndarray) -> float:
    """``sd(e)/√n`` (ddof = 1) — reported, never the headline (PREREG §3.6 item 3)."""
    e = np.asarray(e, dtype=float)
    return float(e.std(ddof=1) / math.sqrt(len(e))) if len(e) > 1 else float("nan")


def _grid_step(T: np.ndarray) -> float:
    ts = np.unique(T)
    d = np.diff(ts)
    return float(d.min()) if len(d) else 1.0


def cluster_se(resid: pd.DataFrame) -> float:
    """Plain one-way country-cluster SE of the pooled mean of ``resid.u`` (columns ``iso3, T, u``): every
    within-country pair of rows gets weight 1 whatever their T distance, cross-country covariances are zero
    — ``sqrt(Σ_c (Σ_{i∈c} (u_i − ū))²) / n``.  This is the estimator PREREG §3.6 item 6 names ("cluster =
    country across T"); :func:`cluster_hac_se` is its kernel-truncated variant and converges to it as
    ``L → ∞``."""
    df = resid[["iso3", "T", "u"]].dropna()
    if len(df) < 2:
        return float("nan")
    d = df["u"].to_numpy(dtype=float) - df["u"].mean()
    sums = pd.Series(d).groupby(df["iso3"].to_numpy(), sort=False).sum().to_numpy()
    return math.sqrt(float((sums ** 2).sum())) / len(df)


def cluster_hac_se(resid: pd.DataFrame, L: int, h: int) -> float:
    """Within-country Bartlett-kernel SE of the pooled mean of ``resid.u`` (columns ``iso3, T, u``).

    Within a country, pairs of rows (s, t) are weighted by the Bartlett kernel in T-steps,
    ``w = 1 − ℓ/(L+1)`` for ``ℓ = |T_s − T_t| / step ≤ L`` (``step`` = the grid spacing, inferred);
    across countries the covariance is zero (the cluster). Summing the kernel-weighted cross-products
    over countries and dividing by n² is the Driscoll–Kraay-style estimator for a mean. ``h`` documents
    the overlap: windows of length ``h`` on a grid of ``step`` overlap for ``h/step − 1`` steps, which
    is the natural ``L``; when ``L < 0`` that default is used.  NOTE: with ``L = 1`` same-country pairs
    two or more grid steps apart get weight 0, so this is NOT the plain cluster estimator of PREREG §3.6
    item 6 — that is :func:`cluster_se`; both are reported."""
    df = resid[["iso3", "T", "u"]].dropna()
    if len(df) < 2:
        return float("nan")
    n = len(df)
    step = _grid_step(df["T"].to_numpy(dtype=float))
    if L < 0:
        L = int(round(h / step)) - 1
    mu = df["u"].mean()
    total = 0.0
    for _, g in df.groupby("iso3", sort=False):
        d = g["u"].to_numpy(dtype=float) - mu
        t = g["T"].to_numpy(dtype=float)
        lag = np.abs(t[:, None] - t[None, :]) / step
        w = np.clip(1.0 - lag / (L + 1), 0.0, None)
        total += float(d @ w @ d)
    return math.sqrt(max(total, 0.0)) / n


# ------------------------------------------------------------------------------------------------ bootstrap
def _group_sums(values: pd.DataFrame, key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    g = values.groupby(key, sort=True)["e"].agg(["sum", "count"])
    return g.index.to_numpy(), g["sum"].to_numpy(dtype=float), g["count"].to_numpy(dtype=float)


def block_bootstrap_ci(values: pd.DataFrame, *, B: int = 5000, block_len: int, seed: int = 0,
                       level: float = 0.95) -> dict:
    """Percentile CIs of the pooled mean of ``values.e`` (columns ``iso3, T, e``) under two schemes:

    ``country_cluster`` — resample countries with replacement, keeping all their (T, row) entries;
    ``block_T`` — circular block bootstrap over the ordered T grid with ``block_len`` consecutive T's
    per block (h/5 in PREREG: 2 for h = 10, 4 for h = 20); ``headline`` — the **wider** of the two.
    Deterministic given ``seed`` (``numpy.random.default_rng``). The resampled statistic is the pooled
    mean (Σ sums / Σ counts), so unequal rows per country or per T are handled exactly.

    ``block_T_degenerate`` is True when ``block_len >= number of distinct T's``: every circular block is then
    the whole series, every resample reproduces the observed mean and the T-block "interval" collapses to a
    point (h = 20 rows have three T's and block length 4).  The flag is reported; the country-cluster CI is
    the only informative scheme in that case and the headline rule (wider CI) selects it automatically."""
    df = values[["iso3", "T", "e"]].dropna()
    rng = np.random.default_rng(seed)
    out: dict = {"mean": float(df["e"].mean()), "B": int(B), "seed": int(seed), "level": level, "n": int(len(df))}
    lo_q, hi_q = 100 * (1 - level) / 2, 100 * (1 + level) / 2
    # (a) country cluster
    _, cs, cc = _group_sums(df, "iso3")
    C = len(cs)
    idx = rng.integers(0, C, size=(B, C))
    means_c = cs[idx].sum(1) / cc[idx].sum(1)
    out["country_cluster"] = (float(np.percentile(means_c, lo_q)), float(np.percentile(means_c, hi_q)))
    # (b) circular blocks over T
    ts, tsum, tcnt = _group_sums(df, "T")
    m = len(ts)
    bl = int(max(1, min(block_len, m)))
    n_blocks = math.ceil(m / bl)
    starts = rng.integers(0, m, size=(B, n_blocks))
    pos = (starts[:, :, None] + np.arange(bl)[None, None, :]).reshape(B, -1)[:, :m] % m
    means_t = tsum[pos].sum(1) / tcnt[pos].sum(1)
    out["block_T"] = (float(np.percentile(means_t, lo_q)), float(np.percentile(means_t, hi_q)))
    out["block_T_degenerate"] = bool(block_len >= m)
    out["n_T"], out["block_len"] = int(m), int(block_len)
    wc = out["country_cluster"][1] - out["country_cluster"][0]
    wt = out["block_T"][1] - out["block_T"][0]
    out["headline_scheme"] = "block_T" if wt > wc else "country_cluster"
    out["headline"] = out[out["headline_scheme"]]
    out["excludes_zero"] = bool(out["headline"][0] * out["headline"][1] > 0)
    out["se_country_cluster"], out["se_block_T"] = float(means_c.std(ddof=1)), float(means_t.std(ddof=1))
    return out


def n_eff(rows: pd.DataFrame, h: int, T0: int = 1990) -> int:
    """Distinct ``(iso3, floor((T − T0)/h))`` pairs — the number of non-overlapping country-blocks
    (PREREG §3.6 item 8). ``rows`` needs columns ``iso3`` and ``T``."""
    if len(rows) == 0:
        return 0
    blocks = np.floor((rows["T"].to_numpy(dtype=float) - T0) / h).astype(int)
    return int(pd.MultiIndex.from_arrays([rows["iso3"].to_numpy(), blocks]).nunique())


# ------------------------------------------------------------------------------------------------ OLS
def _ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).ravel()
    if X.ndim == 1:
        X = X[:, None]
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((u ** 2).sum()) / tss if tss > 0 else float("nan")
    return beta, u, XtX_inv, r2


def _pvals(beta: np.ndarray, se: np.ndarray) -> np.ndarray:
    z = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    return 2.0 * _sps.norm.sf(np.abs(z))


def driscoll_kraay_ols(X, y, t_index, bandwidth: int) -> dict:
    """Pooled OLS with Driscoll–Kraay (1998) SE: scores ``x_i u_i`` are summed per period into
    ``h_t``, the long-run covariance of the ``h_t`` series uses the Bartlett kernel with truncation
    ``bandwidth`` (lags in periods of the sorted unique ``t_index``), and
    ``V = (X'X)⁻¹ S (X'X)⁻¹``. Returns ``{'beta', 'se', 'p', 'r2', 'n', 'n_periods'}`` (two-sided
    normal p-values). No small-sample correction (the cross-check in the tests uses none either)."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    beta, u, XtX_inv, r2 = _ols(X, y)
    t = np.asarray(t_index)
    periods, inv = np.unique(t, return_inverse=True)
    scores = X * u[:, None]
    H = np.zeros((len(periods), X.shape[1]))
    np.add.at(H, inv, scores)
    S = H.T @ H
    L = int(min(bandwidth, len(periods) - 1))
    for j in range(1, L + 1):
        w = 1.0 - j / (L + 1)
        G = H[j:].T @ H[:-j]
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    return {"beta": beta, "se": se, "p": _pvals(beta, se), "r2": r2, "n": int(len(u)), "n_periods": int(len(periods)),
            "bandwidth": L}


def _cluster_meat(scores: np.ndarray, groups: np.ndarray) -> np.ndarray:
    _, inv = np.unique(groups, return_inverse=True)
    G = np.zeros((inv.max() + 1, scores.shape[1]))
    np.add.at(G, inv, scores)
    return G.T @ G


def cluster_ols(X, y, groups) -> dict:
    """Pooled OLS with one-way cluster-robust SE (no finite-sample correction; equals statsmodels
    ``cov_type='cluster'`` with ``use_correction=False, df_correction=False``)."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    beta, u, XtX_inv, r2 = _ols(X, y)
    V = XtX_inv @ _cluster_meat(X * u[:, None], np.asarray(groups)) @ XtX_inv
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    return {"beta": beta, "se": se, "p": _pvals(beta, se), "r2": r2, "n": int(len(u))}


def twoway_cluster_ols(X, y, g1, g2) -> dict:
    """Pooled OLS with two-way (Cameron–Gelbach–Miller) cluster SE: ``V = V_g1 + V_g2 − V_{g1∩g2}``,
    no finite-sample correction. Returns ``{'beta', 'se', 'p', 'r2', 'n', 'n_g1', 'n_g2'}``."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    beta, u, XtX_inv, r2 = _ols(X, y)
    scores = X * u[:, None]
    g1, g2 = np.asarray(g1), np.asarray(g2)
    g12 = np.array([f"{a}|{b}" for a, b in zip(g1, g2)])
    meat = _cluster_meat(scores, g1) + _cluster_meat(scores, g2) - _cluster_meat(scores, g12)
    V = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    return {"beta": beta, "se": se, "p": _pvals(beta, se), "r2": r2, "n": int(len(u)),
            "n_g1": int(len(np.unique(g1))), "n_g2": int(len(np.unique(g2)))}


# ------------------------------------------------------------------------------------------------ misc tests
def sign_test(wins: int, n: int) -> float:
    """Two-sided exact binomial p-value for ``wins`` successes in ``n`` trials at p = ½
    (``min(1, 2·min(P[X ≤ w], P[X ≥ w]))``)."""
    if n <= 0:
        return float("nan")
    lo = _sps.binom.cdf(wins, n, 0.5)
    hi = _sps.binom.sf(wins - 1, n, 0.5)
    return float(min(1.0, 2.0 * min(lo, hi)))


def one_sided_p(null_draws: np.ndarray, observed: float) -> float:
    """PREREG §3.7 [PSD]: ``(#draws ≥ observed + 1) / (B + 1)``."""
    d = np.asarray(null_draws, dtype=float)
    return float((np.sum(d >= observed) + 1) / (len(d) + 1))


def z_p(mu: float, se: float) -> float:
    """Two-sided normal p-value of ``mu / se`` (NaN when ``se`` is not positive)."""
    if not (se > 0):
        return float("nan")
    return float(2.0 * _sps.norm.sf(abs(mu / se)))


def per_T_means(values: pd.DataFrame, col: str = "e") -> pd.Series:
    """The T-aggregated residual series (mean per T, ordered by T) HH/NW are computed on."""
    return values.groupby("T", sort=True)[col].mean()


__all__ = ["hansen_hodrick_se", "newey_west_se", "naive_se", "cluster_se", "cluster_hac_se", "block_bootstrap_ci", "n_eff",
           "driscoll_kraay_ols", "cluster_ols", "twoway_cluster_ols", "sign_test", "one_sided_p", "z_p",
           "per_T_means", "long_run_variance"]
