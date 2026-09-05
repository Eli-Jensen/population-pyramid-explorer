# Vintage sensitivity check — Experiment 1 lookalike sets (PREREG §8)

**Generated:** 2026-09-05T02:45:04+00:00 · code revision `65bcfd2` · `scripts/vintage_check.py` · main-run input `evals/econ/backtest_lookalikes.json` (generated 2026-09-05T02:04:13+00:00, code `93a7c2b`).

## 1. Question and method

The main run selects lookalikes as of T on WPP 2024 back-series — today's estimate of what each pyramid *was* at T, not what was known at T (PREREG §8). This check rebuilds the T cross-section from the UN revision current shortly after T and re-runs the two pre-registered selection rules with **everything else held fixed**: the same candidate set C(T) (countries with WPP 2024 population ≥ 1 M at T and a single-source growth window), the same prototype set P(T) (its pyramids stay WPP 2024 — the prototypes are chosen on GDP windows, as pre-registered), the same σ (`data/processed/sigma.json`) and the same `blend` metric (½·L2/σ + ½·per-sex W1/σ on the 42 age×sex shares). Only the **candidates'** 42-share vectors are swapped for the archive's. Query B (PRIMARY) = the k candidates with the smallest min-distance to P(T), ties by the second-smallest prototype distance. Query A = the k candidates nearest China 1990, reported twice: anchor vector from WPP 2024 (only the candidates change) and anchor from the archive as well (everything the selector sees is of the archive's vintage). Candidates the archive does not carry are dropped from the archive-side set and listed. Overlap = Jaccard |A∩B|/|A∪B| between the WPP 2024 set and the archive set at k = 10 (pre-registered expectation ≥ 0.6) and k = 5 (secondary). Revision size per country = ‖s42_archive − s42_2024‖₂ (also in σ_l2 units and as the blend distance between the two vectors).

Revision rule: WPP 2000 for T ≤ 2000, WPP 2010 for 2000 < T ≤ 2010 (PREREG §8). Primary T's: 2010, 2000; the other T's the archives cover are additional rows under the same rule. Robustness rows use the next revision (WPP 2002 for T = 2000).

**Self-check.** Before touching the archive, the re-implementation was run on the WPP 2024 vectors and had to reproduce the recorded lookalike sets exactly (same ids, same order) — see §5.

## 2. Sources

Discovered through `https://population.un.org/wpp/assets/downloads.json` (folder *Archive* → group *CSV files* → *<rev> Revision*), also listed on `https://population.un.org/wpp/Download/Archive/`. Raw files under `data/raw/wpp_archive/` (gitignored). Member read: `WPP<rev>_PopulationByAgeSex_5x5_Medium.csv` (medium variant, 5-year age groups × 5-year time points, 1 July, thousands).

| revision | zip | url | zip sha256 | bytes | member | member sha256 | member date in zip |
|---|---|---|---|---|---|---|---|
| WPP 2000 | `WPP2000-CSV-data.zip` | https://population.un.org/wpp/assets/Excel%20Files/5_Archive/WPP2000-CSV-data.zip | `141a94b3e1746bed1ea712ba636e99aeeef4af47c26fd119eb3856d8f9d61daa` | 14056801 | `WPP2000_PopulationByAgeSex_5x5_Medium.csv` | `c170d74878d23d292b60694943c333a2fb9e998e55d22bafa2775d2f4b7238ad` | 2020-01-24 |
| WPP 2002 | `WPP2002-CSV-data.zip` | https://population.un.org/wpp/assets/Excel%20Files/5_Archive/WPP2002-CSV-data.zip | `9ed02c5aa2cd6e66b0a407fe53cb332371e538a8bed736500eeb9a9c4c33783c` | 13456679 | `WPP2002_PopulationByAgeSex_5x5_Medium.csv` | `e8d30de715c64dca4a115134cafb19c2b66e37fb8dfff1c62cae7ca78cf006e6` | 2020-01-24 |
| WPP 2010 | `WPP2010-CSV-data.zip` | https://population.un.org/wpp/assets/Excel%20Files/5_Archive/WPP2010-CSV-data.zip | `cc51fdb8a9c069abd5d29fc4b94b0fdff1d35442413290cd1d5766793ca5acf0` | 106068723 | `WPP2010_PopulationByAgeSex_5x5_Medium.csv` | `3ac9a1dde36a89f1010cd2f6a7efdfc2a6ac1efffcea4df2bbb7f674803cf635` | 2020-01-24 |

Not used: `WPP<rev>-Excel-files.zip` (the 2010 Excel release, 402 MB, carries the same medium-variant figures as the CSV re-export); WPP 2012 (`WPP2012-CSV-data.zip`, 125 MB) exists at the same location and was not needed.

## 3. Bin alignment

identity: the archive carries the same 21 five-year bins with an open 100+ bin

## 4. Entity mapping

Countries are matched on the UN `LocID` (stable across revisions; the corpus's `pipeline/locations.parquet` carries LocID ↔ ISO3). A predecessor state stands in for the successor that kept its ISO3 code only when the successor has no row of its own; the substitution is flagged on every row that uses it.

**WPP 2000@1990 at 1990:** 185 of 237 corpus countries mapped.
- predecessor rows used: LocID 736 “Sudan (Former)” → SDN (Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan); LocID 891 “Serbia and Montenegro” → SRB (Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo))
- archive countries/areas (LocID < 900) with no corpus id: LocID 530 “Netherlands Antilles” — Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities); LocID 830 “Channel Islands” — Channel Islands (GGY and JEY are separate WPP 2024 entities)
- corpus countries absent from the archive (52, none ≥ 1 M except where listed under the T rows): ABW, AIA, AND, ASM, ATG, BES, BLM, BMU, COK, CUW, CYM, DMA, FLK, FRO, FSM, GGY, GIB, GRD, GRL, IMN, JEY, KIR, KNA, LIE, MAF, MCO, MHL, MNE, MNP, MSR, MYT, NIU, NRU, PLW, SHN, SMR, SPM, SSD, STP, SXM, SYC, TCA, TKL, TON, TUV, TWN, VAT, VCT, VGB, VIR, WLF, XKX

**WPP 2000@1995 at 1995:** 185 of 237 corpus countries mapped.
- predecessor rows used: LocID 736 “Sudan (Former)” → SDN (Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan); LocID 891 “Serbia and Montenegro” → SRB (Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo))
- archive countries/areas (LocID < 900) with no corpus id: LocID 530 “Netherlands Antilles” — Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities); LocID 830 “Channel Islands” — Channel Islands (GGY and JEY are separate WPP 2024 entities)
- corpus countries absent from the archive (52, none ≥ 1 M except where listed under the T rows): ABW, AIA, AND, ASM, ATG, BES, BLM, BMU, COK, CUW, CYM, DMA, FLK, FRO, FSM, GGY, GIB, GRD, GRL, IMN, JEY, KIR, KNA, LIE, MAF, MCO, MHL, MNE, MNP, MSR, MYT, NIU, NRU, PLW, SHN, SMR, SPM, SSD, STP, SXM, SYC, TCA, TKL, TON, TUV, TWN, VAT, VCT, VGB, VIR, WLF, XKX

**WPP 2000@2000 at 2000:** 185 of 237 corpus countries mapped.
- predecessor rows used: LocID 736 “Sudan (Former)” → SDN (Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan); LocID 891 “Serbia and Montenegro” → SRB (Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo))
- archive countries/areas (LocID < 900) with no corpus id: LocID 530 “Netherlands Antilles” — Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities); LocID 830 “Channel Islands” — Channel Islands (GGY and JEY are separate WPP 2024 entities)
- corpus countries absent from the archive (52, none ≥ 1 M except where listed under the T rows): ABW, AIA, AND, ASM, ATG, BES, BLM, BMU, COK, CUW, CYM, DMA, FLK, FRO, FSM, GGY, GIB, GRD, GRL, IMN, JEY, KIR, KNA, LIE, MAF, MCO, MHL, MNE, MNP, MSR, MYT, NIU, NRU, PLW, SHN, SMR, SPM, SSD, STP, SXM, SYC, TCA, TKL, TON, TUV, TWN, VAT, VCT, VGB, VIR, WLF, XKX

**WPP 2002@2000 at 2000:** 190 of 237 corpus countries mapped.
- predecessor rows used: LocID 736 “Sudan (Former)” → SDN (Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan); LocID 891 “Serbia and Montenegro” → SRB (Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo))
- archive countries/areas (LocID < 900) with no corpus id: LocID 530 “Netherlands Antilles” — Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities); LocID 830 “Channel Islands” — Channel Islands (GGY and JEY are separate WPP 2024 entities)
- corpus countries absent from the archive (47, none ≥ 1 M except where listed under the T rows): ABW, AIA, AND, ASM, ATG, BES, BLM, BMU, COK, CUW, CYM, DMA, FLK, FRO, GGY, GIB, GRD, GRL, IMN, JEY, KIR, KNA, LIE, MAF, MCO, MHL, MNE, MNP, MSR, MYT, NIU, NRU, PLW, SHN, SMR, SPM, SSD, SXM, SYC, TCA, TKL, TUV, TWN, VAT, VGB, WLF, XKX

**WPP 2010@2005 at 2005:** 195 of 237 corpus countries mapped.
- predecessor rows used: LocID 736 “Sudan (Former)” → SDN (Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan)
- archive countries/areas (LocID < 900) with no corpus id: LocID 530 “Netherlands Antilles” — Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities); LocID 830 “Channel Islands” — Channel Islands (GGY and JEY are separate WPP 2024 entities)
- labels: LocID 158 labelled 'Other non-specified areas' in WPP 2010/2012 (Taiwan Province of China)
- corpus countries absent from the archive (42, none ≥ 1 M except where listed under the T rows): AIA, AND, ASM, ATG, BES, BLM, BMU, COK, CUW, CYM, DMA, FLK, FRO, GGY, GIB, GRL, IMN, JEY, KIR, KNA, LIE, MAF, MCO, MHL, MNP, MSR, NIU, NRU, PLW, SHN, SMR, SPM, SSD, SXM, SYC, TCA, TKL, TUV, VAT, VGB, WLF, XKX

**WPP 2010@2010 at 2010:** 195 of 237 corpus countries mapped.
- predecessor rows used: LocID 736 “Sudan (Former)” → SDN (Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan)
- archive countries/areas (LocID < 900) with no corpus id: LocID 530 “Netherlands Antilles” — Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities); LocID 830 “Channel Islands” — Channel Islands (GGY and JEY are separate WPP 2024 entities)
- labels: LocID 158 labelled 'Other non-specified areas' in WPP 2010/2012 (Taiwan Province of China)
- corpus countries absent from the archive (42, none ≥ 1 M except where listed under the T rows): AIA, AND, ASM, ATG, BES, BLM, BMU, COK, CUW, CYM, DMA, FLK, FRO, GGY, GIB, GRL, IMN, JEY, KIR, KNA, LIE, MAF, MCO, MHL, MNP, MSR, NIU, NRU, PLW, SHN, SMR, SPM, SSD, SXM, SYC, TCA, TKL, TUV, VAT, VGB, WLF, XKX

## 5. Results per T

**Expectation:** k = 10 Jaccard(WPP 2024 set, archive set) ≥ 0.6 at every T where an archive exists (PREREG §8); Query B is the primary rule — met in 4 of 15 (query, T) cells; not met: B@1990, B@1995, B@2000, A_anchor_wpp2024@2000, A_anchor_archive@2000, B@2005, A_anchor_wpp2024@2005, A_anchor_archive@2005, B@2010, A_anchor_wpp2024@2010, A_anchor_archive@2010. Query B did NOT meet the expectation at every T.

### T = 2010 · WPP 2010 (primary)

C(T): 156 candidates, 155 with an archive vector; without one (dropped from the archive side): SSD. P(T): 139 prototypes (WPP 2024 pyramids).
Predecessor rows inside C(T): SDN ← LocID 736 “Sudan (Former)”.

Self-check (WPP 2024 vectors → recorded sets): B k=10: reproduced; B k=5: reproduced; A k=10: reproduced; A k=5: reproduced.

| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |
|---|---|---|---|---|---|---|
| B | 10 | NGA, SLE, LBR, TCD, TZA, SOM, COD, AGO, ECU, MDG | BEN, TCD, GHA, MDG, SOM, PHL, ECU, GIN, TZA, UGA | 5 | 0.33 | **not met** |
| B | 5 | NGA, SLE, LBR, TCD, TZA | BEN, TCD, GHA, MDG, SOM | 1 | 0.11 | — |
| A_anchor_wpp2024 | 10 | DZA, UZB, MAR, IND, ECU, DOM, LBY, PRY, KGZ, MYS | DZA, IND, EGY, ZAF, PER, BGD, ECU, UZB, LBY, VEN | 5 | 0.33 | **not met** |
| A_anchor_wpp2024 | 5 | DZA, UZB, MAR, IND, ECU | DZA, IND, EGY, ZAF, PER | 2 | 0.25 | — |
| A_anchor_archive | 10 | DZA, UZB, MAR, IND, ECU, DOM, LBY, PRY, KGZ, MYS | IND, DZA, PER, VEN, ECU, EGY, ZAF, MYS, DOM, UZB | 6 | 0.43 | **not met** |
| A_anchor_archive | 5 | DZA, UZB, MAR, IND, ECU | IND, DZA, PER, VEN, ECU | 3 | 0.43 | — |

Rank continuity (additional diagnostics, not pre-registered): B: Spearman ρ 0.932 over 155 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 11 / max 37 (5 within 10, 7 within 20); median |Δ statistic| 0.0256 vs a WPP 2024 rank-1→rank-20 spread of 0.0513 · A_anchor_wpp2024: Spearman ρ 0.966 over 154 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 10 / max 19 (5 within 10, 10 within 20); median |Δ statistic| 0.0385 vs a WPP 2024 rank-1→rank-20 spread of 0.1746 · A_anchor_archive: Spearman ρ 0.965 over 154 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 10 / max 19 (6 within 10, 10 within 20); median |Δ statistic| 0.0663 vs a WPP 2024 rank-1→rank-20 spread of 0.1746.

Revision size over the 155 candidates with both vectors: median L2 0.0094 (max 0.0562, SAU); in σ_l2 units median 0.166 (max 0.988); blend distance between the two vintages median 0.141 (max 1.122); |total-population revision| median 2.1 % (max 41.1 %, GNQ).

Ten largest shape revisions (L2):

| iso3 | name | L2 | L2/σ | blend d | Δpop | via |
|---|---|---|---|---|---|---|
| SAU | Saudi Arabia | 0.0562 | 0.988 | 1.122 | +9.1 % | — |
| SGP | Singapore | 0.0476 | 0.838 | 0.668 | +0.2 % | — |
| BDI | Burundi | 0.0433 | 0.761 | 0.580 | -10.6 % | — |
| ARE | United Arab Emirates | 0.0359 | 0.631 | 0.632 | +8.3 % | — |
| ZWE | Zimbabwe | 0.0353 | 0.620 | 0.556 | -5.9 % | — |
| CAF | Central African Republic | 0.0301 | 0.530 | 0.436 | -2.0 % | — |
| GNQ | Equatorial Guinea | 0.0285 | 0.501 | 0.402 | -41.1 % | — |
| KWT | Kuwait | 0.0283 | 0.499 | 0.558 | -7.0 % | — |
| TGO | Togo | 0.0277 | 0.487 | 0.374 | -4.7 % | — |
| JOR | Jordan | 0.0269 | 0.473 | 0.346 | -15.2 % | — |

China 1990 anchor: archive vs WPP 2024 L2 0.0070 (0.123 σ_l2), blend distance 0.136.

### T = 2005 · WPP 2010 (additional (same PREREG §8 rule))

C(T): 152 candidates, 152 with an archive vector. P(T): 125 prototypes (WPP 2024 pyramids).
Predecessor rows inside C(T): SDN ← LocID 736 “Sudan (Former)”.

Self-check (WPP 2024 vectors → recorded sets): B k=10: reproduced; B k=5: reproduced; A k=10: reproduced; A k=5: reproduced.

| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |
|---|---|---|---|---|---|---|
| B | 10 | SLE, LBR, COD, SOM, AFG, NGA, AGO, TCD, TZA, BOL | TCD, BEN, MDG, BOL, GIN, UGA, MOZ, GAB, TZA, ETH | 3 | 0.18 | **not met** |
| B | 5 | SLE, LBR, COD, SOM, AFG | TCD, BEN, MDG, BOL, GIN | 0 | 0.00 | — |
| A_anchor_wpp2024 | 10 | MMR, DZA, IDN, PAN, MAR, MYS, PER, VEN, IND, LBN | LBY, VEN, IDN, ECU, PER, MYS, DZA, IND, PAN, CRI | 7 | 0.54 | **not met** |
| A_anchor_wpp2024 | 5 | MMR, DZA, IDN, PAN, MAR | LBY, VEN, IDN, ECU, PER | 1 | 0.11 | — |
| A_anchor_archive | 10 | MMR, DZA, IDN, PAN, MAR, MYS, PER, VEN, IND, LBN | IND, CRI, IDN, PAN, VEN, MYS, LBY, TUR, ECU, PER | 6 | 0.43 | **not met** |
| A_anchor_archive | 5 | MMR, DZA, IDN, PAN, MAR | IND, CRI, IDN, PAN, VEN | 2 | 0.25 | — |

Rank continuity (additional diagnostics, not pre-registered): B: Spearman ρ 0.927 over 152 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 20 / max 46 (3 within 10, 6 within 20); median |Δ statistic| 0.0229 vs a WPP 2024 rank-1→rank-20 spread of 0.0791 · A_anchor_wpp2024: Spearman ρ 0.965 over 151 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 8 / max 30 (7 within 10, 9 within 20); median |Δ statistic| 0.0325 vs a WPP 2024 rank-1→rank-20 spread of 0.1353 · A_anchor_archive: Spearman ρ 0.961 over 151 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 8 / max 26 (6 within 10, 9 within 20); median |Δ statistic| 0.0593 vs a WPP 2024 rank-1→rank-20 spread of 0.1353.

Revision size over the 152 candidates with both vectors: median L2 0.0083 (max 0.0436, SAU); in σ_l2 units median 0.146 (max 0.768); blend distance between the two vintages median 0.134 (max 0.717); |total-population revision| median 1.8 % (max 30.7 %, SRB).

Ten largest shape revisions (L2):

| iso3 | name | L2 | L2/σ | blend d | Δpop | via |
|---|---|---|---|---|---|---|
| SAU | Saudi Arabia | 0.0436 | 0.768 | 0.717 | +16.9 % | — |
| SGP | Singapore | 0.0436 | 0.767 | 0.544 | -0.1 % | — |
| ZWE | Zimbabwe | 0.0307 | 0.540 | 0.526 | +0.7 % | — |
| ARE | United Arab Emirates | 0.0300 | 0.529 | 0.430 | -12.8 % | — |
| BDI | Burundi | 0.0290 | 0.511 | 0.410 | -4.4 % | — |
| CIV | Côte d'Ivoire | 0.0265 | 0.466 | 0.458 | -10.2 % | — |
| SRB | Serbia | 0.0240 | 0.421 | 0.491 | +30.7 % | — |
| JOR | Jordan | 0.0234 | 0.411 | 0.271 | -11.4 % | — |
| SDN | Sudan | 0.0216 | 0.380 | 0.333 | +22.9 % | Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan |
| JAM | Jamaica | 0.0212 | 0.373 | 0.291 | -0.2 % | — |

China 1990 anchor: archive vs WPP 2024 L2 0.0070 (0.123 σ_l2), blend distance 0.136.

### T = 2000 · WPP 2000 (primary)

C(T): 151 candidates, 150 with an archive vector; without one (dropped from the archive side): TWN. P(T): 106 prototypes (WPP 2024 pyramids).
Predecessor rows inside C(T): SDN ← LocID 736 “Sudan (Former)”; SRB ← LocID 891 “Serbia and Montenegro”.

Self-check (WPP 2024 vectors → recorded sets): B k=10: reproduced; B k=5: reproduced; A k=10: reproduced; A k=5: reproduced.

| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |
|---|---|---|---|---|---|---|
| B | 10 | COD, GIN, SLE, AFG, ECU, MWI, IDN, TUR, AGO, BEN | COG, GNB, TCD, ETH, NER, MDG, MLI, SLE, UGA, MRT | 1 | 0.05 | **not met** |
| B | 5 | COD, GIN, SLE, AFG, ECU | COG, GNB, TCD, ETH, NER | 0 | 0.00 | — |
| A_anchor_wpp2024 | 10 | TUR, IDN, MMR, PAN, TUN, BRA, LBN, COL, CRI, VEN | TUR, IDN, PAN, CRI, TUN, ALB, IND, DOM, BRA, MYS | 6 | 0.43 | **not met** |
| A_anchor_wpp2024 | 5 | TUR, IDN, MMR, PAN, TUN | TUR, IDN, PAN, CRI, TUN | 4 | 0.67 | — |
| A_anchor_archive | 10 | TUR, IDN, MMR, PAN, TUN, BRA, LBN, COL, CRI, VEN | TUR, ALB, IDN, TUN, LKA, PAN, IND, CRI, BRA, THA | 6 | 0.43 | **not met** |
| A_anchor_archive | 5 | TUR, IDN, MMR, PAN, TUN | TUR, ALB, IDN, TUN, LKA | 3 | 0.43 | — |

Rank continuity (additional diagnostics, not pre-registered): B: Spearman ρ 0.859 over 150 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 20 / max 41 (1 within 10, 6 within 20); median |Δ statistic| 0.0392 vs a WPP 2024 rank-1→rank-20 spread of 0.0672 · A_anchor_wpp2024: Spearman ρ 0.944 over 149 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 7 / max 23 (6 within 10, 9 within 20); median |Δ statistic| 0.0529 vs a WPP 2024 rank-1→rank-20 spread of 0.2799 · A_anchor_archive: Spearman ρ 0.927 over 149 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 8 / max 23 (6 within 10, 9 within 20); median |Δ statistic| 0.0791 vs a WPP 2024 rank-1→rank-20 spread of 0.2799.

Revision size over the 150 candidates with both vectors: median L2 0.0102 (max 0.1010, ARE); in σ_l2 units median 0.180 (max 1.776); blend distance between the two vintages median 0.159 (max 1.376); |total-population revision| median 2.2 % (max 37.1 %, SRB).

Ten largest shape revisions (L2):

| iso3 | name | L2 | L2/σ | blend d | Δpop | via |
|---|---|---|---|---|---|---|
| ARE | United Arab Emirates | 0.1010 | 1.776 | 1.376 | -25.4 % | — |
| KWT | Kuwait | 0.0895 | 1.574 | 0.986 | -2.1 % | — |
| OMN | Oman | 0.0525 | 0.924 | 1.070 | +11.2 % | — |
| LBR | Liberia | 0.0408 | 0.718 | 0.521 | -0.5 % | — |
| SAU | Saudi Arabia | 0.0365 | 0.642 | 0.537 | +25.8 % | — |
| SGP | Singapore | 0.0358 | 0.630 | 0.477 | -0.4 % | — |
| YEM | Yemen | 0.0339 | 0.596 | 0.389 | -6.5 % | — |
| AFG | Afghanistan | 0.0339 | 0.596 | 0.552 | +8.1 % | — |
| GMB | Gambia | 0.0337 | 0.593 | 0.482 | -10.5 % | — |
| ZWE | Zimbabwe | 0.0313 | 0.550 | 0.557 | +6.2 % | — |

China 1990 anchor: archive vs WPP 2024 L2 0.0076 (0.133 σ_l2), blend distance 0.143.

### T = 1995 · WPP 2000 (additional (same PREREG §8 rule))

C(T): 150 candidates, 149 with an archive vector; without one (dropped from the archive side): TWN. P(T): 92 prototypes (WPP 2024 pyramids).
Predecessor rows inside C(T): SDN ← LocID 736 “Sudan (Former)”; SRB ← LocID 891 “Serbia and Montenegro”.

Self-check (WPP 2024 vectors → recorded sets): B k=10: reproduced; B k=5: reproduced; A k=10: reproduced; A k=5: reproduced.

| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |
|---|---|---|---|---|---|---|
| B | 10 | SLE, MWI, PSE, GIN, COD, LAO, AFG, NGA, LBR, BOL | GNB, COG, GIN, ETH, NER, CMR, SLE, NGA, TCD, MDG | 3 | 0.18 | **not met** |
| B | 5 | SLE, MWI, PSE, GIN, COD | GNB, COG, GIN, ETH, NER | 1 | 0.11 | — |
| A_anchor_wpp2024 | 10 | LKA, TUR, MUS, IDN, BRA, PAN, TUN, MMR, CHL, THA | ALB, TUR, PAN, LKA, THA, IDN, BRA, MUS, CRI, CHL | 8 | 0.67 | met |
| A_anchor_wpp2024 | 5 | LKA, TUR, MUS, IDN, BRA | ALB, TUR, PAN, LKA, THA | 2 | 0.25 | — |
| A_anchor_archive | 10 | LKA, TUR, MUS, IDN, BRA, PAN, TUN, MMR, CHL, THA | LKA, ALB, THA, TUR, MUS, PAN, CHL, PRK, IDN, BRA | 8 | 0.67 | met |
| A_anchor_archive | 5 | LKA, TUR, MUS, IDN, BRA | LKA, ALB, THA, TUR, MUS | 3 | 0.43 | — |

Rank continuity (additional diagnostics, not pre-registered): B: Spearman ρ 0.824 over 149 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 18 / max 129 (3 within 10, 6 within 20); median |Δ statistic| 0.0299 vs a WPP 2024 rank-1→rank-20 spread of 0.0672 · A_anchor_wpp2024: Spearman ρ 0.918 over 148 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 6 / max 17 (8 within 10, 10 within 20); median |Δ statistic| 0.0488 vs a WPP 2024 rank-1→rank-20 spread of 0.2436 · A_anchor_archive: Spearman ρ 0.896 over 148 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 6 / max 22 (8 within 10, 9 within 20); median |Δ statistic| 0.0794 vs a WPP 2024 rank-1→rank-20 spread of 0.2436.

Revision size over the 149 candidates with both vectors: median L2 0.0086 (max 0.0890, KWT); in σ_l2 units median 0.152 (max 1.565); blend distance between the two vintages median 0.148 (max 1.080); |total-population revision| median 1.8 % (max 34.8 %, SRB).

Ten largest shape revisions (L2):

| iso3 | name | L2 | L2/σ | blend d | Δpop | via |
|---|---|---|---|---|---|---|
| KWT | Kuwait | 0.0890 | 1.565 | 1.006 | +0.6 % | — |
| ARE | United Arab Emirates | 0.0749 | 1.318 | 0.981 | -3.4 % | — |
| LBR | Liberia | 0.0626 | 1.101 | 0.793 | -5.7 % | — |
| OMN | Oman | 0.0476 | 0.837 | 1.080 | +1.6 % | — |
| ZWE | Zimbabwe | 0.0359 | 0.631 | 0.592 | +4.6 % | — |
| SAU | Saudi Arabia | 0.0348 | 0.612 | 0.421 | +28.6 % | — |
| BIH | Bosnia and Herzegovina | 0.0330 | 0.580 | 0.490 | -7.9 % | — |
| RWA | Rwanda | 0.0323 | 0.568 | 0.523 | -12.2 % | — |
| GMB | Gambia | 0.0314 | 0.553 | 0.444 | -11.8 % | — |
| AFG | Afghanistan | 0.0292 | 0.514 | 0.507 | +11.8 % | — |

China 1990 anchor: archive vs WPP 2024 L2 0.0076 (0.133 σ_l2), blend distance 0.143.

### T = 1990 · WPP 2000 (additional (same PREREG §8 rule))

C(T): 148 candidates, 147 with an archive vector; without one (dropped from the archive side): TWN. P(T): 82 prototypes (WPP 2024 pyramids).
Predecessor rows inside C(T): SDN ← LocID 736 “Sudan (Former)”; SRB ← LocID 891 “Serbia and Montenegro”.

Self-check (WPP 2024 vectors → recorded sets): B k=10: reproduced; B k=5: reproduced; A k=10: reproduced; A k=5: reproduced.

| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |
|---|---|---|---|---|---|---|
| B | 10 | NGA, SLE, COD, CMR, PSE, LBR, GIN, LAO, NPL, BOL | CMR, TCD, GMB, SLE, NER, ETH, GIN, MOZ, MRT, MDG | 3 | 0.18 | **not met** |
| B | 5 | NGA, SLE, COD, CMR, PSE | CMR, TCD, GMB, SLE, NER | 2 | 0.25 | — |
| A_anchor_wpp2024 | 10 | MUS, CHL, THA, ALB, LKA, KOR, TTO, TWN, TUR, ISR | ALB, CHL, LKA, MUS, PRK, THA, KOR, TTO, PAN, TUR | 8 | 0.67 | met |
| A_anchor_wpp2024 | 5 | MUS, CHL, THA, ALB, LKA | ALB, CHL, LKA, MUS, PRK | 4 | 0.67 | — |
| A_anchor_archive | 10 | MUS, CHL, THA, ALB, LKA, KOR, TTO, TWN, TUR, ISR | LKA, ALB, PRK, KOR, CHL, MUS, CUB, THA, ISR, TTO | 8 | 0.67 | met |
| A_anchor_archive | 5 | MUS, CHL, THA, ALB, LKA | LKA, ALB, PRK, KOR, CHL | 3 | 0.43 | — |

Rank continuity (additional diagnostics, not pre-registered): B: Spearman ρ 0.846 over 147 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 24 / max 68 (3 within 10, 5 within 20); median |Δ statistic| 0.0239 vs a WPP 2024 rank-1→rank-20 spread of 0.0841 · A_anchor_wpp2024: Spearman ρ 0.924 over 146 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 6 / max 12 (8 within 10, 10 within 20); median |Δ statistic| 0.0352 vs a WPP 2024 rank-1→rank-20 spread of 0.3218 · A_anchor_archive: Spearman ρ 0.892 over 146 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 7 / max 16 (8 within 10, 10 within 20); median |Δ statistic| 0.0785 vs a WPP 2024 rank-1→rank-20 spread of 0.3218.

Revision size over the 147 candidates with both vectors: median L2 0.0082 (max 0.0446, ARE); in σ_l2 units median 0.144 (max 0.784); blend distance between the two vintages median 0.138 (max 0.706); |total-population revision| median 1.8 % (max 44.7 %, SAU).

Ten largest shape revisions (L2):

| iso3 | name | L2 | L2/σ | blend d | Δpop | via |
|---|---|---|---|---|---|---|
| ARE | United Arab Emirates | 0.0446 | 0.784 | 0.620 | +6.1 % | — |
| KWT | Kuwait | 0.0415 | 0.729 | 0.496 | +27.2 % | — |
| LBR | Liberia | 0.0399 | 0.702 | 0.519 | -3.6 % | — |
| OMN | Oman | 0.0315 | 0.555 | 0.706 | +1.2 % | — |
| GMB | Gambia | 0.0274 | 0.483 | 0.375 | -12.0 % | — |
| CAF | Central African Republic | 0.0246 | 0.432 | 0.464 | +2.5 % | — |
| KHM | Cambodia | 0.0245 | 0.431 | 0.271 | +30.6 % | — |
| SDN | Sudan | 0.0235 | 0.413 | 0.328 | +12.7 % | Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan |
| SRB | Serbia | 0.0231 | 0.407 | 0.461 | +29.0 % | Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo) |
| LBY | Libya | 0.0229 | 0.402 | 0.445 | -3.0 % | — |

China 1990 anchor: archive vs WPP 2024 L2 0.0076 (0.133 σ_l2), blend distance 0.143.

## 6. Robustness rows (next revision)

### T = 2000 · WPP 2002 (robustness: WPP 2002 instead of WPP 2000)

C(T): 151 candidates, 150 with an archive vector; without one (dropped from the archive side): TWN. P(T): 106 prototypes (WPP 2024 pyramids).
Predecessor rows inside C(T): SDN ← LocID 736 “Sudan (Former)”; SRB ← LocID 891 “Serbia and Montenegro”.

Self-check (WPP 2024 vectors → recorded sets): B k=10: reproduced; B k=5: reproduced; A k=10: reproduced; A k=5: reproduced.

| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |
|---|---|---|---|---|---|---|
| B | 10 | COD, GIN, SLE, AFG, ECU, MWI, IDN, TUR, AGO, BEN | TCD, GNB, MWI, NER, YEM, MDG, COG, SLE, NGA, GMB | 2 | 0.11 | **not met** |
| B | 5 | COD, GIN, SLE, AFG, ECU | TCD, GNB, MWI, NER, YEM | 0 | 0.00 | — |
| A_anchor_wpp2024 | 10 | TUR, IDN, MMR, PAN, TUN, BRA, LBN, COL, CRI, VEN | TUR, PAN, IDN, CRI, TUN, ALB, DOM, BRA, MYS, IND | 6 | 0.43 | **not met** |
| A_anchor_wpp2024 | 5 | TUR, IDN, MMR, PAN, TUN | TUR, PAN, IDN, CRI, TUN | 4 | 0.67 | — |
| A_anchor_archive | 10 | TUR, IDN, MMR, PAN, TUN, BRA, LBN, COL, CRI, VEN | ALB, TUR, IDN, CRI, PAN, TUN, IND, BRA, LKA, DOM | 6 | 0.43 | **not met** |
| A_anchor_archive | 5 | TUR, IDN, MMR, PAN, TUN | ALB, TUR, IDN, CRI, PAN | 3 | 0.43 | — |

Rank continuity (additional diagnostics, not pre-registered): B: Spearman ρ 0.905 over 150 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 18 / max 39 (2 within 10, 5 within 20); median |Δ statistic| 0.0339 vs a WPP 2024 rank-1→rank-20 spread of 0.0672 · A_anchor_wpp2024: Spearman ρ 0.947 over 149 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 6 / max 18 (6 within 10, 10 within 20); median |Δ statistic| 0.0479 vs a WPP 2024 rank-1→rank-20 spread of 0.2799 · A_anchor_archive: Spearman ρ 0.936 over 149 common candidates; the WPP 2024 k = 10 set sits at archive ranks median 7 / max 21 (6 within 10, 9 within 20); median |Δ statistic| 0.0604 vs a WPP 2024 rank-1→rank-20 spread of 0.2799.

Revision size over the 150 candidates with both vectors: median L2 0.0095 (max 0.0631, ARE); in σ_l2 units median 0.167 (max 1.110); blend distance between the two vintages median 0.151 (max 1.015); |total-population revision| median 1.9 % (max 37.2 %, SRB).

Ten largest shape revisions (L2):

| iso3 | name | L2 | L2/σ | blend d | Δpop | via |
|---|---|---|---|---|---|---|
| ARE | United Arab Emirates | 0.0631 | 1.110 | 1.015 | -19.3 % | — |
| KWT | Kuwait | 0.0380 | 0.668 | 0.582 | +14.9 % | — |
| SGP | Singapore | 0.0359 | 0.631 | 0.479 | -0.5 % | — |
| AFG | Afghanistan | 0.0341 | 0.600 | 0.553 | +6.3 % | — |
| SDN | Sudan | 0.0295 | 0.519 | 0.426 | +13.0 % | Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan |
| GMB | Gambia | 0.0284 | 0.500 | 0.418 | -9.8 % | — |
| CIV | Côte d'Ivoire | 0.0280 | 0.492 | 0.422 | -10.6 % | — |
| OMN | Oman | 0.0265 | 0.467 | 0.301 | +14.3 % | — |
| RWA | Rwanda | 0.0252 | 0.444 | 0.315 | -6.0 % | — |
| SRB | Serbia | 0.0249 | 0.438 | 0.524 | +37.2 % | Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo) |

China 1990 anchor: archive vs WPP 2024 L2 0.0083 (0.146 σ_l2), blend distance 0.145.

## 7. Caveats

- The archive CSVs are the UN's 2020 re-export of each revision's database (member dates 2020-01-24 inside the zips), not the files distributed at the time; they already carry the 21-bin (100+) layout with populated 85–99 and 100+ cells, whereas the printed WPP 2000/2002 tables used an 80+ open bin. The figures are the revision's, the layout is the re-export's.
- Only the candidates' shape vectors are of the archive's vintage. The candidate set C(T) (WPP 2024 population ≥ 1 M at T plus a growth window) and the prototype set P(T) (top-decile GDP windows; WPP 2024 pyramids) are held at the main run's values, as pre-registered, so the check isolates the demographic-revision channel and does not re-run the full backtest.
- σ (sigma.json) is the WPP 2024 corpus's; the archive vectors are measured with the main run's yardstick, which is the quantity of interest (would the same rule, applied to the numbers available at T, have chosen the same countries?).
- Predecessor states (Sudan (Former) → SDN; Serbia and Montenegro → SRB) stand in for successors that have no archive row; their archive vectors describe a larger territory than the WPP 2024 back-series for the successor. Candidates without any archive row (e.g. SSD in WPP 2010; TWN in WPP 2000/2002) are dropped from the archive-side set, which can only lower the Jaccard.
- WPP 2000 for T = 1990/1995 and WPP 2010 for T = 2005 are what PREREG §8 prescribes (the revision current for T ≤ 2000 / ≤ 2010), not the revision current at those T's (WPP 1990/1994/2004 exist only as Excel zips and were not used).
- Jaccard is a set statistic on k ids: one swapped country changes k = 10 Jaccard from 1.00 to 0.82 and k = 5 from 1.00 to 0.67; the k = 5 rows are secondary and no threshold was pre-registered for them.
