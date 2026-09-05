# Human triplets — fit (SYNTHETIC ORACLE, not a human judgment)

Selection: seed 0, 80 unique items + 8 swapped duplicates (gap ≥ 30), anchors = 2024 countries ≥ 1 M (161 in the pool, 0 reused), candidates = same-year countries ≥ 100k; corpus hash `e2bf14d57600`.
Responses: 88/88 answered, 6 ties, median response 6047.0 ms.

Oracle: `{"metric": "blend", "w_l2": null, "sigma_bins": null, "lambda": null, "noise": 0.1, "tie_rate": 0.05, "dup_noise": 0.1, "seed": 0}` — these numbers only exercise the pipeline.

## 1. Self-agreement (pre-registered gate: ≥ 6 of 8 duplicate pairs)

**8 / 8** pairs agreed → **gate met**. Status: informational (self-agreement gate met).

| dup item | original | stratum | original answer | duplicate answer | agree |
|---|---|---|---|---|---|
| 51 | 18 | numeric | A | A | yes |
| 52 | 11 | numeric | A | A | yes |
| 54 | 17 | visual | B | B | yes |
| 58 | 23 | visual | B | B | yes |
| 60 | 24 | visual | B | B | yes |
| 61 | 25 | visual | A | A | yes |
| 80 | 44 | opposite | tie | tie | yes |
| 84 | 4 | numeric | A | A | yes |

## 2. Pairwise agreement per metric (unique items; ties and equal-distance items excluded)

| metric | judged | agree | overall | visual (32) | numeric (38) | opposite (10) |
|---|---|---|---|---|---|---|
| `blend` | 75 | 67 | 89 % | 84 % | 94 % | 89 % |
| `l2` | 75 | 53 | 71 % | 74 % | 66 % | 78 % |
| `w1` | 75 | 50 | 67 % | 74 % | 74 % | 11 % |
| `l2s` | 75 | 55 | 73 % | 77 % | 69 % | 78 % |
| `hel` | 75 | 49 | 65 % | 71 % | 66 % | 44 % |
| `feat` | 75 | 57 | 76 % | 77 % | 71 % | 89 % |
| `w1sex` | 75 | 61 | 81 % | 81 % | 80 % | 89 % |
| `w1bal` | 75 | 49 | 65 % | 71 % | 71 % | 22 % |
| `clr` | 75 | 36 | 48 % | 45 % | 57 % | 22 % |
| `trend@10` | 75 | 39 | 52 % | 61 % | 37 % | 78 % |
| `visual:dinov2-base` | 75 | 43 | 57 % | 52 % | 71 % | 22 % |
| `visual:siglip2-base-naflex` | 75 | 30 | 40 % | 16 % | 63 % | 33 % |

## 3. Paired sign tests (exact two-sided binomial on discordant items, α = 0.05)

MDE: pre-registered: with 32 items one side must win ≥ 22 of the non-tie discordant items (≈ 69 %); the exact two-sided binomial gives p = 0.050 at 22/32 (one-sided 0.025), so 23/32 is the first count called here; with 48 numeric/opposite items the pairwise comparisons resolve gaps ≥ ~20 points.

| comparison | items | ties | discordant | wins a | wins b | p | called |
|---|---|---|---|---|---|---|---|
| `blend` (a) vs `visual:siglip2-base-naflex` (b) | 32 | 1 | 31 | 26 | 5 | < 0.001 | blend |
| `visual:siglip2-base-naflex` (a) vs `visual:dinov2-base` (b) | 32 | 1 | 17 | 3 | 14 | 0.013 | visual:dinov2-base |
| `blend` (a) vs `l2` (b) | 48 | 4 | 13 | 12 | 1 | 0.003 | blend |
| `blend` (a) vs `l2s` (b) | 48 | 4 | 12 | 11 | 1 | 0.006 | blend |
| `blend` (a) vs `hel` (b) | 48 | 4 | 16 | 15 | 1 | < 0.001 | blend |
| `blend` (a) vs `w1sex` (b) | 48 | 4 | 7 | 6 | 1 | 0.125 | no |
| `blend` (a) vs `w1bal` (b) | 48 | 4 | 16 | 15 | 1 | < 0.001 | blend |
| `blend` (a) vs `trend@10` (b) | 48 | 4 | 23 | 22 | 1 | < 0.001 | blend |
| `l2` (a) vs `l2s` (b) | 48 | 4 | 3 | 1 | 2 | 1.000 | no |
| `l2` (a) vs `hel` (b) | 48 | 4 | 11 | 7 | 4 | 0.549 | no |
| `l2` (a) vs `w1sex` (b) | 48 | 4 | 20 | 7 | 13 | 0.263 | no |
| `l2` (a) vs `w1bal` (b) | 48 | 4 | 19 | 11 | 8 | 0.648 | no |
| `l2` (a) vs `trend@10` (b) | 48 | 4 | 22 | 16 | 6 | 0.052 | no |
| `l2s` (a) vs `hel` (b) | 48 | 4 | 12 | 8 | 4 | 0.388 | no |
| `l2s` (a) vs `w1sex` (b) | 48 | 4 | 19 | 7 | 12 | 0.359 | no |
| `l2s` (a) vs `w1bal` (b) | 48 | 4 | 16 | 10 | 6 | 0.454 | no |
| `l2s` (a) vs `trend@10` (b) | 48 | 4 | 25 | 18 | 7 | 0.043 | l2s |
| `hel` (a) vs `w1sex` (b) | 48 | 4 | 23 | 7 | 16 | 0.093 | no |
| `hel` (a) vs `w1bal` (b) | 48 | 4 | 14 | 7 | 7 | 1.000 | no |
| `hel` (a) vs `trend@10` (b) | 48 | 4 | 25 | 16 | 9 | 0.230 | no |
| `w1sex` (a) vs `w1bal` (b) | 48 | 4 | 19 | 14 | 5 | 0.064 | no |
| `w1sex` (a) vs `trend@10` (b) | 48 | 4 | 30 | 23 | 7 | 0.005 | w1sex |
| `w1bal` (a) vs `trend@10` (b) | 48 | 4 | 33 | 20 | 13 | 0.296 | no |

## 4. Leave-one-out grid on the 44 non-tie numeric items (visual items never enter)

### blend weight w (on L2) × smoothing σ

| w_l2 | σ (bins) | judged | agree | in-sample |
|---|---|---|---|---|
| 0.5 | 0 | 44 | 41 | 93 % |
| 0.3 | 0 | 44 | 41 | 93 % |
| 0.4 | 0 | 44 | 41 | 93 % |
| 0.6 | 0 | 44 | 37 | 84 % |
| 0.7 | 0 | 44 | 35 | 80 % |
| 0.5 | 1 | 44 | 38 | 86 % |
| 0.3 | 1 | 44 | 41 | 93 % |
| 0.4 | 1 | 44 | 40 | 91 % |
| 0.6 | 1 | 44 | 35 | 80 % |
| 0.7 | 1 | 44 | 34 | 77 % |

LOO agreement 93 %; LOO-selected cells `[{"cell": {"w_l2": 0.5, "sigma_bins": 0}, "n": 44}]`; in-sample best w = 0.5, σ = 0 bin; best vs shipped default (0.5, 0 — the as-built `blend` smooths nothing; PLAN's 'σ = 1 bin' names the `l2s` kernel): 0–0, p = —.

### w1bal λ

| λ | judged | agree | in-sample |
|---|---|---|---|
| 50 | 44 | 27 | 61 % |
| 0 | 44 | 27 | 61 % |
| 10 | 44 | 27 | 61 % |
| 25 | 44 | 26 | 59 % |
| 100 | 44 | 33 | 75 % |

LOO agreement 75 %; in-sample best λ = 100.0; best vs shipped λ = 50: 7–1, p = 0.070.

## 5. Recommendations (informational per DECISION 4; verdicts.json is never edited by this script)

- default metric: `blend`
- exposed image space: `visual:siglip2-base-naflex` → `visual:dinov2-base` (visual:dinov2-base won the paired test on the 32 visual items (14–3, p = 0.013); G1 still decides in verdicts.json)
- blend / w1bal parameters: w_l2 = 0.5, σ = 0 bin, λ = 50 (shipped defaults kept)
- not modified by fit_params.py — apply by hand after review
