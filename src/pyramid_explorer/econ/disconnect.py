"""Experiment 3 — the disconnect table (evals/econ/PREREG.md §5).

One row per pre-registered (country, year): pyramid statistics, blend distance to China 1990 with its same-year
percentile, GDP-per-capita multiples over the following 30 years (clipped to the last observed year), the MSCI
country-index facts transcribed in ``evals/econ/msci_citations.yaml`` (cited, never series), and — where a
US-listed single-country fund exists — the fund's annualised total return and maximum drawdown over the clipped
window against SPY, EEM and VT / VT-proxy over the identical days.  Rows without a fact or fund carry the explicit
state ("no MSCI figure transcribed", "no US-listed single-country fund").
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.metrics import distances

ROWS: tuple[tuple[str, int], ...] = (("CHN", 1990), ("KOR", 1975), ("KOR", 1990), ("JPN", 1960), ("TWN", 1970),
                                    ("THA", 1985), ("VNM", 2000), ("IND", 2005))
NOW_ROWS: tuple[tuple[str, int], ...] = (("PHL", 2024), ("BGD", 2024), ("NPL", 2024), ("LAO", 2024), ("KHM", 2024))
ANCHOR = ("CHN", 1990)
SPAN = 30
LAST_FULL_YEAR = 2025            # last complete calendar year at run time (windows past it clip to the latest bar)
MIN_ANNUALISE_YEARS = 1.0        # a fund window under one full year (span rounded to 2 dp) is reported as a raw total return, never as pp/yr
IMPLEMENTATION_NOTES = [
    f"Disconnect fund windows under {MIN_ANNUALISE_YEARS:.0f} full year (window_years rounded to two decimals < 1.00; a fund whose history starts "
    "inside the row's last calendar year, e.g. EWT for TWN 1970: 2000-06-23 → 2000-12-29, 0.52 y) are flagged too_short_to_annualise and shown as "
    "the raw total return over the span; the annualised figure stays in disconnect.json but is never printed as pp/yr. The row is never dropped.",
]
NO_MSCI = "no MSCI figure transcribed"
NO_FUND = "no US-listed single-country fund"
NO_FUND_IN_WINDOW = "no US-listed single-country fund existed inside the window"
CSV_COLUMNS = ["iso3", "year", "kind", "median_age", "u15", "wa", "o65", "s0_s20", "tfr", "d_blend_chn1990", "pct_same_year",
               "pct_band", "y_t", "mult_10", "mult_20", "mult_30", "y_last_year", "mult_last", "msci_index", "msci_since",
               "msci_ann_pct_gross", "msci_max_dd_pct", "msci_state", "ticker", "fund_entry", "fund_exit", "fund_ann_log_pct",
               "fund_cagr_pct", "fund_max_dd", "spy_ann_log_pct", "eem_ann_log_pct", "vt_ann_log_pct", "vt_benchmark", "fund_state"]


def pyramid_stats(corpus: lk.Corpus, iso3: str, year: int, tfr: dict | None = None) -> dict[str, float | None]:
    """median age, u15 / wa / o65 shares, s0/s20 ratio (``base_slope_20``) and TFR (``tfr[(iso3, year)]`` if given)."""
    f = corpus.feats.iloc[corpus.row(iso3, year)]
    out = {"median_age": float(f["median_age"]), "u15": float(f["u15"]), "wa": float(f["wa"]), "o65": float(f["o65"]),
           "s0_s20": float(f["base_slope_20"])}
    out["tfr"] = float(tfr[(iso3, year)]) if tfr and (iso3, year) in tfr else None
    return out


def distance_to_anchor(corpus: lk.Corpus, iso3: str, year: int, *, anchor: tuple[str, int] = ANCHOR,
                       minpop: float = lk.MINPOP) -> dict[str, Any]:
    """``d_blend`` to the anchor row and its percentile among the same-year countries ≥ 1 M (share at least as close)."""
    q = corpus.X[corpus.row(*anchor)]
    ids = corpus.country_ids(year, minpop)
    rows = corpus.rows(ids, year)
    d_all = distances("blend", q, corpus.X[rows], sigma=corpus.sigma).astype(np.float64)
    d = float(distances("blend", q, corpus.X[[corpus.row(iso3, year)]], sigma=corpus.sigma)[0])
    pct = float((d_all <= d).mean())
    band = ("the anchor itself" if (iso3, year) == anchor else
            "nearest 5 %" if pct <= 0.05 else "nearest 10 %" if pct <= 0.10 else "nearest quarter" if pct <= 0.25
            else "nearest half" if pct <= 0.5 else "farther half")
    return {"d_blend_chn1990": d, "pct_same_year": pct, "pct_band": band, "n_same_year": int(len(ids))}


def level_multiples(levels: pd.Series, iso3: str, year: int, *, span: int = SPAN) -> dict[str, Any]:
    """``y_t`` and ``y_{t+10}/y_t … y_{t+30}/y_t`` from the level series (MultiIndex (iso3, year) → level),
    clipped to the country's last observed year (``mult_last`` over ``[t, last]``)."""
    try:
        s = levels.xs(iso3, level=0).dropna()
    except KeyError:
        return {"y_t": None, "multiples": {}, "y_last_year": None, "mult_last": None, "state": "no level series"}
    if year not in s.index or s[year] <= 0:
        last = int(s.index.max()) if len(s) else None
        return {"y_t": None, "multiples": {}, "y_last_year": last, "mult_last": None,
                "state": f"no level at {year}" + (f" (level series ends {last})" if last is not None else "")}
    y0 = float(s[year])
    mult = {}
    for k in (10, 20, 30):
        yy = year + k
        mult[k] = float(s[yy] / y0) if yy in s.index else None
    last = int(s.index.max())
    return {"y_t": y0, "multiples": mult, "y_last_year": last, "mult_last": float(s[last] / y0) if last > year else None,
            "state": "ok" if year + span <= last else f"clipped to last observed year {last}"}


def msci_facts(citations: dict, iso3: str, year: int) -> dict[str, Any]:
    """The transcribed MSCI facts for the row (gross sheet 'since' figure, with the net sheet beside it) or the
    explicit no-figure state.  Never computes; only cites."""
    idx = (citations.get("indexes") or {}).get(iso3)
    if not idx:
        return {"state": NO_MSCI}
    g, n = idx.get("gross", {}), idx.get("net", {})
    since = str(g.get("since"))
    clipped = since[:4].isdigit() and int(since[:4]) > year
    return {"state": "ok", "index_name": idx.get("name"), "verified": idx.get("verified"),
            "since": since, "clipped_to_index_history": bool(clipped),
            "ann_pct_gross_since": (g.get("annualised_pct") or {}).get("since"),
            "ann_pct_net_since": (n.get("annualised_pct") or {}).get("since"), "net_since": str(n.get("since")),
            "max_drawdown_pct_gross": g.get("max_drawdown_pct"), "max_drawdown_period_gross": [str(x) for x in g.get("max_drawdown_period") or []],
            "url_gross": g.get("url"), "url_net": n.get("url"), "accessed": str(citations.get("accessed")), "as_of": str(citations.get("as_of"))}


FETCH_KW = {"dead_series": "ok"}   # same policy as scripts/fetch_etf.py (deviation recorded, series discarded)


def _ltd(etf_mod, year: int, fetch_kw: dict) -> pd.Timestamp:
    """Last trading day of ``year`` from the SPY calendar; calendar-year end for years before SPY (1993)."""
    try:
        return etf_mod.last_trading_day(year, **fetch_kw)
    except ValueError:
        return pd.Timestamp(f"{year}-12-31")


def fund_block(universe: pd.DataFrame, etf_mod, iso3: str, year: int, *, span: int = SPAN,
               last_full_year: int = LAST_FULL_YEAR, fetch_kw: dict | None = None) -> dict[str, Any]:
    """The country's earliest-inception single-country fund over ``[t, t + 30]`` clipped to the fund's history and
    to the last complete calendar year: annualised log return, CAGR, maximum drawdown, and SPY / EEM / VT (VT-proxy)
    over the identical window.  Explicit states when no fund exists or none existed inside the window."""
    u = universe[(universe["role"].astype(str).str.replace("single_country", "country") == "country") & (universe["iso3"] == iso3)]
    if u.empty:
        return {"state": NO_FUND}
    u = u.assign(inception=pd.to_datetime(u["inception"])).sort_values("inception")
    e = u.iloc[0]
    fk = FETCH_KW if fetch_kw is None else fetch_kw
    exit_year = min(year + span, last_full_year)
    ltd_entry = _ltd(etf_mod, year, fk)
    exit_ = _ltd(etf_mod, exit_year, fk)
    if e["inception"] > exit_:
        return {"state": NO_FUND_IN_WINDOW, "ticker": str(e["ticker"]), "inception": e["inception"].date().isoformat(),
                "window_end": exit_.date().isoformat()}
    entry = max(ltd_entry, e["inception"])
    out: dict[str, Any] = {"state": "ok", "ticker": str(e["ticker"]), "name": e.get("name"), "issuer": e.get("issuer"),
                           "inception": e["inception"].date().isoformat(),
                           "delisted": None if pd.isna(e.get("delisted")) else str(e.get("delisted"))[:10],
                           "window_requested": [ltd_entry.date().isoformat(), exit_.date().isoformat()],
                           "entry_from_inception": bool(entry > ltd_entry)}
    if entry > ltd_entry and hasattr(etf_mod, "fetch_prices"):
        try:                                   # the fund is younger than the row: enter at its first bar on/after inception
            px = etf_mod.fetch_prices(str(e["ticker"]), **fk)
            first = px.loc[px["date"] >= entry, "date"]
            if len(first):
                entry = pd.Timestamp(first.iloc[0])
        except Exception as exc:  # noqa: BLE001 — a delisted fund routes to the manual ladder; keep the inception date
            out["entry_note"] = str(exc)
    try:
        wr = etf_mod.window_return(str(e["ticker"]), entry, exit_, **fk)
    except Exception as exc:  # noqa: BLE001 — reported, never fatal
        out.update({"state": f"fund return unavailable: {exc}"})
        return out
    r = wr.get("r_ann")
    r = None if r is None or not np.isfinite(float(r)) else float(r)
    status = str(wr.get("status"))
    yrs = wr.get("years")
    yrs_f = None if yrs is None or not np.isfinite(float(yrs)) else float(yrs)
    r_log = wr.get("r_log")
    r_log = None if r_log is None or not np.isfinite(float(r_log)) else float(r_log)
    if r_log is None and r is not None and yrs_f:
        r_log = r * yrs_f
    out.update({"status": status, "window_years": None if yrs_f is None else round(yrs_f, 2),
                "entry_used": None if pd.isna(wr.get("entry_used")) else str(wr.get("entry_used"))[:10],
                "exit_used": None if pd.isna(wr.get("exit_used")) else str(wr.get("exit_used"))[:10],
                "ann_log_return": r, "cagr": None if r is None else float(np.exp(r) - 1),
                "total_log_return": r_log, "total_return": None if r_log is None else float(np.exp(r_log) - 1),
                # pre-specified rendering rule: a window shorter than MIN_ANNUALISE_YEARS is not a per-year statistic
                "too_short_to_annualise": bool(yrs_f is not None and round(yrs_f, 2) < MIN_ANNUALISE_YEARS), "min_annualise_years": MIN_ANNUALISE_YEARS,
                "max_dd": None if wr.get("max_dd") is None or not np.isfinite(float(wr["max_dd"])) else float(wr["max_dd"])})
    if r is None:
        out["state"] = f"fund window status: {status}"
        return out
    eu, xu = pd.Timestamp(wr.get("entry_used", entry)), pd.Timestamp(wr.get("exit_used", exit_))
    def _total(b: dict) -> float | None:
        rl = b.get("r_log")
        if rl is not None and np.isfinite(float(rl)):
            return float(rl)
        return float(b["r_ann"]) * yrs_f if yrs_f and b.get("r_ann") is not None else None

    for tk in ("SPY", "EEM"):
        try:
            b = etf_mod.window_return(tk, eu, xu, **fk)
            out[tk.lower()] = {"ann_log_return": float(b["r_ann"]), "total_log_return": _total(b), "max_dd": b.get("max_dd"), "status": b.get("status")}
        except Exception as exc:  # noqa: BLE001
            out[tk.lower()] = {"state": f"unavailable: {exc}"}
    try:
        v = etf_mod.vt_benchmark(eu, xu, **fk)
        out["vt"] = {"ann_log_return": float(v["r_ann"]), "total_log_return": _total(v), "benchmark": v.get("benchmark"), "proxy_rule": v.get("proxy_rule"),
                     "switch_date": None if v.get("switch_date") is None else str(v.get("switch_date"))[:10]}
    except Exception as exc:  # noqa: BLE001
        out["vt"] = {"state": f"unavailable: {exc}", "benchmark": "none"}
    return out


def build_row(corpus: lk.Corpus, levels: pd.Series, citations: dict, iso3: str, year: int, *, kind: str,
              tfr: dict | None = None, universe: pd.DataFrame | None = None, etf_mod=None) -> dict[str, Any]:
    name = next((e.get("short_name") or e.get("name") for e in corpus.entities if e["id"] == iso3), iso3)
    row: dict[str, Any] = {"iso3": iso3, "year": year, "kind": kind, "name": name, "pyramid": pyramid_stats(corpus, iso3, year, tfr),
                           "distance": distance_to_anchor(corpus, iso3, year), "levels": level_multiples(levels, iso3, year),
                           "msci": msci_facts(citations, iso3, year) if kind == "history" else {"state": NO_MSCI, "note": "now-row: no historical index figure needed"}}
    if universe is not None and etf_mod is not None:
        row["fund"] = fund_block(universe, etf_mod, iso3, year)
    else:
        row["fund"] = {"state": "fund statistics not computed (no price data in this run)"}
    return row


def flatten(rows: list[dict]) -> pd.DataFrame:
    """``tables/disconnect.csv``: one flat line per row."""
    out = []
    for r in rows:
        p, d, lv, m, f = r["pyramid"], r["distance"], r["levels"], r["msci"], r.get("fund", {})
        mult = lv.get("multiples", {})
        out.append({"iso3": r["iso3"], "year": r["year"], "kind": r["kind"], **{k: p.get(k) for k in ("median_age", "u15", "wa", "o65", "s0_s20", "tfr")},
                    "d_blend_chn1990": d["d_blend_chn1990"], "pct_same_year": d["pct_same_year"], "pct_band": d["pct_band"],
                    "y_t": lv.get("y_t"), "mult_10": mult.get(10), "mult_20": mult.get(20), "mult_30": mult.get(30),
                    "y_last_year": lv.get("y_last_year"), "mult_last": lv.get("mult_last"),
                    "msci_index": m.get("index_name"), "msci_since": m.get("since"), "msci_ann_pct_gross": m.get("ann_pct_gross_since"),
                    "msci_max_dd_pct": m.get("max_drawdown_pct_gross"), "msci_state": m.get("state"),
                    "ticker": f.get("ticker"), "fund_entry": f.get("entry_used"), "fund_exit": f.get("exit_used"),
                    "fund_ann_log_pct": None if f.get("ann_log_return") is None else 100 * f["ann_log_return"],
                    "fund_cagr_pct": None if f.get("cagr") is None else 100 * f["cagr"], "fund_max_dd": f.get("max_dd"),
                    "spy_ann_log_pct": None if not f.get("spy", {}).get("ann_log_return") else 100 * f["spy"]["ann_log_return"],
                    "eem_ann_log_pct": None if not f.get("eem", {}).get("ann_log_return") else 100 * f["eem"]["ann_log_return"],
                    "vt_ann_log_pct": None if not f.get("vt", {}).get("ann_log_return") else 100 * f["vt"]["ann_log_return"],
                    "vt_benchmark": f.get("vt", {}).get("benchmark"), "fund_state": f.get("state")})
    return pd.DataFrame(out, columns=CSV_COLUMNS)


def run(corpus: lk.Corpus, levels: pd.DataFrame, citations: dict, *, tfr: dict | None = None,
        universe: pd.DataFrame | None = None, etf_mod=None, rows: tuple = ROWS, now_rows: tuple = NOW_ROWS,
        log: Callable[[str], None] | None = None) -> tuple[dict, pd.DataFrame]:
    """Experiment 3 end to end → ``(disconnect.json dict, tables/disconnect.csv frame)``.  ``levels`` is the
    ``iso3, year, y_level`` frame; ``tfr`` maps ``(iso3, year)`` → TFR when the indicator is available."""
    say = log or (lambda s: None)
    lv = levels.drop_duplicates(["iso3", "year"]).set_index(["iso3", "year"])["y_level"].sort_index()
    out_rows = []
    for kind, lst in (("history", rows), ("now", now_rows)):
        for iso3, year in lst:
            say(f"[exp3] {iso3} {year}")
            if (iso3, year) not in corpus.row_wide.stack().index:
                out_rows.append({"iso3": iso3, "year": year, "kind": kind, "state": "not in corpus"})
                continue
            out_rows.append(build_row(corpus, lv, citations, iso3, year, kind=kind, tfr=tfr, universe=universe, etf_mod=etf_mod))
    result = {"_meta": {"anchor": list(ANCHOR), "span_years": SPAN, "last_full_year": LAST_FULL_YEAR,
                        "msci_source": "evals/econ/msci_citations.yaml (hand-transcribed facts, cited; never series)",
                        "msci_accessed": str(citations.get("accessed")), "msci_as_of": str(citations.get("as_of")),
                        "vt_rule": "VT from 2008-06-24; VT proxy before (PREREG §3.5); 'none' where no proxy is defined for the window",
                        "percentile": "share of same-year countries ≥ 1 M at least as close to CHN 1990 (smaller = closer)",
                        "tfr_indicator": "tfr_wpp" if tfr else None,
                        "min_annualise_years": MIN_ANNUALISE_YEARS,
                        "implementation_notes": list(IMPLEMENTATION_NOTES),
                        "deviations": proxy_extension_deviations(out_rows)},
              "rows": out_rows}
    return result, flatten([r for r in out_rows if "pyramid" in r])


def proxy_extension_deviations(rows: list[dict]) -> list[str]:
    """PREREG §3.5 fixes the VT proxy for exactly two windows (entry 2000-12-29 and the last trading day of 2005).  A
    disconnect fund window that starts before VT's first bar on any other date used the nearest pre-registered rule
    (2000 rule for entries before 2005, 2005 rule after), flagged ``vt_proxy`` — an extension, recorded here."""
    used = []
    for r in rows:
        f = r.get("fund") or {}
        vt = f.get("vt") or {}
        if f.get("state") == "ok" and vt.get("benchmark") == "vt_proxy":
            used.append(f"{r['iso3']} {r['year']} ({f.get('ticker')} {f.get('entry_used')}→{f.get('exit_used')}: {vt.get('proxy_rule')} rule)")
    if not used:
        return []
    return ["Disconnect table (PREREG §5): the VT proxy of §3.5 is pre-registered only for the T = 2000 and T = 2005 windows; the fund "
            "windows " + "; ".join(used) + " begin before VT's first bar (2008-06-26) on other dates, so vt_benchmark applied the "
            "nearest pre-registered weights (2000 rule for entries before 2005, else the 2005 rule) until VT's first bar — an extension of §3.5, "
            "flagged vt_proxy on every such number."]
