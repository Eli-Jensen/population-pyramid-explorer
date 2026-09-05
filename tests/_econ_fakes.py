"""Stand-ins for the E1 interfaces (``econ.stats``, ``econ.etf``) used by the E2 unit tests.

The statistics here are plain, small numpy implementations with the SAME signatures as ``econ.stats`` so the
experiment modules can be exercised without the real module; they are not the shipped estimators.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm


def _autocov(u: np.ndarray, lag: int) -> float:
    u = u - u.mean()
    n = len(u)
    return float((u[lag:] * u[:n - lag]).sum() / n)


def hansen_hodrick_se(u, L: int) -> float:
    u = np.asarray(u, dtype=np.float64)
    n = len(u)
    v = _autocov(u, 0) + 2 * sum(_autocov(u, l) for l in range(1, min(L, n - 1) + 1))
    return math.sqrt(max(v, 1e-18) / n)


def newey_west_se(u, L: int) -> float:
    u = np.asarray(u, dtype=np.float64)
    n = len(u)
    v = _autocov(u, 0) + 2 * sum((1 - l / (L + 1)) * _autocov(u, l) for l in range(1, min(L, n - 1) + 1))
    return math.sqrt(max(v, 1e-18) / n)


def cluster_se(resid: pd.DataFrame) -> float:
    d = resid["u"] - resid["u"].mean()
    sums = d.groupby(resid["iso3"]).sum().to_numpy()
    return math.sqrt(max(float((sums ** 2).sum()), 1e-18)) / len(resid)


def cluster_hac_se(resid: pd.DataFrame, L: int, h: int) -> float:
    d = resid.copy()
    d["u"] = d["u"] - d["u"].mean()
    n = len(d)
    tot = 0.0
    for _, g in d.groupby("iso3"):
        g = g.sort_values("T")
        u = g["u"].to_numpy()
        tot += (u ** 2).sum()
        for l in range(1, min(L, len(u) - 1) + 1):
            tot += 2 * (1 - l / (L + 1)) * (u[l:] * u[:-l]).sum()
    return math.sqrt(max(tot, 1e-18)) / n


def block_bootstrap_ci(values: pd.DataFrame, *, B=5000, block_len: int, seed=0, level=0.95) -> dict:
    rng = np.random.default_rng(seed)
    a = (1 - level) / 2
    e = values["e"].to_numpy(dtype=np.float64)
    groups = values.groupby("iso3").indices
    ids = list(groups)
    idx = rng.integers(0, len(ids), (B, len(ids)))
    sums = np.array([e[groups[c]].sum() for c in ids])
    cnts = np.array([len(groups[c]) for c in ids])
    mu_c = sums[idx].sum(1) / cnts[idx].sum(1)
    Ts = sorted(values["T"].unique())
    tg = values.groupby("T").indices
    tsum = np.array([e[tg[t]].sum() for t in Ts])
    tcnt = np.array([len(tg[t]) for t in Ts])
    nT = len(Ts)
    nb = math.ceil(nT / block_len)
    starts = rng.integers(0, nT, (B, nb))
    pos = (starts[:, :, None] + np.arange(block_len)[None, None, :]).reshape(B, -1)[:, :nT] % nT
    mu_t = tsum[pos].sum(1) / tcnt[pos].sum(1)
    cc = (float(np.quantile(mu_c, a)), float(np.quantile(mu_c, 1 - a)))
    bt = (float(np.quantile(mu_t, a)), float(np.quantile(mu_t, 1 - a)))
    head = cc if cc[1] - cc[0] >= bt[1] - bt[0] else bt
    return {"country_cluster": cc, "block_T": bt, "headline": head, "block_T_degenerate": block_len >= nT}


def n_eff(picks: pd.DataFrame, h: int, T0=1990) -> int:
    blocks = ((picks["T"].to_numpy() - T0) // h).astype(int)
    return int(len(set(zip(picks["iso3"], blocks))))


def _ols(X, y):
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return beta, resid, XtX_inv, r2


def driscoll_kraay_ols(X, y, t_index, bandwidth: int) -> dict:
    X = np.asarray(X, dtype=np.float64)
    beta, resid, XtX_inv, r2 = _ols(X, y)
    t = np.asarray(t_index)
    Ts = np.unique(t)
    H = np.stack([(X[t == tt] * resid[t == tt][:, None]).sum(0) for tt in Ts])   # [T, p]
    S = H.T @ H
    for l in range(1, min(bandwidth, len(Ts) - 1) + 1):
        w = 1 - l / (bandwidth + 1)
        G = H[l:].T @ H[:-l]
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 1e-300))
    p = 2 * (1 - norm.cdf(np.abs(beta) / se))
    return {"beta": beta, "se": se, "p": p, "r2": float(r2)}


def _cluster_V(X, resid, g, XtX_inv):
    S = np.zeros((X.shape[1], X.shape[1]))
    for gg in np.unique(g):
        s = (X[g == gg] * resid[g == gg][:, None]).sum(0)
        S += np.outer(s, s)
    return XtX_inv @ S @ XtX_inv


def twoway_cluster_ols(X, y, g1, g2) -> dict:
    X = np.asarray(X, dtype=np.float64)
    beta, resid, XtX_inv, r2 = _ols(X, y)
    g1 = np.asarray(g1); g2 = np.asarray(g2)
    g12 = np.array([f"{a}|{b}" for a, b in zip(g1, g2)])
    V = _cluster_V(X, resid, g1, XtX_inv) + _cluster_V(X, resid, g2, XtX_inv) - _cluster_V(X, resid, g12, XtX_inv)
    se = np.sqrt(np.maximum(np.diag(V), 1e-300))
    p = 2 * (1 - norm.cdf(np.abs(beta) / se))
    return {"beta": beta, "se": se, "p": p, "r2": float(r2)}


def sign_test(wins: int, n: int) -> float:
    return float(binomtest(wins, n, 0.5).pvalue)


class FakeReturns:
    """A ``lookalike.ReturnsProvider`` over a hand-made table: ``rows[T] = DataFrame(iso3, ticker, status, r)``,
    ``vt[T]``, ``ew[T]``, ``refs[T]``; the ``universe`` frame lists which iso3 have a fund at all."""

    def __init__(self, rows: dict, vt: dict, ew: dict | None = None, refs: dict | None = None, universe_iso3=()):
        self.rows, self._vt, self._ew, self._refs = rows, vt, ew or {}, refs or {}
        self.universe = pd.DataFrame({"iso3": list(universe_iso3), "role": "single_country"})

    def etf_table(self, T):
        t = self.rows[T].copy()
        if "max_dd" not in t:
            t["max_dd"] = np.nan
        return t

    def vt(self, T):
        return {"r_ann": self._vt[T], "benchmark": "vt" if T >= 2010 else "vt_proxy", "legs": []}

    def ew(self, T):
        return {"r_ann": self._ew.get(T, float(np.nanmean(self.rows[T]["r"]))), "n": int(self.rows[T]["r"].notna().sum())}

    def refs(self, T):
        return self._refs.get(T, {"SPY": self._vt[T] + 0.01, "EFA": self._vt[T] - 0.01, "EEM": self._vt[T]})
