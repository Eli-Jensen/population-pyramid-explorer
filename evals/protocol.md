# Similarity-evaluation protocol (pre-registered, M0)

Owner: agent D. Written 2026-09-04, before `scripts/eval_similarity.py --full` was first run on the real corpus and
before any human triplet was selected. PLAN §4.6 is the specification; this file fixes the operational choices so
the numbers in `evals/RESULTS.md` cannot drift with the metric they judge. **Per DECISION 4 the verdicts are
informational**: both `blend` and `visual` ship as user-selectable methods; `verdicts.json` decides only which of the
two image spaces is exposed by name (the better G1 continuity) and whether `blend` keeps the default.

## 1. Inputs, kept apart

| kind | file | role |
|---|---|---|
| frozen external labels | `evals/labels/korenjak_cerne.yaml` (a), `hahn_klimroth_2025.yaml` (b), `thresholds_stage.yaml` (c), `rieti.yaml` (d), `yoshida_epitome.yaml` (e) | **gates** G2(a–e); each header records source, URL, data vintage and its fallback status (PLAN §4.6 ladder). Status as committed: (a) rung 1 — 2008 Informatica lists, 2006 primary, IDB-2008 vintage, sensitivity row omitted (no IDB totals); (b) rule set, classes recomputed from WPP2024; (c) thresholds; (d) window [1985, 1995]; (e) Table 1 in full, targets corrected from the PLAN's summary (World 1990 → {IND, EGY, DZA, BGD}; World 2015 → {COL, PER, ECU, LKA, MEX, BRA, ARG}; World 2050 → {URY, PRI}). |
| hand-edited groups | `evals/canonical_groups.yaml`, `evals/time_shift.yaml` | **regression, reported only** (never gates), except the RIETI row of `time_shift.yaml`, which is G2(d) |
| corpus | `data/processed/{corpus_s42.npy, corpus_keys.parquet, entities.json, sigma.json}` | scored as built; `verdicts.json` carries `data_hash` (sha256 of the little-endian u16 corpus) |
| image spaces | `evals/embeddings/<model>.pca64.npy` (+ `.meta.json`) | metric `visual:<model>`; scored only when row-aligned with the corpus; `emb_meta_hash` per model |

Candidates everywhere: countries only, population ≥ 100k in the candidate's own year, own entity excluded
(the product default), unless a test says otherwise. `sex="2"` (two-sex 42-vector) throughout; `sigma.json` as
fitted by `metrics.fit_sigma`. Seeds are fixed (`seed=0`); query samples are drawn once per run and shared by every
metric so the comparison is paired.

## 2. Gates (numbers in RESULTS.md; verdict rules in §4)

- **G1 continuity** (self excluded, candidates = all country-years ≥ 100k, era all): for a query (c, y),
  C1 = P(nearest neighbour is the same country with |Δy| ≤ 1), C5 = P(one of the 5 nearest is). Reported for
  query years 1950–2023 (observed) and 2024–2100 (projected, inflated by convergence); **the gate applies to the
  observed span: C1 ≥ 0.95, C5 ≥ 0.99.** `trend@10` (and `path@10`) use the same definition with Δ over
  [y−10, y]; candidates need y−10 ≥ 1950.
- **G2 external labels** (same-year top-10, k = 10): (a) Korenjak-Černe 2006 four-cluster labels — class
  agreement = mean fraction of a labelled country's top-10 (among labelled countries) sharing its cluster, gate
  ≥ 0.7; 1996 and 2001 reported as sensitivity rows. Normalised P@k = hits / min(k, |G|−1) is NOT tabulated for
  these clusters: every cluster has ≥ 44 members, so min(10, |G|−1) = 10 and P@10 coincides with class agreement
  (it was printed as a second identical column in the first run and dropped in the fix wave). (b)
  Hahn-Klimroth classes computed from the 2024 rows with the buckets/tolerance fixed in the yaml — agreement ≥ 0.85.
  (c) stage (median-age rule) agreement ≥ 0.9 on 2024. (d) CHN 2020 → JPN best year (era all) ∈ [1985, 1995].
  (e) Yoshida: query World (`agg-900`) in 1990 / 2015 / 2050 against countries in 2015: ≥ 3 / ≥ 3 / both named
  countries in the top-5 — all three must hold.
- **G4 outliers**: isolation I(x) = mean d to the 5 nearest same-year countries ≥ 100k in 2024; gate = {QAT, ARE,
  BHR, KWT} ⊆ top-10. Reported: with the floor off, whether MCO and VAT enter the top-10.
- **Opposites test** (reported): 20 random 2024 anchors, β = 2 (pre-registered; the shipped default preset is
  β = 0.5 since the fix wave — a β sweep is reported beside the test), k = 5: the 5 opposites cover ≥ 3 Hahn-Klimroth
  classes and ≥ 3 UN regions (`region_locid`); β = 0 reproduces plain farthest-5 exactly; per-entity dedupe holds
  in any-year mode.
- **Method agreement** (reported): mean top-10 Jaccard over 200 random same-year queries (years 1960–2023), every
  metric × every metric, incl. `trend@10`, `path@10` and each `visual:<model>` present.
- **Regression** (reported): canonical groups — normalised P@5 and MRR per group at 2024; time-shift windows —
  y* = argmin_y d(query, target_y) over era all and whether it lands in the window.

## 3. Human triplets (M4; design fixed now, PLAN §4.6 item 8)

- Question, fixed: *"Which of A or B is more similar in shape to the anchor?"* If Q3's default is taken, the 32
  blend-vs-visual items are re-asked in a second 15-minute sitting with "looks more alike" (sides re-randomised);
  that result is published as a finding and never used for promotion.
- n = 80 unique items, stratified: 32 where A/B = top-1 of `blend` vs the best image space by G1 on the same
  anchor; 38 where A/B = top-1 of two disagreeing numeric metrics; 10 "most different" items (A/B = top-1 opposite
  under two metrics; question: which is more *different*). Anchor = random 2024 country ≥ 1M; text-free,
  identical-scale renders; answers A / B / tie.
- Reliability (single rater): 8 duplicates appended (4 blend-vs-visual, 3 numeric, 1 opposite) with A/B sides
  swapped, ≥ 30 positions later → 88 items ≈ 75 min. Sides randomised per item; order, side map and response
  time recorded in `evals/triplets.json`. Self-agreement on the 8 pairs (ties count as disagreement unless both
  are ties). **Rule: self-agreement < 6/8 ⇒ no verdict is promoted above `lab` from triplet evidence**, the α/σ/λ
  fit is reported but the shipped defaults stay α = 0.5 / σ = 1 bin. An optional second rater is reported as κ,
  never pooled.
- Agreement is pairwise for every metric: a metric agrees with a judgment if it ranks the chosen item closer to
  the anchor than the other. Ties excluded from tests, reported as counts; duplicates excluded (first response).
- Decision = paired sign test (McNemar) on discordant triplets at α = 0.05; MDE stated up front: with 32
  blend-vs-visual items one side must win ≥ 22 of the non-tie discordant items (≈ 69 %); with 80 total the
  numeric-vs-numeric comparisons resolve gaps ≥ ~20 points. Marginal CIs reported, never used for verdicts.
- α and smoothing σ (λ for `w1bal`) grid-searched leave-one-out on the numeric triplets only.

## 4. Decision rules → `evals/verdicts.json`

Verdict ∈ {default, menu, advanced, lab, rejected}, per PLAN §4.3, evaluated mechanically:

- `default` = `blend` unless a challenger passes every gate AND beats `blend` on the paired triplet test (M4).
- `menu` = passes G1 + G2 + G4 (M0) and triplet agreement ≥ 75 % on the common set (M4). **In M0, before
  triplets exist, a metric that passes G1 + G2 + G4 is written as `menu` with `provisional: true`.**
- `advanced` = passes G1 + G4 only. `lab` = fails a gate but C1 ≥ 0.8. `rejected` = C1 < 0.8, or G2 badly failed
  (Hahn-Klimroth class agreement < 0.6).
- G2 "passes" = (a) ≥ 0.7 on 2006 AND (b) ≥ 0.85 AND (c) ≥ 0.9 AND (d) in window. If (a)'s labels were
  unobtainable the ladder demotes (a) to reported; as committed, (a) IS available (rung 1) and gates.
- **Amendments recorded before the first full run (after a 3-metric smoke run, applied to every metric alike):**
  (i) G2(b) is gated at the shape-*family* level — the paper's lower/middle/upper diamond variants are one
  family ("Diamond (middle, lower and upper variants)" in its Table 1); the fine 11-class agreement is reported
  beside it. Reason: the variants are neighbours by construction, so fine-level agreement measures the bucket
  discretisation, not the metric. (ii) **G2(e) Yoshida is demoted to reported.** The paper's own metric
  (`clr` on total shares) reproduces India's 1990 distance on WPP2024 rows (0.59 vs the paper's 0.579) yet fails
  the pre-registered top-5 targets in all three years: Bolivia and Puerto Rico were revised materially between
  WPP2015 and WPP2024, so the targets are vintage-dominated and cannot separate metrics. Hits@5, hits@10 and
  the rank of every named country are still reported for every metric. (iii) The opposites test's "pass" is
  defined on the anchor means (mean fine HK classes ≥ 3 AND mean UN regions ≥ 3); the per-anchor fraction
  meeting ≥ 3/≥ 3 is reported beside it. It is a reported test either way.
- **Amendment recorded after the first full run (fix wave, 2026-09-04; changes reporting, not any gate):**
  (iv) the opposites coverage target fails for every metric and the failure is structural — the MMR pool is the
  farthest quartile, all young 'pyramid'-class countries for an old anchor, so shape-space diversity cannot buy
  class or region variety at any β. The test stays as pre-registered (β = 2) and is reported with a β sweep
  (Jaccard vs strict, raw rank, region coverage); the product presets were re-calibrated to β = 0.5 / 2 from that
  sweep (PLAN §5). `verdicts.json` gains top-level `exposed_visual` (DECISION 4, machine-readable) and
  `_meta.findings` (β sweep, W1 share of `blend` by era); the KC P@10 column is dropped (§2).
- `trend@10` / `path@10` are mode toggles, not menu entries: they carry a verdict from G1 only
  (`menu` if the observed-span C1 ≥ 0.95 else `lab`), flagged `scope: trend-mode`.
- `visual:<model>`: same rules; the pre-registered predictions in `evals/image_embeddings.md` (C1 < 0.95, HK
  agreement ≥ 0.6, expected verdict `lab`) are evaluated in RESULTS.md. Whichever image space has the higher
  observed-span C1 is the one exposed as "Visual"; the other stays URL-only.
- Every verdict is **informational** (DECISION 4); `verdicts.json` says so in its `informational` flag and records
  `data_hash`, `emb_meta_hash` per model, the sha256 of every label file, the git HEAD and the protocol stage.

## 5. Reproduction

`make labels` rewrites the label files from the transcriptions embedded in `scripts/fetch_labels.py`
(`--refetch` re-downloads and re-derives the Korenjak-Černe lists from the PDF and asserts equality);
`make eval` = `scripts/eval_similarity.py --full` → `evals/RESULTS.md` + `evals/verdicts.json`;
`uv run pytest tests/test_protocol.py` checks the scoring functions on synthetic data (fast) and, under `-m slow`,
re-derives the headline gates on the real corpus.
