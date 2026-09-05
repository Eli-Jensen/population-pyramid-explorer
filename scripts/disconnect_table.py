#!/usr/bin/env python
"""Experiment 3 — disconnect table (evals/econ/PREREG.md §5) → evals/econ/disconnect.json + tables/disconnect.csv.

    uv run --group econ scripts/disconnect_table.py [--no-etf]

MSCI numbers are cited from evals/econ/msci_citations.yaml (facts, never series); fund statistics come from the
cached daily adjusted closes through ``econ.etf`` unless ``--no-etf``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from pyramid_explorer.econ import disconnect, lookalike as lk, results
from pyramid_explorer.paths import ECON_EVALS


def load_tfr() -> dict | None:
    """``{(iso3, year): TFR}`` from the store's ``tfr_wpp`` (or ``tfr``) indicator; None when unavailable."""
    try:
        from pyramid_explorer import db
        with db.connect(read_only=True) as con:
            ids = {r[0] for r in con.execute("SELECT id FROM indicator").fetchall()}
            ind = "tfr_wpp" if "tfr_wpp" in ids else ("tfr" if "tfr" in ids else None)
            if ind is None:
                return None
            df = db.load_indicator(con, ind)
        return {(str(e), int(y)): float(v) for e, y, v in zip(df["entity_id"], df["year"], df["value"])}
    except Exception as exc:  # noqa: BLE001 — TFR is optional (PREREG §5: omit when absent)
        print(f"[disconnect_table] TFR unavailable: {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-etf", action="store_true", help="skip fund statistics (no price data needed)")
    ap.add_argument("--out-dir", default=str(ECON_EVALS))
    ap.add_argument("--allow-uncommitted-prereg", action="store_true")
    args = ap.parse_args(argv)
    ok, why = results.prereg_is_committed()
    if not ok and not args.allow_uncommitted_prereg:
        print(f"[disconnect_table] refusing to run: {why} (PREREG §0.1)", file=sys.stderr)
        return 2
    say = lambda s: print(s, file=sys.stderr)
    corpus, gd = lk.load_real_corpus(), lk.load_real_growth()
    citations = yaml.safe_load((ECON_EVALS / "msci_citations.yaml").read_text())
    universe = etf_mod = None
    if not args.no_etf:
        from pyramid_explorer.econ import etf as etf_mod
        universe = etf_mod.load_universe()
    res, table = disconnect.run(corpus, gd.levels, citations, tfr=load_tfr(), universe=universe, etf_mod=etf_mod, log=say)
    res["_meta"]["run"] = results.run_metadata(seed=lk.SEED, B=0)
    out = Path(args.out_dir)
    lk.dump_json(res, out / "disconnect.json")
    (out / "tables").mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "tables" / "disconnect.csv", index=False)
    with __import__("pandas").option_context("display.width", 250, "display.max_columns", 40):
        print(table[["iso3", "year", "median_age", "wa", "d_blend_chn1990", "pct_band", "mult_10", "mult_30", "msci_ann_pct_gross", "ticker", "fund_cagr_pct", "vt_ann_log_pct", "fund_state"]].to_string(index=False))
    print(f"wrote {out / 'disconnect.json'} and {out / 'tables' / 'disconnect.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
