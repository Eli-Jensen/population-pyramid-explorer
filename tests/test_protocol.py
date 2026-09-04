"""Evaluation protocol (evals/protocol.md): fast synthetic checks of the scoring functions in
``scripts/eval_similarity.py`` and, under ``-m slow``, the headline gates re-derived on the real corpus."""
from __future__ import annotations

import importlib.util
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from pyramid_explorer.paths import DATA_PROCESSED, EVALS, N_BINS, N_DIMS, REPO_ROOT

spec = importlib.util.spec_from_file_location("eval_similarity", REPO_ROOT / "scripts" / "eval_similarity.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

LABELS = {p.stem: yaml.safe_load(p.read_text()) for p in sorted((EVALS / "labels").glob("*.yaml"))}


# ------------------------------------------------------------------------------------------------ labels on disk
def test_label_files_present_with_headers():
    assert set(LABELS) == {"korenjak_cerne", "hahn_klimroth_2025", "thresholds_stage", "rieti", "yoshida_epitome"}
    for name, doc in LABELS.items():
        assert doc["source"]["url"].startswith("http"), name
        assert "vintage" in doc and doc["retrieved"], name
    kc = LABELS["korenjak_cerne"]
    assert kc["fallback_status"] == "rung1_2008_lists" and kc["primary_year"] == 2006
    for year, exp in ((1996, {"A": 77, "D": 60}), (2001, {"A": 60, "D": 54}), (2006, {"D": 46})):
        raw = kc["years"][year]["raw_names"]
        for c, n in exp.items():
            assert len(raw[c]) == n, (year, c)          # the paper's own counts (§3.1–3.2)
        ids = [i for c in raw.values() for i in c]
        assert len(ids) == len(set(ids)) == kc["years"][year]["n_countries_paper"]
    m = kc["years"][2006]["clusters"]
    assert "VUT" not in m["A"] and {"BRN", "GUM", "MNP", "TCA", "ARE", "KWT"} <= set(m["B"])
    assert {"ALB", "ARM", "DMA", "KAZ", "KNA", "TTO"} <= set(m["C"]) and {"JPN", "DEU", "ITA"} <= set(m["D"])
    assert {"ARE", "QAT", "KWT", "BHR"} <= set(kc["years"][1996]["clusters"]["C"])


def test_hk_rules_cover_sequences():
    rules = LABELS["hahn_klimroth_2025"]["rules"]
    seqs = [tuple(r["seq"]) for r in rules]
    assert len(seqs) == len(set(seqs)) == 74                 # Table S8: 74 of the 81 sequences
    assert all(("class" in r) ^ ("cases" in r) for r in rules)
    assert all(r["cases"][-1][0] == "else" for r in rules if "cases" in r)


def test_yoshida_targets_and_windows():
    y = LABELS["yoshida_epitome"]
    assert [r["id"] for r in y["table1_countries"][1990]] == ["IND", "EGY", "DZA", "BGD"]
    assert y["table1_countries"][2050][0] == {"id": "URY", "d_ait": 0.419}
    w = yaml.safe_load((EVALS / "time_shift.yaml").read_text())["windows"]
    assert [x for x in w if x.get("gate")] == [{"query": ["CHN", 2020], "target": "JPN", "window": [1985, 1995], "gate": True,
                                                "source": "evals/labels/rieti.yaml"}]
    assert LABELS["rieti"]["window"] == [1985, 1995]
    g = yaml.safe_load((EVALS / "canonical_groups.yaml").read_text())["groups"]
    assert set(g) == {"aged_europe", "sahel", "gulf_migrant", "anglo_nordic", "korea_taiwan", "china_thailand_cuba"}


# ------------------------------------------------------------------------------------------------ scoring functions
def _pyr(shape: str) -> np.ndarray:
    """Synthetic two-sex share vectors with a known Hahn-Klimroth shape."""
    age = np.arange(N_BINS)
    if shape == "pyramid":
        a = np.exp(-0.12 * age)
    elif shape == "column":
        a = np.r_[np.ones(17), np.zeros(4)]
    elif shape == "inverted_pyramid":
        a = np.r_[np.exp(0.10 * age[:17]), np.zeros(4)]
    elif shape == "upper_diamond":
        a = np.r_[np.linspace(1, 2, 12), [1.5, 0.8, 0.4, 0.2, 0.1, 0.05, 0, 0, 0]]
    v = np.r_[a, a] / (2 * a.sum())
    return v


def test_hk_classes_synthetic():
    spec_hk = LABELS["hahn_klimroth_2025"]
    X = np.stack([_pyr(s) for s in ("pyramid", "column", "inverted_pyramid", "upper_diamond")])
    assert list(ev.hk_classes(X, spec_hk)) == ["pyramid", "column", "inverted_pyramid", "upper_diamond"]
    assert list(ev.hk_family(np.array(["lower_diamond", "upper_diamond", "bell"], dtype=object))) == ["diamond", "diamond", "bell"]


def test_hk_conditional_rule_evaluation():
    spec_hk = LABELS["hahn_klimroth_2025"]
    b = spec_hk["buckets"]
    # sequence (-1, -1, -1, 1) with B3 > B5 → pyramid, B3 ≤ B5 → hourglass (paper's ambiguous case)
    def vec(b5_density):
        a = np.zeros(N_BINS)
        for k, dens in zip(("B1", "B2", "B3", "B4", "B5"), (1.0, 0.8, 0.6, 0.4, b5_density)):
            for j in b[k]["bins"]:
                a[j] = dens * b[k]["width_years"] / len(b[k]["bins"])
        return np.r_[a, a] / (2 * a.sum())
    assert list(ev.hk_classes(np.stack([vec(0.5), vec(0.7)]), spec_hk)) == ["pyramid", "hourglass"]


def test_precision_mrr_jaccard_continuity():
    assert ev.norm_precision(["a", "b", "x", "y", "z"], {"q", "a", "b"}, 5) == 1.0          # hits / min(5, |G|−1) = 2/2
    assert ev.norm_precision(["x", "a", "y", "z", "w"], {"q", "a", "b", "c", "d", "e", "f", "g"}, 5) == 0.2
    assert np.isnan(ev.norm_precision(["x"], {"q"}, 5))
    assert ev.mrr(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3) and ev.mrr(["x"], {"a"}) == 0.0
    assert ev.jaccard({1, 2}, {2, 3}) == pytest.approx(1 / 3) and ev.jaccard(set(), set()) == 1.0
    same = np.array([[1, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 0, 0, 0], [1, 1, 0, 0, 0]], bool)
    assert ev.continuity_stats(same) == {"C1": 0.5, "C5": 0.75, "n": 4}


def _synth_ctx(seed: int = 0):
    """Tiny entity-major corpus: 6 countries + 1 aggregate, smooth in time, distinct in shape."""
    from pyramid_explorer.metrics import fit_sigma
    rng = np.random.default_rng(seed)
    ids = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "agg-900"]
    rows, X = [], []
    for e, i in enumerate(ids):
        base = rng.dirichlet(np.ones(N_DIMS) * 5)
        drift = rng.normal(0, 0.002, N_DIMS)
        for t, y in enumerate(range(1950, 2101)):
            v = np.clip(base + drift * t + rng.normal(0, 1e-4, N_DIMS), 1e-6, None)
            X.append(v / v.sum())
            rows.append((e * 151 + t, i, -1, y, "aggregate" if i.startswith("agg") else "country", 5000.0))
    keys = pd.DataFrame(rows, columns=["row", "id", "locid", "year", "type", "pop_total"])
    ents = [{"id": i, "type": "aggregate" if i.startswith("agg") else "country", "region_locid": 900 + e % 3} for e, i in enumerate(ids)]
    X = np.asarray(X)
    return ev.Ctx(X, keys, ents, fit_sigma(X, keys, ents, n_pairs=500))


def test_ctx_topk_and_continuity_synthetic():
    ctx = _synth_ctx()
    for metric in ("blend", "l2", "trend", "path", "feat"):
        g = ev.g1_continuity(ctx, metric, n_queries=12, seed=0)
        assert g["observed"]["C1"] >= 0.9 and g["projected"]["n"] == 12, metric
    row = 3 * 151 + 50
    nn = ctx.topk("blend", row, ctx.eligible(), 3)
    assert row not in nn and set(ctx.id[nn]) == {"DDD"} and np.abs(ctx.year[nn] - 2000).max() <= 2
    assert ctx.dedupe_topk("blend", row, ctx.eligible(), 3) and "DDD" not in ctx.dedupe_topk("blend", row, ctx.eligible(), 6)


def test_isolation_and_best_year_synthetic():
    ctx = _synth_ctx()
    order = ev.g4_isolation(ctx, "l2", 2024, 0.0)
    assert sorted(order) == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    assert abs(ev.best_year(ctx, "blend", ("AAA", 2000), "AAA") - 2000) <= 1


def test_beta_sweep_and_exposed_visual_synthetic():
    ctx = _synth_ctx()
    sw = ev.beta_sweep(ctx, "blend", 2024, betas=(0.0, 0.5, 2.0), n_anchors=4, k=3)
    assert [r["beta"] for r in sw] == [0.0, 0.5, 2.0] and sw[0]["jaccard_vs_strict"] == 1.0 and sw[2]["identical_to_beta2"] == 1.0
    assert all(r["n"] == 4 and 1 <= r["mean_regions"] <= 3 and r["mean_raw_rank"] >= 1 for r in sw)
    assert ev.exposed_visual({"blend": {}}) is None
    res = {"visual:a": {"g1": {"observed": {"C1": 0.51}}}, "visual:b": {"g1": {"observed": {"C1": 0.55}}}, "blend": {}}
    e = ev.exposed_visual(res)
    assert e["model"] == "b" and e["metric"] == "visual:b" and e["alternates"] == ["a"] and e["C1_obs"] == 0.55
    assert ev._gated(0.8495, 0.85) == "0.8495 ✗" and ev._gated(0.868, 0.85) == "0.868 ✓" and ev._gated(0.85, 0.85) == "0.8500 ✓"


def test_verdict_rules():
    base = {"g1": {"observed": {"C1": 0.99, "C5": 1.0}}, "kc": {"2006": {"agree": 0.8}}, "hk_agree": 0.9, "stage_agree": 0.95,
            "rieti": {"pass": True}, "yoshida": {"pass": False}, "g4": {"pass": True}}
    assert ev.verdict("blend", base)[0] == "default"
    assert ev.verdict("l2", base)[0] == "menu"                        # G2e is reported only
    assert ev.verdict("l2", {**base, "g4": {"pass": False}})[0] == "lab"
    assert ev.verdict("l2", {**base, "kc": {"2006": {"agree": 0.5}}})[0] == "advanced"
    assert ev.verdict("l2", {**base, "hk_agree": 0.5})[0] == "rejected"
    assert ev.verdict("l2", {**base, "g1": {"observed": {"C1": 0.7, "C5": 0.9}}})[0] == "rejected"
    assert ev.verdict("trend", {**base, "g4": {"pass": False}})[0] == "menu"
    assert ev.verdict("path", {**base, "g1": {"observed": {"C1": 0.9, "C5": 1.0}}})[0] == "lab"


# ------------------------------------------------------------------------------------------------ real corpus
@pytest.mark.slow
def test_protocol_on_real_corpus(tmp_path):
    if not (DATA_PROCESSED / "corpus_s42.npy").exists():
        pytest.skip("no corpus on disk")
    out = ev.run_full(n_queries=40, n_anchors=6, seed=0, out_dir=tmp_path, verbose=False, sweep_anchors=12)
    res = out["results"]
    assert res["blend"]["g1"]["observed"]["C1"] >= 0.95 and res["blend"]["g4"]["pass"]
    assert res["blend"]["rieti"]["pass"] and res["blend"]["kc"]["2006"]["agree"] >= 0.7
    assert res["blend"]["opposites"]["div0_exact"] and res["blend"]["opposites"]["dedupe_any_year"]
    assert res["blend"]["opposites"]["beta"] == 2.0                    # pre-registered β, whatever the shipped default
    assert res["blend"]["verdict"] == "default"
    assert all(0 <= g["p_at_5"] <= 1 for g in res["blend"]["regression"]["groups"].values() if g["p_at_5"] is not None)
    v = json.loads((tmp_path / "verdicts.json").read_text())
    assert len(v["data_hash"]) == 64 and v["_meta"]["informational"] is True
    assert "kc2006_p10" not in v["blend"]["numbers"]                    # degenerate for large clusters (protocol §2)
    f = v["_meta"]["findings"]
    assert [r["beta"] for r in f["beta_sweep"]] == list(ev.SWEEP_BETAS) and f["beta_sweep"][0]["jaccard_vs_strict"] == 1.0
    assert f["blend_w1_share"]["2"]["all"] == pytest.approx(0.5, abs=0.03)
    if v["_meta"]["embeddings"]:
        assert v["exposed_visual"]["model"] in v["emb_meta_hash"] and v["exposed_visual"]["metric"].startswith("visual:")
    else:
        assert v["exposed_visual"] is None
    md = (tmp_path / "RESULTS.md").read_text()
    assert md.startswith("# Similarity evaluation") and "MMR β sweep" in md and "W1 share of `blend` by era" in md
