"""vintage.py (PREREG §8 vintage sensitivity check): bin alignment, LocID mapping with predecessor rows, the selection
re-implementation on the synthetic corpus (identical vectors ⇒ Jaccard 1; perturbed vectors ⇒ valid sets), the check
document, and the guarded RESULTS.md §7 hook in results.py (fixture document → paragraph; absent file → the caveat)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import yaml

from pyramid_explorer.econ import decide, lookalike as lk, results, vintage as vg
from pyramid_explorer.paths import AGE_STARTS, ECON_EVALS, N_DIMS
from tests.test_econ_lookalike import synth_world

SENTENCES = yaml.safe_load((ECON_EVALS / "ui_sentences.yaml").read_text())
DENY = decide.compile_deny_list(SENTENCES)


# ----------------------------------------------------------------------------------------------- bins
def test_align_bins_identity_open80_and_fold_above_100():
    m21, f21, note = vg.align_bins(np.array(AGE_STARTS), np.arange(21.0), 2 * np.arange(21.0))
    assert note.startswith("identity") and m21.tolist() == list(range(21)) and f21[-1] == 40
    # a 17-bin ladder with an open 80+ bin: people land in 80–84, nothing above
    m21, f21, note = vg.align_bins(np.arange(0, 81, 5), np.ones(17), np.ones(17))
    assert "80+" in note and m21.sum() == 17 and m21[16] == 1 and m21[17:].sum() == 0 and f21[16] == 1
    # unsorted input is fine; a 23-bin ladder folds 100–104 and 105+ into 100+
    order = np.random.default_rng(0).permutation(23)
    m21, f21, note = vg.align_bins(np.arange(0, 111, 5)[order], np.ones(23)[order], np.full(23, 2.0)[order])
    assert m21[20] == 3 and f21[20] == 6 and m21.sum() == 23 and "summed into the 100+" in note
    with pytest.raises(ValueError):
        vg.align_bins(np.array([0, 5, 15]), np.ones(3), np.ones(3))
    with pytest.raises(ValueError):
        vg.align_bins(np.array([0, 1, 2]), np.ones(3), np.ones(3))


# ----------------------------------------------------------------------------------------------- mapping
def _archive_frame(rows: dict[int, tuple[str, list[int], float]], year: int = 2010) -> pd.DataFrame:
    """rows: locid -> (name, age_starts, scale); male = scale·(k+1), female = scale·(k+2) per bin."""
    recs = []
    for lid, (name, starts, scale) in rows.items():
        for k, a in enumerate(starts):
            recs.append({"locid": lid, "name": name, "year": year, "age_start": a, "age_span": 5 if a < starts[-1] else -1,
                         "pop_male": scale * (k + 1), "pop_female": scale * (k + 2)})
    return pd.DataFrame(recs)


def test_archive_cross_section_maps_locids_predecessors_and_reports_unmapped():
    ents = [{"id": "AAA", "locid": 1, "type": "country", "name": "A"}, {"id": "BBB", "locid": 2, "type": "country", "name": "B"},
            {"id": "SDN", "locid": 729, "type": "country", "name": "Sudan"}, {"id": "SSD", "locid": 728, "type": "country", "name": "South Sudan"},
            {"id": "agg-900", "locid": 900, "type": "world", "name": "World"}]
    pop = _archive_frame({1: ("A", AGE_STARTS, 1.0), 2: ("B", list(range(0, 81, 5)), 10.0), 736: ("Sudan (Former)", AGE_STARTS, 2.0),
                          530: ("Netherlands Antilles", AGE_STARTS, 1.0), 900: ("WORLD", AGE_STARTS, 100.0)})
    sl = vg.archive_cross_section(pop, 2010, ents, revision=2010)
    assert list(sl.keys["iso3"]) == ["AAA", "BBB", "SDN"] and sl.X.shape == (3, N_DIMS)
    assert np.allclose(sl.X.sum(1), 1.0) and (sl.X >= 0).all()
    # BBB's 80+ ladder: bins 85+ are zero for both sexes
    b = sl.vector("BBB")
    assert b[17:21].sum() == 0 and b[38:42].sum() == 0 and b[16] > 0
    assert [p["iso3"] for p in sl.predecessors_used] == ["SDN"] and sl.predecessors_used[0]["locid"] == 736
    assert sl.keys.loc[sl.keys["iso3"] == "SDN", "via"].iloc[0].startswith("Sudan (Former)")
    assert [u["locid"] for u in sl.archive_unmapped] == [530] and sl.archive_unmapped[0]["note"].startswith("Netherlands Antilles")
    assert sl.corpus_absent == ["SSD"]                       # no archive row, no predecessor → reported, never invented
    assert sl.vectors(["AAA", "SSD", "ZZZ"]).keys() == {"AAA"}
    # a predecessor row is NOT used when the successor has its own row
    pop2 = pd.concat([pop, _archive_frame({729: ("Sudan", AGE_STARTS, 3.0)})], ignore_index=True)
    sl2 = vg.archive_cross_section(pop2, 2010, ents, revision=2010)
    assert sl2.predecessors_used == [] and sl2.keys.loc[sl2.keys["iso3"] == "SDN", "locid"].iloc[0] == 729
    assert [u["locid"] for u in sl2.archive_unmapped] == [530, 736]
    with pytest.raises(ValueError):
        vg.archive_cross_section(pop, 1999, ents)
    # archive_vector: a single (iso3, year) lookup, None when absent
    assert np.allclose(vg.archive_vector(pop, ents, "AAA", 2010), sl.vector("AAA"))
    assert vg.archive_vector(pop, ents, "AAA", 1990) is None and vg.archive_vector(pop, ents, "SSD", 2010) is None


def test_jaccard_and_revision_rule():
    assert vg.jaccard([], []) == 1.0 and vg.jaccard(["a"], ["b"]) == 0.0 and vg.jaccard(list("abcde"), list("abcdx")) == pytest.approx(4 / 6)
    assert vg.revision_for_T(1990) == 2000 and vg.revision_for_T(2000) == 2000 and vg.revision_for_T(2005) == 2010
    assert vg.revision_for_T(2010) == 2010 and vg.revision_for_T(2015) is None
    assert vg.archive_url(2010).endswith("/5_Archive/WPP2010-CSV-data.zip")


# ----------------------------------------------------------------------------------------------- selection on the synthetic corpus
@pytest.fixture(scope="module")
def world():
    return synth_world(seed=3, signal=True, n_c=24)


def _slice_from(corpus: lk.Corpus, T: int, perturb: float, rng, drop: set[str] = frozenset()) -> vg.ArchiveSlice:
    ids = [i for i in corpus.country_ids(T) if i not in drop]
    X = np.stack([corpus.X[corpus.row(i, T)] for i in ids])
    if perturb:
        X = np.clip(X + rng.normal(0, perturb, X.shape), 1e-6, None)
        X /= X.sum(1, keepdims=True)
    keys = pd.DataFrame({"iso3": ids, "locid": range(len(ids)), "name": ids, "pop_total": 5000.0, "via": None})
    return vg.ArchiveSlice(2010, T, X, keys, [], [], [], "identity")


def test_identical_vectors_reproduce_the_main_run_and_perturbed_vectors_stay_valid(world):
    corpus, gd, _ = world
    T = 2010
    res, _ = lk.run(corpus, gd, stats=__import__("tests._econ_fakes", fromlist=["x"]), B=200, growth_T={10: (T,)}, queries=("A", "B"), ks=(10, 5))
    sl_same = _slice_from(corpus, T, 0.0, None)
    anchor_same = corpus.X[corpus.row(lk.ANCHOR_ID, lk.ANCHOR_YEAR)]
    d = vg.check_T(corpus, gd, T, sl_same, res, anchor_archive=anchor_same)
    assert d["n_candidates"] == d["n_candidates_with_archive"] and d["unmapped_candidates"] == []
    for q in ("A", "B"):
        for k in ("10", "5"):
            assert d["self_check_wpp2024_reproduced"][q][k]["identical"] is True
    for name, qd in d["queries"].items():
        for k in ("10", "5"):
            c = qd["k"][k]
            assert c["jaccard"] == 1.0 and c["archive"] == c["wpp2024"] and c["only_archive"] == [] and len(c["archive"]) == int(k)
        assert qd["rank_continuity"]["spearman"] == pytest.approx(1.0) and qd["rank_continuity"]["n_within_k"] == 10
    assert d["queries"]["B"]["k"]["10"]["met"] is True and d["queries"]["B"]["k"]["5"]["met"] is None
    assert d["revision_size"]["l2_max"] == 0.0 and d["anchor_revision"]["l2"] == 0.0
    # perturbed archive with one candidate missing: sets are still k long, the missing country never appears, Jaccard ∈ [0, 1]
    rng = np.random.default_rng(0)
    gone = d["queries"]["B"]["k"]["10"]["wpp2024"][0]
    sl_pert = _slice_from(corpus, T, 0.004, rng, drop={gone})
    d2 = vg.check_T(corpus, gd, T, sl_pert, res, anchor_archive=anchor_same + rng.normal(0, 0.002, N_DIMS))
    assert d2["unmapped_candidates"] == [gone] and d2["n_candidates_with_archive"] == d2["n_candidates"] - 1
    for name, qd in d2["queries"].items():
        c = qd["k"]["10"]
        assert len(c["archive"]) == 10 and gone not in c["archive"] and 0.0 <= c["jaccard"] <= 1.0
        assert c["n_common"] == len(set(c["archive"]) & set(c["wpp2024"])) and c["met"] == (c["jaccard"] >= 0.6)
        assert -1.0 <= qd["rank_continuity"]["spearman"] <= 1.0
    assert d2["revision_size"]["n"] == d2["n_candidates_with_archive"] and d2["revision_size"]["l2_median"] > 0
    assert d2["anchor_revision"]["d_blend"] > 0
    # without an archive anchor the archive-anchor variant is reported as unavailable, not dropped
    d3 = vg.check_T(corpus, gd, T, sl_pert, res, anchor_archive=None)
    assert d3["queries"]["A_anchor_archive"]["k"]["10"]["jaccard"] is None and d3["anchor_revision"] is None
    summ = vg.summarise({"2010": d, "2000": d2})
    assert summ["cells"] == 6 and summ["cells_met"] == 3 + sum(int(q["k"]["10"]["met"]) for q in d2["queries"].values())
    assert summ["B_k10_met_at_every_T"] == bool(d2["queries"]["B"]["k"]["10"]["met"])
    md = vg.render_vintage_md({"_meta": {"generated_at": "t", "git_rev": "r"}, "sources": {}, "mapping": {}, "per_T": {"2010": d, "2000": d2},
                               "robustness": {}, "summary": summ, "caveats": ["c"], "bin_alignment": "identity"})
    assert "### T = 2010" in md and "Rank continuity" in md and "Ten largest shape revisions" in md


# ----------------------------------------------------------------------------------------------- RESULTS.md §7 hook
def _fixture_doc() -> dict:
    cell = lambda j, wpp, arch: {"wpp2024": wpp, "archive": arch, "jaccard": j, "n_common": len(set(wpp) & set(arch)), "met": j >= 0.6,
                                 "only_wpp2024": sorted(set(wpp) - set(arch)), "only_archive": sorted(set(arch) - set(wpp))}
    q = lambda jb, ja, jaa: {
        "B": {"query": "B", "label": "B", "k": {"10": cell(jb, list("abcdefghij"), list("abcdefghiK")), "5": cell(0.67, list("abcde"), list("abcdK"))},
              "rank_continuity": {"n": 150, "spearman": 0.93, "median_archive_rank": 9.0, "max_archive_rank": 37, "n_within_k": 6, "n_within_2k": 8,
                                  "median_abs_change": 0.0256, "wpp2024_kth_gap": 0.0513}},
        "A_anchor_wpp2024": {"query": "A", "label": "A", "k": {"10": cell(ja, list("abcdefghij"), list("abcdefgXYZ")), "5": cell(0.25, list("abcde"), list("abXYZ"))}},
        "A_anchor_archive": {"query": "A", "label": "A", "k": {"10": cell(jaa, list("abcdefghij"), list("abcdefXYZW")), "5": cell(0.43, list("abcde"), list("abcXY"))}}}
    per_T = {"2010": {"T": 2010, "revision": 2010, "role": "primary", "n_candidates": 156, "n_candidates_with_archive": 155, "unmapped_candidates": ["SSD"],
                      "predecessors_used_in_candidates": [{"locid": 736, "iso3": "SDN", "name": "Sudan (Former)", "note": "n"}], "queries": q(0.82, 0.33, 0.43),
                      "revision_size": {"n": 155, "l2_median": 0.0094, "l2_sigma_median": 0.17, "l2_max": 0.0562, "l2_max_iso3": "SAU", "d_blend_median": 0.18}},
             "2000": {"T": 2000, "revision": 2000, "role": "primary", "n_candidates": 151, "n_candidates_with_archive": 150, "unmapped_candidates": ["TWN"],
                      "predecessors_used_in_candidates": [], "queries": q(0.05, 0.43, 0.43),
                      "revision_size": {"n": 150, "l2_median": 0.0102, "l2_sigma_median": 0.18, "l2_max": 0.101, "l2_max_iso3": "ARE", "d_blend_median": 0.2}}}
    return {"_meta": {"generated_at": "2026-09-04T22:40:00+00:00", "threshold_jaccard_k10": 0.6, "self_check_passed": True}, "per_T": per_T,
            "robustness": {"2000@2002": {"T": 2000, "revision": 2002, "queries": {"B": {"k": {"10": {"jaccard": 0.11}}}}}},
            "summary": vg.summarise(per_T)}


def _ctx(**kw) -> dict:
    base = {"prereg_commit": "abc", "run": {}, "sources": [], "universe": {"entries": []}, "guard": None, "backtest": {}, "panel": {},
            "disconnect": None, "decision": {"levels": {}, "rendered": {}, "allowed_sentence_ids": [], "predictions": {}}, "implementation_notes": [], "deviations": []}
    base.update(kw)
    return base


def test_results_hook_renders_the_vintage_paragraph_from_a_fixture_document():
    doc = _fixture_doc()
    md = results.render_results(_ctx(vintage_check=doc))
    sec = md.split("## 7. Vintage statement (PREREG §8)")[1].split("## 8.")[0]
    assert "was performed with the WPP 2010 / WPP 2000 CSV archives" in sec
    assert "**Vintage check (PREREG §8) — performed.**" in sec and "(2026-09-04)" in sec
    assert "WPP 2010 for T = 2010; WPP 2000 for T = 2000" in sec
    assert "Query B (primary) — 2010: 0.82, 2000: 0.05" in sec and "Query A, China-1990 anchor from WPP 2024 — 2010: 0.33, 2000: 0.43" in sec
    assert "Query A, anchor from the archive too — 2010: 0.43, 2000: 0.43" in sec and "k = 5: Query B (primary) — 2010: 0.67, 2000: 0.67" in sec
    assert "NOT met by Query B at every T" in sec and "held in 1 of 6 (rule, T) cells" in sec
    assert "below the threshold: B@2000, A_anchor_wpp2024@2000, A_anchor_archive@2000, A_anchor_wpp2024@2010, A_anchor_archive@2010" in sec
    assert "Rank continuity (additional, not pre-registered" in sec and "Query B — 2010: ρ 0.93, WPP 2024 members at archive ranks ≤ 37; 2000: ρ 0.93" in sec
    assert "T = 2010: median L2 0.0094 = 0.17 σ_l2, max 0.0562 (SAU)" in sec and "Candidates the archive does not carry" in sec and "2010: SSD; 2000: TWN" in sec
    assert "Predecessor rows used: SDN ← Sudan (Former)" in sec and "T = 2000 on WPP 2002: Query B k = 10 Jaccard 0.11" in sec
    assert "reproduced every recorded WPP 2024 lookalike set exactly" in sec and "RESULTS_vintage.md" in sec
    assert "Growth-data vintage" in sec                      # the existing second paragraph is still there, after the check
    assert decide.scan_deny_list(md, DENY) == []
    # the paragraph alone is also clean and one paragraph
    para = results.vintage_summary(doc)
    assert "\n" not in para and decide.scan_deny_list(para, DENY) == []
    # the ≥ 0.6 wording flips when every Query B cell holds
    good = _fixture_doc()
    for t in good["per_T"].values():
        for name in t["queries"]:
            t["queries"][name]["k"]["10"].update({"jaccard": 0.82, "met": True})
    good["summary"] = vg.summarise(good["per_T"])
    assert "was met by Query B at every T and held in 6 of 6 (rule, T) cells overall." in results.vintage_summary(good)


def test_results_hook_is_guarded(tmp_path, monkeypatch):
    # explicit None suppresses the summary and keeps the pre-existing caveat wording
    md = results.render_results(_ctx(vintage_check=None))
    assert results.VINTAGE_NOT_PERFORMED in md and "Vintage check (PREREG §8) — performed" not in md
    # an explicit vintage_status wins over the derived one
    md = results.render_results(_ctx(vintage_check=_fixture_doc(), vintage_status="custom status."))
    assert "custom status." in md and "Vintage check (PREREG §8) — performed" in md
    # loader: missing → None; malformed → None; document without per_T → None; a real document → dict
    assert results.load_vintage_check(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert results.load_vintage_check(bad) is None
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"per_T": {}}))
    assert results.load_vintage_check(empty) is None
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_fixture_doc()))
    assert results.load_vintage_check(good)["per_T"]["2010"]["revision"] == 2010
    # when the key is absent from ctx the default path is consulted; point it at an empty dir → caveat wording
    monkeypatch.setattr(results, "load_vintage_check", lambda path=None: None)
    md = results.render_results(_ctx())
    assert results.VINTAGE_NOT_PERFORMED in md


def test_recorded_lookalikes_orders_by_distance():
    bt = {"rows": {"B|10|10|growth": {"picks": [{"T": 2010, "iso3": "X", "d": 0.3}, {"T": 2010, "iso3": "Y", "d": 0.1}, {"T": 2000, "iso3": "Z", "d": 0.0}]}}}
    assert vg.recorded_lookalikes(bt, "B", 10, 2010) == ["Y", "X"] and vg.recorded_lookalikes(bt, "B", 10, 1990) == []
    assert vg.recorded_lookalikes(bt, "A", 10, 2010) == []
