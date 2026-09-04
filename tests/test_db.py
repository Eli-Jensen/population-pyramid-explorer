"""DuckDB store (A1, CONTRACT AMENDMENTS §A): an in-memory synthetic world pushed through the same
``ingest_*`` functions the build uses, plus real-store checks (slow, skipped when the file is absent)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from pyramid_explorer import db, entities as E, patches, quantise, shapes
from pyramid_explorer.paths import DATA_PROCESSED, N_BINS, N_DIMS, N_YEARS, REPO_ROOT, WEB_DATA, WEB_SRC_DATA
from tests.test_wpp import synthetic_world

SIGMA = {"l2": {"2": 0.08, "1": 0.09}, "w1sex": {"2": 11.0}, "w1": {"1": 10.0}}
REAL_DB = db.DB_PATH.exists()


def build_synthetic_db(world: SimpleNamespace, tmp_dir: Path, path: str | Path = ":memory:") -> SimpleNamespace:
    """The full A1 build order on the synthetic world; returns (con, entities, patch, ...)."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    con = db.connect(path, rebuild=path != ":memory:")
    db.ingest_sources(con)
    db.ingest_locations(con, world.loc)
    patched, patch = patches.apply_togo_patch(world.raw, world.update_csv, world.loc)
    ents = E.build_entities(patched, world.loc, names=world.names, n_agg_range=None)   # entities from the PATCHED frame
    patch = patches.restrict_to_entities(patch, ents)
    db.insert_entities(con, ents)
    sov = tmp_dir / "sovereignty.yaml"
    sov.write_text(yaml.safe_dump({"rows": [{"entity_id": "TGO", "state_since": 1960, "predecessor": "FRA",
                                             "event": "independence", "note": "synthetic", "ref": "test"}]}))
    db.ingest_sovereignty(con, sov)
    db.ingest_pop_age5(con, world.raw, patched, patch)
    db.ingest_wpp_indicators(con, world.indicators, world.indicators_update, patch)
    years = np.arange(1950, 2024)
    maddison = pd.DataFrame({"code": np.repeat(["AAA", "BBB", "SUN"], len(years)), "year": np.tile(years, 3),
                             "indicator_id": "gdppc_maddison", "value": 1000.0 + np.arange(3 * len(years)),
                             "is_forecast": False})
    econ = {"maddison": db.ingest_indicators(con, "maddison", "maddison-2023", maddison)}
    weo = pd.DataFrame({"code": ["AAA", "TGO", "AAA", "TGO"], "year": [2024, 2024, 2030, 2030],
                        "indicator_id": "gdppc_ppp_weo", "value": [1.0, 2.0, 3.0, 4.0], "is_forecast": [False, False, True, True]})
    econ["weo"] = db.ingest_indicators(con, "weo", "weo-2025-04", weo)
    report = db.refresh_derived(con)
    s42, keys = db.load_corpus(con)
    u16 = quantise.shares_to_u16(s42)
    db.write_u16(con, u16)
    data_hash = __import__("hashlib").sha256(np.ascontiguousarray(u16, dtype="<u2").tobytes()).hexdigest()
    db.write_build_meta(con, {"data_hash": data_hash, "patches": json.dumps([patch["id"]])})
    db.write_sigma(con, SIGMA)
    return SimpleNamespace(con=con, entities=ents, patch=patch, patched=patched, report=report, s42=s42, keys=keys,
                           u16=u16, data_hash=data_hash, econ=econ)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return synthetic_world(tmp_path_factory.mktemp("dbworld"))


@pytest.fixture(scope="module")
def store(world, tmp_path_factory):
    return build_synthetic_db(world, tmp_path_factory.mktemp("dbstore"))


# ----------------------------------------------------------------------------- schema, versions

def test_schema_applies_and_meta_written():
    con = db.connect(":memory:")
    tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    assert {"source", "patch", "build_meta", "location", "entity", "entity_alias", "entity_membership", "sovereignty",
            "pop_age5", "pop_age5_vanilla", "pyramid", "corpus_u16", "sigma", "indicator", "indicator_value",
            "source_entity_map", "source_orphan", "coverage", "embedding_model", "embedding", "embedding_pca64",
            "eval_label_set", "eval_label", "eval_triplet", "eval_verdict",
            "corpus_entity", "corpus_row", "indicator_public", "entity_years"} <= tables
    assert db.build_meta(con)["schema_version"] == db.SCHEMA_VERSION
    assert con.execute("SELECT count(*) FROM corpus_row").fetchone()[0] == 0
    assert con.execute("SELECT l1([1.0, 2.0], [0.0, 4.0])").fetchone()[0] == 3.0


def test_version_mismatch_refuses(tmp_path):
    p = tmp_path / "old.duckdb"
    con = db.connect(p)
    db.write_build_meta(con, schema_version="0")
    con.close()
    with pytest.raises(RuntimeError, match="schema_version"):
        db.connect(p)
    with pytest.raises(FileNotFoundError):
        db.connect(tmp_path / "missing.duckdb", read_only=True)


# ----------------------------------------------------------------------------- corpus invariants

def test_corpus_row_matches_shapes_row_index(store):
    rows = store.con.execute("SELECT entity_id, year, row FROM corpus_row ORDER BY row").fetchall()
    idx = shapes.row_index(store.keys)
    assert len(rows) == len(idx) == len(store.entities) * N_YEARS
    assert all(idx[(e, int(y))] == r for e, y, r in rows)
    assert [r[2] for r in rows] == list(range(len(rows)))


def test_entity_order_equals_entities_export(store, tmp_path):
    assert [e["id"] for e in db.load_entities(store.con)] == [e["id"] for e in store.entities]
    paths = db.export_processed(store.con, tmp_path)
    assert json.loads(paths["entities"].read_text()) == store.entities
    assert store.keys["id"].drop_duplicates().tolist() == [e["id"] for e in store.entities]


def test_shares_sum_to_one_and_dense_shape(store):
    assert store.s42.shape == (len(store.entities) * N_YEARS, N_DIMS)
    assert np.abs(store.s42.sum(1) - 1).max() < 1e-12
    assert (store.s42 >= 0).all()
    assert list(store.keys.columns) == ["row", "id", "locid", "year", "type", "pop_total"]
    assert store.keys["type"].tolist() == ["country"] * 3 * N_YEARS + ["aggregate"] * 2 * N_YEARS


def test_21_bins_x_151_years(store):
    for t in ("pop_age5", "pop_age5_vanilla"):
        g = store.con.execute(f"SELECT entity_id, count(*) FROM {t} GROUP BY 1").fetchall()
        assert all(n == N_BINS * N_YEARS for _, n in g) and len(g) == len(store.entities)


def test_cdf_monotone_and_consistent(store):
    cdf = db.load_cdf(store.con)
    m, f = cdf[:, :21], cdf[:, 21:]
    assert (np.diff(m, axis=1) >= -1e-15).all() and (np.diff(f, axis=1) >= -1e-15).all()
    assert np.allclose(m[:, -1] + f[:, -1], 1.0, atol=1e-12)
    assert np.allclose(np.cumsum(store.s42[:, :21], axis=1), m, atol=1e-12)


def test_member_sum_on_vanilla_and_patch_identity(store):
    rep = store.report
    assert rep["member_sum_worst_bin_ratio"] <= 1
    assert rep["patch_togo-2026-01-19"] == {"entities": ["TGO"], "recomputed": ["agg-900"]}
    changed = store.con.execute("""
        SELECT entity_id, count(*) FROM pop_age5 p JOIN pop_age5_vanilla v USING (entity_id, year, age_start)
        WHERE p.pop_male <> v.pop_male OR p.pop_female <> v.pop_female GROUP BY 1 ORDER BY 1""").fetchall()
    assert [e for e, _ in changed] == ["TGO", "agg-900"]
    src = dict(store.con.execute("SELECT entity_id, max(source_id) FROM pop_age5 GROUP BY 1").fetchall())
    assert src["TGO"] == src["agg-900"] == "wpp2024-togo-update" and src["AAA"] == "wpp2024"
    assert db.load_patches(store.con)[0]["recomputed_aggregates"] == [900]


def test_entities_pop_2026_matches_patched_corpus(store):
    """entities.json is built from the patched frame: TGO's pop_2026 (and every aggregate containing it) equals the
    shipped pyramid total, not the vanilla UN figure (the synthetic patch scales TGO by 1.1 in every year)."""
    pop = store.keys.set_index(["id", "year"])["pop_total"]
    for e in store.entities:
        assert abs(e["pop_2026"] - pop[(e["id"], 2026)]) < 1e-3, e["id"]
    van = store.con.execute("SELECT sum(pop_male + pop_female) FROM pop_age5_vanilla WHERE entity_id = 'TGO' AND year = 2026").fetchone()[0]
    tgo = next(e for e in store.entities if e["id"] == "TGO")
    assert abs(tgo["pop_2026"] - van) > 1.0                       # the assertion above is not vacuous
    doc = json.loads(store.con.execute("SELECT doc FROM entity WHERE id = 'TGO'").fetchone()[0])
    assert doc["pop_2026"] == tgo["pop_2026"] == store.con.execute("SELECT pop_2026 FROM entity WHERE id = 'TGO'").fetchone()[0]


def test_member_sum_failure_is_caught(world, tmp_path):
    bad = world.raw.copy()
    bad.loc[(bad["locid"] == 900) & (bad["year"] == 1990) & (bad["age_start"] == 0), "pop_male"] += 50
    con = db.connect(":memory:")
    db.ingest_sources(con)
    db.ingest_locations(con, world.loc)
    db.insert_entities(con, E.build_entities(bad, world.loc, names=world.names, n_agg_range=None))
    db.ingest_pop_age5(con, bad, bad, None)
    with pytest.raises(AssertionError, match="member-sum"):
        db.refresh_derived(con)


def test_fk_rejects_unknown_entity(store):
    with pytest.raises(Exception, match="(?i)foreign key|constraint"):
        store.con.execute("INSERT INTO pop_age5 VALUES ('ZZZ', 1950, 0, 1, 1, 'wpp2024', NULL)")
    with pytest.raises(Exception, match="(?i)foreign key|constraint"):
        store.con.execute("INSERT INTO indicator_value VALUES ('AAA', 1950, 'nope', 'wpp2024', 1, FALSE)")


def test_sovereignty_unknown_entity_raises(store, tmp_path):
    p = tmp_path / "sov.yaml"
    p.write_text(yaml.safe_dump({"rows": [{"entity_id": "ZZZ", "state_since": 2000}]}))
    with pytest.raises(ValueError, match="unknown entity"):
        db.ingest_sovereignty(store.con, p)
    ey = db.entity_years(store.con).set_index("entity_id")
    assert ey.at["TGO", "state_since"] == 1960 and ey.at["TGO", "predecessor"] == "FRA"
    assert ey.at["AAA", "pyramid_first"] == 1950 and ey.at["AAA", "pyramid_last"] == 2100
    assert ey.at["AAA", "gdp_first"] == 1950 and ey.at["AAA", "gdp_last"] == 2023


# ----------------------------------------------------------------------------- indicators, sources, coverage

def test_source_codes_all_accounted(store):
    """Every upstream code is either mapped to an entity or recorded as an orphan — never dropped silently."""
    assert store.econ["maddison"] == {"rows": 2 * 74, "orphans": ["SUN"]}
    orphans = store.con.execute("SELECT source_id, code, reason, n_rows, first_year, last_year FROM source_orphan").fetchall()
    assert orphans == [("maddison-2023", "SUN", "drop", 74, 1950, 2023)]
    assert store.econ["weo"] == {"rows": 4, "orphans": []}
    ids = {r[0] for r in store.con.execute("SELECT DISTINCT indicator_id FROM indicator_value").fetchall()}
    assert {"gdppc_maddison", "gdppc_ppp_weo", "pop_total_wpp", "median_age_wpp", "tfr_wpp"} <= ids
    n_ind = store.con.execute("SELECT count(*) FROM indicator").fetchone()[0]
    assert n_ind == len(db.WPP_INDICATORS) + 2


def test_unexpected_orphan_raises(store):
    bad = pd.DataFrame({"code": ["QQQ"], "year": [2000], "indicator_id": ["rgdpna_pwt"], "value": [1.0], "is_forecast": [False]})
    with pytest.raises(ValueError, match="unexpected orphan"):
        db.ingest_indicators(store.con, "pwt", "pwt-11.0", bad)


def test_wpp_indicators_patched_source_and_bin_sum_check(store):
    df = db.load_indicator(store.con, "pop_total_wpp")
    src = df.groupby("entity_id")["source_id"].agg(set)
    assert src["TGO"] == {"wpp2024-togo-update"} and src["agg-900"] == {"wpp2024"}
    tot = store.con.execute("SELECT sum(pop_male + pop_female) FROM pop_age5 WHERE entity_id = 'TGO' AND year = 2022").fetchone()[0]
    val = df[(df["entity_id"] == "TGO") & (df["year"] == 2022)]["value"].item()
    assert abs(tot - val) <= 0.02
    assert store.report["bin_sum_vs_tpop_worst"] <= 0.02
    assert (df["is_forecast"] == (df["year"] > 2023)).all()
    # the recomputed aggregate keeps vanilla indicators: its bins differ from pop_total_wpp by exactly the TGO delta,
    # which the sanity check verifies as an identity (never silently skipped)
    agg = store.con.execute("SELECT sum(pop_male + pop_female) FROM pop_age5 WHERE entity_id = 'agg-900' AND year = 2026").fetchone()[0]
    ind = df[(df["entity_id"] == "agg-900") & (df["year"] == 2026)]["value"].item()
    d_tgo = store.con.execute("""SELECT sum(p.pop_male + p.pop_female - v.pop_male - v.pop_female) FROM pop_age5 p
        JOIN pop_age5_vanilla v USING (entity_id, year, age_start) WHERE entity_id = 'TGO' AND year = 2026""").fetchone()[0]
    assert abs(agg - ind) > 1.0 and abs((agg - ind) - d_tgo) <= 0.02 + 0.001 * N_BINS * 3
    assert store.report["bin_sum_recomputed_identity_worst"] <= 0.02 + 0.001 * N_BINS * 3


def test_bin_sum_failure_is_caught(world):
    bad = world.indicators.copy()
    bad.loc[(bad["locid"] == 1) & (bad["year"] == 1990), "pop_total"] += 5.0
    con = db.connect(":memory:")
    db.ingest_sources(con)
    db.ingest_locations(con, world.loc)
    db.insert_entities(con, E.build_entities(world.raw, world.loc, names=world.names, n_agg_range=None))
    db.ingest_pop_age5(con, world.raw, world.raw, None)
    db.ingest_wpp_indicators(con, bad, None, None)
    with pytest.raises(AssertionError, match="bin sums differ"):
        db.refresh_derived(con)


def test_coverage_rows_and_last_actual(store):
    cov = db.coverage(store.con).set_index(["entity_id", "series", "source_id"])
    assert cov.loc[("AAA", "pyramid", "wpp2024")].tolist() == [1950, 2100, 151, 0, 2023]
    assert cov.loc[("AAA", "gdppc_maddison", "maddison-2023")].tolist() == [1950, 2023, 74, 0, 2023]
    assert cov.loc[("AAA", "gdppc_ppp_weo", "weo-2025-04")].tolist() == [2024, 2030, 2, 5, 2024]
    assert cov.loc[("TGO", "pyramid", "wpp2024-togo-update")]["n_obs"] == 151
    both = store.con.execute("""
        SELECT count(DISTINCT c.entity_id) FROM coverage c JOIN indicator_value iv ON iv.entity_id = c.entity_id
        WHERE c.series = 'pyramid' AND c.first_year <= 1990 AND iv.indicator_id = 'gdppc_maddison' AND iv.year = 1990""").fetchone()[0]
    assert both == 2


def test_indicator_public_hides_weo_and_export_never_ships_it(store, tmp_path):
    pub = {r[0] for r in store.con.execute("SELECT DISTINCT source_id FROM indicator_public").fetchall()}
    assert "weo-2025-04" not in pub and {"wpp2024", "maddison-2023"} <= pub
    assert db.load_indicator(store.con, "gdppc_ppp_weo", public_only=True).empty
    assert len(db.load_indicator(store.con, "gdppc_ppp_weo")) == 4
    paths = db.export_processed(store.con, tmp_path)
    ind = pd.read_parquet(paths["indicators"])
    assert not ind["indicator_id"].str.contains("_weo").any() and "weo-2025-04" not in set(ind["source_id"])
    assert {"gdppc_maddison", "pop_total_wpp"} <= set(ind["indicator_id"])
    ey = pd.read_parquet(paths["entity_years"])
    sources = set().union(*(set(s) for s in ey["sources"] if s is not None))
    assert "weo-2025-04" not in sources and {"wpp2024", "maddison-2023"} <= sources     # entity_years.sources too
    assert ey.set_index("entity_id").at["AAA", "gdp_last"] == 2023                       # GDP span ignores WEO
    assert not any(_scan(p) for p in paths.values() if p.suffix in (".parquet", ".json")), "export mentions WEO/IMF"


WEO_TEXT = re.compile(r"weo|imf|ngdp", re.IGNORECASE)      # text columns / JSON: any spelling
WEO_BYTES = (b"_weo", b"NGDP", b"weo-20", b"WEO")          # binaries: exact tokens only (3-byte regexes false-positive on bytes)


def _scan(path: Path) -> bool:
    """True when a shipped file mentions a WEO source/indicator id or the IMF's NGDP codes — text and LIST
    columns of parquet files are exploded and matched case-insensitively; binaries are token-matched."""
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
        for c in df.columns:
            col = df[c]
            if len(col) and isinstance(col.dropna().iloc[0] if col.notna().any() else None, (list, np.ndarray)):
                col = col.dropna().explode()
            if col.dtype == object or str(col.dtype) in ("string", "str"):
                if col.dropna().astype(str).str.contains(WEO_TEXT).any():
                    return True
        return False
    if path.suffix == ".json":
        return bool(WEO_TEXT.search(path.read_text(encoding="utf-8")))
    data = path.read_bytes()
    return any(tok in data for tok in WEO_BYTES)


def test_weo_never_exported():
    files = list(DATA_PROCESSED.glob("*.parquet")) + list(WEB_DATA.rglob("*")) + list(WEB_SRC_DATA.glob("*.json"))
    files = [f for f in files if f.is_file() and f.suffix in (".parquet", ".json", ".bin", ".u16", ".f32", ".f16", ".d16z")]
    if not files:
        pytest.skip("nothing exported yet")
    leaks = [str(f.relative_to(REPO_ROOT)) for f in files if _scan(f)]
    assert not leaks, leaks


# ----------------------------------------------------------------------------- arrays, knn, macros

def test_arrow_array_round_trip_exact(store):
    s42, keys = db.load_corpus(store.con)
    assert np.array_equal(s42, store.s42) and s42.dtype == np.float64
    assert np.array_equal(db.load_u16(store.con), store.u16)
    assert keys.equals(store.keys)
    assert db.load_sigma(store.con) == SIGMA


def test_knn_sql_equals_numpy(store, tmp_path):
    rng = np.random.default_rng(0)
    n = len(store.keys)
    Z = rng.normal(size=(n, 64)).astype(np.float32)
    Z /= np.linalg.norm(Z, axis=1, keepdims=True)
    pca, full, meta = tmp_path / "toy.pca64.npy", tmp_path / "toy.npy", tmp_path / "toy.meta.json"
    np.save(pca, Z.astype(np.float16))
    np.save(full, rng.normal(size=(n, 768)).astype(np.float32))
    meta.write_text(json.dumps({"data_hash": "wrong", "hf_id": "toy/toy", "dim": 768}))
    with pytest.raises(ValueError, match="data_hash"):
        db.ingest_embeddings(store.con, "toy", full, pca, meta, store.keys)
    meta.write_text(json.dumps({"data_hash": store.data_hash, "hf_id": "toy/toy", "dim": 768}))
    out = db.ingest_embeddings(store.con, "toy", full, pca, meta, store.keys)
    assert out == {"model": "toy", "pca64": n, "full": n}
    Zdb = db.load_embeddings(store.con, "toy")
    assert np.array_equal(Zdb, Z.astype(np.float16).astype(np.float32))
    assert db.load_embeddings(store.con, "toy", dim=768).shape == (n, 768)
    q = store.keys.index[(store.keys["id"] == "BBB") & (store.keys["year"] == 2000)][0]
    d = 1 - Zdb @ Zdb[q] / (np.linalg.norm(Zdb, axis=1) * np.linalg.norm(Zdb[q]))
    d[q] = np.inf
    top = db.knn(store.con, "BBB", 2000, model="toy", k=10)
    assert top["row"].tolist() == np.argsort(d, kind="stable")[:10].tolist()
    assert np.allclose(top["d"].to_numpy(), np.sort(d)[:10], atol=1e-5)
    only_c = db.knn(store.con, "BBB", 2000, model="toy", k=5, where="cr.type = 'country' AND cr.year = 2000")
    assert only_c["year"].eq(2000).all() and set(only_c["entity_id"]) <= {"AAA", "TGO"}


def test_blend_macro_equals_metrics_distances(store):
    from pyramid_explorer import metrics as M

    rng = np.random.default_rng(0)
    n = len(store.keys)
    a, b = rng.integers(0, n, 300), rng.integers(0, n, 300)
    con = store.con
    con.register("_pairs", pd.DataFrame({"a": a, "b": b, "i": np.arange(300)}))
    got = con.execute(f"""
        SELECT blend_d(pa.s42, pa.cdf42, pb.s42, pb.cdf42, {SIGMA['l2']['2']}, {SIGMA['w1sex']['2']}) AS d
        FROM _pairs p JOIN pyramid pa ON pa.row = p.a JOIN pyramid pb ON pb.row = p.b ORDER BY p.i""").df()["d"].to_numpy()
    con.unregister("_pairs")
    want = np.array([M.distances("blend", store.s42[i], store.s42[j][None, :], sex="2", sigma=SIGMA)[0] for i, j in zip(a, b)])
    assert np.abs(got - want).max() < 1e-6                     # metrics returns float32; the macro is exact float64
    want64 = M.distances_pairs_blend(store.s42[a], store.s42[b], "2", SIGMA)
    assert np.abs(got - want64).max() < 1e-9


# ----------------------------------------------------------------------------- exports, rebuild, diff

def test_export_processed_files(store, tmp_path):
    paths = db.export_processed(store.con, tmp_path)
    assert {"entities", "pyramids", "corpus_keys", "corpus_s42", "corpus_u16", "sigma", "patches", "indicators",
            "coverage", "entity_years"} <= set(paths)
    pyr = pd.read_parquet(paths["pyramids"])
    assert list(pyr.columns) == ["id", "locid", "year", "age_start", "pop_male", "pop_female"]
    assert len(pyr) == len(store.entities) * N_YEARS * N_BINS and pyr["id"].iloc[0] == "AAA"
    assert np.array_equal(np.load(paths["corpus_s42"]), store.s42)
    assert pd.read_parquet(paths["corpus_keys"]).equals(store.keys)
    assert np.array_equal(np.load(paths["corpus_u16"]), store.u16)
    assert json.loads(paths["sigma"].read_text()) == SIGMA
    assert json.loads(paths["patches"].read_text())[0]["id"] == "togo-2026-01-19"
    s42, keys = shapes.build_corpus(pyr, store.entities, out_dir=tmp_path / "again")
    assert np.allclose(s42, store.s42, atol=1e-15) and keys["pop_total"].to_numpy() == pytest.approx(store.keys["pop_total"].to_numpy())


def test_rebuild_deterministic(world, tmp_path):
    a = build_synthetic_db(world, tmp_path / "a", tmp_path / "a.duckdb")
    b = build_synthetic_db(world, tmp_path / "b", tmp_path / "b.duckdb")
    assert a.data_hash == b.data_hash and np.array_equal(a.s42, b.s42) and a.entities == b.entities
    pa_, pb_ = db.export_processed(a.con, tmp_path / "a"), db.export_processed(b.con, tmp_path / "b")
    for k in ("entities", "corpus_s42", "corpus_keys", "pyramids", "indicators", "coverage"):
        assert pa_[k].read_bytes() == pb_[k].read_bytes(), k
    a.con.close()
    diff = db.diff_against(b.con, tmp_path / "a.duckdb")
    assert diff["entities_added"] == diff["entities_removed"] == [] and diff["shares_changed"] == []
    assert diff["coverage"] == {"added": 0, "removed": 0, "changed_last_year": 0}
    b.con.close()


def test_build_meta_and_ingest_evals(store):
    meta = db.build_meta(store.con)
    assert meta["data_hash"] == store.data_hash and meta["revision"] == "wpp2024"
    out = db.ingest_evals(store.con, label_sets={"toy": pd.DataFrame({"entity_id": ["AAA"], "year": [2000], "label": ["x"]})},
                          triplets=pd.DataFrame({"anchor_id": ["AAA"], "anchor_year": [2000], "a_id": ["BBB"], "a_year": [2000],
                                                 "b_id": ["TGO"], "b_year": [2000], "choice": ["a"]}),
                          verdicts={"blend": {"G1": {"value": 0.9, "verdict": "pass"}}, "data_hash": store.data_hash})
    assert out == {"labels": 1, "triplets": 1, "verdicts": 1}


# ----------------------------------------------------------------------------- the real store (slow)

@pytest.fixture(scope="module")
def real():
    if not REAL_DB:
        pytest.skip("explorer.duckdb not built")
    con = db.connect(read_only=True)
    yield con
    con.close()


@pytest.mark.slow
def test_real_counts_and_togo(real):
    n_c, n_a = real.execute("SELECT count(*) FILTER (WHERE type = 'country'), count(*) FILTER (WHERE type = 'aggregate') FROM entity").fetchone()
    assert n_c == 237 and 40 <= n_a <= 44
    assert real.execute("SELECT count(*) FROM pyramid").fetchone()[0] == (n_c + n_a) * N_YEARS
    tgo = real.execute("SELECT total FROM pyramid WHERE entity_id = 'TGO' AND year = 2022").fetchone()[0]
    van = real.execute("SELECT sum(pop_male + pop_female) FROM pop_age5_vanilla WHERE entity_id = 'TGO' AND year = 2022").fetchone()[0]
    assert 8000 < tgo < 8500 and abs(tgo - van) > 100
    assert real.execute("SELECT count(*) FROM source WHERE NOT redistributable").fetchone()[0] >= 1


@pytest.mark.slow
def test_real_patch_identity(real):
    rows = real.execute("""
        WITH d AS (SELECT p.entity_id, p.year, p.age_start, p.pop_male - v.pop_male AS dm, p.pop_female - v.pop_female AS df
                   FROM pop_age5 p JOIN pop_age5_vanilla v USING (entity_id, year, age_start)),
        t AS (SELECT year, age_start, dm, df FROM d WHERE entity_id = 'TGO')
        SELECT d.entity_id, max(greatest(abs(d.dm - t.dm), abs(d.df - t.df))) AS worst
        FROM d JOIN t USING (year, age_start) WHERE d.entity_id LIKE 'agg-%' AND d.entity_id IN
             (SELECT agg_id FROM entity_membership WHERE member_id = 'TGO') GROUP BY 1""").df()
    assert len(rows) >= 7 and (rows["worst"] <= 0.001 * 237).all()
    assert real.execute("""SELECT count(*) FROM pop_age5 p JOIN pop_age5_vanilla v USING (entity_id, year, age_start)
        WHERE (p.pop_male <> v.pop_male OR p.pop_female <> v.pop_female) AND entity_id NOT IN
              (SELECT agg_id FROM entity_membership WHERE member_id = 'TGO') AND entity_id <> 'TGO'""").fetchone()[0] == 0


@pytest.mark.slow
def test_real_entities_pop_2026_match_corpus_and_patch_lists_entities_only(real):
    """The MAJOR integration finding: entities.json used to carry vanilla pop_2026 for TGO and the 7 recomputed
    aggregates. Every entity's pop_2026 must equal the shipped 2026 pyramid total, and the patch record must name
    only aggregates the site ships."""
    rows = real.execute("""SELECT e.id, e.pop_2026, p.total, e.doc->>'pop_2026' AS doc_pop FROM entity e
        JOIN pyramid p ON p.entity_id = e.id AND p.year = 2026""").df()
    assert len(rows) == real.execute("SELECT count(*) FROM entity").fetchone()[0]
    assert (rows["pop_2026"] - rows["total"]).abs().max() < 1e-3
    assert (rows["doc_pop"].astype(float) - rows["total"]).abs().max() < 1e-3
    van = real.execute("SELECT sum(pop_male + pop_female) FROM pop_age5_vanilla WHERE entity_id = 'TGO' AND year = 2026").fetchone()[0]
    assert abs(rows.set_index("id").at["TGO", "pop_2026"] - van) > 100        # patched, not vanilla
    ents = {r[0] for r in real.execute("SELECT locid FROM entity").fetchall()}
    for rec in db.load_patches(real):
        assert set(rec["recomputed_aggregates"]) <= ents and {900, 903, 914, 1834, 902, 941, 1500} <= set(rec["recomputed_aggregates"])
    ey = db.entity_years(real)
    assert "weo-2025-04" not in set().union(*(set(s) for s in ey["sources"] if s is not None))
    dangling = real.execute("""SELECT count(*) FROM entity c WHERE c.type = 'country' AND (
        (c.region_locid IS NOT NULL AND c.region_locid NOT IN (SELECT locid FROM entity)) OR
        (c.subregion_locid IS NOT NULL AND c.subregion_locid NOT IN (SELECT locid FROM entity)) OR
        (c.sdg_region_locid IS NOT NULL AND c.sdg_region_locid NOT IN (SELECT locid FROM entity)))""").fetchone()[0]
    assert dangling == 0


@pytest.mark.slow
def test_real_coverage_1990_example(real):
    if not real.execute("SELECT count(*) FROM indicator_value WHERE indicator_id = 'gdppc_maddison'").fetchone()[0]:
        pytest.skip("Maddison not ingested (make data && make build)")
    n = real.execute("""
        SELECT count(DISTINCT c.entity_id) FROM coverage c JOIN entity e ON e.id = c.entity_id
        JOIN indicator_value iv ON iv.entity_id = c.entity_id AND iv.indicator_id = 'gdppc_maddison' AND iv.year = 1990
        WHERE e.type = 'country' AND c.series = 'pyramid' AND c.first_year <= 1990""").fetchone()[0]
    assert 140 <= n <= 169


@pytest.mark.slow
def test_real_blend_macro_1000_pairs(real):
    from pyramid_explorer import metrics as M

    sigma = db.load_sigma(real)
    if "l2" not in sigma or "w1sex" not in sigma:
        pytest.skip("sigma not written yet")
    s42, keys = db.load_corpus(real)
    rng = np.random.default_rng(0)
    a, b = rng.integers(0, len(keys), 1000), rng.integers(0, len(keys), 1000)
    real.register("_pairs", pd.DataFrame({"a": a, "b": b, "i": np.arange(1000)}))
    got = real.execute(f"""SELECT blend_d(pa.s42, pa.cdf42, pb.s42, pb.cdf42, {sigma['l2']['2']}, {sigma['w1sex']['2']}) AS d
        FROM _pairs p JOIN pyramid pa ON pa.row = p.a JOIN pyramid pb ON pb.row = p.b ORDER BY p.i""").df()["d"].to_numpy()
    real.unregister("_pairs")
    want = M.distances_pairs_blend(s42[a], s42[b], "2", sigma)
    assert np.abs(got - want).max() < 1e-9
