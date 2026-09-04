# Literature sweep: pyramid-shape similarity + chart-image embeddings (2026-09-04)

Scope: (a) clustering/classifying countries by age structure; (b) chart embedding/retrieval with VLMs; (c) do image embeddings of rendered plots recover the data; (d) similarity search over population pyramids. Searched arXiv, Semantic Scholar, OpenAlex, Google Scholar, CrossRef, web. ~20 papers below, grouped by topic, each with takeaway + design implication.

---

## (a) + (d): Demography — clustering / distances on age structure and population pyramids

### 1. Korenjak-Cerne, Kejzar, Batagelj (2015). "A weighted clustering of population pyramids for the world's countries, 1996, 2001, 2006." *Population Studies* 69(1). https://doi.org/10.1080/00324728.2014.954597
- The canonical "cluster pyramids as data" paper. Each pyramid is represented as a pair of **histogram-valued symbolic objects** (male, female shares by 5-yr age group) and clustered with adaptive leader + Ward on **squared L2 between the share vectors**, weighted by population size. Clusters map cleanly onto demographic-transition stages and track how countries migrate between shapes across 1996-2006. Follow-ups: Kejzar & Korenjak-Cerne (2021, *ADAC*, https://doi.org/10.1007/s11634-020-00425-4) generalise to modal-valued data; ISI 2015 proceedings apply the same method to US counties + Brazilian municipalities.
- **Implication:** the demography literature's default for "shape similarity" is plain Euclidean distance on the 42-dim (21 bins x 2 sexes) share vector, normalised to total = 1. This is a strong, published baseline; any image-embedding approach must beat it on some evaluation to justify itself.

### 2. Yoshida, Er-Rbib, Tsutsumi (2018/2019). "Which country epitomizes the world? A study from the perspective of demographic composition." arXiv:1810.00210; *Sustainability* 11(22):6404. https://arxiv.org/abs/1810.00210
- Treats age structure as **compositional data** and uses the **Aitchison distance** (Euclidean on centred-log-ratios) on UN WPP shares to find the country most similar to the world pyramid per period (1990s India/N.Africa -> 2015-30 South America -> 2040 Oceania/N.America -> 2050-60 Uruguay/Puerto Rico -> far future Italy/Japan), then hierarchically clusters 2015 countries; Russia + W.Europe form a cluster matching no world period ("recessive" structure).
- **Implication:** this is literally "most-similar pyramid across years" done with a closed-form metric on the WPP table Eli already has. Aitchison distance is a second cheap baseline; it is more sensitive to small bins (old ages) than L2, which may or may not match human "shape" intuition — worth including in the eval.

### 3. Bivand, Wilk, Kossowski (2017). "Spatial association of population pyramids across Europe: The application of symbolic data, cluster analysis and join-count tests." *Spatial Statistics* 21:339-361. https://doi.org/10.1016/j.spasta.2017.03.003
- Applies the Korenjak-Cerne histogram-symbolic-data clustering to NUTS-2/3 regional pyramids and tests spatial autocorrelation of the resulting classes.
- **Implication:** confirms the share-vector-L2 representation is reusable at sub-national scale; nothing image-based needed.

### 4. Hahn-Klimroth, Meireles, Lackey, Bertelsen, Dierkes, Clauss (2025). "A semi-automatic approach to study population dynamics based on population pyramids." arXiv:2508.03788 (q-bio.PE/cs.LG/stat.AP). https://arxiv.org/abs/2508.03788
- Algorithmic (rule-based) classification of age distributions into a shape taxonomy: [normal/inverted] pyramid, plunger, bell, [lower/middle/upper] diamond, column, hourglass; developed on zoo mammal populations 1970-2024 but explicitly pitched for humans.
- **Implication:** gives a ready-made discrete **shape vocabulary** and a rule set that could label all 36k WPP pyramids for free; usable as (i) a filter/facet ("show me other hourglasses"), and (ii) weak labels for evaluating any learned embedding (nearest neighbours should share the class).

### 5. Wijenayake et al. (2025). "PoPStat-COVID19: Leveraging Population Pyramids to Quantify Demographic Vulnerability to COVID-19." arXiv:2509.14213; companion "Devising PoPStat" (SSRN 5233269). https://arxiv.org/abs/2509.14213
- Defines **PoPDivergence = KL divergence of a country's WPP age-sex distribution from a reference pyramid** (reference optimised; Malta chosen). The scalar correlates r=-0.86 with log COVID cases across 180+ countries and beats median age, GDP pc, HDI, etc. Sensitivity to reference choice checked.
- **Implication:** KL / JS divergence between pyramids is another principled, one-line distance; it is asymmetric (KL) so use JS or symmetrised KL for retrieval. Also evidence that "whole-pyramid" distances carry information that summary stats (median age) miss — supports the app's premise.

### 6. Jiang & Bigot (2022-24). "Wasserstein multivariate auto-regressive models for modeling distributional time series." arXiv:2207.05442 (stat.ML). https://arxiv.org/abs/2207.05442
- Models per-country age distributions as points in 1-D **Wasserstein space** (W2 = L2 between quantile functions) and fits an AR model across countries; Fig. 12 shows age-structure evolution 1996-2036 in that geometry.
- **Implication:** for 1-D histograms on an ordered support (age), W1/W2 is closed-form (cumulative-histogram difference / quantile L2), so it is as cheap as L2 but respects that a 5-year shift is a small change while L2 treats it as large. Compute W1 separately for male and female halves (and optionally on the sex ratio). Strong candidate for the default metric.

### 7. Sauerberg (2026). "The Wasserstein Distance for Mortality Comparisons: Absolute versus Net Differences in Survival." arXiv:2608.27120 (stat.AP). https://arxiv.org/abs/2608.27120
- Shows W1 between two age-at-death distributions equals the life-expectancy gap unless survivorship curves cross (they cross in 59.8% of 69k HMD pairs, but the reversal is usually tiny).
- **Implication:** demographers are now using Wasserstein on age distributions as a legitimate comparison tool; expect W1 between pyramids to behave roughly like "difference in mean age" plus a shape correction — so pair it with a shape-only metric (e.g., L2 on shares or W1 after aligning means) if you want to separate "older" from "differently shaped".

### 8. Leger & Mazzuco (2020/2021). "What can we learn from functional clustering of mortality data? An application to HMD data." arXiv:2003.05780; *Demography* 58(5). https://arxiv.org/abs/2003.05780
- Functional data analysis (FDA) + functional PCA on age-specific curves for 32 HMD countries 1960-2010; clusters correspond to *stages* of the same trajectory reached with different timing (Eastern Europe stuck in stage 2).
- **Implication:** the FDA framing ("countries are on the same path at different times") is exactly what a cross-year similarity search surfaces (e.g., Vietnam 2024 ~ South Korea 1995). A functional-PCA basis over all 36k pyramids gives a ~5-10-dim shape embedding that is interpretable (PC1 = ageing, PC2 = bulge position...) — good for a 2-D "map of pyramids" view.

### 9. Wilson (2001, 2011) *Population and Development Review*; Dorius (2008) PDR; Krupowicz & Kuropka (2022) *Sustainability* 14(2):1024. "Global demographic convergence" / "Convergence of population structures of the EU member states".
- Convergence literature: fertility/mortality converged strongly 1950-2000 (Wilson); fertility inequality reconsidered (Dorius); EU age-structure variables show beta-convergence historically and again ~2050, sigma-convergence inconclusive (Krupowicz & Kuropka, 10 age-structure variables).
- **Implication:** convergence means the **same-year** nearest-neighbour set gets more crowded and less informative over time (many near-identical ageing pyramids by 2050); the cross-year search ("which past pyramid does X resemble") is where the interesting answers live. Also justifies showing "distance to nearest neighbour" as a distinctiveness score.

### 10. Herrero, Martinez, Villar (2019). "Population Structure and the Human Development Index." *Social Indicators Research* 141:731-763. https://doi.org/10.1007/s11205-018-1852-0
- Clusters countries by pyramid type (e.g., rectangular vs expansive) and shows countries with similar life expectancy can have very different pyramids; HDI adjusted for age structure.
- **Implication:** pyramid similarity is *not* the same as development similarity; UI should let the user see socio-economic neighbours vs shape neighbours side by side, not conflate them.

### (also) Drago & Talamo (2017/2018). DTW-based clustering of fertility time series 1960-2013 (Springer chapter, https://doi.org/10.1007/978-3-319-65193-4_2). Minor: shows DTW used on demographic curves; DTW is not needed for a fixed 21-bin age axis but is relevant if matching *trajectories* of pyramids over decades.

---

## (b): Chart embedding / retrieval with vision models

### 11. Luo, Zhou, Tang, Li, Chai, Shen (2023). "Learned Data-aware Image Representations of Line Charts for Similarity Search" (LineNet + LineBench). *Proc. ACM Manag. Data (SIGMOD)* 1(1):88. https://doi.org/10.1145/3588942 ; code https://github.com/HKUSTDial/LineNet-and-LineBench-SIGMOD2023
- The closest existing system to Eli's idea. Goal: embed chart *images* so that embedding distance ~ DTW distance on the *underlying data* (Eq. 1: min |dist(F(Vi),F(Vj)) - dist(Di,Dj)|). Trained ViT triplet-autoencoder with pseudo-labels from DTW on the data. **Ablation (Table 4, TrafficVol): image-only triplets (LineNet-V) P@10 = 0.11 / R10@100 = 0.09 vs full data-aware LineNet 0.79 / 0.70; data-only LineNet-D 0.74.** Generic visual CNN baseline (V-CNN) "fails to capture the fine-grained similarity".
- **Implication:** the single most important finding for this design. Off-the-shelf image embeddings of charts do **not** recover data similarity; you only get there by supervising the image encoder *with the data distance* — at which point, if you already have the data (Eli does), the image encoder is a detour. It also shows the way to do image embedding *properly* if Eli wants it for its own sake (e.g., to accept a user-uploaded pyramid screenshot): train on (image, W1-on-data) pairs.

### 12. Lee, Chang, Park, Seo (2024). "Assessing Graphical Perception of Image Embedding Models using Channel Effectiveness." IEEE VIS 2024 (short). arXiv:2407.20845. https://arxiv.org/abs/2407.20845
- Tests CLIP image embeddings on synthetic stimuli per Cleveland-McGill channel (length, position, area, tilt, curvature, colour). Measures (i) accuracy = linearity between embedding change and stimulus magnitude, (ii) discriminability = embedding distance between distinct stimuli. CLIP "perceives channel accuracy differently from humans" and has idiosyncratic discriminability for **length** (the channel a pyramid uses).
- **Implication:** CLIP-family embedding distance is not a monotone function of bar-length differences; expect nearest neighbours by CLIP to be driven by layout/colour/text more than by the population shares. Do not use zero-shot CLIP/SigLIP as the similarity metric without a measured calibration.

### 13. Long, Chatzimparmpas, Alexander, Kay, Hullman (2025). "Seeing Eye to AI? Applying Deep-Feature-Based Similarity Metrics to Information Visualization." CHI 2025. arXiv:2503.00228. https://doi.org/10.1145/3706598.3713955
- LPIPS-style deep-feature metrics (5 architectures, 3 weight sets) replicate crowd-sourced *human* similarity judgments of scatterplots and visual channels better than tuned MS-SSIM.
- **Implication:** if the target is "looks similar to a human", ImageNet-feature LPIPS on rendered pyramids is a defensible, cheap image metric — better than raw CLIP cosine. But it measures perceptual similarity of the picture, not similarity of the demographic state; render everything with identical style/axes or the metric will key on rendering differences.

### 14. Ma, Tung, Wang, Gao, Pan, Chen (2018). "ScatterNet: A Deep Subjective Similarity Model for Visual Analysis of Scatterplots." IEEE TVCG (VIS 2018). https://ieeexplore.ieee.org/document/8490694
- Learns a CNN similarity for scatterplots from human pairwise judgments (triplet loss); generic image features and pixel metrics disagree with human "subjective similarity".
- **Implication:** same lesson as 11/13 from the vis community: chart similarity needs chart-specific supervision (human or data-derived); generic features are not enough.

### 15. Li, Wang, Wu, Wei, Qu (2022). "Structure-aware Visualization Retrieval." CHI 2022. arXiv:2202.05960. — and Nguyen & Gehlenborg (2025). "Safire: Similarity Framework for Visualization Retrieval." arXiv:2510.16662.
- Li et al.: bitmap-only retrieval ignores SVG structure; fusing visual + structural features improves retrieval. Safire: taxonomy of visualization similarity — criteria (data / encoding / interaction / style / metadata) x representation modality (raster / vector / spec / NL); "the choice of representation modality ... shapes retrieval capabilities and limitations."
- **Implication:** Safire's vocabulary makes the design decision explicit: Eli wants **data-facet** similarity; the raster modality is the lowest-information representation for that facet. Since the app renders the pyramids itself, the spec/data modality is available for free — use it.

### 16. Chart-specialist encoders: Lee et al. 2022 **Pix2Struct** (arXiv:2210.03347); Liu et al. 2022 **MatCha** (arXiv:2212.09662) and **DePlot** (arXiv:2212.10505, chart->table); Masry et al. 2023 **UniChart** (arXiv:2305.14761); Zhang et al. 2024 **TinyChart** (arXiv:2404.16635); Masry et al. 2024 **ChartGemma** (arXiv:2407.04172); Xu et al. 2024 **ChartMoE** (arXiv:2409.03277); Poonam et al. 2026 **Bar-JEPA** (arXiv:2608.06062).
- All are encoder-decoder or LLM-connector models trained for chart QA / de-rendering (chart-to-table). Their *encoders* (Pix2Struct-ViT, SigLIP in ChartGemma, JEPA in Bar-JEPA) are trained to support text generation, not metric embedding; none publishes a chart-to-chart retrieval eval. Bar-JEPA is the one explicitly aimed at **per-bar numeric value recovery** from bar charts (tick + bar coordinate regression from self-supervised features) and reports it beats end-to-end supervised baselines.
- **Implication:** two viable roles for these models, neither is "embed and cosine": (i) **de-render** a pyramid image to numbers (DePlot / Bar-JEPA style) then use the demographic metrics — useful only for external/uploaded images; (ii) pool an encoder's patch tokens as a feature and *fine-tune* it with data-derived labels a la LineNet. Zero-shot pooled embeddings from these should be treated as untested.

### 17. Liu, Zeng, Zhang, Wang, Shan, He (2025). "On the Perception Bottleneck of VLMs for Chart Understanding." Findings of EMNLP 2025. arXiv:2503.18435. https://arxiv.org/abs/2503.18435
- Decomposes chart failures into vision-encoder bottleneck vs extraction bottleneck; finds visual representations contain more information than linear probes/retrieval-accuracy metrics reveal, but the encoder (CLIP/SigLIP-class) is still the binding constraint; they improve it with contrastive fine-tuning on charts.
- **Implication:** consistent with 12: frozen VLM encoders under-represent numeric chart content; fine-tuning with a contrastive objective on charts is what helps — which again requires labels from the data.

### 18. Wu et al. (2025). "Boosting Text-to-Chart Retrieval through Training with Synthesized Semantic Insights." arXiv:2505.10043; Xiao et al. (2023) WYTIWYR (arXiv:2304.06991); Ji et al. (2024) "Dataset Discovery via Line Charts" ICDE 2025 (arXiv:2408.09506).
- Chart-retrieval benchmarks exist but are **text-to-chart** or **chart-to-dataset** (cross-modal); Ji et al. reach 30-41% gains over baselines using segment-level encoders that "preserve fine-grained information". No published chart-to-chart *by underlying data* benchmark exists other than LineBench (11).
- **Implication:** there is no off-the-shelf benchmark for Eli's exact task; Eli would need to build a small eval (see recommendations) — and LineBench's design (pseudo-labels from data distance, P@10 / R10@100) is the template.

---

## (c): Do VLMs / image embeddings recover the numbers in a chart?

### 19. Rahmanzadehgervi, Bolton, Taesiri, Nguyen (2024). "Vision language models are blind: Failing to translate detailed visual features into words." ACCV 2024. arXiv:2407.06581.
- BlindTest: 7 trivial geometric tasks (overlapping circles, line intersections, counting); 4 SOTA VLMs average 58%; performance depends on spacing/resolution. Linear probes show the *vision encoders* contain enough information; the LM fails to decode it.
- **Implication:** generative VLM *answers* about pyramids ("which is older?") are unreliable at fine spatial precision; but linear-probe results hint that encoder features + a small learned head (not cosine) can extract quantitative structure — again pointing to supervised probing, not zero-shot similarity.

### 20. Mukherjee, Ren, Moritz, Assogba (2025). "EncQA: Benchmarking Vision-Language Models on Visual Encodings for Charts." arXiv:2508.04650. — and Wang et al. (2024) "CharXiv" (NeurIPS 2024, arXiv:2406.18521).
- EncQA: 2,076 synthetic QA pairs over 6 channels x 8 tasks; 9 VLMs vary widely by channel; **retrieve-value and compute-derived-value on length/position are far from solved and do not improve with model size for many pairs**. CharXiv: GPT-4o 47% vs humans 80.5% on reasoning over real charts; small chart perturbations drop scores up to 34.5%.
- **Implication:** rendered-bar value recovery by VLMs is noisy at the ~few-percent level that distinguishes neighbouring pyramids (adjacent WPP years differ by <1% per bin). An image path cannot be expected to resolve year-to-year or close-country differences; it can only recover coarse shape classes.

### (supporting) Zhou et al. 2020 "Reverse-engineering bar charts using neural networks" (arXiv:2009.02491); Sreevalsan-Nair et al. 2020 tensor-field bar/scatter extraction (arXiv:2010.02319); Cheng et al. 2023 ChartReader (arXiv:2304.02173). Dedicated de-rendering models reach high per-bar accuracy on clean synthetic bars — i.e., if you must go image -> numbers, use a de-renderer, not an embedding.

---

## What should change the design

1. **Invert the pipeline: numbers first, images optional.** Every strong result (LineNet ablation 0.11 vs 0.79; CLIP channel-linearity failure; EncQA/CharXiv value-retrieval gaps; Safire's modality argument) says raster embeddings are the *worst* representation for data-facet similarity, and the only way to make them work is to supervise them with a distance computed on the data. Eli already has the data for all 36k pyramids, so the retrieval index should be built on **vectors derived from the 42 shares** (male/female x 21 bins), not on pixels.

2. **Metric menu with demographic precedent (all closed-form, all < 1 ms per pair, 36k x 36k feasible offline or on the fly):**
   - L2 on normalised shares (Korenjak-Cerne 2015) — baseline, matches most published clusterings.
   - Aitchison / CLR-Euclidean (Yoshida 2019) — compositional; emphasises tails.
   - JS divergence (PoPStat, KL) — probabilistic.
   - **1-D Wasserstein per sex** (Jiang-Bigot; Sauerberg) — shift-aware; likely best match to "shape" intuition; recommend as default, with a "shape-only" variant computed after centring on mean age so "older" and "differently shaped" can be separated.
   - Functional-PCA scores (Leger-Mazzuco) — 5-10-dim interpretable embedding for the 2-D map and for fast ANN.
   Expose these as a user-selectable "similarity definition" — that *is* the adjustable-constraint UI Eli wants, alongside year filters.

3. **Sex handling is a design decision the literature leaves open:** cluster papers concatenate male/female shares normalised to total; W1 needs a per-sex or pooled choice. Provide "pooled age distribution" vs "sex-specific" toggles; the difference matters for Gulf states (male migrant bulge) and post-war cohorts.

4. **Keep the image-embedding idea, but as a measured experiment and as an input path, not the index:**
   - Experiment: render all pyramids in one fixed style, embed with SigLIP/CLIP + LPIPS(ImageNet) + a chart encoder (ChartGemma's SigLIP, Bar-JEPA), and score P@10 / R10@100 against the data-metric ground truth exactly like LineBench, plus agreement with Hahn-Klimroth shape classes. This settles "does the image path work" with numbers before belief.
   - Input path: if a user pastes an arbitrary pyramid screenshot from the web, de-render it (Bar-JEPA / DePlot-style) to 42 numbers, then search the numeric index.
   - If Eli wants a learned image embedding regardless, the recipe is LineNet's: triplets with pseudo-labels from W1 on the data.

5. **Cross-year search is the product, same-year is the default view.** Convergence literature implies same-year neighbours become near-duplicates by 2050; the interesting output is "Country X in 2024 resembles Country Y in year Z" (Leger-Mazzuco's "same path, different timing"). Index all 36k (entity, year) rows; add year-range and "exclude same entity" constraints; show distance-to-nearest as a distinctiveness score.

6. **Ship a shape vocabulary + evaluation labels for free:** implement Hahn-Klimroth's rule-based shape classes (pyramid / bell / column / hourglass / diamond variants) over the WPP table; use as facets and as a sanity metric (neighbour class agreement) for every metric/embedding.

7. **Aggregates:** exclude WPP regional/income aggregates (World, Africa, "More developed regions") from neighbour results by default; Yoshida's "which country epitomises the world" is a nice explicit mode instead.

---

## Sources (URLs)
- https://doi.org/10.1080/00324728.2014.954597
- https://doi.org/10.1007/s11634-020-00425-4
- https://arxiv.org/abs/1810.00210
- https://doi.org/10.1016/j.spasta.2017.03.003
- https://arxiv.org/abs/2508.03788
- https://arxiv.org/abs/2509.14213 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5233269
- https://arxiv.org/abs/2207.05442
- https://arxiv.org/abs/2608.27120
- https://arxiv.org/abs/2003.05780
- https://doi.org/10.1111/j.1728-4457.2011.00415.x ; https://doi.org/10.1111/j.1728-4457.2001.00155.x ; https://doi.org/10.1111/j.1728-4457.2008.00235.x ; https://www.mdpi.com/2071-1050/14/2/1024
- https://doi.org/10.1007/s11205-018-1852-0
- https://doi.org/10.1007/978-3-319-65193-4_2
- https://doi.org/10.1145/3588942 ; https://github.com/HKUSTDial/LineNet-and-LineBench-SIGMOD2023 ; https://shenleixian.github.io/pdf/LineNet.pdf
- https://arxiv.org/abs/2407.20845
- https://arxiv.org/abs/2503.00228 ; https://doi.org/10.1145/3706598.3713955
- https://ieeexplore.ieee.org/document/8490694
- https://arxiv.org/abs/2202.05960 ; https://arxiv.org/abs/2510.16662
- https://arxiv.org/abs/2210.03347 ; https://arxiv.org/abs/2212.09662 ; https://arxiv.org/abs/2212.10505 ; https://arxiv.org/abs/2305.14761 ; https://arxiv.org/abs/2404.16635 ; https://arxiv.org/abs/2407.04172 ; https://arxiv.org/abs/2409.03277 ; https://arxiv.org/abs/2608.06062
- https://arxiv.org/abs/2503.18435
- https://arxiv.org/abs/2505.10043 ; https://arxiv.org/abs/2304.06991 ; https://arxiv.org/abs/2408.09506
- https://arxiv.org/abs/2407.06581
- https://arxiv.org/abs/2508.04650 ; https://arxiv.org/abs/2406.18521
- https://arxiv.org/abs/2009.02491 ; https://arxiv.org/abs/2010.02319 ; https://arxiv.org/abs/2304.02173
