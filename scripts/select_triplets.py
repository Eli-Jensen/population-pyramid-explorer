#!/usr/bin/env python
"""Select the 88 human-triplet items (PLAN §4.6 item 8; evals/protocol.md §3) → evals/triplets_selection.json
(+ a copy under web/src/data/ for the /eval/triplets collector).

    uv run scripts/select_triplets.py                      # seed 0, real corpus, exposed image space from verdicts.json
    uv run scripts/select_triplets.py --seed 1 --out /tmp/sel.json --no-web

Deterministic: one seed, no wall-clock in the output.  Uses the built corpus (`shapes.load_corpus`), `sigma.json`
(fitted on first use when absent), `evals/verdicts.json` (G1 gate → numeric candidates; `exposed_visual` → the
image space of the visual stratum) and every `evals/embeddings/<model>.pca64.npy` aligned with the corpus.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer import triplets as T  # noqa: E402
from pyramid_explorer.metrics import fit_sigma, load_sigma, SIGMA_PATH  # noqa: E402
from pyramid_explorer.paths import EVALS  # noqa: E402
from pyramid_explorer.search import load_inputs  # noqa: E402

EMB_DIR = EVALS / "embeddings"


def load_embeddings(n_rows: int, emb_dir: Path = EMB_DIR) -> dict[str, np.ndarray]:
    """Every ``<model>.pca64.npy`` with exactly ``n_rows`` rows (others are skipped with a note)."""
    out = {}
    for p in sorted(emb_dir.glob("*.pca64.npy")):
        E = np.load(p).astype(np.float32)
        model = p.name[: -len(".pca64.npy")]
        if E.shape[0] != n_rows:
            print(f"[skip] {p.name}: {E.shape[0]} rows vs corpus {n_rows}", file=sys.stderr)
            continue
        out[model] = E
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--anchor-year", type=int, default=2024)
    ap.add_argument("--anchor-minpop", type=float, default=1000.0, help="thousands (default 1 M)")
    ap.add_argument("--cand-minpop", type=float, default=100.0, help="thousands (product default 100k)")
    ap.add_argument("--out", type=Path, default=T.SELECTION_PATH)
    ap.add_argument("--no-web", action="store_true", help="do not copy to web/src/data/triplets_selection.json")
    a = ap.parse_args(argv)

    X, keys, ents = load_inputs()
    sigma = load_sigma() if SIGMA_PATH.exists() else fit_sigma(X, keys, ents, write=True)
    emb = load_embeddings(len(keys))
    verdicts = json.loads(T.VERDICTS_PATH.read_text()) if T.VERDICTS_PATH.exists() else None
    sp = T.Space(X, keys, ents, sigma, emb, cand_minpop=a.cand_minpop)
    numeric = T.numeric_metrics_from_verdicts(verdicts)
    visual = T.exposed_visual_from_verdicts(verdicts, sp.visual_metrics)
    print(f"corpus {len(keys)} rows · image spaces {list(emb)} · visual stratum uses {visual} · numeric {numeric}")
    sel = T.select_triplets(sp, seed=a.seed, anchor_year=a.anchor_year, anchor_minpop=a.anchor_minpop,
                            numeric_metrics=numeric, visual_metric=visual, data_hash=T.corpus_hash(X))
    T.write_selection(sel, a.out, None if a.no_web else T.SELECTION_WEB_PATH)
    strata = {s: sum(1 for it in sel["items"] if it["stratum"] == s and it["duplicate_of"] is None) for s in T.STRATA}
    print(f"wrote {a.out} ({a.out.stat().st_size / 1024:.0f} KB): {sel['n_unique']} unique {strata} + "
          f"{sel['n_items'] - sel['n_unique']} duplicates = {sel['n_items']} items; anchors {sel['n_anchor_pool']} in pool, "
          f"{sel['n_anchor_reused']} reused")
    for s, u in sel["pair_uses"].items():
        print(f"  {s} pairs: {u}")
    if not a.no_web:
        print(f"copied to {T.SELECTION_WEB_PATH}")


if __name__ == "__main__":
    main()
