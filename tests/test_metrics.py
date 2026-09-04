"""metrics.py — definitions (CONTRACT §4), sigma fitting, decomposition, trend/path/visual, timing."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.features import features, zscores
from pyramid_explorer.metrics import (KERNEL, METRICS, SNAPSHOT_METRICS, TREND_WINDOWS, W1BAL_LAMBDA, blend_balance,
                                      decompose, distances, fit_sigma, lagged, load_sigma, sample_pairs, smooth)
from pyramid_explorer.paths import DATA_PROCESSED, N_BINS, N_YEARS

BASE_METRICS = [m for m in SNAPSHOT_METRICS if m != "feat"]


def synth_corpus(n_ent: int = 6, seed: int = 0, n_years: int = N_YEARS):
    """Entity-major synthetic corpus: smooth drift per entity so adjacent years are nearest neighbours."""
    rng = np.random.default_rng(seed)
    rows, keys = [], []
    ids = [f"E{i:02d}" for i in range(n_ent)]
    for e, eid in enumerate(ids):
        base = rng.dirichlet(np.ones(42) * 3)
        drift = rng.normal(0, 0.002, 42)
        for t in range(n_years):
            s = np.clip(base + t * drift, 1e-4, None); s /= s.sum()
            rows.append(s)
            keys.append((e * n_years + t, eid, 1950 + t, "country" if e < n_ent - 1 else "aggregate", 1000.0 + 100 * e))
    X = np.array(rows)
    keys = pd.DataFrame(keys, columns=["row", "id", "year", "type", "pop_total"])
    keys.loc[keys.id == ids[-1], "id"] = "agg-900"
    ents = [{"id": i, "type": "country"} for i in ids[:-1]] + [{"id": "agg-900", "type": "aggregate"}]
    return X, keys, ents


@pytest.fixture(scope="module")
def synth():
    return synth_corpus()


@pytest.fixture(scope="module")
def corpus():
    if not (DATA_PROCESSED / "corpus_s42.npy").exists():
        pytest.skip("provisional corpus absent")
    X = np.load(DATA_PROCESSED / "corpus_s42.npy")
    keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
    ents = json.loads((DATA_PROCESSED / "entities.json").read_text())
    return X, keys, ents


@pytest.fixture(scope="module")
def sigma(corpus):
    return fit_sigma(*corpus)


def test_metric_list():
    assert METRICS[0] == "blend" and {"l2", "w1", "l2s", "hel", "feat", "w1sex", "w1bal", "clr", "trend", "path"} <= set(METRICS)


@pytest.mark.parametrize("metric", BASE_METRICS)
@pytest.mark.parametrize("sex", ["2", "1"])
def test_identity_symmetry_nonneg(synth, metric, sex):
    X, keys, ents = synth
    s = fit_sigma(X, keys, ents, n_pairs=500)
    d = distances(metric, X[10], X, sex=sex, sigma=s)
    assert d.dtype == np.float32 and d.shape == (len(X),) and d[10] == pytest.approx(0, abs=1e-6) and (d >= 0).all()
    d2 = distances(metric, X[200], X[[10]], sex=sex, sigma=s)[0]
    assert d2 == pytest.approx(d[200], rel=1e-5)


def test_l2_and_hellinger_definitions(synth):
    X = synth[0]
    assert distances("l2", X[0], X[[1]])[0] == pytest.approx(np.linalg.norm(X[0] - X[1]), rel=1e-6)
    a, b = np.sqrt(X[0]), np.sqrt(X[1])
    assert distances("hel", X[0], X[[1]])[0] == pytest.approx(np.linalg.norm(a - b) / np.sqrt(2), rel=1e-6)
    assert distances("hel", X[0], X, sex="1").max() <= 1.0


def test_w1_is_years_and_sex_blind():
    prof = np.zeros(N_BINS); prof[:5] = 0.2
    shifted = np.roll(prof, 1)                                             # everyone one bin (5 y) older
    a = np.concatenate([0.5 * prof, 0.5 * prof]); b = np.concatenate([0.5 * shifted, 0.5 * shifted])
    assert distances("w1", a, b[None])[0] == pytest.approx(5.0, abs=1e-6)
    assert distances("w1sex", a, b[None])[0] == pytest.approx(5.0, abs=1e-6)      # 2.5 y per sex
    # w1 ignores sex; w1sex charges a male surplus as transport parked at 100+
    c = np.concatenate([0.7 * prof, 0.3 * prof])
    assert distances("w1", a, c[None])[0] == pytest.approx(0, abs=1e-9)
    assert distances("w1sex", a, c[None])[0] > 10
    assert distances("w1sex", a, c[None], sex="1")[0] == pytest.approx(0, abs=1e-9)


def test_blend_uses_sigma_and_halves(synth):
    X, keys, ents = synth
    s = fit_sigma(X, keys, ents, n_pairs=500)
    for sex in ("2", "1"):
        l2 = distances("l2", X[0], X, sex=sex) / s["l2"][sex]
        w = distances("w1sex" if sex == "2" else "w1", X[0], X, sex=sex) / s["w1sex" if sex == "2" else "w1"][sex]
        assert np.allclose(distances("blend", X[0], X, sex=sex, sigma=s), 0.5 * l2 + 0.5 * w, rtol=1e-5)
    with pytest.raises(KeyError):
        distances("blend", X[0], X, sigma={"l2": {"2": 1.0}})


def test_smoothing_kernel_preserves_mass_and_tolerates_shift():
    assert KERNEL.sum() == pytest.approx(0.991, abs=1e-3)
    s = np.zeros(42); s[8] = 0.5; s[29] = 0.5
    sm = smooth(s)[0]
    assert sm[:N_BINS].sum() == pytest.approx(0.5 * KERNEL.sum()) and sm.shape == (42,)
    t = np.zeros(42); t[9] = 0.5; t[30] = 0.5
    u = np.zeros(42); u[14] = 0.5; u[35] = 0.5
    assert distances("l2s", s, t[None])[0] < distances("l2s", s, u[None])[0] and distances("l2", s, t[None])[0] == distances("l2", s, u[None])[0]


def test_w1bal_and_clr(synth):
    X = synth[0]
    a = X[0]; a21 = a[:N_BINS] + a[N_BINS:]
    swapped = np.concatenate([a[N_BINS:], a[:N_BINS]])                   # same ages, sexes swapped
    assert distances("w1", a, swapped[None])[0] == pytest.approx(0, abs=1e-9)
    assert distances("w1bal", a, swapped[None])[0] > 0 and distances("w1bal", a, swapped[None], sex="1")[0] == pytest.approx(0, abs=1e-9)
    lg = np.log(a + 1e-6); lg -= lg.mean(); lh = np.log(X[1] + 1e-6); lh -= lh.mean()
    assert distances("clr", a, X[[1]])[0] == pytest.approx(np.linalg.norm(lg - lh), rel=1e-5)


def test_w1bal_formula_pinned_symmetric_weights():
    """CONTRACT §4: w1bal = w1(s21) + λ·Σ_k ½(s21_a,k + s21_b,k)·|r_a,k − r_b,k| — the bin weight is the MEAN of the
    two totals, so the metric is symmetric; a hand-built pair pins the formula for the web twin."""
    m = np.zeros(N_BINS); f = np.zeros(N_BINS)
    m[[0, 4, 8]] = [0.20, 0.15, 0.10]; f[[0, 4, 8]] = [0.20, 0.15, 0.20]          # b: female surplus at bin 8
    a = np.concatenate([np.array([0.25, 0, 0, 0, 0.15, 0, 0, 0, 0.10] + [0] * 12), np.array([0.25, 0, 0, 0, 0.15, 0, 0, 0, 0.10] + [0] * 12)])
    b = np.concatenate([m, f])
    a21, b21 = a[:N_BINS] + a[N_BINS:], b[:N_BINS] + b[N_BINS:]
    w1 = 5.0 * np.abs(np.cumsum(a21) - np.cumsum(b21)).sum()
    ra = np.divide(a[:N_BINS], a21, out=np.full(N_BINS, 0.5), where=a21 > 0)
    rb = np.divide(b[:N_BINS], b21, out=np.full(N_BINS, 0.5), where=b21 > 0)
    expect = w1 + W1BAL_LAMBDA * (0.5 * (a21 + b21) * np.abs(ra - rb)).sum()
    assert expect > w1 > 0
    assert distances("w1bal", a, b[None])[0] == pytest.approx(expect, rel=1e-6)
    assert distances("w1bal", b, a[None])[0] == pytest.approx(expect, rel=1e-6)            # symmetric
    assert distances("w1bal", a, b[None], sex="1")[0] == pytest.approx(w1, rel=1e-6)       # total-only drops the penalty


def test_blend_balance_reports_w1_share_by_era(synth):
    X, keys, ents = synth
    s = fit_sigma(X, keys, ents, n_pairs=500)
    bal = blend_balance(X, keys, ents, s, n_pairs=2000)
    assert set(bal) == {"2", "1"} and {"obs", "nowcast", "proj", "all"} <= set(bal["2"])
    assert all(0.0 < v < 1.0 for d in bal.values() for v in d.values())
    assert bal["2"]["all"] == pytest.approx(0.5, abs=0.1)     # σ makes the halves equal on the pooled sample


def test_blend_balance_real_corpus_tilt(corpus, sigma):
    """Documented asymmetry (RESULTS.md): σ_w1 grows into the projections, so observed-year pairs lean on L2."""
    bal = blend_balance(*corpus, sigma)
    assert bal["2"]["all"] == pytest.approx(0.5, abs=0.03) and bal["1"]["all"] == pytest.approx(0.5, abs=0.03)
    assert bal["2"]["obs"] < bal["2"]["nowcast"] < bal["2"]["proj"]
    assert bal["2"]["nowcast"] == pytest.approx(0.5, abs=0.05)     # balanced at the default (2024–2026) years
    print({sex: {k: round(v, 3) for k, v in d.items()} for sex, d in bal.items()})


def test_feat_metric_uses_zscored_reference(synth):
    X = synth[0]
    z = zscores(features(X), np.arange(151))
    d = distances("feat", X[0], X, feats=z)
    assert d[0] == pytest.approx(0, abs=1e-6) and np.isfinite(d).all()
    d_auto = distances("feat", X[0], X)                                   # reference = all rows
    assert d_auto[0] == pytest.approx(0, abs=1e-6)


def test_visual_cosine(synth):
    rng = np.random.default_rng(1)
    E = rng.normal(size=(len(synth[0]), 64))
    d = distances("visual:siglip2-base-naflex", synth[0][3], synth[0], emb=E, q_row=3)
    assert d[3] == pytest.approx(0, abs=1e-6) and (d >= 0).all() and d.max() <= 2 + 1e-6
    with pytest.raises(ValueError):
        distances("visual:x", synth[0][3], synth[0])


def test_lagged_and_trend(synth):
    X, keys, ents = synth
    s = fit_sigma(X, keys, ents, n_pairs=500)
    Xl = lagged(X, 10)
    assert np.isnan(Xl[:10]).all() and np.isnan(Xl[151:161]).all() and np.array_equal(Xl[161], X[151])
    d = distances("trend", X[20], X, L=10, X_prev=Xl, q_prev=Xl[20], sigma=s)
    assert d[20] == pytest.approx(0, abs=1e-6) and np.isnan(d[:10]).all()
    dq, dX = X[20] - Xl[20], X - Xl
    assert np.allclose(d[10:151], np.linalg.norm(dX[10:151] - dq, axis=1) / s["trend@10"]["2"], rtol=1e-5)
    stack = np.stack([lagged(X, 5), Xl])
    assert np.allclose(distances("trend", X[20], X, L=10, X_prev=stack, q_prev=stack[:, 20], sigma=s)[10:151], d[10:151])
    p = distances("path", X[20], X, L=10, X_prev=stack, q_prev=stack[:, 20], sigma=s)
    manual = (distances("blend", X[20], X, sigma=s) + distances("blend", stack[0, 20], stack[0], sigma=s)
              + distances("blend", Xl[20], Xl, sigma=s)) / 3
    assert np.allclose(p[10:151], manual[10:151], rtol=1e-5) and p[20] == pytest.approx(0, abs=1e-6)
    with pytest.raises(ValueError):
        distances("trend", X[20], X, L=10, sigma=s)


def test_sample_pairs_same_year_distinct_country(synth):
    X, keys, ents = synth
    a, b = sample_pairs(keys, ents, 300, seed=0, minpop=0)
    assert (keys.year.to_numpy()[a] == keys.year.to_numpy()[b]).all() and (keys.id.to_numpy()[a] != keys.id.to_numpy()[b]).all()
    assert not (keys.id.to_numpy()[a] == "agg-900").any()
    a2, _ = sample_pairs(keys, ents, 300, seed=0, minpop=0)
    assert np.array_equal(a, a2)


def test_fit_sigma_keys_write_and_load(synth, tmp_path):
    X, keys, ents = synth
    p = tmp_path / "sigma.json"
    s = fit_sigma(X, keys, ents, n_pairs=300, write=True, path=p)
    assert {"l2", "w1", "w1sex", "l2s", "hel", "feat", "w1bal", "clr", "blend"} | {f"trend@{L}" for L in TREND_WINDOWS} <= set(s)
    assert all(set(v) == {"2", "1"} and all(x > 0 for x in v.values()) for v in s.values())
    assert s["w1"]["2"] == s["w1"]["1"] == s["w1sex"]["1"]
    assert json.loads(p.read_text()) == s and load_sigma(p) == s
    assert isinstance(load_sigma(tmp_path / "missing.json"), dict)


def test_sigma_provisional_values(sigma):
    """Same-year country pairs ≥ 100k (CONTRACT §4). NB: 0.083 / 11.3 in the plan were ALL-year pairs."""
    assert 0.045 <= sigma["l2"]["2"] <= 0.10 and 5 <= sigma["w1sex"]["2"] <= 14
    assert sigma["blend"]["2"] == pytest.approx(1.0, abs=0.05) and sigma["blend"]["1"] == pytest.approx(1.0, abs=0.05)
    assert sigma["trend@5"]["2"] < sigma["trend@10"]["2"] < sigma["trend@20"]["2"]
    print({m: {k: round(v, 4) for k, v in sigma[m].items()} for m in ("l2", "w1sex", "w1", "trend@10")})


def test_decompose_blend(corpus, sigma):
    X, keys, _ = corpus
    row = lambda i, y: int(keys.index[(keys.id == i) & (keys.year == y)][0])
    q, x = X[row("JPN", 2026)], X[row("QAT", 2026)]
    dec = decompose("blend", q, x, sex="2", sigma=sigma)
    assert dec["d"] == pytest.approx(dec["l2_part"] + dec["w1_part"], rel=1e-6)
    assert dec["d"] == pytest.approx(distances("blend", q, x[None], sigma=sigma)[0], rel=1e-5)
    assert abs(sum(c for _, c in dec["top_bins_l2"]) - 1) < 1 and dec["w1_years"] > 20     # Gulf male surplus = big transport
    assert dec["top_bins_w1"][0][0] < N_BINS                                             # the male CDF gap dominates
    assert sum(c for _, c in dec["top_bins_w1"]) <= dec["w1_years"] + 1e-9
    dl2 = decompose("l2", q, x, sex="2", sigma=sigma)
    assert dl2["w1_part"] == 0 and dl2["l2_part"] == pytest.approx(dl2["d"])
    d1 = decompose("blend", q, x, sex="1", sigma=sigma)
    assert d1["w1_years"] < dec["w1_years"] and all(k < N_BINS for k, _ in d1["top_bins_l2"])


def test_blend_timing_full_corpus(corpus, sigma):
    X, keys, _ = corpus
    q = X[int(keys.index[(keys.id == "JPN") & (keys.year == 2026)][0])]
    distances("blend", q, X, sigma=sigma)
    times = []
    for _ in range(20):
        t = time.perf_counter(); distances("blend", q, X, sigma=sigma); times.append(time.perf_counter() - t)
    ms = 1000 * float(np.median(times))
    print(f"blend over {len(X)} rows: {ms:.2f} ms/query (median of 20)")
    assert ms < 100
