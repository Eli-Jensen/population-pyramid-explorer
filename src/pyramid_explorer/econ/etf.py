"""ETF plumbing for the economic-lens backtest: universe, Yahoo fetch + survivorship guard, window
returns, the VT / VT-proxy benchmark and the equal-weight basket (PREREG.md §3.4, §3.5, §6).

Rules that this module enforces and never relaxes:

* the universe is ``evals/econ/etf_universe.yaml`` (no ticker added or removed after the fetch);
* liveness comes only from the yaml (``delisted: null``) **and** guard assertion 3 — a Yahoo quote is
  never evidence that a fund exists; a delisted ticker's prices are never used, its returns come from
  the hand-transcribed NAV ladder ``evals/econ/etf_manual.yaml``;
* bars before the yaml inception and after the yaml delisting date are dropped, never the reverse;
* raw prices stay in ``data/raw/etf/`` (gitignored); everything exported is a derived statistic.

Every guard decision is written to ``data/out/etf_guard_report.json``.
"""
from __future__ import annotations

import json
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pyramid_explorer.paths import DATA_OUT, DATA_RAW_ETF, ECON_EVALS

UNIVERSE_YAML = ECON_EVALS / "etf_universe.yaml"
MANUAL_YAML = ECON_EVALS / "etf_manual.yaml"
CROSSCHECK_YAML = ECON_EVALS / "etf_crosscheck.yaml"
GUARD_REPORT = DATA_OUT / "etf_guard_report.json"
VT_INCEPTION = pd.Timestamp("2008-06-24")
EFA_INCEPTION = pd.Timestamp("2001-08-14")
PROXY_WEIGHTS = {  # PREREG §3.5, fixed before any fetch
    "2000": {"before_efa": {"SPY": 1.0}, "after_efa": {"SPY": 0.6, "EFA": 0.4}},
    "2005": {"all": {"SPY": 0.5, "EFA": 0.4, "EEM": 0.1}},
}
# guard thresholds (PREREG §6)
MIN_BARS, FIRST_BAR_SLACK_DAYS, LIVE_SLACK_DAYS, MAX_GAP_DAYS = 250, 45, 10, 45
ENTRY_MAX_TRADING_DAYS_BACK = 5      # PREREG §3.4 [PSD]
A1, A2, A3, A4_NOT_REFUSED, A4_LOOKS_LIVE, A5 = ("A1_n_bars", "A2_first_bar", "A3_live_last_bar",
                                                  "A4_delisted_not_refused", "A4_delisted_looks_live", "A5_gap")


class EtfGuardError(RuntimeError):
    """A survivorship-guard assertion failed; ``.assertion`` carries the id (e.g. ``A1_n_bars``)."""

    def __init__(self, assertion: str, ticker: str, detail: str = ""):
        self.assertion, self.ticker, self.detail = assertion, ticker, detail
        super().__init__(f"{ticker}: {assertion}" + (f" — {detail}" if detail else ""))


# ------------------------------------------------------------------------------------------------ universe
def load_universe(path: Path = UNIVERSE_YAML) -> pd.DataFrame:
    """The pre-registered universe: one row per instrument with ``ticker, yahoo_symbol`` (defaults to
    the ticker), ``iso3, role`` (single_country | benchmark | basket), ``inception`` (Timestamp),
    ``delisted`` (Timestamp or NaT), ``status``, ``name``, ``issuer``, ``msci_class`` …"""
    doc = yaml.safe_load(Path(path).read_text())
    df = pd.DataFrame(doc["entries"])
    df["yahoo_symbol"] = df["yahoo_symbol"].where(df["yahoo_symbol"].notna(), df["ticker"]) if "yahoo_symbol" in df else df["ticker"]
    df["inception"] = pd.to_datetime(df["inception"])
    df["delisted"] = pd.to_datetime(df["delisted"])
    df["is_delisted"] = df["delisted"].notna()
    return df.set_index("ticker", drop=False).rename_axis(None)


def universe_entry(ticker: str, universe: pd.DataFrame | None = None) -> dict:
    u = load_universe() if universe is None else universe
    if ticker not in u.index:
        raise KeyError(f"{ticker!r} is not in etf_universe.yaml (nothing is added after the fetch)")
    return u.loc[ticker].to_dict()


# ------------------------------------------------------------------------------------------------ fetch
_SESSION = None


def _session():
    """One shared HTTP session for every Yahoo call (cookie/crumb reuse; the raw endpoint 429s bursts)."""
    global _SESSION
    if _SESSION is None:
        try:
            from curl_cffi import requests as cffi_requests
            _SESSION = cffi_requests.Session(impersonate="chrome")
        except Exception:  # noqa: BLE001 — yfinance manages its own session then
            _SESSION = False
    return _SESSION or None


def _download_raw(symbol: str, *, retries: int = 6, base_delay: float = 2.0) -> pd.DataFrame:
    """Daily ``date, adjclose, close, volume`` from Yahoo through yfinance (``range=max``), with
    exponential backoff on rate limits and transient errors. An empty frame means Yahoo returned no
    usable history (the 'no data' refusal signature) — that is a result, not an error."""
    import yfinance as yf
    from yfinance import exceptions as yfx

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            try:
                t = yf.Ticker(symbol, session=_session())
            except TypeError:
                t = yf.Ticker(symbol)
            hist = t.history(period="max", interval="1d", auto_adjust=False, actions=False, raise_errors=False)
            if hist is None or len(hist) == 0:
                return pd.DataFrame(columns=["date", "adjclose", "close", "volume"])
            idx = pd.DatetimeIndex(hist.index)
            if idx.tz is not None:
                idx = idx.tz_convert("America/New_York").tz_localize(None)
            out = pd.DataFrame({"date": idx.normalize(), "adjclose": hist["Adj Close"].to_numpy(dtype=float),
                                "close": hist["Close"].to_numpy(dtype=float), "volume": hist["Volume"].to_numpy(dtype=float)})
            out = out.dropna(subset=["adjclose"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
            return out
        except yfx.YFRateLimitError as e:  # pragma: no cover — network
            last_exc = e
        except Exception as e:  # noqa: BLE001 — transient network failures  # pragma: no cover
            last_exc = e
            if "delisted" in str(e).lower() or "no price data" in str(e).lower():
                return pd.DataFrame(columns=["date", "adjclose", "close", "volume"])
        time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 1))
    raise RuntimeError(f"{symbol}: Yahoo fetch failed after {retries} attempts: {last_exc!r}")


def _cache_paths(ticker: str, cache_dir: Path) -> tuple[Path, Path]:
    return cache_dir / f"{ticker}.parquet", cache_dir / f"{ticker}.meta.json"


def raw_prices(ticker: str, *, force: bool = False, cache_dir: Path = DATA_RAW_ETF,
               universe: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Raw (unclipped) Yahoo bars for ``ticker`` from the parquet cache, fetching once when absent or
    ``force``. Returns ``(bars, meta)``; ``meta`` records symbol, fetched_at, n_bars, first/last bar."""
    entry = universe_entry(ticker, universe)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    pq, mj = _cache_paths(ticker, cache_dir)
    if pq.exists() and mj.exists() and not force:
        bars = pd.read_parquet(pq)
        bars["date"] = pd.to_datetime(bars["date"])
        return bars, json.loads(mj.read_text())
    bars = _download_raw(str(entry["yahoo_symbol"]))
    meta = {"ticker": ticker, "symbol": str(entry["yahoo_symbol"]), "source": "yfinance chart v8 range=max interval=1d adjclose",
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n_bars": int(len(bars)),
            "first_bar": None if bars.empty else str(bars["date"].iloc[0].date()),
            "last_bar": None if bars.empty else str(bars["date"].iloc[-1].date())}
    bars.to_parquet(pq, index=False)
    mj.write_text(json.dumps(meta, indent=1))
    return bars, meta


# ------------------------------------------------------------------------------------------------ guard
def signature(bars: pd.DataFrame) -> str:
    """Yahoo's answer shape: ``no_data`` (empty), ``one_bar`` (a single stale quote) or ``series``."""
    n = len(bars)
    return "no_data" if n == 0 else "one_bar" if n == 1 else "series"


def clip_to_yaml(bars: pd.DataFrame, entry: dict) -> pd.DataFrame:
    """Drop bars before the yaml inception and after the yaml delisting date (PREREG §6) — never the
    reverse (NORW's Yahoo history predates its inception; PAK's outlives its last trading day)."""
    if bars.empty:
        return bars
    m = bars["date"] >= pd.Timestamp(entry["inception"])
    if pd.notna(entry.get("delisted")):
        m &= bars["date"] <= pd.Timestamp(entry["delisted"])
    return bars[m].reset_index(drop=True)


def guard(series: pd.DataFrame, entry: dict, today) -> list[str]:
    """Assertion ids violated by the RAW ``series`` (columns ``date, adjclose``) for a universe entry.

    Live funds (``delisted`` null): ``A1_n_bars`` (≥ 250 bars after clipping), ``A2_first_bar``
    (first raw bar ≤ inception + 45 d), ``A3_live_last_bar`` (last bar ≥ today − 10 d), ``A5_gap``
    (no gap > 45 d between consecutive clipped bars). Delisted funds: Yahoo must have **refused** —
    ``no_data`` or ``one_bar`` both pass; a multi-bar series is ``A4_delisted_not_refused`` and, if
    that series runs to within 10 d of today, also ``A4_delisted_looks_live`` (a real disagreement
    between the yaml and the feed). Delisted funds are routed to the manual ladder in every case."""
    today = pd.Timestamp(today).normalize()
    inception = pd.Timestamp(entry["inception"])
    delisted = entry.get("delisted")
    bad: list[str] = []
    sig = signature(series)
    if pd.notna(delisted):
        if sig == "series":
            bad.append(A4_NOT_REFUSED)
            if series["date"].iloc[-1] >= today - pd.Timedelta(days=LIVE_SLACK_DAYS):
                bad.append(A4_LOOKS_LIVE)
        return bad
    clipped = clip_to_yaml(series, entry)
    if len(clipped) < MIN_BARS:
        bad.append(A1)
    if series.empty or series["date"].iloc[0] > inception + pd.Timedelta(days=FIRST_BAR_SLACK_DAYS):
        bad.append(A2)
    if series.empty or series["date"].iloc[-1] < today - pd.Timedelta(days=LIVE_SLACK_DAYS):
        bad.append(A3)
    if len(clipped) > 1 and clipped["date"].diff().dt.days.max() > MAX_GAP_DAYS:
        bad.append(A5)
    return bad


_REPORT: dict = {"tickers": {}}


def _log_guard(ticker: str, record: dict, report_path: Path | None) -> None:
    _REPORT["tickers"][ticker] = record
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if report_path.exists():
            try:
                existing = json.loads(report_path.read_text())
            except json.JSONDecodeError:
                existing = {}
        tickers = existing.get("tickers", {})
        tickers[ticker] = record
        existing.update({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "thresholds": {"min_bars": MIN_BARS, "first_bar_slack_days": FIRST_BAR_SLACK_DAYS,
                                        "live_slack_days": LIVE_SLACK_DAYS, "max_gap_days": MAX_GAP_DAYS},
                         "tickers": dict(sorted(tickers.items()))})
        report_path.write_text(json.dumps(existing, indent=1, default=str))


def fetch_prices(ticker: str, *, force: bool = False, today=None, dead_series: str = "fail",
                 cache_dir: Path = DATA_RAW_ETF, report_path: Path | None = GUARD_REPORT,
                 universe: pd.DataFrame | None = None) -> pd.DataFrame:
    """Guarded daily ``date, adjclose`` for ``ticker``: raw bars (cached under ``data/raw/etf/``),
    the guard applied, then clipped to the yaml inception/delisting dates. Raises
    :class:`EtfGuardError` carrying the first violated assertion id. A delisted ticker returns an
    EMPTY frame with ``.attrs['route'] == 'manual'`` (its returns come from the NAV ladder).

    ``dead_series`` — what to do when Yahoo serves a multi-bar history for a delisted ticker
    (PREREG §6 A4 asserts a refusal): ``'fail'`` raises (the pre-registered behaviour); ``'ok'``
    records the deviation in the guard report and continues — the series is still never used. A
    dead series that runs to within 10 days of today fails in both modes."""
    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    entry = universe_entry(ticker, universe)
    bars, meta = raw_prices(ticker, force=force, cache_dir=cache_dir, universe=universe)
    violations = guard(bars, entry, today)
    clipped = clip_to_yaml(bars, entry)
    sig = signature(bars)
    delisted = pd.notna(entry.get("delisted"))
    deviation = None
    fatal = list(violations)
    if delisted and A4_NOT_REFUSED in fatal and A4_LOOKS_LIVE not in fatal and dead_series == "ok":
        fatal.remove(A4_NOT_REFUSED)
        deviation = (f"Yahoo served {len(bars)} daily bars ({bars['date'].iloc[0].date()} → {bars['date'].iloc[-1].date()}) "
                     f"for delisted {ticker} (yaml last trading day {pd.Timestamp(entry['delisted']).date()}); PREREG §6 A4 "
                     "asserted a refusal. Series discarded; returns from etf_manual.yaml.")
    record = {"symbol": meta.get("symbol"), "role": entry.get("role"), "iso3": entry.get("iso3"),
              "status_yaml": entry.get("status"), "inception_yaml": str(pd.Timestamp(entry["inception"]).date()),
              "delisted_yaml": None if not delisted else str(pd.Timestamp(entry["delisted"]).date()),
              "fetched_at": meta.get("fetched_at"), "today": str(today.date()), "signature": sig,
              "n_raw_bars": int(len(bars)), "first_raw_bar": meta.get("first_bar"), "last_raw_bar": meta.get("last_bar"),
              "n_bars": int(len(clipped)),
              "first_bar": None if clipped.empty else str(clipped["date"].iloc[0].date()),
              "last_bar": None if clipped.empty else str(clipped["date"].iloc[-1].date()),
              "first_bar_minus_inception_days": None if bars.empty else int((bars["date"].iloc[0] - pd.Timestamp(entry["inception"])).days),
              "max_gap_days": None if len(clipped) < 2 else int(clipped["date"].diff().dt.days.max()),
              "violations": violations, "fatal": fatal, "deviation": deviation,
              "route": "manual" if delisted else "yahoo", "passed": not fatal}
    _log_guard(ticker, record, report_path)
    if fatal:
        raise EtfGuardError(fatal[0], ticker, f"signature={sig}, n_raw={len(bars)}, first={meta.get('first_bar')}, last={meta.get('last_bar')}")
    if delisted:
        out = pd.DataFrame(columns=["date", "adjclose"])
        out.attrs["route"] = "manual"
        return out
    out = clipped[["date", "adjclose"]].reset_index(drop=True)
    out.attrs["route"] = "yahoo"
    return out


def guard_report() -> dict:
    """The in-memory guard decisions of this process (``{ticker: record}``)."""
    return dict(_REPORT["tickers"])


# ------------------------------------------------------------------------------------------------ manual ladder
LADDER_COLS = ["ticker", "year", "tr_nav", "source_url", "kind", "date_from", "date_to", "derived", "method", "note"]


def _tr(d: dict) -> float:
    """tr_nav as a fraction (``tr_pct`` divided by 100); NaN when the transcriber found nothing (null)."""
    if d.get("tr_nav") is not None:
        return float(d["tr_nav"])
    if d.get("tr_pct") is not None:
        return float(d["tr_pct"]) / 100.0
    return float("nan")


def _load_manual_doc(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise EtfGuardError("manual_ladder_unparseable", path.name, str(e).splitlines()[0]) from e


def manual_funds(path: Path = MANUAL_YAML) -> dict[str, dict]:
    """Fund-level facts of E3's ``etf_manual.yaml`` (``funds:`` list): ``{ticker: {inception,
    last_trading_day, liquidation_date, liquidation_nav, distributions, cash_ladder, …}}`` with the
    dates as Timestamps (NaT when null). Empty when the file is absent."""
    doc = _load_manual_doc(path)
    out: dict[str, dict] = {}
    for f in doc.get("funds", []) or []:
        e = dict(f)
        for k in ("inception", "last_trading_day", "liquidation_date"):
            e[k] = pd.to_datetime(e.get(k)) if e.get(k) else pd.NaT
        out[f["ticker"]] = e
    return out


def manual_ladder(path: Path = MANUAL_YAML) -> pd.DataFrame:
    """Hand-transcribed NAV total returns for the delisted funds (E3's ``evals/econ/etf_manual.yaml``)
    as long rows ``ticker, year, tr_nav`` (fraction; NaN = not found), ``source_url, kind``
    (``calendar_year`` | ``partial`` | ``liquidation``), ``date_from, date_to`` (stub bounds; the
    calendar year for full years), ``derived, method, note``.

    E3's layout: ``funds: [{ticker, years: [{year, tr_nav, …}], partial_periods: [{period:
    "YYYY-MM-DD..YYYY-MM-DD", tr_nav, derived, …}], last_trading_day, liquidation_date, …}]``. A stub
    whose end reaches the fund's liquidation date / last trading day is the ``liquidation`` row; an
    earlier-ending stub stays ``partial`` (the window past it is ``manual_incomplete``). The older
    ``entries:`` / ``rows:`` layouts used by the tests are accepted too. Percent fields (``tr_pct``)
    are divided by 100; an absent file yields an empty frame; a malformed file raises
    :class:`EtfGuardError` (``manual_ladder_unparseable``)."""
    doc = _load_manual_doc(path)
    rows: list[dict] = []

    def _year_row(ticker: str, r: dict) -> dict:
        y = int(r["year"])
        return {"ticker": ticker, "year": y, "tr_nav": _tr(r), "source_url": r.get("source_url"), "kind": "calendar_year",
                "date_from": pd.Timestamp(f"{y}-01-01"), "date_to": pd.Timestamp(f"{y}-12-31"),
                "derived": bool(r.get("derived", False)), "method": r.get("method"), "note": r.get("note")}

    for f in doc.get("funds", []) or []:
        t = f["ticker"]
        end_dates = [pd.to_datetime(f[k]) for k in ("last_trading_day", "liquidation_date") if f.get(k)]
        for r in f.get("years", []) or []:
            rows.append(_year_row(t, r))
        for r in f.get("partial_periods", []) or []:
            a, b = (pd.to_datetime(x) for x in str(r["period"]).split(".."))
            reaches_end = any(b >= d for d in end_dates) if end_dates else False
            rows.append({"ticker": t, "year": int(b.year), "tr_nav": _tr(r), "source_url": r.get("source_url"),
                         "kind": "liquidation" if reaches_end and a.month == 1 and a.day == 1 else "partial",
                         "date_from": a, "date_to": b, "derived": bool(r.get("derived", False)), "method": r.get("method"),
                         "note": r.get("note")})
    for r in doc.get("rows", []) or []:
        if r.get("date"):
            d = pd.to_datetime(r["date"])
            rows.append({"ticker": r["ticker"], "year": int(d.year), "tr_nav": _tr(r), "source_url": r.get("source_url"),
                         "kind": "liquidation", "date_from": pd.Timestamp(f"{d.year}-01-01"), "date_to": d,
                         "derived": bool(r.get("derived", False)), "method": r.get("method"), "note": r.get("note")})
        else:
            rows.append(_year_row(r["ticker"], r))
    for t, e in (doc.get("entries", {}) or {}).items():
        for r in e.get("years", []) or []:
            rows.append(_year_row(t, r))
        liq = e.get("liquidation")
        if liq:
            d = pd.to_datetime(liq["date"])
            rows.append({"ticker": t, "year": int(d.year), "tr_nav": _tr(liq), "source_url": liq.get("source_url"),
                         "kind": "liquidation", "date_from": pd.Timestamp(f"{d.year}-01-01"), "date_to": d,
                         "derived": False, "method": None, "note": None})
    out = pd.DataFrame(rows, columns=LADDER_COLS)
    if not out.empty:
        out["year"] = out["year"].astype(int)
    return out.sort_values(["ticker", "year", "kind"]).reset_index(drop=True)


def _cash_ladder_multiple(cl: dict) -> tuple[float, str] | None:
    """(terminal value per unit of the reference year-end NAV, reference key) from E3's ``cash_ladder``
    block — ``nav_YYYY_MM_DD`` (the last regular year-end NAV) plus ``distributions_total_to_date`` and
    ``residual_nav_YYYY_MM_DD``; None when the reference NAV is not transcribed."""
    if not cl:
        return None
    ref = sorted(k for k in cl if k.startswith("nav_") and cl[k] is not None)
    if not ref:
        return None
    nav_ref = float(cl[ref[0]])
    dist = float(cl.get("distributions_total_to_date") or 0.0)
    resid = [float(cl[k]) for k in cl if k.startswith("residual_nav_") and cl[k] is not None]
    return (dist + (resid[0] if resid else 0.0)) / nav_ref, ref[0]


def _manual_window(ticker: str, entry: dict, entry_date: pd.Timestamp, exit_date: pd.Timestamp,
                   ladder: pd.DataFrame, funds: dict[str, dict] | None = None) -> dict:
    """Compound the calendar-year ladder from the year after ``entry_date`` through ``exit_date``.

    The fund's end is E3's ``last_trading_day`` / ``liquidation_date`` when transcribed (NGE's real
    close was 2024-03-25, not the frozen universe's 2023-07-28), else the universe ``delisted`` date. A
    liquidation inside the window compounds the full years, then the final stub (kind ``liquidation``),
    then 0 % cash to the exit (``status='liquidated_in_window'``). Funds that halted with a residual NAV
    and later paid cash (ERUS, RSX) use the ``cash_ladder`` multiple from the last regular year-end.
    Anything the ladder does not cover (a null year, a stub that stops early, no cash ladder) leaves the
    value unchanged over that span and sets ``status='manual_incomplete'`` with the uncovered spans in
    ``incomplete`` — the row is never silently dropped."""
    rows = ladder[ladder["ticker"] == ticker]
    if rows.empty:
        raise EtfGuardError("manual_ladder_missing", ticker, "no rows in etf_manual.yaml")
    fund = (funds or {}).get(ticker, {})
    years_cal = rows[rows["kind"] == "calendar_year"].set_index("year")["tr_nav"].to_dict()
    liq_rows = rows[rows["kind"] == "liquidation"]
    part_rows = rows[rows["kind"] == "partial"]
    end_candidates = [d for d in (fund.get("last_trading_day"), fund.get("liquidation_date")) if d is not None and pd.notna(d)]
    fund_end = max(end_candidates) if end_candidates else (pd.Timestamp(entry["delisted"]) if pd.notna(entry.get("delisted")) else pd.NaT)
    cash = _cash_ladder_multiple(fund.get("cash_ladder") or {})
    v, path, incomplete, sources = 1.0, [(entry_date, 1.0)], [], []
    status, end_used = "manual", exit_date

    def _apply_partial(y: int, until: pd.Timestamp, label: str) -> None:
        """A Jan-1 stub covering part of year ``y``: apply it, list the uncovered remainder."""
        nonlocal v
        p = part_rows[(part_rows["year"] == y) & (part_rows["date_from"].dt.month == 1) & (part_rows["date_from"].dt.day == 1)]
        p = p[p["tr_nav"].notna()]
        if len(p):
            v *= 1.0 + float(p["tr_nav"].iloc[0])
            path.append((pd.Timestamp(p["date_to"].iloc[0]), v))
            incomplete.append(f"{pd.Timestamp(p['date_to'].iloc[0]).date()}..{until.date()} ({label} not transcribed)")
        else:
            incomplete.append(f"{y}-01-01..{until.date()} ({label} not transcribed)")

    for y in range(entry_date.year + 1, exit_date.year + 1):
        if cash is not None and f"nav_{y - 1}_12_31" == cash[1]:
            # halted fund: the cash actually released after the reference year-end, then 0 % cash
            v *= cash[0]
            path.append((fund_end if pd.notna(fund_end) else pd.Timestamp(f"{y}-12-31"), v))
            status, end_used = "liquidated_in_window", fund_end
            sources.append(f"cash_ladder from {cash[1]}")
            break
        in_liq_year = pd.notna(fund_end) and y == fund_end.year and fund_end <= exit_date
        if in_liq_year:
            stub = liq_rows[(liq_rows["year"] == y) & liq_rows["tr_nav"].notna()]
            if len(stub):
                v *= 1.0 + float(stub["tr_nav"].iloc[0])
                path.append((pd.Timestamp(stub["date_to"].iloc[0]), v))
            elif y in years_cal and pd.notna(years_cal[y]):
                # the halt year has a published calendar-year NAV return (the fund kept striking a NAV
                # after trading stopped): apply it; the cash paid afterwards is only expressible through
                # a cash_ladder with a reference NAV, which this fund lacks -> the tail is incomplete
                v *= 1.0 + years_cal[y]
                path.append((pd.Timestamp(f"{y}-12-31"), v))
                sources.append(f"halt year {y} from its calendar-year figure")
                if fund.get("cash_ladder"):
                    incomplete.append(f"{y}-12-31..{exit_date.date()} (post-halt cash distributions: reference NAV not transcribed)")
            else:
                _apply_partial(y, fund_end, "final stub")
            status, end_used = "liquidated_in_window", fund_end
            break
        if y in years_cal and pd.notna(years_cal[y]):
            v *= 1.0 + years_cal[y]
            path.append((pd.Timestamp(f"{y}-12-31"), v))
        else:
            _apply_partial(y, pd.Timestamp(f"{y}-12-31"), "calendar year")
    if incomplete:
        status = "manual_incomplete"
    vals = np.array([p[1] for p in path])
    max_dd = float((vals / np.maximum.accumulate(vals) - 1.0).min())
    years = (exit_date - entry_date).days / 365.25
    r_log = math.log(v) if v > 0 else float("-inf")
    return {"r_ann": r_log / years, "r_log": r_log, "years": years, "max_dd": max_dd, "max_dd_basis": "annual_nav_ladder",
            "status": status, "entry_used": entry_date, "exit_used": exit_date, "last_fund_day": end_used,
            "gross": v, "source": "etf_manual.yaml", "incomplete": incomplete, "sources": sources,
            "liquidated_in_window": status in ("liquidated_in_window", "manual_incomplete") and pd.notna(fund_end) and fund_end <= exit_date}


# ------------------------------------------------------------------------------------------------ calendar
def spy_calendar(**kw) -> pd.DatetimeIndex:
    """NYSE trading days as SPY's bar dates (1993-01-29 → today)."""
    return pd.DatetimeIndex(fetch_prices("SPY", **kw)["date"])


def last_trading_day(year: int, **kw) -> pd.Timestamp:
    """Last NYSE trading day of ``year`` from SPY's calendar."""
    cal = spy_calendar(**kw)
    days = cal[cal.year == year]
    if len(days) == 0:
        raise ValueError(f"no SPY bars in {year}")
    return pd.Timestamp(days.max())


def _bar_on_or_before(prices: pd.DataFrame, when: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    sub = prices[prices["date"] <= when]
    if sub.empty:
        return None
    r = sub.iloc[-1]
    return pd.Timestamp(r["date"]), float(r["adjclose"])


def _trading_days_between(cal: pd.DatetimeIndex, a: pd.Timestamp, b: pd.Timestamp) -> int:
    return int(((cal > a) & (cal <= b)).sum())


# ------------------------------------------------------------------------------------------------ window return
def window_return(ticker: str, entry: pd.Timestamp, exit: pd.Timestamp, *, ladder: pd.DataFrame | None = None,
                  funds: dict[str, dict] | None = None, universe: pd.DataFrame | None = None, **fetch_kw) -> dict:
    """USD total-return statistics of ``ticker`` over ``[entry, exit]`` from daily adjusted closes.

    ``{'r_ann'`` (log return per year), ``'r_log'`` (total log return), ``'years'``, ``'max_dd'``,
    ``'status'`` ∈ {ok, liquidated_in_window, manual, manual_incomplete, no_fund_at_entry, not_investable},
    ``'entry_used', 'exit_used'}``. Entry = the last bar on or before ``entry`` within 5 trading days
    (else ``not_investable``); exit = the last bar on or before ``exit``. A fund whose inception is
    after ``entry`` (or that had already left the market) is ``no_fund_at_entry``. Delisted funds go
    through the manual NAV ladder (``status`` manual / liquidated_in_window)."""
    entry, exit = pd.Timestamp(entry).normalize(), pd.Timestamp(exit).normalize()
    e = universe_entry(ticker, universe)
    base = {"ticker": ticker, "iso3": e.get("iso3"), "entry": entry, "exit": exit, "r_ann": float("nan"), "r_log": float("nan"),
            "years": (exit - entry).days / 365.25, "max_dd": float("nan"), "entry_used": pd.NaT, "exit_used": pd.NaT}
    if pd.Timestamp(e["inception"]) > entry or (pd.notna(e.get("delisted")) and pd.Timestamp(e["delisted"]) <= entry):
        return {**base, "status": "no_fund_at_entry"}
    if pd.notna(e.get("delisted")):
        fetch_prices(ticker, universe=universe, **fetch_kw)          # runs the guard (refusal asserted); no prices used
        lad = manual_ladder() if ladder is None else ladder
        fnd = manual_funds() if funds is None else funds
        return {**base, **_manual_window(ticker, e, entry, exit, lad, fnd)}
    prices = fetch_prices(ticker, universe=universe, **fetch_kw)
    cal = spy_calendar(universe=universe, **fetch_kw) if ticker != "SPY" else pd.DatetimeIndex(prices["date"])
    start = _bar_on_or_before(prices, entry)
    if start is None or _trading_days_between(cal, start[0], entry) > ENTRY_MAX_TRADING_DAYS_BACK:
        return {**base, "status": "not_investable"}
    end = _bar_on_or_before(prices, exit)
    if end is None or end[0] <= start[0]:
        return {**base, "status": "not_investable"}
    path = prices[(prices["date"] >= start[0]) & (prices["date"] <= end[0])]["adjclose"].to_numpy(dtype=float)
    years = (end[0] - start[0]).days / 365.25
    r_log = math.log(end[1] / start[1])
    return {**base, "r_ann": r_log / years, "r_log": r_log, "years": years,
            "max_dd": float((path / np.maximum.accumulate(path) - 1.0).min()), "max_dd_basis": "daily_adjclose",
            "status": "ok", "entry_used": start[0], "exit_used": end[0], "gross": end[1] / start[1]}


# ------------------------------------------------------------------------------------------------ VT benchmark
def _proxy_rule(entry: pd.Timestamp) -> str:
    """PREREG §3.5 proxies are pre-registered for the T = 2000 and T = 2005 windows; any other pre-VT
    entry uses the rule of the nearest pre-registered T at or before it (2000 for T < 2005)."""
    return "2005" if entry.year >= 2005 else "2000"


def _aligned(legs: dict[str, pd.DataFrame], cal: pd.DatetimeIndex) -> pd.DataFrame:
    frame = pd.DataFrame(index=cal)
    for k, p in legs.items():
        frame[k] = p.set_index("date")["adjclose"].reindex(cal).ffill()
    return frame


def vt_benchmark(entry: pd.Timestamp, exit: pd.Timestamp, *, universe: pd.DataFrame | None = None,
                 prices: dict[str, pd.DataFrame] | None = None, **fetch_kw) -> dict:
    """VT total return over ``[entry, exit]`` with the pre-registered proxy before VT's first bar.

    * ``entry`` ≥ 2008-06-24: VT itself (``benchmark='vt'``).
    * T = 2000 rule (entry before 2005): SPY 100 % until EFA's first bar, then SPY 60 / EFA 40;
    * T = 2005 rule: SPY 50 / EFA 40 / EEM 10 from entry;
    * both rebalanced to target on the last trading day of every calendar year and carried into VT
      at VT's adjusted close on its first bar ≥ 2008-06-24 (frictionless; ``benchmark='vt_proxy'``).

    ``prices`` may supply ``{ticker: date/adjclose frame}`` (tests); otherwise the guarded cache is
    used. Returns ``{'r_ann', 'r_log', 'years', 'benchmark', 'proxy_rule', 'legs', 'rebalance_dates',
    'switch_date', 'efa_start', 'entry_used', 'exit_used', 'gross'}``."""
    entry, exit = pd.Timestamp(entry).normalize(), pd.Timestamp(exit).normalize()
    need = ["SPY", "EFA", "EEM", "VT"]
    px = dict(prices or {})
    for t in need:
        if t not in px:
            px[t] = fetch_prices(t, universe=universe, **fetch_kw)
    cal = pd.DatetimeIndex(px["SPY"]["date"])
    cal = cal[(cal >= entry - pd.Timedelta(days=10)) & (cal <= exit)]
    start = cal[cal <= entry]
    if len(start) == 0:
        raise ValueError(f"no SPY bar on or before {entry.date()}")
    entry_used, exit_used = pd.Timestamp(start[-1]), pd.Timestamp(cal[-1])
    cal = cal[(cal >= entry_used)]
    frame = _aligned(px, cal)
    vt_first = px["VT"]["date"][px["VT"]["date"] >= VT_INCEPTION].min()
    efa_first = px["EFA"]["date"].min()
    if entry_used >= vt_first:
        r_log = math.log(frame.loc[exit_used, "VT"] / frame.loc[entry_used, "VT"])
        years = (exit_used - entry_used).days / 365.25
        return {"r_ann": r_log / years, "r_log": r_log, "years": years, "benchmark": "vt", "proxy_rule": None,
                "legs": [{"from": entry_used, "to": exit_used, "weights": {"VT": 1.0}}], "rebalance_dates": [],
                "switch_date": None, "efa_start": None, "entry_used": entry_used, "exit_used": exit_used, "gross": math.exp(r_log)}
    rule = _proxy_rule(entry_used)

    def target(day: pd.Timestamp) -> dict[str, float]:
        if day >= vt_first:
            return {"VT": 1.0}
        if rule == "2000":
            return PROXY_WEIGHTS["2000"]["after_efa"] if day >= efa_first else PROXY_WEIGHTS["2000"]["before_efa"]
        return PROXY_WEIGHTS["2005"]["all"]

    year_ends = {pd.Timestamp(d) for d in pd.Series(cal).groupby(cal.year).max() if d < exit_used}
    events = set(year_ends) | {entry_used}
    switch = pd.Timestamp(cal[cal >= vt_first].min()) if (cal >= vt_first).any() else None
    if switch is not None:
        events.add(switch)
    efa_start = None
    if rule == "2000" and (cal >= efa_first).any() and entry_used < efa_first:
        efa_start = pd.Timestamp(cal[cal >= efa_first].min())
        events.add(efa_start)
    units: dict[str, float] = {}
    value, legs, rebal = 1.0, [], []
    seg_from, seg_w = entry_used, None
    for day in cal:
        row = frame.loc[day]
        if units:
            value = float(sum(u * row[k] for k, u in units.items()))
        if day in events:
            w = target(day)
            units = {k: value * wk / float(row[k]) for k, wk in w.items() if wk > 0}
            if seg_w is not None and w != seg_w:
                legs.append({"from": seg_from, "to": day, "weights": seg_w})
                seg_from = day
            seg_w = w
            rebal.append(day)
    legs.append({"from": seg_from, "to": exit_used, "weights": seg_w})
    years = (exit_used - entry_used).days / 365.25
    r_log = math.log(value)
    return {"r_ann": r_log / years, "r_log": r_log, "years": years, "benchmark": "vt_proxy", "proxy_rule": rule, "legs": legs,
            "rebalance_dates": sorted(rebal), "switch_date": switch, "efa_start": efa_start,
            "entry_used": entry_used, "exit_used": exit_used, "gross": value}


# ------------------------------------------------------------------------------------------------ equal-weight basket
def ew_basket(T: int, entry: pd.Timestamp, exit: pd.Timestamp, *, strict: bool = True, one_per_country: bool = False,
              universe: pd.DataFrame | None = None, ladder: pd.DataFrame | None = None, funds: dict[str, dict] | None = None,
              **fetch_kw) -> dict:
    """Equal-weight (weights set at ``entry`` only, no rebalancing) total return of ALL
    ``role == single_country`` instruments with ``inception <= entry`` that were still trading at
    entry, liquidations compounding to the liquidation NAV then 0 % cash (PREREG §3.4–3.5). The
    basket's gross return is the mean of the members' gross returns; ``r_ann = ln(mean)/years``.

    ``strict=True`` raises :class:`EtfGuardError` when a delisted member lacks its ladder or its ladder
    does not reach the exit (``manual_incomplete``) — silently dropping it would reintroduce
    survivorship; ``strict=False`` keeps ``manual_incomplete`` members at their known path value
    (missing spans at 0 %) and lists them under ``incomplete``, excluding only members with no ladder
    at all (``n_missing_manual``). ``one_per_country`` keeps the earliest-inception fund per iso3."""
    u = load_universe() if universe is None else universe
    entry, exit = pd.Timestamp(entry).normalize(), pd.Timestamp(exit).normalize()
    m = u[(u["role"] == "single_country") & (u["inception"] <= entry) & (u["delisted"].isna() | (u["delisted"] > entry))]
    if one_per_country:
        m = m.sort_values("inception").drop_duplicates("iso3")
    lad = manual_ladder() if ladder is None else ladder
    fnd = manual_funds() if funds is None else funds
    members, gross, missing, incomplete, liquidated = [], [], [], [], 0
    for t in sorted(m["ticker"]):
        try:
            w = window_return(t, entry, exit, ladder=lad, funds=fnd, universe=u, **fetch_kw)
        except EtfGuardError as err:
            if err.assertion == "manual_ladder_missing" and not strict:
                missing.append(t)
                continue
            raise
        if w["status"] == "manual_incomplete":
            if strict:
                raise EtfGuardError("manual_ladder_incomplete", t, "; ".join(w.get("incomplete", [])))
            incomplete.append(t)
        if w["status"] in ("ok", "manual", "liquidated_in_window", "manual_incomplete"):
            members.append({"ticker": t, "iso3": w["iso3"], "status": w["status"], "r_log": w["r_log"], "gross": w["gross"]})
            gross.append(w["gross"])
            liquidated += bool(w.get("liquidated_in_window")) or w["status"] == "liquidated_in_window"
    years = (exit - entry).days / 365.25
    mean_gross = float(np.mean(gross)) if gross else float("nan")
    return {"T": T, "r_ann": math.log(mean_gross) / years if gross else float("nan"), "r_log": math.log(mean_gross) if gross else float("nan"),
            "years": years, "n": len(gross), "n_liquidated": int(liquidated), "n_missing_manual": len(missing),
            "missing_manual": missing, "incomplete": incomplete, "members": members, "entry": entry, "exit": exit}


# ------------------------------------------------------------------------------------------------ cross-check
def _annualised_pct(p0: float, p1: float, d0: pd.Timestamp, d1: pd.Timestamp) -> float:
    years = (d1 - d0).days / 365.25
    return 100.0 * ((p1 / p0) ** (1.0 / years) - 1.0)


def crosscheck(path: Path = CROSSCHECK_YAML, *, universe: pd.DataFrame | None = None, **fetch_kw) -> pd.DataFrame:
    """Computed annualised total returns from adjusted closes vs the issuer NAV figures in
    ``etf_crosscheck.yaml`` — the 10-year figure (first bar on or before ``as_of − 10 y`` to the bar on
    or before ``as_of``) and since-inception (first clipped bar → ``as_of``; SPY's alternative
    since-inception figure at its own date). Columns ``ticker, figure, as_of, start_used, end_used,
    published_pct, computed_pct, delta_pp, tolerance_pp, passed``."""
    doc = yaml.safe_load(Path(path).read_text())
    tol = float(doc.get("tolerance_pp", 0.5))
    rows = []
    for ticker, e in doc["entries"].items():
        if str(e.get("verified", "")).lower() != "yes":
            continue
        prices = fetch_prices(ticker, universe=universe, **fetch_kw)
        for fig in e.get("check", []):
            if fig == "since_inception_alt":
                alt = e["since_inception_alt"]
                as_of, published = pd.Timestamp(alt["as_of"]), alt["nav_pct"]
                start = (pd.Timestamp(prices["date"].iloc[0]), float(prices["adjclose"].iloc[0]))
            else:
                as_of, published = pd.Timestamp(e["as_of"]), e["nav_pct"][fig]
                if fig == "since_inception":
                    start = (pd.Timestamp(prices["date"].iloc[0]), float(prices["adjclose"].iloc[0]))
                else:
                    n = int(fig.rstrip("y"))
                    start = _bar_on_or_before(prices, as_of - pd.DateOffset(years=n))
            end = _bar_on_or_before(prices, as_of)
            if start is None or end is None or published is None:
                rows.append({"ticker": ticker, "figure": fig, "as_of": as_of, "start_used": None, "end_used": None,
                             "published_pct": published, "computed_pct": float("nan"), "delta_pp": float("nan"),
                             "tolerance_pp": tol, "passed": False})
                continue
            computed = _annualised_pct(start[1], end[1], start[0], end[0])
            rows.append({"ticker": ticker, "figure": fig, "as_of": as_of, "start_used": start[0], "end_used": end[0],
                         "published_pct": float(published), "computed_pct": computed, "delta_pp": computed - float(published),
                         "tolerance_pp": tol, "passed": bool(abs(computed - float(published)) <= tol)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ derived table
RETURN_GRID_T = (2000, 2005, 2010, 2015)          # PREREG §3.1 returns rows, h = 10


def window_table(*, universe: pd.DataFrame | None = None, ladder: pd.DataFrame | None = None, **fetch_kw) -> pd.DataFrame:
    """Derived statistics only (never prices): one row per instrument × pre-registered return window
    (entry = last trading day of T, exit = last trading day of T + 10) with the status, ``r_ann``,
    ``max_dd``, the VT / VT-proxy return over the identical window and the excess; plus one
    ``since_inception`` row per live instrument. Delisted funds without their ladder yet are
    ``manual_missing`` rather than an error, so the table can be written before E3's yaml lands."""
    u = load_universe() if universe is None else universe
    try:
        lad = manual_ladder() if ladder is None else ladder
        fnd = manual_funds()
    except EtfGuardError as err:                      # E3's file absent/malformed: every manual row waits
        print(f"etf_manual.yaml unusable ({err}); manual rows are 'manual_missing'")
        lad, fnd = pd.DataFrame(columns=LADDER_COLS), {}
    rows = []
    vt_cache: dict[int, dict] = {}
    for T in RETURN_GRID_T:
        entry, exit = last_trading_day(T, universe=u, **fetch_kw), last_trading_day(T + 10, universe=u, **fetch_kw)
        vt_cache[T] = vt_benchmark(entry, exit, universe=u, **fetch_kw)
        for t in u["ticker"]:
            try:
                w = window_return(t, entry, exit, ladder=lad, funds=fnd, universe=u, **fetch_kw)
            except EtfGuardError as err:
                if err.assertion != "manual_ladder_missing":
                    raise
                w = {"status": "manual_missing", "r_ann": float("nan"), "r_log": float("nan"), "max_dd": float("nan"),
                     "entry_used": pd.NaT, "exit_used": pd.NaT}
            v = vt_cache[T]
            rows.append({"ticker": t, "iso3": u.loc[t, "iso3"], "role": u.loc[t, "role"], "T": T, "h": 10,
                         "entry": entry.date(), "exit": exit.date(), "status": w["status"],
                         "entry_used": None if pd.isna(w["entry_used"]) else pd.Timestamp(w["entry_used"]).date(),
                         "exit_used": None if pd.isna(w["exit_used"]) else pd.Timestamp(w["exit_used"]).date(),
                         "r_ann": w["r_ann"], "r_log": w["r_log"], "max_dd": w["max_dd"],
                         "r_vt_ann": v["r_ann"], "benchmark": v["benchmark"], "er_ann": w["r_ann"] - v["r_ann"],
                         "incomplete": "; ".join(w.get("incomplete", []) or [])})
    for t in u["ticker"]:
        rec = _REPORT["tickers"].get(t) or {}
        if u.loc[t, "is_delisted"] or not rec.get("passed"):
            continue
        p = fetch_prices(t, universe=u, **fetch_kw)
        d0, d1 = pd.Timestamp(p["date"].iloc[0]), pd.Timestamp(p["date"].iloc[-1])
        r_log = math.log(float(p["adjclose"].iloc[-1]) / float(p["adjclose"].iloc[0]))
        years = (d1 - d0).days / 365.25
        path = p["adjclose"].to_numpy(dtype=float)
        rows.append({"ticker": t, "iso3": u.loc[t, "iso3"], "role": u.loc[t, "role"], "T": None, "h": None,
                     "entry": d0.date(), "exit": d1.date(), "status": "since_inception", "entry_used": d0.date(), "exit_used": d1.date(),
                     "r_ann": r_log / years, "r_log": r_log, "max_dd": float((path / np.maximum.accumulate(path) - 1.0).min()),
                     "r_vt_ann": float("nan"), "benchmark": None, "er_ann": float("nan"), "incomplete": ""})
    return pd.DataFrame(rows)


__all__ = ["EtfGuardError", "load_universe", "universe_entry", "raw_prices", "fetch_prices", "guard", "signature", "clip_to_yaml",
           "manual_ladder", "manual_funds", "window_return", "vt_benchmark", "ew_basket", "last_trading_day", "spy_calendar", "crosscheck",
           "window_table", "guard_report", "PROXY_WEIGHTS", "VT_INCEPTION", "UNIVERSE_YAML", "MANUAL_YAML", "GUARD_REPORT"]
