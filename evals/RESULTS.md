# Similarity evaluation — RESULTS (M0 (no triplets), verdicts informational per DECISION 4)

Built 2026-09-04T22:52:19+00:00 · git `a5b987458d60f64e1f106739193d6cb2d7a116f2` · corpus 42280 rows / 237 countries + 43 aggregates · data_hash `e2bf14d57600d364…` (sha256(corpus_u16 little-endian bytes)) · σ from data/processed/sigma.json · seed 0 · 300 continuity queries per span, 20 opposites anchors · protocol: `evals/protocol.md`.

Label files (sha256, first 16): `hahn_klimroth_2025.yaml` 6bddac9b05d100e2, `korenjak_cerne.yaml` d0901dc7a68a124f, `rieti.yaml` f9bf2421c7375e0b, `thresholds_stage.yaml` 48d818d972c1ef6d, `yoshida_epitome.yaml` cd6cca3cbfd3163d.  
Korenjak-Černe fallback status: **rung1_2008_lists** (2015 memberships paywalled; 2008 lists, IDB-2008 vintage); vintage-sensitivity row: omitted — IDB-2008 totals unavailable.

Image spaces: `dinov2-base` rows 42280, alignment: exact; `siglip2-base-naflex` rows 42280, alignment: exact.

## G1 continuity (gate on the observed span: C1 ≥ 0.95, C5 ≥ 0.99)

| metric | C1 obs | C5 obs | C1 proj | C5 proj | gate |
|---|---|---|---|---|---|
| blend | 0.993 ✓ | 1.000 ✓ | 1.000 | 1.000 | ✓ |
| l2 | 0.990 ✓ | 0.997 ✓ | 1.000 | 1.000 | ✓ |
| w1 | 0.793 ✗ | 0.930 ✗ | 0.650 | 0.800 | ✗ |
| l2s | 0.990 ✓ | 0.997 ✓ | 0.993 | 1.000 | ✓ |
| hel | 1.000 ✓ | 1.000 ✓ | 1.000 | 1.000 | ✓ |
| feat | 0.863 ✗ | 0.953 ✗ | 0.933 | 0.990 | ✗ |
| w1sex | 0.9500 ✓ | 0.997 ✓ | 0.917 | 0.997 | ✓ |
| w1bal | 0.997 ✓ | 0.997 ✓ | 0.977 | 1.000 | ✓ |
| clr | 0.987 ✓ | 0.9900 ✓ | 0.997 | 1.000 | ✓ |
| trend | 0.990 ✓ | 1.000 ✓ | 0.997 | 1.000 | ✓ |
| path | 1.000 ✓ | 1.000 ✓ | 1.000 | 1.000 | ✓ |
| visual:dinov2-base | 0.513 ✗ | 0.733 ✗ | 0.587 | 0.830 | ✗ |
| visual:siglip2-base-naflex | 0.550 ✗ | 0.777 ✗ | 0.723 | 0.890 | ✗ |

## G2 external labels

| metric | KC2006 agree (≥0.7) | KC1996 | KC2001 | HK family agree (≥0.85) | HK fine | stage agree (≥0.9) | CHN2020→JPN y* [1985,1995] | Yoshida hits@5 1990/2015/2050 (reported) | G2 |
|---|---|---|---|---|---|---|---|---|---|
| blend | 0.858 ✓ | 0.879 | 0.817 | 0.868 ✓ | 0.709 | 0.927 ✓ | 1994 ✓ | 1/1/0 ✗ | ✓ |
| l2 | 0.852 ✓ | 0.888 | 0.825 | 0.872 ✓ | 0.734 | 0.922 ✓ | 1998 ✗ | 1/2/1 ✗ | ✗ |
| w1 | 0.860 ✓ | 0.885 | 0.805 | 0.8505 ✓ | 0.679 | 0.953 ✓ | 1993 ✓ | 2/2/0 ✗ | ✓ |
| l2s | 0.850 ✓ | 0.895 | 0.819 | 0.880 ✓ | 0.728 | 0.932 ✓ | 1994 ✓ | 1/2/1 ✗ | ✓ |
| hel | 0.853 ✓ | 0.878 | 0.816 | 0.853 ✓ | 0.708 | 0.914 ✓ | 1994 ✓ | 1/1/1 ✗ | ✓ |
| feat | 0.799 ✓ | 0.864 | 0.809 | 0.881 ✓ | 0.707 | 0.897 ✗ | 1981 ✗ | 1/1/1 ✗ | ✗ |
| w1sex | 0.840 ✓ | 0.849 | 0.794 | 0.8495 ✗ | 0.680 | 0.935 ✓ | 1994 ✓ | 1/0/0 ✗ | ✗ |
| w1bal | 0.865 ✓ | 0.874 | 0.811 | 0.855 ✓ | 0.682 | 0.942 ✓ | 1993 ✓ | 1/1/0 ✗ | ✓ |
| clr | 0.754 ✓ | 0.735 | 0.708 | 0.787 ✗ | 0.619 | 0.857 ✗ | 1994 ✓ | 1/2/0 ✗ | ✗ |
| trend | 0.615 ✗ | 0.639 | 0.626 | 0.680 ✗ | 0.585 | 0.667 ✗ | 1980 ✗ | 0/0/0 ✗ | ✗ |
| path | 0.854 ✓ | 0.865 | 0.816 | 0.853 ✓ | 0.692 | 0.917 ✓ | 1994 ✓ | 1/0/0 ✗ | ✓ |
| visual:dinov2-base | 0.734 ✓ | 0.796 | 0.772 | 0.862 ✓ | 0.690 | 0.828 ✗ | 2012 ✗ | 1/0/0 ✗ | ✗ |
| visual:siglip2-base-naflex | 0.715 ✓ | 0.772 | 0.732 | 0.847 ✗ | 0.677 | 0.832 ✗ | 1990 ✓ | 0/3/0 ✗ | ✗ |

Gated cells carry their own tick and show 4 decimals when within 0.001 of the gate. Normalised P@10 is not tabulated for the Korenjak-Černe clusters: the smallest cluster has 30 members, so min(10, |G|−1) = 10 and P@10 coincides with class agreement (protocol.md §2).

Hahn-Klimroth classes on the 2024 country set (≥ 100k): fine {'bell': 6, 'diamond': 38, 'inverted_plunger': 1, 'inverted_pyramid': 1, 'lower_diamond': 20, 'other': 3, 'pyramid': 97, 'upper_diamond': 34}; families (gate level) {'bell': 6, 'diamond': 92, 'inverted_plunger': 1, 'inverted_pyramid': 1, 'other': 3, 'pyramid': 97}.

G2(e) Yoshida — DEMOTED TO REPORTED (protocol.md §4 amendment, recorded before this run's verdicts but after a smoke run: the paper's own metric, `clr` on total shares, reproduces India's 1990 distance (0.59 vs the paper's 0.579) yet fails the pre-registered top-5 targets on WPP2024 rows — Bolivia and Puerto Rico were revised between WPP2015 and WPP2024). Top-5 (World Y vs countries 2015) and rank of every named country: 

- `blend`: 1990: BOL,EGY,PHL,PRY,LAO — ranks {'IND': '>10', 'EGY': 2, 'DZA': '>10', 'BGD': '>10'} · 2015: LBN,PAN,PER,IDN,TUR — ranks {'COL': '>10', 'PER': 3, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': 9} · 2050: AUS,ISL,USA,NZL,NOR — ranks {'URY': 7, 'PRI': '>10'}
- `l2`: 1990: BOL,EGY,PHL,HTI,NIC — ranks {'IND': '>10', 'EGY': 2, 'DZA': '>10', 'BGD': '>10'} · 2015: PAN,LBN,PER,IDN,ARG — ranks {'COL': '>10', 'PER': 3, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': 5} · 2050: ISL,AUS,URY,NOR,USA — ranks {'URY': 3, 'PRI': '>10'}
- `w1`: 1990: BOL,KHM,PRY,BGD,EGY — ranks {'IND': '>10', 'EGY': 5, 'DZA': '>10', 'BGD': 4} · 2015: LBN,KAZ,COL,TUN,PER — ranks {'COL': 3, 'PER': 5, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': '>10'} · 2050: NZL,AUS,GEO,USA,ISL — ranks {'URY': 10, 'PRI': '>10'}
- `l2s`: 1990: BOL,EGY,PHL,KHM,DJI — ranks {'IND': '>10', 'EGY': 2, 'DZA': '>10', 'BGD': '>10'} · 2015: LBN,PAN,PER,IDN,ARG — ranks {'COL': '>10', 'PER': 3, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': 5} · 2050: ISL,AUS,NZL,USA,URY — ranks {'URY': 5, 'PRI': '>10'}
- `hel`: 1990: BOL,PRY,EGY,NIC,ECU — ranks {'IND': '>10', 'EGY': 3, 'DZA': '>10', 'BGD': 10} · 2015: PAN,LBN,PER,TUR,NCL — ranks {'COL': 6, 'PER': 3, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': '>10'} · 2050: AUS,NOR,ISL,GBR,URY — ranks {'URY': 5, 'PRI': '>10'}
- `feat`: 1990: BOL,EGY,KHM,PRY,NIC — ranks {'IND': '>10', 'EGY': 2, 'DZA': '>10', 'BGD': '>10'} · 2015: PAN,GUM,LBN,PER,IDN — ranks {'COL': '>10', 'PER': 4, 'ECU': '>10', 'LKA': 6, 'MEX': '>10', 'BRA': '>10', 'ARG': 10} · 2050: FRA,NOR,URY,NZL,BEL — ranks {'URY': 3, 'PRI': '>10'}
- `w1sex`: 1990: BOL,PRY,EGY,PHL,BLZ — ranks {'IND': '>10', 'EGY': 3, 'DZA': '>10', 'BGD': '>10'} · 2015: TUR,LBN,PAN,PYF,IDN — ranks {'COL': 9, 'PER': 6, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': '>10'} · 2050: USA,AUS,ISL,NZL,NOR — ranks {'URY': 10, 'PRI': '>10'}
- `w1bal`: 1990: BOL,PRY,EGY,PHL,KHM — ranks {'IND': '>10', 'EGY': 3, 'DZA': '>10', 'BGD': 9} · 2015: LBN,TUR,COL,TUN,PAN — ranks {'COL': 3, 'PER': 8, 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': '>10'} · 2050: USA,AUS,ISL,NZL,NOR — ranks {'URY': 10, 'PRI': '>10'}
- `clr`: 1990: BOL,PRY,ECU,SUR,IND — ranks {'IND': 5, 'EGY': '>10', 'DZA': 8, 'BGD': '>10'} · 2015: PAN,CRI,TUR,COL,BRA — ranks {'COL': 4, 'PER': '>10', 'ECU': 8, 'LKA': '>10', 'MEX': '>10', 'BRA': 5, 'ARG': '>10'} · 2050: GBR,SWE,CAN,FRA,USA — ranks {'URY': '>10', 'PRI': '>10'}
- `trend`: 1990: ARG,PAK,HTI,BOL,BEN — ranks {'IND': '>10', 'EGY': '>10', 'DZA': '>10', 'BGD': '>10'} · 2015: PAN,VEN,LBN,DOM,EGY — ranks {'COL': '>10', 'PER': '>10', 'ECU': '>10', 'LKA': '>10', 'MEX': 10, 'BRA': '>10', 'ARG': '>10'} · 2050: ISR,SEN,ARG,NGA,TZA — ranks {'URY': '>10', 'PRI': '>10'}
- `path`: 1990: BOL,EGY,PRY,ECU,PHL — ranks {'IND': '>10', 'EGY': 2, 'DZA': '>10', 'BGD': 6} · 2015: TUR,LBN,PAN,PYF,IDN — ranks {'COL': 8, 'PER': '>10', 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': '>10'} · 2050: AUS,ISL,USA,NOR,NZL — ranks {'URY': 7, 'PRI': '>10'}
- `visual:dinov2-base`: 1990: EGY,TON,SWZ,HTI,HND — ranks {'IND': '>10', 'EGY': 1, 'DZA': '>10', 'BGD': '>10'} · 2015: PAN,IDN,MAR,NIC,PRY — ranks {'COL': '>10', 'PER': '>10', 'ECU': '>10', 'LKA': '>10', 'MEX': '>10', 'BRA': '>10', 'ARG': '>10'} · 2050: SWE,ISL,IRL,LKA,REU — ranks {'URY': 9, 'PRI': '>10'}
- `visual:siglip2-base-naflex`: 1990: HTI,BOL,PHL,JOR,NIC — ranks {'IND': '>10', 'EGY': '>10', 'DZA': '>10', 'BGD': '>10'} · 2015: PER,MEX,ECU,BGD,PAN — ranks {'COL': '>10', 'PER': 1, 'ECU': 3, 'LKA': '>10', 'MEX': 2, 'BRA': '>10', 'ARG': '>10'} · 2050: AUS,SWE,ISL,GBR,NZL — ranks {'URY': 9, 'PRI': '>10'}

## G4 outliers (isolation, 2024; gate = {QAT, ARE, BHR, KWT} ⊆ top-10)

| metric | top-10 most isolated | gate | floor off: MCO/VAT enter | top-10 (floor off) |
|---|---|---|---|---|
| blend | QAT, ARE, KWT, SAU, HKG, OMN, SYC, MAC, SGP, BHR | ✓ | MCO, VAT | QAT, VAT, ARE, KWT, MCO, SAU, HKG, OMN, MNP, MAC |
| l2 | QAT, ARE, KWT, OMN, SAU, BHR, MDV, SGP, MAC, HKG | ✓ | MCO, VAT | VAT, QAT, ARE, KWT, MCO, OMN, SAU, BHR, MDV, SGP |
| w1 | JPN, QAT, OMN, KWT, ARE, SAU, HKG, MDV, BHR, GUM | ✓ | MCO, VAT | VAT, MCO, QAT, JPN, OMN, KWT, ARE, SAU, MDV, BHR |
| l2s | QAT, KWT, ARE, OMN, SAU, HKG, SGP, BHR, MDV, MAC | ✓ | MCO, VAT | VAT, QAT, MCO, KWT, ARE, OMN, SAU, HKG, SGP, MNP |
| hel | QAT, KWT, ARE, OMN, HKG, SGP, MAC, SAU, MDV, BHR | ✓ | MCO, VAT | VAT, MCO, QAT, KWT, ARE, MNP, NIU, OMN, FLK, HKG |
| feat | QAT, JPN, ARE, OMN, UZB, SGP, MYT, KWT, SAU, MDV | ✗ | MCO, VAT | VAT, MCO, QAT, JPN, ARE, OMN, UZB, MYT, SGP, KWT |
| w1sex | QAT, ARE, SAU, SYC, HKG, KWT, OMN, CAF, ESH, MLT | ✗ | MCO, VAT | QAT, VAT, ARE, MCO, SAU, HKG, KWT, OMN, SYC, PLW |
| w1bal | QAT, OMN, KWT, HKG, MAC, SAU, ARE, SYC, MDV, JPN | ✗ | MCO, VAT | VAT, QAT, MCO, OMN, NIU, KWT, HKG, SHN, SAU, ARE |
| clr | ABW, QAT, ARE, CAF, KWT, BHR, ESH, KEN, TON, HKG | ✓ | MCO, VAT | VAT, NIU, NRU, TKL, MCO, TUV, SHN, SPM, MSR, FLK |
| trend | MDV, QAT, SYR, OMN, MAC, CHN, CUW, SSD, BHR, MLT | ✗ | VAT | VAT, BLM, MDV, QAT, NIU, SYR, TKL, OMN, FLK, MAC |
| path | QAT, KWT, ARE, OMN, MDV, SAU, BHR, HKG, SGP, SYC | ✓ | MCO, VAT | QAT, VAT, KWT, ARE, MCO, OMN, MDV, SAU, BHR, HKG |
| visual:dinov2-base | SGP, SYC, IRN, CYP, SLV, MNG, VNM, MDA, VCT, CPV | ✗ | MCO, VAT | VAT, SGP, MCO, NIU, GRL, MHL, SYC, IRN, FLK, CYM |
| visual:siglip2-base-naflex | SLV, URY, MYS, BLZ, SAU, BRN, OMN, MLT, SGP, LKA | ✗ | VAT | SLV, URY, VAT, MYS, BLZ, SAU, OMN, MLT, BRN, CYM |

## Opposites test (20 random 2024 anchors, β = 2 as pre-registered, k = 5)

| metric | mean/min HK classes (fine) | mean/min UN regions | anchors with ≥3/≥3 | pass (means ≥ 3) | β=0 = farthest-5 | dedupe (any-year) |
|---|---|---|---|---|---|---|
| blend | 2.20/2 | 2.00/1 | 0.00 | ✗ | ✓ | ✓ |
| l2 | 2.45/2 | 2.00/2 | 0.00 | ✗ | ✓ | ✓ |
| w1 | 1.85/1 | 1.80/1 | 0.40 | ✗ | ✓ | ✓ |
| l2s | 2.70/2 | 2.20/2 | 0.15 | ✗ | ✓ | ✓ |
| hel | 2.80/2 | 2.10/2 | 0.05 | ✗ | ✓ | ✓ |
| feat | 2.85/2 | 1.75/1 | 0.00 | ✗ | ✓ | ✓ |
| w1sex | 2.15/2 | 2.00/2 | 0.00 | ✗ | ✓ | ✓ |
| w1bal | 2.50/1 | 2.10/2 | 0.10 | ✗ | ✓ | ✓ |
| clr | 2.55/2 | 2.80/2 | 0.30 | ✗ | ✓ | ✓ |
| trend | 3.10/3 | 1.70/1 | 0.05 | ✗ | ✓ | ✓ |
| path | 2.40/2 | 1.70/1 | 0.00 | ✗ | ✓ | ✓ |
| visual:dinov2-base | 1.90/1 | 3.00/2 | 0.30 | ✗ | ✓ | ✓ |
| visual:siglip2-base-naflex | 2.35/1 | 2.85/2 | 0.40 | ✗ | ✓ | ✓ |

### MMR β sweep (`blend`, k = 5, all 200 country anchors ≥ 100k at 2024; shipped presets: strict β=0, balanced β=0.5, spread β=2)

| β | mean top-5 Jaccard vs strict (β=0) | mean raw rank of picks | mean distinct UN regions | anchors identical to β=2 |
|---|---|---|---|---|
| 0 | 1.00 | 3.0 | 1.86 | 0.00 |
| 0.25 | 0.75 | 4.9 | 1.92 | 0.00 |
| 0.5 | 0.62 | 5.8 | 1.83 | 0.01 |
| 1 | 0.49 | 9.6 | 1.70 | 0.12 |
| 2 | 0.37 | 14.2 | 2.00 | 1.00 |
| 4 | 0.35 | 15.7 | 2.02 | 0.79 |
| 8 | 0.33 | 16.5 | 2.14 | 0.67 |

The coverage target (≥ 3 Hahn-Klimroth classes AND ≥ 3 UN regions among 5 opposites) fails for every metric and is **structural, not a bug**: the MMR pool is the farthest quartile, which for any old anchor is entirely young 'pyramid'-class Sahel/Gulf countries, so diversity over SHAPE distance cannot buy class or region variety at any β (mean regions never exceeds ~2.1). The diversity term also saturates early (β = 2 and β = 4 pick the same five for most anchors), so the presets were re-calibrated from the sweep — balanced β = 0.5 keeps ≈ ⅔ of the strict list, spread β = 2 ≈ ⅓ — and product copy must not promise regional variety; a region/class cap is a v1.1 option (PLAN §5).

### Documented asymmetry: W1 share of `blend` by era (median over same-year pairs ≥ 100k)

| sex | observed ≤ 2023 | nowcast 2024–2026 | projected > 2026 | pooled (σ fit) |
|---|---|---|---|---|
| two-sex | 0.469 | 0.502 | 0.534 | 0.503 |
| total only | 0.450 | 0.510 | 0.562 | 0.503 |

σ is the median over pairs pooled uniformly over 1950–2100 (CONTRACT §4), so the two halves of `blend` are equal on the pooled sample only; σ_w1 rises into the projections, which tilts observed-year pairs towards the L2 term. The definition stands (it lands balanced exactly at the 2024–2026 default years); the tilt is recorded here and in the build report (`blend_w1_share`) rather than hidden.

## Method agreement (mean top-10 Jaccard, 200 random same-year queries 1960–2023)

| | blend | l2 | w1 | l2s | hel | feat | w1sex | w1bal | clr | trend | path | visual:dinov2-base | visual:siglip2-base-naflex |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| blend | 1.00 | 0.60 | 0.41 | 0.63 | 0.56 | 0.39 | 0.58 | 0.56 | 0.21 | 0.17 | 0.65 | 0.21 | 0.19 |
| l2 | 0.60 | 1.00 | 0.39 | 0.72 | 0.64 | 0.45 | 0.35 | 0.43 | 0.21 | 0.21 | 0.50 | 0.23 | 0.20 |
| w1 | 0.41 | 0.39 | 1.00 | 0.47 | 0.43 | 0.33 | 0.36 | 0.56 | 0.18 | 0.11 | 0.38 | 0.19 | 0.18 |
| l2s | 0.63 | 0.72 | 0.47 | 1.00 | 0.61 | 0.45 | 0.40 | 0.52 | 0.20 | 0.16 | 0.52 | 0.22 | 0.19 |
| hel | 0.56 | 0.64 | 0.43 | 0.61 | 1.00 | 0.42 | 0.36 | 0.50 | 0.26 | 0.21 | 0.54 | 0.22 | 0.20 |
| feat | 0.39 | 0.45 | 0.33 | 0.45 | 0.42 | 1.00 | 0.28 | 0.34 | 0.19 | 0.15 | 0.33 | 0.21 | 0.17 |
| w1sex | 0.58 | 0.35 | 0.36 | 0.40 | 0.36 | 0.28 | 1.00 | 0.54 | 0.18 | 0.10 | 0.52 | 0.17 | 0.17 |
| w1bal | 0.56 | 0.43 | 0.56 | 0.52 | 0.50 | 0.34 | 0.54 | 1.00 | 0.21 | 0.13 | 0.53 | 0.19 | 0.18 |
| clr | 0.21 | 0.21 | 0.18 | 0.20 | 0.26 | 0.19 | 0.18 | 0.21 | 1.00 | 0.12 | 0.21 | 0.14 | 0.15 |
| trend | 0.17 | 0.21 | 0.11 | 0.16 | 0.21 | 0.15 | 0.10 | 0.13 | 0.12 | 1.00 | 0.18 | 0.11 | 0.12 |
| path | 0.65 | 0.50 | 0.38 | 0.52 | 0.54 | 0.33 | 0.52 | 0.53 | 0.21 | 0.18 | 1.00 | 0.19 | 0.18 |
| visual:dinov2-base | 0.21 | 0.23 | 0.19 | 0.22 | 0.22 | 0.21 | 0.17 | 0.19 | 0.14 | 0.11 | 0.19 | 1.00 | 0.19 |
| visual:siglip2-base-naflex | 0.19 | 0.20 | 0.18 | 0.19 | 0.20 | 0.17 | 0.17 | 0.18 | 0.15 | 0.12 | 0.18 | 0.19 | 1.00 |

## Regression (reported, never gates): canonical groups at 2024 — normalised P@5 / MRR

| metric | aged_europe | sahel | gulf_migrant | anglo_nordic | korea_taiwan | china_thailand_cuba |
|---|---|---|---|---|---|---|
| blend | 0.50 / 0.87 | 1.00 / 1.00 | 0.80 / 0.67 | 0.63 / 0.71 | – / 1.00 | – / 0.26 |
| l2 | 0.60 / 0.88 | 1.00 / 1.00 | 0.70 / 0.67 | 0.73 / 0.89 | – / 1.00 | – / 0.49 |
| w1 | 0.50 / 0.78 | 1.00 / 1.00 | 0.65 / 0.75 | 0.37 / 0.78 | – / 1.00 | – / 0.67 |
| l2s | 0.57 / 0.89 | 1.00 / 1.00 | 0.70 / 0.67 | 0.67 / 0.83 | – / 1.00 | – / 0.83 |
| hel | 0.63 / 0.88 | 1.00 / 1.00 | 0.75 / 0.77 | 0.73 / 0.92 | – / 1.00 | – / 0.56 |
| feat | 0.47 / 0.89 | 0.92 / 0.88 | 0.80 / 0.80 | 0.70 / 0.92 | – / 0.67 | – / 0.83 |
| w1sex | 0.63 / 0.81 | 1.00 / 1.00 | 0.80 / 0.67 | 0.47 / 0.79 | – / 1.00 | – / 0.12 |
| w1bal | 0.70 / 0.92 | 1.00 / 1.00 | 0.75 / 0.80 | 0.47 / 0.71 | – / 1.00 | – / 0.29 |
| clr | 0.60 / 0.81 | 0.25 / 0.50 | 0.60 / 0.67 | 0.60 / 0.89 | – / 0.00 | – / 0.67 |
| trend | 0.47 / 0.72 | 0.25 / 0.45 | 0.20 / 0.40 | 0.60 / 0.92 | – / 0.12 | – / 0.21 |
| path | 0.53 / 0.92 | 1.00 / 1.00 | 0.65 / 0.80 | 0.57 / 0.79 | – / 1.00 | – / 0.20 |
| visual:dinov2-base | 0.27 / 0.61 | 0.83 / 0.88 | 0.95 / 0.87 | 0.40 / 0.77 | – / 0.75 | – / 0.05 |
| visual:siglip2-base-naflex | 0.50 / 0.78 | 0.33 / 0.42 | 0.65 / 0.87 | 0.17 / 0.27 | – / 0.67 | – / 0.38 |

## Regression: time-shift windows (best year, era all)

| metric | KOR 2050 → JPN [2040, 2060] | KOR 2024 → JPN [2000, 2010] | IND 2024 → CHN [1995, 2005] | CHN 2020 → JPN [1985, 1995] (gate) |
|---|---|---|---|---|
| blend | 2050 ✓ | 2005 ✓ | 1999 ✓ | 1994 ✓ |
| l2 | 2050 ✓ | 2003 ✓ | 1999 ✓ | 1998 ✗ |
| w1 | 2051 ✓ | 2006 ✓ | 2000 ✓ | 1993 ✓ |
| l2s | 2047 ✓ | 2005 ✓ | 1999 ✓ | 1994 ✓ |
| hel | 2050 ✓ | 2004 ✓ | 1999 ✓ | 1994 ✓ |
| feat | 2051 ✓ | 1996 ✗ | 1996 ✓ | 1981 ✗ |
| w1sex | 2053 ✓ | 2007 ✓ | 2000 ✓ | 1994 ✓ |
| w1bal | 2051 ✓ | 2010 ✓ | 2000 ✓ | 1993 ✓ |
| clr | 2039 ✗ | 2000 ✓ | 2013 ✗ | 1994 ✓ |
| trend | 2091 ✗ | 1999 ✗ | 1974 ✗ | 1980 ✗ |
| path | 2049 ✓ | 2004 ✓ | 2000 ✓ | 1994 ✓ |
| visual:dinov2-base | 2026 ✗ | 2008 ✓ | 2004 ✓ | 2012 ✗ |
| visual:siglip2-base-naflex | 2038 ✗ | 2036 ✗ | 2004 ✓ | 1990 ✓ |

## Verdicts (protocol.md §4; INFORMATIONAL — both blend and visual ship)

| metric | verdict | G1 | G2 | G4 | note |
|---|---|---|---|---|---|
| blend | **default** | ✓ | ✓ | ✓ |  |
| l2 | **advanced** | ✓ | ✗ | ✓ |  |
| w1 | **rejected** | ✗ | ✓ | ✓ |  |
| l2s | **menu** | ✓ | ✓ | ✓ | provisional until M4 triplets |
| hel | **menu** | ✓ | ✓ | ✓ | provisional until M4 triplets |
| feat | **lab** | ✗ | ✗ | ✗ |  |
| w1sex | **lab** | ✓ | ✗ | ✗ |  |
| w1bal | **lab** | ✓ | ✓ | ✗ |  |
| clr | **advanced** | ✓ | ✗ | ✓ |  |
| trend | **menu** | ✓ | ✗ | ✗ | trend-mode toggle (G1 only) |
| path | **menu** | ✓ | ✓ | ✓ | trend-mode toggle (G1 only) |
| visual:dinov2-base | **rejected** | ✗ | ✗ | ✗ |  |
| visual:siglip2-base-naflex | **rejected** | ✗ | ✗ | ✗ |  |

### Image-space predictions (evals/image_embeddings.md §2)

- `visual:dinov2-base`: C1 = 0.513 (< 0.95 as predicted); HK agreement = 0.862 (≥ 0.6 as predicted); expected verdict `lab` → observed `rejected` (NOT met — worse than predicted (C1 < 0.8)).
- `visual:siglip2-base-naflex`: C1 = 0.550 (< 0.95 as predicted); HK agreement = 0.847 (≥ 0.6 as predicted); expected verdict `lab` → observed `rejected` (NOT met — worse than predicted (C1 < 0.8)).
- Exposed as "Visual" (better observed-span G1 C1): `visual:siglip2-base-naflex` (C1 obs 0.550); URL-only: `visual:dinov2-base`. Recorded as `exposed_visual` in verdicts.json and meta.json.

## Findings recorded with the hand-edited groups

- JPN's nearest 2024 neighbours are Southern European, not KOR/TWN, so no East-Asia group exists; VNM sits between THA and IDN and is in no group. Both are statements about `blend`, not label choices.
- Korenjak-Černe labels: IDB-2008 vintage on 17 five-year bins (80+ open) vs our WPP2024 21-bin rows; Netherlands Antilles unmapped; Gaza Strip + West Bank merged into PSE.
