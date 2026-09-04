# Image-embedding experiment — pre-registration (written before the run)

Owner: agent C (render + embed). Written 2026-09-04, **before** `scripts/embed_images.py` was run on the
corpus. Everything above the "Results" marker is frozen; the results block at the end is written by the script
and replaced on every re-run (`<!-- results:start -->` … `<!-- results:end -->`). Verdicts are decided by
`scripts/eval_similarity.py` (agent D) and Eli's triplets in M4 — this file reports, it does not decide.

## 1. Question

Does a general-purpose vision encoder, fed a text-free canonical render of a population pyramid, produce a
similarity space that (a) is continuous in time like the numeric metrics, (b) agrees with external class
labels, and (c) picks neighbours a human prefers over `blend`'s? PLAN §4.5 gives the background: on 224-px
renders SigLIP2-base / DINOv2-base correlated with shape distance at Spearman ≈ 0.83 but overlapped W1's top-10
by only 17–19 %, and were fragile to render nuisances.

## 2. Pre-registered predictions (numeric gates; hypotheses, not conclusions)

| id | prediction | gate value | measured by |
|---|---|---|---|
| P1 | SigLIP2-naflex G1 continuity fails | C1 < 0.95 on 1950–2023 queries | this script (G1, self excluded, NN same entity with \|Δy\| ≤ 1) and D's protocol |
| P2 | DINOv2-base G1 continuity fails | C1 < 0.95 on 1950–2023 queries | same |
| P3 | both spaces are *related* to shape, not noise | Hahn-Klimroth class agreement ≥ 0.6 for both (D's G2b, same-year top-10) | `eval_similarity.py` |
| P4 | neither space beats `blend` on the paired triplet test | McNemar on the 32 blend-vs-visual triplets at α = 0.05 not significant in visual's favour | M4 triplets |
| P5 | Spearman(embedding cosine distance, blend) on random pairs ≈ 0.8 (0.7–0.9) for both | reported | this script |
| P6 | top-10 overlap with `blend` (same-year, own entity excluded) < 0.35 for both | reported | this script |
| P7 | PCA-64 (no whitening) preserves the ranking: Spearman(full-dim cosine, PCA-64 cosine) ≥ 0.98 | reported | this script |

Expected verdict for `visual`: **`lab`** (PLAN §4.3). If P1/P2 are wrong (C1 ≥ 0.95) and the space passes
G2/G4, `visual` ships as `menu`, captioned "experimental: what a vision model thinks looks alike".

## 3. Pre-registered niche (the only admissible post-hoc claim)

Visual "wins the niche" only if it beats `blend` by the paired sign test at α = 0.05 on the ≥ 15 triplets whose
**anchor carries a detected cohort notch/bulge** (PLAN §4.4 step 4 detector on the 2024 set: residual
|s_k − smoothed_k| with bins 0 and 20 excluded, threshold = same-year p95). Rationale: a ViT sees a notch as a
salient local feature, whereas the CDF term of `blend` charges it roughly in proportion to its mass. No other
niche will be claimed.

## 4. Renderer (`render.py`, style frozen by `style_hash()`)

- `canon2` (two-sex): white background, 21 rows of `size/21` px, **100+ on top, 0–4 at the bottom**, male bars
  grow LEFT from the centre in steelblue (70, 130, 180), female bars grow RIGHT in (238, 121, 137); half-width =
  **17 %** of total population (corpus max single-sex bin = 16.1 %, so nothing clips); zero gap, no text, no
  axes, no frame. Bar length = `round(share / 0.17 × size/2)` px. Pure numpy raster (integer pixels, no
  anti-aliasing) so identical inputs give identical bytes across machines and library versions.
- `canon1` (total-only, sex-blind): `s21 / 2` mirrored on both sides in grey (110, 110, 110), same geometry.
- `style_hash()` = sha256 over the renderer source + constants; it is written into every `*.meta.json` and
  `embed_images.py` refuses to embed on-disk renders whose hash differs.
- Sizes: 336² for SigLIP2 (21 rows × 16 px = one patch row per age bin), 294² for DINOv2 (21 × 14).

## 5. Models and processor settings (asserted on the first batch, recorded in `*.meta.json`)

| key | HF id | patch | render | processor | assertion |
|---|---|---|---|---|---|
| `siglip2-base-naflex` | `google/siglip2-base-patch16-naflex` (Apache-2.0) | 16 | canon2 @ 336² | `Siglip2ImageProcessor` with **`max_num_patches = 441`** (default 256 would resize to ≈ 256 px) | `spatial_shapes == (21, 21)`, `pixel_attention_mask.sum() == 441`, un-patched/un-normalised tensor equals the render (max abs diff ≤ 1/255) |
| `dinov2-base` | `facebook/dinov2-base` (Apache-2.0) | 14 | canon2 @ 294² | `BitImageProcessor` with **`do_resize = False, do_center_crop = False`** (default would resize 256 → crop 224) | `pixel_values.shape[-2:] == (294, 294)`, un-normalised tensor equals the render (≤ 1/255) |

Caveat (recorded up front): naflex was trained at the 256 / 576 / 1024-patch budgets; 441 is inside the range
but not a trained budget. If the 441 result looks degenerate (P5 far below 0.7, or continuity far below
DINOv2's), the fallback is 576 patches = 384² (24 rows × 16 px is *not* bin-aligned, so that would be a
second, separately hashed render). Inference in float16 on MPS (fp16 vs fp32 cosine ≥ 0.99996 on a 64-image
probe; run-to-run identical outputs). Embeddings = pooled image features (`get_image_features().pooler_output`
for SigLIP2, `pooler_output` = CLS for DINOv2), L2-normalised, float32; PCA-64 without whitening (whitening
collapsed Spearman-vs-W1 from 0.83 to 0.15 in the research phase), stored as float16 with mean/proj in
`{model}.pca.npz`.

## 6. Factorial invariance diagnostic (reported, never gated)

The product's safeguard against style drift is the style hash; this diagnostic only says *which* render
artefact each model is sensitive to. Design, fixed before the run:

- Sample: 2,000 pyramids drawn (seed 0) from the year grid {1950, 1960, …, 2100} × all entities, so two
  sampled rows of the same country are ≥ 10 years apart and self-match is meaningful (adjacent years are
  *supposed* to be indistinguishable).
- Base = the canonical style for the model. Four factors, **each varied alone**:
  1. `colour`: bars recoloured (male (60, 60, 60), female (160, 160, 160) — monochrome greys, same layout);
  2. `gap`: 2-px white gap between rows (bars 2 px shorter, same row pitch);
  3. `resolution`: ± 2 patch rows (SigLIP2 336 → 304 / 368; DINOv2 294 → 266 / 322), the processor re-pinned
     to the new size (`max_num_patches` = rows × cols; DINOv2 native size), rows then have non-integer pitch
     and are rounded to pixel edges;
  4. `aspect`: 4:3 canvas (336 × 448 / 294 × 392), bars scaled to the new half-width.
- Statistics per factor and model: cross-style **self-match rank** (rank of pyramid *i* among the 2,000
  canonical embeddings when queried with its variant embedding: median, P(rank = 1), P(rank ≤ 10)) and
  **top-10 Jaccard** between each pyramid's canonical-space neighbours and its variant-space neighbours
  (both within the 2,000-sample; mean over pyramids). Also the mean cosine between a pyramid and its own
  variant, against the mean cosine to its nearest *different* pyramid, for scale.
- Prediction (from PLAN §4.5's 224-px measurements): colour is the worst factor for SigLIP2 (self-cosine
  < nearest-other cosine), per-image rescaling would be the worst for DINOv2 but is excluded by design (fixed
  ± 17 % axis); resolution ± 2 patches should keep top-10 Jaccard > 0.5 for DINOv2 (native position-embedding
  interpolation) and lower for SigLIP2-naflex.

## 7. Other reported numbers (this script)

Throughput (img/s incl. preprocessing) and wall time per model; Spearman(embedding cosine distance, blend)
and (…, l2) on 2,000 random row pairs (seed 0); top-10 overlap with `blend` and `l2` for 300 random queries
(seed 0), same-year with own entity excluded (the product default) and any-year with own entity excluded;
G1 continuity C1 / C5 for full-dim and PCA-64 cosine, split 1950–2023 vs 2024–2100 by query year; PCA
explained variance at 16 / 64 components; p1–p99 cosine spread (dynamic range).

`blend` and `l2` come from `pyramid_explorer.metrics` (agent B) with `sigma.json` if present, else B's
fallback constants; both facts are recorded in the results block.

Provenance in every `*.meta.json`: `data_hash` = the build's definition (CONTRACT amendment A: sha256 over the
little-endian uint16 corpus, so `db.ingest_embeddings` can match it against `build_meta.data_hash`), plus
`s42_file_sha256` of `corpus_s42.npy`; HF id + snapshot revision + `model.safetensors` sha256; processor config
and the asserted shapes; render kind/size/style hash; throughput; PCA mean (768 floats, also in
`{model}.pca.npz` with the projection) and the projection's sha256.

<!-- results:start -->
_Run 2026-09-04T21:59:11+00:00 on the corpus (42280 rows, 280 entities, data_hash `e2bf14d57600…`); numeric metrics from pyramid_explorer.metrics (σ: data/processed/sigma.json)._

| model | img/s | wall | C1 obs (full / pca64) | C5 obs | C1 proj | ρ(cos, blend) | ρ(cos, l2) | top-10 ∩ blend same-yr | ∩ l2 same-yr | ∩ blend any-yr | ρ(full, pca64) | var16 / var64 | cos p1 / p50 / p99 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `siglip2-base-naflex` | 62 | 11.4 min | 0.605 / 0.517 | 0.791 | 0.746 | 0.703 | 0.677 | 30.2 % | 31.3 % | 7.5 % | 0.800 | 0.916 / 0.973 | 0.866 / 0.960 / 0.996 |
| `dinov2-base` | 63 | 11.2 min | 0.529 / 0.466 | 0.739 | 0.630 | 0.835 | 0.824 | 30.9 % | 34.2 % | 8.2 % | 0.947 | 0.962 / 0.991 | 0.665 / 0.888 / 0.995 |

Processor assertions (first batch): `siglip2-base-naflex` Siglip2ImageProcessorPil {'max_num_patches': 441} → spatial_shapes [21, 21], mask sum 441, pixel_values [8, 441, 768], max |Δpixel| 0.000/255; `dinov2-base` BitImageProcessorPil {'do_resize': False, 'do_center_crop': False} → pixel_values [8, 3, 294, 294], max |Δpixel| 0.000/255.

Pre-registered predictions (§2), auto-scored on this run:

- `siglip2-base-naflex`: P1/P2 C1 < 0.95 → 0.605 **met**; P5 ρ(cos, blend) ∈ [0.7, 0.9] → 0.703 **met**; P6 top-10 overlap with blend < 0.35 → 0.302 **met**; P7 ρ(full, pca64) ≥ 0.98 → 0.800 **NOT met**.
- `dinov2-base`: P1/P2 C1 < 0.95 → 0.529 **met**; P5 ρ(cos, blend) ∈ [0.7, 0.9] → 0.835 **met**; P6 top-10 overlap with blend < 0.35 → 0.309 **met**; P7 ρ(full, pca64) ≥ 0.98 → 0.947 **NOT met**.
- P3 (class agreement) and P4 (triplets) are scored by `eval_similarity.py` and M4, not here.

Factorial invariance diagnostic (§6; variant query vs canonical gallery within the sample; reported, not gated):

| model | factor | canvas | cos(self, variant) | cos(nearest other) | self rank median | top-1 | top-10 | top-10 Jaccard |
|---|---|---|---|---|---|---|---|---|
| `siglip2-base-naflex` | colour | 336×336 | 0.882 | 0.997 | 128 | 2.5 % | 9.8 % | 0.193 |
| `siglip2-base-naflex` | gap | 336×336 | 0.908 | 0.997 | 200 | 1.8 % | 8.8 % | 0.173 |
| `siglip2-base-naflex` | resolution- | 304×304 | 0.942 | 0.997 | 283 | 0.8 % | 4.0 % | 0.107 |
| `siglip2-base-naflex` | resolution+ | 368×368 | 0.942 | 0.997 | 255 | 0.9 % | 4.5 % | 0.116 |
| `siglip2-base-naflex` | aspect | 336×448 | 0.962 | 0.997 | 183 | 2.1 % | 9.8 % | 0.114 |
| `dinov2-base` | colour | 294×294 | 0.848 | 0.995 | 109 | 2.6 % | 12.6 % | 0.320 |
| `dinov2-base` | gap | 294×294 | 0.843 | 0.995 | 133 | 1.6 % | 9.7 % | 0.218 |
| `dinov2-base` | resolution- | 266×266 | 0.887 | 0.995 | 99 | 2.1 % | 12.7 % | 0.150 |
| `dinov2-base` | resolution+ | 322×322 | 0.877 | 0.995 | 130 | 1.4 % | 10.2 % | 0.154 |
| `dinov2-base` | aspect | 294×392 | 0.950 | 0.995 | 40 | 6.6 % | 25.1 % | 0.145 |
<!-- results:end -->

## 8. Post-run notes (written after the run; NOT pre-registered — interpretation only, no new claims)

- **Timing.** ≈ 12 min per model for 42,280 images on MPS/fp16 (58–60 img/s), slower than the plan's 3–6 min
  estimate: naflex at 441 patches and DINOv2 at 294² (441 patches) each see ~2.2× the tokens of the 224-px
  research setting. Renders are ~20 s per corpus array; the diagnostic (2,000 × 5 variants) ≈ 3–4 min per model.
- **P7 is mis-specified, not failed.** Random-pair Spearman(full cosine, PCA-64 cosine) = 0.80 / 0.94, but
  Spearman(full cosine, PCA-64 **L2**) = 1.000 for both models and Spearman(centred-full cosine, PCA-64 cosine)
  = 1.000: the 64-d truncation preserves the global order exactly; the drop is entirely the mean-centring, which
  changes cosine geometry because both spaces sit in a narrow cone (mean vector norm 0.98 / 0.93 for unit
  vectors; p50 pairwise cosine 0.96 / 0.89). `metrics.distances('visual:*')` takes cosine on the centred 64-d
  vectors, i.e. the *centred* geometry, which has slightly higher continuity than raw cosine (C1 obs 0.624 vs
  0.605 SigLIP2; 0.543 vs 0.529 DINOv2 at 768-d).
- **What PCA-64 does lose is the near-duplicate tail.** C1 obs falls from 0.624 (centred 768-d) to 0.517
  (64-d) for SigLIP2 and 0.543 → 0.466 for DINOv2, and "NN is the same entity in any year" from 0.73 → 0.65 /
  0.66 → 0.60: adjacent-year discrimination lives in the ~3 % / ~1 % residual variance. float16 storage changes
  nothing (identical C1/C5 to float32; 0.7 % of components are sub-normal). If `visual` ever ships, the web
  space's continuity is the `continuity_pca64` number, not `continuity_full`.
- **Provisional vs real corpus.** SigLIP2 on the 237-country provisional corpus gave C1 obs 0.618 / ρ(blend)
  0.688 / overlap 0.334; on the real corpus (280 entities incl. 43 aggregates, Togo patch) 0.605 / 0.703 / 0.302
  — same picture. Both models' continuity is far below the numeric metrics' (P1/P2 met by a wide margin), and
  is *higher* on projected years (smoother WPP projections) than on observed ones.
- **Invariance (§6 predictions).** Colour is indeed the worst factor by self-cosine for both models (0.88 /
  0.85 vs nearest-other 0.997 / 0.995), but by neighbourhood every factor is catastrophic: cross-style
  self-match rank medians 99–283 out of 2,000 and top-10 Jaccard 0.11–0.32; the resolution ± 2-patch prediction
  (DINOv2 Jaccard > 0.5) was wrong (0.15). Both encoders separate *styles* far more than *pyramids*
  (self-variant cosine < nearest-other cosine everywhere), which is exactly why the style hash, not invariance,
  is the shipping safeguard.
- **Retrieval sanity (DB `knn`, PCA-64).** JPN 2023 same-year → PRI, GRC, HKG, TWN, UKR (SigLIP2) / PRI, PRT,
  BIH, HKG, ITA (DINOv2); KOR 2026 any-year → ESP 2029–32, ITA 2027 (SigLIP2) / TWN 2025–33 (DINOv2).
