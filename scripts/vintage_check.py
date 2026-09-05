#!/usr/bin/env python
"""Vintage sensitivity check for Experiment 1 (evals/econ/PREREG.md §8) → evals/econ/vintage/{vintage_check.json, RESULTS_vintage.md}.

    uv run --group econ scripts/vintage_check.py [--T 2010,2000] [--all-T] [--robustness 2000:2002] [--no-download]

Downloads (once) the UN's archived ``WPP<rev>-CSV-data.zip`` for the revisions the T grid needs (WPP 2010 for 2000 < T ≤ 2010,
WPP 2000 for T ≤ 2000 — PREREG §8) into ``data/raw/wpp_archive/`` (gitignored), rebuilds the T cross-section's 42-share
vectors from the archive, re-runs Query A (both anchors) and Query B with the main run's candidate sets, prototype sets and σ,
and reports the k = 10 / k = 5 Jaccard overlap with the lookalike sets recorded in ``evals/econ/backtest_lookalikes.json``
(expectation: ≥ 0.6 at k = 10) plus the size of the revisions.  ``scripts/decide_econ.py`` picks the JSON up when it
renders RESULTS.md §7 (``results.vintage_summary``).  Needs the built corpus + GDP store (``make build``) and the main
run's ``backtest_lookalikes.json``.  Never edits PREREG.md or RESULTS.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.econ import results
from pyramid_explorer.econ import vintage as vg
from pyramid_explorer.paths import ECON_EVALS


def _parse_T(s: str) -> list[int]:
    return [int(t) for t in s.split(",") if t.strip()]


def _parse_robustness(s: str) -> list[tuple[int, int]]:
    out = []
    for item in s.split(","):
        if not item.strip():
            continue
        T, rev = item.split(":")
        out.append((int(T), int(rev)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--T", default=",".join(str(t) for t in vg.PRIMARY_T), help="comma-separated T's (default: the pre-registered 2010, 2000)")
    ap.add_argument("--all-T", action="store_true", help="every T on the grid an archive covers (1990, 1995, 2000, 2005, 2010)")
    ap.add_argument("--robustness", default="2000:2002", help="extra T:revision pairs, e.g. 2000:2002,2010:2012 (default 2000:2002; '' for none)")
    ap.add_argument("--archive-dir", default=str(vg.ARCHIVE_DIR))
    ap.add_argument("--out-dir", default=str(vg.VINTAGE_DIR))
    ap.add_argument("--backtest", default=str(ECON_EVALS / "backtest_lookalikes.json"))
    ap.add_argument("--no-download", action="store_true", help="fail instead of downloading a missing archive zip")
    args = ap.parse_args(argv)
    say = lambda s: print(s, file=sys.stderr)

    Ts = sorted(set(_parse_T(args.T)) | ({1990, 1995, 2000, 2005, 2010} if args.all_T else set()), reverse=True)
    robust = _parse_robustness(args.robustness)
    bad = [T for T in Ts if vg.revision_for_T(T) is None]
    if bad:
        say(f"[vintage_check] no archive predates the outcome for T = {bad} (PREREG §8 covers T ≤ 2010); dropping them")
        Ts = [T for T in Ts if T not in bad]
    archive_dir, out_dir = Path(args.archive_dir), Path(args.out_dir)
    bt_path = Path(args.backtest)
    backtest = json.loads(bt_path.read_text()) if bt_path.exists() else None
    if backtest is None:
        say(f"[vintage_check] WARNING: {bt_path} missing — Jaccard is computed against the recomputed WPP 2024 sets, not the recorded ones")

    say("[vintage_check] loading corpus + growth windows")
    corpus = lk.load_real_corpus()
    gd = lk.load_real_growth()
    entities = corpus.entities
    n_countries = sum(1 for e in entities if e.get("type") == "country")

    needed = sorted({vg.revision_for_T(T) for T in Ts} | {rev for _, rev in robust})
    sources, pops = {}, {}
    for rev in needed:
        say(f"[vintage_check] archive WPP {rev}: {vg.REVISION_ZIPS[rev]} ({'download if missing' if not args.no_download else 'must exist'})")
        sources[str(rev)] = vg.ensure_archive(rev, archive_dir, download=not args.no_download)
        pops[rev] = vg.load_archive_population(rev, archive_dir)
    # Query A's anchor of the archive's vintage: China's 1990 pyramid as that revision estimated it
    anchors = {rev: vg.archive_vector(pops[rev], entities, lk.ANCHOR_ID, lk.ANCHOR_YEAR) for rev in needed}
    for rev, v in anchors.items():
        say(f"[vintage_check] WPP {rev} {lk.ANCHOR_ID} {lk.ANCHOR_YEAR} anchor: {'found' if v is not None else 'ABSENT'}")

    per_T, robustness, mapping, bin_notes = {}, {}, {}, set()
    for T in Ts:
        rev = vg.revision_for_T(T)
        sl = vg.archive_cross_section(pops[rev], T, entities, revision=rev)
        bin_notes.add(sl.bin_note)
        mapping[f"{rev}@{T}"] = {"revision": rev, "year": T, "n_mapped": int(len(sl.keys)), "n_corpus_countries": n_countries,
                                 "predecessors_used": sl.predecessors_used, "archive_unmapped": sl.archive_unmapped,
                                 "corpus_absent": sl.corpus_absent, "labels": {str(k): v for k, v in vg.ARCHIVE_LABELS.items() if k in set(sl.keys["locid"])}}
        say(f"[vintage_check] T={T} WPP {rev}: {len(sl.keys)} countries mapped, predecessors {[p['iso3'] for p in sl.predecessors_used]}, "
            f"archive-only {[u['locid'] for u in sl.archive_unmapped]}")
        role = "primary" if T in vg.PRIMARY_T else "additional (same PREREG §8 rule)"
        per_T[str(T)] = vg.check_T(corpus, gd, T, sl, backtest, anchor_archive=anchors[rev], role=role)
        d = per_T[str(T)]
        say("  " + "; ".join(f"{name} k=10 J={c['k']['10']['jaccard']}" for name, c in d["queries"].items() if c["k"]["10"].get("jaccard") is not None)
            + f"; unmapped candidates {d['unmapped_candidates']}")
    for T, rev in robust:
        sl = vg.archive_cross_section(pops[rev], T, entities, revision=rev)
        bin_notes.add(sl.bin_note)
        mapping[f"{rev}@{T}"] = {"revision": rev, "year": T, "n_mapped": int(len(sl.keys)), "n_corpus_countries": n_countries,
                                 "predecessors_used": sl.predecessors_used, "archive_unmapped": sl.archive_unmapped,
                                 "corpus_absent": sl.corpus_absent, "labels": {str(k): v for k, v in vg.ARCHIVE_LABELS.items() if k in set(sl.keys["locid"])}}
        robustness[f"{T}@{rev}"] = vg.check_T(corpus, gd, T, sl, backtest, anchor_archive=anchors[rev],
                                              role=f"robustness: WPP {rev} instead of WPP {vg.revision_for_T(T)}")
        d = robustness[f"{T}@{rev}"]
        say(f"[vintage_check] robustness T={T} WPP {rev}: " + "; ".join(f"{name} k=10 J={c['k']['10']['jaccard']}" for name, c in d["queries"].items()
                                                                       if c["k"]["10"].get("jaccard") is not None))

    self_ok = all(v["identical"] for d in list(per_T.values()) + list(robustness.values())
                  for q in d["self_check_wpp2024_reproduced"].values() for v in q.values() if v["identical"] is not None)
    caveats = [
        "The archive CSVs are the UN's 2020 re-export of each revision's database (member dates 2020-01-24 inside the zips), not the "
        "files distributed at the time; they already carry the 21-bin (100+) layout with populated 85–99 and 100+ cells, whereas the "
        "printed WPP 2000/2002 tables used an 80+ open bin. The figures are the revision's, the layout is the re-export's.",
        "Only the candidates' shape vectors are of the archive's vintage. The candidate set C(T) (WPP 2024 population ≥ 1 M at T plus a "
        "growth window) and the prototype set P(T) (top-decile GDP windows; WPP 2024 pyramids) are held at the main run's values, as "
        "pre-registered, so the check isolates the demographic-revision channel and does not re-run the full backtest.",
        "σ (sigma.json) is the WPP 2024 corpus's; the archive vectors are measured with the main run's yardstick, which is the "
        "quantity of interest (would the same rule, applied to the numbers available at T, have chosen the same countries?).",
        "Predecessor states (Sudan (Former) → SDN; Serbia and Montenegro → SRB) stand in for successors that have no archive row; their "
        "archive vectors describe a larger territory than the WPP 2024 back-series for the successor. Candidates without any archive "
        "row (e.g. SSD in WPP 2010; TWN in WPP 2000/2002) are dropped from the archive-side set, which can only lower the Jaccard.",
        "WPP 2000 for T = 1990/1995 and WPP 2010 for T = 2005 are what PREREG §8 prescribes (the revision current for T ≤ 2000 / ≤ 2010), "
        "not the revision current at those T's (WPP 1990/1994/2004 exist only as Excel zips and were not used).",
        "Jaccard is a set statistic on k ids: one swapped country changes k = 10 Jaccard from 1.00 to 0.82 and k = 5 from 1.00 to 0.67; "
        "the k = 5 rows are secondary and no threshold was pre-registered for them.",
    ] + ([] if self_ok else ["SELF-CHECK FAILED: the re-implementation did not reproduce every recorded WPP 2024 lookalike set — the Jaccard rows are not comparable."])
    run = results.run_metadata(seed=lk.SEED, B=0)
    doc = {"_meta": {"generated_at": run["generated_at"], "git_rev": run["git_rev"], "script": "scripts/vintage_check.py", "prereg_section": "§8",
                     "threshold_jaccard_k10": vg.THRESHOLD_JACCARD, "ks": list(vg.KS), "metric": "blend", "sigma_l2_two_sex": corpus.sigma["l2"]["2"],
                     "sigma_w1sex_two_sex": corpus.sigma["w1sex"]["2"], "revision_rule": "WPP 2000 for T <= 2000; WPP 2010 for 2000 < T <= 2010",
                     "primary_T": list(vg.PRIMARY_T), "T_values": Ts, "robustness": [f"{T}:{rev}" for T, rev in robust],
                     "backtest_run": ((backtest or {}).get("_meta") or {}).get("run"), "self_check_passed": self_ok},
           "sources": sources, "bin_alignment": " / ".join(sorted(bin_notes)), "mapping": mapping, "per_T": per_T, "robustness": robustness,
           "summary": vg.summarise(per_T), "caveats": caveats}
    out_dir.mkdir(parents=True, exist_ok=True)
    lk.dump_json(doc, out_dir / "vintage_check.json")
    (out_dir / "RESULTS_vintage.md").write_text(vg.render_vintage_md(doc))
    s = doc["summary"]
    print(f"self-check reproduced recorded WPP 2024 sets: {self_ok}")
    for tkey, d in sorted(per_T.items(), reverse=True):
        print(f"T={tkey} WPP {d['revision']}: " + "; ".join(f"{n} J10={c['k']['10'].get('jaccard')} J5={c['k']['5'].get('jaccard')}" for n, c in d["queries"].items())
              + f"; revision L2 median={d['revision_size'].get('l2_median')} max={d['revision_size'].get('l2_max')} ({d['revision_size'].get('l2_max_iso3')})")
    print(f"expectation (k = 10 Jaccard ≥ {s['threshold']}): {s['cells_met']}/{s['cells']} cells met; Query B at every T: {s['B_k10_met_at_every_T']}"
          + (f"; not met: {s['not_met']}" if s["not_met"] else ""))
    print(f"wrote {out_dir / 'vintage_check.json'} and {out_dir / 'RESULTS_vintage.md'}")
    return 0 if self_ok else 1


if __name__ == "__main__":
    sys.exit(main())
