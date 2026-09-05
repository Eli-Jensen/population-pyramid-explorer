"""Per-country investability record → ``evals/instruments.yaml`` (plan §7, M5.4).

Inputs (all already in the repo; NO network):
* ``evals/econ/etf_universe.yaml``  — the frozen universe (tickers, issuers, inception, status, delisted, msci_class);
* ``evals/econ/etf_manual.yaml``    — issuer-filed calendar-year NAV returns and the corrected liquidation dates for the
                                      delisted funds (``prereg_deviations``: NGE's last trading day is 2024-03-25);
* ``evals/econ/tables/etf_returns.csv`` — the backtest's window table (T = 2015, h = 10 row → ``cagr_10y_pct`` with VT
                                      over the identical window);
* ``data/raw/etf/<ticker>.parquet`` — cached daily adjusted closes (gitignored) for the since-inception statistics of
                                      LIVE funds; absent cache → those fields are null, never fetched here;
* ``evals/markets.yaml``            — country events (index deletion, repatriation, trading halt) and a market-class
                                      snapshot for countries without a fund.

Only DERIVED statistics leave this module (a CAGR, a drawdown, a date) — never a price series. Every market number is
paired with VT over the identical window (VT proxy before 2008-06-24, flagged), as the language rules require.
"""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pyramid_explorer.econ import etf
from pyramid_explorer.paths import DATA_RAW_ETF, ECON_EVALS, EVALS

MARKETS_YAML = EVALS / "markets.yaml"
INSTRUMENTS_YAML = EVALS / "instruments.yaml"
RETURNS_CSV = ECON_EVALS / "tables" / "etf_returns.csv"
BENCH_TICKERS = ("SPY", "EFA", "EEM", "VT")
TEN_YEAR_T, TEN_YEAR_H = 2015, 10
STATUS_RANK = {"live": 0, "liquidating": 1, "liquidated": 2}

HEADER = """\
# Per-country investability for the economic lens — GENERATED BODY below the `generated:` line, hand-editable header.
# Regenerate with `uv run --group econ scripts/build_econ.py` (pyramid_explorer.econ.instruments.write_instruments);
# the generator re-reads this header verbatim and replaces everything after `generated:`.
#
# What the fields mean
#   status       live | liquidating | liquidated | none  — the best-standing fund of the country (frozen universe +
#                etf_manual.yaml corrections; a Yahoo quote is never evidence of life)
#   msci_class   DM | EM | FM | standalone | none | null  — as recorded in etf_universe.yaml (funds) or
#                evals/markets.yaml (snapshot for fund-less countries); null = not looked up
#   mobility     open | restricted | closed | not_assessed — derived: standalone or an index_deletion event → closed;
#                FM with a repatriation event → restricted; EM / DM → open; otherwise not_assessed
#   tickers[]    every single-country fund of the universe for that country, with DERIVED statistics only:
#                since_inception_cagr_pct (+ vt_same_window_pct, benchmark vt|vt_proxy, window) from cached daily adjusted
#                closes for live funds, or from the issuer's full calendar-year NAV returns for delisted funds
#                (window = those calendar years, flagged full_calendar_years_only); cagr_10y_pct = the backtest's
#                2015-12-31 → 2025-12-31 window (etf_returns.csv, status as recorded) with VT over the same window;
#                max_dd_pct = maximum drawdown over the since-inception window (live) or the backtest window (manual)
#   events[]     dated country events from evals/markets.yaml (verified flag per event)
# Past figures only; nothing here is a forecast or a recommendation. Fund names are examples of what exists or existed.
"""


# ------------------------------------------------------------------------------------------------ helpers
def _d(x) -> str | None:
    try:
        if x is None or pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return str(pd.Timestamp(x).date())


def _pct(x) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 2)


def _cagr_pct_from_log(r_ann_log) -> float | None:
    return None if r_ann_log is None or not np.isfinite(r_ann_log) else _pct(100.0 * (math.exp(float(r_ann_log)) - 1.0))


def cached_prices(ticker: str, entry: dict, cache_dir: Path = DATA_RAW_ETF) -> pd.DataFrame | None:
    """Clipped ``date, adjclose`` bars from the parquet cache, or None when absent. No network."""
    pq = Path(cache_dir) / f"{ticker}.parquet"
    if not pq.exists():
        return None
    bars = pd.read_parquet(pq)
    bars["date"] = pd.to_datetime(bars["date"])
    bars = etf.clip_to_yaml(bars, entry)
    return bars[["date", "adjclose"]].reset_index(drop=True) if len(bars) else None


def max_drawdown_pct(adj: pd.Series) -> float | None:
    a = pd.Series(adj, dtype=float).dropna()
    if len(a) < 2:
        return None
    dd = a / a.cummax() - 1.0
    return _pct(100.0 * float(dd.min()))


def _vt_same_window(entry_date: pd.Timestamp, exit_date: pd.Timestamp, bench: dict[str, pd.DataFrame]) -> dict:
    """VT (or the pre-registered proxy) CAGR over the identical window, from cached benchmark bars."""
    if not bench or "SPY" not in bench:
        return {"vt_same_window_pct": None, "benchmark": "unavailable"}
    try:
        v = etf.vt_benchmark(entry_date, exit_date, prices=bench)
    except Exception as e:  # noqa: BLE001 — a benchmark gap is reported, never fatal
        return {"vt_same_window_pct": None, "benchmark": f"unavailable ({type(e).__name__})"}
    return {"vt_same_window_pct": _cagr_pct_from_log(v["r_ann"]), "benchmark": v["benchmark"],
            "window": [_d(v["entry_used"]), _d(v["exit_used"])]}


# ------------------------------------------------------------------------------------------------ per ticker
def since_inception_live(ticker: str, entry: dict, bench: dict[str, pd.DataFrame], cache_dir: Path = DATA_RAW_ETF) -> dict:
    bars = cached_prices(ticker, entry, cache_dir)
    if bars is None or len(bars) < 2:
        return {"since_inception_cagr_pct": None, "max_dd_pct": None, "as_of": None, "vt_same_window_pct": None,
                "benchmark": None, "window": None, "basis": "no cached daily series"}
    p0, p1 = float(bars["adjclose"].iloc[0]), float(bars["adjclose"].iloc[-1])
    d0, d1 = bars["date"].iloc[0], bars["date"].iloc[-1]
    years = (d1 - d0).days / 365.25
    out = {"since_inception_cagr_pct": _pct(100.0 * ((p1 / p0) ** (1.0 / years) - 1.0)) if years >= 1 else None,
           "max_dd_pct": max_drawdown_pct(bars["adjclose"]), "as_of": _d(d1), "window": [_d(d0), _d(d1)],
           "basis": "daily adjusted closes, first bar after inception to the last cached bar"}
    out.update(_vt_same_window(d0, d1, bench))
    return out


def since_inception_manual(ticker: str, fund: dict, bench: dict[str, pd.DataFrame]) -> dict:
    """Full calendar years of issuer NAV total return compounded (stubs and reinvestment artefacts excluded)."""
    years = [y for y in fund.get("years", []) if y.get("tr_nav") is not None and not y.get("reinvestment_artifact")]
    if not years:
        return {"since_inception_cagr_pct": None, "max_dd_pct": None, "as_of": None, "vt_same_window_pct": None,
                "benchmark": None, "window": None, "basis": "no full calendar year transcribed"}
    ys = sorted(int(y["year"]) for y in years)
    contiguous = ys == list(range(ys[0], ys[-1] + 1))
    growth = float(np.prod([1.0 + float(y["tr_nav"]) for y in years]))
    n = len(years)
    d0, d1 = pd.Timestamp(f"{ys[0] - 1}-12-31"), pd.Timestamp(f"{ys[-1]}-12-31")
    out = {"since_inception_cagr_pct": _pct(100.0 * (growth ** (1.0 / n) - 1.0)), "as_of": _d(d1),
           "window": [_d(d0), _d(d1)], "n_full_years": n, "contiguous": contiguous,
           "basis": "issuer calendar-year NAV total returns compounded (full_calendar_years_only; inception and final stubs excluded)"}
    out.update(_vt_same_window(d0, d1, bench))
    return out


def ten_year_row(returns: pd.DataFrame, ticker: str) -> dict:
    """The backtest's T = 2015, h = 10 window for ``ticker`` (etf_returns.csv), with VT over the identical window."""
    r = returns[(returns["ticker"] == ticker) & (returns["T"] == TEN_YEAR_T) & (returns["h"] == TEN_YEAR_H)]
    if r.empty:
        return {"cagr_10y_pct": None, "cagr_10y_status": "no row"}
    r = r.iloc[0]
    return {"cagr_10y_pct": _cagr_pct_from_log(r["r_ann"]), "cagr_10y_vt_pct": _cagr_pct_from_log(r["r_vt_ann"]),
            "cagr_10y_window": [str(r["entry_used"]) if pd.notna(r.get("entry_used")) else str(r["entry"]),
                                str(r["exit_used"]) if pd.notna(r.get("exit_used")) else str(r["exit"])],
            "cagr_10y_benchmark": r["benchmark"], "cagr_10y_status": r["status"],
            "cagr_10y_max_dd_pct": _pct(100.0 * r["max_dd"]) if pd.notna(r["max_dd"]) else None,
            "cagr_10y_incomplete": None if pd.isna(r.get("incomplete")) else str(r["incomplete"])}


def ticker_record(entry: dict, manual: dict[str, dict], returns: pd.DataFrame, bench: dict[str, pd.DataFrame],
                  cache_dir: Path = DATA_RAW_ETF) -> dict:
    t = entry["ticker"]
    fund = manual.get(t)
    delisted = _d(entry.get("delisted"))
    if fund and fund.get("last_trading_day") is not None:
        delisted = _d(fund["last_trading_day"])          # etf_manual.yaml corrections win (NGE 2024-03-25)
    status_url = entry.get("status_url")          # the issuer notice named in the frozen universe
    rec = {"ticker": t, "name": entry.get("name"), "issuer": entry.get("issuer"), "inception": _d(entry["inception"]),
           "status": entry["status"], "delisted": delisted,
           "delisted_universe": _d(entry.get("delisted")) if fund and _d(entry.get("delisted")) != delisted else None,
           "liquidation_date": _d(fund["liquidation_date"]) if fund and fund.get("liquidation_date") is not None else None,
           "msci_class": None if pd.isna(entry.get("msci_class")) else entry["msci_class"],
           "status_url": None if status_url is None or (isinstance(status_url, float) and math.isnan(status_url)) else str(status_url),
           "liquidation_source_url": fund.get("liquidation_source_url") if fund else None,
           "source_url": entry.get("source_url")}
    stats = since_inception_manual(t, fund, bench) if fund else since_inception_live(t, entry, bench, cache_dir)
    rec.update(stats)
    ten = ten_year_row(returns, t)
    rec.update(ten)
    if fund and rec.get("max_dd_pct") is None:
        rec["max_dd_pct"] = ten.get("cagr_10y_max_dd_pct")
        rec["max_dd_basis"] = "backtest 2015–2025 ladder path (annual marks)" if rec["max_dd_pct"] is not None else None
    return rec


# ------------------------------------------------------------------------------------------------ per country
def mobility(msci_class: str | None, events: list[dict]) -> str:
    kinds = {e["kind"] for e in events}
    if msci_class == "standalone" or "index_deletion" in kinds:
        return "closed"
    if msci_class == "FM" and "repatriation" in kinds:
        return "restricted"
    if msci_class in ("EM", "DM"):
        return "open"
    return "not_assessed"


def country_status(tickers: list[dict]) -> str:
    if not tickers:
        return "none"
    return min((t["status"] for t in tickers), key=lambda s: STATUS_RANK.get(s, 9))


def load_benchmarks(universe: pd.DataFrame, cache_dir: Path = DATA_RAW_ETF) -> dict[str, pd.DataFrame]:
    out = {}
    for t in BENCH_TICKERS:
        row = universe[universe["ticker"] == t]
        if row.empty:
            continue
        bars = cached_prices(t, row.iloc[0].to_dict(), cache_dir)
        if bars is not None:
            out[t] = bars
    return out


def build_instruments(*, universe: pd.DataFrame | None = None, manual: dict[str, dict] | None = None,
                      returns: pd.DataFrame | None = None, markets: dict | None = None,
                      country_ids: list[str] | None = None, cache_dir: Path = DATA_RAW_ETF) -> dict:
    """``{'as_of', 'countries': {iso3: {...}}, 'baskets': [...], 'counts': {...}}``."""
    universe = universe if universe is not None else etf.load_universe()
    manual = manual if manual is not None else etf.manual_funds()
    returns = returns if returns is not None else (pd.read_csv(RETURNS_CSV) if RETURNS_CSV.exists() else pd.DataFrame(columns=["ticker", "T", "h"]))
    markets = markets if markets is not None else yaml.safe_load(MARKETS_YAML.read_text(encoding="utf-8"))
    bench = load_benchmarks(universe, cache_dir)
    events_by = {}
    for e in markets.get("events", []) or []:
        events_by.setdefault(e["iso3"], []).append({**e, "date": _d(e["date"])})
    snapshot = (markets.get("msci_class_snapshot") or {}).get("classes", {}) or {}

    countries: dict[str, dict] = {}
    singles = universe[universe["role"] == "single_country"]
    for iso3, grp in singles.groupby("iso3"):
        recs = [ticker_record(r.to_dict(), manual, returns, bench, cache_dir) for _, r in grp.sort_values("inception").iterrows()]
        classes = [r["msci_class"] for r in recs if r["msci_class"]]
        cls = classes[0] if classes else None
        ev = sorted(events_by.get(iso3, []), key=lambda e: e["date"])
        countries[iso3] = {"status": country_status(recs), "msci_class": cls, "msci_class_source": "etf_universe.yaml",
                           "mobility": mobility(cls, ev), "tickers": recs, "events": ev}
    for iso3, cls in snapshot.items():
        if iso3 in countries:
            continue
        ev = sorted(events_by.get(iso3, []), key=lambda e: e["date"])
        countries[iso3] = {"status": "none", "msci_class": cls, "msci_class_source": "markets.yaml snapshot",
                           "mobility": mobility(cls, ev), "tickers": [], "events": ev}
    for iso3 in country_ids or []:
        if iso3 not in countries:
            ev = sorted(events_by.get(iso3, []), key=lambda e: e["date"])
            countries[iso3] = {"status": "none", "msci_class": None, "msci_class_source": None,
                               "mobility": mobility(None, ev), "tickers": [], "events": ev}
    baskets = [ticker_record(r.to_dict(), manual, returns, bench, cache_dir)
               for _, r in universe[universe["role"] == "basket"].iterrows()]
    statuses = pd.Series([c["status"] for c in countries.values()]).value_counts().to_dict()
    mob = pd.Series([c["mobility"] for c in countries.values()]).value_counts().to_dict()
    uni_doc = yaml.safe_load(etf.UNIVERSE_YAML.read_text(encoding="utf-8")) if etf.UNIVERSE_YAML.exists() else {}
    as_of_dates = [t["as_of"] for c in countries.values() for t in c["tickers"] if t.get("as_of")]
    return _plain({"as_of": max(as_of_dates) if as_of_dates else (str(uni_doc.get("as_of")) if uni_doc else None),
            "universe_as_of": str(uni_doc.get("as_of")) if uni_doc else None,
            "counts": {"countries": len(countries), "status": {k: int(v) for k, v in statuses.items()},
                       "mobility": {k: int(v) for k, v in mob.items()},
                       "tickers": int(sum(len(c["tickers"]) for c in countries.values())),
                       "cached_series": sorted(k for k in bench)},
            "countries": dict(sorted(countries.items())), "baskets": baskets})


# ------------------------------------------------------------------------------------------------ yaml I/O
def _plain(o):
    """yaml-safe plain types (numpy scalars → python, NaN → None)."""
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, date)):
        return _d(o)
    if o is pd.NA:
        return None
    return o


def read_header(path: Path = INSTRUMENTS_YAML) -> str:
    """The hand-editable header of an existing file (everything before the ``generated:`` line), else the default."""
    if path.exists():
        text = path.read_text(encoding="utf-8")
        head, sep, _ = text.partition("\ngenerated:")
        if sep:
            return head + "\n"
    return HEADER


def write_instruments(doc: dict, path: Path = INSTRUMENTS_YAML) -> Path:
    body = yaml.safe_dump(_plain(doc), sort_keys=False, allow_unicode=True, width=120, default_flow_style=False)
    path.write_text(read_header(path).rstrip("\n") + "\ngenerated:\n" + "".join("  " + l + "\n" for l in body.splitlines()), encoding="utf-8")
    return path


def load_instruments(path: Path = INSTRUMENTS_YAML) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["generated"]
