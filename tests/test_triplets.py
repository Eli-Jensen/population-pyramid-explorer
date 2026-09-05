"""triplets.py — selection (determinism, strata, duplicate placement, side randomisation, recorded distances) and
fitting (self-agreement gate, exact sign test, planted-preference recovery) on a synthetic corpus; under ``-m slow``
the committed selection is re-derived on the real corpus."""
from __future__ import annotations

import json
from math import comb

import numpy as np
import pytest
import yaml

from pyramid_explorer import triplets as T
from pyramid_explorer.econ import decide
from pyramid_explorer.metrics import fit_sigma
from pyramid_explorer.paths import ECON_EVALS
from pyramid_explorer.quantise import U16_TOTAL
from tests.test_metrics import synth_corpus

DENY = decide.compile_deny_list(yaml.safe_load((ECON_EVALS / "ui_sentences.yaml").read_text()))


@pytest.fixture(scope="module")
def space():
    X, keys, ents = synth_corpus(n_ent=100, seed=7)
    sigma = fit_sigma(X, keys, ents, n_pairs=2000)
    rng = np.random.default_rng(1)
    emb = {"fake-a": rng.normal(size=(len(X), 16)).astype(np.float32), "fake-b": rng.normal(size=(len(X), 16)).astype(np.float32)}
    return T.Space(X, keys, ents, sigma, emb)


@pytest.fixture(scope="module")
def sel(space):
    return T.select_triplets(space, seed=0, visual_metric="visual:fake-a", data_hash=T.corpus_hash(space.X))


def uniques(sel):
    return [it for it in sel["items"] if it["duplicate_of"] is None]


# ------------------------------------------------------------------------------------------------ selection
def test_selection_deterministic(space, sel):
    again = T.select_triplets(space, seed=0, visual_metric="visual:fake-a", data_hash=T.corpus_hash(space.X))
    assert json.dumps(again, sort_keys=True) == json.dumps(sel, sort_keys=True)
    other = T.select_triplets(space, seed=1, visual_metric="visual:fake-a")
    assert [it["anchor"]["id"] for it in other["items"]] != [it["anchor"]["id"] for it in sel["items"]]


def test_stratum_counts_and_item_indices(sel):
    assert sel["n_items"] == 88 and sel["n_unique"] == 80 and len(sel["items"]) == 88
    assert [it["item"] for it in sel["items"]] == list(range(88))
    u = uniques(sel)
    assert {s: sum(it["stratum"] == s for it in u) for s in T.STRATA} == {"visual": 32, "numeric": 38, "opposite": 10}
    assert all(it["variant"] == ("different" if it["stratum"] == "opposite" else "similar") for it in u)
    assert all(it["question"] == T.QUESTIONS[it["variant"]] for it in sel["items"])
    assert sel["n_anchor_reused"] == 0                      # 99 anchors ≥ 80 items: every anchor used once
    assert sel["visual_metric"] == "visual:fake-a" and sel["recorded_metrics"][-2:] == ["visual:fake-a", "visual:fake-b"]


def test_duplicates_swapped_and_placed_30_later(sel):
    dups = [it for it in sel["items"] if it["duplicate_of"] is not None]
    assert len(dups) == 8
    assert {s: sum(d["stratum"] == s for d in dups) for s in T.DUPLICATES} == {"visual": 4, "numeric": 3, "opposite": 1}
    assert len({d["duplicate_of"] for d in dups}) == 8
    for d in dups:
        o = sel["items"][d["duplicate_of"]]
        assert o["duplicate_of"] is None
        assert d["item"] - o["item"] >= T.MIN_DUP_GAP
        assert (d["anchor"], d["A"], d["B"], d["pair"], d["shares"], d["distances"]) == (o["anchor"], o["A"], o["B"], o["pair"], o["shares"], o["distances"])
        assert d["side_map"] == {"left": o["side_map"]["right"], "right": o["side_map"]["left"]}


def test_sides_and_labels_randomised(sel):
    u = uniques(sel)
    lefts = [it["side_map"]["left"] for it in u]
    assert set(lefts) == {"A", "B"} and 20 <= lefts.count("A") <= 60
    assert all(it["side_map"]["right"] != it["side_map"]["left"] for it in u)
    vis = [it for it in u if it["stratum"] == "visual"]
    a_metrics = {it["A"]["metric"] for it in vis}
    assert a_metrics == {"blend", "visual:fake-a"}        # the A label is not always the same metric
    assert all(set(it["pair"]) == {"blend", "visual:fake-a"} for it in vis)


def test_items_are_real_disagreements(sel):
    for it in uniques(sel):
        assert it["A"]["id"] != it["B"]["id"] != it["anchor"]["id"] != it["A"]["id"]
        assert it["A"]["year"] == it["B"]["year"] == it["anchor"]["year"] == 2024
        ma, mb = it["A"]["metric"], it["B"]["metric"]
        assert it["pair"] == [ma, mb]
        if it["variant"] == "similar":
            assert it["distances"][ma]["A"] <= it["distances"][ma]["B"]      # A is ma's nearest
            assert it["distances"][mb]["B"] <= it["distances"][mb]["A"]
        else:
            assert it["distances"][ma]["A"] >= it["distances"][ma]["B"]      # A is ma's farthest
            assert it["distances"][mb]["B"] >= it["distances"][mb]["A"]
        if it["stratum"] != "visual":
            assert set(it["pair"]) <= set(sel["numeric_metrics"]) and len(set(it["pair"])) == 2


def test_numeric_pairs_spread(sel):
    used = sel["pair_uses"]["numeric"]
    assert sum(used.values()) == 38 and len(used) >= 10        # least-used-first keeps coverage broad
    assert sum(sel["pair_uses"]["opposite"].values()) == 10


def test_inline_u16_rows_and_components(sel, space):
    for it in sel["items"]:
        for k in ("anchor", "A", "B"):
            row = it["shares"][k]
            assert len(row) == 42 and sum(row) == U16_TOTAL and all(0 <= v <= U16_TOTAL for v in row)
    sig = sel["sigma"]
    for it in uniques(sel)[:20]:
        for k in ("A", "B"):
            c = it["components"][k]
            assert T.blend_from(c, 0.5, 0, sig) == pytest.approx(it["distances"]["blend"][k], rel=1e-5)
            assert T.w1bal_from(c, 50.0) == pytest.approx(it["distances"]["w1bal"][k], rel=1e-5)
            assert c["l2"] == pytest.approx(it["distances"]["l2"][k], rel=1e-5)
            assert c["w1sex"] == pytest.approx(it["distances"]["w1sex"][k], rel=1e-5)
            assert c["l2_s1"] == pytest.approx(it["distances"]["l2s"][k], rel=1e-5)


def test_write_selection_roundtrip(sel, tmp_path):
    p, w = tmp_path / "sel.json", tmp_path / "web" / "sel.json"
    T.write_selection(sel, p, w)
    assert json.loads(p.read_text()) == sel and w.read_bytes() == p.read_bytes()
    assert decide.scan_deny_list(p.read_text(), DENY) == [], "deny-listed wording in the selection file"


def test_numeric_metrics_and_visual_from_verdicts():
    v = {"trend": {"gates": {"G1": False}}, "hel": {"gates": {"G1": True}},
         "exposed_visual": {"metric": "visual:siglip2-base-naflex"}}
    assert T.numeric_metrics_from_verdicts(v) == ["blend", "l2", "l2s", "hel", "w1sex", "w1bal"]
    assert T.numeric_metrics_from_verdicts(None) == T.NUMERIC_CANDIDATES
    assert T.exposed_visual_from_verdicts(v, ["visual:dinov2-base", "visual:siglip2-base-naflex"]) == "visual:siglip2-base-naflex"
    assert T.exposed_visual_from_verdicts(None, ["visual:x"]) == "visual:x"


# ------------------------------------------------------------------------------------------------ agreement semantics
def _item(variant, dA, dB):
    return {"variant": variant, "distances": {"m": {"A": dA, "B": dB}}}


def test_metric_agrees_and_prefers():
    assert T.metric_agrees(_item("similar", 1.0, 2.0), "m", "A") is True
    assert T.metric_agrees(_item("similar", 1.0, 2.0), "m", "B") is False
    assert T.metric_agrees(_item("different", 1.0, 2.0), "m", "B") is True       # farther wins the opposite variant
    assert T.metric_agrees(_item("different", 1.0, 2.0), "m", "A") is False
    assert T.metric_agrees(_item("similar", 1.0, 2.0), "m", "tie") is None
    assert T.metric_agrees(_item("similar", 1.0, 1.0), "m", "A") is None
    assert T.metric_agrees(_item("similar", None, 1.0), "m", "A") is None
    assert T.metric_prefers(_item("similar", 1.0, 2.0), "m") == "A"
    assert T.metric_prefers(_item("different", 1.0, 2.0), "m") == "B"
    assert T.metric_prefers(_item("similar", 2.0, 2.0), "m") is None


def test_sign_test_is_exact_binomial():
    t = T.sign_test(8, 2)
    assert t["p"] == pytest.approx(2 * sum(comb(10, k) for k in range(3)) / 2 ** 10)      # 0.109375
    assert t["winner"] is None
    t = T.sign_test(10, 0)
    assert t["p"] == pytest.approx(2 / 2 ** 10) and t["winner"] == "a"
    # the pre-registered MDE says "≥ 22 of 32": exact two-sided that is p = 0.0501 (one-sided 0.025) — 23 is the first call
    t = T.sign_test(22, 10)
    assert t["p"] == pytest.approx(2 * sum(comb(32, k) for k in range(11)) / 2 ** 32) and t["winner"] is None
    assert T.sign_test(23, 9)["winner"] == "a" and T.sign_test(23, 9)["p"] < 0.05
    assert T.sign_test(5, 5)["p"] == pytest.approx(1.0)
    assert T.sign_test(0, 0) == {"n_discordant": 0, "wins_a": 0, "wins_b": 0, "p": None, "winner": None}


# ------------------------------------------------------------------------------------------------ fit
def test_self_agreement_gate(sel):
    good = T.synthetic_responses(sel, seed=0, noise=0.1, dup_noise=0.0)
    f = T.fit(sel, good)
    assert f["self_agreement"]["n_pairs"] == 8 and f["self_agreement"]["n_agree"] == 8 and f["promotion_allowed"]
    assert f["n_answered"] == 88 and f["n_missing"] == 0
    bad = json.loads(json.dumps(good))
    dups = [r for r in bad["items"] if sel["items"][r["item"]]["duplicate_of"] is not None]
    for r in dups[:3]:                                        # flip three duplicates → 5/8
        r["choice"] = {"A": "B", "B": "A", "tie": "A"}[r["choice"]]
    f = T.fit(sel, bad)
    assert f["self_agreement"]["n_agree"] == 5 and not f["self_agreement"]["passes"] and not f["promotion_allowed"]
    assert "nothing may be promoted" in f["status"]
    assert f["recommendations"]["blend_params"] == {"w_l2": 0.5, "sigma_bins": 0, "lambda": 50.0, "changed": False}
    assert f["grid"]["blend"]["default"] == {"w_l2": 0.5, "sigma_bins": 0}       # the as-built blend (no smoothing)
    assert f["recommendations"]["default_metric"] == "blend"
    assert f["recommendations"]["exposed_visual"]["recommended"] == sel["visual_metric"]
    tie = json.loads(json.dumps(good))
    for r in tie["items"]:
        if sel["items"][r["item"]]["duplicate_of"] is not None:
            r["choice"] = "tie"
    assert T.fit(sel, tie)["self_agreement"]["n_agree"] <= 1                  # tie vs non-tie counts as disagreement


def test_first_response_counts_and_missing_items(sel):
    resp = T.synthetic_responses(sel, seed=2, noise=0.0, tie_rate=0.0)
    resp["items"] = resp["items"][:60] + [{"item": 0, "choice": "tie", "rt_ms": 1}]
    f = T.fit(sel, resp)
    assert f["n_answered"] == 60 and f["n_missing"] == 28
    assert T.responses_by_item(resp)[0]["choice"] == resp["items"][0]["choice"]
    with pytest.raises(ValueError, match="choice must be"):
        T.responses_by_item({"items": [{"item": 0, "choice": "left"}]})


def test_fit_recovers_planted_blend_weight(sel):
    hi = T.fit(sel, T.synthetic_responses(sel, seed=0, w_l2=0.7, sigma_bins=0, noise=0.02, tie_rate=0.0))
    assert hi["grid"]["blend"]["in_sample_best"]["w_l2"] >= 0.6
    assert hi["grid"]["blend"]["loo_agreement"] > 0.8
    lo = T.fit(sel, T.synthetic_responses(sel, seed=0, w_l2=0.3, sigma_bins=1, noise=0.02, tie_rate=0.0))
    assert lo["grid"]["blend"]["in_sample_best"]["w_l2"] <= 0.4
    assert hi["grid"]["n_items"] == lo["grid"]["n_items"] == 48                 # numeric strata only, no ties
    tbl = {(r["w_l2"], r["sigma_bins"]): r["agreement"] for r in hi["grid"]["blend"]["table"]}
    assert tbl[(0.7, 0)] >= tbl[(0.3, 1)]


def test_fit_recovers_planted_lambda(sel):
    big = T.fit(sel, T.synthetic_responses(sel, seed=0, lam=100.0, noise=0.02, tie_rate=0.0))
    none = T.fit(sel, T.synthetic_responses(sel, seed=0, lam=0.0, noise=0.02, tie_rate=0.0))
    assert big["grid"]["w1bal"]["in_sample_best"]["lambda"] >= 50.0
    assert none["grid"]["w1bal"]["in_sample_best"]["lambda"] <= 25.0


def test_paired_test_calls_the_oracle_metric(sel):
    by_visual = T.fit(sel, T.synthetic_responses(sel, seed=0, metric="visual:fake-a", noise=0.05, tie_rate=0.0))
    t = by_visual["tests"]["blend_vs_visual"]
    assert t["n_items"] == 32 and t["n_discordant"] == 32 and t["winner"] == "visual:fake-a" and t["p"] < 0.05
    assert by_visual["agreement"]["visual:fake-a"]["by_stratum"]["visual"]["agreement"] > 0.85
    # image space not passing G1/G2/G4 in verdicts → default stays blend even when it wins the paired test
    assert by_visual["recommendations"]["default_metric"] == "blend"
    verdicts = {"visual:fake-a": {"gates": {"G1": True, "G2": True, "G4": True}}}
    assert T.fit(sel, T.synthetic_responses(sel, seed=0, metric="visual:fake-a", noise=0.05, tie_rate=0.0), verdicts)["recommendations"]["default_metric"] == "visual:fake-a"
    by_blend = T.fit(sel, T.synthetic_responses(sel, seed=0, metric="blend", noise=0.05, tie_rate=0.0))
    assert by_blend["tests"]["blend_vs_visual"]["winner"] == "blend"
    # an oracle answering by the OTHER image space → the fit recommends exposing it (printed, never applied)
    by_b = T.fit(sel, T.synthetic_responses(sel, seed=0, metric="visual:fake-b", noise=0.02, tie_rate=0.0))
    rec = by_b["recommendations"]["exposed_visual"]
    assert rec["current"] == "visual:fake-a" and rec["recommended"] == "visual:fake-b"


def test_report_renders_without_deny_listed_words(sel):
    f = T.fit(sel, T.synthetic_responses(sel, seed=0))
    md = T.render_report(f, sel)
    assert md.startswith("# Human triplets") and "SYNTHETIC ORACLE" in md and "## 5. Recommendations" in md
    assert decide.scan_deny_list(md, DENY) == []                # evals/econ/ui_sentences.yaml deny list (the tested rule)
    assert decide.scan_deny_list(json.dumps(f), DENY) == []     # JSON-able and clean


# ------------------------------------------------------------------------------------------------ real corpus
@pytest.mark.slow
def test_committed_selection_reproduces():
    import importlib.util

    from pyramid_explorer.paths import REPO_ROOT

    if not T.SELECTION_PATH.exists():
        pytest.skip("evals/triplets_selection.json not built")
    spec = importlib.util.spec_from_file_location("select_triplets", REPO_ROOT / "scripts" / "select_triplets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from pyramid_explorer.metrics import load_sigma
    from pyramid_explorer.search import load_inputs

    committed = json.loads(T.SELECTION_PATH.read_text())
    X, keys, ents = load_inputs()
    sp = T.Space(X, keys, ents, load_sigma(), mod.load_embeddings(len(keys)))
    fresh = T.select_triplets(sp, seed=committed["seed"], numeric_metrics=committed["numeric_metrics"],
                              visual_metric=committed["visual_metric"], data_hash=T.corpus_hash(X))
    assert fresh == committed
    assert json.loads(T.SELECTION_WEB_PATH.read_text()) == committed
