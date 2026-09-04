"""Pyramids and corpus (A1) — thin wrappers over :mod:`pyramid_explorer.db` that still write and
read the CONTRACT §1 files (``pyramids.parquet``, ``corpus_s42.npy``, ``corpus_keys.parquet``).

When ``data/processed/explorer.duckdb`` exists the loaders read the store; otherwise they fall back
to the raw WPP frame (``build_*``) or the exported files (``load_*``), so B/C/D never need duckdb.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer.paths import AGE_STARTS, DATA_PROCESSED, N_BINS, N_DIMS, N_YEARS, YEARS

PYRAMIDS = DATA_PROCESSED / "pyramids.parquet"
CORPUS_S42 = DATA_PROCESSED / "corpus_s42.npy"
CORPUS_KEYS = DATA_PROCESSED / "corpus_keys.parquet"
PYR_COLS = ["id", "locid", "year", "age_start", "pop_male", "pop_female"]
KEY_COLS = ["row", "id", "locid", "year", "type", "pop_total"]


def _db_exists() -> bool:
    from pyramid_explorer import db

    return db.DB_PATH.exists()


def pyramids_from_raw(raw: pd.DataFrame, entities: list[dict]) -> pd.DataFrame:
    """Long ``id, locid, year, age_start, pop_male, pop_female`` in corpus order from a raw WPP frame."""
    ids = pd.DataFrame({"locid": [e["locid"] for e in entities], "id": [e["id"] for e in entities],
                        "idx": range(len(entities))})
    df = raw.merge(ids, on="locid", how="inner").sort_values(["idx", "year", "age_start"])
    return df[PYR_COLS].reset_index(drop=True)


def build_pyramids(patched: bool = True, *, out: Path | None = None) -> pd.DataFrame:
    """Write ``data/processed/pyramids.parquet`` (thousands, patched by default) and return it.
    Reads ``pop_age5`` / ``pop_age5_vanilla`` from the store when it exists, else the raw files."""
    from pyramid_explorer import db

    if _db_exists():
        with db.connect(read_only=True) as con:
            pyr = db.load_pyramids(con, patched=patched)
    else:
        from pyramid_explorer.data import wpp
        from pyramid_explorer.entities import build_entities

        raw = wpp.load_raw_population(patched=False)
        entities = build_entities(raw, wpp.load_locations())
        pyr = pyramids_from_raw(wpp.load_raw_population(patched=True) if patched else raw, entities)
    out = out or PYRAMIDS
    out.parent.mkdir(parents=True, exist_ok=True)
    pyr.to_parquet(out, index=False)
    return pyr


def load_pyramids() -> pd.DataFrame:
    """``pyramids.parquet`` (the patched long frame)."""
    return pd.read_parquet(PYRAMIDS)


def build_corpus(pyr: pd.DataFrame, entities: list[dict], *, out_dir: Path | None = None) -> tuple[np.ndarray, pd.DataFrame]:
    """(s42 float64 [n, 42], keys) in corpus order from the long frame; also writes ``corpus_s42.npy``
    and ``corpus_keys.parquet``. Raises when any entity lacks its 151 x 21 block."""
    order = {e["id"]: i for i, e in enumerate(entities)}
    df = pyr[pyr["id"].isin(order)]
    df = df.assign(idx=df["id"].map(order)).sort_values(["idx", "year", "age_start"])
    n = len(entities)
    if len(df) != n * N_YEARS * N_BINS:
        missing = sorted(set(order) - set(df["id"]))
        raise ValueError(f"expected {n} x {N_YEARS} x {N_BINS} rows, got {len(df)}; missing entities {missing[:5]}")
    years = df["year"].to_numpy().reshape(n, N_YEARS, N_BINS)
    bins = df["age_start"].to_numpy().reshape(n, N_YEARS, N_BINS)
    if not (years == np.array(YEARS)[None, :, None]).all() or not (bins == np.array(AGE_STARTS)[None, None, :]).all():
        raise ValueError("every entity needs years 1950..2100 x age_start 0..100 step 5")
    m = df["pop_male"].to_numpy(dtype=np.float64).reshape(n, N_YEARS, N_BINS)
    f = df["pop_female"].to_numpy(dtype=np.float64).reshape(n, N_YEARS, N_BINS)
    total = m.sum(2) + f.sum(2)
    if not (total > 0).all():
        raise ValueError("zero total population in some entity-year")
    s42 = (np.concatenate([m, f], axis=2) / total[:, :, None]).reshape(n * N_YEARS, N_DIMS)
    keys = pd.DataFrame({
        "row": np.arange(n * N_YEARS, dtype=np.int64),
        "id": np.repeat([e["id"] for e in entities], N_YEARS),
        "locid": np.repeat([int(e["locid"]) for e in entities], N_YEARS).astype(np.int64),
        "year": np.tile(np.array(YEARS, dtype=np.int64), n),
        "type": np.repeat([e["type"] for e in entities], N_YEARS),
        "pop_total": total.ravel(),
    })
    out = Path(out_dir or DATA_PROCESSED)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / CORPUS_S42.name, s42)
    keys.to_parquet(out / CORPUS_KEYS.name, index=False)
    return s42, keys


def load_corpus() -> tuple[np.ndarray, pd.DataFrame]:
    """(s42, keys): from the store when present, else the exported files."""
    if _db_exists():
        from pyramid_explorer import db

        with db.connect(read_only=True) as con:
            return db.load_corpus(con)
    return np.load(CORPUS_S42), pd.read_parquet(CORPUS_KEYS)


def row_index(keys: pd.DataFrame) -> dict[tuple[str, int], int]:
    """``(id, year) -> row``."""
    return {(i, int(y)): int(r) for i, y, r in zip(keys["id"], keys["year"], keys["row"])}


__all__ = ["build_pyramids", "load_pyramids", "build_corpus", "load_corpus", "row_index", "pyramids_from_raw"]
