"""decide.py (table-driven L0/L1/L2 cases, deny-list), disconnect.py (pure parts with a fake etf module),
results.py rendering, and the PREREG hash check (PREREG §0.3, §9)."""
from __future__ import annotations

import copy
import json
import subprocess

import numpy as np
import pandas as pd
import pytest
import yaml

from pyramid_explorer.econ import decide, disconnect, results
from pyramid_explorer.paths import ECON_EVALS, REPO_ROOT

SENTENCES = yaml.safe_load((ECON_EVALS / "ui_sentences.yaml").read_text())


# ----------------------------------------------------------------------------------------------- fixtures
def good_backtest() -> dict:
    """A backtest document in which every L1 and L2 condition holds."""
    g_stats = {"n": 60, "n_eff": 40, "mean_excess": 0.9, "ci_headline": [0.2, 1.6], "ci_excludes_0": True, "hit_rate": 0.65,
               "hh_p": 0.01, "nw2_p": 0.01, "nw4_p": 0.02, "per_T": {"1990": {"mean_excess": 0.8, "n": 10, "hit_rate": 0.6},
                                                                     "2000": {"mean_excess": 1.0, "n": 10, "hit_rate": 0.7}}}
    r_stats = {"n": 24, "n_eff": 22, "mean_excess": 2.0, "ci_headline": [0.5, 3.5], "ci_excludes_0": True, "hit_rate": 0.7,
               "hh_p": 0.01, "nw2_p": 0.02, "nw4_p": 0.03, "per_T": {}}
    picks = [{"T": 2010, "iso3": "IDN", "ticker": "EIDO", "status": "investable", "r": 0.05, "r_vt": 0.09, "er": -0.04, "benchmark": "vt",
              "inception": "2010-05-05", "issuer": "iShares", "delisted": None},
             {"T": 2015, "iso3": "NGA", "ticker": "NGE", "status": "liquidated_in_window", "r": -0.10, "r_vt": 0.10, "er": -0.20, "benchmark": "vt",
              "inception": "2013-04-02", "issuer": "Global X", "delisted": "2023-07-28"},
             {"T": 2005, "iso3": "BGD", "ticker": None, "status": "no_fund_at_entry", "r": None, "r_vt": 0.05, "er": None, "benchmark": "vt_proxy"},
             {"T": 2005, "iso3": "NPL", "ticker": None, "status": "no_fund_ever", "r": None, "r_vt": 0.05, "er": None, "benchmark": "vt_proxy"}]
    return {"rows": {
        "B|10|10|growth": {"query": "B", "k": 10, "h": 10, "outcome": "growth", "stats": g_stats,
                           "nulls": {"N1": {"p_mean_excess": 0.01, "share_at_least_as_good": 0.01, "B": 5000},
                                     "N2": {"p_mean_excess": 0.02, "share_at_least_as_good": 0.02, "B": 5000}},
                           "median_g_per_T": {"1990": 1.5, "2000": 2.0}, "candidates_per_T": {"1990": 100, "2000": 120},
                           "picks": [{"T": 1990, "iso3": "KOR", "d": 0.5, "g": 0.05, "eg": 0.02}]},
        "B|10|10|returns": {"query": "B", "k": 10, "h": 10, "outcome": "returns", "stats": r_stats, "n_picks": 40,
                            "vs": {"ew": {"mean_excess": 1.0}}, "nulls": {"N1_investable": {"p_mean_excess": 0.01}, "N4_investable": {"p_one_sided": 0.02}},
                            "oos_block_T_ge_2010": {"n": 12, "mean_excess_vs_vt": 1.5, "same_sign_as_pooled": True}, "picks": picks}},
        "n3": {"10|10": {"delta": 0.1, "ci_headline": [-0.5, 0.7]}},
        "predictions": {"P1": {"statement": "x", "met": False}}}


def good_panel() -> dict:
    return {"specs": {"S3": {"coef": {"D": {"beta": -0.004, "p_dk": 0.01}, "WA": {"beta": 0.1, "p_dk": 0.01}, "dWA": {"beta": 0.2, "p_dk": 0.04}}, "r2": 0.3}},
            "holdout": {"oos_r2": {"S0": {"vs_mean": 0.05}, "S3": {"vs_mean": 0.08}}}, "predictions": {"P6": {"statement": "y", "met": True}}}


def good_disconnect() -> dict:
    return {"rows": [{"iso3": "CHN", "year": 1990, "name": "China", "kind": "history",
                      "levels": {"y_t": 1000.0, "multiples": {"10": 1.5, "20": 3.0, "30": 6.2}, "y_last_year": 2023, "mult_last": 7.0},
                      "msci": {"state": "ok", "index_name": "MSCI China", "ann_pct_gross_since": 1.55, "since": "1992-12-31",
                               "max_drawdown_pct_gross": 88.63, "accessed": "2026-09-04"}},
                     {"iso3": "LAO", "year": 2024, "name": "Lao PDR", "kind": "now",
                      "levels": {"y_t": 500.0, "multiples": {}, "y_last_year": 2024, "mult_last": None}, "msci": {"state": decide.PRIMARY_N3 and "no MSCI figure transcribed"}},
                     {"iso3": "KOR", "year": 1975, "name": "Korea", "kind": "history",
                      "levels": {"y_t": 2000.0, "multiples": {"10": 2.0, "20": 4.0, "30": 8.0}, "y_last_year": 2023, "mult_last": 12.0},
                      "msci": {"state": "no MSCI figure transcribed"}}]}


def run_decide(bt=None, pn=None, dc=None) -> dict:
    bt = good_backtest() if bt is None else bt
    pn = good_panel() if pn is None else pn
    return decide.decide(bt, pn, SENTENCES, prereg_commit="abc", disconnect=dc)


def _set(doc: dict, path: str, value) -> dict:
    d = copy.deepcopy(doc)
    cur = d
    keys = path.split("/")
    for k in keys[:-1]:
        cur = cur[k]
    cur[keys[-1]] = value
    return d


# ----------------------------------------------------------------------------------------------- decision cases
def test_all_good_grants_every_level():
    dec = run_decide()
    assert dec["levels_granted"] == ["L0", "L1", "L2"]
    assert all(c["ok"] for c in dec["conditions"].values())
    assert "L1.growth_association" in dec["allowed_sentence_ids"] and "L2.returns_signal" in dec["allowed_sentence_ids"]
    assert dec["deny_list_violations"] == []
    assert dec["rendered"]["L1.growth_association"][0].endswith("The working-age share alone accounts for this.")
    assert dec["prereg_commit"] == "abc"


L1_CASES = [
    ("rows/B|10|10|growth/stats/mean_excess", -0.2, "mu_eg_gt_0"),
    ("rows/B|10|10|growth/stats/ci_excludes_0", False, "ci_headline_excludes_0"),
    ("rows/B|10|10|growth/nulls/N1/p_mean_excess", 0.30, "p_n1_lt_05"),
    ("rows/B|10|10|growth/nulls/N2/p_mean_excess", 0.06, "p_n2_lt_05"),
    ("rows/B|10|10|growth/stats/n_eff", 15, "n_eff_ge_20"),            # significant but N_eff = 15 → L0 only
]


@pytest.mark.parametrize("path,value,cond", L1_CASES)
def test_each_l1_condition_alone_blocks_l1(path, value, cond):
    dec = run_decide(bt=_set(good_backtest(), path, value))
    assert not dec["levels"]["L1"]["granted"] and dec["levels"]["L1"]["failed"] == [cond]
    assert dec["levels"]["L0"]["granted"]
    assert "L1.growth_association" not in dec["allowed_sentence_ids"] and "L1.growth_association" not in dec["rendered"]


@pytest.mark.parametrize("path,value,cond", [
    ("specs/S3/coef/D/beta", 0.002, "panel_s3_d_lt_0_dk_p_lt_05"),
    ("specs/S3/coef/D/p_dk", 0.2, "panel_s3_d_lt_0_dk_p_lt_05"),
    ("holdout/oos_r2/S3/vs_mean", 0.04, "oos_r2_s3_gt_s0"),
])
def test_each_panel_condition_alone_blocks_l1(path, value, cond):
    dec = run_decide(pn=_set(good_panel(), path, value))
    assert dec["levels"]["L1"]["failed"] == [cond] and not dec["levels"]["L1"]["granted"]
    assert dec["levels"]["L2"]["granted"]                               # L2 does not read the panel


L2_CASES = [
    ("rows/B|10|10|returns/stats/mean_excess", -1.0, "mu_er_vs_vt_gt_0"),     # beat the basket but lost to VT → no L2
    ("rows/B|10|10|returns/stats/ci_excludes_0", False, "ci_er_headline_excludes_0"),
    ("rows/B|10|10|returns/stats/hh_p", 0.2, "hh_p_lt_05"),
    ("rows/B|10|10|returns/stats/nw4_p", 0.07, "nw_p_lt_05"),                  # L = 2 AND L = 4 are both required
    ("rows/B|10|10|returns/vs/ew/mean_excess", -0.5, "mu_er_vs_ew_gt_0"),
    ("rows/B|10|10|returns/nulls/N1_investable/p_mean_excess", 0.3, "beats_n1_investable_p_lt_05"),
    ("rows/B|10|10|returns/nulls/N4_investable/p_one_sided", 0.5, "beats_n4_p_lt_05"),
    ("rows/B|10|10|returns/stats/n_eff", 12, "n_eff_returns_ge_20"),
    ("rows/B|10|10|returns/oos_block_T_ge_2010/same_sign_as_pooled", False, "oos_block_same_sign"),   # CI excludes 0 but OOS sign flips → L0
]


@pytest.mark.parametrize("path,value,cond", L2_CASES)
def test_each_l2_condition_alone_blocks_l2(path, value, cond):
    dec = run_decide(bt=_set(good_backtest(), path, value))
    assert not dec["levels"]["L2"]["granted"] and dec["levels"]["L2"]["failed"] == [cond]
    assert dec["levels"]["L1"]["granted"] and dec["levels"]["L0"]["granted"]
    assert "L2.returns_signal" not in dec["rendered"]


def test_missing_inputs_make_conditions_unavailable_and_l0_still_renders():
    bt = good_backtest()
    del bt["rows"]["B|10|10|returns"]
    dec = run_decide(bt=bt, pn={})
    assert dec["levels"]["L0"]["granted"] and not dec["levels"]["L1"]["granted"] and not dec["levels"]["L2"]["granted"]
    assert "panel_s3_d_lt_0_dk_p_lt_05" in dec["levels"]["L1"]["unavailable"]
    assert set(dec["levels"]["L2"]["unavailable"]) >= {"mu_er_vs_vt_gt_0", "hh_p_lt_05"}
    assert dec["rendered"]["L0.what_happened"] and dec["rendered"]["L0.null"]


def test_p2_toggles_working_age_addendum():
    dec = run_decide(bt=_set(good_backtest(), "n3/10|10/delta", 0.8))
    assert dec["conditions"]["p2_met"]["ok"] is False
    assert not dec["rendered"]["L1.growth_association"][0].endswith("accounts for this.")


def test_l0_rendering_covers_every_variant():
    dec = run_decide(dc=good_disconnect())
    r = dec["rendered"]
    assert len(r["L0.what_happened"]) == 2 and "1990" in r["L0.what_happened"][0]
    assert len(r["L0.vs_vt"]) == 2 and "VT over the same window" in r["L0.vs_vt"][0]
    inv = " ".join(r["L0.investability"])
    assert "has existed since 2010-05-05" in inv and "liquidated on 2023-07-28" in inv and "existed in 2005" in inv and "exists for this country" in inv
    assert len(r["L0.disconnect"]) == 2 and "MSCI China" in r["L0.disconnect"][0] and "no MSCI figure transcribed" in r["L0.disconnect"][1]
    assert "p = 0.01" in r["L0.null"][0]


# ----------------------------------------------------------------------------------------------- deny list
def test_deny_list_catches_planted_phrases():
    pats = decide.compile_deny_list(SENTENCES)
    bad = "Investors should invest here; the top 10 picks have outsized alpha and an expected return that will outperform."
    hits = decide.scan_deny_list(bad, pats)
    matched = {h["match"].lower() for h in hits}
    assert {"should invest", "top 10", "picks", "outsized", "alpha", "expected return", "will outperform"} <= matched
    assert decide.scan_deny_list("GDP per capita grew 2.1 %/yr; VT over the same window returned 9 %/yr.", pats) == []
    # a planted phrase inside a rendered sentence is reported by decide()
    s = copy.deepcopy(SENTENCES)
    s["sentences"]["L0.null"]["template"] = "This is an opportunity to buy {k} countries (p = {p_n1:.2f})."
    dec = decide.decide(good_backtest(), good_panel(), s, prereg_commit="x")
    assert any(v["where"].startswith("rendered:L0.null") for v in dec["deny_list_violations"])
    assert any(v["where"].startswith("template:L0.null") for v in dec["deny_list_violations"])


def test_every_template_renders_clean_with_dummy_values():
    pats = decide.compile_deny_list(SENTENCES)
    templates = decide.all_templates(SENTENCES)
    assert len(templates) >= 12
    for sid, tpl in templates.items():
        text = decide.render_template(tpl, decide.DUMMY)
        assert decide.scan_deny_list(text, pats) == [], (sid, text)
        assert decide.scan_deny_list(tpl, pats) == [], sid


# ----------------------------------------------------------------------------------------------- disconnect (pure parts)
class _FakeEtf:
    def last_trading_day(self, year, **kw):
        if year < 1993:
            raise ValueError("no SPY bars")                    # like the real SPY calendar
        return pd.Timestamp(f"{year}-12-31")

    def window_return(self, ticker, entry, exit, **kw):
        if ticker == "EEM" and entry < pd.Timestamp("2003-04-07"):
            raise ValueError("no fund at entry")
        return {"r_ann": 0.05 if ticker != "SPY" else 0.08, "max_dd": -0.4, "status": "ok", "entry_used": entry, "exit_used": exit}

    def vt_benchmark(self, entry, exit, **kw):
        return {"r_ann": 0.07, "benchmark": "vt" if entry >= pd.Timestamp("2008-06-24") else "vt_proxy"}


def test_disconnect_pure_parts():
    cites = yaml.safe_load((ECON_EVALS / "msci_citations.yaml").read_text())
    m = disconnect.msci_facts(cites, "CHN", 1990)
    assert m["state"] == "ok" and m["ann_pct_gross_since"] == 1.55 and m["max_drawdown_pct_gross"] == 88.63 and m["clipped_to_index_history"]
    assert disconnect.msci_facts(cites, "KOR", 1990)["clipped_to_index_history"] and disconnect.msci_facts(cites, "LAO", 2024)["state"] == disconnect.NO_MSCI
    lv = pd.DataFrame({"iso3": ["X"] * 40, "year": range(1984, 2024), "y_level": np.exp(np.linspace(0, 2, 40))}).set_index(["iso3", "year"])["y_level"]
    r = disconnect.level_multiples(lv, "X", 1995)
    assert r["multiples"][10] == pytest.approx(np.exp(10 * 2 / 39)) and r["multiples"][30] is None and r["y_last_year"] == 2023 and "clipped" in r["state"]
    assert r["mult_last"] == pytest.approx(np.exp(28 * 2 / 39))
    assert disconnect.level_multiples(lv, "X", 1990)["multiples"][30] == pytest.approx(np.exp(30 * 2 / 39))
    assert disconnect.level_multiples(lv, "Y", 1990)["state"] == "no level series"
    uni = pd.DataFrame([{"ticker": "FXI", "iso3": "CHN", "role": "single_country", "inception": "2004-10-05", "delisted": None, "name": "n", "issuer": "i"},
                        {"ticker": "MCHI", "iso3": "CHN", "role": "single_country", "inception": "2011-03-29", "delisted": None, "name": "n", "issuer": "i"},
                        {"ticker": "EWJ", "iso3": "JPN", "role": "single_country", "inception": "1996-03-12", "delisted": None, "name": "n", "issuer": "i"}])
    f = disconnect.fund_block(uni, _FakeEtf(), "CHN", 1990)
    assert f["ticker"] == "FXI" and f["entry_from_inception"] and f["state"] == "ok" and f["vt"]["benchmark"] == "vt_proxy"
    assert f["cagr"] == pytest.approx(np.exp(0.05) - 1) and f["spy"]["ann_log_return"] == 0.08 and f["eem"]["ann_log_return"] == 0.05
    assert disconnect.fund_block(uni, _FakeEtf(), "JPN", 1960)["state"] == disconnect.NO_FUND_IN_WINDOW
    assert disconnect.fund_block(uni, _FakeEtf(), "BGD", 2024)["state"] == disconnect.NO_FUND
    f2 = disconnect.fund_block(uni, _FakeEtf(), "JPN", 1990)      # window 1990→2020, fund from 1996; EEM did not exist at entry
    assert f2["entry_used"] == "1996-03-12" and "state" in f2["eem"]


def test_results_render_is_deny_list_clean_and_complete():
    dec = run_decide(dc=good_disconnect())
    universe = yaml.safe_load((ECON_EVALS / "etf_universe.yaml").read_text())
    ctx = {"prereg_commit": "abc", "run": {"generated_at": "t", "git_rev": "r", "seed": 1, "B": 10}, "sources": [{"id": "pwt-11.0", "family": "pwt", "redistributable": True}],
           "universe": universe, "guard": None, "backtest": good_backtest(), "panel": good_panel(), "disconnect": good_disconnect(), "decision": dec,
           "implementation_notes": ["note"], "deviations": []}
    md = results.render_results(ctx)
    for head in ("## 1. Data vintages", "## 2. ETF universe", "## 3. Pre-registered predictions", "## 4. Experiment 1", "## 5. Experiment 2",
                 "## 6. Experiment 3", "## 7. Vintage statement", "## 8. Decision levels", "## 10. Deviations from PREREG"):
        assert head in md
    assert "`abc`" in md and "N_eff" in md and "VT over the same window" in md
    assert decide.scan_deny_list(md, decide.compile_deny_list(SENTENCES)) == []


# ----------------------------------------------------------------------------------------------- PREREG hash
def _git_prereg_hash() -> str:
    try:
        return subprocess.run(["git", "log", "-1", "--format=%H", "--", "evals/econ/PREREG.md"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def test_prereg_hash():
    """PREREG §0.3: RESULTS.md and decision.json must cite the commit that last touched PREREG.md (14f8c3c…)."""
    h = _git_prereg_hash()
    if not h:
        pytest.skip("git history unavailable")
    assert h.startswith("14f8c3c")
    assert results.prereg_commit_hash() == h
    dec_path, res_path = ECON_EVALS / "decision.json", ECON_EVALS / "RESULTS.md"
    if not dec_path.exists() and not res_path.exists():
        pytest.skip("backtest outputs not written yet")
    if dec_path.exists():
        assert json.loads(dec_path.read_text())["prereg_commit"] == h
    if res_path.exists():
        assert h in res_path.read_text()


def test_prereg_and_companions_are_committed_and_unmodified():
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", "evals/econ/PREREG.md", "evals/econ/etf_universe.yaml", "evals/econ/ui_sentences.yaml",
                              "evals/econ/msci_citations.yaml", "evals/econ/etf_crosscheck.yaml"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git unavailable")
    assert out.stdout.strip() == "", f"pre-registered files modified after commit:\n{out.stdout}"


# ----------------------------------------------------------------------------------------------- units and per-T support in L0
def test_vs_vt_sentence_carries_cagr_not_log_return():
    """The `%/yr` placeholders of L0.vs_vt receive 100·(e^r − 1); a log return of 0.05/yr renders as +5.1 %/yr, not +5.0."""
    assert decide.cagr_pct(0.05) == pytest.approx(100 * (np.exp(0.05) - 1))
    assert decide.cagr_pct(-0.07341) == pytest.approx(-7.08, abs=0.01)
    dec = run_decide()
    s = dec["rendered"]["L0.vs_vt"][0]
    assert "EIDO total return 2010–2020: +5.1 %/yr" in s and "VT over the same window: +9.4 %/yr" in s
    s2 = dec["rendered"]["L0.vs_vt"][1]
    assert "NGE" in s2 and "-9.5 %/yr" in s2 and "+10.5 %/yr" in s2          # exp(-0.10) − 1 = −9.52 %, exp(0.10) − 1 = +10.52 %


def test_what_happened_uses_per_T_support_and_observed_span():
    bt = good_backtest()
    g = bt["rows"]["B|10|10|growth"]
    g["stats"]["per_T"]["2015"] = {"mean_excess": -1.0, "n": 10, "hit_rate": 0.3}
    g["median_g_per_T"]["2015"] = 1.4
    g["candidates_per_T"]["2015"] = 157
    g["picks"] = [{"T": 2015, "iso3": "NGA", "src": "pwt", "partial": True}, {"T": 2015, "iso3": "AFG", "src": "maddison", "partial": True},
                  {"T": 1990, "iso3": "KOR", "src": "pwt", "partial": False}]
    dec = run_decide(bt=bt)
    texts = dec["rendered"]["L0.what_happened"]
    assert all("(N_eff = 10;" in t for t in texts) and not any("N_eff = 40" in t for t in texts)   # per-T support, not the pooled 40
    assert "over the following 7–8 years" in texts[-1] and "in 2015" in texts[-1]
    assert "over the following 10 years" in texts[0]
    # a single-source 2015 cohort names its own span; a non-2015 T is always h
    assert decide.span_years([{"T": 2015, "src": "pwt"}], 2015, 10) == 8
    assert decide.span_years([{"T": 2015, "src": "maddison"}], 2015, 10) == 7
    assert decide.span_years([], 2015, 10) == "7–8" and decide.span_years([], 2000, 10) == 10


def test_disconnect_short_window_is_not_annualised():
    class _ShortEtf(_FakeEtf):
        def window_return(self, ticker, entry, exit, **kw):
            out = super().window_return(ticker, entry, exit, **kw)
            return {**out, "years": 0.52, "r_log": -0.5625, "r_ann": -1.0819}       # EWT 2000-06-23 → 2000-12-29

    uni = pd.DataFrame([{"ticker": "EWT", "iso3": "TWN", "role": "single_country", "inception": "2000-06-20", "delisted": None, "name": "n", "issuer": "i"}])
    f = disconnect.fund_block(uni, _ShortEtf(), "TWN", 1970)
    assert f["too_short_to_annualise"] and f["window_years"] == 0.52 and f["min_annualise_years"] == disconnect.MIN_ANNUALISE_YEARS
    assert f["total_return"] == pytest.approx(np.exp(-0.5625) - 1) and f["ann_log_return"] == pytest.approx(-1.0819)
    dc = {"_meta": {"min_annualise_years": 1.0}, "rows": [{"iso3": "TWN", "year": 1970, "kind": "history", "name": "Taiwan",
                                                          "pyramid": {"median_age": 18.8, "u15": .4, "wa": .56, "o65": .03, "s0_s20": 1.7, "tfr": 4.0},
                                                          "distance": {"d_blend_chn1990": 0.95, "pct_band": "nearest half", "pct_same_year": 0.35},
                                                          "levels": {"multiples": {"10": 2.07, "20": 3.85, "30": 6.45}}, "msci": {"state": "no MSCI figure transcribed"}, "fund": f}]}
    md = results.render_results({"prereg_commit": "abc", "run": {}, "sources": [], "universe": {"entries": []}, "guard": None, "backtest": {}, "panel": {},
                                 "disconnect": dc, "decision": run_decide(), "implementation_notes": [], "deviations": []})
    assert "window under 1 y, not annualised" in md and "-108.19 pp/yr" not in md and "total return -43.02 % over the span" in md
    assert decide.scan_deny_list(md, decide.compile_deny_list(SENTENCES)) == []        # 'short' is a denied word — never in the wording
    long = disconnect.fund_block(uni, _FakeEtf(), "TWN", 1990)
    assert not long["too_short_to_annualise"]

    class _OneYearEtf(_FakeEtf):
        def window_return(self, ticker, entry, exit, **kw):
            return {**super().window_return(ticker, entry, exit, **kw), "years": 365 / 365.25, "r_log": 0.0155}    # EPHE 2024-12-31 → 2025-12-31

    assert not disconnect.fund_block(uni, _OneYearEtf(), "TWN", 2024)["too_short_to_annualise"]        # a one-year window annualises


def test_results_flag_degenerate_T_block_ci_and_relabel_cluster_se():
    bt = good_backtest()
    g = bt["rows"]["B|10|10|growth"]
    g["stats"].update({"ci_block_T": [0.33, 0.33], "ci_block_T_degenerate": True, "ci_country_cluster": [-0.5, 1.2], "cluster_se": 0.42, "cluster_p": 0.65,
                       "cluster_hac_se": 0.49, "cluster_hac_p": 0.70, "cluster_hac_L": 1})
    bt["n3"]["10|10"].update({"ci_block_T": [0.35, 0.35], "ci_block_T_degenerate": True, "ci_country_cluster": [-0.7, 1.5]})
    dec = run_decide(bt=bt)
    md = results.render_results({"prereg_commit": "abc", "run": {}, "sources": [], "universe": {"entries": []}, "guard": None, "backtest": bt, "panel": good_panel(),
                                 "disconnect": None, "decision": dec, "implementation_notes": [], "deviations": []})
    assert "[+0.33, +0.33] — degenerate: block length ≥ number of T's" in md
    assert "[+0.35, +0.35] (degenerate: block length ≥ n_T)" in md
    assert "country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.42 / 0.650" in md
    assert "within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.49 / 0.700" in md
    assert "country-cluster HAC SE" not in md
    assert "without any multiple-comparison adjustment" in md and "Publication lag" in md
    assert "compound annual growth rate" in md


def test_results_render_panel_self_match_note_and_p7_flag():
    pn = good_panel()
    pn["specs"]["S2"] = {"coef": {"D": {"beta": -0.0024, "se_dk": 0.0002, "p_dk": 0.0}}, "r2": 0.31, "n": 7561}
    pn["specs"]["S3"].update({"n": 7561})
    pn["specs"]["S3"]["coef"]["D"].update({"se_dk": 0.0002})
    pn["sample"] = {"n": 7561, "n_self_match": 88, "share_self_match_top_decile_g": 0.92, "n_own_prototype_overlap": 1234, "share_own_prototype_overlap": 0.163,
                    "self_match_t_max": 1993, "d_clip": 1e-9, "D_at_clip": -20.72, "D_quantiles": {"0.01": -20.72, "0.5": -1.55}, "mean_g_own_overlap": 0.038,
                    "mean_g_other": 0.013, "n_self_match_in_test_block": 0, "n_own_prototype_overlap_in_test_block": 0}
    pn["robustness"] = {"ex_overlap": {"rule": "drop overlap", "n": 6327, "specs": {"S2": {"coef": {"D": {"beta": 0.0036, "se_dk": 0.0014, "p_dk": 0.012}}, "r2": 0.3},
                                                                                     "S3": {"coef": {"D": {"beta": 0.00101, "se_dk": 0.00232, "p_dk": 0.664}}, "r2": 0.3}}}}
    pn["predictions"]["P7"] = {"statement": "D < 0 in-sample but …", "components": {"D_lt_0_in_sample": {"beta": -0.0024, "p_dk": 0.0, "ok": True, "note": "artifact — see §5 note"}}, "met": True}
    dec = run_decide(pn=pn)
    md = results.render_results({"prereg_commit": "abc", "run": {}, "sources": [], "universe": {"entries": []}, "guard": None, "backtest": good_backtest(), "panel": pn,
                                 "disconnect": None, "decision": dec, "implementation_notes": [], "deviations": []})
    assert "Prototype self-matching — mandatory note" in md and "88 sample rows are their own nearest prototype" in md and "1234 rows (16.3 %)" in md
    assert "`ex_overlap`" in md and "+0.00101 (SE 0.00232, p 0.664)" in md and "**not evidence**" in md
    assert "D_lt_0_in_sample: beta=-0.002, p_dk=0.000 → ok (artifact — see §5 note)" in md
    assert decide.scan_deny_list(md, decide.compile_deny_list(SENTENCES)) == []
