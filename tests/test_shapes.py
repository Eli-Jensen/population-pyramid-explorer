"""shapes (A1): frame → corpus wrappers, file round trips, and agreement with the DuckDB store."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer import db, entities as E, shapes
from pyramid_explorer.paths import DATA_PROCESSED, N_BINS, N_DIMS, N_YEARS
from tests.test_db import build_synthetic_db
from tests.test_wpp import synthetic_world


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return synthetic_world(tmp_path_factory.mktemp("shapes"))


@pytest.fixture(scope="module")
def ents(world):
    return E.build_entities(world.raw, world.loc, names=world.names, n_agg_range=None)


def test_pyramids_from_raw_is_corpus_ordered(world, ents):
    pyr = shapes.pyramids_from_raw(world.raw, ents)
    assert list(pyr.columns) == shapes.PYR_COLS
    assert pyr["id"].drop_duplicates().tolist() == [e["id"] for e in ents]
    assert len(pyr) == len(ents) * N_YEARS * N_BINS
    assert pyr["year"].iloc[0] == 1950 and pyr["age_start"].iloc[:2].tolist() == [0, 5]


def test_build_corpus_shape_keys_and_files(world, ents, tmp_path):
    pyr = shapes.pyramids_from_raw(world.raw, ents)
    s42, keys = shapes.build_corpus(pyr, ents, out_dir=tmp_path)
    n = len(ents) * N_YEARS
    assert s42.shape == (n, N_DIMS) and s42.dtype == np.float64
    assert np.abs(s42.sum(1) - 1).max() < 1e-12 and (s42 >= 0).all()
    assert list(keys.columns) == shapes.KEY_COLS and len(keys) == n
    assert keys["row"].tolist() == list(range(n))
    idx = shapes.row_index(keys)
    for i, e in enumerate(ents):
        assert idx[(e["id"], 1950)] == i * N_YEARS and idx[(e["id"], 2100)] == i * N_YEARS + 150
        assert keys.loc[idx[(e["id"], 2026)], "pop_total"] == pytest.approx(e["pop_2026"], abs=1e-3)
    assert np.array_equal(np.load(tmp_path / "corpus_s42.npy"), s42)
    assert pd.read_parquet(tmp_path / "corpus_keys.parquet").equals(keys)
    # s21 identity and male/female split
    s21 = s42[:, :21] + s42[:, 21:]
    assert np.allclose(s21.sum(1), 1)


def test_build_corpus_rejects_incomplete_frames(world, ents, tmp_path):
    pyr = shapes.pyramids_from_raw(world.raw, ents)
    with pytest.raises(ValueError, match="rows"):
        shapes.build_corpus(pyr.iloc[:-1], ents, out_dir=tmp_path)
    shuffled = pyr.copy()
    shuffled.loc[shuffled.index[0], "year"] = 1949
    with pytest.raises(ValueError):
        shapes.build_corpus(shuffled, ents, out_dir=tmp_path)


def test_build_corpus_matches_db_load_corpus(world, ents, tmp_path):
    store = build_synthetic_db(world, tmp_path)
    pyr = db.load_pyramids(store.con)
    s42, keys = shapes.build_corpus(pyr, ents, out_dir=tmp_path)
    assert np.allclose(s42, store.s42, atol=1e-15)
    assert keys["id"].tolist() == store.keys["id"].tolist() and keys["year"].tolist() == store.keys["year"].tolist()
    assert keys["type"].tolist() == store.keys["type"].tolist()
    assert np.allclose(keys["pop_total"], store.keys["pop_total"])
    van = db.load_pyramids(store.con, patched=False)
    assert len(van) == len(pyr) and not van.equals(pyr)
    store.con.close()


def test_file_backed_loaders_without_db(world, ents, tmp_path, monkeypatch):
    pyr = shapes.pyramids_from_raw(world.raw, ents)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "absent.duckdb")
    monkeypatch.setattr(shapes, "CORPUS_S42", tmp_path / "corpus_s42.npy")
    monkeypatch.setattr(shapes, "CORPUS_KEYS", tmp_path / "corpus_keys.parquet")
    monkeypatch.setattr(shapes, "PYRAMIDS", tmp_path / "pyramids.parquet")
    s42, keys = shapes.build_corpus(pyr, ents, out_dir=tmp_path)
    pyr.to_parquet(tmp_path / "pyramids.parquet", index=False)
    X, K = shapes.load_corpus()
    assert np.array_equal(X, s42) and K.equals(keys)
    assert shapes.load_pyramids().equals(pyr)


def test_db_backed_loaders(world, tmp_path, monkeypatch):
    p = tmp_path / "store.duckdb"
    store = build_synthetic_db(world, tmp_path, p)
    store.con.close()
    monkeypatch.setattr(db, "DB_PATH", p)
    monkeypatch.setattr(shapes, "PYRAMIDS", tmp_path / "pyramids.parquet")
    X, K = shapes.load_corpus()
    assert np.array_equal(X, store.s42) and K.equals(store.keys)
    pyr = shapes.build_pyramids(patched=True)
    assert (tmp_path / "pyramids.parquet").exists() and shapes.load_pyramids().equals(pyr)
    assert E.load_entities() == store.entities
    tgo = pyr[(pyr["id"] == "TGO") & (pyr["year"] == 2000)][["pop_male", "pop_female"]].to_numpy()
    van = shapes.build_pyramids(patched=False)
    tgo_v = van[(van["id"] == "TGO") & (van["year"] == 2000)][["pop_male", "pop_female"]].to_numpy()
    assert not np.array_equal(tgo, tgo_v)


# ----------------------------------------------------------------------------- real corpus (slow)

@pytest.mark.slow
@pytest.mark.skipif(not (DATA_PROCESSED / "corpus_s42.npy").exists(), reason="corpus not built")
def test_real_corpus_consistent_with_entities():
    X, keys = shapes.load_corpus()
    ents = E.load_entities()
    assert X.shape == (len(ents) * N_YEARS, N_DIMS) and len(keys) == X.shape[0]
    assert keys["id"].drop_duplicates().tolist() == [e["id"] for e in ents]
    assert np.abs(X.sum(1) - 1).max() < 1e-9
    idx = shapes.row_index(keys)
    assert idx[("JPN", 2024)] == [e["id"] for e in ents].index("JPN") * N_YEARS + 74
