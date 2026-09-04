"""Econ loaders (F): remap rules, loader parsing on tiny fixtures, manifest bookkeeping.

Network-free by default; real raw files under data/raw/econ/ add coverage checks when present.
"""
from __future__ import annotations

import json

import openpyxl
import pandas as pd
import pytest

from pyramid_explorer.data import econ_iso3, econ_manifest, imf, maddison, pwt, wdi

LONG_COLS = ["code", "year", "indicator_id", "value", "is_forecast"]
IDS = {"CHN", "XKX", "PSE", "USA", "JPN"}


def _long(rows: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["code", "year", "indicator_id", "value"])
    df["is_forecast"] = False
    return df


# --- econ_iso3 ------------------------------------------------------------------------------

def test_rules_cover_every_family():
    rules = econ_iso3.load_rules()
    assert set(rules) == set(econ_iso3.FAMILIES)
    assert rules["weo"]["remap"] == {"UVK": "XKX", "WBG": "PSE"}
    assert set(rules["maddison"]["drop"]) == {"CSK", "SUN", "YUG"}
    assert "CHI" in rules["wdi"]["drop"]
    for fam, r in rules.items():
        assert set(r["drop"]) <= set(r["expected_orphans"]), fam


def test_apply_remap_maps_drops_and_records_orphans():
    df = _long([("UVK", 2000, "x", 1.0), ("WBG", 2000, "x", 2.0), ("CHN", 2000, "x", 3.0)])
    mapped, orphans = econ_iso3.apply_remap(df, "weo", ids=IDS)
    assert list(mapped["entity_id"]) == ["XKX", "PSE", "CHN"]
    assert list(mapped["code"]) == ["UVK", "WBG", "CHN"]          # upstream code untouched
    assert orphans.empty

    df = _long([("CSK", 1950, "g", 1.0), ("CSK", 1990, "g", 2.0), ("CHN", 1990, "g", 3.0)])
    mapped, orphans = econ_iso3.apply_remap(df, "maddison", ids=IDS)
    assert set(mapped["entity_id"]) == {"CHN"}
    assert orphans.to_dict("records") == [
        {"code": "CSK", "reason": "drop", "n_rows": 2, "first_year": 1950, "last_year": 1990}]


def test_apply_remap_unknown_code_is_strict_by_default():
    df = _long([("ZZZ", 2000, "x", 1.0), ("CHN", 2000, "x", 3.0)])
    with pytest.raises(ValueError, match="ZZZ"):
        econ_iso3.apply_remap(df, "pwt", ids=IDS)
    mapped, orphans = econ_iso3.apply_remap(df, "pwt", ids=IDS, strict=False)
    assert list(mapped["entity_id"]) == ["CHN"]
    assert orphans.iloc[0][["code", "reason"]].tolist() == ["ZZZ", "unknown"]


def test_entity_ids_from_export_not_hardcoded():
    ids = econ_iso3.entity_ids()
    assert {"CHN", "TWN", "XKX", "PSE", "TGO"} <= ids
    assert all(isinstance(i, str) for i in ids)


# --- loaders on fixtures --------------------------------------------------------------------

def _xlsx(path, sheet, header, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_maddison_load_long(tmp_path):
    f = tmp_path / "mpd.xlsx"
    _xlsx(f, maddison.SHEET, ["countrycode", "country", "region", "year", "gdppc", "pop"],
          [("CHN", "China", "East Asia", 1, None, None), ("CHN", "China", "East Asia", 1990, 1500.5, 1150000),
           ("CSK", "Czechoslovakia", "Europe", 1990, 9000, None)])
    long = maddison.load_long(f)
    assert list(long.columns) == LONG_COLS
    assert set(long["indicator_id"]) == {"gdppc_maddison", "pop_maddison"}
    assert len(long) == 3 and not long["is_forecast"].any()
    assert long.set_index(["code", "indicator_id", "year"])["value"]["CHN", "gdppc_maddison", 1990] == 1500.5


def test_pwt_load_long(tmp_path):
    f = tmp_path / "pwt.xlsx"
    _xlsx(f, pwt.SHEET, ["countrycode", "country", "year", "rgdpe", "rgdpna", "pop", "emp", "hc", "avh"],
          [("CHN", "China", 1990, 1e6, 1.1e6, 1150.0, 600.0, 1.9, 2000.0),
           ("CHN", "China", 1991, None, None, 1160.0, None, None, None)])
    long = pwt.load_long(f)
    assert list(long.columns) == LONG_COLS
    assert set(long["indicator_id"]) == {"rgdpna_pwt", "rgdpe_pwt", "pop_pwt", "hc_pwt", "emp_pwt"}
    assert len(long) == 6                      # 5 in 1990 + pop in 1991; NaNs dropped
    assert long.query("year == 1991")["indicator_id"].tolist() == ["pop_pwt"]


def _wdi_page(code, obs):
    return [{"page": 1, "pages": 1, "per_page": 20000, "total": len(obs)},
            [{"indicator": {"id": code}, "country": {"id": o[0]}, "countryiso3code": o[0], "date": str(o[1]),
              "value": o[2]} for o in obs]]


def test_wdi_load_long_drops_aggregates_and_nulls(tmp_path):
    (tmp_path / "countries.json").write_text(json.dumps([[{"page": 1, "pages": 1}, [
        {"id": "CHN", "region": {"value": "East Asia & Pacific"}},
        {"id": "WLD", "region": {"value": "Aggregates"}},
        {"id": "CHI", "region": {"value": "Europe & Central Asia"}}]]]))
    for code in wdi.INDICATORS:
        (tmp_path / f"{code}.json").write_text(json.dumps([_wdi_page(code, [
            ("CHN", 1990, 1.5), ("CHN", 1991, None), ("WLD", 1990, 9.0), ("CHI", 1990, 2.0)])]))
    long = wdi.load_long(tmp_path)
    assert list(long.columns) == LONG_COLS
    assert set(long["code"]) == {"CHN", "CHI"} and len(long) == 2 * len(wdi.INDICATORS)
    assert set(long["indicator_id"]) == set(wdi.INDICATORS.values())
    mapped, orphans = econ_iso3.apply_remap(long, "wdi", ids=IDS)
    assert set(mapped["entity_id"]) == {"CHN"} and orphans["code"].tolist() == ["CHI"]


def test_oghist_load_long(tmp_path):
    f = tmp_path / "OGHIST.xlsx"
    _xlsx(f, wdi.OGHIST_SHEET, [None, "World Bank Analytical Classifications"], [
        (None, "Bank's fiscal year:", "FY89", "FY90", "FY91", "FY92"),
        (None, "Data for calendar year :", 1987, 1988, 1989, 1990),
        (None, "Low income (L)", "<= 480", "<= 545", "<= 580", "<= 610"),
        ("CHN", "China", "L", "L", "LM*", "UM"),
        ("ALB", "Albania", "..", None, "L", "UM")])
    long = wdi.load_income_long(f)
    assert list(long.columns) == LONG_COLS
    assert set(long["indicator_id"]) == {"income_class_wb"}
    chn = long[long["code"] == "CHN"].set_index("year")["value"]
    assert chn.to_dict() == {1989: 1.0, 1990: 1.0, 1991: 2.0, 1992: 3.0}     # FY -> fiscal year, '*' ignored
    assert long[long["code"] == "ALB"]["year"].tolist() == [1991, 1992]         # '..' and blanks skipped


def test_oghist_non_contiguous_header_raises(tmp_path):
    f = tmp_path / "OGHIST.xlsx"
    _xlsx(f, wdi.OGHIST_SHEET, [None, "x"], [(None, "Bank's fiscal year:", "FY89", "FY91"), ("CHN", "China", "L", "L")])
    with pytest.raises(ValueError, match="contiguous"):
        wdi.load_income_long(f)


def test_weo_load_long_marks_forecasts(tmp_path):
    f = tmp_path / "weo.parquet"
    pd.DataFrame({"iso3": ["UVK", "UVK", "CHN"], "year": [2024, 2025, 1990],
                  "indicator": ["gdp_pc_ppp", "gdp_pc_ppp", "real_gdp_growth"],
                  "value": [15000.0, 15500.0, 3.9], "vintage": "2025-04"}).to_parquet(f)
    long = imf.load_long(f)
    assert list(long.columns) == LONG_COLS
    assert long["indicator_id"].tolist() == ["real_gdp_growth_weo", "gdppc_ppp_weo", "gdppc_ppp_weo"]  # sorted by code
    assert long["is_forecast"].tolist() == [False, False, True]
    assert imf.REDISTRIBUTABLE is False
    mapped, _ = econ_iso3.apply_remap(long, "weo", ids=IDS)
    assert set(mapped["entity_id"]) == {"XKX", "CHN"} and set(mapped["code"]) == {"UVK", "CHN"}


def test_weo_to_long_honours_vintage_last_actual_year():
    raw = pd.DataFrame({"iso3": ["CHN", "CHN"], "year": [2023, 2024], "indicator": ["gdp_usd", "gdp_usd"],
                        "value": [17.0, 18.0], "vintage": "2024-04"})
    long = imf.to_long(raw, last_actual_year=2023)
    assert long["indicator_id"].tolist() == ["gdp_usd_weo"] * 2 and long["is_forecast"].tolist() == [False, True]


# --- manifest -------------------------------------------------------------------------------

def test_manifest_record_is_idempotent(tmp_path):
    raw = econ_manifest.DATA_RAW / "econ" / "_test_manifest.bin"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"abc")
    m = tmp_path / "m.json"
    try:
        e1 = econ_manifest.record("t", raw, url="u", source="t", licence="l", redistributable=True, path=m)
        e1 = {**e1, "fetched_at": "2000-01-01"}
        m.write_text(json.dumps({"t": e1}))
        e2 = econ_manifest.record("t", raw, url="u", source="t", licence="l", redistributable=True, path=m)
        assert e2["fetched_at"] == "2000-01-01" and e2["bytes"] == 3        # same sha -> date kept
        raw.write_bytes(b"abcd")
        e3 = econ_manifest.record("t", raw, url="u", source="t", licence="l", redistributable=True, path=m)
        assert e3["fetched_at"] != "2000-01-01" and e3["sha256"] != e2["sha256"]
        assert econ_manifest.verify("t", path=m)
    finally:
        raw.unlink()


# --- real raw files (present after `make data`) --------------------------------------------

@pytest.mark.skipif(not maddison.FILE.exists(), reason="run scripts/fetch_econ.py first")
def test_real_maddison_orphans_are_exactly_the_allowlist():
    mapped, orphans = econ_iso3.apply_remap(maddison.load_long(), "maddison")
    assert set(orphans["code"]) == {"CSK", "SUN", "YUG"}
    assert set(mapped["entity_id"]) <= econ_iso3.entity_ids()
    assert mapped.query("entity_id == 'CHN' and indicator_id == 'gdppc_maddison' and year == 1990")["value"].item() == pytest.approx(2982, abs=1)


@pytest.mark.skipif(not (wdi.WDI_DIR / "countries.json").exists() or not imf.FILE.exists(),
                    reason="run scripts/fetch_econ.py first")
def test_real_wdi_weo_all_codes_accounted_for():
    for family, long in (("wdi", wdi.load_long()), ("oghist", wdi.load_income_long()), ("weo", imf.load_long())):
        mapped, orphans = econ_iso3.apply_remap(long, family)
        assert len(mapped) + orphans["n_rows"].sum() == len(long), family
        assert set(mapped["entity_id"]) <= econ_iso3.entity_ids(), family
    chn = wdi.load_income_long().query("code == 'CHN'")["year"]
    assert chn.tolist() == list(range(1989, chn.max() + 1))    # FY18-21 formula headers parsed via cached values
    assert econ_manifest.load_manifest()[imf.SOURCE]["redistributable"] is False


@pytest.mark.network
def test_fetch_maddison_smoke():
    f = maddison.fetch()
    assert f.exists() and econ_manifest.verify(maddison.SOURCE)
    assert {"gdppc_maddison", "pop_maddison"} == set(maddison.load_long(f)["indicator_id"])
