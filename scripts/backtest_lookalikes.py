#!/usr/bin/env python
"""Experiment 1 — lookalike-as-of-T (evals/econ/PREREG.md §3) → evals/econ/backtest_lookalikes.json + tables/backtest_picks.csv.

    uv run --group econ scripts/backtest_lookalikes.py [--B 5000] [--no-returns] [--queries A,B,B_soft,B3,C,N4] [--vintage]

Reads the built corpus (DuckDB store / exports), the GDP windows through ``econ.data`` and — unless ``--no-returns`` —
the cached ETF prices through ``econ.etf`` (run ``scripts/fetch_etf.py`` first).  Refuses to run unless
``evals/econ/PREREG.md`` is committed and unmodified (PREREG §0.1).  ``--vintage`` is accepted for the pre-registered
optional re-run; the WPP 2010 / 2000 archives are not wired in this build, so it records that fact in the output.
"""
from __future__ import annotations

import argparse
import sys

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.econ import results
from pyramid_explorer.paths import ECON_EVALS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--B", type=int, default=lk.B_DEFAULT, help="bootstrap / null draws (PREREG: 5000)")
    ap.add_argument("--seed", type=int, default=lk.SEED)
    ap.add_argument("--no-returns", action="store_true", help="growth outcomes only (no ETF prices needed)")
    ap.add_argument("--queries", default=",".join(lk.QUERIES))
    ap.add_argument("--vintage", action="store_true", help="pre-registered optional re-run on WPP 2010/2000 archives (not wired)")
    ap.add_argument("--out-dir", default=str(ECON_EVALS))
    ap.add_argument("--allow-uncommitted-prereg", action="store_true", help="development only; the Makefile never passes this")
    args = ap.parse_args(argv)

    ok, why = results.prereg_is_committed()
    if not ok and not args.allow_uncommitted_prereg:
        print(f"[backtest_lookalikes] refusing to run: {why} (PREREG §0.1)", file=sys.stderr)
        return 2
    say = lambda s: print(s, file=sys.stderr)
    say("[backtest_lookalikes] loading corpus + growth windows")
    corpus = lk.load_real_corpus()
    gd = lk.load_real_growth()
    provider = None
    if not args.no_returns:
        say("[backtest_lookalikes] ETF returns provider (econ.etf)")
        provider = lk.EtfReturns()
    res, table = lk.run(corpus, gd, provider, B=args.B, seed=args.seed, queries=tuple(q for q in args.queries.split(",") if q), log=say)
    res["_meta"]["run"] = results.run_metadata(seed=args.seed, B=args.B)
    res["_meta"]["returns_computed"] = provider is not None
    res["_meta"]["vintage"] = ("requested but not performed: WPP 2010 / WPP 2000 archive inputs are not wired in this build; "
                               "the PREREG §8 paragraph stands" if args.vintage else "not requested")
    res["_meta"]["implementation_notes"] = [
        "Prototype top decile is taken over windows with pop ≥ 1 M ending ≤ T (the same set the prototypes are drawn from).",
        "The N4 comparator's p-value is a paired block bootstrap of μ̂(lookalikes) − μ̂(N4) on the same resamples (both schemes; the larger p is reported) — PREREG names the comparison but not the test.",
        "Kernel SEs (Hansen–Hodrick, Newey–West) are reported as n/a when the T-aggregated series has no more points than lags + 1 (h = 20 rows have three T's).",
        "N2 is computed for growth outcomes; return outcomes use N1-investable and N4-investable as pre-registered.",
        "The T = 2015 partial growth window (h = 8 / 7) is pooled into the h = 10 rows and flagged; n_partial is printed on every row.",
        "PREREG §3.6 item 6 ('country-cluster HAC SE, cluster = country across T') is reported as the plain one-way country-cluster SE "
        "(every within-country pair weight 1, 'country-cluster SE'); the within-country Bartlett-kernel variant truncated at L = h/5 − 1 "
        "grid steps (same-country pairs ≥ 2 steps apart get weight 0) is printed beside it under its own label. Neither is the headline.",
        "For h = 20 rows the circular T-block bootstrap is degenerate by construction (three T's, block length 4 ≥ n_T: every resample is the "
        "full series), so its 'interval' is a point; such cells are flagged, and the country-cluster CI — the wider one — is the headline.",
        "The 36 statistic rows (24 growth + 12 returns, every query × k × h × outcome) are reported without a multiple-comparison adjustment; "
        "only Query B k = 10 h = 10 is confirmatory (P1, P3 and the decision rules read it), every other row is secondary or informational.",
    ]
    out = ECON_EVALS if args.out_dir == str(ECON_EVALS) else __import__("pathlib").Path(args.out_dir)
    lk.dump_json(res, out / "backtest_lookalikes.json")
    (out / "tables").mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "tables" / "backtest_picks.csv", index=False)
    for key in ("B|10|10|growth", "B|10|20|growth", "B|10|10|returns", "A|10|10|growth", "N4|10|10|growth"):
        row = res["rows"].get(key)
        if not row:
            continue
        s = row["stats"]
        extra = f" status={row.get('status_counts')}" if row["outcome"] == "returns" else ""
        n1 = row["nulls"].get("N1") or row["nulls"].get("N1_investable") or {}
        print(f"{key:20s} n={s['n']:3d} N_eff={s['n_eff']:3d} mean excess={s['mean_excess']:+.2f} pp/yr hit={s['hit_rate']:.2f} "
              f"CI={s['ci_headline']} p_N1={n1.get('p_mean_excess')}{extra}")
    print("predictions: " + ", ".join(f"{k}: {'met' if v.get('met') else 'not met'}" for k, v in res["predictions"].items()))
    print(f"wrote {out / 'backtest_lookalikes.json'} and {out / 'tables' / 'backtest_picks.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
