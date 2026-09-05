"""scripts/export_econ_ui.py (the Evidence page's schema owner): the RESULTS §1 vintage parser reads the vintage table
only, the returns members carry both units and the SEC-filing last trading day, and the frozen liquidation sentence is
annotated rather than edited."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import yaml

from pyramid_explorer.econ.evidence import load_ui_module
from pyramid_explorer.paths import REPO_ROOT

ECON = REPO_ROOT / "evals" / "econ"
needs_results = pytest.mark.skipif(not (ECON / "RESULTS.md").exists(), reason="needs `make backtest`")

SYNTHETIC = """# RESULTS

## 1. Data vintages and fetch dates

| source | family | vintage | licence | shipped | fetched | sha256 |
|---|---|---|---|---|---|---|
| curated | curated | — | MIT | yes | — | — |
| pwt-11.0 | pwt | 11.0 | CC BY 4.0 | yes | 2026-09-04 | 7b337e94f39d |
| weo-2025-04 | weo | 2025-04 | IMF terms of use (no redistribution) | no | 2026-09-04 | 4a5bb1b5ab9a |

Growth series: PWT. T = 2015 growth windows are partial (PWT h = 8 → 2023, Maddison h = 7 → 2022) and flagged.

| candidate set C(T) | 1990 | 1995 | 2000 | 2005 | 2010 | 2015 |
|---|---|---|---|---|---|---|
| 10, growth | 148 | 150 | 151 | 152 | 156 | 157 |
| 10, returns | — | — | 151 | 152 | 156 | 157 |

## 2. Next
"""


def test_results_vintages_reads_the_vintage_table_only():
    ui = load_ui_module()
    rows = ui.results_vintages(SYNTHETIC)
    assert [r["source"] for r in rows] == ["curated", "pwt-11.0", "weo-2025-04"]
    assert all(r["family"] in ui.VINTAGE_FAMILIES for r in rows)
    assert ui.results_partial_note(SYNTHETIC) == "PWT h = 8 → 2023, Maddison h = 7 → 2022"
    # a row with an unknown family is refused, never shipped as a vintage
    bad = SYNTHETIC.replace("| curated | curated |", "| 10, growth | 148 |")
    with pytest.raises(ValueError, match="unknown family"):
        ui.results_vintages(bad)


@needs_results
def test_results_vintages_on_the_recorded_run():
    ui = load_ui_module()
    rows = ui.results_vintages((ECON / "RESULTS.md").read_text(encoding="utf-8"))
    assert len(rows) == 8 and {r["family"] for r in rows} <= ui.VINTAGE_FAMILIES
    assert sum(r["shipped"] == "yes" for r in rows) == 7 and [r for r in rows if r["shipped"] == "no"][0]["family"] == "weo"
    assert not any(r["source"].startswith(("10,", "20,")) for r in rows)


@needs_results
def test_returns_members_carry_both_units_and_the_filing_date():
    ui = load_ui_module()
    bt = ui.load_json(ECON / "backtest_lookalikes.json")
    manual = ui.load_yaml(ECON / "etf_manual.yaml")
    row = ui.returns_row(bt, ui.PRIMARY_RETURNS, manual)
    nge = next(m for t in row["per_T"] for m in t["picks"] if m["ticker"] == "NGE")
    assert math.isclose(nge["r_cagr"], 100 * (math.exp(nge["r_pp"] / 100) - 1))
    assert round(nge["r_pp"], 2) == -7.34 and round(nge["r_vt_pp"], 2) == 11.12  # RESULTS §8
    assert round(nge["r_cagr"], 1) == -7.1 and round(nge["r_vt_cagr"], 1) == 11.8  # the L0.vs_vt sentence
    assert nge["delisted_universe"] == "2023-07-28" and nge["last_trading_day"] == "2024-03-25"
    t2015 = next(t for t in row["per_T"] if t["T"] == 2015)
    assert math.isclose(t2015["r_vt_cagr"], nge["r_vt_cagr"])


@needs_results
def test_rendered_notes_annotate_the_frozen_liquidation_date():
    ui = load_ui_module()
    decision = ui.load_json(ECON / "decision.json")
    universe = ui.load_yaml(ECON / "etf_universe.yaml")
    manual = ui.load_yaml(ECON / "etf_manual.yaml")
    notes = ui.rendered_notes({k: ui.uniq(v) for k, v in decision["rendered"].items()}, universe, manual)
    assert notes == [{"sentence": "NGE was liquidated on 2023-07-28 (issuer notice).", "ticker": "NGE", "universe_date": "2023-07-28", "last_trading_day": "2024-03-25"}]


@needs_results
def test_disconnect_rows_name_the_level_series_and_carry_totals():
    ui = load_ui_module()
    dc = ui.load_json(ECON / "disconnect.json")
    ls = ui.load_level_sources(ECON / "tables" / "gdp_pc.parquet")
    rows = ui.disconnect_rows(dc, ls)
    chn = next(r for r in rows if r["iso3"] == "CHN" and r["year"] == 1990)
    assert chn["levels"]["source"] == "PWT 11.0 rgdpe/pop, 2017 PPP $"
    twn = next(r for r in rows if r["iso3"] == "TWN" and r["year"] == 1970)
    assert twn["fund"]["too_short_to_annualise"] and round(twn["fund"]["vt_total_log"], 4) == -0.0902
    assert math.isclose(twn["fund"]["vt_total_pct"], 100 * (math.exp(twn["fund"]["vt_total_log"]) - 1))
