"""bands.py — percentile tables built with an injected distance function on a synthetic corpus."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer import bands as B
from pyramid_explorer.paths import N_YEARS, YEARS

N_ENT = 6


def _corpus(seed: int = 0):
    """6 synthetic entities × 151 years: 4 countries ≥ 100k, one micro country, one aggregate."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, N_YEARS)[:, None]
    X = np.concatenate([rng.gamma(2, size=42) * (1 - t) + rng.gamma(2, size=42) * t for _ in range(N_ENT)])
    X /= X.sum(1, keepdims=True)
    ids = ["AAA", "BBB", "CCC", "DDD", "MIC", "agg-900"]
    keys = pd.DataFrame({
        "row": np.arange(N_ENT * N_YEARS), "id": np.repeat(ids, N_YEARS), "locid": -1,
        "year": np.tile(YEARS, N_ENT), "type": ["country"] * 5 * N_YEARS + ["aggregate"] * N_YEARS,
        "pop_total": np.repeat([1000.0, 2000.0, 3000.0, 4000.0, 50.0, 10000.0], N_YEARS)})
    entities = [{"id": i, "type": "aggregate" if i.startswith("agg") else "country"} for i in ids]
    return X, keys, entities


def _l2_fn(X):
    calls = []

    def fn(metric, q_row, rows, sex):
        calls.append((metric, q_row, len(rows), sex))
        L = B.trend_window(metric) or 0
        q = X[q_row] - (X[q_row - L] if L else 0)
        c = X[rows] - (X[rows - L] if L else 0)
        return np.linalg.norm(c - q, axis=1)

    fn.calls = calls
    return fn


@pytest.fixture(scope="module")
def built():
    X, keys, entities = _corpus()
    fn = _l2_fn(X)
    out = B.build_bands(X, keys, entities, {}, ["l2", "trend@20"], n_pairs=40, dist_fn=fn)
    return X, keys, out, fn


def test_grid_is_24_points():
    assert len(B.GRID) == 24 and B.GRID[0] == 0 and B.GRID[-1] == 100 and B.GRID == sorted(B.GRID)


def test_shapes(built):
    _, _, out, _ = built
    assert set(out) == {"same", "cross", "best"}
    same = out["same"]["l2"]["2"]
    assert set(same) == set(YEARS) and all(len(v) == 24 for v in same.values())
    for fam in ("cross", "best"):
        tab = out[fam]["l2"]["1"]
        assert set(tab) == {"obs", "all"} and set(tab["all"]) == set(B.DECADES)
        assert all(len(v) == 24 for v in tab["obs"].values())


def test_quantiles_monotone_nonnegative(built):
    _, _, out, _ = built
    for name, vals in B.flatten_bands(out).items():
        assert vals == sorted(vals) and vals[0] >= 0, name


def test_only_eligible_countries_are_paired(built):
    _, keys, out, fn = built
    ent = keys["row"].to_numpy() // N_YEARS
    for metric, q_row, _, _ in fn.calls:
        assert ent[q_row] < 4, "micro country / aggregate must never be a query"
    # same-year tables never pair an entity with itself: distances are strictly positive
    assert min(v[0] for v in out["same"]["l2"]["2"].values()) > 0


def test_trend_windows_masked(built):
    _, _, out, fn = built
    same = out["same"]["trend@20"]["2"]
    assert min(same) == 1970 and 1969 not in same
    assert all(q_row % N_YEARS >= 20 for m, q_row, _, _ in fn.calls if m == "trend@20")
    assert 1950 not in out["cross"]["trend@20"]["2"]["all"] and 1970 in out["cross"]["trend@20"]["2"]["all"]


def test_best_is_min_over_years_hence_smaller(built):
    _, _, out, _ = built
    for era in B.ERAS:
        for dec in B.DECADES:
            best, cross = out["best"]["l2"]["2"][era][dec], out["cross"]["l2"]["2"][era][dec]
            assert best[12] <= cross[12]  # median of the min ≤ median of a random draw


def test_obs_era_restricts_candidate_years():
    X, keys, entities = _corpus()
    seen = []

    def fn(metric, q_row, rows, sex):
        seen.append((rows, q_row))
        return np.ones(len(rows))

    B.build_bands(X, keys, entities, {}, ["l2"], n_pairs=20, dist_fn=fn, current_year=2026, last_observed_year=2023)
    years = keys["year"].to_numpy()
    # every call made for a 2090s query under era=obs must only see candidates ≤ 2026 — check via the pattern
    # that no call from a query in 2090+ contains a candidate year > 2026 in *all* calls, obs ones included:
    calls_2090 = [rows for rows, q in seen if years[q] >= 2090]
    assert any((years[r] <= 2026).all() for r in calls_2090)  # the obs calls
    assert any((years[r] > 2026).any() for r in calls_2090)   # the all-era calls


def test_deterministic_and_seed_sensitive():
    X, keys, entities = _corpus()
    a = B.build_bands(X, keys, entities, {}, ["l2"], n_pairs=30, dist_fn=_l2_fn(X))
    b = B.build_bands(X, keys, entities, {}, ["l2"], n_pairs=30, dist_fn=_l2_fn(X))
    c = B.build_bands(X, keys, entities, {}, ["l2"], n_pairs=30, dist_fn=_l2_fn(X), seed=1)
    assert B.flatten_bands(a) == B.flatten_bands(b) != B.flatten_bands(c)


def test_sex_blind_metric_built_once_and_aliased():
    """w1 / feat / visual:* ignore sex, so their tables are computed for sex='2' only, aliased to '1', and stored
    once in the binary (both index names → one offset); l2 still gets two distinct passes."""
    X, keys, entities = _corpus()
    base = _l2_fn(X)

    def fn(metric, q_row, rows, sex):          # sex-dependent for the non-blind metric, so its two tables differ
        return base(metric, q_row, rows, sex) * (2.0 if sex == "1" else 1.0)

    fn.calls = base.calls
    out = B.build_bands(X, keys, entities, {}, ["w1", "l2", "visual:toy"], n_pairs=30, dist_fn=fn)
    sexes = {m: {s for mm, _, _, s in fn.calls if mm == m} for m in ("w1", "l2", "visual:toy")}
    assert sexes == {"w1": {"2"}, "l2": {"2", "1"}, "visual:toy": {"2"}}
    assert B.sex_blind("w1") and B.sex_blind("feat") and B.sex_blind("visual:x") and not B.sex_blind("blend")
    for fam in ("same", "cross", "best"):
        assert out[fam]["w1"]["1"] is out[fam]["w1"]["2"] and out[fam]["l2"]["1"] is not out[fam]["l2"]["2"]
    buf = B.serialize_bands(out)
    n = int.from_bytes(buf[:4], "little")
    index = __import__("json").loads(buf[4:4 + n])
    assert index["same/w1/1/1990"] == index["same/w1/2/1990"] and index["same/l2/1/1990"] != index["same/l2/2/1990"]
    flat = B.flatten_bands(out)
    unique = {tuple(np.asarray(v, dtype="<f4").tolist()) for v in flat.values()}
    assert len(buf) == 4 + n + 4 * sum(len(u) for u in unique) < 4 + n + 4 * sum(len(v) for v in flat.values())
    back = B.deserialize_bands(buf)
    assert set(back) == set(flat) and np.array_equal(back["cross/w1/1/obs/2020"], back["cross/w1/2/obs/2020"])


def test_serialize_round_trip(built):
    _, _, out, _ = built
    buf = B.serialize_bands(out)
    back = B.deserialize_bands(buf)
    flat = B.flatten_bands(out)
    assert list(back) == list(flat)
    assert "same/l2/2/1990" in back and "cross/trend@20/1/obs/2020" in back and "best/l2/2/all/2100" in back
    for name, vals in flat.items():
        assert np.allclose(back[name], np.asarray(vals, dtype=np.float32))
    n = int.from_bytes(buf[:4], "little")
    unique = {tuple(np.asarray(v, dtype="<f4").tolist()) for v in flat.values()}   # identical tables stored once
    assert buf[4:5] == b"{" and len(buf) == 4 + n + 4 * sum(len(u) for u in unique)


def test_serialize_empty_and_default_subset(built):
    _, _, out, _ = built
    assert B.deserialize_bands(B.serialize_bands({})) == {}
    sub = B.default_subset(out, metric="l2", sex="2")
    assert list(B.flatten_bands(sub)) == [f"same/l2/2/{y}" for y in YEARS]
    assert B.default_subset(out, metric="nope") == {}


def test_band_label():
    q = list(np.linspace(0, 1, 24))  # quantile value == GRID rank position
    p5, p25, p75, p95 = q[3], q[7], q[13], q[17]
    assert B.band_label(p5, q) == "very_close" and B.band_label(0.0, q) == "very_close"
    assert B.band_label(p5 + 1e-6, q) == "close" and B.band_label(p25, q) == "close"
    assert B.band_label((p25 + p75) / 2, q) == "typical"
    assert B.band_label(p75, q) == "far" and B.band_label(p95 - 1e-6, q) == "far"
    assert B.band_label(p95, q) == "extreme" and B.band_label(9.0, q) == "extreme"
    with pytest.raises(ValueError):
        B.band_label(0.1, [0.0, 1.0])


def test_default_dist_fn_uses_metrics_module():
    pytest.importorskip("pyramid_explorer.metrics")
    from pyramid_explorer import metrics as M
    if not hasattr(M, "distances"):
        pytest.skip("metrics.distances not implemented yet")
    X, _, _ = _corpus()
    fn = B.default_dist_fn(X, {})
    d = fn("l2", 0, np.array([1, 2, 200]), "2")
    assert d.shape == (3,) and np.all(d >= 0)
