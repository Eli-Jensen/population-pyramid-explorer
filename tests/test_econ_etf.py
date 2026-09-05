"""Survivorship guard, clipping, window maths, liquidation compounding, VT proxy legs (PREREG §3.4–3.5,
§6, §9) — all on synthetic fixtures; no network (the live fetch is exercised by scripts/fetch_etf.py)."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.econ import etf as E

TODAY = pd.Timestamp("2026-09-04")


def _bars(start: str, n: int | None = None, *, end: str | None = None, price: float = 100.0, growth: float = 0.0) -> pd.DataFrame:
    """Business-day bars: ``n`` of them from ``start``, or ``start``..``end`` inclusive."""
    dates = pd.bdate_range(start, end) if end else pd.bdate_range(start, periods=n)
    n = len(dates)
    p = price * np.exp(growth * np.arange(n) / 252)
    return pd.DataFrame({"date": dates, "adjclose": p, "close": p, "volume": 1000.0})


def _entry(ticker="XXX", inception="2010-01-04", delisted=None, role="single_country", iso3="XXX", status="live"):
    return {"ticker": ticker, "yahoo_symbol": ticker, "inception": pd.Timestamp(inception),
            "delisted": pd.Timestamp(delisted) if delisted else pd.NaT, "role": role, "iso3": iso3,
            "status": status if not delisted else "liquidated"}


# ------------------------------------------------------------------------------------------------ universe
def test_universe_loads_with_yahoo_symbol_default_and_dates():
    u = E.load_universe()
    assert len(u) == 55 and u["role"].value_counts().to_dict() == {"single_country": 48, "benchmark": 6, "basket": 1}
    assert u.loc["GXG", "yahoo_symbol"] == "COLO" and u.loc["EWJ", "yahoo_symbol"] == "EWJ"
    assert u["is_delisted"].sum() == 6 and set(u.index[u["is_delisted"]]) == {"ERUS", "FM", "EGPT", "RSX", "NGE", "PAK"}
    assert u.loc["VT", "inception"] == E.VT_INCEPTION and pd.isna(u.loc["VT", "delisted"])


# ------------------------------------------------------------------------------------------------ guard
def test_nge_one_bar_signature_is_the_asserted_refusal():
    nge = _entry("NGE", "2013-04-02", delisted="2023-07-28")
    one = pd.DataFrame({"date": [pd.Timestamp("2024-03-25")], "adjclose": [5.0]})
    assert E.signature(one) == "one_bar"
    assert E.guard(one, nge, TODAY) == []                     # refused as asserted -> manual ladder


def test_erus_no_data_signature_is_also_a_refusal():
    erus = _entry("ERUS", "2010-11-09", delisted="2022-08-17")
    empty = pd.DataFrame(columns=["date", "adjclose"])
    assert E.signature(empty) == "no_data"
    assert E.guard(empty, erus, TODAY) == []


def test_delisted_with_a_served_series_trips_a4_and_looks_live_when_recent():
    nge = _entry("NGE", "2013-04-02", delisted="2023-07-28")
    dead = _bars("2013-04-02", 2768)                            # ends 2023-12 -> well before today
    assert E.guard(dead, nge, TODAY) == [E.A4_NOT_REFUSED]
    live_looking = _bars("2013-04-02", end="2026-09-03")        # runs to yesterday
    assert E.guard(live_looking, nge, TODAY) == [E.A4_NOT_REFUSED, E.A4_LOOKS_LIVE]


def test_live_300_bar_fixture_passes_and_one_bar_fails_a1_a3():
    e = _entry(inception="2025-06-02")
    ok = _bars("2025-06-02", end="2026-09-04")                  # ~330 bars
    assert ok["date"].iloc[-1] >= TODAY - pd.Timedelta(days=10)
    assert E.guard(ok, e, TODAY) == []
    one = ok.iloc[[0]]
    assert set(E.guard(one, e, TODAY)) == {E.A1, E.A3}


def test_first_bar_slack_and_gap_assertions():
    e = _entry(inception="2010-01-04")
    late = _bars("2010-03-01", end="2026-09-04")                # first bar 56 d after inception
    assert E.guard(late, e, TODAY) == [E.A2]
    fine = _bars("2010-02-10", end="2026-09-04")                # 37 d: inside the 45 d slack
    assert E.guard(fine, e, TODAY) == []
    gap = _bars("2010-01-04", end="2026-09-04")
    gap = gap[(gap["date"] < "2015-01-01") | (gap["date"] > "2015-03-05")]   # a ~63-day hole
    assert E.guard(gap, e, TODAY) == [E.A5]
    stale = _bars("2010-01-04", end="2025-05-30")               # yaml says live: disagreement
    assert E.guard(stale, e, TODAY) == [E.A3]


def test_clipping_drops_before_inception_and_after_delisting_never_the_reverse():
    norw = _entry("NORW", "2010-11-09")
    bars = _bars("2009-08-19", end="2026-09-04")
    clipped = E.clip_to_yaml(bars, norw)
    assert clipped["date"].iloc[0] == pd.Timestamp("2010-11-09")
    assert E.guard(bars, norw, TODAY) == []                     # early history is not a violation (A2 is '<=')
    pak = _entry("PAK", "2015-04-22", delisted="2024-02-16")
    tail = _bars("2015-04-22", 2600)
    assert E.clip_to_yaml(tail, pak)["date"].iloc[-1] <= pd.Timestamp("2024-02-16")


def test_fetch_prices_routes_and_raises(tmp_path, monkeypatch):
    u = E.load_universe()
    calls: list[str] = []

    def fake_download(symbol: str, **kw):
        calls.append(symbol)
        if symbol == "ERUS":
            return pd.DataFrame(columns=["date", "adjclose", "close", "volume"])
        if symbol == "NGE":
            return _bars("2013-04-02", 2768)
        if symbol == "PAK":
            return pd.DataFrame({"date": [pd.Timestamp("2025-06-11")], "adjclose": [20.0], "close": [20.0], "volume": [0.0]})
        if symbol == "COLO":
            return _bars("2009-02-09", 4600)
        return _bars("2010-05-07", 4300)

    monkeypatch.setattr(E, "_download_raw", fake_download)
    report = tmp_path / "report.json"
    kw = dict(today=TODAY, cache_dir=tmp_path, report_path=report, universe=u)
    # refused (no data) -> empty frame, manual route, cached so the second call does not download
    out = E.fetch_prices("ERUS", **kw)
    assert out.empty and out.attrs["route"] == "manual"
    E.fetch_prices("ERUS", **kw)
    assert calls.count("ERUS") == 1
    # one stale bar -> manual route too
    assert E.fetch_prices("PAK", **kw).attrs["route"] == "manual"
    # a served dead series: fails by default, recorded deviation with dead_series='ok', never returns prices
    with pytest.raises(E.EtfGuardError) as ei:
        E.fetch_prices("NGE", **kw)
    assert ei.value.assertion == E.A4_NOT_REFUSED
    out = E.fetch_prices("NGE", dead_series="ok", **kw)
    assert out.empty and out.attrs["route"] == "manual"
    rec = E.guard_report()["NGE"]
    assert rec["deviation"] and rec["violations"] == [E.A4_NOT_REFUSED] and rec["fatal"] == [] and rec["passed"]
    # live ticker via its yahoo_symbol, clipped to inception
    out = E.fetch_prices("GXG", **kw)
    assert calls[-1] == "COLO" and out["date"].iloc[0] >= pd.Timestamp("2009-02-05") and out.attrs["route"] == "yahoo"
    # a live fund whose first bar is far too late (EIDO inception 2010-05-05; fixture starts 2010-05-07: fine)
    assert E.fetch_prices("EIDO", **kw).shape[0] > 250
    rep = json.loads(report.read_text())
    assert {"ERUS", "PAK", "NGE", "GXG", "EIDO"} <= set(rep["tickers"]) and rep["tickers"]["ERUS"]["signature"] == "no_data"


# ------------------------------------------------------------------------------------------------ window maths
def _synthetic_universe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["yahoo_symbol"] = df["ticker"]
    df["inception"] = pd.to_datetime(df["inception"])
    df["delisted"] = pd.to_datetime(df.get("delisted"))
    df["is_delisted"] = df["delisted"].notna()
    return df.set_index("ticker", drop=False).rename_axis(None)


def _install_prices(monkeypatch, prices: dict[str, pd.DataFrame]):
    def fake_fetch(ticker, **kw):
        p = prices[ticker][["date", "adjclose"]].reset_index(drop=True)
        p.attrs["route"] = "yahoo"
        return p
    monkeypatch.setattr(E, "fetch_prices", fake_fetch)


def test_window_return_maths_on_synthetic_path(monkeypatch):
    # SPY calendar + a fund growing at exactly 7 %/yr (log) with one 30 % drawdown inside the window
    cal = _bars("1993-01-29", 9000)
    fund = _bars("2000-07-10", 7000, price=50.0, growth=0.07)
    fund.loc[(fund["date"] > "2008-06-01") & (fund["date"] < "2009-03-01"), "adjclose"] *= 0.7
    u = _synthetic_universe([{"ticker": "SPY", "iso3": "USA", "role": "benchmark", "inception": "1993-01-22", "status": "live"},
                             {"ticker": "FND", "iso3": "BRA", "role": "single_country", "inception": "2000-07-10", "status": "live"}])
    _install_prices(monkeypatch, {"SPY": cal, "FND": fund})
    entry, exit = pd.Timestamp("2000-12-29"), pd.Timestamp("2010-12-31")
    w = E.window_return("FND", entry, exit, universe=u)
    assert w["status"] == "ok"
    assert w["entry_used"] <= entry and w["exit_used"] <= exit
    n_between = len(fund[(fund["date"] > w["entry_used"]) & (fund["date"] <= w["exit_used"])])
    assert math.isclose(w["r_log"], 0.07 * n_between / 252, rel_tol=1e-9)          # ln(p_exit / p_entry)
    years = (w["exit_used"] - w["entry_used"]).days / 365.25
    assert math.isclose(w["r_ann"], w["r_log"] / years) and 9.9 < years < 10.1
    assert -0.30 <= w["max_dd"] < -0.29                         # the 30 % shock, slightly offset by drift inside it
    # inception after entry -> no_fund_at_entry, and the fund's first day itself is investable
    assert E.window_return("FND", pd.Timestamp("2000-06-30"), exit, universe=u)["status"] == "no_fund_at_entry"
    # entry more than 5 trading days after the fund's last bar before it -> not_investable
    gappy = fund[(fund["date"] < "2000-12-15") | (fund["date"] > "2001-01-15")]
    _install_prices(monkeypatch, {"SPY": cal, "FND": gappy})
    assert E.window_return("FND", entry, exit, universe=u)["status"] == "not_investable"


def _ladder(ticker: str, years: dict[int, float], liq: tuple[str, float] | None = None) -> pd.DataFrame:
    rows = [{"ticker": ticker, "year": y, "tr_nav": v, "source_url": "u", "kind": "calendar_year",
             "date_from": pd.Timestamp(f"{y}-01-01"), "date_to": pd.Timestamp(f"{y}-12-31"), "derived": False, "method": "ncsr_fh", "note": None}
            for y, v in years.items()]
    if liq:
        d = pd.Timestamp(liq[0])
        rows.append({"ticker": ticker, "year": d.year, "tr_nav": liq[1], "source_url": "u", "kind": "liquidation",
                     "date_from": pd.Timestamp(f"{d.year}-01-01"), "date_to": d, "derived": True, "method": "derived", "note": None})
    return pd.DataFrame(rows, columns=E.LADDER_COLS)


def test_liquidation_compounds_to_nav_then_zero_cash(monkeypatch):
    u = _synthetic_universe([{"ticker": "DED", "iso3": "NGA", "role": "single_country", "inception": "2013-04-02",
                              "delisted": "2023-07-28", "status": "liquidated"}])
    ladder = _ladder("DED", {2016: 0.10, 2017: -0.20, 2018: 0.05, 2019: 0.0, 2020: 0.0, 2021: 0.0, 2022: -0.5, 2023: 0.0},
                     liq=("2023-07-28", -0.10))
    monkeypatch.setattr(E, "fetch_prices", lambda *a, **k: pd.DataFrame(columns=["date", "adjclose"]))
    entry, exit = pd.Timestamp("2015-12-31"), pd.Timestamp("2025-12-31")
    w = E.window_return("DED", entry, exit, ladder=ladder, funds={}, universe=u)
    # 2016..2022 calendar years, then the 2023 stub to the liquidation date, then cash at 0 %
    gross = 1.10 * 0.80 * 1.05 * 1.0 * 1.0 * 1.0 * 0.5 * 0.90
    assert w["status"] == "liquidated_in_window" and math.isclose(w["gross"], gross) and w["liquidated_in_window"]
    assert math.isclose(w["r_ann"], math.log(gross) / ((exit - entry).days / 365.25))
    assert w["last_fund_day"] == pd.Timestamp("2023-07-28") and w["max_dd_basis"] == "annual_nav_ladder"
    assert math.isclose(w["max_dd"], gross / 1.10 - 1)                  # peak after 2016, trough at the end
    # a window that ends before the liquidation is plain 'manual'
    w2 = E.window_return("DED", entry, pd.Timestamp("2018-12-31"), ladder=ladder, funds={}, universe=u)
    assert w2["status"] == "manual" and math.isclose(w2["gross"], 1.10 * 0.80 * 1.05) and not w2["incomplete"]
    # a missing year is never a silent drop: value carried flat, status manual_incomplete, span listed
    w3 = E.window_return("DED", pd.Timestamp("2014-12-31"), exit, ladder=ladder, funds={}, universe=u)
    assert w3["status"] == "manual_incomplete" and w3["incomplete"] == ["2015-01-01..2015-12-31 (calendar year not transcribed)"]
    assert math.isclose(w3["gross"], gross)
    # no rows at all for the ticker -> error
    with pytest.raises(E.EtfGuardError) as ei:
        E.window_return("DED", entry, exit, ladder=ladder[ladder.ticker == "ZZZ"], funds={}, universe=u)
    assert ei.value.assertion == "manual_ladder_missing"


def test_e3_funds_layout_partial_stub_and_cash_ladder(tmp_path):
    y = tmp_path / "m.yaml"
    y.write_text("""
funds:
  - ticker: NGE
    inception: "2013-04-02"
    last_trading_day: "2024-03-25"
    liquidation_date: "2024-03-29"
    years:
      - {year: 2022, tr_nav: -0.0656, method: 485bpos_bar, source_url: "https://a"}
      - {year: 2023, tr_nav: -0.2727, method: 485bpos_bar, source_url: "https://a"}
    partial_periods:
      - {period: "2013-04-02..2013-12-31", tr_nav: null, derived: false, method: null, source_url: null}
      - {period: "2024-01-01..2024-01-31", tr_nav: 0.09131, derived: false, method: nport_month, source_url: "https://b"}
  - ticker: EGPT
    last_trading_day: "2024-03-21"
    liquidation_date: "2024-03-28"
    years:
      - {year: 2023, tr_nav: 0.2478, method: ncsr_fh, source_url: "https://c"}
    partial_periods:
      - {period: "2024-01-01..2024-03-28", tr_nav: -0.1084, derived: true, method: derived, source_url: "https://c"}
  - ticker: ERUS
    last_trading_day: "2022-03-03"
    liquidation_date: null
    years:
      - {year: 2020, tr_nav: 0.10, source_url: "https://e"}
      - {year: 2021, tr_nav: 0.20, source_url: "https://e"}
      - {year: 2022, tr_nav: -0.99844, source_url: "https://e"}
      - {year: 2023, tr_nav: null, source_url: null}
    cash_ladder:
      distributions_total_to_date: 4.098728
      residual_nav_2026_09_03: 0.0352
  - ticker: FM
    last_trading_day: "2025-01-06"
    liquidation_date: "2025-01-09"
    liquidation_nav: 27.234261
    years:
      - {year: 2023, tr_nav: 0.10, source_url: "https://f"}
    partial_periods:
      - {period: "2024-01-01..2024-11-30", tr_nav: 0.06751, derived: true, method: nport_compound, source_url: "https://f"}
      - {period: "2025-01-01..2025-01-09", tr_nav: null, derived: false, method: null, source_url: null}
  - ticker: RSX
    last_trading_day: "2022-03-03"
    liquidation_date: null
    years:
      - {year: 2020, tr_nav: 0.10, source_url: "https://d"}
      - {year: 2021, tr_nav: 0.20, source_url: "https://d"}
      - {year: 2022, tr_nav: -0.9862, source_url: "https://d"}
      - {year: 2023, tr_nav: 2.9665, source_url: "https://d", reinvestment_artifact: true}
    cash_ladder:
      nav_2021_12_31: 26.75
      nav_2022_12_31: 0.37
      distributions_total_to_date: 1.6051
      residual_nav_2025_12_31: 0.34
""")
    lad, funds = E.manual_ladder(y), E.manual_funds(y)
    assert set(lad["ticker"]) == {"NGE", "EGPT", "RSX", "ERUS", "FM"} and funds["NGE"]["last_trading_day"] == pd.Timestamp("2024-03-25")
    nge = lad[lad.ticker == "NGE"]
    assert list(nge["kind"]) == ["partial", "calendar_year", "calendar_year", "partial"]     # the Jan-2024 stub stops early
    assert math.isnan(nge[nge.year == 2013]["tr_nav"].iloc[0])
    eg = lad[(lad.ticker == "EGPT") & (lad.kind == "liquidation")]
    assert len(eg) == 1 and eg["date_to"].iloc[0] == pd.Timestamp("2024-03-28")
    u = _synthetic_universe([{"ticker": "NGE", "iso3": "NGA", "role": "single_country", "inception": "2013-04-02", "delisted": "2023-07-28", "status": "liquidated"},
                             {"ticker": "EGPT", "iso3": "EGY", "role": "single_country", "inception": "2010-02-16", "delisted": "2024-03-21", "status": "liquidated"},
                             {"ticker": "RSX", "iso3": "RUS", "role": "single_country", "inception": "2007-04-24", "delisted": "2023-01-12", "status": "liquidating"},
                             {"ticker": "ERUS", "iso3": "RUS", "role": "single_country", "inception": "2010-11-09", "delisted": "2022-08-17", "status": "liquidating"},
                             {"ticker": "FM", "iso3": None, "role": "basket", "inception": "2012-09-12", "delisted": "2025-01-06", "status": "liquidated"}])
    import pyramid_explorer.econ.etf as EE
    orig = EE.fetch_prices
    EE.fetch_prices = lambda *a, **k: pd.DataFrame(columns=["date", "adjclose"])
    try:
        # NGE: the ladder's 2024-03-25 close (not the frozen universe's 2023-07-28) is the fund end; 2023 is a full year;
        # Feb-Mar 2024 not transcribed -> manual_incomplete, value carried through January
        w = E.window_return("NGE", pd.Timestamp("2021-12-31"), pd.Timestamp("2031-12-31"), ladder=lad, funds=funds, universe=u)
        assert w["status"] == "manual_incomplete" and w["last_fund_day"] == pd.Timestamp("2024-03-29")
        assert math.isclose(w["gross"], (1 - 0.0656) * (1 - 0.2727) * 1.09131) and w["liquidated_in_window"]
        assert w["incomplete"] == ["2024-01-31..2024-03-29 (final stub not transcribed)"]
        # EGPT: complete through the derived final stub
        w = E.window_return("EGPT", pd.Timestamp("2022-12-31"), pd.Timestamp("2032-12-31"), ladder=lad, funds=funds, universe=u)
        assert w["status"] == "liquidated_in_window" and math.isclose(w["gross"], 1.2478 * (1 - 0.1084))
        # RSX: 2020, 2021 compounded, then the cash ladder multiple from the 2021-12-31 NAV, never the 2022-2023 artifacts
        w = E.window_return("RSX", pd.Timestamp("2019-12-31"), pd.Timestamp("2029-12-31"), ladder=lad, funds=funds, universe=u)
        assert w["status"] == "liquidated_in_window" and math.isclose(w["gross"], 1.1 * 1.2 * (1.6051 + 0.34) / 26.75)
        # ERUS: halt year 2022 has a calendar-year NAV figure -> applied (the -99.8 % is real); the later cash
        # distributions cannot be expressed without a reference NAV -> incomplete tail, never a flat carry
        w = E.window_return("ERUS", pd.Timestamp("2019-12-31"), pd.Timestamp("2029-12-31"), ladder=lad, funds=funds, universe=u)
        assert w["status"] == "manual_incomplete" and math.isclose(w["gross"], 1.1 * 1.2 * (1 - 0.99844))
        assert w["incomplete"] == ["2022-12-31..2029-12-31 (post-halt cash distributions: reference NAV not transcribed)"]
        assert w["liquidated_in_window"] and w["sources"] == ["halt year 2022 from its calendar-year figure"]
        # FM: 2024 known only through November (derived 11-month stub), final 2025 stub null
        w = E.window_return("FM", pd.Timestamp("2022-12-31"), pd.Timestamp("2032-12-31"), ladder=lad, funds=funds, universe=u)
        assert math.isclose(w["gross"], 1.1 * 1.06751) and w["status"] == "manual_incomplete"
        assert w["incomplete"] == ["2024-11-30..2024-12-31 (calendar year not transcribed)", "2025-01-01..2025-01-09 (final stub not transcribed)"]
    finally:
        EE.fetch_prices = orig


def test_manual_ladder_parses_legacy_layouts_and_malformed_file(tmp_path):
    y = tmp_path / "m.yaml"
    y.write_text("""
entries:
  NGE:
    years:
      - {year: 2014, tr_pct: -15.2, source_url: "https://a"}
      - {year: 2015, tr_nav: -0.30, source_url: "https://b"}
    liquidation: {date: "2023-07-28", tr_pct: 3.0, source_url: "https://c"}
rows:
  - {ticker: PAK, year: 2016, tr_nav: 0.12, source_url: "https://d"}
""")
    lad = E.manual_ladder(y)
    assert len(lad) == 4 and set(lad["ticker"]) == {"NGE", "PAK"}
    nge = lad[lad.ticker == "NGE"].set_index("kind")
    assert math.isclose(lad[(lad.ticker == "NGE") & (lad.year == 2014)]["tr_nav"].iloc[0], -0.152)
    assert nge.loc["liquidation", "date_to"] == pd.Timestamp("2023-07-28") and math.isclose(nge.loc["liquidation", "tr_nav"], 0.03)
    assert E.manual_ladder(tmp_path / "absent.yaml").empty and E.manual_funds(tmp_path / "absent.yaml") == {}
    bad = tmp_path / "bad.yaml"
    bad.write_text("funds:\n  - ticker: X\n    years: [\n")
    with pytest.raises(E.EtfGuardError) as ei:
        E.manual_ladder(bad)
    assert ei.value.assertion == "manual_ladder_unparseable"


# ------------------------------------------------------------------------------------------------ VT benchmark
def _flat(start: str, n: int, level: float, daily: float = 0.0) -> pd.DataFrame:
    """Deterministic price path: level·(1+daily)^k on business days."""
    d = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"date": d, "adjclose": level * (1 + daily) ** np.arange(n)})


def test_vt_benchmark_leg_weights_and_switch_date_2000_rule():
    cal_n = 9000
    spy = _flat("1993-01-29", cal_n, 100.0, 0.0004)             # ~10.6 %/yr
    efa = _flat("2001-08-14", cal_n, 50.0, 0.0002)
    eem = _flat("2003-04-07", cal_n, 20.0, 0.0006)
    vt = _flat("2008-06-24", cal_n, 40.0, 0.0003)
    prices = {"SPY": spy, "EFA": efa, "EEM": eem, "VT": vt}
    entry, exit = pd.Timestamp("2000-12-29"), pd.Timestamp("2010-12-31")
    b = E.vt_benchmark(entry, exit, prices=prices)
    assert b["benchmark"] == "vt_proxy" and b["proxy_rule"] == "2000"
    ws = [leg["weights"] for leg in b["legs"]]
    assert ws == [{"SPY": 1.0}, {"SPY": 0.6, "EFA": 0.4}, {"VT": 1.0}]
    assert b["efa_start"] == pd.Timestamp("2001-08-14") and b["switch_date"] == pd.Timestamp("2008-06-24")
    assert b["legs"][1]["from"] == pd.Timestamp("2001-08-14") and b["legs"][2]["from"] == pd.Timestamp("2008-06-24")
    # year-end rebalances: every last business day of 2001..2009 inside the window (plus entry, efa start, switch)
    ye = {pd.Timestamp(d) for d in pd.Series(spy["date"]).groupby(spy["date"].dt.year).max() if entry < d < exit}
    assert ye <= set(b["rebalance_dates"])
    # value check: replicate the path by hand
    frame = E._aligned(prices, pd.DatetimeIndex(spy["date"][(spy["date"] >= entry) & (spy["date"] <= exit)]))
    v, units = 1.0, {}
    events = sorted(set(b["rebalance_dates"]))
    for day in frame.index:
        row = frame.loc[day]
        if units:
            v = sum(u * row[k] for k, u in units.items())
        if day in events:
            w = {"VT": 1.0} if day >= pd.Timestamp("2008-06-24") else ({"SPY": 0.6, "EFA": 0.4} if day >= pd.Timestamp("2001-08-14") else {"SPY": 1.0})
            units = {k: v * wk / row[k] for k, wk in w.items()}
    assert math.isclose(b["gross"], v, rel_tol=1e-12)
    assert math.isclose(b["r_ann"], math.log(v) / ((b["exit_used"] - b["entry_used"]).days / 365.25))


def test_vt_benchmark_2005_rule_and_pure_vt():
    n = 9000
    prices = {"SPY": _flat("1993-01-29", n, 100.0, 0.0004), "EFA": _flat("2001-08-14", n, 50.0, 0.0002),
              "EEM": _flat("2003-04-07", n, 20.0, 0.0006), "VT": _flat("2008-06-24", n, 40.0, 0.0003)}
    b = E.vt_benchmark(pd.Timestamp("2005-12-30"), pd.Timestamp("2015-12-31"), prices=prices)
    assert b["proxy_rule"] == "2005" and [leg["weights"] for leg in b["legs"]] == [{"SPY": 0.5, "EFA": 0.4, "EEM": 0.1}, {"VT": 1.0}]
    assert b["switch_date"] == pd.Timestamp("2008-06-24") and b["efa_start"] is None
    # first segment: value at the first year-end equals the unrebalanced blend (no rebalance before it)
    pure = E.vt_benchmark(pd.Timestamp("2010-12-31"), pd.Timestamp("2020-12-31"), prices=prices)
    assert pure["benchmark"] == "vt" and pure["legs"] == [{"from": pd.Timestamp("2010-12-31"), "to": pd.Timestamp("2020-12-31"), "weights": {"VT": 1.0}}]
    vt = prices["VT"].set_index("date")["adjclose"]
    assert math.isclose(pure["gross"], vt[pd.Timestamp("2020-12-31")] / vt[pd.Timestamp("2010-12-31")])


# ------------------------------------------------------------------------------------------------ equal-weight basket
def test_ew_basket_is_strict_about_missing_ladders(monkeypatch):
    cal = _bars("1993-01-29", 9000)
    a = _bars("1996-03-12", 8000, price=10.0, growth=0.05)
    b = _bars("1996-03-12", 8000, price=10.0, growth=-0.05)
    u = _synthetic_universe([{"ticker": "SPY", "iso3": "USA", "role": "benchmark", "inception": "1993-01-22", "status": "live"},
                             {"ticker": "AAA", "iso3": "AAA", "role": "single_country", "inception": "1996-03-12", "status": "live"},
                             {"ticker": "BBB", "iso3": "BBB", "role": "single_country", "inception": "1996-03-12", "status": "live"},
                             {"ticker": "LATE", "iso3": "LTE", "role": "single_country", "inception": "2012-01-01", "status": "live"},
                             {"ticker": "DED", "iso3": "DED", "role": "single_country", "inception": "2000-01-03", "delisted": "2008-05-01", "status": "liquidated"}])

    def fake_fetch(ticker, **kw):
        if ticker == "DED":
            e = pd.DataFrame(columns=["date", "adjclose"]); e.attrs["route"] = "manual"; return e
        p = {"SPY": cal, "AAA": a, "BBB": b}[ticker][["date", "adjclose"]].reset_index(drop=True)
        p.attrs["route"] = "yahoo"
        return p
    monkeypatch.setattr(E, "fetch_prices", fake_fetch)
    entry, exit = pd.Timestamp("2005-12-30"), pd.Timestamp("2015-12-31")
    empty_ladder = pd.DataFrame(columns=E.LADDER_COLS)
    with pytest.raises(E.EtfGuardError):
        E.ew_basket(2005, entry, exit, universe=u, ladder=empty_ladder, funds={})
    out = E.ew_basket(2005, entry, exit, universe=u, ladder=empty_ladder, funds={}, strict=False)
    assert out["n"] == 2 and out["missing_manual"] == ["DED"] and {m["ticker"] for m in out["members"]} == {"AAA", "BBB"}
    ga = math.exp(out["members"][0]["r_log"]); gb = math.exp(out["members"][1]["r_log"])
    assert math.isclose(out["r_log"], math.log((ga + gb) / 2))
    ladder = _ladder("DED", {2006: 0.1, 2007: 0.1}, liq=("2008-05-01", -0.5))
    out = E.ew_basket(2005, entry, exit, universe=u, ladder=ladder, funds={})
    assert out["n"] == 3 and out["n_liquidated"] == 1
    assert math.isclose(out["r_log"], math.log((ga + gb + 1.1 * 1.1 * 0.5) / 3))
    # an incomplete ladder (2007 missing) is an error under strict, kept-and-listed otherwise
    holey = _ladder("DED", {2006: 0.1}, liq=("2008-05-01", -0.5))
    with pytest.raises(E.EtfGuardError) as ei:
        E.ew_basket(2005, entry, exit, universe=u, ladder=holey, funds={})
    assert ei.value.assertion == "manual_ladder_incomplete"
    out = E.ew_basket(2005, entry, exit, universe=u, ladder=holey, funds={}, strict=False)
    assert out["incomplete"] == ["DED"] and out["n"] == 3
