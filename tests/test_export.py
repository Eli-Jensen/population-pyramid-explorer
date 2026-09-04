"""export.py — hashed shards, meta/entities JSON, NOTICE, build report, budgets (synthetic corpus)."""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer import bands as B
from pyramid_explorer import export as E
from pyramid_explorer.delta import decode_blob
from pyramid_explorer.paths import N_YEARS, YEARS
from pyramid_explorer.quantise import shares_to_u16

IDS = ["AAA", "BBB", "CCC", "DDD", "agg-900"]


def _corpus(seed: int = 0):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, N_YEARS)[:, None]
    X = np.concatenate([rng.gamma(2, size=42) * (1 - t) + rng.gamma(2, size=42) * t for _ in IDS])
    X /= X.sum(1, keepdims=True)
    keys = pd.DataFrame({"row": np.arange(len(IDS) * N_YEARS), "id": np.repeat(IDS, N_YEARS), "locid": -1,
                         "year": np.tile(YEARS, len(IDS)), "type": ["country"] * 4 * N_YEARS + ["aggregate"] * N_YEARS,
                         "pop_total": np.repeat([1000.0, 2000.0, 3000.0, 4000.0, 10000.0], N_YEARS)})
    entities = [{"id": i, "type": "aggregate" if i.startswith("agg") else "country", "name": f"Nämé {i}",
                 "axis_pct": 10 if i != "DDD" else 17} for i in IDS]
    return X, keys, entities


def _l2(X):
    return lambda metric, q, rows, sex: np.linalg.norm(X[rows] - X[q], axis=1)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    X, keys, entities = _corpus()
    u16 = shares_to_u16(X)
    bands = B.build_bands(X, keys, entities, {}, ["blend", "trend@10"], n_pairs=20, dist_fn=_l2(X))
    root = tmp_path_factory.mktemp("web")
    # a stale file that the wipe must remove
    stale = root / "public" / "data" / "wpp2024" / "years.deadbeef" / "1950.u16"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    emb = {"toy": np.random.default_rng(1).normal(size=(len(keys), 64)).astype(np.float32)}
    patches = [{"id": "togo-2026-01-19", "locids": [768], "recomputed_aggregates": [900]}]
    sigma = {"l2": {"2": 0.05, "1": 0.07}}
    report = E.write_web_data(entities=entities, keys=keys, s42=X, u16=u16, bands=bands, sigma=sigma, patches=patches,
                              emb=emb, out_root=root, report_path=root / "build-report.json")
    return {"X": X, "keys": keys, "entities": entities, "u16": u16, "bands": bands, "root": root, "report": report,
            "emb": emb, "meta": json.loads((root / "src/data/meta.json").read_text())}


def test_directory_wiped_and_hashed_names(built):
    data = built["root"] / "public/data/wpp2024"
    names = sorted(p.name for p in data.iterdir())
    assert not (data / "years.deadbeef").exists()
    assert [n for n in names if n.startswith("years.")] == [built["meta"]["files"]["years"].split("/")[-1]]
    for logical in ("shares_d16z", "shares_u16", "totals", "bands", "bands_default"):
        path = built["meta"]["files"][logical]
        assert re.fullmatch(r"data/wpp2024/[a-z_]+\.[0-9a-f]{8}\.(d16z|u16|f32|bin)", path), path
        assert (built["root"] / "public" / path).exists()
    assert (data / "NOTICE").exists()


def test_year_and_entity_shards_decode(built):
    root, meta, u16, keys = built["root"], built["meta"], built["u16"], built["keys"]
    n_ent = len(IDS)
    year = 1987
    raw = (root / "public" / meta["files"]["years"] / f"{year}.u16").read_bytes()
    assert len(raw) == n_ent * 84 + n_ent * 4
    u = np.frombuffer(raw[: n_ent * 84], dtype="<u2").reshape(n_ent, 42)
    t = np.frombuffer(raw[n_ent * 84:], dtype="<f4")
    rows = (year - 1950) + N_YEARS * np.arange(n_ent)
    assert np.array_equal(u, u16[rows]) and np.allclose(t, keys.pop_total.to_numpy()[rows])
    raw = (root / "public" / meta["files"]["pyramids"] / "CCC.u16").read_bytes()
    assert len(raw) == N_YEARS * 84 + N_YEARS * 4
    u = np.frombuffer(raw[: N_YEARS * 84], dtype="<u2").reshape(N_YEARS, 42)
    assert np.array_equal(u, u16[2 * N_YEARS:3 * N_YEARS])
    assert np.frombuffer(raw[N_YEARS * 84:], dtype="<f4")[0] == np.float32(3000.0)


def test_blob_totals_bands_emb_files(built):
    root, meta, u16 = built["root"], built["meta"], built["u16"]
    pub = root / "public"
    blob = (pub / meta["files"]["shares_d16z"]).read_bytes()
    assert blob[:2] == b"\x1f\x8b" and np.array_equal(decode_blob(blob, len(u16)), u16)
    flat = np.frombuffer((pub / meta["files"]["shares_u16"]).read_bytes(), dtype="<u2").reshape(-1, 42)
    assert np.array_equal(flat, u16)
    totals = np.frombuffer((pub / meta["files"]["totals"]).read_bytes(), dtype="<f4")
    assert np.allclose(totals, built["keys"].pop_total.to_numpy())
    bands = B.deserialize_bands((pub / meta["files"]["bands"]).read_bytes())
    assert "same/blend/2/2026" in bands and "best/trend@10/1/obs/1990" in bands
    default = B.deserialize_bands((pub / meta["files"]["bands_default"]).read_bytes())
    assert list(default) == [f"same/blend/2/{y}" for y in YEARS]
    assert np.allclose(default["same/blend/2/2026"], bands["same/blend/2/2026"])
    Z = np.frombuffer((pub / meta["files"]["emb"]["toy"]).read_bytes(), dtype="<f2").reshape(-1, 64)
    assert np.allclose(Z, built["emb"]["toy"], atol=1e-2)


def test_meta_and_entities_json(built):
    meta, root = built["meta"], built["root"]
    for k in ("revision", "patches", "built", "last_observed_year", "n_entities", "n_countries", "n_rows",
              "files", "sigma", "kernel", "budgets", "sizes", "attribution"):
        assert k in meta, k
    assert meta["n_entities"] == 5 and meta["n_countries"] == 4 and meta["n_rows"] == 5 * N_YEARS
    assert meta["kernel"] == [0.054, 0.242, 0.399, 0.242, 0.054] and meta["last_observed_year"] == 2023
    assert meta["patches"][0]["id"] == "togo-2026-01-19"
    assert any("United Nations" in a for a in meta["attribution"]) and any("togo" in a for a in meta["attribution"])
    ents = json.loads((root / "src/data/entities.json").read_text())
    assert [e["id"] for e in ents] == IDS and ents[0]["name"] == "Nämé AAA"
    s = meta["sizes"]
    assert s["entity_shard_max"] == N_YEARS * 88 and s["year_shard_max"] == 5 * 88
    assert s["first_paint"] == s["entities_gz"] + s["meta_gz"] + s["entity_shard_max"] + s["year_shard_max"] + s["bands_default"]
    assert set(s["layouts"]) == {"raw_gz", "delta_gz", "zigzag_gz", "delta_transposed_gz"}
    assert s["dir_total_with_emb"] - s["dir_total"] == s["emb"]["toy"] == 5 * N_YEARS * 64 * 2
    assert s["meta_gz"] > 0 and s["dir_total"] > s["shares_u16"] + s["shares_d16z"]


def test_notice_and_report(built):
    notice = (built["root"] / "public/data/wpp2024/NOTICE").read_text()
    assert "CC BY 3.0 IGO" in notice and "togo-2026-01-19" in notice
    r = built["report"]
    assert r == json.loads((built["root"] / "build-report.json").read_text())
    assert r["checks"] == {"u16_row_sums_65535": True, "d16z_round_trip": True, "budgets": []}
    assert r["axis_distribution"] == {"10": 4, "17": 1}
    assert r["sizes"]["bands_tables"]["same/blend"]["tables"] == 2 * N_YEARS  # both sexes


def test_budget_violation_raises_and_reports(tmp_path):
    X, keys, entities = _corpus()
    u16 = shares_to_u16(X)
    with pytest.raises(E.BudgetError, match="year_shard"):
        E.write_web_data(entities=entities, keys=keys, s42=X, u16=u16, bands=None, sigma={}, patches=[],
                         out_root=tmp_path, report_path=tmp_path / "r.json", budgets={"year_shard": 100})
    assert json.loads((tmp_path / "r.json").read_text())["checks"]["budgets"]


def test_no_bands_no_emb_still_writes_deterministic_files(tmp_path):
    X, keys, entities = _corpus()
    u16 = shares_to_u16(X)
    kw = {"entities": entities, "keys": keys, "s42": X, "u16": u16, "bands": None, "sigma": {}, "patches": [],
          "out_root": tmp_path, "report_path": tmp_path / "r.json"}
    a = E.write_web_data(**kw)["files"]
    b = E.write_web_data(**kw)["files"]
    assert a == b and a["emb"] == {}
    assert B.deserialize_bands((tmp_path / "public" / a["bands"]).read_bytes()) == {}


def test_input_validation(tmp_path):
    X, keys, entities = _corpus()
    u16 = shares_to_u16(X)
    bad = keys.copy()
    bad.loc[0, "id"] = "ZZZ"
    with pytest.raises(ValueError, match="order"):
        E.write_web_data(entities=entities, keys=bad, s42=X, u16=u16, bands=None, sigma={}, patches=[], out_root=tmp_path)
    with pytest.raises(ValueError, match="65535"):
        E.write_web_data(entities=entities, keys=keys, s42=X, u16=u16 + 1, bands=None, sigma={}, patches=[],
                         out_root=tmp_path)
    with pytest.raises(ValueError, match="emb"):
        E.write_web_data(entities=entities, keys=keys, s42=X, u16=u16, bands=None, sigma={}, patches=[],
                         out_root=tmp_path, emb={"m": np.zeros((3, 64))})


def test_attribution_from_sources_yaml(tmp_path):
    y = tmp_path / "sources.yaml"
    y.write_text("sources:\n  - id: wpp\n    redistributable: true\n    attribution: 'UN WPP text'\n"
                 "  - id: weo\n    redistributable: false\n    attribution: 'IMF must not appear'\n")
    lines = E.attribution_lines([], sources_yaml=y)
    assert lines == ["UN WPP text"]
    assert E.attribution_lines([], sources_yaml=tmp_path / "missing.yaml") == [E.WPP_ATTRIBUTION]


def test_sha8_dir_is_order_independent():
    assert E.sha8_dir({"b": b"2", "a": b"1"}) == E.sha8_dir({"a": b"1", "b": b"2"}) == E.sha8(b"12")


def test_attribution_family_filter(tmp_path):
    y = tmp_path / "sources.yaml"
    y.write_text("sources:\n  a:\n    family: wpp\n    redistributable: true\n    attribution: 'UN'\n"
                 "  b:\n    family: pwt\n    redistributable: true\n    attribution: 'PWT'\n")
    assert E.attribution_lines([], sources_yaml=y, families={"wpp"}) == ["UN"]
    assert E.attribution_lines([], sources_yaml=y) == ["UN", "PWT"]


# ------------------------------------------------------------------------------- build_data.py via a test double
def _load_build_script():
    import importlib.util

    from pyramid_explorer.paths import REPO_ROOT

    spec = importlib.util.spec_from_file_location("build_data", REPO_ROOT / "scripts" / "build_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeDB:
    """Records the AMENDMENTS §A call order; serves the synthetic corpus as db.load_corpus would."""

    def __init__(self, s42, keys):
        self.calls, self.s42, self.keys = [], s42, keys
        self.u16 = self.sigma = self.meta = None

    def __getattr__(self, name):  # every other db.* call is recorded and returns None
        def fn(*a, **k):
            self.calls.append(name)
        return fn

    def connect(self, path=None, *, read_only=False, rebuild=False):
        self.calls.append("connect")
        assert rebuild
        return self

    def close(self):
        self.calls.append("close")

    def load_corpus(self, con):
        self.calls.append("load_corpus")
        return self.s42, self.keys

    def write_u16(self, con, u16):
        self.calls.append("write_u16")
        self.u16 = u16

    def write_build_meta(self, con, **kv):
        self.calls.append("write_build_meta")
        self.meta = kv

    def write_sigma(self, con, sigma):
        self.calls.append("write_sigma")
        self.sigma = sigma

    def ingest_indicators(self, con, family, source_id, long_df):
        self.calls.append(f"ingest_indicators:{family}")
        return {"rows": len(long_df), "orphans": 0}

    def coverage(self, con):
        self.calls.append("coverage")
        return pd.DataFrame({"entity_id": ["AAA"], "series": ["pyramid"], "source_id": ["wpp2024"]})

    def diff_against(self, con, old):
        self.calls.append("diff_against")
        return {"entities_added": [], "entities_removed": []}


@pytest.fixture
def doubles(monkeypatch, tmp_path):
    import sys
    import types

    pytest.importorskip("pyramid_explorer.metrics")
    X, keys, entities = _corpus()
    db = _FakeDB(X, keys)
    raw = pd.DataFrame({"locid": [1], "iso3": ["AAA"]})
    locations = pd.DataFrame({"LocID": [1]})
    update_csv = tmp_path / "update.csv"
    update_csv.write_text("x")
    patch = {"id": "togo-2026-01-19", "locids": [768], "recomputed_aggregates": [900]}
    ind = pd.DataFrame({"locid": [1], "year": [2000], "is_forecast": [False]})
    wpp = types.SimpleNamespace(load_locations=lambda: locations, load_raw_population=lambda patched=True: raw,
                                togo_update_csv=lambda: update_csv, load_indicators=lambda: ind,
                                load_indicators_update=lambda: ind)
    seen: dict = {}
    patched_frame = raw.copy()                       # a distinct object, so the test can tell which frame entities saw

    def build_entities(raw_, loc_):
        seen["frame"] = raw_
        return entities

    ent_mod = types.SimpleNamespace(build_entities=build_entities)
    patches_mod = types.SimpleNamespace(apply_togo_patch=lambda raw_, csv_, loc_: (patched_frame, patch))
    maddison = types.SimpleNamespace(load_long=lambda: pd.DataFrame({"code": ["AAA"], "year": [2000]}))

    def missing():
        raise FileNotFoundError("pwt110.xlsx")

    pwt = types.SimpleNamespace(load_long=missing, load_income_long=missing)
    for name, mod in {"pyramid_explorer.db": db, "pyramid_explorer.data.wpp": wpp, "pyramid_explorer.entities": ent_mod,
                      "pyramid_explorer.patches": patches_mod, "pyramid_explorer.data.maddison": maddison,
                      "pyramid_explorer.data.pwt": pwt, "pyramid_explorer.data.wdi": pwt,
                      "pyramid_explorer.data.imf": pwt}.items():
        monkeypatch.setitem(sys.modules, name, mod)
    return {"db": db, "X": X, "keys": keys, "entities": entities, "tmp": tmp_path, "patch": patch, "seen": seen,
            "raw": raw, "patched_frame": patched_frame}


def test_build_data_end_to_end_with_double(doubles, capsys):
    bd = _load_build_script()
    d = doubles
    pca = d["tmp"] / "toy.pca64.npy"
    np.save(pca, np.random.default_rng(2).normal(size=(len(d["keys"]), 64)).astype(np.float32))
    (d["tmp"] / "toy.meta.json").write_text("{}")
    (d["tmp"] / "old.duckdb").write_bytes(b"")
    report = bd.main(["--emb", str(pca), "--no-full-emb", "--diff-against", str(d["tmp"] / "old.duckdb"), "--bands-pairs", "20"],
                     out_root=d["tmp"] / "web", report_path=d["tmp"] / "report.json")
    db = d["db"]
    order = [c for c in db.calls if c not in ("close", "git_rev")]
    expected = ["connect", "ingest_sources", "ingest_locations", "insert_entities", "ingest_sovereignty", "ingest_pop_age5",
                "ingest_wpp_indicators", "ingest_indicators:maddison", "refresh_derived", "load_corpus", "write_u16",
                "write_build_meta", "write_sigma", "ingest_embeddings", "export_processed", "coverage", "diff_against"]
    assert order == expected  # pwt/wdi/oghist/weo skipped with a warning (raw file absent)
    assert d["seen"]["frame"] is d["patched_frame"]     # entities are built from the PATCHED frame (CONTRACT §A)
    assert np.all(db.u16.sum(1, dtype=np.int64) == 65535) and db.meta["data_hash"] == report["data_hash"]
    assert set(report["blend_w1_share"]) == {"2", "1"} and "all" in report["blend_w1_share"]["2"]
    assert db.meta["schema_version"] == "1" and db.meta["patches"] == '["togo-2026-01-19"]' 
    assert "trend@10" in db.sigma and report["sigma"] == db.sigma
    assert report["patches"] == [d["patch"]] and report["econ"] == {"maddison": {"rows": 1, "orphans": 0}}
    assert report["coverage"] == {"pyramid/wpp2024": 1} and "diff" in report
    meta = json.loads((d["tmp"] / "web/src/data/meta.json").read_text())
    assert "visual:toy" in meta["sizes"]["bands_tables"].get("same/visual:toy", {}) or "same/visual:toy" in meta["sizes"]["bands_tables"]
    assert set(meta["files"]["emb"]) == {"toy"}
    assert {"same/blend", "same/trend@20", "best/w1bal", "cross/feat"} <= set(meta["sizes"]["bands_tables"])
    assert "same/clr" not in meta["sizes"]["bands_tables"]  # evaluation-only metric gets no bands
    if "verdicts" in meta:                                    # the repo's verdicts.json is for the real corpus ⇒ stale here
        assert meta["verdicts"]["stale"] and meta["verdicts"]["exposed_visual"] is None
        assert all(v["verdict"] == "lab" for v in meta["verdicts"]["metrics"].values())
    out = capsys.readouterr().out
    assert "first paint" in out and "delta-transposed gz" in out and "budgets: OK" in out
    assert json.loads((d["tmp"] / "report.json").read_text())["n_entities"] == 5


def test_build_data_no_patches_no_gdp(doubles):
    bd = _load_build_script()
    d = doubles
    report = bd.build(bd.parse_args(["--no-patches", "--no-gdp", "--bands-pairs", "20"]),
                      out_root=d["tmp"] / "web", report_path=d["tmp"] / "report.json")
    assert report["patches"] == [] and report["econ"] == {}
    assert d["seen"]["frame"] is d["raw"]                # vanilla build: entities from the raw frame
    assert not any(c.startswith("ingest_indicators") for c in d["db"].calls)
    assert report["files"]["emb"] == {}


def test_load_verdicts_caps_absent_bands_and_exposed_visual(tmp_path):
    """meta.verdicts: a metric with no bands in this build is capped at lab; visual verdicts and exposed_visual
    survive only for models passed via --emb with a matching meta hash; a stale file downgrades everything."""
    import hashlib

    bd = _load_build_script()
    meta_toy = tmp_path / "toy.meta.json"
    meta_toy.write_text('{"model": "toy"}')
    sha = hashlib.sha256(meta_toy.read_bytes()).hexdigest()
    v = {"blend": {"verdict": "default"}, "clr": {"verdict": "advanced"}, "l2": {"verdict": "advanced"},
         "trend": {"verdict": "menu", "provisional": True, "scope": "trend-mode"},
         "visual:toy": {"verdict": "menu", "provisional": True}, "visual:other": {"verdict": "rejected"},
         "exposed_visual": {"model": "toy", "metric": "visual:toy", "C1_obs": 0.55, "alternates": ["other"]},
         "data_hash": "abc", "emb_meta_hash": {"toy": sha, "other": "deadbeef"}, "_meta": {}}
    p = tmp_path / "verdicts.json"
    p.write_text(json.dumps(v))
    emb = {"toy": {"meta": meta_toy}}
    bands = ["blend", "l2", "trend@10", "visual:toy"]
    out = bd.load_verdicts(emb, "abc", bands, path=p)
    m = out["metrics"]
    assert not out["stale"] and m["blend"]["verdict"] == "default" and m["l2"]["verdict"] == "advanced"
    assert m["clr"]["verdict"] == "lab"                       # evaluation-only: no bands ⇒ never above lab
    assert m["trend"] == {"verdict": "menu", "provisional": True, "scope": "trend-mode"}   # trend@L bands cover it
    assert m["visual:toy"]["verdict"] == "menu" and m["visual:other"]["verdict"] == "lab"
    assert out["exposed_visual"] == {"model": "toy", "metric": "visual:toy", "C1_obs": 0.55, "alternates": []}
    for metric, r in m.items():
        if r["verdict"] not in ("lab", "rejected") and metric not in ("trend", "path"):
            assert metric in bands, metric
    stale = bd.load_verdicts(emb, "zzz", bands, path=p)
    assert stale["stale"] and stale["exposed_visual"] is None
    assert all(r["verdict"] == "lab" for r in stale["metrics"].values())
    unshipped = bd.load_verdicts({}, "abc", bands, path=p)    # visual verdicts need --emb
    assert unshipped["metrics"]["visual:toy"]["verdict"] == "lab" and unshipped["exposed_visual"] is None
    assert bd.load_verdicts(emb, "abc", bands, path=tmp_path / "missing.json") is None


def test_build_data_names_owner_when_module_missing(monkeypatch, tmp_path):
    import sys

    bd = _load_build_script()
    monkeypatch.setitem(sys.modules, "pyramid_explorer.db", None)  # import raises ImportError
    with pytest.raises(SystemExit, match="owner A1"):
        bd.build(bd.parse_args([]))
    pca = tmp_path / "m.pca64.npy"
    np.save(pca, np.zeros((3, 64), np.float32))
    with pytest.raises(SystemExit, match="owner C"):  # --emb without its meta.json
        bd.load_embeddings([pca])
