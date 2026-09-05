"""Growth windows on toy panels (PREREG §2.1): single-source endpoints, PWT preferred, Maddison
fallback per window, the partial T = 2015 tail, and the committed table round trip."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.econ import data as D


def _panel(rows: list[tuple]) -> pd.DataFrame:
    """rows: (iso3, year, y_pwt, y_maddison) with None for missing."""
    df = pd.DataFrame(rows, columns=["iso3", "year", "y_growth_pwt", "y_growth_maddison"]).astype({"year": int})
    has = df["y_growth_pwt"].notna()
    df["y_growth"] = df["y_growth_pwt"].where(has, df["y_growth_maddison"])
    df["src_growth"] = np.where(has, "pwt", np.where(df["y_growth_maddison"].notna(), "maddison", None))
    df["y_level"], df["src_level"] = df["y_growth"], df["src_growth"]
    return df[D.PANEL_COLS]


def test_growth_is_log_per_year_and_pwt_preferred():
    # AAA doubles in PWT over 10 years (g = ln2/10); Maddison says something else and must be ignored
    rows = [("AAA", 1990, 100.0, 50.0), ("AAA", 2000, 200.0, 60.0)]
    w = D.growth_windows(_panel(rows), 10)
    assert len(w) == 1
    r = w.iloc[0]
    assert (r.iso3, r.t, r.h, r.src, bool(r.partial)) == ("AAA", 1990, 10, "pwt", False)
    assert math.isclose(r.g, math.log(2) / 10)


def test_never_mixes_sources_within_a_window():
    # PWT has 1990 only, Maddison has 2000 only -> NO window (a mixed one would be a bug)
    rows = [("BBB", 1990, 100.0, None), ("BBB", 2000, None, 60.0)]
    assert D.growth_windows(_panel(rows), 10).empty
    # PWT has 1990, Maddison has both -> Maddison window, flagged
    rows = [("CCC", 1990, 100.0, 50.0), ("CCC", 2000, None, 100.0)]
    w = D.growth_windows(_panel(rows), 10)
    assert len(w) == 1 and w.iloc[0].src == "maddison" and math.isclose(w.iloc[0].g, math.log(2) / 10)


def test_fallback_is_per_window_not_per_country():
    # PWT covers 2000-2013 only; Maddison covers 1950-2013. Windows starting before 1990 (ending < 2000)
    # are Maddison, windows fully inside PWT are PWT — same country, both sources, none mixed.
    rows = []
    for y in range(1950, 2024):
        rows.append(("DDD", y, 100.0 * 1.02 ** (y - 2000) if y >= 2000 else None, 80.0 * 1.01 ** (y - 1950)))
    w = D.growth_windows(_panel(rows), 10)
    by_t = w.set_index("t")
    assert by_t.loc[1985, "src"] == "maddison" and math.isclose(by_t.loc[1985, "g"], math.log(1.01))
    assert by_t.loc[1995, "src"] == "maddison"          # PWT lacks 1995 -> Maddison for 1995->2005
    assert by_t.loc[2000, "src"] == "pwt" and math.isclose(by_t.loc[2000, "g"], math.log(1.02))
    assert w["t"].min() == 1950 and w["t"].max() == 2013   # PREREG grid for h = 10
    assert not w["partial"].any()
    # h = 20: t <= 2003
    w20 = D.growth_windows(_panel(rows), 20)
    assert w20["t"].max() == 2003 and w20["h"].eq(20).all()
    assert math.isclose(w20.set_index("t").loc[2003, "g"], math.log(1.02))   # 2003->2023 all PWT


def test_partial_2015_tail_uses_actual_span():
    rows = [("EEE", 2015, 100.0, 10.0), ("EEE", 2022, None, 20.0), ("EEE", 2023, 300.0, None),
            ("FFF", 2015, None, 10.0), ("FFF", 2022, None, 20.0)]
    p = D.partial_windows(_panel(rows))
    p = p.set_index("iso3")
    assert p.loc["EEE", "h"] == 8 and p.loc["EEE", "src"] == "pwt" and math.isclose(p.loc["EEE", "g"], math.log(3) / 8)
    assert p.loc["FFF", "h"] == 7 and p.loc["FFF", "src"] == "maddison" and math.isclose(p.loc["FFF", "g"], math.log(2) / 7)
    assert p["partial"].all()


def test_pop_at_reads_corpus_keys_in_thousands():
    keys = pd.DataFrame({"row": [0, 1], "id": ["CHN", "CHN"], "locid": [156, 156], "year": [1990, 1991],
                         "type": ["country", "country"], "pop_total": [1153704.0, 1170000.0]})
    assert D.pop_at(keys, "CHN", 1990) == 1153704.0
    assert math.isnan(D.pop_at(keys, "CHN", 2000))
    tab = D.pop_table(keys)
    assert tab[("CHN", 1991)] == 1170000.0


def test_table_round_trip_uses_prereg_names(tmp_path, monkeypatch):
    rows = [("GGG", 1990, 100.0, None), ("GGG", 2000, 200.0, None), ("GGG", 2015, 300.0, None), ("GGG", 2023, 330.0, None)]
    panel = _panel(rows)
    monkeypatch.setattr(D, "load_gdp_panel", lambda con=None: panel)
    paths = D.write_tables(tmp_path)
    gdp = pd.read_parquet(paths["gdp_pc"])
    assert list(gdp.columns) == ["iso3", "year", "y_growth_source", "y_level_source", "y_growth", "y_level"]
    win = pd.read_parquet(paths["windows"])
    assert list(win.columns) == ["iso3", "T", "h", "g", "source", "partial"]
    assert set(win["h"]) == {10, 8} and win.loc[win["h"] == 8, "partial"].all()
    g2, w2 = D.read_tables(tmp_path)
    assert {"src_growth", "src_level"} <= set(g2.columns) and {"t", "src"} <= set(w2.columns)


@pytest.mark.skipif(not (D.ECON_EVALS.parent.parent / "data" / "processed" / "explorer.duckdb").exists(),
                    reason="needs the built store")
def test_real_store_smoke():
    panel = D.load_gdp_panel()
    assert set(panel["src_growth"].dropna()) <= {"pwt", "maddison"}
    chn = panel[(panel.iso3 == "CHN") & (panel.year == 1990)].iloc[0]
    assert chn.src_growth == "pwt" and 1500 < chn.y_growth < 1700     # rgdpna/pop, 2021 US$
    w = D.growth_windows(panel, 10)
    assert w["t"].between(1950, 2013).all() and not w.duplicated(["iso3", "t"]).any()
    assert (w[w.iso3 == "CHN"].set_index("t").loc[1990, "g"] * 100) > 8   # China 1990-2000 > 8 %/yr
