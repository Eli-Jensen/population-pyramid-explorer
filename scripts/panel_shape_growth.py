#!/usr/bin/env python
"""Experiment 2 — shape → growth panel (evals/econ/PREREG.md §4) → evals/econ/panel_shape_growth.json + tables/panel_coefs.csv.

    uv run --group econ scripts/panel_shape_growth.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.econ import panel, results
from pyramid_explorer.paths import ECON_EVALS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(ECON_EVALS))
    ap.add_argument("--allow-uncommitted-prereg", action="store_true")
    args = ap.parse_args(argv)
    ok, why = results.prereg_is_committed()
    if not ok and not args.allow_uncommitted_prereg:
        print(f"[panel_shape_growth] refusing to run: {why} (PREREG §0.1)", file=sys.stderr)
        return 2
    say = lambda s: print(s, file=sys.stderr)
    corpus, gd = lk.load_real_corpus(), lk.load_real_growth()
    res, coefs = panel.run(corpus, gd, log=say)
    res["_meta"]["run"] = results.run_metadata(seed=lk.SEED, B=0)
    out = Path(args.out_dir)
    lk.dump_json(res, out / "panel_shape_growth.json")
    (out / "tables").mkdir(parents=True, exist_ok=True)
    coefs.to_csv(out / "tables" / "panel_coefs.csv", index=False)
    s3 = res["specs"]["S3"]["coef"]
    print(f"n={res['sample']['n']} N_eff={res['sample']['n_eff']} | S3: " + ", ".join(f"{k} β={v['beta']:+.4f} p_DK={v['p_dk']:.3f}" for k, v in s3.items()))
    print("OOS R² vs mean: " + ", ".join(f"{k} {v['vs_mean']:+.4f}" for k, v in res["holdout"]["oos_r2"].items()))
    print("predictions: " + ", ".join(f"{k}: {'met' if v.get('met') else 'not met'}" for k, v in res["predictions"].items()))
    print(f"wrote {out / 'panel_shape_growth.json'} and {out / 'tables' / 'panel_coefs.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
