#!/usr/bin/env python
"""Fit and report the human triplets (PLAN §4.6 item 8; evals/protocol.md §3) → evals/TRIPLETS.md + evals/triplets_fit.json.

    uv run scripts/fit_params.py                          # evals/triplets.json (the rater's answers) + the selection
    uv run scripts/fit_params.py --synthetic              # noisy oracle → evals/triplets.synthetic.json, then fit it
    uv run scripts/fit_params.py --synthetic --oracle-w 0.7 --oracle-sigma 0 --noise 0.1 --seed 3

Order of operations (pre-registered): self-agreement on the 8 duplicate pairs first — below 6/8 the script says so
and marks everything informational; then pairwise agreement per metric, exact sign tests (blend vs the exposed image
space on the 32 visual items; every numeric pair on the 48 numeric/opposite items), and the leave-one-out grid over
the blend weight / smoothing (and λ for w1bal) on the numeric strata only.  `evals/verdicts.json` is read for the
G1/G2/G4 gates but NEVER written: a recommended change is printed for review.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer import triplets as T  # noqa: E402

SYNTHETIC_PATH = T.EVALS / "triplets.synthetic.json"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection", type=Path, default=T.SELECTION_PATH)
    ap.add_argument("--responses", type=Path, default=None, help=f"default {T.RESPONSES_PATH} ({SYNTHETIC_PATH} with --synthetic)")
    ap.add_argument("--report", type=Path, default=T.REPORT_PATH)
    ap.add_argument("--fit-out", type=Path, default=T.FIT_PATH)
    ap.add_argument("--synthetic", action="store_true", help="write a noisy-oracle responses file first and fit that")
    ap.add_argument("--oracle-metric", default="blend", help="metric the oracle answers by (default blend)")
    ap.add_argument("--oracle-w", type=float, default=None, help="oracle blend weight on L2 (re-weighted blend)")
    ap.add_argument("--oracle-sigma", type=int, default=None, choices=(0, 1), help="oracle smoothing in bins")
    ap.add_argument("--oracle-lambda", type=float, default=None, help="oracle w1bal λ")
    ap.add_argument("--noise", type=float, default=0.1)
    ap.add_argument("--tie-rate", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    if not a.selection.exists():
        sys.exit(f"{a.selection} missing — run `make triplets-select` first")
    sel = json.loads(a.selection.read_text())
    responses_path = a.responses or (SYNTHETIC_PATH if a.synthetic else T.RESPONSES_PATH)
    if a.synthetic:
        responses = T.synthetic_responses(sel, seed=a.seed, metric=a.oracle_metric, w_l2=a.oracle_w, sigma_bins=a.oracle_sigma,
                                          lam=a.oracle_lambda, noise=a.noise, tie_rate=a.tie_rate)
        responses_path.write_text(json.dumps(responses, indent=1) + "\n")
        print(f"[synthetic] wrote {responses_path} (oracle {responses['oracle']})")
    elif not responses_path.exists():
        sys.exit(f"{responses_path} missing — Eli has not judged yet; use --synthetic to exercise the pipeline")
    else:
        responses = json.loads(responses_path.read_text())
    if responses.get("synthetic") and not a.synthetic:
        print("[warning] the responses file is marked synthetic — the report says so")
    verdicts = json.loads(T.VERDICTS_PATH.read_text()) if T.VERDICTS_PATH.exists() else None

    f = T.fit(sel, responses, verdicts)
    a.fit_out.write_text(json.dumps(f, indent=1, ensure_ascii=False) + "\n")
    a.report.write_text(T.render_report(f, sel))

    sa = f["self_agreement"]
    print(f"self-agreement {sa['n_agree']}/{sa['n_pairs']} → {'gate met' if sa['passes'] else 'GATE NOT MET'}: {f['status']}")
    if not sa["passes"]:
        print("  ⇒ no verdict may be promoted above `lab` on triplet evidence; shipped defaults stay w = 0.5 on raw shares (σ = 0), λ = 50")
    print(f"answered {f['n_answered']}/{f['n_items']}, ties {f['n_tie']}")
    print("pairwise agreement:", ", ".join(f"{m} {T._pct(r['agreement'])}" for m, r in f["agreement"].items()))
    t = f["tests"]["blend_vs_visual"]
    print(f"blend vs {t['b']}: {t['wins_a']}–{t['wins_b']} on {t['n_discordant']} discordant, p = {T._p(t['p'])}, called: {t['winner'] or 'no'}")
    b, w = f["grid"]["blend"], f["grid"]["w1bal"]
    print(f"grid (n = {f['grid']['n_items']}): blend best {b['in_sample_best']} LOO {T._pct(b['loo_agreement'])}; "
          f"w1bal best {w['in_sample_best']} LOO {T._pct(w['loo_agreement'])}")
    r = f["recommendations"]
    print(f"recommendations: default `{r['default_metric']}`; exposed image space {r['exposed_visual']['current']} → "
          f"{r['exposed_visual']['recommended']} ({r['exposed_visual']['reason']}); params {r['blend_params']}")
    if r["exposed_visual"]["recommended"] != r["exposed_visual"]["current"]:
        print(f"RECOMMENDED CHANGE (not applied): verdicts.json exposed_visual.metric → {r['exposed_visual']['recommended']}")
    print(f"wrote {a.report} and {a.fit_out}")


if __name__ == "__main__":
    main()
