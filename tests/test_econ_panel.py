"""Experiment 2 (panel.py) on the planted synthetic world, with E1 stand-ins: sample construction, sign recovery,
holdout mechanics (FE carry-forward, OOS R² identities), predictions and the coefficient table."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.econ import panel
from tests import _econ_fakes as fakes
from tests.test_econ_lookalike import synth_world


@pytest.fixture(scope="module")
def world():
    return synth_world(seed=1, signal=True, n_c=24)


@pytest.fixture(scope="module")
def sample(world):
    corpus, gd, _ = world
    return panel.build_sample(corpus, gd)


def test_sample_columns_and_window(sample):
    df, P, report = sample
    assert {"iso3", "t", "g", "lny", "WA", "dWA", "D", "D_feat", "region", "decade", "fe"} <= set(df.columns)
    assert df["t"].min() >= 1960 and df["t"].max() <= 2013           # dWA needs t − 10 ≥ 1950
    assert df[["lny", "WA", "dWA", "D", "D_feat"]].notna().all().all()
    assert (P["year"] + 10 <= panel.PROTO_TRAIN_END).all()
    assert report["n"] == len(df) and report["n_prototypes"] == len(P)
    assert (df["fe"] == df["region"] + "|" + df["decade"].astype(str)).all()


def test_design_matrix_shapes(sample):
    df, _, _ = sample
    X, names = panel.design(df, "S3")
    assert X.shape == (len(df), 4 + df["fe"].nunique()) and names[:4] == ["lny", "WA", "dWA", "D"]
    assert np.allclose(X[:, 4:].sum(1), 1.0)                          # exactly one FE dummy per row
    Xh, _ = panel.design(df.head(5).assign(fe="zzz|1"), "S0", fe_levels=["a|1", "b|1"])
    assert Xh.shape == (5, 3) and Xh[:, 1:].sum() == 0               # unseen level → all-zero dummies


def test_planted_signal_recovered_in_specs(sample):
    df, _, _ = sample
    specs = panel.fit_specs(df, stats=fakes)
    assert set(specs) == set(panel.SPECS)
    # growth was planted as a decreasing function of the blend distance to the planted prototype: D < 0, strongly
    assert specs["S2"]["coef"]["D"]["beta"] < 0 and specs["S2"]["coef"]["D"]["p_dk"] < 0.01
    assert specs["S3"]["coef"]["D"]["beta"] < 0
    assert specs["S3"]["r2"] >= specs["S1"]["r2"] - 1e-12 and specs["S2"]["r2"] >= specs["S0"]["r2"] - 1e-12
    for spec, v in specs.items():
        assert list(v["coef"]) == panel.SPECS[spec]
        for c in v["coef"].values():
            assert {"beta", "se_dk", "p_dk", "se_2way", "p_2way"} == set(c) and 0 <= c["p_dk"] <= 1


def test_holdout_mechanics(sample):
    df, _, _ = sample
    ho = panel.holdout(df)
    assert ho["train"]["t_max"] == 1993 and ho["test"]["t_range"] == [2003, 2013]
    oos = ho["oos_r2"]
    # identities: a spec against itself is 0; S0 vs the mean is what the S0 predictor buys
    assert oos["S0"]["vs_s0"] == pytest.approx(0.0) and oos["S1"]["vs_s1"] == pytest.approx(0.0)
    assert oos["S2"]["vs_mean"] > oos["S0"]["vs_mean"]                # D carries the planted signal out of sample
    for spec in panel.SPECS:
        assert set(ho["spearman"][spec]["per_t"]) == set(range(2003, 2014))
    assert ho["spearman"]["S2"]["mean"] > 0.5


def test_holdout_carries_region_fe_forward_and_drops_unknown_regions():
    rng = np.random.default_rng(0)
    rows = []
    for c in range(12):
        region = "R1" if c < 8 else ("R2" if c < 10 else "R3")
        for t in range(1960, 2014):
            if region == "R3" and t <= 1993:
                continue                                              # R3 has no training rows at all
            rows.append({"iso3": f"c{c}", "t": t, "g": rng.normal(), "lny": rng.normal(), "WA": rng.normal(), "dWA": rng.normal(),
                         "D": rng.normal(), "D_feat": rng.normal(), "region": region})
    df = pd.DataFrame(rows)
    df["decade"] = (df["t"] // 10) * 10
    df["fe"] = df["region"] + "|" + df["decade"].astype(str)
    ho = panel.holdout(df)
    assert ho["test"]["n_dropped_no_region_fe"] == 2 * 11             # R3: 2 countries × 11 test years
    assert ho["test"]["n"] == 10 * 11


def test_predictions_and_run(world):
    corpus, gd, _ = world
    res, coefs = panel.run(corpus, gd, stats=fakes)
    assert {"P6", "P7", "P8"} <= set(res["predictions"])
    assert res["predictions"]["P6"]["spec"] == "S3" and set(res["predictions"]["P6"]["components"]) == {"WA", "dWA"}
    assert set(res["predictions"]["P7"]["components"]) == {"D_lt_0_in_sample", "delta_r2_s3_s1_lt_.03", "oos_gain_s3_over_s1_lt_.02"}
    assert res["sample"]["n_eff"] <= res["sample"]["n"] and res["sample"]["n_eff"] > 0
    assert res["delta_r2_s3_s1"] == pytest.approx(res["specs"]["S3"]["r2"] - res["specs"]["S1"]["r2"])
    assert set(coefs.columns) >= {"spec", "term", "beta", "se_dk", "p_dk", "se_2way", "p_2way", "r2", "n"}
    assert len(coefs) == (1 + len(panel.ROBUSTNESS)) * sum(len(v) for v in panel.SPECS.values())   # primary + 3 refits
    lk.to_jsonable(res)


def test_prototype_overlap_masks_and_robustness_refits(sample):
    df, P, report = sample
    sm, ov = panel.prototype_overlap(df, P)
    # every exact self-match is an own-overlap row and sits at min d = 0 → D = ln(clip); no self-match after the training block
    assert sm.sum() == report["n_self_match"] and ov.sum() == report["n_own_prototype_overlap"] and (ov | ~sm).all()
    assert np.allclose(df.loc[sm, "D"], np.log(panel.D_CLIP))
    assert sm.sum() >= 1                                              # the synthetic prototypes are sample rows by construction
    assert set(zip(df.loc[sm, "iso3"], df.loc[sm, "t"])) <= set(zip(P["iso3"], P["year"]))
    # own-overlap = same country, |t − y| < 10 — check one hand-built case
    P2 = pd.DataFrame({"iso3": ["X"], "year": [1980], "g": [0.1]})
    d2 = pd.DataFrame({"iso3": ["X", "X", "X", "Y"], "t": [1980, 1989, 1990, 1980]})
    s2, o2 = panel.prototype_overlap(d2, P2)
    assert list(s2) == [True, False, False, False] and list(o2) == [True, True, False, False]
    # the floor variant has no −20.72 leverage points and agrees with D wherever min d > 0
    assert df["D_floor"].min() >= np.log(report["d_floor_smallest_nonzero"]) - 1e-12
    assert np.allclose(df.loc[~sm, "D_floor"], df.loc[~sm, "D"])
    rob = panel.robustness_refits(df, stats=fakes)
    assert set(rob) == set(panel.ROBUSTNESS)
    assert rob["ex_selfmatch"]["n"] == len(df) - sm.sum() and rob["ex_overlap"]["n"] == len(df) - ov.sum() and rob["floor"]["n"] == len(df)
    for r in rob.values():
        assert set(r["specs"]) == set(panel.SPECS) and "D" in r["specs"]["S3"]["coef"]


def test_run_reports_self_match_diagnostics_and_suffixed_refit_rows(world):
    corpus, gd, _ = world
    res, coefs = panel.run(corpus, gd, stats=fakes)
    smp = res["sample"]
    assert {"n_self_match", "n_own_prototype_overlap", "share_own_prototype_overlap", "n_self_match_in_test_block", "d_floor_smallest_nonzero"} <= set(smp)
    assert smp["n_self_match_in_test_block"] == 0                     # P_train windows end ≤ 2003 → y ≤ 1993 < 2003
    assert set(res["robustness"]) == {"ex_selfmatch", "ex_overlap", "floor"}
    note = res["predictions"]["P7"]["components"]["D_lt_0_in_sample"]["note"]
    assert note.startswith("artifact") and "self-matching" in note and "ex_overlap" not in note and "β_D" in note
    suffixed = {s for s in coefs["spec"] if "_" in s}
    assert suffixed == {f"{spec}_{key}" for spec in panel.SPECS for key in panel.ROBUSTNESS}
    assert len(coefs) == 4 * sum(len(v) for v in panel.SPECS.values())
    lk.to_jsonable(res)
