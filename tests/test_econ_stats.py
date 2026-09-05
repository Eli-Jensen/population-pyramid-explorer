"""Standard errors for overlapping-window panels (PREREG §3.6, §9): coverage on simulated panels,
agreement with statsmodels where it is importable, N_eff on a hand-built design, the sign test."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.econ import stats as S

try:  # optional cross-check only
    import statsmodels.api as sm
except Exception:  # noqa: BLE001
    sm = None


# ------------------------------------------------------------------------------------------------ simulated panels
def _overlapping_panel(rng: np.random.Generator, C: int, n_T: int, h: int, step: int) -> tuple[np.ndarray, pd.DataFrame]:
    """C independent countries, T grid of n_T points spaced ``step`` years, each residual the sum of the
    ``h`` annual shocks inside its window (MA(h/step − 1) across T, variance 1)."""
    years = n_T * step + h
    eps = rng.normal(size=(C, years))
    e = np.stack([eps[:, k * step:k * step + h].sum(1) for k in range(n_T)], 1) / math.sqrt(h)
    T = np.arange(n_T) * step + 1990
    df = pd.DataFrame({"iso3": np.repeat([f"C{i:03d}" for i in range(C)], n_T), "T": np.tile(T, C), "e": e.ravel()})
    return e, df


def _coverage(h: int, *, C: int = 20, n_T: int = 100, step: int = 5, nsim: int = 2000, B: int = 200, seed: int = 20260904) -> dict:
    rng = np.random.default_rng(seed)
    hs = h // step
    hits = {k: 0 for k in ("naive", "hh", "nw2", "nw4", "cluster", "boot")}
    for s in range(nsim):
        e, df = _overlapping_panel(rng, C, n_T, h, step)
        mu, ubar = e.mean(), e.mean(0)          # true mean 0
        hits["naive"] += abs(mu) < 1.96 * S.naive_se(e.ravel())
        hits["hh"] += abs(mu) < 1.96 * S.hansen_hodrick_se(ubar, hs - 1)
        hits["nw2"] += abs(mu) < 1.96 * S.newey_west_se(ubar, 2)
        hits["nw4"] += abs(mu) < 1.96 * S.newey_west_se(ubar, 4)
        hits["cluster"] += abs(mu) < 1.96 * S.cluster_hac_se(df.rename(columns={"e": "u"}), hs - 1, h)
        ci = S.block_bootstrap_ci(df, B=B, block_len=hs, seed=s)
        hits["boot"] += ci["headline"][0] < 0 < ci["headline"][1]
    return {k: v / nsim for k, v in hits.items()}


@pytest.mark.parametrize("h", [10, 20])
def test_coverage_corrections_bite(h):
    """95 % nominal: HH (L = h/5 − 1), NW (L = 2, 4), the headline block bootstrap and the country-cluster
    HAC all cover in [.90, .98] on 2,000 simulated overlapping panels while the naive SE does not."""
    cov = _coverage(h)
    assert cov["naive"] < 0.90, cov
    for k in ("hh", "nw4", "boot", "cluster"):
        assert 0.90 <= cov[k] <= 0.98, (k, cov)
    assert cov["nw2"] > cov["naive"] + 0.03, cov     # L = 2 corrects too, less fully for h = 20 (MA(3) in T-steps)


def test_naive_se_and_kernels_on_known_series():
    u = np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
    assert math.isclose(S.naive_se(u), u.std(ddof=1) / math.sqrt(6))
    # perfectly alternating: gamma_1 = -gamma_0 (approx) -> uniform LRV goes <= 0 -> Bartlett fallback / NaN
    assert math.isnan(S.hansen_hodrick_se(u, 1, fallback="nan"))
    assert S.hansen_hodrick_se(u, 1) == S.newey_west_se(u, 1)
    # white noise: L = 0 equals the naive SE with divisor n
    w = np.random.default_rng(0).normal(size=50)
    assert math.isclose(S.newey_west_se(w, 0), w.std(ddof=0) / math.sqrt(50))
    assert math.isclose(S.hansen_hodrick_se(w, 0), S.newey_west_se(w, 0))


@pytest.mark.skipif(sm is None, reason="statsmodels not importable")
def test_agrees_with_statsmodels_to_1e6():
    rng = np.random.default_rng(1)
    u = rng.normal(size=40).cumsum() * 0.1 + rng.normal(size=40)
    for L in (1, 2, 4):
        fit = sm.OLS(u, np.ones((40, 1))).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False})
        assert abs(S.newey_west_se(u, L) - float(np.asarray(fit.bse)[0])) < 1e-6
    n = 300
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    g1, g2, t = rng.integers(0, 20, n), rng.integers(0, 15, n), rng.integers(0, 30, n)
    y = X @ [1.0, 2.0] + rng.normal(size=n) + 0.1 * g1
    fit = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": g1, "use_correction": False, "df_correction": False})
    assert np.allclose(S.cluster_ols(X, y, g1)["se"], np.asarray(fit.bse), atol=1e-6)
    fit = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": np.column_stack([g1, g2]), "use_correction": False, "df_correction": False})
    assert np.allclose(S.twoway_cluster_ols(X, y, g1, g2)["se"], np.asarray(fit.bse), atol=1e-6)
    o = np.argsort(t, kind="stable")
    fit = sm.OLS(y[o], X[o]).fit(cov_type="nw-groupsum", cov_kwds={"time": t[o], "maxlags": 3, "use_correction": False})
    dk = S.driscoll_kraay_ols(X[o], y[o], t[o], 3)
    assert np.allclose(dk["se"], np.asarray(fit.bse), atol=1e-6)
    assert np.allclose(dk["beta"], np.asarray(fit.params), atol=1e-8) and abs(dk["r2"] - fit.rsquared) < 1e-8


def test_cluster_hac_reduces_to_cluster_when_L_is_zero():
    rng = np.random.default_rng(2)
    e, df = _overlapping_panel(rng, 12, 6, 10, 5)
    u = df.rename(columns={"e": "u"})
    d = u["u"] - u["u"].mean()
    # L = 0: only same-row terms survive -> the heteroskedasticity-robust SE of the mean, sqrt(sum d_i^2)/n
    assert math.isclose(S.cluster_hac_se(u, 0, 10), math.sqrt((d ** 2).sum()) / len(u))
    # L >= max lag (5 T-steps here): every within-country pair gets weight ~1 only as L -> inf; with the
    # Bartlett kernel the plain cluster sum is the limit, so a huge L must reproduce it
    dc = u.assign(d=d).groupby("iso3")["d"].sum()
    assert math.isclose(S.cluster_hac_se(u, 10_000_000, 10), math.sqrt((dc ** 2).sum()) / len(u), rel_tol=1e-5)
    # L = -1 -> default L = h/step - 1 = 1, which adds adjacent-T cross terms (differs from L = 0)
    assert S.cluster_hac_se(u, -1, 10) != S.cluster_hac_se(u, 0, 10)


# ------------------------------------------------------------------------------------------------ bootstrap
def test_block_bootstrap_is_deterministic_and_headline_is_wider():
    rng = np.random.default_rng(3)
    _, df = _overlapping_panel(rng, 15, 6, 10, 5)
    df["e"] += 0.4
    a = S.block_bootstrap_ci(df, B=500, block_len=2, seed=20260904)
    b = S.block_bootstrap_ci(df, B=500, block_len=2, seed=20260904)
    assert a["country_cluster"] == b["country_cluster"] and a["block_T"] == b["block_T"]
    wc = a["country_cluster"][1] - a["country_cluster"][0]
    wt = a["block_T"][1] - a["block_T"][0]
    assert a["headline"] == (a["block_T"] if wt > wc else a["country_cluster"])
    assert a["headline"][0] <= a["mean"] <= a["headline"][1]
    assert a["excludes_zero"] == (a["headline"][0] * a["headline"][1] > 0)


def test_block_bootstrap_handles_unequal_rows_per_T():
    df = pd.DataFrame({"iso3": ["A", "A", "B", "C", "C", "C"], "T": [1990, 1995, 1990, 1990, 1995, 2000], "e": [1, 2, 3, 4, 5, 6.0]})
    out = S.block_bootstrap_ci(df, B=50, block_len=1, seed=0)
    assert out["n"] == 6 and math.isclose(out["mean"], 3.5)
    assert 1.0 <= out["block_T"][0] <= out["block_T"][1] <= 6.0


# ------------------------------------------------------------------------------------------------ N_eff, sign test
def test_n_eff_on_hand_built_design():
    rows = pd.DataFrame({"iso3": ["VNM", "VNM", "VNM", "IND", "IND", "BGD"], "T": [1990, 1995, 2000, 2010, 2015, 2015]})
    # h = 10 blocks: 1990,1995 -> 0; 2000 -> 1; 2010,2015 -> 2  => VNM {0,1}, IND {2}, BGD {2} = 4
    assert S.n_eff(rows, 10) == 4
    # h = 20 blocks: 1990..2009 -> 0; 2010.. -> 1 => VNM {0}, IND {1}, BGD {1} = 3
    assert S.n_eff(rows, 20) == 3
    assert S.n_eff(rows.iloc[0:0], 10) == 0
    assert S.n_eff(rows, 10) <= len(rows)


def test_sign_test_exact():
    assert math.isclose(S.sign_test(10, 10), 2 * 0.5 ** 10)
    assert math.isclose(S.sign_test(0, 10), 2 * 0.5 ** 10)
    assert S.sign_test(5, 10) == 1.0
    assert math.isclose(S.sign_test(7, 10), 0.34375)
    assert math.isnan(S.sign_test(0, 0))


def test_one_sided_p_and_z_p():
    draws = np.arange(100) / 100
    assert math.isclose(S.one_sided_p(draws, 0.95), (5 + 1) / 101)
    assert math.isclose(S.one_sided_p(draws, 2.0), 1 / 101)
    assert math.isclose(S.z_p(1.96, 1.0), 0.05, abs_tol=1e-3)
    assert math.isnan(S.z_p(1.0, 0.0))


def test_per_T_means_orders_by_T():
    df = pd.DataFrame({"T": [2000, 1990, 2000, 1990], "e": [2.0, 1.0, 4.0, 3.0]})
    m = S.per_T_means(df)
    assert list(m.index) == [1990, 2000] and list(m) == [2.0, 3.0]


def test_plain_cluster_se_is_the_large_L_limit_of_the_kernel_version():
    """PREREG §3.6 item 6 names the plain one-way cluster SE; cluster_hac_se(L → ∞) must reproduce it and the
    L = 1 kernel version must differ whenever a country has rows ≥ 2 grid steps apart."""
    rng = np.random.default_rng(5)
    _, df = _overlapping_panel(rng, 10, 6, 10, 5)
    u = df.rename(columns={"e": "u"})
    d = u["u"] - u["u"].mean()
    plain = math.sqrt((d.groupby(u["iso3"]).sum() ** 2).sum()) / len(u)
    assert math.isclose(S.cluster_se(u), plain)
    assert math.isclose(S.cluster_hac_se(u, 10_000_000, 10), S.cluster_se(u), rel_tol=1e-6)
    assert S.cluster_hac_se(u, 1, 10) != S.cluster_se(u)
    assert math.isnan(S.cluster_se(u.head(1)))


def test_block_bootstrap_flags_degenerate_T_blocks():
    """Three T's with block length 4 (h = 20): every circular block is the whole series, the T-block CI is a point."""
    rng = np.random.default_rng(6)
    _, df = _overlapping_panel(rng, 10, 3, 20, 5)
    out = S.block_bootstrap_ci(df, B=200, block_len=4, seed=1)
    assert out["block_T_degenerate"] and out["n_T"] == 3 and out["block_len"] == 4
    assert out["block_T"][0] == pytest.approx(out["mean"]) and out["block_T"][1] == pytest.approx(out["mean"])
    assert out["headline_scheme"] == "country_cluster"
    ok = S.block_bootstrap_ci(df, B=200, block_len=2, seed=1)
    assert not ok["block_T_degenerate"] and ok["block_T"][1] > ok["block_T"][0]
