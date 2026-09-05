"""M5 econ export — splice / typology / instruments / export_econ / evidence (pure parts on fixtures; the shipped files
when present). Licence guard (plan §7): nothing under web/public/data names a non-redistributable source, and the
econ file carries no index-provider series (the classification label under ``msci_class`` is the one allowed token)."""
from __future__ import annotations

import gzip
import json
import re

import numpy as np
import pandas as pd
import pytest
import yaml

from pyramid_explorer.econ import export_econ as X, instruments as I, splice as S, typology as T
from pyramid_explorer.paths import DATA_PROCESSED, PIPELINE, REPO_ROOT, WEB_DATA, WEB_SRC_DATA

DB = DATA_PROCESSED / "explorer.duckdb"
ECZ = sorted((WEB_DATA / "wpp2024").glob("econ.*.ecz"))
LICENCE_RE = re.compile(r"weo|imf|ngdp", re.I)
PROVIDER_RE = re.compile(r"msci", re.I)
needs_db = pytest.mark.skipif(not DB.exists(), reason="needs `make build`")
needs_ecz = pytest.mark.skipif(not ECZ, reason="econ.*.ecz not exported yet")


# ------------------------------------------------------------------------------------------------ splice (pure)
def _frame(rows: dict[str, dict[int, float]], years=range(2019, 2025)) -> pd.DataFrame:
    return pd.DataFrame({y: [rows[c].get(y, np.nan) for c in rows] for y in years}, index=list(rows))


def test_splice_extends_maddison_with_wdi_growth_then_pwt_then_stops():
    mad = _frame({"AAA": {2019: 100.0, 2020: 110.0, 2021: 120.0, 2022: 130.0}, "BBB": {}})
    wdi = _frame({"AAA": {2022: 50.0, 2023: 55.0}, "BBB": {2019: 10.0, 2020: 12.0, 2021: np.nan, 2022: 14.0}})
    pwt = _frame({"AAA": {2023: 7.0, 2024: 7.7}, "BBB": {}})
    level, flag = S.splice_gdppc(mad, wdi, pwt, ratio=0.5)
    assert level.at["AAA", 2022] == 130.0 and flag.at["AAA", 2022] == "maddison"
    assert level.at["AAA", 2023] == pytest.approx(130.0 * 55 / 50) and flag.at["AAA", 2023] == "wdi_growth"
    assert level.at["AAA", 2024] == pytest.approx(level.at["AAA", 2023] * 1.1) and flag.at["AAA", 2024] == "pwt_growth"
    # WDI-only country: rescaled level, gaps stay missing
    assert level.at["BBB", 2019] == 5.0 and flag.at["BBB", 2019] == "wdi_rescaled"
    assert np.isnan(level.at["BBB", 2021]) and pd.isna(flag.at["BBB", 2021])
    assert np.isnan(level.at["BBB", 2023])


def test_splice_growth_series_prefers_pwt_and_converts_wdi_to_log():
    rg = _frame({"AAA": {2019: 100.0, 2020: 105.0, 2021: np.nan, 2022: 110.0}})
    w = _frame({"AAA": {2020: 9.0, 2021: 3.0, 2022: 2.0, 2023: 4.0}})
    g, flag = S.growth_series(rg, w)
    assert g.at["AAA", 2020] == pytest.approx(100 * np.log(1.05)) and flag.at["AAA", 2020] == "pwt"
    assert g.at["AAA", 2021] == pytest.approx(100 * np.log1p(0.03)) and flag.at["AAA", 2021] == "wdi"
    assert np.isnan(g.at["AAA", 2019]) and pd.isna(flag.at["AAA", 2019])


def test_splice_growth10_extends_per_capita_with_wdi():
    years = range(2000, 2015)
    pc = pd.DataFrame({y: [100.0 * 1.02 ** (y - 2000) if y <= 2013 else np.nan] for y in years}, index=["AAA"])
    wdi = pd.DataFrame({y: [50.0 * 1.05 ** (y - 2000)] for y in years}, index=["AAA"])
    g10, flag = S.growth10_series(pc, wdi)
    assert g10.at["AAA", 2013] == pytest.approx(100 * np.log(1.02)) and flag.at["AAA", 2013] == "pwt"
    assert flag.at["AAA", 2014] == "wdi_ext" and g10.at["AAA", 2014] > g10.at["AAA", 2013]
    assert np.isnan(g10.at["AAA", 2009])


def test_rescale_ratio_is_the_median_over_countries_with_both():
    mad = _frame({"A": {2017: 20.0}, "B": {2017: 30.0}, "C": {2017: 40.0}, "D": {}}, years=range(2017, 2018))
    wdi = _frame({"A": {2017: 10.0}, "B": {2017: 10.0}, "C": {2017: np.nan}, "D": {2017: 5.0}}, years=range(2017, 2018))
    r, n = S.rescale_ratio(mad, wdi, 2017)
    assert r == 2.5 and n == 2


# ------------------------------------------------------------------------------------------------ typology (pure)
def _series(d: dict[tuple[str, int], float]) -> pd.Series:
    idx = pd.MultiIndex.from_tuples(list(d), names=["iso3", "year"])
    return pd.Series(list(d.values()), index=idx, dtype=float)


def test_typology_rule_matches_wps7893_table_1():
    thr = T.load_thresholds()
    # PRE: growing share, TFR ≥ 4; EARLY: growing, TFR < 4; LATE: not growing, TFR(y−30) ≥ 2.1; POST: not growing, TFR(y−30) < 2.1
    wa = _series({("PRE", 2015): .52, ("PRE", 2030): .55, ("EAR", 2015): .60, ("EAR", 2030): .63, ("LAT", 2015): .70, ("LAT", 2030): .68,
                  ("POS", 2015): .66, ("POS", 2030): .60, ("NA1", 2015): .66, ("NA1", 2030): .60, ("NA2", 2015): .60})
    tfr = _series({("PRE", 2015): 5.4, ("PRE", 1985): 6.6, ("EAR", 2015): 2.3, ("EAR", 1985): 4.3, ("LAT", 2015): 1.6, ("LAT", 1985): 2.75,
                   ("POS", 2015): 1.4, ("POS", 1985): 1.4, ("NA2", 2015): 2.0})   # NA1: no generation-ago TFR; NA2: no look-ahead share
    out = T.assign(wa, tfr, range(2015, 2016), thr).set_index("iso3")["stage"]
    assert out.to_dict() == {"PRE": 1, "EAR": 2, "LAT": 3, "POS": 4, "NA1": 0, "NA2": 0}


def test_typology_yaml_cites_the_source_and_says_adapted():
    doc = yaml.safe_load((PIPELINE / "typology.yaml").read_text(encoding="utf-8"))
    assert doc["source"]["adapted"] is True and "7893" in doc["source"]["citation"] and doc["source"]["url"].startswith("https://")
    assert doc["thresholds"]["tfr_high"] == 4.0 and doc["thresholds"]["tfr_replacement"] == 2.1
    assert doc["thresholds"]["horizon_years"] == 15 and doc["thresholds"]["generation_years"] == 30
    assert len(doc["reproduction_2015"]["named"]) == 20 and len(doc["reproduction_2015"]["table_a1"]) >= 100


@needs_db
def test_typology_reproduces_2015_assignments():
    """20 named countries reproduce the report's 2015 group (WPS7893 Table A1) and the whole transcribed table agrees
    at ≥ the yaml's floor — differences are WPP 2015 → 2024 revisions on borderline rows, listed in the yaml."""
    thr = T.load_thresholds()
    stages = T.build_stages(thresholds=thr, years=range(2010, 2025))
    rep = T.reproduction_report(stages, thr["_doc"])
    assert rep["named_all_agree"], rep["named_disagree"]
    assert rep["rate"] >= thr["_doc"]["reproduction_2015"]["min_agreement_rate"], rep["disagreements"]
    d = T.distribution(stages, 2024)
    assert set(d) <= {"n/a", "pre", "early", "late", "post"} and d.get("n/a", 0) <= 3


# ------------------------------------------------------------------------------------------------ instruments (pure)
def test_mobility_and_country_status_rules():
    assert I.mobility("standalone", []) == "closed"
    assert I.mobility("FM", [{"kind": "index_deletion"}]) == "closed"
    assert I.mobility("FM", [{"kind": "repatriation"}]) == "restricted"
    assert I.mobility("FM", []) == "not_assessed"
    assert I.mobility("EM", []) == "open" and I.mobility("DM", []) == "open"
    assert I.mobility(None, []) == "not_assessed" and I.mobility("none", []) == "not_assessed"
    assert I.country_status([]) == "none"
    assert I.country_status([{"status": "liquidated"}, {"status": "live"}]) == "live"
    assert I.country_status([{"status": "liquidated"}, {"status": "liquidating"}]) == "liquidating"


def test_instrument_stats_are_derived_and_paired_with_vt():
    dates = pd.bdate_range("2012-02-03", "2026-09-04")
    bars = pd.DataFrame({"date": dates, "adjclose": np.linspace(20.0, 50.0, len(dates))})
    entry = {"ticker": "FND", "inception": "2012-02-02", "delisted": None}
    spy = pd.DataFrame({"date": pd.bdate_range("1993-01-29", "2026-09-04")})
    spy["adjclose"] = np.linspace(40.0, 500.0, len(spy))
    vt = pd.DataFrame({"date": pd.bdate_range("2008-06-24", "2026-09-04")})
    vt["adjclose"] = np.linspace(50.0, 120.0, len(vt))
    bench = {"SPY": spy, "VT": vt}
    rec = I.since_inception_live("FND", entry, bench, cache_dir=REPO_ROOT / "does-not-exist")
    assert rec["since_inception_cagr_pct"] is None and rec["basis"] == "no cached daily series"
    # with a cache
    tmp = REPO_ROOT / "data" / "out" / "_test_cache"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        bars.to_parquet(tmp / "FND.parquet", index=False)
        rec = I.since_inception_live("FND", entry, bench, cache_dir=tmp)
    finally:
        (tmp / "FND.parquet").unlink(missing_ok=True)
    years = (dates[-1] - dates[0]).days / 365.25
    assert rec["since_inception_cagr_pct"] == pytest.approx(100 * ((50 / 20) ** (1 / years) - 1), abs=0.01)
    assert rec["max_dd_pct"] == 0.0 and rec["as_of"] == "2026-09-04" and rec["benchmark"] == "vt"
    assert rec["vt_same_window_pct"] is not None
    assert I.max_drawdown_pct(pd.Series([1.0, 2.0, 1.0, 1.5])) == -50.0


def test_manual_levels_compound_full_years_only():
    fund = {"years": [{"year": 2014, "tr_nav": -0.5}, {"year": 2015, "tr_nav": 1.0}, {"year": 2017, "tr_nav": 0.1},
                      {"year": 2018, "tr_nav": 3.0, "reinvestment_artifact": True}]}
    lv = X.manual_levels(fund)
    assert lv["from_year"] == 2013 and lv["levels"] == [1.0, 0.5, 1.0]     # 2016 missing → stops; 2017/2018 not reached
    assert X.manual_levels({"years": []}) is None


def test_instruments_yaml_is_human_editable_and_loads():
    p = I.INSTRUMENTS_YAML
    if not p.exists():
        pytest.skip("evals/instruments.yaml not generated yet")
    text = p.read_text(encoding="utf-8")
    assert text.startswith("#") and "\ngenerated:\n" in text
    doc = I.load_instruments(p)
    assert set(doc) >= {"as_of", "counts", "countries", "baskets"}
    for iso3, c in doc["countries"].items():
        assert c["status"] in ("live", "liquidating", "liquidated", "none")
        assert c["mobility"] in ("open", "restricted", "closed", "not_assessed")
        for t in c["tickers"]:
            assert t["status"] in ("live", "liquidating", "liquidated")
            if t.get("cagr_10y_pct") is not None:
                assert t.get("cagr_10y_vt_pct") is not None, f"{t['ticker']}: a market number without VT"
            if t.get("since_inception_cagr_pct") is not None:
                assert t.get("vt_same_window_pct") is not None or t.get("benchmark", "").startswith("unavailable"), t["ticker"]
    nge = next(t for t in doc["countries"]["NGA"]["tickers"] if t["ticker"] == "NGE")
    assert nge["status"] == "liquidated" and nge["delisted"] == "2024-03-25" and nge["delisted_universe"] == "2023-07-28"
    assert doc["countries"]["NGA"]["mobility"] == "closed" and doc["countries"]["RUS"]["mobility"] == "closed"


# ------------------------------------------------------------------------------------------------ export (pure)
def _tiny():
    ids, years = ["AAA", "BBB"], range(1950, 2025)
    sp = pd.DataFrame({"iso3": np.repeat(ids, 75), "year": np.tile(list(years), 2)})
    sp["gdppc"] = np.where(sp["iso3"] == "AAA", 1000.0 * 1.02 ** (sp["year"] - 1950), np.nan)
    sp["g10"] = np.where(sp["year"] >= 1960, 2.0, np.nan)
    sp["g_rgdp"] = -3.5
    sp["tfr"] = 2.5
    sp["income_class"] = np.where(sp["year"] >= 1989, 3, 0)
    st = pd.DataFrame({"iso3": sp["iso3"], "year": sp["year"], "stage": np.where(sp["year"] >= 1980, 2, 0)})
    return ids, years, sp, st


def test_encode_decode_round_trip_and_sentinels():
    ids, years, sp, st = _tiny()
    arrays = X.encode_arrays(sp, st, ids, years)
    header = {"ids": ids, "year_min": 1950, "year_max": 2024, "arrays": {}}
    off = 0
    for name, (dt, spec) in X.ARRAYS.items():
        header["arrays"][name] = {**spec, "offset": off}
        off += arrays[name].nbytes
    blob = X.pack(header, arrays)
    assert blob[:2] == b"\x1f\x8b"
    h2, arr = X.unpack(blob)
    assert h2["ids"] == ids
    assert arr["gdppc"][0] == pytest.approx(1000.0, rel=1e-3) and arr["gdppc"][74] == pytest.approx(1000 * 1.02 ** 74, rel=1e-3)
    assert np.isnan(arr["gdppc"][75:]).all()                      # BBB has no series
    assert np.isnan(arr["g_rgdp"][0]) and arr["g_rgdp"][10] == pytest.approx(2.0)
    assert arr["g_rgdp_1y"][3] == pytest.approx(-3.5) and arr["tfr"][3] == pytest.approx(2.5)
    assert arr["income"][38] == 0 and arr["income"][39] == 3 and arr["stage"][29] == 0 and arr["stage"][30] == 2
    # deterministic bytes (mtime 0) → stable sha8
    assert X.pack(header, arrays) == blob


def test_guard_text_allows_only_the_class_key():
    assert X.guard_text('{"msci_class":"EM","x":1}') == []
    assert X.guard_text('{"name":"iShares MSCI Japan"}') == ["header names the index provider outside the msci_class key"]
    assert "non-redistributable" in X.guard_text('{"source":"weo-2025-04"}')[0]


def test_register_in_meta_preserves_everything_else(tmp_path):
    p = tmp_path / "meta.json"
    p.write_text('{"a":1,"files":{"years":"x","notice":"n"},"z":"é"}', encoding="utf-8")
    X.register_in_meta(p, "data/wpp2024/econ.deadbeef.ecz")
    assert p.read_text(encoding="utf-8") == '{"a":1,"files":{"years":"x","notice":"n","econ":"data/wpp2024/econ.deadbeef.ecz"},"z":"é"}'
    p.write_text('{"a": 1}\n', encoding="utf-8")     # pretty-printed → refuses rather than reformatting
    with pytest.raises(RuntimeError):
        X.register_in_meta(p, "x")


def test_append_notice_is_idempotent(tmp_path):
    p = tmp_path / "NOTICE"
    p.write_text("base\n", encoding="utf-8")
    assert X.append_notice(p) is True and X.append_notice(p) is False
    assert p.read_text(encoding="utf-8").count("Economic-context series") == 1
    assert not LICENCE_RE.search(X.NOTICE_LINE) and not PROVIDER_RE.search(X.NOTICE_LINE)


# ------------------------------------------------------------------------------------------------ shipped files
@needs_ecz
def test_shipped_econ_file_decodes_within_budget_and_matches_meta():
    p = ECZ[-1]
    blob = p.read_bytes()
    assert len(blob) <= X.SIZE_BUDGET and not p.name.endswith(".gz")
    assert p.name == f"econ.{X.sha8(blob)}.ecz"
    header, arr = X.unpack(blob)
    n = len(header["ids"]) * (header["year_max"] - header["year_min"] + 1)
    assert header["year_min"] == 1950 and header["year_max"] == 2024 and len(header["ids"]) >= 200
    assert all(len(a) == n for a in arr.values())
    assert header["body_bytes"] == sum(a.nbytes for a in [np.zeros(n, dtype={"u16": "<u2", "i16": "<i2", "u8": "<u1"}[s["dtype"]]) for s in header["arrays"].values()])
    assert set(header["arrays"]) >= {"gdppc", "g_rgdp", "tfr", "income", "stage"}
    assert set(np.unique(arr["stage"])) <= {0, 1, 2, 3, 4} and set(np.unique(arr["income"])) <= {0, 1, 2, 3, 4}
    meta = json.loads((WEB_SRC_DATA / "meta.json").read_text(encoding="utf-8"))
    assert meta["files"]["econ"] == f"data/wpp2024/{p.name}"
    ent = json.loads((WEB_SRC_DATA / "econ_entities.json").read_text(encoding="utf-8"))
    assert set(ent) == set(header["ids"])
    has = {i for k, i in enumerate(header["ids"]) if np.isfinite(arr["gdppc"][k * 75:(k + 1) * 75]).any()}
    assert {i for i, v in ent.items() if v["has_econ"]} == has
    for v in ent.values():
        assert set(v) >= {"has_econ", "investability_status", "msci_class"}
    # instruments: every shipped market number carries VT over the identical window; ≤ 40 levels per fund
    vt = header["benchmark"]["vt"]
    assert vt and len(vt["levels"]) >= 20 and header["benchmark"]["vt_first_bar"] == "2008-06-24"
    for iso3, recs in header["instruments"].items():
        for r in recs:
            assert r["status"] in ("live", "liquidating", "liquidated") and r["msci_class"] in ("DM", "EM", "FM", "standalone", "none", None)
            if r["annual"]:
                assert len(r["annual"]["levels"]) <= 40
            if r["stats"].get("cagr_10y_pct") is not None:
                assert r["stats"].get("cagr_10y_vt_pct") is not None, (iso3, r["ticker"])


@needs_ecz
def test_shipped_econ_file_reproduces_the_splice():
    """The file's CHN 1990 cell equals Maddison's 2011$ level and the store's TFR (quantisation ≤ 0.03 %)."""
    if not DB.exists():
        pytest.skip("needs `make build`")
    header, arr = X.unpack(ECZ[-1].read_bytes())
    sp = S.build_splice()
    i = header["ids"].index("CHN")
    row = sp[(sp["iso3"] == "CHN") & (sp["year"] == 1990)].iloc[0]
    c = i * 75 + 40
    assert arr["gdppc"][c] == pytest.approx(row["gdppc"], rel=3e-4) and row["gdppc_flag"] == "maddison"
    assert arr["tfr"][c] == pytest.approx(row["tfr"], abs=1e-3) and arr["income"][c] == row["income_class"]
    assert arr["g_rgdp"][c] == pytest.approx(row["g10"], abs=0.006)


def test_licence_guard_over_shipped_data():
    """Nothing under web/public/data names a non-redistributable source; the econ header names the index provider only
    through the `msci_class` classification key (a label, not a series)."""
    files = [f for f in WEB_DATA.rglob("*") if f.is_file()]
    if not files:
        pytest.skip("nothing exported yet")
    for f in files:
        if f.suffix in (".u16", ".f32", ".f16", ".d16z", ".bin"):
            continue
        data = f.read_bytes()
        if f.suffix == ".ecz":
            raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
            n = int.from_bytes(raw[:4], "little")
            header_json = raw[4:4 + n].decode("utf-8")
            assert X.guard_text(header_json) == [], f.name
            continue
        text = data.decode("utf-8", "ignore")
        assert not LICENCE_RE.search(text), f"{f.relative_to(REPO_ROOT)} names a non-redistributable source"
        assert not PROVIDER_RE.search(text), f"{f.relative_to(REPO_ROOT)} names the index provider"


def test_web_src_data_econ_jsons_are_clean_and_traceable():
    ev_p, dec_p, ui_p = (WEB_SRC_DATA / f"{n}.json" for n in ("evidence", "econ_decision", "ui_sentences"))
    if not (ev_p.exists() and dec_p.exists() and ui_p.exists()):
        pytest.skip("econ web JSONs not exported yet")
    for p in (ev_p, dec_p, ui_p):
        assert not LICENCE_RE.search(p.read_text(encoding="utf-8")), p.name
    decision = json.loads((REPO_ROOT / "evals" / "econ" / "decision.json").read_text(encoding="utf-8"))
    dec = json.loads(dec_p.read_text(encoding="utf-8"))
    assert dec["allowed_sentence_ids"] == sorted(decision["allowed_sentence_ids"]) == ["L0.disconnect", "L0.investability", "L0.null", "L0.vs_vt", "L0.what_happened"]
    assert dec["levels"]["L1"]["granted"] is False and dec["levels"]["L2"]["granted"] is False and dec["prereg_commit"] == decision["prereg_commit"]
    ev = json.loads(ev_p.read_text(encoding="utf-8"))
    bt = json.loads((REPO_ROOT / "evals" / "econ" / "backtest_lookalikes.json").read_text(encoding="utf-8"))
    g = bt["rows"]["B|10|10|growth"]["stats"]
    assert ev["backtest"]["growth"]["mean_excess"] == g["mean_excess"] and ev["backtest"]["growth"]["n_eff"] == g["n_eff"]
    assert ev["backtest"]["growth"]["ci_headline"] == g["ci_headline"]
    assert ev["backtest"]["returns"]["mean_excess_vs_vt"] == bt["rows"]["B|10|10|returns"]["stats"]["mean_excess"]
    assert ev["backtest"]["ew_minus_vt"] == decision["predictions"]["P3b"]["ew_minus_vt_pp_per_yr"]
    chn = next(r for r in ev["disconnect"]["rows"] if r["iso3"] == "CHN" and r["year"] == 1990)
    assert chn["msci"]["ann_pct_gross_since"] == 1.55 and chn["msci"]["max_drawdown_pct_gross"] == 88.63
    assert ev["typology"]["adapted"] is True and ev["typology"]["reproduction_2015"]["named_all_agree"] is True
    assert ev["instruments"]["countries"]["NGA"]["tickers"][0]["delisted"] == "2024-03-25"
    assert all(len(l["findings"]) > 0 and all("verified" in f for f in l["findings"]) for l in ev["links"]) and len(ev["links"]) == 4
    ui = json.loads(ui_p.read_text(encoding="utf-8"))
    src = yaml.safe_load((REPO_ROOT / "evals" / "econ" / "ui_sentences.yaml").read_text(encoding="utf-8"))
    assert ui["deny_list"] == src["deny_list"] and set(ui["sentences"]) == set(src["sentences"])
    deny = [re.compile(r, re.I) for r in src["deny_list"]]
    for l in ev["links"]:
        for f in l["findings"]:
            hits = [d.pattern for d in deny if d.search(f["claim"])]
            assert not hits, (f["claim"], hits)
