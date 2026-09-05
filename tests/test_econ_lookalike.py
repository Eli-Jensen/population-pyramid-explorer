"""Experiment 1 (lookalike.py) on a planted-prototype synthetic corpus (PREREG §9), with E1 stand-ins.

Signal planted: every country-year shape is a mixture of its own base pyramid and one planted prototype;
10-year growth is a decreasing function of the blend distance to that prototype plus noise.  Under the planted
signal Query B must recover it (hit rate > .8, N1 p < .01); with growth independent of shape the one-sided N1 p
over many seeds must be ~uniform (KS).  Also: prototype dedupe rule, income caliper, N_eff, the picks table,
the returns path with a fake provider, and the prediction evaluation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import kstest

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.metrics import distances, fit_sigma
from pyramid_explorer.paths import N_YEARS, YEARS
from tests import _econ_fakes as fakes

N_C = 30
IDS = ["CHN"] + [f"C{i:02d}" for i in range(1, N_C)]


def synth_world(seed: int = 0, signal: bool = True, n_c: int = N_C):
    """(Corpus, GrowthData, proto_shape): entity-major corpus of n_c countries × 151 years."""
    rng = np.random.default_rng(seed)
    ids = IDS[:n_c]
    proto = rng.dirichlet(np.ones(42) * 4)
    rows, keys = [], []
    W = np.empty((n_c, N_YEARS))
    for e, eid in enumerate(ids):
        base = rng.dirichlet(np.ones(42) * 4)
        w0, slope = rng.uniform(0.0, 0.9), rng.normal(0, 0.003)
        for t in range(N_YEARS):
            w = float(np.clip(w0 + slope * t + rng.normal(0, 0.01), 0, 1))
            W[e, t] = w
            s = (1 - w) * base + w * proto
            s = np.clip(s + rng.normal(0, 0.0005, 42), 1e-5, None)
            s /= s.sum()
            rows.append(s)
            keys.append((e * N_YEARS + t, eid, e + 1, 1950 + t, "country", 5000.0 + 10 * e))
    X = np.array(rows)
    keys = pd.DataFrame(keys, columns=["row", "id", "locid", "year", "type", "pop_total"])
    ents = [{"id": i, "type": "country", "sdg_region_locid": 1830 + (n % 4), "name": i} for n, i in enumerate(ids)]
    sigma = fit_sigma(X, keys, ents, n_pairs=800)
    d = distances("blend", proto, X, sigma=sigma).astype(np.float64)
    # growth in log points/yr: strong decreasing function of the distance to the prototype (or pure noise)
    g_yearly = (0.05 - 0.03 * d) if signal else np.zeros(len(X))
    g_yearly = g_yearly + rng.normal(0, 0.004, len(X))
    win = []
    for h in (10, 20, 8):
        for t in range(1950, 2101 - h):
            if h == 8 and t != 2015:
                continue
            for e, eid in enumerate(ids):
                r0 = e * N_YEARS + (t - 1950)
                win.append((eid, t, h, float(g_yearly[r0]), "pwt", h == 8))
    windows = pd.DataFrame(win, columns=["iso3", "t", "h", "g", "src", "partial"])
    lvl = pd.DataFrame([(eid, y, float(np.exp(rng.normal(8.5 + 0.02 * e, 0.1) + 0.02 * (y - 1950)))) for e, eid in enumerate(ids) for y in YEARS],
                       columns=["iso3", "year", "y_level"])
    return lk.Corpus(X, keys, ents, sigma), lk.GrowthData(windows, lvl), proto


@pytest.fixture(scope="module")
def world():
    return synth_world(seed=0, signal=True)


def _run(corpus, gd, **kw):
    kw.setdefault("B", 1500)
    kw.setdefault("growth_T", {10: (1990, 1995, 2000, 2005, 2010)})
    kw.setdefault("queries", ("B", "B3", "N4"))
    kw.setdefault("ks", (10,))
    return lk.run(corpus, gd, stats=fakes, **kw)


def test_planted_prototype_is_recovered(world):
    corpus, gd, _ = world
    res, table = _run(corpus, gd)
    row = res["rows"]["B|10|10|growth"]
    assert row["stats"]["hit_rate"] > 0.8
    assert row["stats"]["mean_excess"] > 0
    assert row["nulls"]["N1"]["p_mean_excess"] < 0.01
    assert row["stats"]["n"] == 50 and row["stats"]["n_T"] == 5
    assert 0 < row["stats"]["n_eff"] <= 50
    lo, hi = row["stats"]["ci_headline"]
    assert lo <= row["stats"]["mean_excess"] <= hi
    # the wider of the two CIs is the headline
    w = lambda c: c[1] - c[0]
    assert w(row["stats"]["ci_headline"]) == pytest.approx(max(w(row["stats"]["ci_country_cluster"]), w(row["stats"]["ci_block_T"])))
    # candidate / prototype / pick rows all land in the table with the pre-registered columns
    assert set(lk.PICK_COLUMNS) <= set(table.columns)
    assert set(table["role"]) == {"candidate", "prototype", "pick"}
    picks = table[(table["role"] == "pick") & (table["query"] == "B")]
    assert len(picks) == 50 and picks.groupby("T").size().eq(10).all()
    assert (table.loc[table["role"] == "candidate", "query"] == "candidates").all()


def test_null_p_is_uniform_without_signal():
    ps = []
    for seed in range(50):
        corpus, gd, _ = synth_world(seed=seed, signal=False, n_c=18)
        res, _ = lk.run(corpus, gd, stats=fakes, B=300, growth_T={10: (1990, 2000, 2010)}, queries=("B",), ks=(5,))
        ps.append(res["rows"]["B|5|10|growth"]["nulls"]["N1"]["p_mean_excess"])
    ps = np.array(ps)
    assert kstest(ps, "uniform").pvalue > 0.01
    assert (ps < 0.05).mean() < 0.25


def test_prototype_set_dedupe_rule(world):
    corpus, gd, proto = world
    P = lk.prototype_set(corpus, gd, 2000)
    assert not P.empty
    assert (P["year"] + 10 <= 2000).all()
    assert P.groupby("iso3").size().max() <= lk.PROTO_MAX_PER_COUNTRY
    for _, g in P.groupby("iso3"):
        ys = np.sort(g["year"].to_numpy())
        assert (np.diff(ys) >= lk.PROTO_MIN_GAP).all()
    # top decile: every kept window is above the decile cut of all windows ending <= T
    w = gd.windows10_ending_by(2000)
    assert P["g"].min() >= np.quantile(w["g"], 0.9) - 1e-12
    # prototypes lie close to the planted shape (they are the fast growers)
    d = distances("blend", proto, corpus.X[P["row"].to_numpy()], sigma=corpus.sigma)
    d_all = distances("blend", proto, corpus.X[corpus.rows(corpus.country_ids(1990), 1990)], sigma=corpus.sigma)
    assert np.median(d) < np.median(d_all)


def test_min_distances_softmin_and_ties():
    D = np.array([[1.0, 3.0, 0.5], [2.0, 1.0, 0.5], [5.0, 2.0, 9.0]])
    md = lk.min_distances(D)
    assert md["D"].tolist() == [1.0, 1.0, 0.5] and md["D2"].tolist() == [2.0, 2.0, 0.5]
    assert (md["soft"] <= md["D"] + 1e-12).all()          # soft-min never exceeds the min
    empty = lk.min_distances(np.zeros((0, 3)))
    assert np.isnan(empty["D"]).all()


def test_income_caliper_respected():
    rng = np.random.default_rng(1)
    lny = np.concatenate([np.linspace(6, 7, 20), np.linspace(9, 10, 20)])      # two well-separated income bands
    e = rng.normal(0, 1, 40)
    is_pick = np.zeros(40, bool); is_pick[[0, 1, 2, 3, 4]] = True               # all lookalikes in the poor band
    n2 = lk.null_N2({2000: {"e": e, "lny": lny, "is_pick": is_pick}}, B=200, seed=0)
    assert n2["diag"]["n_caliper_matched"] == 5 and n2["diag"]["n_decile_fallback"] == 0
    assert n2["diag"]["max_abs_gap_caliper"] <= lk.CALIPER
    # the null mean is the poor band's non-lookalike mean, not the pooled mean
    poor = e[5:20]
    assert abs(np.nanmean(n2["mu"]) - poor.mean() * 100) < 0.6 * np.std(poor) * 100
    # fallback path: an isolated lookalike with no caliper neighbour draws from its decile
    lny2 = lny.copy(); lny2[0] = 8.0
    n2b = lk.null_N2({2000: {"e": e, "lny": lny2, "is_pick": is_pick}}, B=50, seed=0)
    assert n2b["diag"]["n_decile_fallback"] + n2b["diag"]["n_unmatched"] >= 1


def test_null_p_definition():
    assert lk.null_p(np.array([0.1, 0.2, 0.3]), 0.25) == pytest.approx(2 / 4)
    assert lk.null_p(np.array([0.1, 0.2, 0.3]), 1.0) == pytest.approx(1 / 4)
    assert np.isnan(lk.null_p(np.array([]), 0.1))


def test_partial_2015_window_uses_h8_then_h7():
    win = pd.DataFrame([("A", 2015, 8, 0.02, "pwt"), ("B", 2015, 7, 0.01, "maddison"), ("A", 2015, 10, 0.5, "pwt")],
                       columns=["iso3", "t", "h", "g", "src"])
    panel = pd.DataFrame({"iso3": ["A", "B"], "year": [2015, 2015], "y_level": [1.0, 2.0]})
    calls = {}

    def gw(p, h):
        calls[h] = True
        return win[win["h"] == h].copy()

    gd = lk.GrowthData.from_panel(panel.assign(y_growth=1.0), gw)
    assert set(calls) == {10, 20, 8, 7}
    g = gd.g(2015, 10)
    assert g.set_index("iso3")["h"].to_dict() == {"A": 8, "B": 7} and g["partial"].all()


def test_returns_path_with_fake_provider(world):
    corpus, gd, _ = world
    ids = IDS
    rng = np.random.default_rng(3)
    rows, vt = {}, {}
    for T in (2000, 2005, 2010, 2015):
        inv = ids[: 6 if T <= 2005 else 20]
        t = pd.DataFrame({"iso3": inv, "ticker": [f"E{i}" for i in inv], "status": "investable",
                          "r": rng.normal(0.05, 0.05, len(inv))})
        t.loc[t.index[-1], "status"] = "liquidated_in_window"
        rows[T] = t
        vt[T] = 0.06
    prov = fakes.FakeReturns(rows, vt, universe_iso3=ids[:24])
    res, table = lk.run(corpus, gd, prov, stats=fakes, B=400, growth_T={10: (2000, 2005, 2010, 2015)}, queries=("B", "A", "N4"), ks=(10,))
    r = res["rows"]["B|10|10|returns"]
    assert set(r["status_counts"]) <= {"investable", "liquidated_in_window", "no_fund_at_entry", "no_fund_ever"}
    assert sum(r["status_counts"].values()) == 40
    assert r["stats"]["n"] == r["status_counts"].get("investable", 0) + r["status_counts"].get("liquidated_in_window", 0)
    assert set(r["vs"]) == {"ew", "spy", "efa", "eem"}
    assert "N1_investable" in r["nulls"] and "N4_investable" in r["nulls"]
    assert 0 < r["nulls"]["N1_investable"]["p_mean_excess"] <= 1
    assert r["benchmark_per_T"] == {2000: "vt_proxy", 2005: "vt_proxy", 2010: "vt", 2015: "vt"}
    assert "oos_block_T_ge_2010" in r and r["oos_block_T_ge_2010"]["n"] >= 0
    tr = table[(table["outcome"] == "returns") & (table["query"] == "B")]
    assert len(tr) == 40 and tr["status"].notna().all()
    assert "P3" in res["predictions"] and "P3b" in res["predictions"] and "P5" in res["predictions"]
    assert set(res["predictions"]["P3"]["components"]) >= {"mu_er_in_[-4,3]_vs_vt", "ci_width_gt_8", "n_eff_lt_15", "ge_1_liquidation_in_2015_cohort"}
    # partial 2015 growth rows are flagged
    assert res["rows"]["B|10|10|growth"]["n_partial"] == 10


def test_predictions_p1_p2_p4_shape(world):
    corpus, gd, _ = world
    res, _ = lk.run(corpus, gd, stats=fakes, B=300, growth_T={10: (1990, 2000, 2010), 20: (1990, 1995, 2000)}, queries=("A", "B", "B3"), ks=(10, 5))
    p = res["predictions"]
    assert {"P1", "P2", "P4", "P5"} <= set(p)
    assert set(p["P1"]["components"]) == {"mu_eg_in_[0.3,1.5]", "hit_rate_in_[.55,.70]", "n_eff_in_[20,30]"}
    assert isinstance(p["P2"]["met"], bool) and "delta" in res["n3"]["10|10"]
    assert p["P4"]["row"] == "B|10|20|growth"
    assert set(res["rows"]) >= {"A|5|10|growth", "B|5|20|growth", "B3|10|10|growth"}
    # json-safe
    lk.to_jsonable(res)


def test_paired_bootstrap_sign():
    rng = np.random.default_rng(0)
    a = pd.DataFrame({"iso3": [f"c{i}" for i in range(40)], "T": np.repeat([1990, 2000, 2010, 2020], 10), "e": rng.normal(0.02, 0.005, 40)})
    b = a.assign(e=rng.normal(-0.02, 0.005, 40), iso3=[f"d{i}" for i in range(40)])
    pb = lk.paired_bootstrap(a, b, 10, B=500, seed=0)
    assert pb["delta"] > 0 and pb["ci_headline"][0] > 0 and pb["p_one_sided"] < 0.01
    pb2 = lk.paired_bootstrap(b, a, 10, B=500, seed=0)
    assert pb2["delta"] < 0 and pb2["p_one_sided"] > 0.9


def test_degenerate_samples_never_exclude_zero():
    one = pd.DataFrame({"iso3": ["A"], "T": [2015], "e": [-0.18], "top_q": [False]})
    s = lk.pooled_statistics(one, 10, stats=fakes, B=50)
    assert s["n"] == 1 and s["ci_degenerate"] and not s["ci_excludes_0"]
    assert np.isnan(s["hh_se"]) and np.isnan(s["naive_se"])
    same_country = pd.DataFrame({"iso3": ["A", "A"], "T": [2010, 2015], "e": [0.02, 0.03], "top_q": [True, True]})
    s2 = lk.pooled_statistics(same_country, 10, stats=fakes, B=50)
    assert s2["ci_degenerate"] and not s2["ci_excludes_0"]
    many = pd.DataFrame({"iso3": [f"c{i}" for i in range(12)], "T": [2010, 2015] * 6, "e": np.linspace(0.02, 0.04, 12), "top_q": True})
    s3 = lk.pooled_statistics(many, 10, stats=fakes, B=200)
    assert not s3["ci_degenerate"] and s3["ci_excludes_0"]


def test_etf_returns_keeps_prereg_status_for_liquidated_funds_with_ladder_gaps():
    """PREREG §3.4: a fund liquidated inside the window is `liquidated_in_window` even when its manual NAV ladder
    has gaps (econ.etf reports `manual_incomplete`); the gaps travel in `incomplete` so P3's liquidation clause and
    the status counts see the liquidation while RESULTS still lists the uncovered span."""
    from types import SimpleNamespace

    uni = pd.DataFrame({"ticker": ["NGE", "EWJ"], "iso3": ["NGA", "JPN"], "role": ["single_country", "single_country"],
                        "inception": pd.to_datetime(["2013-04-02", "1996-03-12"]), "delisted": [pd.Timestamp("2023-07-28"), pd.NaT],
                        "issuer": ["Global X", "iShares"]}).set_index("ticker", drop=False)

    def window_return(ticker, entry, exit_, **kw):
        if ticker == "NGE":
            return {"r_ann": -0.07, "max_dd": -0.56, "status": "manual_incomplete", "liquidated_in_window": True,
                    "incomplete": ["2024-01-31..2024-03-29 (final stub not transcribed)"]}
        return {"r_ann": 0.04, "max_dd": -0.3, "status": "ok", "liquidated_in_window": False, "incomplete": []}

    fake_etf = SimpleNamespace(load_universe=lambda: uni, last_trading_day=lambda y, **kw: pd.Timestamp(f"{y}-12-31"),
                               window_return=window_return, EtfGuardError=RuntimeError)
    prov = lk.EtfReturns(etf_mod=fake_etf, fetch_kw={})
    t = prov.etf_table(2015).set_index("iso3")
    assert t.loc["NGA", "status"] == "liquidated_in_window" and "2024-01-31..2024-03-29" in t.loc["NGA", "incomplete"]
    assert t.loc["JPN", "status"] == "investable" and pd.isna(t.loc["JPN", "incomplete"])
    # nothing at entry for a fund that was not yet listed
    t2 = prov.etf_table(2010).set_index("iso3")
    assert t2.loc["NGA", "status"] == "no_fund_at_entry" and np.isnan(t2.loc["NGA", "r"])


def test_pooled_statistics_reports_plain_cluster_se_and_flags_degenerate_T_blocks():
    rng = np.random.default_rng(9)
    rows = pd.DataFrame({"iso3": [f"c{i}" for i in range(30)], "T": np.repeat([1990, 1995, 2000], 10), "e": rng.normal(0.003, 0.01, 30), "top_q": False})
    s20 = lk.pooled_statistics(rows, 20, stats=fakes, B=100)
    assert s20["ci_block_T_degenerate"] and s20["bootstrap"]["block_len"] == 4 and s20["n_T"] == 3
    assert s20["ci_block_T"][0] == pytest.approx(s20["mean_excess"]) and s20["ci_block_T"][1] == pytest.approx(s20["mean_excess"])
    assert s20["ci_headline"] == s20["ci_country_cluster"]                # the wider (only informative) scheme wins
    assert np.isfinite(s20["cluster_se"]) and np.isfinite(s20["cluster_hac_se"]) and s20["cluster_hac_L"] == 3
    s10 = lk.pooled_statistics(rows, 10, stats=fakes, B=100)
    assert not s10["ci_block_T_degenerate"] and s10["cluster_hac_L"] == 1
    # plain cluster SE = sqrt(sum_c (sum_i d_i)^2)/n with one row per country here = the heteroskedasticity-robust SE of the mean
    d = rows["e"] * 100 - rows["e"].mean() * 100
    assert s10["cluster_se"] == pytest.approx(np.sqrt((d ** 2).sum()) / 30, rel=1e-6)
    pb = lk.paired_bootstrap(rows.iloc[:15], rows.iloc[15:], 20, B=100, seed=0)
    assert pb["ci_block_T_degenerate"]
