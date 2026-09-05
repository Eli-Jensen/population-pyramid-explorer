"""Write ``evals/fixtures/parity_500.json`` — the Python-side truth the TS math twins are tested against.

Samples 500 corpus rows (seed 0, without replacement) from ``data/processed/corpus_u16.npy`` +
``corpus_keys.parquet``, dequantises them EXACTLY as the browser does (``float32(u) / 65535``,
:func:`pyramid_explorer.quantise.u16_to_shares`), computes :func:`pyramid_explorer.features.features`
and records ``{id, year, row, pop_total, u16[42], features{…}}`` per row (NaN → null). Five fixed
"spot" rows (first row, an entity's last/first-year boundary pair, Japan 2026, the last row) carry
their raw u16 so the Node integration test can check the decoded ``shares.*.d16z`` against the
source array. ``data_hash`` is sha256 over the little-endian uint16 corpus bytes and must equal
``meta.verdicts.data_hash`` (AMENDMENTS §F).

    uv run python scripts/parity_fixture.py            # writes evals/fixtures/parity_500.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer.features import FEATURE_NAMES, features
from pyramid_explorer.paths import DATA_PROCESSED, EVALS, N_DIMS, N_YEARS
from pyramid_explorer.quantise import U16_TOTAL, u16_to_shares

OUT = EVALS / "fixtures" / "parity_500.json"


def _clean(v):
    """JSON-safe scalar: numpy → Python, NaN → None."""
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    return v


def build(n: int = 500, seed: int = 0) -> dict:
    u16 = np.load(DATA_PROCESSED / "corpus_u16.npy")
    keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
    if u16.shape != (len(keys), N_DIMS) or u16.dtype != np.uint16:
        raise SystemExit(f"corpus_u16.npy {u16.shape} {u16.dtype} does not match keys ({len(keys)} rows)")
    if not np.all(u16.sum(axis=1, dtype=np.int64) == U16_TOTAL):
        raise SystemExit("some corpus row does not sum to 65535 — quantise round trip broken")
    n_rows = len(keys)
    if n_rows % N_YEARS:
        raise SystemExit(f"n_rows {n_rows} is not a multiple of {N_YEARS}")

    rng = np.random.default_rng(seed)
    sample = np.sort(rng.choice(n_rows, size=n, replace=False))
    row_of = {(i, y): r for r, i, y in zip(keys["row"], keys["id"], keys["year"], strict=True)}
    spot_rows = [0, N_YEARS - 1, N_YEARS, row_of[("JPN", 2026)], n_rows - 1]
    wanted = np.unique(np.concatenate([sample, spot_rows]))

    # dequantise exactly like the browser (float32 u / 65535), then features in float64 — same as the JS twin
    shares = u16_to_shares(u16[wanted])
    feat = features(shares)
    feat.index = wanted  # so .loc[corpus_row] works below

    def rec(r: int) -> dict:
        k = keys.iloc[r]
        f = feat.loc[r]
        return {
            "row": int(r),
            "id": str(k["id"]),
            "year": int(k["year"]),
            "pop_total": float(k["pop_total"]),
            "u16": [int(x) for x in u16[r]],
            "features": {name: _clean(f[name]) for name in FEATURE_NAMES},
        }

    data_hash = hashlib.sha256(np.ascontiguousarray(u16.astype("<u2")).tobytes()).hexdigest()
    stages = feat.loc[sample]["stage"].value_counts().to_dict()
    return {
        "_meta": {
            "source": "scripts/parity_fixture.py",
            "inputs": ["data/processed/corpus_u16.npy", "data/processed/corpus_keys.parquet"],
            "dequantise": "float32(u16) / 65535, features in float64 (pyramid_explorer.features.features)",
            "stages_in_sample": {str(k): int(v) for k, v in stages.items()},
            "quantisation_max_abs_err_units": float(
                np.abs(u16[sample].astype(np.float64)
                       - np.load(DATA_PROCESSED / "corpus_s42.npy", mmap_mode="r")[sample] * U16_TOTAL).max()
            ) if (DATA_PROCESSED / "corpus_s42.npy").exists() else None,
        },
        "n_rows": int(n_rows),
        "n_years": int(N_YEARS),
        "n_dims": int(N_DIMS),
        "u16_total": int(U16_TOTAL),
        "seed": int(seed),
        "data_hash": data_hash,
        "feature_names": list(FEATURE_NAMES),
        "rows": [rec(int(r)) for r in sample],
        "spot": [rec(int(r)) for r in spot_rows],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    fixture = build(args.n, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fixture, separators=(",", ":"), allow_nan=False) + "\n")
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB): {len(fixture['rows'])} rows, "
          f"{len(fixture['spot'])} spot rows, data_hash {fixture['data_hash'][:12]}…, "
          f"stages {fixture['_meta']['stages_in_sample']}")


if __name__ == "__main__":
    main()
