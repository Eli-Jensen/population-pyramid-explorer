# Embedding ~36k population-pyramid images vs raw share vectors — practical engineering assessment

Date: 2026-09-04. Machine used for all local measurements: Apple M4 Max, 36 GB unified memory, 14 cores (Eli's Mac), torch 2.14.0 + transformers 5.16.1 on MPS, Node 24.14 for the in-browser proxy. Scripts + raw outputs: `/private/tmp/claude-501/-Users-elijensen-Projects/d786032f-481e-46d5-993f-907c938b43fe/scratchpad/bench/` (`prep.py`, `render_bench.py`, `kaleido_bench.py`, `embed_bench.py`, `artifact_eval.py`, `knn_bench.mjs`, `vec_analysis.py`).

Dataset facts (from `data/processed/wpp2024_population_age5.parquet`): 237 entities × 151 years = **35,787 pyramids** (not 36k even; 751,527 rows / 21 bins). Share vector = 42 floats (21 male + 21 female bins as fraction of total) summing to 1. Largest single-sex 5-yr bin share in the whole dataset = **16.1%** (Guam 1950, males 20–24 — US base), p99.9 = 12.2%; so a fixed x-axis of ±17% never clips. 100+ bin exceeds 2% of population only for HKG 2079–2100 and PRI 2100 (23 pyramids) — keep the bin, it is real.

Legend for "verified": **[V]** = read on vendor page/official price list today; **[T]** = third-party calculator/blog only; **[M]** = measured here; **[?]** = could not verify.

---

## 1. Candidate image-embedding models

### 1a. Open-weight encoders (run locally, $0)

| Model | Weights / license | Emb. dims | Input res | Params | Local on Apple Silicon | Measured img/s (M4 Max, MPS, fp16, batch 32, incl. preprocessing) [M] |
|---|---|---|---|---|---|---|
| **SigLIP 2** `google/siglip2-base-patch16-{224,256,384,512}`, `-base-patch32-256`, `-large-patch16-{256,384,512}`, `-so400m-patch14-{224,384}`, `-so400m-patch16-{256,384,512}`, `-giant-opt-patch16-{256,384}`, NaFlex variants [V: HF collection] | Apache-2.0 [V] | base **768**, large **1024**, so400m **1152**, giant-opt **1536** [V: config.json / blog] | 224–512 per checkpoint; NaFlex = variable | base 375M total (86M vision), so400m ~1B total | Yes: PyTorch MPS (used here); MLX via `mlx-embeddings` (lists SigLIP so400m-patch14-384) [V]; no published MLX throughput [?] | **base-224: 248 img/s fp16, 213 img/s fp32 → 35.8k in ~2.5 min**; **so400m-p14-384: 12.8 img/s → 47 min; so400m-p16-512: 8.3 img/s → 72 min** (fp16; first load 3–4 min to download 1.1 GB) |
| **CLIP ViT-L/14** `openai/clip-vit-large-patch14` | MIT (openai/CLIP repo) [V-ish: HF card has no license field; GitHub LICENSE is MIT] | 768 (proj) [V config] | 224 | 428M total | Yes (MPS) | **56.5 img/s fp16 → 35.8k in ~10.6 min** |
| **CLIP ViT-L/14 LAION** `laion/CLIP-ViT-L-14-laion2B-s32B-b82K` (also `laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K`) | MIT [V] | 768 [V config] | 224 | ~428M | Yes (same arch; open_clip or HF) | same as OpenAI L/14 (same architecture) — not separately timed |
| **DINOv2** `facebook/dinov2-{small,base,large,giant}` | Apache-2.0 [V] | 384 / **768** / 1024 / 1536 (CLS pooler) [V config] | processor default 224 crop; supports 518 (14-px patches) | base 87M | Yes (MPS) | **base-224: 160 img/s fp16 → 35.8k in ~3.7 min** |
| **DINOv3** `facebook/dinov3-vit{s16,b16,l16,h16plus,7b16}-pretrain-lvd1689m` (+ ConvNeXt, + SAT-493M satellite variants) | **Custom "DINOv3 License"** (gated on HF; commercial OK; must ship license copy + display "Built with DINOv3"; no training competing models; trade-control clauses) [V: ai.meta.com license page] | 384 / 768 / 1024 / 1280 / 4096 [V] | 224 default, 16-px patches | 21M–6.7B | Yes via HF transformers on MPS (ViT-B/L trivially; 7B needs ~14 GB fp16 — fits 36 GB) | not timed; ViT-B/16 ≈ DINOv2-base class (~150–250 img/s expected) [?] |
| **jina-clip-v2** `jinaai/jina-clip-v2` | **CC BY-NC 4.0** (non-commercial only; commercial via API/marketplaces) [V] | **1024**, Matryoshka down to 64 [V] | 512 | 0.9B (image tower 304M, EVA02) | Yes in principle (custom code, xformers/flash-attn optional); not timed | ~ViT-L class at 512 px → expect 15–30 img/s on MPS [?] |
| **nomic-embed-vision-v1.5** | Apache-2.0 [V] | 768 (shares space with nomic-embed-text-v1.5) | 224, patch 16 (ViT-B/16) [V config] | 92.9M [V] | Yes (custom code `NomicVisionModel`) | ~DINOv2-base class (≈150–250 img/s) [?] |
| **ChartGemma** `ahmed-masry/chartgemma` (PaliGemma-based, SigLIP-so400m tower) | MIT (weights); Gemma terms for the LM part | not an embedding model — encoder hidden states only | 448 | 3B | possible but it is an image-text-to-text model, no retrieval head [V] | n/a |
| UniChart / MatCha (Donut-/Pix2Struct-based chart encoders) | MIT / Apache | encoder-decoder; no pooled embedding | 960–1024 | 200–300M | n/a | n/a |

**Chart-specialised encoders: none suitable.** Everything "chart-specialised" (UniChart, MatCha, ChartGemma, ChartVerse/ChartAnchor 2025–26 work) is trained for chart-QA / chart-to-text, not for chart-to-chart similarity; Chart2Vec (arXiv 2306.08304) embeds Vega-Lite *specs*, not pixels, and is trained on chart co-occurrence for storytelling. No chart-retrieval encoder with weights that I could find [?]. The one relevant signal from the literature: DINOv2/v3 (vision-only, self-supervised) beat CLIP-family on pure visual-similarity retrieval; CLIP-family collapse "a red/blue bar chart" into a semantic blob (confirmed below on our own images).

### 1b. API models

Costs computed for 35,787 images ("36k") and 71,574 ("72k") at a 224×224 canonical render unless noted; per-image figures come from the vendor's own rules.

| Model | Dims | Image → tokens / price rule | Batch limits | 36k cost | 72k cost | Notes |
|---|---|---|---|---|---|---|
| **Voyage `voyage-multimodal-3.5`** (Jan 2026; `-3` still served) [V: docs.voyageai.com/docs/pricing, /docs/multimodal-embeddings] | 1024 default; 256/512/2048 Matryoshka; float/int8/uint8/binary out | 1 token per 560 px; **$0.60 per B pixels** (= $0.12/M tokens); images <50k px billed as 50k px, >2M px downsampled → **$0.00003/img at 224²** (50,176 px), $0.000157/img at 512² | 1,000 inputs/request, 320k tokens/request, 20 MB & 16 M px per image; Batch API −33%, 100k inputs/batch, 12 h window (free credits don't apply to Batch) | **$1.07** (224²) / $5.6 (512²) — **but 150 B free pixels/account covers ≈3 M images → effectively $0** | $2.15 / $11.3 → $0 within free tier | best price/latency trade among APIs; explicit pixel rule; small images upscaled = fine |
| **Gemini Embedding 2** `gemini-embedding-2-preview` (GA-preview since 2026-03-10) [V: ai.google.dev pricing + model page] | 128–3072 flexible (768/1536/3072 recommended), auto-normalised truncation | Images $0.45/M tokens, Google's own line: **$0.00012/image** (≈258–267 tokens implied); Batch $0.225/M ($0.00006/img); **Free tier: all input types free of charge** (rate-limited) | max **6 images per request** → ≥6k requests for 36k; Batch API available (enqueued-token caps per tier) | **$4.29** std / $2.15 batch / $0 free-tier | $8.59 / $4.29 / $0 | 6-images-per-call is the annoying part; PNG/JPEG only |
| **Cohere Embed v4** `embed-v4.0` [V docs for limits; pricing $0.12/M text, **$0.47/M image tokens** is [T] — cohere.com/pricing rendered only Model Vault rates for me] | 1536 default; 256/512/1024; float/int8/uint8/binary/ubinary | image-token count rule for Embed v4 **not documented** [?]; images >2,458,624 px downsampled, <3,136 px upsampled; if the Command-vision rule (512² tiles × 256 tokens + 256 thumbnail) applies, a 224² image ≈ 512 tokens → $0.00024/img | 96 inputs/request, 20 MB payload, 5 MB/image; Batch Embed Jobs exist | ≈ **$8.6** (if 512 tok/img) [?] | ≈ $17 | most expensive; trial keys free but rate-limited |
| **Amazon Titan Multimodal Embeddings G1** `amazon.titan-embed-image-v1` [V: AWS price-list CSV us-east-1, pulled today] | 1024 default; 384/256 | **$0.00006 per input image** on-demand, **$0.00003 batch**; text $0.0008/1k tok ($0.0004 batch); max 25 MB, 2048×2048 | one image per InvokeModel call; Bedrock batch inference = JSONL on S3 (min 100 records/job) | **$2.15** on-demand / $1.07 batch | $4.29 / $2.15 | Nov-2023 model, weakest of the set; one call per image (36k calls) |
| **Amazon Nova Multimodal Embeddings** `amazon.nova-2-multimodal-embeddings-v1:0` (Oct 2025) [V price-list CSV; dims from AWS blog] | 3072 / 1024 / 384 / 256 | **standard image $0.00006** on-demand / **$0.00003 batch** (a "document image" type is $0.0006 / $0.00048 — do not tag pyramids as documents); tokens $0.135/M ($0.0675/M batch) | sync InvokeModel for images; async/batch via S3 | **$2.15** / $1.07 batch | $4.29 / $2.15 | modern replacement for Titan; same per-image price |
| **jina-clip-v2 (Jina API)** [V: jina.ai/embeddings lists **~16,000 tokens per image** for jina-clip-v2; $/token pack price not shown on page — third parties quote ≈$0.02/M tokens [T]] | 1024 (Matryoshka ≥64) | ≈16k tokens/img × ~$0.02/M ≈ **$0.00032/img** [T] | "no batch size limit"; 500 RPM / 2 M TPM paid tier → ≈125 images/min at 16k tok each | ≈ **$11.5** [T] | ≈ $23 [T] | 1 M free tokens (non-commercial) ≈ 62 images. Self-hosting is free but CC BY-NC |
| **Nomic API (nomic-embed-vision-v1.5)** | 768 | pricing "custom"/not public; 1 M free tokens [T] | [?] | [?] | [?] | self-host instead (Apache-2.0, 93M params) |

Bottom line on APIs: every API option is **$0–$10 for the whole corpus** and the only real cost is engineering + rate-limit babysitting; Voyage (free tier, 1,000 images/request) and Gemini Embedding 2 (free tier, but 6 images/request) are the two worth trying if an API model is wanted at all. Locally, SigLIP2-base does the whole corpus in **~2.5 minutes** on Eli's Mac, so local open weights are the default.

---

## 2. Measured: does an off-the-shelf image embedding track *shape*, or rendering artifacts?

Setup [M]: 600 random pyramids (then 2,000 for the second table) rendered with the canonical NumPy raster (224², two-tone, ±17% fixed axis), embedded with SigLIP2-base-224 and DINOv2-base (fp16, MPS), L2-normalised. Reference "shape" metrics: W1 (earth-mover) on the 21-bin total age distribution, and L2 on the 42-d share vector. Note that the two *share-space* metrics themselves agree only moderately on neighbour sets (top-10 overlap L2-vs-W1 = **42%**; Spearman of pairwise distances 0.93), which is the yardstick for the rows below.

**A. Rank agreement with shape distance (20k random pairs, 2,000-pyramid subset)**

| Embedding, post-processing | Spearman(W1, embedding dist) | top-10 neighbour overlap vs W1 | vs L2-share |
|---|---|---|---|
| SigLIP2-base raw cosine | 0.845 | 18.7% | 25.0% |
| SigLIP2-base mean-centred cosine | 0.834 | 18.7% | 25.3% |
| SigLIP2-base PCA-64 (centred, not whitened) | 0.834 | 17.9% | 23.8% |
| SigLIP2-base PCA-64 whitened | **0.158** | 17.7% | 24.7% |
| DINOv2-base raw cosine | 0.832 | 17.1% | 24.0% |
| DINOv2-base PCA-64 (centred) | 0.817 | 16.9% | 23.3% |
| DINOv2-base PCA-64 whitened | **0.147** | 17.4% | 25.0% |
| (yardstick) L2-share vs W1 | 0.931 | 42.3% | — |

Reading: the image embeddings are *correlated* with shape distance (ρ≈0.83 — they are not nonsense) but their neighbour sets overlap with a shape metric's neighbour sets at roughly half the rate that two shape metrics overlap with each other. Nearest-neighbour lists are a tail statistic; ρ=0.83 on all pairs still yields top-10 lists that are ~80% different. PCA-64 (no whitening) loses nothing → storage answer. Embedding PCA cum-var: 16 comps 87–91%, 64 comps 96–98% — the embeddings, like the shares, live on a low-dimensional manifold.

**B. Sensitivity to rendering nuisances (600 subset; same pyramid re-rendered with one change)**

| Nuisance change | SigLIP2 cos(same pyramid, variant) | DINOv2 cos | For scale: cos to the nearest *different* pyramid |
|---|---|---|---|
| two-tone → monochrome | 0.897 | 0.836 | SigLIP2 0.994 / DINOv2 0.985 (mean) |
| white → light-grey (240) background | 0.983 | 0.989 | |
| 224 px → 256 px render (then resized by processor) | 0.977 | 0.950 | |
| fixed axis → per-image "fit to widest bar" | 0.939 | 0.777 | |
| cos between two *random different* pyramids | 0.944 (p5 0.893) | 0.809 (p5 0.632) | |

Reading: **every nuisance moves an image farther from itself than its nearest genuine neighbour is** (0.90–0.98 vs 0.99); recolouring the bars moves a SigLIP2 embedding *more than swapping in a random other country does* (0.897 vs 0.944 mean). So (a) rendering must be frozen bit-for-bit for the life of the index, (b) any redesign = re-embed everything (cheap, 2.5 min, but the neighbour lists change), (c) the "variant→original top-1 retrieval" was 2.5–46% (SigLIP2) / 3–96% (DINOv2) — low partly because random subsets contain the same country in adjacent years, which is *supposed* to be indistinguishable; DINOv2 is the more render-robust of the two except to per-image rescaling, which wrecks both.

Not measured (worth doing before believing anything): a blind human check of 30–50 query→neighbour triples (W1 pick vs embedding pick), and the same tables for so400m/CLIP-L (throughput says so400m costs 20–30× more compute for, on this evidence, no obvious reason).

---

## 3. Deterministic headless rendering of 36k pyramids

All measured on M4 Max, single process, 224×224 canonical render (21 mirrored bars, no text/axes), [M]:

| Renderer | ms / image | s per 1k | 35.8k total | Deterministic bytes (same input twice)? | Notes |
|---|---|---|---|---|---|
| **Pure NumPy raster** (fill rectangles in a uint8 array) | **0.06** (array) / 0.49 incl. PNG encode | 0.06 / 0.5 | 2 s / 18 s | yes (bit-exact by construction) | zero dependencies beyond NumPy+Pillow; integer-pixel bars (no anti-aliasing) — arguably the *most* canonical: identical inputs → identical pixels, no font/AA/version drift |
| **Hand-written SVG → resvg** (`resvg-py`) | **1.13** | 1.1 | 40 s | yes | anti-aliased fractional bar widths; SVG is 1.4 KB, PNG 1.5 KB; resvg is pinned Rust, reproducible across OSes |
| matplotlib Agg, reuse one Figure and `set_width` on 42 Rectangle patches, grab RGBA buffer | 1.14 | 1.1 | 41 s | yes | the "right" matplotlib pattern |
| matplotlib Agg, new Figure per image, `savefig(png)` | 9.2 | 9.2 | 5.5 min | yes | naive pattern; 8× slower purely from figure construction |
| **Vega-Lite → vl-convert** (`vegalite_to_png`, spec with inline data) | 10.2 (1.2 for `_to_svg`) | 10.2 | 6 min | yes | embedded Deno runtime; fine but no reason to use it here; ~7 KB PNGs. resvg is what vl-convert uses internally for PNG |
| **Plotly + kaleido 1.4** (`fig.to_image`) with `kaleido.start_sync_server()` | 47.6 | 48 | 28 min | yes | Chrome-backed; a left-over zero-line artefact showed up in the sample; kaleido 1.x needs a Chrome install (present on this Mac) |
| Plotly + kaleido 1.4 without the persistent server | **2,288** | 2,288 | 23 h | – | matches the known 50× regression report (plotly/Kaleido#400); never do this |

Reproducibility notes: (a) PNG bytes from Agg/resvg/vl-convert were identical across two runs here, but Agg output can change across matplotlib versions (AA/rounding) and fonts if any text is present — pin versions and never draw text. (b) For image-embedding work, encode images once and store them (PNG, ~1–2 KB each → 36k ≈ 50–80 MB; or keep them as a single uint8 array 36k×224×224×3 = 5.4 GB raw, 2 GB gz — better to store shares and re-render from the deterministic NumPy raster on demand). (c) Parallelism: NumPy raster is so fast that multiprocessing is pointless; resvg/Agg scale linearly over 14 cores if ever needed.

---

## 4. What a canonical rendering should look like

Goal: every pixel that varies between images should be caused by the share vector and nothing else.

1. **No text, ticks, axes, gridlines, legend, title, frame.** Any of these is a constant the model "sees" in every image and it pushes all embeddings into one semantic cone (the cos-sim floor of ~0.9 measured in §2 is exactly this).
2. **Fixed 21 bins, fixed bar height = H/21, zero gap** (gaps add a high-frequency stripe pattern whose phase relative to the 16-px patch grid changes with image size — it is constant across images at a fixed size, so it is only a problem if you ever change the size). Rendering at a size that is a multiple of 21 and of the patch size (e.g. 336 = 21×16) makes each bar exactly one patch row for patch-16 models; the HF processor then resizes to the checkpoint's resolution anyway, so simplest is: render directly at the model resolution (224/256/384/512) with anti-aliasing (resvg) or integer rounding (NumPy) and accept ±1 px quantisation (bars are ~10.7 px tall at 224).
3. **Mirrored: males left, females right, x = share of *total* population**, symmetric fixed range **±17%** (max observed 16.1%). Fixed range keeps *absolute* width meaningful (an old rectangular pyramid genuinely has narrower young bars than a young triangle). Do **not** rescale per image to the max bar: it erases the dispersion information and in §2 it was the nuisance variant that hurt retrieval most.
4. **Second rendering (the "×2")**: total-only, i.e. draw T/2 on each side (or one-sided). This removes sex-ratio information (Gulf states' male migrant bulges dominate the two-sex picture) and is closer to what people mean by "shape". Use it *instead of* mono-colouring the two-sex chart: monochrome two-sex still encodes sex asymmetry in the outline.
5. **Colour**: constant two-tone (e.g. muted blue/red) or single grey — irrelevant as long as it is constant; what matters is contrast vs background (plain white, no alpha). ImageNet-normalised models are fine with either. §2 measured that switching two-tone→mono moved SigLIP2 embeddings to cos 0.897 with themselves, i.e. far more than the distance to the nearest *different* pyramid (0.994) — a reminder that any global rendering change invalidates the whole index.
6. **Resolution**: 224 is enough for 21 bars (each ~11 px × ≤112 px). Larger checkpoints (384/512) buy nothing for this content and cost 3–10× throughput.
7. **Post-processing**: raw cosine between *any* two pyramids is ~0.9+ (SigLIP2) because of the shared layout, so the discriminative signal is a small residual. Measured in §2: mean-centring changes nothing in the rankings (cosine is nearly invariant to it here), **PCA-64 without whitening keeps the rankings (use it for storage), PCA-whitening destroys them** (Spearman with W1 drops from 0.83 to 0.15–0.38 — the low-variance PCs are noise, not signal). Do not whiten.

Risks that remain even with a perfect canonical render: (i) ViT patch-grid aliasing — two pyramids that differ by a sub-pixel bar width can land on different rounding, a discontinuity a metric on the share vector does not have; (ii) the model's notion of "similar" is not Wasserstein-like — it can weigh a spiky 20–24 bin (visually salient) far more than a slow tilt of the whole outline; (iii) the total-only vs two-sex renderings give different neighbour sets and you must choose which one the UI means by "shape".

---

## 5. Storage for a static site (N = 35,787)

| dims | float32 | float16 | int8 | binary (1 bit) |
|---|---|---|---|---|
| 21 (total shares) | 3.0 MB | 1.5 MB | 0.75 MB | — |
| **42 (two-sex shares)** | 6.0 MB | **3.0 MB** | 1.5 MB | — |
| 64 (PCA of an embedding) | 9.2 MB | **4.6 MB** | 2.3 MB | 0.29 MB |
| 512 | 73 MB | 37 MB | 18 MB | 2.3 MB |
| 768 (SigLIP2-base / CLIP-L / DINOv2-base) | 110 MB | 55 MB | 27 MB | 3.4 MB |
| 1024 (Voyage / jina / Titan) | 147 MB | 73 MB | 37 MB | 4.6 MB |
| 1152 (SigLIP2-so400m) | 165 MB | 82 MB | 41 MB | 5.2 MB |
| 3072 (Gemini / Nova max) | 440 MB | 220 MB | 110 MB | 14 MB |

×2 for the 72k two-rendering variant. Notes: (a) the raw **42-d share vectors are 3 MB as float16 and are lossless** — nothing to quantise; PCA on them: 2 comps = 89% var, 5 = 95.8%, 8 = 98.1%, 16 = 99.5%, 32 = 99.97% [M] (the demographic manifold is very low-dimensional, which is the strongest hint that a 768-d image embedding is overkill). (b) For any ViT embedding, ship **PCA-32/64 as float16 (2.3–4.6 MB)** — after mean-centring, 64 PCs keep essentially all neighbour structure for this kind of near-1-parameter-family data; int8 on unit vectors keeps cos-sim ≈0.997 to fp32 [M, random-vector proxy]. (c) Serve as a single little-endian `.bin` + a tiny JSON key file (iso3, year) and `fetch().arrayBuffer()` into a `Float32Array`/`Int8Array` (float16 → decode with `Float16Array` where available, else store int8 with a per-dim scale). (d) A full N×N distance matrix is 5.1 GB float32 — never ship; but *per-year* 237×237 matrices for all 151 years are only 17 MB f16 / 8.5 MB uint8, which is a viable "same-year, all methods" shortcut.

---

## 6. In-browser nearest-neighbour cost (Node 24 V8 as Chrome proxy, single thread, brute force over 35,787 rows, typed arrays) [M]

| Vector | dot-product scan per query | top-50 selection | matrix size |
|---|---|---|---|
| 21-d f32 (W1 via precomputed CDFs, |ΔCDF| sum) | **0.84 ms** | +0.1–0.2 ms | 3 MB |
| 42-d f32 L2 | 0.93 ms | | 6 MB |
| 64-d f32 | 1.5 ms | | 9 MB |
| 128-d f32 | 3.2 ms | | 18 MB |
| 512-d f32 / int8 | 11.9 / 15.8 ms | | 73 / 18 MB |
| 768-d f32 / int8 | 18.3 / 24.2 ms | | 110 / 27 MB |
| 1152-d f32 / int8 | 27.5 / 35.2 ms | | 165 / 41 MB |

Everything is interactive without an index; even 1152-d full-precision is <30 ms on desktop V8 (expect 1.5–3× slower on a phone / Safari JSC; int8 is *slower* than f32 in JS because of the int→double conversion unless you use SIMD/WASM). With a "same year" constraint the candidate set is 236 → microseconds; "range of years" is a contiguous slice if rows are sorted year-major. **Wasserstein-1** on the 21-bin total distribution is exact and closed-form: W1 = Σ_b |CDF_a(b) − CDF_q(b)| × bin width; precompute CDFs once (or on the fly — 0.89 ms vs 0.84 ms, no difference). For two-sex W1 use the 42-d version as two separate 21-bin transports (male↔male, female↔female, weighted by sex share) or W1 on totals + a sex-ratio penalty. In NumPy the same scans are 0.45–1.1 ms and a **full 35,787² W1 matrix takes ~1 minute** (chunked), a 1152-d full Gram matrix ~1 s (BLAS) — so all offline "precompute every method" runs are trivial.

Sanity check that W1 on shares behaves like "shape similarity" (same-year, 2024): USA → Gibraltar, Australia, New Zealand, Montenegro; Niger → Somalia, Mali, Chad; Japan → St Helena, Italy, San Marino, Martinique, Portugal, Greece; Japan-2024 vs *any year* → Anguilla 2054–57 and Thailand 2050–53 (i.e. "who will look like Japan today"), farthest → Rwanda/Niger 1950s–2000s. That is the feature working with zero ML.

---

## 7. Cheap A/B of methods: precompute vs live

Per-method **top-50 neighbour lists** for all 35,787 pyramids: 50 × uint16 = **3.58 MB** per method (indices only), **7.2 MB** with float16 distances; top-20: 1.4 / 2.9 MB. Same-year-only top-50 (uint8 entity index): 1.8 MB per method. Random-index lists compress poorly (expect ≤25% from brotli).

But the *constraint UI* (same year / year range / any year) makes global top-50 lists insufficient: a global top-50 of Japan-2024 is entirely Japan-2023/2025 and Thailand-2050s; the same-year answer is not in it. You would need per-constraint lists (global, same-year, per-decade …) per method, which explodes. Better split:

- **Live compute (default)** for anything ≤128-d: ship the 42-d shares (3 MB f16) and one PCA-64 float16 (4.6 MB) *per embedding method*; each query is 1–3 ms in the browser for any constraint, so *all* methods can be live, and A/B is a toggle in the UI. Exclude the query's own entity (or its ±k years) from the candidate set — otherwise every "nearest" is the same country a year apart.
- **Precomputed lists only for evaluation**, offline, not shipped: compute top-50 per method for the same-year and any-year cases (NumPy, seconds), then measure (a) top-10 overlap between methods, (b) rank correlation of distances on random pairs, (c) a 30–50-pair human "which neighbour looks more alike" blind test rendered by the same canonical renderer. Ship the winners' vectors, not lists.
- If an expensive model *does* win and you want full-dim fidelity, ship its float16 PCA-128 (9 MB) rather than lists; still <10 ms/query.

Offline cost of "every method": W1 full matrix ~1 min, 42-d L2 seconds, each ViT embedding 2.5–11 min on the Mac (§1), Gram matrices ~1 s each.

---

## 8. Recommendation

1. **Default metric = W1 (or L2) on the 42-d share vectors**, computed live in the browser; ship 3 MB. It is exact, deterministic, explainable ("mass moved between age bins"), needs no model, and its neighbours already pass the eye test.
2. **Run the image-embedding idea as an experiment, not the architecture**: SigLIP2-base-224 (Apache-2.0, 2.5 min for the corpus) and DINOv2-base (3.7 min) locally on the canonical NumPy/resvg render; PCA-64 (no whitening); compare neighbour overlap and a blind human check against W1. Keep it in the UI as a selectable "visual similarity (SigLIP2)" method only if it wins something identifiable (e.g. picks up bulge/notch *patterns* that W1 smooths over). Measured evidence in §2 says the embeddings are strongly artifact-sensitive and only moderately rank-correlated with shape distances.
3. If an API is used anyway, Voyage multimodal-3.5 (free tier covers 3 M images; 1,000 per request) or Gemini Embedding 2 (free tier; 6 per request) — not Cohere/jina (most expensive), not Titan (oldest).
4. Rendering: NumPy raster (or hand SVG + resvg if anti-aliasing is wanted); skip matplotlib-per-figure, vl-convert and kaleido for the batch job; use Svelte-side SVG for the *display* of the pyramids in the viewer (a different job from the embedding render).

---

## Sources

- SigLIP 2 collection + blog: https://huggingface.co/collections/google/siglip2-67b5dcef38c175486e240107 ; https://huggingface.co/blog/siglip2 ; https://huggingface.co/google/siglip2-so400m-patch16-512 (Apache-2.0); dims from each repo's `config.json`
- CLIP: https://huggingface.co/openai/clip-vit-large-patch14 ; https://huggingface.co/laion/CLIP-ViT-L-14-laion2B-s32B-b82K (MIT); openai/CLIP GitHub LICENSE (MIT)
- DINOv2: https://huggingface.co/facebook/dinov2-base (Apache-2.0). DINOv3: https://ai.meta.com/resources/models-and-libraries/dinov3-license/ ; https://github.com/facebookresearch/dinov3 ; https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m
- jina-clip-v2: https://huggingface.co/jinaai/jina-clip-v2 (CC BY-NC 4.0); Jina API page (16k tokens/image, rate limits, no batch limit): https://jina.ai/embeddings/
- nomic-embed-vision-v1.5: https://huggingface.co/nomic-ai/nomic-embed-vision-v1.5 ; Nomic pricing overview: https://docs.nomic.ai/docs/models-and-pricing/overview
- Voyage pricing + limits: https://docs.voyageai.com/docs/pricing ; https://docs.voyageai.com/docs/multimodal-embeddings ; https://docs.voyageai.com/reference/multimodal-embeddings-api ; https://blog.voyageai.com/2026/01/15/voyage-multimodal-3-5/ ; batch: https://docs.voyageai.com/docs/batch-inference
- Gemini Embedding 2: https://ai.google.dev/gemini-api/docs/pricing ; https://ai.google.dev/gemini-api/docs/models/gemini-embedding-2-preview ; https://ai.google.dev/gemini-api/docs/embeddings ; https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-embedding-2/
- Cohere Embed v4: https://docs.cohere.com/reference/embed ; https://docs.cohere.com/docs/multimodal-embeddings ; https://docs.cohere.com/docs/cohere-embed ; price $0.12/M text, $0.47/M image tokens: third-party (vercel.com/ai-gateway/models/embed-v4.0, cloudprice.net) — cohere.com/pricing only rendered Model Vault rates
- Amazon Bedrock official price list (us-east-1 CSV): https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.csv ; Titan MM G1 model page: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-multiemb-models.html ; Nova MME: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-amazon-nova-multimodal-embeddings.html ; https://aws.amazon.com/blogs/aws/amazon-nova-multimodal-embeddings-now-available-in-amazon-bedrock/
- Chart models: UniChart https://arxiv.org/abs/2305.14761 ; ChartGemma https://huggingface.co/ahmed-masry/chartgemma ; Chart2Vec https://arxiv.org/abs/2306.08304
- Kaleido regression: https://github.com/plotly/Kaleido/issues/400 ; vl-convert perf note: https://pypi.org/project/vl-convert-python
- OpenCLIP GPU throughput reference (RTX 3090: ViT-L/14 54 img/s, SigLIP so400m 50 img/s): https://gist.github.com/TACIXAT/ecd4f636bf6af28cb69d641e29d7b362
- MLX: https://github.com/Blaizzy/mlx-embeddings
- Pyramid clustering with Wasserstein: Informatica 32 (2008) "Clustering of Population Pyramids"; https://pubmed.ncbi.nlm.nih.gov/25309982/
