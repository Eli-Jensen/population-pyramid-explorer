"""features.py — synthetic pyramids + provisional-corpus reference values (research/similarity_methods §3)."""
from __future__ import annotations


import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.features import FEATURE_NAMES, NUMERIC_FEATURES, features, median_age, s21, zscore_vector, zscores
from pyramid_explorer.paths import DATA_PROCESSED, N_BINS


def pyramid(age_profile: np.ndarray, male_share: float = 0.5) -> np.ndarray:
    a = np.asarray(age_profile, float) / np.sum(age_profile)
    return np.concatenate([male_share * a, (1 - male_share) * a])


@pytest.fixture(scope="module")
def corpus():
    if not (DATA_PROCESSED / "corpus_s42.npy").exists():
        pytest.skip("provisional corpus absent")
    X = np.load(DATA_PROCESSED / "corpus_s42.npy")
    keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
    row = {(i, y): r for r, i, y in zip(keys["row"], keys["id"], keys["year"])}
    return X, keys, row


def test_columns_and_shape():
    f = features(np.tile(pyramid(np.ones(N_BINS)), (3, 1)))
    assert list(f.columns) == FEATURE_NAMES and len(f) == 3
    assert features(pyramid(np.ones(N_BINS))).shape == (1, len(FEATURE_NAMES))


def test_uniform_pyramid_median_mean_and_shares():
    f = features(pyramid(np.ones(N_BINS))).iloc[0]
    assert f.median_age == pytest.approx(52.5) and f.mean_age == pytest.approx(52.5)
    assert f.u15 == pytest.approx(3 / 21) and f.wa == pytest.approx(10 / 21) and f.o65 == pytest.approx(8 / 21)
    assert f.o80 == pytest.approx(5 / 21) and f.total_dep == pytest.approx(11 / 10)
    assert f.base_slope_20 == pytest.approx(1.0) and f.wa_sex_ratio == pytest.approx(1.0) and f.stage == "constrictive"


def test_median_interpolation_and_100_plus():
    # all mass in the 100+ bin → median inside [100, 105)
    top = np.zeros(N_BINS); top[-1] = 1
    assert median_age(top[None])[0] == pytest.approx(102.5)
    # two equal bins 0-4 and 5-9 → CDF hits 0.5 exactly at the bin edge
    two = np.zeros(N_BINS); two[:2] = 0.5
    assert median_age(two[None])[0] == pytest.approx(5.0)


def test_stage_rule_and_flags():
    young = features(pyramid(0.8 ** np.arange(N_BINS))).iloc[0]          # geometric decay → expansive
    assert young.stage == "expansive" and young.median_age < 25 and young.base_slope_20 > 1
    old = features(pyramid(np.r_[np.ones(10), 3 * np.ones(11)])).iloc[0]   # mass above 50 → urn
    assert old.stage == "constrictive" and old.flag_urn and old.modal_bin >= 45
    mid = features(pyramid(np.r_[np.ones(12), 0.1 * np.ones(9)])).iloc[0]
    assert mid.stage == "stationary" and not mid.flag_urn
    gulf = features(pyramid(np.ones(N_BINS), male_share=0.75)).iloc[0]
    assert gulf.flag_male_skew and gulf.wa_sex_ratio == pytest.approx(3.0)
    assert not features(pyramid(np.ones(N_BINS))).iloc[0].flag_male_skew


def test_zscores_reference_and_query_vector():
    rng = np.random.default_rng(0)
    X = rng.dirichlet(np.ones(42), 50)
    f = features(X)
    z = zscores(f, np.arange(20))
    assert list(z.columns) == NUMERIC_FEATURES
    assert np.allclose(z.iloc[:20].mean(), 0, atol=1e-9) and np.allclose(z.iloc[:20].std(ddof=0), 1, atol=1e-9)
    assert np.allclose(zscore_vector(f.iloc[[3]], z)[0], z.iloc[3].to_numpy())
    const = f.copy(); const["modal_bin"] = 5.0
    assert np.isfinite(zscores(const, np.arange(50))["modal_bin"]).all()      # zero variance → sd 1


def test_provisional_reference_values(corpus):
    X, _, row = corpus
    f = features(X)
    jpn, ner, qat, kor = f.iloc[row["JPN", 2024]], f.iloc[row["NER", 2024]], f.iloc[row["QAT", 2024]], f.iloc[row["KOR", 2050]]
    assert jpn.median_age == pytest.approx(50.4, abs=0.6) and jpn.o65 == pytest.approx(0.298, abs=0.01)
    assert jpn.u15 == pytest.approx(0.114, abs=0.01) and jpn.old_dep == pytest.approx(0.51, abs=0.03)
    assert jpn.base_slope_20 == pytest.approx(0.66, abs=0.05) and jpn.stage == "constrictive" and jpn.flag_urn
    assert ner.median_age == pytest.approx(16.5, abs=0.6) and ner.u15 == pytest.approx(0.466, abs=0.01) and ner.stage == "expansive"
    assert qat.wa_sex_ratio == pytest.approx(3.22, abs=0.1) and qat.flag_male_skew and qat.stage == "stationary"
    assert kor.median_age == pytest.approx(57.8, abs=0.6) and kor.o65 == pytest.approx(0.397, abs=0.01)
    assert np.isfinite(f[NUMERIC_FEATURES].to_numpy()).all()
    assert set(f.stage.unique()) <= {"expansive", "constrictive", "stationary"}


def test_s21_sums_to_one(corpus):
    X = corpus[0]
    assert np.allclose(s21(X).sum(1), 1)
