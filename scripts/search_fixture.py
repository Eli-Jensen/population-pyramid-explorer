#!/usr/bin/env python
"""Write ``evals/fixtures/search_cases.json`` — the Python-side truth ``web/src/lib/{search,bands,explain}.ts``
are tested against (twins, opposites, strict farthest, time-shift, isolation, decomposition, feature z-deltas).

    uv run python scripts/search_fixture.py            # writes evals/fixtures/search_cases.json

Inputs are the exported corpus (``data/processed/corpus_u16.npy`` + ``corpus_keys.parquet`` + ``entities.json``),
``data/processed/sigma.json`` (identical to ``meta.sigma``), the SHIPPED percentile tables
(``web/public/data/wpp2024/bands.*.bin``, read with :func:`pyramid_explorer.bands.deserialize_bands`) and, for the
``visual`` case, ``evals/embeddings/<model>.pca64.npy`` (asserted byte-identical to the shipped ``emb/*.f16``).

Dequantisation is ``float64(u16) / 65535`` — the exact numbers the browser sees when it divides a Uint16 by 65535
in float64 — and every distance is computed in float64: ``pyramid_explorer.metrics.distances`` ends with
``.astype(np.float32)`` for its own consumers, so this script swaps the module's ``np.float32`` for ``np.float64``
(a shim over numpy; nothing else changes). The web engine therefore has to match the fixture to ~1e-9, not 1e-6,
and rank ties are decided on the same float64 values on both sides.

Percentile-of-d is linear interpolation on the 24-point GRID (``percentile_of`` below, mirrored by
``bands.ts``); the table is chosen by |Δy| and the EFFECTIVE era (``same[metric][sex][year]`` when Δy = 0,
``cross[metric][sex][era][decade]`` otherwise, ``best[...]`` for time-shift rows — PLAN §3.4a). Table metric names:
``trend@L`` for trend/motion, ``visual:<model>`` for visual, and ``blend`` as the documented proxy for ``path``
(the path distance is a mean of blend distances; no ``path`` tables are built).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer import metrics as M  # noqa: E402
from pyramid_explorer.bands import GRID, band_label, deserialize_bands  # noqa: E402
from pyramid_explorer.features import NUMERIC_FEATURES, features, zscores  # noqa: E402
from pyramid_explorer.metrics import decompose, load_sigma  # noqa: E402
from pyramid_explorer.paths import DATA_PROCESSED, EVALS, LAST_OBSERVED_YEAR, N_DIMS, N_YEARS, WEB, WEB_SRC_DATA, YEARS  # noqa: E402
from pyramid_explorer.search import (DIV_PRESETS, Query, Result, best_year_per_entity, candidate_mask, different,  # noqa: E402
                                     isolation, row_of, similar)

OUT = EVALS / "fixtures" / "search_cases.json"
U16_TOTAL = 65535
EXPLAIN = ["median_age", "o65", "u15", "base_slope_20", "wa_sex_ratio", "modal_bin"]
CURRENT_YEAR = 2026


class _NumpyF64:
    """numpy, except ``float32`` is ``float64`` — makes ``metrics.distances`` return float64 (see module doc)."""

    float32 = np.float64

    def __getattr__(self, name):
        return getattr(np, name)


def _clean(v):
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    return v


def r9(x: float | None) -> float | None:
    return None if x is None else round(float(x), 9)


# ---------------------------------------------------------------------------------------------- bands
def percentile_of(d: float, q: np.ndarray) -> float:
    """Linear interpolation of the percentile of ``d`` on the GRID quantiles ``q`` (ascending, 24 values)."""
    q = np.asarray(q, dtype=np.float64)
    if d <= q[0]:
        return 0.0
    if d >= q[-1]:
        return 100.0
    i = int(np.searchsorted(q, d, side="right")) - 1          # q[i] ≤ d < q[i+1]  ⇒  q[i+1] > q[i]
    lo, hi = q[i], q[i + 1]
    return float(GRID[i] + (d - lo) / (hi - lo) * (GRID[i + 1] - GRID[i]))


def effective_era(q: Query) -> str:
    return "all" if q.era == "obs" and q.year > q.current_year else q.era


def table_metric(q: Query) -> str:
    if q.trend == "motion":
        return f"trend@{q.L}"
    if q.trend == "path":
        return "blend"                                          # documented proxy (module doc)
    return q.metric


def table_name(q: Query, kind: str, cand_year: int) -> str:
    m, era, dec = table_metric(q), effective_era(q), (q.year // 10) * 10
    if kind == "best":
        return f"best/{m}/{q.sex}/{era}/{dec}"
    if cand_year == q.year:
        return f"same/{m}/{q.sex}/{q.year}"
    return f"cross/{m}/{q.sex}/{era}/{dec}"


def band_of(bands: dict[str, np.ndarray], q: Query, kind: str, cand_year: int, d: float) -> dict:
    name = table_name(q, kind, cand_year)
    t = bands.get(name)
    if t is None:
        return {"band": "typical", "percentile": None, "table": None}
    return {"band": band_label(d, [float(v) for v in t]), "percentile": r9(percentile_of(d, t)), "table": name}


# ---------------------------------------------------------------------------------------------- inputs
def load() -> tuple[np.ndarray, pd.DataFrame, list[dict], dict, dict[str, np.ndarray], dict]:
    u16 = np.load(DATA_PROCESSED / "corpus_u16.npy")
    keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
    ents = json.loads((DATA_PROCESSED / "entities.json").read_text())
    if u16.shape != (len(keys), N_DIMS) or u16.dtype != np.uint16:
        raise SystemExit(f"corpus_u16.npy {u16.shape} {u16.dtype} does not match keys ({len(keys)} rows)")
    X = u16.astype(np.float64) / U16_TOTAL
    sigma = load_sigma()
    meta = json.loads((WEB_SRC_DATA / "meta.json").read_text())
    if json.dumps(sigma, sort_keys=True) != json.dumps(meta["sigma"], sort_keys=True):
        raise SystemExit("data/processed/sigma.json differs from web/src/data/meta.json sigma — rebuild first")
    bands = deserialize_bands((WEB / "public" / meta["files"]["bands"]).read_bytes())
    data_hash = hashlib.sha256(np.ascontiguousarray(u16, dtype="<u2").tobytes()).hexdigest()
    if meta.get("verdicts") and meta["verdicts"]["data_hash"] != data_hash:
        raise SystemExit("corpus_u16.npy is not the corpus meta.json was built from")
    return X, keys, ents, sigma, bands, meta


def load_emb(meta: dict, model: str) -> np.ndarray:
    e = np.load(EVALS / "embeddings" / f"{model}.pca64.npy")
    if e.dtype != np.float16 or e.shape != (meta["n_rows"], 64):
        raise SystemExit(f"{model}.pca64.npy has shape {e.shape} {e.dtype}")
    shipped = (WEB / "public" / meta["files"]["emb"][model]).read_bytes()
    if shipped != np.ascontiguousarray(e, dtype="<f2").tobytes():
        raise SystemExit(f"shipped emb/{model}.f16 differs from evals/embeddings/{model}.pca64.npy")
    return e.astype(np.float32)


# ---------------------------------------------------------------------------------------------- cases
def qdict(q: Query) -> dict:
    d = asdict(q)
    return {"id": d["id"], "year": d["year"], "mode": d["mode"], "n": d["n"], "from": d["from_year"], "to": d["to_year"],
            "era": d["era"], "scope": d["scope"], "minpop": d["minpop"], "metric": d["metric"], "sex": d["sex"],
            "k": d["k"], "div": d["div"], "trend": d["trend"], "L": d["L"], "currentYear": d["current_year"]}


def results(rs: list[Result], q: Query, bands, kind: str = "auto") -> list[dict]:
    out = []
    for r in rs:
        b = band_of(bands, q, kind, r.year, r.d)
        out.append({"id": r.id, "year": r.year, "row": r.row, "d": r9(r.d), "rankRaw": r.rank_raw, "dy": r.dy, **b})
    return out


def case(name: str, X, keys, ents, q: Query, sigma, bands, *, emb=None, time_shift: int = 0) -> dict:
    mask = candidate_mask(keys, ents, q)
    twins = similar(X, keys, ents, q, sigma, emb=emb)
    opp = different(X, keys, ents, q, sigma, emb=emb)
    strict = different(X, keys, ents, replace(q, div=0.0), sigma, emb=emb)
    out = {"name": name, "query": qdict(q), "effectiveEra": effective_era(q), "tableMetric": table_metric(q),
           "nCandidates": int(mask.sum()), "queryRow": row_of(keys, q.id, q.year),
           "similar": results(twins, q, bands), "different": results(opp, q, bands), "strict": results(strict, q, bands)}
    if time_shift:
        ts = best_year_per_entity(X, keys, ents, q, sigma, emb=emb)
        rows = []
        for r in ts.head(time_shift).itertuples(index=False):
            b = band_of(bands, q, "best", int(r.best_year), float(r.d))
            rows.append({"id": r.id, "bestYear": int(r.best_year), "d": r9(r.d), "dy": int(r.dy),
                         "boundaryHit": bool(r.boundary_hit), **b})
        out["timeShift"] = {"n": int(len(ts)), "rows": rows}
    return out


def explain_case(name: str, X, keys, ents, q: Query, cand: tuple[str, int], sigma) -> dict:
    qrow, crow = row_of(keys, q.id, q.year), row_of(keys, *cand)
    own = q.metric in ("blend", "l2", "w1", "w1sex")
    dec = decompose(q.metric if own else "blend", X[qrow], X[crow], sex=q.sex, sigma=sigma)
    feat = features(X)
    ref = candidate_mask(keys, ents, Query(id="", year=q.year, scope=q.scope, minpop=q.minpop, current_year=q.current_year, mode="same"))
    z = zscores(feat, np.flatnonzero(ref))
    zq, zc = z.iloc[qrow], z.iloc[crow]
    dz = {f: abs(float(zq[f] - zc[f])) for f in EXPLAIN}
    order = sorted(EXPLAIN, key=lambda f: (dz[f], EXPLAIN.index(f)))
    return {
        "name": name, "query": qdict(q), "cand": {"id": cand[0], "year": cand[1]}, "queryRow": qrow, "candRow": crow,
        "decomposeMetric": q.metric if own else "blend",
        "decompose": {"d": r9(dec["d"]), "l2Part": r9(dec["l2_part"]), "w1Part": r9(dec["w1_part"]), "w1Years": r9(dec["w1_years"]),
                      "topBinsL2": [[k, r9(c)] for k, c in dec["top_bins_l2"]], "topBinsW1": [[k, r9(c)] for k, c in dec["top_bins_w1"]]},
        "referenceYear": q.year, "nReference": int(ref.sum()),
        "features": [{"name": f, "zq": r9(zq[f]), "zc": r9(zc[f]), "rawQ": r9(feat.iloc[qrow][f]), "rawC": r9(feat.iloc[crow][f])}
                     for f in EXPLAIN],
        "alike": order[:2], "differs": order[-1],
    }


def isolation_case(X, keys, ents, sigma, year: int, ids: list[str]) -> dict:
    iso = isolation(X, keys, ents, year, "blend", sigma, sex="2", k=5, minpop=100.0)
    v = dict(zip(iso["id"], iso["isolation"]))
    n = len(v)
    rows = []
    for id_ in ids:
        own = v[id_]
        pct = 100.0 * sum(1 for k, x in v.items() if k != id_ and x < own) / (n - 1)
        rows.append({"id": id_, "isolation": r9(own), "percentile": r9(pct), "rank": int(iso.index[iso["id"] == id_][0]) + 1})
    return {"year": year, "metric": "blend", "sex": "2", "k": 5, "minpop": 100.0, "n": n,
            "top3": iso["id"].head(3).tolist(), "rows": rows}


def build(model: str) -> dict:
    M.np = _NumpyF64()                                           # float64 distances (module doc)
    X, keys, ents, sigma, bands, meta = load()
    emb = load_emb(meta, model)
    J = dict(id="JPN", year=2026)
    cases = [
        case("JPN 2026 same blend sex2 k5 div0.5", X, keys, ents, Query(**J), sigma, bands, time_shift=15),
        case("JPN 2026 same blend sex1", X, keys, ents, Query(**J, sex="1"), sigma, bands),
        case("JPN 2026 same l2", X, keys, ents, Query(**J, metric="l2"), sigma, bands),
        case("JPN 2026 same w1", X, keys, ents, Query(**J, metric="w1"), sigma, bands),
        case("JPN 2026 same l2s", X, keys, ents, Query(**J, metric="l2s"), sigma, bands),
        case("JPN 2026 same hel", X, keys, ents, Query(**J, metric="hel"), sigma, bands),
        case("JPN 2026 same feat", X, keys, ents, Query(**J, metric="feat"), sigma, bands),
        case("JPN 2026 same w1sex sex1 (falls back to w1)", X, keys, ents, Query(**J, metric="w1sex", sex="1"), sigma, bands),
        case("JPN 2026 same w1bal", X, keys, ents, Query(**J, metric="w1bal"), sigma, bands),
        case("JPN 2026 any era obs", X, keys, ents, Query(**J, mode="any"), sigma, bands, time_shift=15),
        case("JPN 2050 any (era flips to all, J8)", X, keys, ents, Query(id="JPN", year=2050, mode="any"), sigma, bands, time_shift=10),
        case("JPN 2026 near ±10", X, keys, ents, Query(**J, mode="near", n=10), sigma, bands),
        case("JPN 2026 range 1990–2000 minpop 1000", X, keys, ents, Query(**J, mode="range", from_year=1990, to_year=2000, minpop=1000.0), sigma, bands),
        case("JPN 2026 same scope all minpop 0", X, keys, ents, Query(**J, scope="all", minpop=0.0, k=8), sigma, bands),
        case("CHN 1990 today trend motion L10", X, keys, ents, Query(id="CHN", year=1990, mode="today", trend="motion", L=10), sigma, bands),
        case("CHN 1990 today trend path L10", X, keys, ents, Query(id="CHN", year=1990, mode="today", trend="path", L=10), sigma, bands),
        case("JPN 2026 any trend motion L20 (mask year−20 ≥ 1950)", X, keys, ents, Query(**J, mode="any", trend="motion", L=20), sigma, bands),
        case("KOR 2026 any (time-shift top 15)", X, keys, ents, Query(id="KOR", year=2026, mode="any"), sigma, bands, time_shift=15),
        case("QAT 2026 same div 0", X, keys, ents, Query(id="QAT", year=2026, div=0.0), sigma, bands),
        case("QAT 2026 same div 0.5", X, keys, ents, Query(id="QAT", year=2026, div=0.5), sigma, bands),
        case("QAT 2026 same div 2", X, keys, ents, Query(id="QAT", year=2026, div=2.0), sigma, bands),
        case(f"USA 2026 same visual:{model}", X, keys, ents, Query(id="USA", year=2026, metric=f"visual:{model}"), sigma, bands, emb=emb),
    ]
    explains = [
        explain_case("JPN–ITA 2026 blend", X, keys, ents, Query(**J), ("ITA", 2026), sigma),
        explain_case("KOR 2026 – JPN 2008 blend (any-year result)", X, keys, ents, Query(id="KOR", year=2026, mode="any"), ("JPN", 2008), sigma),
        explain_case("JPN–NER 2026 blend", X, keys, ents, Query(**J), ("NER", 2026), sigma),
        explain_case("JPN–QAT 2026 l2 (own metric)", X, keys, ents, Query(**J, metric="l2"), ("QAT", 2026), sigma),
        explain_case("JPN–ITA 2026 hel (blend decomposition)", X, keys, ents, Query(**J, metric="hel"), ("ITA", 2026), sigma),
        explain_case("JPN–ITA 2026 sex1", X, keys, ents, Query(**J, sex="1"), ("ITA", 2026), sigma),
    ]
    return {
        "_meta": {
            "source": "scripts/search_fixture.py",
            "inputs": ["data/processed/corpus_u16.npy", "data/processed/corpus_keys.parquet", "data/processed/entities.json",
                       "data/processed/sigma.json", meta["files"]["bands"], f"evals/embeddings/{model}.pca64.npy"],
            "dequantise": "float64(u16) / 65535; distances in float64 (metrics.np.float32 shimmed to float64)",
            "percentile": "linear interpolation on the 24-point GRID; ≤ q[0] → 0, ≥ q[23] → 100",
            "band_table_rule": "Δy = 0 → same/{m}/{sex}/{year}; else cross/{m}/{sex}/{era}/{decade}; time-shift → best/…; era is the EFFECTIVE era (obs flips to all when year > currentYear); trend/motion → trend@L; path → blend (proxy)",
            "grid": GRID, "current_year": CURRENT_YEAR, "last_observed_year": LAST_OBSERVED_YEAR,
            "data_hash": (meta.get("verdicts") or {}).get("data_hash"), "n_rows": int(len(keys)), "n_years": N_YEARS,
            "div_presets": DIV_PRESETS, "visual_model": model,
        },
        "cases": cases,
        "isolation": isolation_case(X, keys, ents, sigma, 2026, ["JPN", "QAT", "NER", "USA", "ITA"]),
        "explain": explains,
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--model", default=None, help="visual model (default: meta.verdicts.exposed_visual.model)")
    a = p.parse_args(argv)
    meta = json.loads((WEB_SRC_DATA / "meta.json").read_text())
    model = a.model or ((meta.get("verdicts") or {}).get("exposed_visual") or {}).get("model") or "siglip2-base-naflex"
    fx = build(model)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(fx, separators=(",", ":"), default=_clean) + "\n")
    n = sum(len(c["similar"]) + len(c["different"]) + len(c["strict"]) + len(c.get("timeShift", {}).get("rows", [])) for c in fx["cases"])
    print(f"wrote {a.out.relative_to(Path.cwd()) if a.out.is_absolute() else a.out}: {len(fx['cases'])} cases, {n} result rows, "
          f"{len(fx['explain'])} explain pairs, {len(fx['isolation']['rows'])} isolation rows ({a.out.stat().st_size / 1024:.0f} KB)")
    for c in fx["cases"]:
        print(f"  {c['name']:<52} cand {c['nCandidates']:>6}  twins {[r['id'] for r in c['similar']]}  opp {[(r['id'], r['rankRaw']) for r in c['different']]}")


if __name__ == "__main__":
    main()
