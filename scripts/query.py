#!/usr/bin/env python
"""Twins, opposites, time-shift table and decomposed reasons for one query (CONTRACT §6 / AMENDMENTS §D).

    make query Q="JPN 2026"
    make query Q="CHN 1990 --mode today --trend motion --L 10 --minpop 1000"
    uv run scripts/query.py KOR 2050 --metric w1 --sex 1 --k 8 --div 0
    uv run scripts/query.py JPN 2026 --metric visual:dinov2-base --emb evals/embeddings/dinov2-base.pca64.npy

Loads the corpus via `pyramid_explorer.shapes.load_corpus()` when A1 provides it, else straight from
``data/processed/``; σ from ``sigma.json`` (fitted and written on first use when absent).  A ``visual:<model>``
metric needs ``--emb`` (an ``[n_rows, D]`` embedding matrix aligned with the corpus).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer.features import features, zscores  # noqa: E402
from pyramid_explorer.metrics import SIGMA_PATH, SNAPSHOT_METRICS, bin_label, decompose, fit_sigma, load_sigma  # noqa: E402
from pyramid_explorer.paths import YEARS  # noqa: E402
from pyramid_explorer.search import (DIV_PRESETS, Query, Result, best_year_per_entity, candidate_mask,  # noqa: E402
                                     different, load_inputs, row_of, similar)

EXPLAIN = ["median_age", "o65", "u15", "base_slope_20", "wa_sex_ratio", "modal_bin"]
FMT = {"median_age": "median age {:.1f}", "o65": "65+ {:.1%}", "u15": "U15 {:.1%}", "base_slope_20": "base slope {:.2f}",
       "wa_sex_ratio": "WA sex ratio {:.2f}", "modal_bin": "modal bin {:.0f}"}


def parse(argv: list[str] | None = None) -> tuple[Query, Path | None]:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("id", help="ISO3 (JPN), slug (japan) or alias (usa, south-korea) — case-insensitive")
    p.add_argument("year", type=int, help=f"{YEARS[0]}..{YEARS[-1]}")
    p.add_argument("--mode", default="same", choices=["same", "near", "range", "any", "today"])
    p.add_argument("--n", type=int, default=10, help="half-width for --mode near")
    p.add_argument("--from", dest="from_year", type=int); p.add_argument("--to", dest="to_year", type=int)
    p.add_argument("--trend", choices=["motion", "path"]); p.add_argument("--L", type=int, default=10, choices=[5, 10, 20])
    p.add_argument("--metric", default="blend", help=f"one of {SNAPSHOT_METRICS} or visual:<model>; trajectories via --trend")
    p.add_argument("--sex", default="2", choices=["2", "1"])
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--div", type=float, default=DIV_PRESETS["balanced"],
                   help="MMR diversity β for the opposites: " + " · ".join(f"{k} {v:g}" for k, v in DIV_PRESETS.items()))
    p.add_argument("--minpop", type=float, default=100.0, help="thousands")
    p.add_argument("--era", default="obs", choices=["obs", "all"]); p.add_argument("--scope", default="c", choices=["c", "all"])
    p.add_argument("--current-year", type=int, default=2026)
    p.add_argument("--emb", type=Path, help="embedding .npy aligned with the corpus (required for --metric visual:<model>)")
    a = p.parse_args(argv)
    if not YEARS[0] <= a.year <= YEARS[-1]:
        p.error(f"year {a.year} outside the corpus ({YEARS[0]}..{YEARS[-1]})")
    if a.metric in ("trend", "path"):
        p.error(f"--metric {a.metric} is a trajectory mode: use --trend motion|path (optionally --L 5|10|20)")
    if a.metric not in SNAPSHOT_METRICS and not a.metric.startswith("visual:"):
        p.error(f"unknown metric {a.metric!r}; choose from {SNAPSHOT_METRICS} or visual:<model>")
    if a.metric.startswith("visual:") and a.emb is None:
        p.error(f"--metric {a.metric} needs --emb <model>.pca64.npy (see `make embed`)")
    q = Query(a.id, a.year, mode=a.mode, n=a.n, from_year=a.from_year, to_year=a.to_year, era=a.era,
              scope=a.scope, minpop=a.minpop, metric=a.metric, sex=a.sex, k=a.k, div=a.div,
              current_year=a.current_year, trend=a.trend, L=a.L)
    return q, a.emb


def resolve_id(token: str, ents: list[dict]) -> str:
    """ISO3 / ``agg-<locid>`` / slug / alias (case-insensitive) → entity id; exits with a hint when unknown."""
    lut = {e["id"].lower(): e["id"] for e in ents}
    for e in ents:
        for a in [e.get("slug"), *e.get("aliases", [])]:
            if a:
                lut.setdefault(str(a).lower(), e["id"])
    hit = lut.get(token.strip().lower())
    if hit is None:
        sys.exit(f"unknown entity {token!r}; try an ISO3 code (JPN), a slug (japan) or an alias (usa, south-korea)")
    return hit


def snapshot_reason(q_vec, x_vec, zq, zx, metric, sex, sigma) -> str:
    """Decomposition of the ranking metric (blend's when the metric has no L2/W1 split) + feature z-deltas."""
    own = metric in ("blend", "l2", "w1", "w1sex")
    dec = decompose(metric if own else "blend", q_vec, x_vec, sex=sex, sigma=sigma)
    dz = {f: abs(zq[f] - zx[f]) for f in EXPLAIN}
    close = sorted(dz, key=dz.get)[:2]
    far = sorted(dz, key=dz.get)[-1]
    parts = [f"{'' if own else 'blend '}d={dec['d']:.2f} (L2 {dec['l2_part']:.2f} + W1 {dec['w1_part']:.2f}; {dec['w1_years']:.1f} y of age movement)",
             "L2 bins " + ", ".join(f"{bin_label(k, sex)} {c:.0%}" for k, c in dec["top_bins_l2"]),
             "W1 bins " + ", ".join(f"{bin_label(k, sex)} {c:.1f}y" for k, c in dec["top_bins_w1"]),
             "alike: " + ", ".join(FMT[f].format(zx["raw"][f]) for f in close),
             "differs: " + FMT[far].format(zx["raw"][far]) + f" vs {FMT[far].format(zq['raw'][far])}"]
    return " | ".join(parts)


def trend_reason(X, keys, q: Query, r: Result) -> str:
    """Compare the query's and candidate's L-year feature movements ("base fell 3.1 pts vs 2.9 pts")."""
    def delta(id, year):
        a, b = features(X[row_of(keys, id, year - q.L)]).iloc[0], features(X[row_of(keys, id, year)]).iloc[0]
        return {f: b[f] - a[f] for f in ("u15", "o65", "median_age", "wa_sex_ratio")}
    dq, dc = delta(q.id, q.year), delta(r.id, r.year)
    return (f"U15 {dq['u15']*100:+.1f} vs {dc['u15']*100:+.1f} pts · 65+ {dq['o65']*100:+.1f} vs {dc['o65']*100:+.1f} pts"
            f" · median age {dq['median_age']:+.1f} vs {dc['median_age']:+.1f} y · WA sex ratio {dq['wa_sex_ratio']:+.2f} vs {dc['wa_sex_ratio']:+.2f}")


def main(argv: list[str] | None = None) -> None:
    q, emb_path = parse(argv)
    X, keys, ents = load_inputs()
    emb = None
    if emb_path is not None:
        emb = np.load(emb_path).astype(np.float32)
        if emb.shape[0] != len(X):
            sys.exit(f"--emb has {emb.shape[0]} rows, corpus has {len(X)}: embeddings must be aligned with the corpus")
    if SIGMA_PATH.exists():
        sigma = load_sigma()
    else:
        print(f"[fitting sigma → {SIGMA_PATH}]"); sigma = fit_sigma(X, keys, ents, write=True)
    name = {e["id"]: e.get("short_name", e["id"]) for e in ents}
    q.id = resolve_id(q.id, ents)
    qrow = row_of(keys, q.id, q.year)
    mask = candidate_mask(keys, ents, q)
    feat = features(X)
    ref = candidate_mask(keys, ents, Query(id="", year=q.year, scope=q.scope, minpop=q.minpop, current_year=q.current_year, mode="same"))
    z = zscores(feat, np.flatnonzero(ref))
    zrow = lambda r: {**z.iloc[r].to_dict(), "raw": feat.iloc[r]}
    zq = zrow(qrow)
    # the header states the EFFECTIVE constraints: the era cap clips near/range/any windows, and a projected
    # query year flips era obs → all (PLAN §6 J8), so the requested values alone would contradict the rows below
    yrs = keys["year"].to_numpy()[mask]
    eff_years = f"{yrs.min()}–{yrs.max()}" if len(yrs) and yrs.min() != yrs.max() else (f"{yrs.min()}" if len(yrs) else "none")
    requested = {"same": "same year", "today": f"today ({q.current_year})", "near": f"{q.year}±{q.n}",
                 "range": f"range {q.from_year or YEARS[0]}–{q.to_year or YEARS[-1]}", "any": "any year"}[q.mode]
    span = f"{requested} → years {eff_years}"
    era = "all (query is a projection)" if q.era == "obs" and q.year > q.current_year else q.era
    metric = q.metric if q.trend is None else f"trend/{q.trend}@{q.L}"
    print(f"{name[q.id]} {q.year} · {span} · era {era} · {'countries' if q.scope == 'c' else 'all entities'} ≥ {q.minpop:g}k"
          f" · metric {metric} · sex {q.sex} · {int(mask.sum())} candidate rows · stage {feat.stage[qrow]}, median age {feat.median_age[qrow]:.1f}")

    def show(title: str, rs: list[Result]) -> None:
        print(f"\n{title}")
        for r in rs:
            tag = f"{name[r.id]} {r.year} ({r.dy:+d} y)" if r.dy else f"{name[r.id]} {r.year}"
            reason = trend_reason(X, keys, q, r) if q.trend else snapshot_reason(X[qrow], X[r.row], zq, zrow(r.row), q.metric, q.sex, sigma)
            print(f"  #{r.rank_raw:<3} {tag:<28} d={r.d:.3f}  {reason}")

    show(f"TWINS (k={q.k})", similar(X, keys, ents, q, sigma, emb=emb))
    show(f"OPPOSITES (k={q.k}, div={q.div:g}; # = raw farthest rank)", different(X, keys, ents, q, sigma, emb=emb))
    ts = best_year_per_entity(X, keys, ents, q, sigma, emb=emb)
    print(f"\nTIME-SHIFT ({name[q.id]} {q.year} across time, era {era}; first 10 of {len(ts)})")
    for r in ts.head(10).itertuples(index=False):
        # a same-year best is a plain match, not a censored one: flag only rows whose y* sits on the era edge
        edge = f"  [not reached by {r.best_year}: true best may lie beyond the era]" if r.boundary_hit and r.best_year != q.year else ""
        print(f"  {name[r.id]:<24} best {r.best_year} ({r.dy:+d} y)  d={r.d:.3f}{edge}")


if __name__ == "__main__":
    main()
