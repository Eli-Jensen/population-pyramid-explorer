#!/usr/bin/env python
"""Fetch the pre-registered ETF universe, run the survivorship guard and the issuer cross-check, and
write the derived tables (PREREG.md §6; ``make backtest`` step 1).

Outputs
  data/raw/etf/<TICKER>.parquet + .meta.json   raw Yahoo bars (gitignored; never shipped)
  data/out/etf_guard_report.json               every guard decision, per ticker
  evals/econ/tables/etf_returns.csv            derived window statistics only (no prices)
  evals/econ/tables/etf_crosscheck.csv         computed vs published annualised returns (deltas)
  evals/econ/tables/gdp_pc.parquet, windows.parquet   the GDP-per-capita tables (--tables)

Exit status is non-zero when any guard assertion fails or any cross-check delta exceeds the
tolerance — the build stops, as pre-registered. ``--dead-series ok`` accepts a multi-bar Yahoo
history for a delisted ticker as a recorded deviation (the series is still never used).
Refuses to run while evals/econ/PREREG.md is uncommitted or modified (PREREG §0.1).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer.econ import data as econ_data  # noqa: E402
from pyramid_explorer.econ import etf  # noqa: E402
from pyramid_explorer.paths import ECON_EVALS, REPO_ROOT  # noqa: E402

TABLES = ECON_EVALS / "tables"


def prereg_committed() -> tuple[bool, str]:
    """(ok, hash): PREREG.md must have a commit and no uncommitted modification."""
    rel = "evals/econ/PREREG.md"
    try:
        h = subprocess.run(["git", "log", "-1", "--format=%H", "--", rel], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, f"git unavailable: {e}"
    if not h:
        return False, "evals/econ/PREREG.md has no commit"
    if dirty:
        return False, f"evals/econ/PREREG.md has uncommitted changes ({dirty})"
    return True, h


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download every ticker (ignore the parquet cache)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD used by guard assertion 3 (default: the run date)")
    ap.add_argument("--tickers", nargs="*", default=None, help="subset of tickers (default: the whole universe)")
    ap.add_argument("--dead-series", choices=["fail", "ok"], default="fail",
                    help="a multi-bar Yahoo history for a delisted ticker: fail (PREREG §6 A4) or record as a deviation")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between tickers on a cold cache")
    ap.add_argument("--no-tables", action="store_true", help="skip gdp_pc/windows parquet tables")
    ap.add_argument("--skip-prereg-check", action="store_true", help="(tests only) do not require a committed PREREG.md")
    args = ap.parse_args(argv)

    if not args.skip_prereg_check:
        ok, msg = prereg_committed()
        if not ok:
            print(f"REFUSED: {msg}. Commit evals/econ/PREREG.md first (PREREG §0.1).", file=sys.stderr)
            return 2
        print(f"PREREG.md commit: {msg}")

    today = pd.Timestamp(args.today) if args.today else pd.Timestamp.today().normalize()
    universe = etf.load_universe()
    tickers = list(args.tickers) if args.tickers else list(universe["ticker"])
    kw = dict(today=today, dead_series=args.dead_series, universe=universe)
    print(f"universe: {len(universe)} instruments ({(universe['role'] == 'single_country').sum()} single-country, "
          f"{(universe['role'] == 'benchmark').sum()} benchmarks, {(universe['role'] == 'basket').sum()} basket); "
          f"{int(universe['is_delisted'].sum())} delisted; today={today.date()}; dead-series={args.dead_series}")

    failures: list[tuple[str, str]] = []
    print(f"{'ticker':6s} {'symbol':6s} {'role':14s} {'sig':8s} {'n_raw':>6s} {'first_raw':10s} {'last_raw':10s} {'n':>6s} {'first':10s} {'last':10s} result")
    for t in tickers:
        cold = not (etf.DATA_RAW_ETF / f"{t}.parquet").exists() or args.force
        try:
            etf.fetch_prices(t, force=args.force, **kw)
            rec = etf.guard_report()[t]
            verdict = "manual-ladder" if rec["route"] == "manual" else "ok"
            if rec.get("deviation"):
                verdict += " DEVIATION(A4 not refused)"
        except etf.EtfGuardError as err:
            rec = etf.guard_report().get(t, {})
            verdict = f"FAIL {err.assertion}"
            failures.append((t, err.assertion))
        print(f"{t:6s} {str(rec.get('symbol')):6s} {str(rec.get('role')):14s} {str(rec.get('signature')):8s} {str(rec.get('n_raw_bars')):>6s} "
              f"{str(rec.get('first_raw_bar')):10s} {str(rec.get('last_raw_bar')):10s} {str(rec.get('n_bars')):>6s} "
              f"{str(rec.get('first_bar')):10s} {str(rec.get('last_bar')):10s} {verdict}")
        if cold and args.sleep:
            time.sleep(args.sleep)

    # cross-check (only meaningful when the seven funds passed)
    cc_fail = 0
    try:
        cc = etf.crosscheck(**kw)
        TABLES.mkdir(parents=True, exist_ok=True)
        cc.to_csv(TABLES / "etf_crosscheck.csv", index=False)
        print("\ncross-check vs issuer NAV figures (|delta| <= tolerance):")
        for r in cc.itertuples():
            print(f"  {r.ticker:4s} {r.figure:20s} as_of={pd.Timestamp(r.as_of).date()} start={r.start_used and pd.Timestamp(r.start_used).date()} "
                  f"published={r.published_pct:7.2f} computed={r.computed_pct:7.2f} delta={r.delta_pp:+6.2f} pp  {'ok' if r.passed else 'FAIL'}")
        cc_fail = int((~cc["passed"]).sum())
    except etf.EtfGuardError as err:
        print(f"\ncross-check skipped: {err}")
        cc_fail = 1

    # derived tables
    if not failures or args.dead_series == "ok":
        try:
            tbl = etf.window_table(**kw)
            tbl.to_csv(TABLES / "etf_returns.csv", index=False)
            n_manual_missing = int((tbl["status"] == "manual_missing").sum())
            print(f"\nwrote {TABLES / 'etf_returns.csv'} ({len(tbl)} rows; {n_manual_missing} window rows await etf_manual.yaml)")
        except etf.EtfGuardError as err:
            print(f"\netf_returns.csv not written: {err}")
    if not args.no_tables:
        paths = econ_data.write_tables(TABLES)
        print("wrote " + ", ".join(str(p) for p in paths.values()))

    report = json.loads(etf.GUARD_REPORT.read_text()) if etf.GUARD_REPORT.exists() else {}
    report["run"] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "today": str(today.date()),
                     "dead_series_policy": args.dead_series, "n_tickers": len(tickers), "failures": failures,
                     "crosscheck_failures": cc_fail}
    etf.GUARD_REPORT.write_text(json.dumps(report, indent=1, default=str))
    print(f"guard report: {etf.GUARD_REPORT}")
    if failures or cc_fail:
        print(f"\nBUILD STOPS: {len(failures)} guard failure(s) {failures}, {cc_fail} cross-check failure(s)", file=sys.stderr)
        return 1
    print("\nall guard assertions and cross-checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
