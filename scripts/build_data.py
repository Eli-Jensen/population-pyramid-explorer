#!/usr/bin/env python
"""Build the DuckDB store, the corpus files, σ, bands and the web shards (CONTRACT AMENDMENTS §A).

Order: connect(rebuild) → ingest_sources → ingest_locations → load_raw_population(patched=False) →
apply_togo_patch → build_entities(PATCHED frame, so pop_2026/is_micro/axis_pct match the shipped pyramids) →
insert_entities → ingest_sovereignty → ingest_pop_age5 → ingest_wpp_indicators → ingest_indicators (maddison /
pwt / wdi / weo, each skipped with a WARNING when its raw file is absent) → refresh_derived → load_corpus →
shares_to_u16 → write_u16 → write_build_meta(data_hash) → fit_sigma → write_sigma → --emb ingest →
export_processed → build_bands → write_web_data → build report (+ coverage summary, --diff-against).

Every sibling module is imported lazily; a missing one fails with a message naming its owner.
Run: ``make build`` (= ``uv run scripts/build_data.py``); flags: --no-patches --no-gdp --weo-vintage V
--no-full-emb --emb NPY (repeatable) --diff-against DB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from pyramid_explorer import bands as bands_mod
from pyramid_explorer import export, quantise
from pyramid_explorer.paths import (
    DATA_PROCESSED,
    LAST_OBSERVED_YEAR,
    REPO_ROOT,
    REVISION,
)

log = logging.getLogger("build_data")

OWNERS = {
    "pyramid_explorer.db": "A1", "pyramid_explorer.data.wpp": "A1", "pyramid_explorer.entities": "A1",
    "pyramid_explorer.patches": "A1", "pyramid_explorer.metrics": "B",
    "pyramid_explorer.data.maddison": "F", "pyramid_explorer.data.pwt": "F", "pyramid_explorer.data.wdi": "F",
    "pyramid_explorer.data.imf": "F",
}
ECON_SOURCES = [  # (remap family in pipeline/econ_iso3.yaml, module, loader, source id in pipeline/sources.yaml)
    ("maddison", "pyramid_explorer.data.maddison", "load_long", "maddison-2023"),
    ("pwt", "pyramid_explorer.data.pwt", "load_long", "pwt-11.0"),
    ("wdi", "pyramid_explorer.data.wdi", "load_long", "wdi"),
    ("oghist", "pyramid_explorer.data.wdi", "load_income_long", "oghist"),  # WB income classes (fetched by wdi.fetch)
    ("weo", "pyramid_explorer.data.imf", "load_long", "weo-{vintage}"),
]
DEFAULT_WEO_VINTAGE = "2025-04"
CURRENT_YEAR = 2026
SCHEMA_VERSION = "1"


def need(module: str, *attrs: str):
    """Import a sibling module (and check the contract names on it) or exit naming the owner."""
    owner = OWNERS.get(module, "?")
    try:
        mod = importlib.import_module(module)
    except ImportError as e:
        sys.exit(f"build_data: cannot import {module} (owner {owner}): {e}")
    for a in attrs:
        if not hasattr(mod, a):
            sys.exit(f"build_data: {module}.{a} missing (owner {owner}; see docs/CONTRACT.md)")
    return mod


class Step:
    """Context manager that logs a step's name and wall time."""

    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        self.t = time.perf_counter()
        log.info("→ %s", self.name)
        return self

    def __exit__(self, *exc):
        log.info("  %s %.1fs", self.name, time.perf_counter() - self.t)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--no-patches", action="store_true", help="build vanilla WPP (skip the Togo interim update)")
    p.add_argument("--no-gdp", action="store_true", help="skip every econ indicator source")
    p.add_argument("--weo-vintage", default=DEFAULT_WEO_VINTAGE, metavar="V", help="IMF WEO vintage, e.g. 2025-04")
    p.add_argument("--no-full-emb", action="store_true", help="ingest only the PCA-64 embeddings into the DB")
    p.add_argument("--emb", action="append", default=[], metavar="NPY", type=Path,
                   help="evals/embeddings/<model>.pca64.npy (repeatable); exports emb/<model>.f16 + visual bands")
    p.add_argument("--diff-against", metavar="DB", type=Path, help="previous explorer.duckdb to diff entities/coverage against")
    p.add_argument("--bands-pairs", type=int, default=2000, help=argparse.SUPPRESS)
    return p.parse_args(argv)


def econ_ingest(con, db, args) -> dict[str, dict]:
    """Ingest each econ source through db.ingest_indicators; a missing raw file is a WARNING, not an error."""
    out: dict[str, dict] = {}
    for family, module, loader, source_id in ECON_SOURCES:
        source_id = source_id.format(vintage=args.weo_vintage)
        try:
            mod = importlib.import_module(module)
        except ImportError as e:
            log.warning("econ %s: module %s missing (owner F): %s — skipped", family, module, e)
            continue
        if not hasattr(mod, loader):
            log.warning("econ %s: %s.%s missing (owner F) — skipped", family, module, loader)
            continue
        try:
            if family == "weo" and args.weo_vintage != DEFAULT_WEO_VINTAGE:
                long_df = weo_vintage_long(mod, args.weo_vintage)
            else:
                long_df = getattr(mod, loader)()
        except FileNotFoundError as e:
            log.warning("econ %s: raw file absent (%s) — skipped; run `make data`", family, e)
            continue
        with Step(f"ingest_indicators {family} ({source_id})"):
            out[family] = db.ingest_indicators(con, family, source_id, long_df)
            log.info("  %s: %s", family, out[family])
    return out


def weo_vintage_long(imf, vintage: str):
    """A non-default WEO vintage: fetched once via DBnomics into ``data/raw/econ/weo_<vintage>.parquet``
    (network), then loaded through the same ``load_long`` reshaping as the default file."""
    import pandas as pd

    path = imf.FILE.with_name(f"weo_{vintage.replace('-', '')}.parquet")
    if not path.exists():
        log.warning("WEO %s not on disk — fetching via DBnomics (network)", vintage)
        path.parent.mkdir(parents=True, exist_ok=True)
        imf.fetch_vintage(vintage).to_parquet(path, index=False)
    return imf.to_long(pd.read_parquet(path), last_actual_year=int(vintage[:4]) - 1)  # April vintages: previous year


def load_embeddings(paths: list[Path]) -> dict[str, dict]:
    """``{model: {"pca": Path, "full": Path|None, "meta": Path|None, "Z": ndarray[n,64]}}`` from --emb paths."""
    out = {}
    for pca in paths:
        if not pca.exists():
            sys.exit(f"build_data: --emb {pca} does not exist (run `make embed`)")
        model = pca.name.removesuffix(".npy").removesuffix(".pca64")
        full = pca.with_name(f"{model}.npy")
        meta = pca.with_name(f"{model}.meta.json")
        if not meta.exists():
            sys.exit(f"build_data: {meta} missing (owner C; the DB ingest needs its data_hash — run `make embed`)")
        Z = np.load(pca)
        if Z.ndim != 2 or Z.shape[1] != export.EMB_DIM:
            sys.exit(f"build_data: --emb {pca} must be [n_rows, {export.EMB_DIM}], got {Z.shape}")
        out[model] = {"pca": pca, "full": full if full.exists() else None, "meta": meta, "Z": Z}
    return out


def load_verdicts(emb: dict, data_hash: str, bands: list[str] | None = None,
                  path: Path = REPO_ROOT / "evals" / "verdicts.json") -> dict | None:
    """``evals/verdicts.json`` → the compact ``meta.verdicts`` block (PLAN §3.6, one writer): per-metric verdict
    + provisional flag, and ``exposed_visual`` (DECISION 4: which image space the UI labels "Visual").

    A verdicts file computed on another ``data_hash`` is stale — every verdict is downgraded to ``lab`` with a
    WARNING (re-run ``make eval``); a ``visual:<model>`` verdict is kept only when that model is passed via
    ``--emb`` AND its ``emb_meta_hash`` equals sha256 of the ``<model>.meta.json`` on disk. A metric with no
    σ-normalised bands in this build (``bands``; e.g. evaluation-only ``clr``) is capped at ``lab`` so the UI never
    offers a menu entry it cannot band. ``exposed_visual`` is ``None`` (with a WARNING) unless that model ships.
    """
    if not path.exists():
        log.warning("%s absent — meta.verdicts omitted (run `make eval`)", path)
        return None
    v = json.loads(path.read_text())
    stale = v.get("data_hash") != data_hash
    if stale:
        log.warning("verdicts.json data_hash %s != build %s — every verdict set to 'lab' until `make eval` is re-run",
                    str(v.get("data_hash"))[:12], data_hash[:12])
    meta_sha = {m: hashlib.sha256(e["meta"].read_bytes()).hexdigest() for m, e in emb.items()}
    out: dict = {"data_hash": v.get("data_hash"), "emb_meta_hash": v.get("emb_meta_hash", {}), "stale": stale,
                 "metrics": {}, "exposed_visual": None}

    def ships(model: str) -> bool:
        return model in emb and meta_sha.get(model) == out["emb_meta_hash"].get(model)

    for metric, r in v.items():
        if not isinstance(r, dict) or "verdict" not in r:
            continue
        verdict = r["verdict"]
        if metric.startswith("visual:") and not ships(metric[len("visual:"):]):
            log.warning("%s: emb_meta_hash mismatch or model not passed via --emb — verdict set to 'lab'", metric)
            verdict = "lab"
        if bands is not None and metric not in bands and metric not in ("trend", "path") and verdict not in ("lab", "rejected"):
            log.warning("%s: verdict %r but no bands in this build — capped to 'lab'", metric, verdict)
            verdict = "lab"
        if stale:
            verdict = "lab"
        out["metrics"][metric] = {"verdict": verdict, "provisional": bool(r.get("provisional", False)),
                                  **({"scope": r["scope"]} if r.get("scope") else {})}
    ev = v.get("exposed_visual")
    if isinstance(ev, dict) and ev.get("model"):
        if stale or not ships(ev["model"]):
            log.warning("exposed_visual %s: stale verdicts or model not shipped via --emb — set to null", ev["model"])
        else:
            out["exposed_visual"] = {"model": ev["model"], "metric": f"visual:{ev['model']}", "C1_obs": ev.get("C1_obs"),
                                     "alternates": [m for m in ev.get("alternates", []) if ships(m)]}
    return out


def bands_metrics(metrics_mod, emb: dict) -> list[str]:
    """Snapshot metrics (minus evaluation-only clr) + trend@L + one visual metric per embedding space."""
    snap = [m for m in metrics_mod.METRICS if m not in ("clr", "trend", "path")]
    return snap + [f"trend@{L}" for L in bands_mod.TREND_WINDOWS] + [f"visual:{m}" for m in emb]


def build(args: argparse.Namespace, *, out_root: Path | None = None, report_path: Path | None = None) -> dict:
    """Run the whole chain; returns the build report dict."""
    db = need("pyramid_explorer.db", "connect", "ingest_sources", "ingest_locations", "insert_entities",
              "ingest_sovereignty", "ingest_pop_age5", "ingest_wpp_indicators", "ingest_indicators", "refresh_derived",
              "load_corpus", "write_u16", "write_build_meta", "write_sigma", "export_processed")
    wpp = need("pyramid_explorer.data.wpp", "load_locations", "load_raw_population", "load_indicators", "togo_update_csv")
    ent_mod = need("pyramid_explorer.entities", "build_entities")
    patches_mod = need("pyramid_explorer.patches", "apply_togo_patch")
    metrics_mod = need("pyramid_explorer.metrics", "fit_sigma", "METRICS")
    emb = load_embeddings(args.emb)
    report: dict = {"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}}
    report["args"]["emb"] = [str(p) for p in args.emb]

    with Step("connect(rebuild)"):
        con = db.connect(rebuild=True)
    with Step("ingest_sources"):
        db.ingest_sources(con)
    with Step("ingest_locations"):
        locations = wpp.load_locations()
        db.ingest_locations(con, locations)
    with Step("load_raw_population(patched=False)"):
        raw = wpp.load_raw_population(patched=False)
    patch_list: list[dict] = []
    patched = raw
    if not args.no_patches:
        with Step("apply_togo_patch"):
            try:
                update_csv = Path(wpp.togo_update_csv())
            except FileNotFoundError:
                update_csv = None
            if update_csv is None or not update_csv.exists():
                log.warning("Togo update CSV not found — building vanilla (use `make data`)")
            else:
                patched, patch = patches_mod.apply_togo_patch(raw, update_csv, locations)
                patch_list = [patch]
    with Step("build_entities(patched) + insert_entities"):
        entities = ent_mod.build_entities(patched, locations)   # pop_2026 / is_micro / axis_pct from the shipped frame
        if patch_list and hasattr(patches_mod, "restrict_to_entities"):
            patch_list = [patches_mod.restrict_to_entities(patch_list[0], entities)]
        db.insert_entities(con, entities)
    with Step("ingest_sovereignty"):
        db.ingest_sovereignty(con)
    patch = patch_list[0] if patch_list else None
    with Step("ingest_pop_age5"):
        db.ingest_pop_age5(con, raw, patched, patch)
    with Step("ingest_wpp_indicators"):
        update = wpp.load_indicators_update() if patch and hasattr(wpp, "load_indicators_update") else None
        db.ingest_wpp_indicators(con, wpp.load_indicators(), update, patch)
    report["econ"] = {} if args.no_gdp else econ_ingest(con, db, args)
    with Step("refresh_derived"):
        db.refresh_derived(con)
    with Step("load_corpus"):
        s42, keys = db.load_corpus(con)
    with Step("shares_to_u16 + write_u16"):
        u16 = quantise.shares_to_u16(s42)
        db.write_u16(con, u16)
        data_hash = hashlib.sha256(np.ascontiguousarray(u16, dtype="<u2").tobytes()).hexdigest()
        db.write_build_meta(con, schema_version=SCHEMA_VERSION, revision=REVISION, data_hash=data_hash,
                            patches=json.dumps([p.get("id") for p in patch_list]), last_observed_year=LAST_OBSERVED_YEAR,
                            built=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                            git_rev=db.git_rev() if hasattr(db, "git_rev") else None)
    with Step("fit_sigma + write_sigma"):
        sigma = metrics_mod.fit_sigma(s42, keys, entities)
        db.write_sigma(con, sigma)
        if hasattr(metrics_mod, "blend_balance"):   # documented asymmetry: W1 share of blend by era (RESULTS.md)
            report["blend_w1_share"] = metrics_mod.blend_balance(s42, keys, entities, sigma, current_year=CURRENT_YEAR,
                                                                 last_observed_year=LAST_OBSERVED_YEAR)
    for model, e in emb.items():
        with Step(f"ingest_embeddings {model}"):
            if e["Z"].shape[0] != len(keys):
                sys.exit(f"build_data: --emb {model} has {e['Z'].shape[0]} rows, corpus has {len(keys)}")
            db.ingest_embeddings(con, model, None if args.no_full_emb else e["full"], e["pca"], e["meta"], keys)
    with Step("export_processed"):
        db.export_processed(con)
    band_metrics = bands_metrics(metrics_mod, emb)
    with Step("build_bands"):
        bands = bands_mod.build_bands(s42, keys, entities, sigma, band_metrics,
                                      n_pairs=args.bands_pairs, current_year=CURRENT_YEAR,
                                      last_observed_year=LAST_OBSERVED_YEAR,
                                      emb={m: e["Z"] for m, e in emb.items()} or None)
    with Step("write_web_data"):
        families = {"wpp"} | set(report["econ"])
        web = export.write_web_data(entities=entities, keys=keys, s42=s42, u16=u16, bands=bands, sigma=sigma,
                                    patches=patch_list, emb={m: e["Z"] for m, e in emb.items()} or None,
                                    out_root=out_root, report_path=report_path, families=families,
                                    verdicts=load_verdicts(emb, data_hash, band_metrics))
    blend_share = report.pop("blend_w1_share", None)
    report.update(web)
    if blend_share is not None:
        report["blend_w1_share"] = blend_share
    report["data_hash"] = data_hash
    if hasattr(db, "coverage"):
        try:
            cov = db.coverage(con)
            report["coverage"] = cov.groupby(["series", "source_id"]).size().to_dict() if len(cov) else {}
            report["coverage"] = {f"{k[0]}/{k[1]}": int(v) for k, v in report["coverage"].items()}
        except Exception as e:  # noqa: BLE001 — coverage is a summary, never a build blocker
            log.warning("coverage summary failed: %s", e)
    if args.diff_against and not args.diff_against.exists():
        log.warning("--diff-against %s does not exist — skipped", args.diff_against)
    elif args.diff_against:
        with Step(f"diff_against {args.diff_against}"):
            report["diff"] = db.diff_against(con, args.diff_against)
    con.close()
    rp = Path(report_path) if report_path else REPO_ROOT / "data" / "out" / "build-report.json"
    rp.write_text(json.dumps(report, indent=1, default=str))
    return report


def w1_share(report: dict) -> str:
    """'   blend W1 share (two-sex) obs/nowcast/proj 0.469 / 0.502 / 0.534' or '' when not measured."""
    share = report.get("blend_w1_share", {}).get("2")
    if not share:
        return ""
    return "   blend W1 share (two-sex) obs/nowcast/proj " + " / ".join(f"{share.get(k, float('nan')):.3f}" for k in ("obs", "nowcast", "proj"))


def summary(report: dict) -> str:
    s, lay = report["sizes"], report["sizes"]["layouts"]
    sig = report["sigma"]
    def kb(n: float) -> str:
        return f"{n / 1000:.1f} KB"

    def mb(n: float) -> str:
        return f"{n / 1e6:.2f} MB"

    def sg(metric: str) -> float:
        return sig.get(metric, {}).get("2", float("nan"))

    emb = ", ".join(f"{m} {mb(n)}" for m, n in s["emb"].items()) or "none"
    lines = [
        (f"build {report['revision']} — {report['n_entities']} entities ({report['n_countries']} countries), "
         f"{report['n_rows']} rows, data_hash {report.get('data_hash', '?')[:12]}"),
        f"patches: {[p.get('id') for p in report['patches']] or 'none'}   econ: {list(report.get('econ', {})) or 'none'}",
        f"σ  l2 {sg('l2'):.4f}  w1sex {sg('w1sex'):.2f}  trend@10 {sg('trend@10'):.4f}" + w1_share(report),
        (f"first paint {kb(s['first_paint'])} (entities gz {kb(s['entities_gz'])} + meta gz {kb(s['meta_gz'])} + entity shard "
         f"{kb(s['entity_shard_max'])} + year shard {kb(s['year_shard_max'])} + bands_default {kb(s['bands_default'])})"),
        f"blob d16z {mb(s['shares_d16z'])}  u16 {mb(s['shares_u16'])}  totals {kb(s['totals'])}  bands {kb(s['bands'])}  emb {emb}",
        (f"layouts: raw gz {mb(lay['raw_gz'])} · delta gz {mb(lay['delta_gz'])} · zigzag gz {mb(lay['zigzag_gz'])} · "
         f"delta-transposed gz {mb(lay['delta_transposed_gz'])}"),
        f"dir total {mb(s['dir_total'])} (with emb {mb(s['dir_total_with_emb'])})   axis {report['axis_distribution']}",
        f"budgets: {'OK' if not report['checks']['budgets'] else report['checks']['budgets']}",
    ]
    if report.get("verdicts"):
        ev = report["verdicts"].get("exposed_visual")
        lines.append(f"verdicts: {'STALE (all lab)' if report['verdicts'].get('stale') else 'fresh'} · exposed as Visual: "
                     f"{ev['model'] if ev else 'none'}")
    if "coverage" in report:
        lines.append(f"coverage rows per series/source: {report['coverage']}")
    if "diff" in report:
        lines.append(f"diff vs previous DB: {report['diff']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None, **kw) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    report = build(args, **kw)
    print(summary(report))
    return report


if __name__ == "__main__":
    main()
