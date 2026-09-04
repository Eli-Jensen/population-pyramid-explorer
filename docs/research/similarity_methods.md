# Shape similarity between population pyramids: definition, measurement, retrieval method

Author: ML-researcher subagent, 2026-09-04. All numbers below were computed on Eli's local
`~/Projects/pyramid-econ/data/processed/wpp2024_population_age5.parquet` (35,787 pyramids = 237 ISO3 entities x 151 years x 21 five-year bins x 2 sexes). Experiment scripts: `scratchpad/research/exp1.py … exp4.py`, `bench.mjs` (same directory as this file).

## 0. TL;DR

* A pyramid is 42 numbers. "Shape" = the 42-vector after dividing by total population. Every method is a metric on that vector; rendering it to pixels and embedding the pixels can only lose or re-weight information, never add it.
* Tested 10 candidate metrics on the whole dataset. Recommended DEFAULT: a two-term blend, `d = 0.5·L2(shares)/0.0834 + 0.5·W1sex/11.34` (constants = median random-pair distances). It scores 0.996 on the temporal-continuity test, ranks ITA #1 / PRT #3 / DEU #6 for Japan 2024, MLI #1 / TCD #2 / SOM #3 for Niger 2024, ARE #1 / BHR #2 for Qatar 2024, and puts Qatar as the single most isolated pyramid of 2024 by a factor of two.
* Pure 1-D Wasserstein on the total age distribution, although the textbook "shape" metric, collapses to |Δ mean age| in practice (Spearman 0.989 with |Δmean| on this data; W1 ≥ |Δmean| always, with equality when CDFs don't cross). Offer it as a toggle labelled "age-shift distance (years)", not as the default.
* Image embeddings (CLIP/SigLIP/DINO/chart encoders) are the wrong default: the information is already in hand, the embedding is opaque, and known failure modes (CLIP-blind pairs, VLM blindness on simple geometry, chart benchmarks) land exactly on the fine-grained bar-length comparisons this feature depends on. They have one genuine niche (text/metaphor queries such as "beehive", "urn"; querying from a screenshot) and can earn a place only by beating the vector metric under the evaluation protocol in §6, including a rendering-invariance test. The experiment costs ~30 min on the Mac; worth running once for the record.
* Brute force is the architecture: 0.9 ms/query for L2 over all 36k pyramids in Node typed arrays, 0.5 ms for W1, 7.6 ms for a full argsort; data payload 6 MB float32 (3 MB uint16). No vector DB, no server, no precompute needed. Even 768-d image embeddings (110 MB f32, 18.5 ms/query in JS) would not need one.
* Important UX finding: in "any year" mode the medium-variant projections dominate (Japan 2024's nearest any-year non-Japan pyramid is Latvia 2064 at d=0.122; nearest observed-era one is Italy 2023 at 0.244). Default "any year" to observed years (1950-2023) plus the current year, with "include projections" as a toggle.

## 1. Setup and what "shape" means

Data: for each (iso3, year) a vector `m ∈ R^21` (male counts by 5-year bin, 0-4 … 100+) and `f ∈ R^21`. `T = Σm + Σf`.

Representations used:
* `s42 = [m/T ; f/T]` (42-d, sums to 1) — shares of total, sex-specific. Recommended base representation.
* `s21 = (m+f)/T` (21-d) — total age distribution; `C21 = cumsum(s21)` its CDF.
* `CM = cumsum(m/T)`, `CF = cumsum(f/T)` — per-sex CDFs of shares-of-total (they end at the male share and female share respectively, not at 1).

"Shape" for this app: size-invariant (divide by T — done), NOT age-shift-invariant (an older pyramid is a different shape), NOT sex-swap-invariant (Qatar's male bulge is the point), tolerant to a bulge moving by one bin (adjacent bins are correlated because cohorts age through them). Those requirements dictate the metric choices below.

Facts about this dataset that matter for design:
* Intrinsic dimensionality is low: PCA of `s42` — PC1 78.7 %, PC2 10.3 %, PC3 3.3 %; 3/5/12/26 components for 90/95/99/99.9 % of variance. PC1 is the young-old axis. Top-5 same-year neighbor overlap between full-42-d L2 and PCA-k L2: 0.47 (k=3), 0.67 (5), 0.83 (8), 0.92 (12). So the distinguishing information lives in the tail components; any method that keeps only the "gestalt" loses the neighbor ranking.
* Global rank correlation between all metrics tested is 0.93-1.00 (Spearman over same-year candidates, 200 random queries) because the age axis dominates everything. Metrics differ where it matters, in the top-10; evaluate on top-k, not on global correlation.
* Aggregates: the parquet keeps only LocTypeID 4 (237 countries/areas). The raw `WPP2024_PopulationByAge5GroupSex_Medium.csv.gz` also has ~52 aggregates (LocTypeID 2/3/5/12/13/14: World, SDG regions, income groups, ADB regions …; ISO3_code empty). Re-parse with `LocTypeName` to include them behind a flag.
* Microstates: 37 entities have < 100k people in 2024 (VAT is 0 after rounding to thousands; NIU 1k, TKL 2k, MCO 38k, LIE, SMR, AND, …). Without a threshold, VAT is the #1 "most isolated" pyramid of 2024 and MCO is #5.
* Estimates vs projections: years ≤ 2023 are estimates, 2024-2100 medium-variant projections. Projections converge in shape (fertility and mortality assumptions homogenize), which is why they flood any-year results.

## 2. Direct metrics on normalized shares

Notation: `a, b` are two pyramids; `k` indexes bins; bin width `h = 5` years.

### 2.1 L2 and cosine on s42

`L2(a,b) = ‖s42_a − s42_b‖₂`; `cos(a,b) = 1 − ⟨s42_a, s42_b⟩ / (‖s42_a‖‖s42_b‖)`.
Cosine and L2 are interchangeable here (Spearman 1.00, identical top-8 lists) because all share vectors have nearly the same norm. Use L2 (cheaper, interpretable: RMS per-bin share gap = L2/√42).
Behavior: sharpest "fingerprint" metric — temporal continuity 0.994-0.996 (nearest neighbor in any-year mode is the same country ±1 year; median rank of the adjacent year is 1, p90 = 1). Canonical ranks: JPN→{ITA 1, PRT 2, GRC 3, DEU 9}; NER→{MLI 1, TCD 2, SOM 3}; QAT→{ARE 1, BHR 2}; USA→{NZL 1, AUS 2, NOR 3, GBR 4, CAN 5}; DEU→{AUT 1, ITA 4, NLD 9}; KOR→{TWN 1, JPN 52}.
Weakness: bin-position blind. Two pyramids whose only difference is a bulge one bin apart score exactly the same as a bulge six bins apart (measured on synthetic data: L2 = 0.0673 in both cases; W1 = 0.24 y vs 1.43 y).

### 2.2 1-D Wasserstein-1 (earth mover's distance) on the age distribution

Closed form on a line: `W1(a,b) = ∫|F_a(x) − F_b(x)| dx = h · Σ_k |C_a,k − C_b,k|`, i.e. the L1 distance between CDFs, in units of years. (Bins are treated as point masses at bin boundaries; with interpolated CDFs the integral is exact. Either is fine at 5-year resolution.) Cost: one cumsum + 21 abs-diffs; 0.63 ms/query in numpy, 0.52 ms in Node.

Why it "respects shape" better than L2: W1 is the minimum cost of moving probability mass, where cost = distance moved in years. Shifting a bulge by one bin moves 5 % of the mass 5 years → 0.25 y; shifting it by six bins costs 6x more. L2 sees both as "one bin lost, one bin gained" and cannot tell them apart. W1 is therefore the right notion when comparing pyramids at different binnings or when cohorts have aged a few years between two snapshots.

What actually happens on this data — a fact that must shape the design:
* `W1(a,b) ≥ |mean_age_a − mean_age_b|` always (Jensen / Kantorovich-Rubinstein with the 1-Lipschitz test function f(x)=x; verified: min over 3000 random pairs of W1 − |Δmean| = −6e-14), with equality iff the two CDFs never cross. Age-distribution CDFs of two countries cross rarely and shallowly, so W1 ≈ |Δ mean age|. Measured: Spearman(W1 rankings, |Δmean age| rankings) = 0.989 over same-year candidates. This is the same mathematics as the 2025 result that the Wasserstein distance between age-at-death distributions equals the life-expectancy gap when survivorship curves do not cross (arXiv 2508.17235).
* Consequences: temporal continuity drops to 0.738 (a Sahel country's neighbour is another Sahel country before its own next year — Niger→Somalia 2024 is 0.20 y apart), USA→{GBR 12, CAN 25}, DEU→{AUT 11, NLD 28, ITA 15}, JPN's top-6 gains Martinique and Hong Kong (right median age, wrong fine structure). It also silently discards sex.
* Verdict: W1 on the total age distribution is a one-number metric in disguise. Keep it as a toggle, display it in years ("mass must move 1.97 years on average to turn Japan 2024 into Italy 2024"), and use it as an explainer, but do not make it the default.

### 2.3 Jensen-Shannon and Hellinger on s42

`JS = sqrt(½KL(a‖m) + ½KL(b‖m))`, `m=(a+b)/2`; `Hel = ‖√a − √b‖₂/√2`. Both are √-domain metrics: they up-weight small bins (85+, 90+, 95+, 100+) relative to L2 because the square root compresses large shares. Results are nearly identical to each other (Spearman 1.00) and to L2 (0.97), with slightly better JPN→DEU (6 vs 9) because Germany's old-age tail matches Japan's. Continuity 0.999. Reasonable toggle ("emphasize the elderly tail"); not needed as default. JS requires clipping zeros (100+ bin is 0 for small countries in 1950).

### 2.4 DTW

Dynamic time warping over the 21-bin sequence with a Sakoe-Chiba band w=3 was tested on the 2024 same-year candidates (pure Python, 11 ms for 199 candidates). JPN top-8: ITA, GRC, BGR, PRT, HRV, POL, ESP, SRB; USA top-8: AUS, NZL, MNE, NOR, MKD, BRB, GBR, DNK. It warps age, which is exactly the invariance we do not want (a 30-year-old cohort is not a 40-year-old cohort), it is not a metric (triangle inequality fails), and it costs O(21·w) per pair in a Python loop or a custom JS kernel. W1 and smoothed L2 give the adjacency tolerance DTW is usually reached for, at lower cost and with a metric. Not recommended.

### 2.5 Gaussian-smoothed L2 (kernel/MMD view)

`L2_σ(a,b) = ‖G_σ * s42_a − G_σ * s42_b‖₂` with a Gaussian kernel of σ bins applied within each sex's 21 bins. This equals a maximum-mean-discrepancy with kernel `G_σ * G_σ` (Gaussian of width σ√2): a proper metric that scores a one-bin shift as small and a six-bin shift as large, while keeping the full vector. Measured: σ=1 → continuity 0.986, JPN→{ITA 1, PRT 2, DEU 4}, DEU→{AUT 1, ITA 5, NLD 15}, NER→{MLI 1, SOM 2, TCD 3}, QAT→{ARE 1, BHR 2}, USA→{NZL 1, AUS 2, NOR 3, GBR 4, CAN 7}. σ=2 over-smooths (continuity 0.929, DEU→AUT 5). σ=1 is a clean single-formula alternative to the blend in §2.8.

### 2.6 Treatment of sex

Three options, all tested:
1. Concatenate male and female shares of total (s42) and use any vector metric. Sex imbalance enters as bin-by-bin gaps. Works: Qatar 2024's isolation score (mean distance to its 5 nearest 2024 countries with ≥100k people) is 0.073 vs 0.051 for the runner-up (ARE, KWT); the top-8 isolated are QAT, ARE, KWT, OMN, SAU, BHR, MDV, SGP.
2. Total-age metric + explicit sex term: `W1(s21) + λ · Σ_k w_k |r_a,k − r_b,k|` where `r_k = m_k/(m_k+f_k)` is the male share within bin k and `w_k = (s21_a,k + s21_b,k)/2` weights bins by how many people are in them (so noisy 95+ bins do not dominate). With λ = 50 y: continuity 0.982, JPN→{ITA 1, GRC 2, PRT 3, DEU 4, KOR 7}. Most explainable ("working-age sex ratio 3.2 vs 1.03"). λ is a free knob.
3. Per-sex CDFs of shares-of-total: `W1sex(a,b) = h · Σ_k (|CM_a,k − CM_b,k| + |CF_a,k − CF_b,k|)`. Because CM ends at the male share, a pyramid with 76 % males vs one with 50 % accumulates a ~0.26 gap across the upper bins — equivalent to transporting the surplus male mass to the top of the age axis (an "unbalanced" transport with the excess parked at age 105). Effect: Qatar's isolation becomes 13.7 vs 4.8 for the runner-up (ARE); continuity 0.942; JPN→{ITA 1, GRC 2, PRT 3, DEU 4}; USA→{AUS 1, NZL 2, NOR 3}. This is the sex-aware term used in the default blend.

Gulf states under the recommended blend (2024, ≥100k): QAT is #1 isolated (1.04), then ARE 0.53, KWT 0.50, SAU 0.46, HKG 0.45, OMN 0.44, MAC, SGP — the Gulf migrant-male cluster plus the female-domestic-worker/expat cities. Without the threshold VAT (0.96) and MCO (0.50, rank 5) join them, which is the intended "flag as different" behavior.

### 2.7 Normalizing, smoothing, single-age vs 5-year

* Normalize by T (sum of all 42 counts). Do not per-bin standardize (z-scoring bins destroys the distributional meaning and inflates the 100+ bin).
* Do not normalize the x-axis per pyramid to "widest bar = 100 %" for the metric; that is a rendering choice (populationpyramid.net does it) and it changes the vector (e.g. Niger's 0-4 bar vs Japan's 50-54 bar). If a "widest-bar-normalized" view is wanted for humans, keep the metric on shares.
* Smoothing: none needed for the 5-year data; WPP is already model-smoothed. σ=1 kernel is a metric design choice (§2.5), not denoising.
* Single-age: WPP2024 publishes `PopulationBySingleAgeSex_Medium_{1950-2023,2024-2100}.csv.gz` (101 ages × 2 sexes = 202-d). It adds cohort-level detail (1959-61 famine notch in China, war notches) that raises fingerprint sensitivity and makes the continuity test trivially perfect, but it does not change who the top-10 same-year neighbours are in any way a human would notice, and it quadruples payload. Recommendation: 5-year bins for the metric; optionally single-age for rendering the selected pyramid only. If single-age is ever used for the metric, use W1 or σ-smoothed L2, never raw L2 (raw L2 on 101 ages is dominated by year-to-year noise).
* Binning-robustness for external inputs: any binning can be mapped to the 21-bin grid by interpolating the CDF at the 5-year cut points; W1 is binning-independent by construction. That removes the "images are robust to different binning" argument for image embeddings.

### 2.8 The recommended default: normalized blend

```
d(a,b) = 0.5 · L2(s42_a, s42_b) / σ_L2  +  0.5 · W1sex(a,b) / σ_W1
σ_L2 = 0.0834   (median L2 over random pairs, all years)
σ_W1 = 11.34 y  (median W1sex over random pairs, all years)
```
Rationale: the L2 term is the fingerprint (fine structure, bin-by-bin), the W1sex term is the transport term (adjacent-bin tolerance + strong sex imbalance signal). Normalizing each by its random-pair median makes the two terms commensurable and makes the resulting number interpretable as "fraction of a typical random-pair distance". Measured: continuity 0.996; JPN→{ITA 1, GRC 2, PRT 3, PRI 4, ESP 5, DEU 6}; NER→{MLI 1, TCD 2, SOM 3}; QAT→{ARE 1, BHR 2}; USA→{NZL 1, AUS 2, NOR 3, GBR 4, ALB 5, CAN 6}; DEU→{AUT 1, ITA 5, NLD 14}; KOR→{TWN 1, ESP 2, JEY 3, AUT 4, SVN 5, CHE 6; JPN 43}.
Percentiles of d over random same-year pairs (≥100k): p1 0.09, p5 0.16, p10 0.22, p25 0.36, p50 0.69, p75 1.16, p90 1.52, p99 2.12, max 3.22. Japan→Italy 2024 = 0.231 (11.5th percentile → "closer than 88 % of random pairs"); Japan→Niger = 2.38 (99.6th). Show that percentile in the UI rather than the raw number.
α = 0.3 gives near-identical results (continuity 0.992, JPN→DEU 4). α and (if used) σ are the only knobs; fit them on Eli's triplet judgments (§6).

Time-shift results under the blend (best-matching year of each other country for Japan 2024): ITA 2028 (0.20), DEU 2040 (0.17), THA 2055 (0.13), TWN 2035 (0.26), KOR 2034 (0.32), CHN 2044 (0.30), BRA 2072 (0.16), USA 2091 (0.37), IND 2100 (0.25), NGA 2100 (1.01 — never). And KOR 2050 ≈ JPN 2050-2053 (all metrics; not "Japan 2040s" — Korea's ageing overtakes Japan's, so the time-shift test in §6 should accept JPN ∈ [2040, 2060]). KOR 2024 ≈ JPN 2003-2007; CHN 2024 ≈ JPN 1997-2003; IND 2024 ≈ CHN 1999-2000; NER 2024 ≈ BGD 1975-1984.

## 3. Engineered demographic features

Compute once per pyramid, ship alongside the vector, use for explanations, filters and a "coarse" toggle:
* median age (linear interpolation within the bin containing CDF = 0.5), mean age, shares under-15 / 15-64 / 65+, child dependency (u15/wa), old-age dependency (65+/wa), total dependency, base slope `s[0-4]/s[20-24]` (<1 = shrinking base), `s[0-4]/s[10-14]` (recent fertility trend), peak bin (argmax), working-age sex ratio `Σm[20-59]/Σf[20-59]`, overall sex ratio, 80+ share, an "hourglass" score (min of 20-34 share relative to neighbours).
* Reference values (2024): JPN median 50.4, u15 0.114, 65+ 0.298, ODR 0.51, base 0.66, WA sex ratio 1.03; ITA 48.8 / 0.119 / 0.246 / 0.39 / 0.67 / 1.02; DEU 46.3 / 0.139 / 0.232 / 0.37 / 0.91 / 1.04; NER 16.5 / 0.466 / 0.026 / 0.05 / 1.93 / 1.04; QAT 34.5 / 0.151 / 0.017 / 0.02 / 0.98 / 3.22; KOR 2050 57.8 / 0.078 / 0.397 / 0.76.
* As a metric: L2 on 8 z-scored features has Spearman 0.94 with the L2_42 ranking and 0.87 with W1; |Δ median age| alone has 0.965 with W1 (again: W1 ≈ mean-age difference). So the features reproduce the coarse ordering but not the top-10; use them to explain, not to rank. Exception: a user-facing "similar median age" or "similar dependency ratio" sort is a legitimate toggle because it is transparent.
* Explainer template: "Similar because both have median age ≈ 49, 65+ share 25-30 %, a shrinking base (0-4 is 2/3 of 20-24) and no sex imbalance. Main difference: Germany's base is flatter (0.91 vs 0.66)." Generate by picking the 2-3 features with the smallest |Δz| and the 1-2 with the largest.
* Stage typology (expansive / constrictive / stationary, textbook labels; the 2025 zoo-population paper arXiv 2508.03788 uses a finer rule-based set: pyramid, inverted pyramid, bell, column, diamond, hourglass, plunger). A rule set that works on WPP: expansive if `s[0-4] > s[10-14] > s[20-24]` and u15 > 0.30; constrictive if `s[0-4] < s[20-24]` and 65+ > 0.12; stationary otherwise; add "male-skewed" if WA sex ratio > 1.3; "inverted/urn" if the modal bin is ≥ 45. Show the label as a badge and allow filtering neighbours by it; do not put it in the distance.

## 4. Learned embeddings from the vectors

* PCA: see §1 — 12 components reproduce 92 % of full-L2 top-5 neighbours; useful only as a 2-D map for the UI (PC1 = age, PC2 ≈ base-vs-middle bulge), not as a retrieval space.
* Autoencoder / VAE: with N = 36k, D = 42, intrinsic dim ≈ 5-12 and no label, a nonlinear bottleneck can only learn a reparametrization of the manifold already captured by PCA + the metric; nearest-neighbour search in 42-d is already 1 ms. No gain, adds an opaque training step.
* Contrastive (SimCLR/triplet) needs a definition of positives. The natural one — same country, |Δyear| ≤ k — learns country identity (the fingerprint), which is the opposite of the goal; positives = "demographer says similar" is exactly the label set we do not have except via Eli's triplets. Conclusion: the only learning worth doing is metric weighting with ≤ 3 parameters (blend α, smoothing σ, sex weight λ, possibly per-bin weights w_k regularized toward 1) fitted by maximizing agreement with the human triplets in §6. That is a grid search, not a model.
* If a "learned" component is ever wanted for a UI feature, a 2-D UMAP/t-SNE of s42 coloured by year with country trajectories drawn as paths is the one that adds something humans cannot get from a list.

## 5. Eli's proposal: render each pyramid, embed with a multimodal model

### 5.1 What the embedding can and cannot capture
The render is a deterministic, injective map r: R^42 → pixels (for a fixed style). An image embedding is g(r(v)); its induced distance `d_img(u,v) = ‖g(r(u)) − g(r(v))‖` is some fixed, opaque function of the same 42 numbers. It cannot contain information absent from v; the only question is whether g's implicit metric on the pyramid manifold is a better shape metric than a designed one. Two structural reasons it is unlikely:
* The pooled embedding of any two pyramids rendered in one style shares an enormous common component ("a two-sided horizontal bar chart, blue and pink, with axis labels"). Shape variation is confined to a small subspace of the 768/1024-d space, so cosine similarities will be compressed into a narrow band (expect ~0.85-0.98 for all pairs) and the ranking becomes sensitive to whatever else moves the vector: anti-aliasing, bar gaps, the axis-scale choice.
* CLIP-style training optimises for caption-level semantics; bar-length comparisons at the 1-2 % level are the kind of fine-grained, geometric information these encoders demonstrably under-represent in the pooled token.

### 5.2 Rendering sensitivity (must be controlled, cannot be eliminated)
* Text: CLIP reads text in images (multimodal "typographic" neurons; Goh et al. 2021). Any country name, year, or population number in the render will dominate the embedding — pyramids would cluster by label text. Renders must be text-free, no legend, no tick labels.
* Axis scale: fixed absolute x-axis (e.g. 0-10 % per bin) vs per-pyramid autoscale (widest bar fills the width, as populationpyramid.net does) produces different images for the same vector. Autoscale removes real information (how peaked the pyramid is) and must not be used for the metric render.
* Colours, bar gaps, aspect ratio, resolution: each changes the vector; the correct test is whether nearest-neighbour lists are invariant to them (§5.5). ViT-L/14 at 224 px sees 16×16 patches: 21 bins over ~200 px ≈ 9.5 px per bar ≈ 1.5 bars per patch; bar length quantised to patch columns of 14 px on a ~100 px half-width ≈ 14 % of the max bar per patch. Sub-patch detail survives in the patch embedding but pooled representations are not trained to preserve it.
* Sexes: side-by-side rendering keeps sex; a symmetric render (total by age) loses it, which is a choice the vector metric makes explicitly (§2.6) and the image metric makes implicitly.

### 5.3 Known evidence
* MMVP / "Eyes Wide Shut" (Tong et al., CVPR 2024): systematic "CLIP-blind pairs" — image pairs with near-identical CLIP embeddings but different content; 9 visual patterns (orientation, counting, relative position, colour/appearance, state, …); 7 of 9 not fixed by scaling CLIP. Bar-length ordering and small positional differences are in the failing families. DINOv2 was used to *detect* CLIP-blind pairs, i.e. it is better at low-level geometry.
* "Vision language models are blind" (Rahmanzadehgervi et al., ACCV 2024, BlindTest): VLMs average 58 % on trivially easy geometric tasks (do two lines intersect, count circles). Linear probes show the encoders contain the information; the pooled/decoded representation does not surface it.
* "On erroneous agreements of CLIP image embeddings" (arXiv 2411.05195): same conclusion from the other side — the encoder tokens retain query-relevant detail, the CLIP embedding (the thing you would put in a vector index) fails to extract it; patch tokens + position embeddings are what recover it.
* Chart benchmarks — CharXiv (NeurIPS 2024), ChartMuseum (2025), EncQA (2025), Chartographer counterfactual charts (2026): even frontier VLMs degrade sharply on unlabeled charts and on value extraction (40-60 % accuracy drops reported for unlabeled complex charts); failures are traced to the visual encoder and to extraction bottlenecks.
* Multimodal chart retrieval (NAACL 2024): derendering charts to tables with DePlot and retrieving on the table is competitive with or better than end-to-end image retrieval — i.e. the numbers are the better representation, and chart-understanding models are trained to *invert* the rendering. Eli already has the inverse.
* Chart2Vec (2023): the one published "chart embedding" combines visual features with the chart's structural/data specification, because pixels alone were insufficient.

### 5.4 Model-by-model notes (for the experiment, not the product)
* CLIP ViT-L/14 (336): baseline; strongest text-reading bias; expect the narrow-band problem.
* SigLIP 2 (Feb 2025, arXiv 2502.14786): sigmoid loss, NaFlex variable resolution, better localization/dense features than SigLIP; still caption-semantic. Best of the contrastive family to try.
* DINOv2 / DINOv3 (Aug 2025, arXiv 2508.10104): self-supervised, no text bias, strong dense/geometric features; the most plausible image encoder for "looks like" since it does not know what a chart is and therefore cannot be distracted by chart semantics. Use the CLS + mean-pooled patch tokens.
* jina-clip-v2, nomic-embed-vision-v1.5: CLIP-family; nothing chart-specific.
* Voyage multimodal-3 (Nov 2024), Cohere Embed v4 (Apr 2025), Gemini Embedding 2 (Mar 2026, arXiv 2605.27295): API-only, document/screenshot oriented (tables, slides); per-image cost is negligible at 36k images but they cannot run in a static Svelte site, add a dependency, and their chart behaviour is only benchmarked on document retrieval (cross-modal Recall@10 in the 76-82 % range on generic document sets), not on shape similarity.
* Chart-specialized: Pix2Struct / MatCha / DePlot (chart→table), UniChart (EMNLP 2023), ChartGemma (2024), ChartMoE (ICLR 2025): encoder-decoders trained to read values off charts. Their encoders are not trained as similarity spaces; their *decoders* are the only reason they are good at charts, and their output on a pyramid render is… the 42 numbers. Use them only for the screenshot-query feature (§5.5c), and even then a frontier VLM (Claude/GPT-4o-class) asked to emit the 21×2 table is simpler.

### 5.5 Where image embeddings could be genuinely valuable
a) Metaphor / text queries: "pyramids that look like a Christmas tree / beehive / urn / kite / hourglass". A CLIP-family text encoder can be pointed at text-free renders; zero-shot reliability on these metaphors is unknown and probably poor. Cheaper and explainable alternative: define each metaphor as a prototype (a hand-picked exemplar pyramid or a rule from §3) and rank by the vector metric; or let an LLM translate the phrase into feature constraints. Only if Eli wants free-text queries beyond a fixed vocabulary does the cross-modal route pay.
b) Human gestalt: if the human triplet test (§6) shows the vector metric disagreeing with Eli's eye in a consistent way, a DINO embedding might capture that gestalt; but first try re-weighting bins / α / σ, which is a 3-parameter fit.
c) Querying from a picture you do not have numbers for (a textbook scan, a sub-national pyramid from a PDF, a screenshot of populationpyramid.net): derender to numbers (VLM → table, or a tiny bar-extraction script), then use the vector metric. Image-embedding the screenshot and searching image space would also work but is strictly worse once the numbers are recovered.
d) Different binning: not a real advantage — CDF interpolation solves it (§2.7).

### 5.6 The evaluation under which it could earn a place
Run the identical protocol of §6 on three embeddings (CLIP ViT-L/14, SigLIP 2 So400m, DINOv2/3 ViT-L) of text-free standardized renders (fixed x-axis 0-10 % per bin, 336×336, sexes side by side, single colour each side, no gaps), plus:
* Rendering-invariance test: re-render 2,000 random pyramids in style B (different colours, 2-px bar gaps, 256 px, 4:3 aspect). Compute same-year top-10 lists in style A and style B. Require Jaccard overlap ≥ 0.9 and cross-style self-match rank = 1 for ≥ 99 % (the pyramid rendered in style B must find itself among style-A renders). If this fails the method measures rendering, not shape, and is disqualified before any similarity judgment.
* Dynamic-range test: report the 1st-99th percentile spread of cosine similarity over random pairs; if it is < 0.1 the ranking is fragile.
* Then compare on continuity, canonical precision@k, outlier isolation ranks, and triplet agreement against the blend. It earns a place only if triplet agreement with Eli exceeds the vector metric's by a margin larger than the 20-triplet noise (§6.4) and it passes the invariance test.
Cost: 36k matplotlib Agg renders ≈ 10-15 ms each ≈ 8 min; ViT-L on Apple silicon via MPS ≈ 30-60 img/s ≈ 10-20 min; embeddings 36k × 768 fp16 = 55 MB. An afternoon. The report's prediction: fails the invariance test for CLIP, passes marginally for DINO, and neither beats the blend on the canonical set. Worth running once precisely because the prediction is falsifiable.

## 6. Hybrid recommendation and evaluation protocol

### 6.1 Metric menu
| key | definition | UI label | role |
|---|---|---|---|
| `blend` | 0.5·L2/σ_L2 + 0.5·W1sex/σ_W1 | "Shape (default)" | default |
| `l2` | L2 on s42 | "Bin-by-bin" | toggle |
| `l2s1` | L2 on σ=1 smoothed s42 | "Bin-by-bin, shift-tolerant" | toggle / alt default |
| `w1` | W1 on total age (years) | "Age-shift distance (years)" | toggle + explainer |
| `w1sex` | per-sex CDF W1 (years) | "Age-shift incl. sex" | toggle |
| `hel` | Hellinger on s42 | "Emphasize elderly tail" | optional |
| `feat` | L2 on z-scored 8 features | "Summary statistics" | optional, explainable |
Every result row shows: percentile band of `blend`, W1 in years, Δ median age, Δ 65+ share, Δ WA sex ratio, and the stage badge.

### 6.2 Metrics
* Temporal continuity (any-year mode, self excluded): C1 = P(NN is same country and |Δy| ≤ 1); C5 = P(adjacent year is in the top 5). Targets: C1 ≥ 0.95, C5 ≥ 0.99. Measured: blend 0.996 / ≈1.0; L2 0.994; W1 0.738 / ~0.9. Note the caveat: C1 rewards fingerprint sensitivity, so a low C1 alone does not make a metric wrong — but it proves that any-year results MUST be deduped per country and exclude self, otherwise the top-k is the query's own neighbouring years (verified: Japan 2024 any-year raw top-5 = JPN 2025, 2023, 2026, 2022, 2027).
* Canonical groups (2024 unless noted), precision@5 and mean reciprocal rank per query, computed on same-year candidates with pop ≥ 100k, own country excluded:
  - G-aged-Europe: JPN, ITA, DEU, PRT, GRC, ESP, HRV, BGR, FIN, AUT, SVN (measured blend MRR: JPN→ITA 1.0)
  - G-Sahel: NER, TCD, MLI, SOM, COD, AGO, UGA, BDI, AFG
  - G-Gulf-migrant: QAT, ARE, BHR, KWT, OMN, SAU
  - G-Anglo-Nordic: USA, AUS, NZL, GBR, CAN, NOR, SWE, IRL
  - G-East-Asia-ultra-low: KOR, TWN (JPN deliberately NOT in this group — measured rank 37-52 under every metric; JPN 2024 ≈ KOR 2034)
  - G-fast-transition: CHN, THA, CUB, VNM? (VNM measured rank 73-83 from CHN — Eli to decide whether the label is wrong or the metric)
  Time-shift pairs (best year must fall in window): KOR 2050 → JPN [2040, 2060]; CHN 2024 → JPN [1995, 2005]; KOR 2024 → JPN [2000, 2010]; IND 2024 → CHN [1995, 2005].
* Outliers: isolation score I(x) = mean d to 5 nearest same-year countries (≥100k). Require QAT, ARE, BHR, KWT in top-10 isolated for 2024; with threshold off, MCO and VAT in top-10. Measured: pass for blend, L2, W1sex; W1 alone puts JPN #1 (defensible: Japan is unprecedented) and QAT #2.
* Method agreement: Spearman over all same-year candidates (0.93-1.00 measured, uninformative) and top-10 Jaccard between methods (informative; report per query).
* Human triplets: see 6.4.

### 6.3 Acceptance
Default metric must pass continuity, ≥ 0.8 mean P@5 on the canonical groups, all outlier checks, and ≥ 80 % triplet agreement. Any toggle may fail continuity if labelled as a coarse metric.

### 6.4 Human-judgment check design
20 triplets is what Eli asked for; note its power: with 20 binary judgments a method at 80 % agreement has a 95 % CI of roughly 58-92 %, so 20 triplets can only distinguish methods that differ by ≥ 25 points. Suggest 50 if it takes < 15 minutes (it should; each triplet is a glance). Select triplets actively: anchor = random 2024 country (≥1M pop); candidates A, B = the top-1 of two methods that disagree (blend vs W1, blend vs image-embedding) so every triplet is informative; render all three text-free at identical scale; Eli picks "more similar to the anchor" or "tie". Score = fraction of non-tie triplets where the method's preferred candidate was chosen. Keep the judgments in a JSON file in the repo; they are the training set for α/σ.

## 7. "Most different": diverse far set

Plain farthest-k is degenerate: farthest-8 from Japan 2024 = QAT, CAF, NER, SOM, TCD, MLI, UGA, COD (one Gulf state and seven Sahel/central-African near-copies). Two remedies, both measured:

Maximal-marginal-relevance / farthest-point sampling:
```
input: query q, candidate set C (after constraints), k, beta (default 2), pool_frac (default 0.25)
pool  = the ceil(pool_frac·|C|) candidates with the largest d(q,·)          # stay "far"
S     = [argmax_{x∈pool} d(q,x)]                                            # the single farthest
while |S| < k:
    for x in pool \ S:  score(x) = d(q,x) + beta · min_{s∈S} d(x,s)        # far from q AND from what is already shown
    S.append(argmax score)
return S ordered by d(q,·)
```
Measured from Japan 2024 (blend, 2024, ≥100k): β=2, pool 0.25 → QAT, CAF, OMN, GNQ, AFG, ARE, MYT, SSD (Gulf, central Africa, Afghanistan, Mayotte, South Sudan — five distinct regimes). β=4 pool 0.5 drifts toward the Gulf (ESH, SYR, YEM, KWT, ARE). β=0.5 collapses back to Sahel. β=2 is the recommended default; expose it as "diversity" slider 0-4.

Cluster-representative variant (more explainable: "one representative per kind of difference"):
```
pool = farthest half of C; k-means (k = number of results) on s42 of pool; from each cluster return its member with the largest d(q,·)
```
Measured: QAT 2.54, CAF 2.52, MWI 2.19, OMN 2.11, GNQ 1.97, LSO 1.93, JOR 1.72, DZA 1.52 — covers Gulf, three African regimes, Jordan (refugee-inflated youth), Algeria (youth bulge + echo). k-means adds run-to-run variance; seed it. Either is < 5 ms in JS for k ≤ 10 with |pool| ≤ 60.

Simplest transparent fallback: farthest-k with a cap of 2 per UN sub-region (region table shipped with the data).

## 8. Query-constraint spec

Defaults in brackets.
* `year_mode`: `same` [default; year = the year shown, default current year 2026] | `range` (y0..y1) | `any`.
* `era`: `observed` (1950-2023) + current year [default in `any`/`range` mode] | `all` (include projections to 2100). Reason: projections converge; Japan 2024's nearest any-year non-Japan pyramid is Latvia 2064 (0.122) whereas the nearest observed is Italy 2023 (0.244). Show a "projected" badge on any result year > 2023.
* `exclude_own_country`: true [default]. When false: own-country years enter as candidates but are deduped to the single best other year and shown as a separate "your own past/future" row; enforce |Δy| ≥ 5 so the trivial ±1-year neighbours do not win (continuity 0.996 guarantees they otherwise would).
* `own_country_lookup` (the "which past year of France looks like Japan today?" feature): given query q and target country c, return argmin_y d(q, c_y) over c's years in the chosen era, with Δy = y − y_q ("France 2081 ≈ Japan 2024, +57 y").
* `entity_scope`: `countries` [default] | `countries+aggregates` (World, regions, income groups; requires re-parsing raw with LocTypeName).
* `min_population`: 100,000 [default] (drops 37 microstates in 2024; VAT rounds to 0); options 0 / 10k / 100k / 1M. Apply on the candidate's population in its own year.
* `k`: 5 [default] for similar and for different; `dedupe_by_country`: true (in range/any mode each country appears once, at its best-matching year; the second-best year is available on expand).
* `metric`: `blend` [default] + the §6.1 menu; `diversity` β for the different set [2].
* `time_shift_table` (separate panel): for every other country c meeting the constraints, y*(c) = argmin_y d(q, c_y); table sorted by d(q, c_{y*}) with Δy; this is the "any year + dedupe" result presented for all countries rather than top-k, and it is where "Korea 2050 ≈ Japan 2051" and "China 2024 ≈ Japan 1997-2003" come from.
* Result row fields: iso3, name, year, d, percentile band, W1 years, Δ median age, Δ 65+, Δ WA sex ratio, stage badge, sparkline of the neighbour pyramid.

## 9. Complexity and architecture

Measured, N = 35,787:
* numpy (M-series Mac): L2 over 42-d 1.0 ms/query f64, 0.8 ms f32; W1 21-d 0.63 ms; W1sex 1.2 ms; blend ≈ 2 ms. Full 36k×36k Gram matrix: 2.7 s and 5.1 GB — do not materialize; per-query is the design.
* Node v24 typed arrays (same as browser JS): L2 42-d 0.89 ms/query; W1 21-d 0.52 ms; full argsort of 36k 7.6 ms (use a partial top-k selection to make that ~1 ms). Constraint filtering is a mask pass, negligible. So a query with dedupe and the diverse far set is ≤ 15 ms end-to-end in the browser, well under a frame budget for interactive sliders.
* Payload: 35,787 × 42 × 4 B = 6.0 MB float32; 3.0 MB as uint16 fixed point (share × 65535, precision 1.5e-5, far below data precision); ~2 MB gzipped. Plus keys (iso3, year), populations, features, region: < 1 MB. Fits a static Svelte site with no server, matching retiremap's pattern. Precomputing every (country, year)'s default-constraint top-20 (36k queries × 2 ms = 72 s in numpy) is optional and only saves the first-query latency.
* Image-embedding scale, for the record: 36k × 768 f32 = 110 MB (55 MB f16, 9 MB after PCA to 64-d); 18.5 ms/query brute-force cosine in JS. Still no index needed.
* When a vector DB / ANN index is warranted: N·D beyond RAM or a cold-start budget (≳ 10^7 vectors, or D ≳ 1k with N ≳ 10^6), multi-tenant server QPS, or filtered search over metadata that cannot be a mask pass. None applies at 36k × 42 or 36k × 768. Sub-national data (e.g. all US counties × years ≈ 3k × 151 ≈ 470k pyramids) would still be brute-force in numpy (13 ms/query) and borderline-fine in the browser (12 ms L2), and only at ~10^7 pyramids (every municipality on Earth × years) would an HNSW index start to matter.

## 10. Pseudo-code

Build step (Python, uv):
```python
import numpy as np, pandas as pd
df = pd.read_parquet("data/processed/wpp2024_population_age5.parquet").sort_values(["iso3","year","age_start"])
keys = df[["iso3","year"]].drop_duplicates().reset_index(drop=True); N = len(keys); B = 21
M = df.pop_male.to_numpy().reshape(N,B); F = df.pop_female.to_numpy().reshape(N,B); T = (M+F).sum(1)
S42 = np.concatenate([M,F],1)/T[:,None]                  # shares of total, male bins then female bins
CM, CF = np.cumsum(S42[:,:B],1), np.cumsum(S42[:,B:],1)  # per-sex CDFs (end at male share / female share)
rng = np.random.default_rng(0); a, b = rng.choice(N,3000), rng.choice(N,3000)
SIG_L2 = np.median(np.linalg.norm(S42[a]-S42[b],axis=1))                                   # ≈0.0834
SIG_W1 = np.median(5*(np.abs(CM[a]-CM[b]).sum(1)+np.abs(CF[a]-CF[b]).sum(1)))               # ≈11.34
# features: median age (interp), u15, wa, o65, cdr, odr, base ratios, wa_sex_ratio, stage label
# export: keys + T + features as JSON; S42 as uint16 (round(S42*65535)) in a .bin; CM/CF recomputed client-side
```
Query (JS, browser; X = Float32Array N×42, CM/CF = Float32Array N×21 computed once at load):
```js
function distances(q, X, CM, CF, sigL2, sigW1, alpha=0.5) {
  const N = X.length/42, out = new Float32Array(N);
  for (let n=0; n<N; n++) {
    let l2=0, w1=0; const o=n*42, o21=n*21;
    for (let d=0; d<42; d++) { const t=X[o+d]-q.x[d]; l2+=t*t; }
    for (let k=0; k<21; k++) { w1+=Math.abs(CM[o21+k]-q.cm[k])+Math.abs(CF[o21+k]-q.cf[k]); }
    out[n] = alpha*Math.sqrt(l2)/sigL2 + (1-alpha)*5*w1/sigW1;
  }
  return out;
}
function candidates(meta, c) { // c = constraint object from §8; returns Int32Array of indices
  // mask: year filter (same/range/any), era (<=2023 or all), pop>=minPop, iso!=own unless allowed, scope
}
function topKDedupe(d, cand, meta, k) { // best year per country, then top-k
  const best = new Map();
  for (const i of cand) { const c = meta.iso[i]; if (!best.has(c) || d[i] < d[best.get(c)]) best.set(c, i); }
  return [...best.values()].sort((i,j)=>d[i]-d[j]).slice(0,k);
}
function diverseFar(d, cand, X, k, beta=2, poolFrac=0.25, pairDist) {
  const pool = [...cand].sort((i,j)=>d[j]-d[i]).slice(0, Math.max(k, Math.ceil(cand.length*poolFrac)));
  const S = [pool[0]];
  while (S.length < k) {
    let bestI=-1, bestScore=-Infinity;
    for (const x of pool) { if (S.includes(x)) continue;
      let minToS=Infinity; for (const s of S) minToS=Math.min(minToS, pairDist(x,s));
      const sc = d[x] + beta*minToS; if (sc>bestScore) { bestScore=sc; bestI=x; } }
    S.push(bestI);
  }
  return S;   // pairDist(x,s) = same formula as distances() for one pair
}
```
Metric definitions for the toggles: `l2 = sqrt(Σ(x−q)²)`; `l2s1`: precompute a smoothed copy `Xs` with kernel [0.054,0.242,0.399,0.242,0.054] applied within each sex's 21 bins (edge mode 'nearest'); `w1 = 5·Σ_k|C21−q.c21|`; `w1sex = 5·Σ_k(|CM−q.cm|+|CF−q.cf|)`; `hel = sqrt(0.5·Σ(√x−√q)²)`; `feat = sqrt(Σ((z−q.z)²))` over the 8 z-scored features.

## 11. Open questions for Eli
1. Is JPN ≈ KOR a required canonical pair? The data says no under every metric (Korea 2024 is ~Japan 2004; Korea 2050 is ~Japan 2051). If Eli's intuition says yes, that is a time-shift match, not a same-year one, and the UI should surface it via the time-shift table.
2. Should sex imbalance count as "shape"? Default here says yes (Qatar is the most different pyramid on Earth). A "sex-blind" toggle (W1/L2 on total) is cheap to keep if not.
3. Any-year default: observed years only, or include projections? Recommendation is observed-only default with a toggle; projections make every ageing country look like Latvia 2064.
4. Triplet budget: 20 (as asked) or 50 (statistically meaningful)? And should the triplets be selected where methods disagree (informative) or uniformly at random (unbiased but mostly trivial)?
5. Is the image-embedding experiment worth an afternoon for the record (recommended: yes, once, with the invariance test), or should it be skipped entirely?
6. Include aggregates (World, regions, income groups) as candidates, as queries, or both?
7. Single-age data: download the two ~300 MB single-age files for rendering detail, or stay at 5-year bins everywhere?

## 12. Sources
* Tong et al., "Eyes Wide Shut? Exploring the Visual Shortcomings of Multimodal LLMs" (CVPR 2024): https://arxiv.org/abs/2401.06209 ; MMVP page https://tsb0601.github.io/mmvp_blog/
* Rahmanzadehgervi et al., "Vision language models are blind" (ACCV 2024): https://arxiv.org/abs/2407.06581
* "On Erroneous Agreements of CLIP Image Embeddings": https://arxiv.org/abs/2411.05195
* CharXiv (NeurIPS 2024 D&B): https://arxiv.org/abs/2406.18521 ; ChartMuseum: https://arxiv.org/abs/2505.13444 ; EncQA: https://arxiv.org/abs/2508.04650 ; Chartographer (2026): https://arxiv.org/abs/2605.27311
* "Multimodal Chart Retrieval: A Comparison of Text, Table and Image Based Approaches" (NAACL 2024): https://aclanthology.org/2024.naacl-long.307.pdf
* Chart2Vec: https://arxiv.org/abs/2306.08304 ; MIEB (Massive Image Embedding Benchmark): https://arxiv.org/abs/2504.10471
* SigLIP 2: https://arxiv.org/abs/2502.14786 ; DINOv3: https://arxiv.org/abs/2508.10104 ; Gemini Embedding 2: https://arxiv.org/abs/2605.27295 ; ChartGemma: https://arxiv.org/abs/2407.04172 ; ChartMoE: https://arxiv.org/abs/2409.03277 ; UniChart: https://arxiv.org/abs/2305.14761 ; Pix2Struct: https://arxiv.org/abs/2210.03347
* Goh et al., "Multimodal Neurons in Artificial Neural Networks" (Distill 2021, typographic attacks): https://distill.pub/2021/multimodal-neurons/
* Wasserstein distance vs life-expectancy gap (2025): https://arxiv.org/abs/2508.17235
* Irpino & Verde, fuzzy clustering with adaptive L2 Wasserstein distances, applied to age-sex pyramids of 228 countries (2014 data): https://arxiv.org/abs/1605.00513
* Korenjak-Černe, Kejžar, Batagelj, "Clustering of Population Pyramids" (Informatica 2008) and "A weighted clustering of population pyramids for the world's countries, 1996, 2001, 2006" (Population Studies 2015): https://pubmed.ncbi.nlm.nih.gov/25309982/
* "A semi-automatic approach to study population dynamics based on population pyramids" (2025, rule-based shape typology): https://arxiv.org/abs/2508.03788
* UN WPP 2024 (data source): https://population.un.org/wpp/ ; reference site https://www.populationpyramid.net
* Local experiments: scratchpad/research/exp1.py, exp2.py, exp3.py, exp4.py, bench.mjs (this directory)
