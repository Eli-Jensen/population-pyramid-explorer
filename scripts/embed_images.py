#!/usr/bin/env python
"""Embed canonical renders with the registered vision models → ``evals/embeddings/``.

    uv run --group embed scripts/embed_images.py --model siglip2-base-naflex --model dinov2-base [--db]
    make embed

Per model: processor assertions on the first batch (`embed.processor_check`), full-corpus embedding
(``{model}.npy`` float32), PCA-64 without whitening (``{model}.pca64.npy`` float16 + ``{model}.pca.npz`` mean/proj),
G1 continuity, rank agreement with ``blend``/``l2`` (agent B's `metrics`), dynamic range, the pre-registered
factorial invariance diagnostic, and ``{model}.meta.json`` (HF id, revision, checkpoint sha, processor config,
asserted shapes, render kind/size/style hash, throughput, corpus data hash).  The results block of
``evals/image_embeddings.md`` is rewritten from the meta files.  ``--db`` hands the outputs to
`pyramid_explorer.db.ingest_embeddings` when A1's module exists.

Images are rendered on the fly (`embed.RenderedCorpus`) unless ``--renders`` points at ``data/renders/`` arrays
whose sidecar style hash matches the current renderer (otherwise the run refuses).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pyramid_explorer import embed as M                      # noqa: E402
from pyramid_explorer import render as R                     # noqa: E402
from pyramid_explorer.paths import DATA_PROCESSED, EVALS     # noqa: E402

MD = EVALS / "image_embeddings.md"
MARK = ("<!-- results:start -->", "<!-- results:end -->")


# --------------------------------------------------------------------------------------------- inputs


def corpus_data_hash(s42: np.ndarray) -> str:
    """The build's ``data_hash`` (CONTRACT amendment A): sha256 over the little-endian uint16 corpus bytes, which is
    what `db.ingest_embeddings` compares against ``build_meta.data_hash``."""
    from pyramid_explorer.quantise import shares_to_u16
    return hashlib.sha256(np.ascontiguousarray(shares_to_u16(s42), dtype="<u2").tobytes()).hexdigest()


def load_corpus(limit: int | None) -> tuple[np.ndarray, pd.DataFrame, list[dict], dict]:
    f = DATA_PROCESSED / "corpus_s42.npy"
    s42 = np.load(f)
    keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
    entities = json.loads((DATA_PROCESSED / "entities.json").read_text())
    info = {"corpus_file": str(f.relative_to(f.parents[2])), "data_hash": corpus_data_hash(s42),
            "s42_file_sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "s42_sha256": s42_sha256(s42),
            "n_rows": int(len(s42)), "n_entities": len(entities),
            "provisional": any("PROVISIONAL" in e.get("notes", []) for e in entities)}
    if limit:
        s42, keys = s42[:limit], keys.iloc[:limit].reset_index(drop=True)
    return s42, keys, entities, info


def numeric_metrics(s42: np.ndarray, keys: pd.DataFrame, entities: list[dict]) -> tuple[dict, dict]:
    """``{'blend': fn, 'l2': fn}`` from agent B's metrics (+ where σ came from), else a local blend fallback."""
    try:
        from pyramid_explorer import metrics as Mx
        sigma = Mx.load_sigma()
        src = "data/processed/sigma.json" if Mx.SIGMA_PATH.exists() else "metrics.DEFAULT_SIGMA"
        fns = {name: (lambda q, X, _n=name: Mx.distances(_n, q, X, sigma=sigma)) for name in ("blend", "l2")}
        return fns, {"source": "pyramid_explorer.metrics", "sigma_source": src,
                     "sigma": {k: sigma[k] for k in ("l2", "w1sex") if k in sigma}}
    except Exception as e:                                    # B not landed / API drift → local definition (CONTRACT §4)
        warnings.warn(f"metrics unavailable ({e!r}); using local blend fallback")
    rng = np.random.default_rng(0)
    country = {e["id"] for e in entities if e["type"] == "country"}
    ok = np.flatnonzero(keys["id"].isin(country).to_numpy() & (keys["pop_total"].to_numpy() >= 100))
    years = keys["year"].to_numpy()
    by_year = {y: ok[years[ok] == y] for y in np.unique(years[ok])}
    ya = rng.choice(list(by_year), 20000)
    a = np.array([rng.choice(by_year[y]) for y in ya])
    b = np.array([rng.choice(by_year[y]) for y in ya])

    def l2(q, X):
        return np.linalg.norm(X - q, axis=1).astype(np.float32)

    def w1s(q, X):
        cq, cX = np.cumsum(q.reshape(2, 21), 1), np.cumsum(X.reshape(-1, 2, 21), 2)
        return (5.0 * np.abs(cX - cq).sum((1, 2))).astype(np.float32)

    s_l2 = float(np.median(np.linalg.norm(s42[a] - s42[b], axis=1)))
    s_w1 = float(np.median([w1s(s42[i], s42[j:j + 1])[0] for i, j in zip(a, b)]))
    return ({"blend": lambda q, X: 0.5 * l2(q, X) / s_l2 + 0.5 * w1s(q, X) / s_w1, "l2": l2},
            {"source": "local fallback", "sigma": {"l2": s_l2, "w1sex": s_w1}})


def s42_sha256(s42: np.ndarray) -> str:
    """sha256 of the share array's bytes — the key `render.render_corpus` writes into its ``.meta.json`` sidecar."""
    return hashlib.sha256(np.ascontiguousarray(s42, dtype=np.float64).tobytes()).hexdigest()


def image_source(model: str, s42: np.ndarray, renders: Path | None, limit: int | None = None):
    spec = M.MODELS[model]
    if renders is not None:
        f = renders / R.render_path(spec["kind"], spec["size"]).name
        meta = json.loads(f.with_suffix(".meta.json").read_text())
        if meta["style_hash"] != R.style_hash():
            raise SystemExit(f"{f}: style hash {meta['style_hash'][:12]} != renderer {R.style_hash()[:12]}; re-run make render")
        arr = np.load(f, mmap_mode="r")
        if len(arr) < len(s42):
            raise SystemExit(f"{f} has {len(arr)} rows, corpus has {len(s42)}")
        if limit is None and meta.get("s42_sha256") != s42_sha256(s42):
            raise SystemExit(f"{f} was rendered from another corpus (s42 sha {meta.get('s42_sha256', '?')[:12]}); re-run make render")
        return arr[:len(s42)], {"source": str(f), "kind": spec["kind"], "size": spec["size"]}
    return M.RenderedCorpus(s42, spec["kind"], spec["size"]), {"source": "on-the-fly", "kind": spec["kind"], "size": spec["size"]}


# --------------------------------------------------------------------------------------------- per-model run


def run_model(model: str, s42, keys, entities, corpus_info, dist_fns, dist_info, a) -> dict:
    import torch
    import transformers
    from scipy.stats import spearmanr
    spec = M.MODELS[model]
    images, render_info = image_source(model, s42, a.renders, a.limit)
    render_info.update(patch=spec["patch"], style_hash=R.style_hash())
    print(f"[{model}] processor check …", flush=True)
    check = M.processor_check(model, np.asarray(images[:min(8, len(images))]))
    M.load_model(model, a.device, a.dtype)                  # load outside the timed region
    print(f"[{model}] embedding {len(images)} images …", flush=True)
    t0 = time.time()
    E = M.embed(model, images, batch=a.batch, device=a.device, dtype=a.dtype, progress=True)
    wall = time.time() - t0
    Z, mean, proj = M.pca64(E)
    a.out.mkdir(parents=True, exist_ok=True)
    files = {"full": a.out / f"{model}.npy", "pca64": a.out / f"{model}.pca64.npy", "pca": a.out / f"{model}.pca.npz",
             "meta": a.out / f"{model}.meta.json"}
    np.save(files["full"], E)
    np.save(files["pca64"], Z)
    np.savez(files["pca"], mean=mean, proj=proj)
    print(f"[{model}] {len(E)} × {E.shape[1]} in {wall:.0f}s ({len(E) / wall:.1f} img/s); evaluating …", flush=True)
    Zf = Z.astype(np.float32)
    ev = {"continuity_full": M.continuity(E, keys), "continuity_pca64": M.continuity(Zf, keys),
          "agreement_full": M.rank_agreement(E, s42, keys, dist_fns, n_queries=min(300, len(E)), seed=0),
          "agreement_pca64": M.rank_agreement(Zf, s42, keys, dist_fns, n_queries=min(300, len(E)), seed=0),
          "dynamic_range": M.dynamic_range(E), "pca_explained_variance": M.explained_variance(E)}
    rng = np.random.default_rng(0)
    p, q = rng.integers(0, len(E), 2000), rng.integers(0, len(E), 2000)
    Zu = M._unit(Zf)
    ev["spearman_full_vs_pca64"] = float(spearmanr(1 - (E[p] * E[q]).sum(1), 1 - (Zu[p] * Zu[q]).sum(1)).correlation)
    inv = None
    if not a.no_diag:
        rows = M.diagnostic_rows(keys, a.diag_n, seed=0)
        print(f"[{model}] invariance diagnostic on {len(rows)} pyramids × {len(M.variant_styles(model))} styles …", flush=True)
        inv = M.invariance_diagnostic(model, s42, rows, batch=a.batch, device=a.device, dtype=a.dtype)
        inv["_design"] = {"n": int(len(rows)), "seed": 0, "year_step": 10,
                          "styles": {k: {kk: vv for kk, vv in v.items()} for k, v in M.variant_styles(model).items()}}
    meta = {"model": model, **M.checkpoint_info(model), "licence": spec["licence"], "dim": int(E.shape[1]),
            "pooling": "get_image_features pooler (attention pool)" if model.startswith("siglip2") else "CLS pooler_output",
            "processor": check, "render": render_info, "inference": {"device": a.device, "dtype": a.dtype, "batch": a.batch,
            "torch": torch.__version__, "transformers": transformers.__version__},
            "n": int(len(E)), "throughput_img_s": len(E) / wall, "wall_s": wall, **corpus_info,
            "pca": {"k": 64, "whitened": False, "file": files["pca"].name, "explained_variance": ev["pca_explained_variance"]},
            "files": {k: v.name for k, v in files.items() if k != "meta"}, "numeric_metrics": dist_info,
            "eval": ev, "invariance": inv, "built": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
    meta.update(db_fields(meta, check, render_info, mean, proj))     # flat keys read by db.ingest_embeddings
    files["meta"].write_text(json.dumps(meta, indent=1))
    print(f"[{model}] C1 full {ev['continuity_full']['observed']['C1']:.3f} / pca64 {ev['continuity_pca64']['observed']['C1']:.3f}; "
          f"Spearman vs blend {ev['agreement_full']['spearman']['blend']:.3f}; "
          f"top-10 overlap same-year vs blend {ev['agreement_full']['overlap_same_year']['blend']:.3f}", flush=True)
    if a.db:
        ingest_db(model, files, keys)
    return meta


def db_fields(meta: dict, check: dict, render_info: dict, mean: np.ndarray, proj: np.ndarray) -> dict:
    """The flat ``embedding_model`` columns A1's `db.ingest_embeddings` reads from the meta file."""
    shapes = {k: check[k] for k in ("spatial_shapes", "mask_sum", "pixel_values_shape", "max_abs_pixel_diff_255") if k in check}
    return {"hf_id": meta["hf"], "checkpoint_sha": meta["checkpoint_sha256"], "render_kind": render_info["kind"],
            "render_size": render_info["size"], "style_hash": render_info["style_hash"],
            "processor_config": check["processor_config"], "asserted_shapes": shapes,
            "pca_mean": [float(x) for x in mean], "pca_proj_sha": hashlib.sha256(np.ascontiguousarray(proj).tobytes()).hexdigest()}


def ingest_db(model: str, files: dict[str, Path], keys: pd.DataFrame) -> None:
    try:
        from pyramid_explorer import db
    except ImportError as e:
        warnings.warn(f"--db requested but pyramid_explorer.db is not available ({e!r}); skipped")
        return
    if not db.DB_PATH.exists():
        warnings.warn(f"--db requested but {db.DB_PATH} does not exist (run make build first); skipped")
        return
    try:
        con = db.connect()
        print(f"[{model}] DB: {db.ingest_embeddings(con, model, files['full'], files['pca64'], files['meta'], keys)}", flush=True)
        con.close()
    except ValueError as e:                                   # data_hash mismatch: the DB was built from another corpus
        warnings.warn(f"--db: {e}; skipped")


# --------------------------------------------------------------------------------------------- report


def _pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def results_block(metas: list[dict]) -> str:
    L = [f"_Run {metas[0]['built']} on the {'PROVISIONAL ' if metas[0].get('provisional') else ''}corpus "
         f"({metas[0]['n_rows']} rows, {metas[0]['n_entities']} entities, data_hash `{metas[0]['data_hash'][:12]}…`); "
         f"numeric metrics from {metas[0]['numeric_metrics']['source']} "
         f"(σ: {metas[0]['numeric_metrics'].get('sigma_source', 'local')})._", ""]
    L += ["| model | img/s | wall | C1 obs (full / pca64) | C5 obs | C1 proj | ρ(cos, blend) | ρ(cos, l2) | top-10 ∩ blend same-yr | ∩ l2 same-yr | ∩ blend any-yr | ρ(full, pca64) | var16 / var64 | cos p1 / p50 / p99 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in metas:
        e, cf, cp = m["eval"], m["eval"]["continuity_full"], m["eval"]["continuity_pca64"]
        ag, dr, pv = e["agreement_full"], e["dynamic_range"], e["pca_explained_variance"]
        L.append(f"| `{m['model']}` | {m['throughput_img_s']:.0f} | {m['wall_s'] / 60:.1f} min | {cf['observed']['C1']:.3f} / {cp['observed']['C1']:.3f} | "
                 f"{cf['observed']['C5']:.3f} | {cf['projected']['C1']:.3f} | {ag['spearman']['blend']:.3f} | {ag['spearman']['l2']:.3f} | "
                 f"{_pct(ag['overlap_same_year']['blend'])} | {_pct(ag['overlap_same_year']['l2'])} | {_pct(ag['overlap_any_year']['blend'])} | "
                 f"{e['spearman_full_vs_pca64']:.3f} | {pv['16']:.3f} / {pv['64']:.3f} | {dr['p1']:.3f} / {dr['p50']:.3f} / {dr['p99']:.3f} |")
    L += ["", "Processor assertions (first batch): " + "; ".join(
        f"`{m['model']}` {m['processor']['hf_processor']} {m['processor']['processor_config']} → "
        + (f"spatial_shapes {m['processor']['spatial_shapes']}, mask sum {m['processor']['mask_sum']}, " if "spatial_shapes" in m["processor"] else "")
        + f"pixel_values {m['processor']['pixel_values_shape']}, max |Δpixel| {m['processor']['max_abs_pixel_diff_255']:.3f}/255"
        for m in metas) + ".", ""]
    L += ["Pre-registered predictions (§2), auto-scored on this run:", ""]
    for m in metas:
        e = m["eval"]
        c1 = e["continuity_full"]["observed"]["C1"]
        rho, ov, rp = e["agreement_full"]["spearman"]["blend"], e["agreement_full"]["overlap_same_year"]["blend"], e["spearman_full_vs_pca64"]
        L.append(f"- `{m['model']}`: P1/P2 C1 < 0.95 → {c1:.3f} **{'met' if c1 < 0.95 else 'NOT met'}**; "
                 f"P5 ρ(cos, blend) ∈ [0.7, 0.9] → {rho:.3f} **{'met' if 0.7 <= rho <= 0.9 else 'NOT met'}**; "
                 f"P6 top-10 overlap with blend < 0.35 → {ov:.3f} **{'met' if ov < 0.35 else 'NOT met'}**; "
                 f"P7 ρ(full, pca64) ≥ 0.98 → {rp:.3f} **{'met' if rp >= 0.98 else 'NOT met'}**.")
    L.append("- P3 (class agreement) and P4 (triplets) are scored by `eval_similarity.py` and M4, not here.")
    if any(m.get("invariance") for m in metas):
        L += ["", "Factorial invariance diagnostic (§6; variant query vs canonical gallery within the sample; reported, not gated):", "",
              "| model | factor | canvas | cos(self, variant) | cos(nearest other) | self rank median | top-1 | top-10 | top-10 Jaccard |",
              "|---|---|---|---|---|---|---|---|---|"]
        for m in metas:
            inv = m.get("invariance") or {}
            for f, r in inv.items():
                if f.startswith("_"):
                    continue
                L.append(f"| `{m['model']}` | {f} | {r['image_hw'][0]}×{r['image_hw'][1]} | {r['self_cos_mean']:.3f} | {r['nearest_other_cos_mean']:.3f} | "
                         f"{r['self_rank_median']:.0f} | {_pct(r['top1'])} | {_pct(r['top10'])} | {r['jaccard_top10']:.3f} |")
    return "\n".join(L)


def update_md(block: str) -> None:
    text = MD.read_text()                                    # the LAST marker pair is the block (the prose mentions them too)
    i, j = text.rindex(MARK[0]) + len(MARK[0]), text.rindex(MARK[1])
    MD.write_text(text[:i] + "\n" + block + "\n" + text[j:])


# --------------------------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", choices=list(M.MODELS), help="repeatable; default: all")
    ap.add_argument("--db", action="store_true", help="ingest into the DuckDB store via db.ingest_embeddings")
    ap.add_argument("--renders", type=Path, default=None, help="use data/renders/ arrays (style hash checked) instead of rendering on the fly")
    ap.add_argument("--out", type=Path, default=M.EMB_DIR)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--dtype", default="float16", choices=["float16", "float32"])
    ap.add_argument("--limit", type=int, default=None, help="smoke test on the first N rows (skips the md update)")
    ap.add_argument("--diag-n", type=int, default=2000)
    ap.add_argument("--no-diag", action="store_true")
    a = ap.parse_args(argv)
    s42, keys, entities, corpus_info = load_corpus(a.limit)
    dist_fns, dist_info = numeric_metrics(s42, keys, entities)
    metas = [run_model(m, s42, keys, entities, corpus_info, dist_fns, dist_info, a) for m in (a.model or list(M.MODELS))]
    if a.limit is None:
        for f in sorted(a.out.glob("*.meta.json")):          # include models embedded in earlier runs
            if not any(m["model"] == f.stem.split(".")[0] for m in metas):
                metas.append(json.loads(f.read_text()))
        update_md(results_block(metas))
        print(f"results written to {MD}")
    else:
        print(results_block(metas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
