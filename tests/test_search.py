"""search.py — mask semantics on a synthetic corpus; twins/opposites/trend/time-shift/isolation on the
provisional corpus (PLAN §4.2 / §5 / §6 and the trend prototype in the build plan §4)."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.metrics import distances, fit_sigma, lagged
from pyramid_explorer.search import (DIV_PRESETS, Query, best_year_per_entity, candidate_mask, different, isolation,
                                     load_inputs, row_of, similar)
from pyramid_explorer.paths import DATA_PROCESSED
from tests.test_metrics import synth_corpus


@pytest.fixture(scope="module")
def synth():
    X, keys, ents = synth_corpus(n_ent=6)
    return X, keys, ents, fit_sigma(X, keys, ents, n_pairs=500)


@pytest.fixture(scope="module")
def corpus():
    if not (DATA_PROCESSED / "corpus_s42.npy").exists():
        pytest.skip("provisional corpus absent")
    X, keys, ents = load_inputs()
    return X, keys, ents, fit_sigma(X, keys, ents)


def ids(results) -> list[str]:
    return [r.id for r in results]


# --------------------------------------------------------------------------------------------- mask
def test_mask_year_modes_era_scope_minpop_own(synth):
    X, keys, ents, _ = synth
    yr, tp, pop, eid = (keys[c].to_numpy() for c in ("year", "type", "pop_total", "id"))
    q = Query("E00", 2026)
    m = candidate_mask(keys, ents, q)
    assert (yr[m] == 2026).all() and (tp[m] == "country").all() and not (eid[m] == "E00").any() and m.sum() == 4
    assert candidate_mask(keys, ents, Query("E00", 2026, scope="all")).sum() == 5
    assert candidate_mask(keys, ents, Query("E00", 2026, minpop=1150)).sum() == 3   # pops 1000+100e; E00 excluded anyway
    assert (yr[candidate_mask(keys, ents, Query("E00", 2000, mode="today"))] == 2026).all()
    near = candidate_mask(keys, ents, Query("E00", 2000, mode="near", n=3))
    assert set(yr[near]) == set(range(1997, 2004))
    rng_ = candidate_mask(keys, ents, Query("E00", 2000, mode="range", from_year=1960, to_year=1962))
    assert set(yr[rng_]) == {1960, 1961, 1962}
    # era obs: ≤ max(last_observed, current) for an observed query year; projections allowed when the query is one
    assert yr[candidate_mask(keys, ents, Query("E00", 2000, mode="any"))].max() == 2026
    assert yr[candidate_mask(keys, ents, Query("E00", 2000, mode="any", era="all"))].max() == 2100
    assert yr[candidate_mask(keys, ents, Query("E00", 2050, mode="any"))].max() == 2100
    assert candidate_mask(keys, ents, Query("E00", 2050, mode="same")).sum() == 4
    assert yr[candidate_mask(keys, ents, Query("E00", 2000, mode="any", current_year=2030))].max() == 2030
    assert yr[candidate_mask(keys, ents, Query("E00", 2000, mode="range", from_year=2040, to_year=2050))].size == 0
    # trend needs year − L ≥ 1950
    t = candidate_mask(keys, ents, Query("E00", 2000, mode="any", trend="motion", L=20))
    assert yr[t].min() == 1970
    with pytest.raises(ValueError):
        candidate_mask(keys, ents, Query("E00", 2000, mode="bogus"))


def test_similar_dedupes_and_sorts(synth):
    X, keys, ents, s = synth
    res = similar(X, keys, ents, Query("E00", 2000, mode="any", era="all", k=10), s)
    assert len(res) == 4 and len({r.id for r in res}) == 4 and "E00" not in ids(res)
    assert [r.d for r in res] == sorted(r.d for r in res) and [r.rank_raw for r in res] == [1, 2, 3, 4]
    assert all(r.dy == r.year - 2000 and keys.year[r.row] == r.year for r in res)


def test_different_div0_is_plain_farthest_k(synth):
    X, keys, ents, s = synth
    q = Query("E00", 2000, mode="any", era="all", k=3, div=0.0)
    res = different(X, keys, ents, q, s)
    m = candidate_mask(keys, ents, q)
    d = distances("blend", X[row_of(keys, "E00", 2000)], X, sigma=s)
    t = pd.DataFrame({"id": keys.id[m], "d": d[m]}).sort_values("d", ascending=False).drop_duplicates("id")
    assert ids(res) == list(t.id[:3]) and [r.rank_raw for r in res] == [1, 2, 3]
    assert [r.d for r in res] == sorted((r.d for r in res), reverse=True)


def test_time_shift_boundary_and_trend_guard(synth):
    X, keys, ents, s = synth
    ts = best_year_per_entity(X, keys, ents, Query("E00", 2000, era="all"), s)
    assert list(ts.columns) == ["id", "best_year", "d", "dy", "boundary_hit"] and len(ts) == 4
    assert ts.d.is_monotonic_increasing and ts.boundary_hit.dtype == bool
    assert (ts.boundary_hit == ts.best_year.isin([1950, 2100])).all()
    with pytest.raises(ValueError):
        similar(X, keys, ents, Query("E00", 1955, trend="motion", L=10), s)
    with pytest.raises(ValueError):
        similar(X, keys, ents, Query("E00", 2000, trend="path", L=7), s)


# --------------------------------------------------------------------------------------------- provisional corpus
@pytest.mark.parametrize("qid, year, expect", [
    ("JPN", 2026, {"ITA", "PRT", "GRC"}), ("NER", 2026, {"MLI", "TCD", "SOM"}), ("QAT", 2026, {"ARE", "BHR"}),
    ("USA", 2026, {"NZL", "AUS"}), ("KOR", 2050, {"TWN"}),
])
def test_same_year_twins(corpus, qid, year, expect):
    X, keys, ents, s = corpus
    got = ids(similar(X, keys, ents, Query(qid, year), s))
    assert expect <= set(got), got
    assert len(got) == 5 and qid not in got


def test_twins_hold_under_l2(corpus):
    X, keys, ents, s = corpus
    assert {"ITA", "PRT", "GRC"} <= set(ids(similar(X, keys, ents, Query("JPN", 2026, metric="l2"), s)))
    assert "TWN" in ids(similar(X, keys, ents, Query("KOR", 2050, metric="l2", sex="1"), s))


def test_japan_opposites_sex_aware_vs_total_only(corpus):
    X, keys, ents, s = corpus
    sahel = {"NER", "MLI", "TCD", "SOM", "CAF", "COD", "UGA", "BDI", "SSD", "AGO", "MOZ", "ZMB", "TZA", "MWI", "ERI", "LSO", "MYT"}
    for div in DIV_PRESETS.values():
        got = ids(different(X, keys, ents, Query("JPN", 2026, div=div), s))
        assert {"QAT", "ARE"} & set(got), (div, got)
    got1 = ids(different(X, keys, ents, Query("JPN", 2026, sex="1", div=0.0), s))
    assert not {"QAT", "ARE"} & set(got1) and len(sahel & set(got1)) >= 4, got1
    got1d = different(X, keys, ents, Query("JPN", 2026, sex="1", div=2.0), s)
    assert len(set(ids(got1d))) == 5 and all(r.rank_raw >= i + 1 for i, r in enumerate(got1d))


def test_different_div0_equals_farthest_k_on_corpus(corpus):
    X, keys, ents, s = corpus
    for mode, kw in (("same", {}), ("any", {"era": "all"})):
        q = Query("JPN", 2026, mode=mode, k=5, div=0.0, **kw)
        res = different(X, keys, ents, q, s)
        m = candidate_mask(keys, ents, q)
        d = distances("blend", X[row_of(keys, "JPN", 2026)], X, sigma=s)
        t = pd.DataFrame({"id": keys.id[m], "d": d[m]}).sort_values("d", ascending=False).drop_duplicates("id")
        assert ids(res) == list(t.id[:5]) and [r.rank_raw for r in res] == [1, 2, 3, 4, 5]
        assert len({r.id for r in res}) == 5


def test_div_presets_are_distinguishable(corpus):
    """PLAN §5 presets strict/balanced/spread must give different lists: balanced keeps most of the strict list
    (Jaccard ≈ ⅔) while spread rewrites it (≈ ⅓); β = 2 vs 4 collapsed, which is why spread is 2, not 4."""
    X, keys, ents, s = corpus
    assert Query("JPN", 2026).div == DIV_PRESETS["balanced"] and list(DIV_PRESETS) == ["strict", "balanced", "spread"]
    assert DIV_PRESETS["strict"] == 0.0 < DIV_PRESETS["balanced"] < DIV_PRESETS["spread"]
    pool = keys[(keys.year == 2026) & (keys.type == "country") & (keys.pop_total >= 100)]
    anchors = pool.sample(60, random_state=0)["id"].tolist()
    sets = {name: [{r.id for r in different(X, keys, ents, Query(a, 2026, div=b), s)} for a in anchors]
            for name, b in DIV_PRESETS.items()}
    jac = lambda x, y: len(x & y) / len(x | y)
    j_bal = np.mean([jac(b, st) for b, st in zip(sets["balanced"], sets["strict"])])
    j_spr = np.mean([jac(sp, st) for sp, st in zip(sets["spread"], sets["strict"])])
    differ = np.mean([b != sp for b, sp in zip(sets["balanced"], sets["spread"])])
    print(f"balanced vs strict Jaccard {j_bal:.2f}; spread vs strict {j_spr:.2f}; balanced≠spread on {differ:.2f}")
    assert 0.5 <= j_bal <= 0.8 and j_spr < j_bal - 0.15 and differ >= 0.5
    bal = different(X, keys, ents, Query("JPN", 2026), s)                       # the default keeps the true farthest
    assert {"CAF", "QAT", "TCD", "NER"} <= set(ids(bal)) and all(r.rank_raw <= 30 for r in bal)


def test_trend_prototypes(corpus):
    X, keys, ents, s = corpus
    chn = ids(similar(X, keys, ents, Query("CHN", 1990, mode="range", from_year=2026, to_year=2026, trend="motion", L=10, minpop=1000), s))
    assert {"ETH", "BGD"} <= set(chn), chn
    assert chn == ids(similar(X, keys, ents, Query("CHN", 1990, mode="today", trend="motion", L=10, minpop=1000), s))
    jpn = ids(similar(X, keys, ents, Query("JPN", 2026, trend="motion", L=10, minpop=1000), s))
    assert {"CZE", "PRT"} & set(jpn), jpn
    path = similar(X, keys, ents, Query("CHN", 1990, mode="today", trend="path", L=10, minpop=1000), s)
    assert len(path) == 5 and all(r.year == 2026 for r in path) and set(ids(path)) != set(chn)
    opp = different(X, keys, ents, Query("JPN", 2026, trend="motion", L=10, minpop=1000), s)
    assert len(opp) == 5 and len(set(ids(opp))) == 5


def test_trend_continuity_adjacent_windows(corpus):
    """Adjacent 10-y windows of the same country are each other's nearest under trend@10 (self excluded)."""
    X, keys, ents, s = corpus
    Xl = lagged(X, 10)
    cand = keys[(keys.year.between(1961, 2022)) & (keys.pop_total >= 100)]
    sample = cand.sample(100, random_state=0)
    ok = 0
    for r in sample.itertuples():
        d = distances("trend", X[r.row], X, L=10, X_prev=Xl, q_prev=Xl[r.row], sigma=s)
        d[r.row] = np.inf
        nn = int(np.nanargmin(d))
        ok += keys.id[nn] == r.id and abs(int(keys.year[nn]) - r.year) == 1
    frac = ok / len(sample)
    print(f"trend@10 continuity (sample of {len(sample)}): {frac:.3f}")
    assert frac >= 0.9


@pytest.mark.parametrize("metric", ["blend", "l2"])
def test_temporal_continuity(corpus, metric):
    """A country's nearest row (self excluded, whole corpus) is one of its adjacent years."""
    X, keys, ents, s = corpus
    cand = keys[(keys.year.between(1951, 2022)) & (keys.pop_total >= 100) & (keys.type == "country")]
    sample = cand.sample(300, random_state=0)
    ok = 0
    for r in sample.itertuples():
        d = distances(metric, X[r.row], X, sigma=s)
        d[r.row] = np.inf
        nn = int(np.argmin(d))
        ok += keys.id[nn] == r.id and abs(int(keys.year[nn]) - r.year) == 1
    frac = ok / len(sample)
    print(f"{metric} temporal continuity (sample of {len(sample)}, observed span): {frac:.3f}")
    assert frac >= 0.95


def test_time_shift_table_provisional(corpus):
    X, keys, ents, s = corpus
    ts = best_year_per_entity(X, keys, ents, Query("JPN", 2026, era="all"), s).set_index("id")
    assert ts.loc["NGA", "boundary_hit"] and ts.loc["NGA", "best_year"] == 2100
    assert not ts.loc["DEU", "boundary_hit"] and 2030 <= ts.loc["DEU", "best_year"] <= 2050
    assert 2030 <= ts.loc["KOR", "best_year"] <= 2045
    kor = best_year_per_entity(X, keys, ents, Query("KOR", 2050, era="all"), s).set_index("id")
    assert 2040 <= kor.loc["JPN", "best_year"] <= 2060                       # PLAN §4.6 regression window
    obs = best_year_per_entity(X, keys, ents, Query("KOR", 2026), s).set_index("id")
    assert 2000 <= obs.loc["JPN", "best_year"] <= 2010 and obs.best_year.max() <= 2026


def test_isolation_gulf_and_microstates(corpus):
    X, keys, ents, s = corpus
    iso = isolation(X, keys, ents, 2024, "blend", s)
    assert {"QAT", "ARE", "BHR", "KWT"} <= set(iso.id[:10]) and iso.id[0] == "QAT"
    assert iso.isolation.is_monotonic_decreasing and "MCO" not in set(iso.id)
    free = isolation(X, keys, ents, 2024, "blend", s, minpop=0)
    assert {"MCO", "VAT"} <= set(free.id[:10])


def test_query_timing(corpus):
    X, keys, ents, s = corpus
    q = Query("JPN", 2026, mode="any", era="all")
    similar(X, keys, ents, q, s)
    t = time.perf_counter(); similar(X, keys, ents, q, s); t1 = time.perf_counter() - t
    t = time.perf_counter(); different(X, keys, ents, q, s); t2 = time.perf_counter() - t
    print(f"similar any-year: {1000*t1:.1f} ms; different (MMR): {1000*t2:.1f} ms")
    assert t1 < 1.0 and t2 < 2.0


# --------------------------------------------------------------------------------------------- CLI
def test_query_cli_smoke(corpus, capsys, tmp_path):
    """scripts/query.py end to end: twins / opposites / time-shift sections, a trend run and a visual run."""
    import importlib.util
    from pyramid_explorer.paths import REPO_ROOT

    spec = importlib.util.spec_from_file_location("query_cli", REPO_ROOT / "scripts" / "query.py")
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    cli.main(["JPN", "2026", "--k", "3"])
    out = capsys.readouterr().out
    assert "TWINS (k=3)" in out and "OPPOSITES" in out and "TIME-SHIFT" in out
    assert "ITA 2026" in out or "Italy 2026" in out          # provisional ids vs real short names
    assert "true best may lie beyond" not in out.split("TIME-SHIFT")[1].split("\n")[1]  # same-year best is not "censored"
    cli.main(["CHN", "1990", "--mode", "today", "--trend", "motion", "--L", "10", "--minpop", "1000", "--k", "3"])
    out = capsys.readouterr().out
    assert "trend/motion@10" in out and ("ETH 2026" in out or "Ethiopia 2026" in out) and "U15" in out
    # aliases / slugs resolve case-insensitively; the header states the EFFECTIVE era and window
    cli.main(["japan", "2050", "--mode", "any", "--k", "2"])
    out = capsys.readouterr().out
    assert out.startswith("Japan 2050") and "era all (query is a projection)" in out and "any year → years 1950–2100" in out
    cli.main(["JPN", "2026", "--mode", "near", "--n", "10", "--k", "2"])
    assert "2026±10 → years 2016–2026" in capsys.readouterr().out             # clipped by the era cap
    with pytest.raises(SystemExit, match="unknown entity"):
        cli.main(["Atlantis", "2026"])
    for bad in (["JPN", "2101"], ["JPN", "2026", "--metric", "trend"], ["JPN", "2026", "--metric", "path"]):
        with pytest.raises(SystemExit):
            cli.parse(bad)
    X = corpus[0]
    emb = tmp_path / "fake.pca64.npy"
    np.save(emb, ((X - X.mean(0)) @ np.random.default_rng(0).normal(size=(42, 64))).astype(np.float32))
    cli.main(["JPN", "2026", "--metric", "visual:fake", "--emb", str(emb), "--k", "3"])
    assert "metric visual:fake" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.parse(["JPN", "2026", "--metric", "visual:fake"])          # visual without --emb
    with pytest.raises(SystemExit):
        cli.parse(["JPN", "2026", "--metric", "bogus"])
