#!/usr/bin/env python
"""Render the whole corpus in one canonical style → ``data/renders/{kind}_{size}.npy`` (+ ``.meta.json``).

    uv run scripts/render_canonical.py --kind canon2 --size 336
    make render                                    # canon2@336, canon2@294, canon1@294

The array is uint8 ``[n, size, size, 3]`` written through a memmap (12 GB for canon2 @ 336); the sidecar
records the style hash so ``embed_images.py`` can refuse renders made by a different renderer.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pyramid_explorer import render as R                      # noqa: E402
from pyramid_explorer.paths import DATA_PROCESSED             # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=list(R.KINDS), default="canon2")
    ap.add_argument("--size", type=int, default=None, help="pixels per side; default = the kind's canonical size")
    ap.add_argument("--out", type=Path, default=None, help="override data/renders/{kind}_{size}.npy")
    ap.add_argument("--corpus", type=Path, default=DATA_PROCESSED / "corpus_s42.npy")
    a = ap.parse_args(argv)
    s42 = np.load(a.corpus)
    size = R.KINDS[a.kind] if a.size is None else a.size
    t0 = time.time()
    arr = R.render_corpus(s42, a.kind, size, a.out)
    out = a.out or R.render_path(a.kind, size)
    print(f"{out}: {arr.shape} uint8 ({out.stat().st_size / 1e9:.2f} GB) in {time.time() - t0:.1f}s; "
          f"style_hash {R.style_hash()[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
