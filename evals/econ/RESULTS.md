# Economic-lens backtest — RESULTS

**PREREG commit:** `14f8c3c6e86a0a4e4242996dd3a733a0f8426618` (`evals/econ/PREREG.md`, frozen; this file cites it and `decision.json` carries it as `prereg_commit`).
**Generated:** 2026-09-05T02:04:22+00:00 · code revision `93a7c2b` · seed 20260904 · B = 5000.

Everything below is past tense and numeric. Every market number stands next to VT over the same window (VT proxy before 2008-06-24, PREREG §3.5); N_eff (distinct country × non-overlapping h-block pairs) is printed beside every statistic; status counts stand beside every return statistic. Nothing here is a forecast.

## 1. Data vintages and fetch dates

| source | family | vintage | licence | shipped | fetched | sha256 |
|---|---|---|---|---|---|---|
| curated | curated | — | MIT | yes | — | — |
| maddison-2023 | maddison | 2023 | CC BY 4.0 | yes | 2026-09-04 | ecc5916ca127 |
| oghist | oghist | FY2026 | CC BY 4.0 | yes | 2026-09-04 | 17eb9e67b2ea |
| pwt-11.0 | pwt | 11.0 | CC BY 4.0 | yes | 2026-09-04 | 7b337e94f39d |
| wdi | wdi | — | CC BY 4.0 | yes | 2026-09-04 | 1497f5a841bc |
| weo-2025-04 | weo | 2025-04 | IMF terms of use (no redistribution) | no | 2026-09-04 | 4a5bb1b5ab9a |
| wpp2024 | wpp | 2024-07-11 | CC BY 3.0 IGO | yes | 2026-09-04 | 9a33c151a9a8 |
| wpp2024-togo-update | wpp | 2026-01-19 | CC BY 3.0 IGO | yes | 2026-09-04 | eb7846bf5d93 |

Growth series: PWT 11.0 `rgdpna/pop` (primary), Maddison 2023 `gdppc` (fallback, never mixed inside a window); level: PWT `rgdpe/pop` else Maddison. Population floor 1000 k (WPP 2024). T = 2015 growth windows are partial (PWT h = 8 → 2023, Maddison h = 7 → 2022) and flagged.

| candidate set C(T) | 1990 | 1995 | 2000 | 2005 | 2010 | 2015 |
|---|---|---|---|---|---|---|
| 10, growth | 148 | 150 | 151 | 152 | 156 | 157 |
| 10, returns | — | — | 151 | 152 | 156 | 157 |
| 20, growth | 148 | 150 | 151 | — | — | — |

## 2. ETF universe and the survivorship guard

55 instruments, hand-curated before any fetch (`etf_universe.yaml`, as of 2026-09-04); no ticker was added or removed.

| ticker | iso3 | role | inception | verified | status | delisted | Δ days (Yahoo − issuer) | yahoo symbol |
|---|---|---|---|---|---|---|---|---|
| EWA | AUS | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWC | CAN | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWD | SWE | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWG | DEU | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWH | HKG | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWI | ITA | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWJ | JPN | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWK | BEL | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWL | CHE | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWM | MYS | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWN | NLD | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWO | AUT | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWP | ESP | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWQ | FRA | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWS | SGP | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWU | GBR | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWW | MEX | single_country | 1996-03-12 | yes | live | — | 0 | — |
| EWY | KOR | single_country | 2000-05-09 | yes | live | — | 0 | — |
| EWT | TWN | single_country | 2000-06-20 | yes | live | — | 0 | — |
| EWZ | BRA | single_country | 2000-07-10 | yes | live | — | 0 | — |
| EZA | ZAF | single_country | 2003-02-03 | yes | live | — | 0 | — |
| FXI | CHN | single_country | 2004-10-05 | yes | live | — | 0 | — |
| ECH | CHL | single_country | 2007-11-12 | yes | live | — | 0 | — |
| THD | THA | single_country | 2008-03-26 | yes | live | — | 6 | — |
| TUR | TUR | single_country | 2008-03-26 | yes | live | — | 0 | — |
| EIS | ISR | single_country | 2008-03-26 | yes | live | — | 0 | — |
| EPU | PER | single_country | 2009-06-19 | yes | live | — | 0 | — |
| EIDO | IDN | single_country | 2010-05-05 | yes | live | — | 0 | — |
| EPOL | POL | single_country | 2010-05-25 | yes | live | — | 0 | — |
| EIRL | IRL | single_country | 2010-05-05 | yes | live | — | 0 | — |
| EPHE | PHL | single_country | 2010-09-28 | yes | live | — | 0 | — |
| ENZL | NZL | single_country | 2010-09-01 | yes | live | — | 0 | — |
| MCHI | CHN | single_country | 2011-03-29 | yes | live | — | 0 | — |
| INDA | IND | single_country | 2012-02-02 | yes | live | — | 0 | — |
| UAE | ARE | single_country | 2014-04-29 | yes | live | — | 2 | — |
| QAT | QAT | single_country | 2014-04-29 | yes | live | — | 2 | — |
| KSA | SAU | single_country | 2015-09-16 | yes | live | — | 0 | — |
| ERUS | RUS | single_country | 2010-11-09 | yes | liquidating | 2022-08-17 | — | — |
| FM | — | basket | 2012-09-12 | yes | liquidated | 2025-01-06 | — | — |
| GXG | COL | single_country | 2009-02-05 | yes | live | — | 4 | COLO |
| VNM | VNM | single_country | 2009-08-11 | no | live | — | 0 | — |
| EGPT | EGY | single_country | 2010-02-16 | no | liquidated | 2024-03-21 | — | — |
| RSX | RUS | single_country | 2007-04-24 | no | liquidating | 2023-01-12 | — | — |
| NGE | NGA | single_country | 2013-04-02 | yes | liquidated | 2023-07-28 | — | — |
| PAK | PAK | single_country | 2015-04-22 | yes | liquidated | 2024-02-16 | — | — |
| ARGT | ARG | single_country | 2011-03-02 | yes | live | — | 0 | — |
| GREK | GRC | single_country | 2011-12-07 | yes | live | — | 0 | — |
| NORW | NOR | single_country | 2010-11-09 | yes | live | — | -442 | — |
| EPI | IND | single_country | 2008-02-22 | no | live | — | 0 | — |
| SPY | USA | benchmark | 1993-01-22 | yes | live | — | 0 | — |
| EFA | DM_EX_US | benchmark | 2001-08-14 | yes | live | — | 0 | — |
| EEM | EM | benchmark | 2003-04-07 | yes | live | — | 0 | — |
| VWO | EM | benchmark | 2005-03-04 | yes | live | — | 0 | — |
| ACWI | WORLD | benchmark | 2008-03-26 | yes | live | — | 0 | — |
| VT | WORLD | benchmark | 2008-06-24 | yes | live | — | 0 | — |

Discrepancies > 45 days between the issuer inception and Yahoo's first bar: NORW (-442 d — DISCREPANCY > 45 days, in the unexpected direction: Yahoo carries daily bars for NORW from 2009-08-24 with real-looking prices and volume (309 rows before the issuer inception), while Global X's fund page says 11/09/10 and the Global X 485BPOS filed 2025 says "since inception on 11/09/10". The plan's "NORW 2009-09" was taken from this Yahoo series. Most likely a Yahoo symbol mix-up (Global X's FTSE Nordic Region ETF launched 2009-08). The fetch must DROP every bar before 2010-11-09 and RESULTS must list this under discrepancies; guard assertion 2 passes trivially and is not the check that catches it.)

### Guard report (per ticker)

| ticker | result | bars | first bar | last bar | assertions noted | route | deviation |
|---|---|---|---|---|---|---|---|
| ACWI | passed | 4640 | 2008-03-28 | 2026-09-04 | — | yahoo | — |
| ARGT | passed | 3901 | 2011-03-03 | 2026-09-04 | — | yahoo | — |
| ECH | passed | 4727 | 2007-11-20 | 2026-09-04 | — | yahoo | — |
| EEM | passed | 5887 | 2003-04-14 | 2026-09-04 | — | yahoo | — |
| EFA | passed | 6293 | 2001-08-27 | 2026-09-04 | — | yahoo | — |
| EGPT | passed | 3549 | 2010-02-16 | 2024-03-21 | A4_delisted_not_refused | manual | Yahoo served 3558 daily bars (2010-02-16 → 2024-04-04) for delisted EGPT (yaml last trading day 2024-03-21); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. |
| EIDO | passed | 4108 | 2010-05-07 | 2026-09-04 | — | yahoo | — |
| EIRL | passed | 4106 | 2010-05-11 | 2026-09-04 | — | yahoo | — |
| EIS | passed | 4640 | 2008-03-28 | 2026-09-04 | — | yahoo | — |
| ENZL | passed | 4026 | 2010-09-02 | 2026-09-04 | — | yahoo | — |
| EPHE | passed | 4008 | 2010-09-29 | 2026-09-04 | — | yahoo | — |
| EPI | passed | 4662 | 2008-02-26 | 2026-09-04 | — | yahoo | — |
| EPOL | passed | 4095 | 2010-05-26 | 2026-09-04 | — | yahoo | — |
| EPU | passed | 4329 | 2009-06-22 | 2026-09-04 | — | yahoo | — |
| ERUS | passed | 0 | None | None | — | manual | — |
| EWA | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWC | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWD | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWG | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWH | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWI | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWJ | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWK | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWL | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWM | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWN | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWO | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWP | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWQ | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWS | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWT | passed | 6589 | 2000-06-23 | 2026-09-04 | — | yahoo | — |
| EWU | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWW | passed | 7667 | 1996-03-18 | 2026-09-04 | — | yahoo | — |
| EWY | passed | 6618 | 2000-05-12 | 2026-09-04 | — | yahoo | — |
| EWZ | passed | 6575 | 2000-07-14 | 2026-09-04 | — | yahoo | — |
| EZA | passed | 5932 | 2003-02-07 | 2026-09-04 | — | yahoo | — |
| FM | passed | 3098 | 2012-09-12 | 2025-01-06 | A4_delisted_not_refused | manual | Yahoo served 3100 daily bars (2012-09-12 → 2025-01-08) for delisted FM (yaml last trading day 2025-01-06); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. |
| FXI | passed | 5512 | 2004-10-08 | 2026-09-04 | — | yahoo | — |
| GREK | passed | 3706 | 2011-12-08 | 2026-09-04 | — | yahoo | — |
| GXG | passed | 4421 | 2009-02-09 | 2026-09-04 | — | yahoo | — |
| INDA | passed | 3668 | 2012-02-03 | 2026-09-04 | — | yahoo | — |
| KSA | passed | 2758 | 2015-09-17 | 2026-09-04 | — | yahoo | — |
| MCHI | passed | 3881 | 2011-03-31 | 2026-09-04 | — | yahoo | — |
| NGE | passed | 2600 | 2013-04-02 | 2023-07-28 | A4_delisted_not_refused | manual | Yahoo served 2768 daily bars (2013-04-02 → 2024-03-28) for delisted NGE (yaml last trading day 2023-07-28); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. |
| NORW | passed | 3979 | 2010-11-09 | 2026-09-04 | — | yahoo | — |
| PAK | passed | 2222 | 2015-04-22 | 2024-02-16 | A4_delisted_not_refused | manual | Yahoo served 2233 daily bars (2015-04-22 → 2024-03-05) for delisted PAK (yaml last trading day 2024-02-16); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. |
| QAT | passed | 3106 | 2014-05-01 | 2026-09-04 | — | yahoo | — |
| RSX | passed | 0 | None | None | — | manual | — |
| SPY | passed | 8458 | 1993-01-29 | 2026-09-04 | — | yahoo | — |
| THD | passed | 4638 | 2008-04-01 | 2026-09-04 | — | yahoo | — |
| TUR | passed | 4640 | 2008-03-28 | 2026-09-04 | — | yahoo | — |
| UAE | passed | 3106 | 2014-05-01 | 2026-09-04 | — | yahoo | — |
| VNM | passed | 4291 | 2009-08-14 | 2026-09-04 | — | yahoo | — |
| VT | passed | 4577 | 2008-06-26 | 2026-09-04 | — | yahoo | — |
| VWO | passed | 5407 | 2005-03-10 | 2026-09-04 | — | yahoo | — |

Guard run 2026-09-05T02:03:47+00:00: 55 tickers, failures [], cross-check failures 0. 'Assertions noted' lists A4 signatures for delisted tickers routed to the manual NAV ladder; a ticker passes when every applicable assertion holds.

Cross-check vs issuer factsheets (`etf_crosscheck.yaml`, |Δ| ≤ 0.5 pp/yr):

| ticker | figure | as of | published %/yr | computed %/yr | Δ pp | passed |
|---|---|---|---|---|---|---|
| EWJ | 10y | 2026-06-30 | 9.54 | 9.48 | -0.057 | True |
| EWJ | since_inception | 2026-06-30 | 2.86 | 2.97 | +0.109 | True |
| EWY | 10y | 2026-06-30 | 16.72 | 16.70 | -0.022 | True |
| EWY | since_inception | 2026-06-30 | 10.57 | 10.71 | +0.143 | True |
| EWZ | 10y | 2026-06-30 | 6.71 | 6.70 | -0.009 | True |
| EWZ | since_inception | 2026-06-30 | 6.01 | 6.27 | +0.263 | True |
| FXI | 10y | 2026-06-30 | 1.75 | 1.62 | -0.125 | True |
| FXI | since_inception | 2026-06-30 | 4.94 | 4.91 | -0.030 | True |
| EEM | 10y | 2026-06-30 | 9.58 | 9.50 | -0.076 | True |
| EEM | since_inception | 2026-06-30 | 10.17 | 10.19 | +0.016 | True |
| SPY | 10y | 2026-06-30 | 15.35 | 15.39 | +0.043 | True |
| SPY | since_inception_alt | 2026-07-31 | 10.80 | 10.79 | -0.008 | True |
| VT | 10y | 2026-06-30 | 12.82 | 12.81 | -0.009 | True |
| VT | since_inception | 2026-06-30 | 8.87 | 8.89 | +0.017 | True |

## 3. Pre-registered predictions (P1–P8, PREREG §3.8) — observed vs stated

| id | pre-registered statement | observed | verdict |
|---|---|---|---|
| P1 | growth μ̂_eg ∈ [+0.3, +1.5] pp/yr, hit rate .55–.70, N1 p < .05 plausible, N2 p likely > .05, N_eff 20–30 | mu_eg_in_[0.3,1.5]: -0.190 → no<br>hit_rate_in_[.55,.70]: 0.483 → no<br>n_eff_in_[20,30]: 43.000 → no<br>p_N1_lt_05_plausible: 0.650 (observed false; soft clause, not in met)<br>p_N2_gt_05_likely: 0.983 (observed true; soft clause, not in met) | **not met** |
| P2 | |shape − 3-band| < 0.3 pp (the 42-vector adds little beyond u15/wa/o65) | value = 0.068<br>ci_headline = [-0.92, +1.18] | **met** |
| P3 | returns vs VT / VT-proxy: investable share < 40 % at T = 2000/05, 60–75 % at 2010/15; μ̂_er ∈ [−4, +3] pp/yr; CI width > 8 pp; zero not rejected; N_eff < 15; ≥ 1 liquidation in the 2015 cohort | investable_share_lt_40pct_at_2000_2005: 2000=0.000, 2005=0.000 → ok<br>investable_share_60_75pct_at_2010_2015: 2010=0.000, 2015=0.100 → no<br>mu_er_in_[-4,3]_vs_vt: -18.463 → no<br>ci_width_gt_8: 0.000 → no<br>zero_not_rejected: [-18.46, -18.46] → ok<br>n_eff_lt_15: 1.000 → ok<br>ge_1_liquidation_in_2015_cohort: 1.000 → ok | **not met** |
| P3b | the equal-weight investable basket itself does not beat VT over 2010–2025 (T = 2010 and T = 2015 windows) | ew_minus_vt_pp_per_yr = {'2010': -5.766732171060745, '2015': -3.8221484478921486} | **met** |
| P4 | h = 20 growth positive with CI including 0 | value = 0.334<br>ci_headline = [-0.53, +1.28] | **met** |
| P5 | Query A same signs as Query B, wider CIs | same_sign_growth: A=1.042, B=-0.190 → no<br>wider_ci_growth: A=[+0.26, +1.85], B=[-1.47, +1.20] → no<br>same_sign_returns: A=-3.965, B=-18.463 → ok | **not met** |
| P6 | WA, ΔWA > 0 (Driscoll–Kraay p < .05) | WA: beta=0.096, p_dk=0.008 → ok<br>dWA: beta=0.041, p_dk=0.193 → no | **not met** |
| P7 | D < 0 in-sample but ΔR²(S3 − S1) < .03 and OOS gain < .02 | D_lt_0_in_sample: beta=-0.002, p_dk=0.000 → ok (artifact — see §5 note: the in-sample coefficient on D is driven by prototype self-matching and is not evidence (88 rows are their own nearest prototype, 16.3 % share an outcome window with an own-country prototype window; without the latter β_D = +0.00101, DK p = 0.664))<br>delta_r2_s3_s1_lt_.03: 0.026 → ok<br>oos_gain_s3_over_s1_lt_.02: -0.002 → ok | **met** |
| P8 | OOS R²(S1 over S0) ∈ [.02, .10] | value = 0.049 | **met** |

## 4. Experiment 1 — lookalike-as-of-T

T grid [1990, 1995, 2000, 2005, 2010, 2015]; growth horizons {'10': [1990, 1995, 2000, 2005, 2010, 2015], '20': [1990, 1995, 2000]}; returns for T ∈ [2000, 2005, 2010, 2015] (h = 10). returns rows: entry = last NYSE trading day of T, exit = of T + 10; excess vs VT (VT proxy before 2008-06-24) is the headline; status counts are reported beside every return statistic. Rows for T = 1990 and 1995 have no return statistic: no US-listed single-country ETF existed at entry (first WEBS 1996-03).

### Prototype sets P(T) (Query B)

| T | |P(T)| | members (country year), highest growth first |
|---|---|---|
| 1990 | 82 | LBY 1959, LBY 1954, SAU 1964, JPN 1959, SGP 1964, MKD 1954, KOR 1968, ROU 1966, SRB 1954, TWN 1963, KOR 1980, TWN 1969, YEM 1969, CHN 1977, GRC 1962, LBY 1964, MWI 1964, JPN 1954, LBN 1976, SVN 1953, SAU 1958, IRN 1955, ROU 1960, KOR 1975, DEU 1950, SGP 1969, THA 1961, HRV 1954, IRQ 1951, ESP 1959, THA 1968, TWN 1974, JAM 1950, ROU 1971, BIH 1956, IRQ 1970, MKD 1962, BGR 1956, ESP 1953, ISR 1953, MYS 1970, PRT 1963, JPN 1964, TUN 1967, BRA 1966, HKG 1978, HKG 1971, BGR 1970, TUN 1962, SVN 1959, PRT 1958, GRC 1955, PRY 1971, PRI 1960, SVN 1968, PSE 1968, SGP 1958, SYR 1970, PAN 1960, NGA 1967, MYS 1964, SAU 1952, COG 1963, PRI 1955, THA 1980, HRV 1959, BGR 1950, DZA 1962, HKG 1960, SRB 1961, ITA 1960, COG 1972, DOM 1968, HRV 1968, SRB 1968, TGO 1959, YEM 1964, GRC 1967, AUT 1953, EGY 1975, RUS 1951, IDN 1971 |
| 1995 | 92 | LBY 1959, LBY 1954, SAU 1964, JPN 1959, SGP 1964, MKD 1954, KOR 1968, KOR 1981, ROU 1966, CHN 1983, SRB 1954, TWN 1963, TWN 1969, YEM 1969, CHN 1977, GRC 1962, LBY 1964, MWI 1964, JPN 1954, LBN 1976, SVN 1953, SAU 1958, IRN 1955, ROU 1960, BWA 1982, THA 1985, KOR 1975, DEU 1950, SGP 1969, THA 1961, HRV 1954, IRQ 1951, ESP 1959, TWN 1982, THA 1968, JAM 1950, ROU 1971, BIH 1956, IRQ 1970, MKD 1962, BGR 1956, ESP 1953, ISR 1953, MYS 1970, PRT 1963, JPN 1964, TUN 1967, BRA 1966, HKG 1978, HKG 1971, BGR 1970, TUN 1962, SVN 1959, PRT 1958, GRC 1955, PRY 1971, PRI 1960, SVN 1968, PSE 1968, SGP 1958, SYR 1970, PAN 1960, NGA 1967, MYS 1964, SAU 1952, CHL 1985, COG 1963, PRI 1955, MLI 1985, HRV 1959, BGR 1950, DZA 1962, KWT 1985, HKG 1960, SRB 1961, ITA 1960, COG 1972, DOM 1968, HRV 1968, SRB 1968, TGO 1959, YEM 1964, GRC 1967, AUT 1953, EGY 1975, RUS 1951, IDN 1985, IDN 1971, ESP 1964, MWI 1959, JOR 1974, MKD 1968 |
| 2000 | 106 | LBY 1959, LBY 1954, BIH 1990, SAU 1964, CHN 1990, JPN 1959, SGP 1964, MKD 1954, KOR 1968, KOR 1981, ROU 1966, CHN 1983, MLI 1990, SRB 1954, TWN 1963, TWN 1969, YEM 1969, CHN 1977, GRC 1962, KOR 1986, LBY 1964, MWI 1964, JPN 1954, LBN 1976, SVN 1953, SAU 1958, IRN 1955, ROU 1960, THA 1986, BWA 1982, DEU 1950, SGP 1969, THA 1961, HRV 1954, IRQ 1951, ESP 1959, TWN 1982, THA 1968, JAM 1950, ROU 1971, LBN 1989, BIH 1956, IRQ 1970, MKD 1962, BGR 1956, ESP 1953, ISR 1953, MYS 1970, PRT 1963, JPN 1964, TUN 1967, BRA 1966, HKG 1978, HKG 1971, BGR 1970, TUN 1962, PSE 1989, KWT 1988, SVN 1959, PRT 1958, GRC 1955, PRY 1971, PRI 1960, SVN 1968, PSE 1968, CHL 1987, SGP 1958, SYR 1970, PAN 1960, MYS 1987, IRL 1989, NGA 1967, MYS 1964, SAU 1952, COG 1963, PRI 1955, MLI 1985, HRV 1959, BGR 1950, VNM 1990, DZA 1962, HKG 1960, SRB 1961, BWA 1987, ITA 1960, MMR 1990, IDN 1987, COG 1972, DOM 1968, HRV 1968, SRB 1968, TGO 1959, YEM 1964, GRC 1967, AUT 1953, EGY 1975, RUS 1951, IDN 1971, BEN 1989, ESP 1964, MWI 1959, JOR 1974, MKD 1968, RUS 1960, CMR 1974, MUS 1984 |
| 2005 | 125 | LBY 1959, LBY 1954, BIH 1992, IRQ 1991, RWA 1994, MLI 1993, ARM 1995, LBR 1995, SAU 1964, MMR 1995, CHN 1990, JPN 1959, SGP 1964, LBY 1995, MKD 1954, AZE 1995, KOR 1968, KOR 1981, ROU 1966, CHN 1983, GEO 1995, SRB 1954, TWN 1963, TWN 1969, YEM 1969, CHN 1977, GRC 1962, KOR 1986, MLI 1988, MWI 1964, JPN 1954, LBN 1976, LVA 1995, SVN 1953, SAU 1958, IRN 1955, ROU 1960, THA 1986, BWA 1982, EST 1995, DEU 1950, SGP 1969, THA 1961, HRV 1954, BLR 1995, IRQ 1951, ESP 1959, KWT 1991, SRB 1995, TWN 1982, TTO 1995, AFG 1994, THA 1968, JAM 1950, ALB 1992, ROU 1971, LBN 1989, BIH 1956, LTU 1995, IRQ 1970, MKD 1962, KAZ 1995, BGR 1956, ESP 1953, ISR 1953, MYS 1970, PRT 1963, JPN 1964, TUN 1967, BRA 1966, HKG 1978, HKG 1971, IRL 1992, BGR 1970, TUN 1962, PSE 1989, SVN 1959, PRT 1958, GRC 1955, PRY 1971, PRI 1960, SVN 1968, PSE 1968, MOZ 1995, CHL 1987, SGP 1958, SYR 1970, PAN 1960, MYS 1987, NGA 1967, MYS 1964, SAU 1952, VNM 1991, COG 1963, PRI 1955, HRV 1959, BGR 1950, DZA 1962, KWT 1985, HKG 1960, SRB 1961, BWA 1987, ITA 1960, IRL 1987, MMR 1990, IDN 1987, COG 1972, DOM 1968, HRV 1968, TGO 1959, YEM 1964, BEN 1994, GRC 1967, AUT 1953, KHM 1995, EGY 1975, PRI 1991, CUB 1994, RUS 1951, IDN 1971, BEN 1989, ESP 1964, MWI 1959, JOR 1974, MKD 1968 |
| 2010 | 139 | LBY 1959, LBY 1954, BIH 1992, AZE 1999, AFG 2000, IRQ 1991, LBY 2000, ARM 1997, MMR 1999, RWA 1994, MLI 1993, CHN 2000, LBR 1995, SAU 1964, CHN 1990, JPN 1959, SGP 1964, LVA 1997, MKD 1954, KOR 1968, KOR 1981, ROU 1966, CHN 1983, GEO 1995, SRB 1954, MMR 1994, TWN 1963, TWN 1969, TCD 2000, YEM 1969, GRC 1962, KOR 1986, BLR 1996, KHM 1998, MLI 1988, KAZ 1998, MWI 1964, JPN 1954, LBN 1976, VNM 2000, SVN 1953, TTO 1996, EST 1996, SAU 1958, IRN 1955, ROU 1960, THA 1986, ALB 1997, BWA 1982, LTU 1997, DEU 1950, SGP 1969, THA 1961, HRV 1954, IRQ 1951, SRB 1998, ESP 1959, KWT 1991, GEO 2000, TWN 1982, AFG 1994, THA 1968, JAM 1950, ALB 1992, RUS 1998, ROU 1971, LBN 1989, BIH 1956, UKR 1998, IRQ 1970, MKD 1962, ARM 1992, BGR 1956, ESP 1953, ISR 1953, MYS 1970, PRT 1963, JPN 1964, MDA 2000, TUN 1967, BRA 1966, HKG 1978, SRB 1993, HKG 1971, IRL 1992, BGR 1970, TUN 1962, PSE 1989, SVN 1959, PRT 1958, BIH 1997, GRC 1955, PRY 1971, PRI 1960, TJK 1998, MOZ 1996, SVN 1968, PSE 1968, CHL 1987, TKM 2000, SGP 1958, SYR 1970, PAN 1960, MYS 1987, UZB 2000, NGA 1967, MYS 1964, SAU 1952, RWA 1999, VNM 1991, COG 1963, PRI 1955, HRV 1959, BGR 1950, CUB 1998, DZA 1962, KWT 1985, HKG 1960, BWA 1987, UGA 2000, ITA 1960, IRL 1987, IDN 1987, MLI 2000, COG 1972, DOM 1968, HRV 1968, LAO 2000, TGO 1959, YEM 1964, BEN 1994, GRC 1967, AUT 1953, EGY 1975, ETH 2000, MNG 1998, PRI 1991, RUS 1951, CUB 1993 |
| 2015 | 153 | LBY 1959, LBY 1954, BIH 1992, AZE 1999, AFG 2001, IRQ 1991, LBY 2000, ARM 1997, MMR 1999, RWA 1994, MLI 1993, AZE 2004, CHN 2001, LBR 1995, SAU 1964, CHN 1990, JPN 1959, SGP 1964, LVA 1997, MKD 1954, MMR 2004, KOR 1968, KOR 1981, ROU 1966, CHN 1983, GEO 1995, SRB 1954, LBR 2005, MMR 1994, TWN 1963, TWN 1969, TCD 2000, YEM 1969, GRC 1962, KOR 1986, BLR 1996, KHM 1998, MLI 1988, KAZ 1998, MWI 1964, JPN 1954, ETH 2003, LBN 1976, VNM 2000, SVN 1953, TTO 1996, BLR 2001, EST 1996, SAU 1958, IRN 1955, ROU 1960, MNG 2003, TKM 2002, THA 1986, ALB 1997, BWA 1982, LTU 1997, ZWE 2005, DEU 1950, SGP 1969, THA 1961, HRV 1954, GEO 2001, IRQ 1951, SRB 1998, ESP 1959, KWT 1991, TWN 1982, VNM 2005, ARM 2002, AFG 1994, THA 1968, IRQ 2003, JAM 1950, ALB 1992, RUS 1998, ROU 1971, LBN 1989, BIH 1956, UZB 2003, UKR 1998, BGD 2005, MKD 1962, ARM 1992, BGR 1956, ESP 1953, ISR 1953, MDA 2001, MYS 1970, PRT 1963, JPN 1964, TUN 1967, KHM 2003, BRA 1966, HKG 1978, SRB 1993, HKG 1971, IRL 1992, BGR 1970, TUN 1962, PSE 1989, SVN 1959, PRT 1958, BIH 1997, GRC 1955, PRY 1971, PRI 1960, TJK 1998, MOZ 1996, SVN 1968, PSE 1968, LKA 2002, CHL 1987, LAO 2005, SGP 1958, SYR 1970, MLI 2004, PAN 2003, PAN 1960, MYS 1987, NGA 1967, MYS 1964, SAU 1952, PSE 2002, RWA 1999, VNM 1991, COG 1963, PRI 1955, HRV 1959, BGR 1950, KAZ 2003, CUB 1998, DZA 1962, URY 2003, KWT 1985, HKG 1960, BWA 1987, UGA 2000, ITA 1960, IRL 1987, IDN 1987, COG 1972, DOM 1968, HRV 1968, LAO 2000, TKM 1997, PER 2003, TGO 1959, YEM 1964, BEN 1994, GRC 1967, AUT 1953, EGY 1975 |

### Benchmarks per returns window (annualised log return, pp/yr)

| T | VT / proxy | benchmark | equal-weight investable basket (n) | SPY | EFA | EEM |
|---|---|---|---|---|---|---|
| 2000 | +2.72 | vt_proxy | +9.69 (20) | +1.41 | — | — |
| 2005 | +4.75 | vt_proxy | +3.67 (22) | +6.98 | +2.76 | +2.79 |
| 2010 | +8.93 | vt | +3.16 (39) | +12.89 | +5.23 | +2.91 |
| 2015 | +11.12 | vt | +7.30 (48) | +13.73 | +7.91 | +7.52 |

VT / VT-proxy legs actually used (PREREG §3.5; first available bars: T = 2000: EFA first bar 2001-08-27; VT switch on its first bar 2008-06-26; year-end rebalancing on SPY's last bar of each calendar year):

| T | from | to | weights |
|---|---|---|---|
| 2000 | 2000-12-29 | 2001-08-27 | SPY 100 % |
| 2000 | 2001-08-27 | 2008-06-26 | SPY 60 %, EFA 40 % |
| 2000 | 2008-06-26 | 2010-12-31 | VT 100 % |
| 2005 | 2005-12-30 | 2008-06-26 | SPY 50 %, EFA 40 %, EEM 10 % |
| 2005 | 2008-06-26 | 2015-12-31 | VT 100 % |
| 2010 | 2010-12-31 | 2020-12-31 | VT 100 % |
| 2015 | 2015-12-31 | 2025-12-31 | VT 100 % |

Equal-weight basket members whose NAV ladder does not reach the exit (kept at their last known value, 0 % thereafter, never dropped): T = 2015: ERUS, NGE, PAK.

### Summary of every row (details follow)

| query | k | h | outcome | n | N_eff | μ̂ (pp/yr) | hit | top-Q | headline CI | p HH | p NW2 | p N1 | p N2 | status counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B | 10 | 10 | growth | 60 | 43 | -0.19 | 0.48 | 0.28 | [-1.47, +1.20] | 0.779 | 0.738 | 0.650 | 0.983 | — |
| B | 10 | 20 | growth | 30 | 17 | +0.33 | 0.53 | 0.27 | [-0.53, +1.28] | — | — | 0.307 | 0.836 | — |
| B | 5 | 10 | growth | 30 | 23 | -0.75 | 0.40 | 0.30 | [-3.65, +2.09] | 0.598 | 0.528 | 0.914 | 0.996 | — |
| B | 5 | 20 | growth | 15 | 9 | -0.49 | 0.40 | 0.13 | [-1.48, +0.81] | — | — | 0.892 | 0.986 | — |
| B_soft | 10 | 10 | growth | 60 | 35 | -0.55 | 0.43 | 0.23 | [-1.47, +0.33] | 0.223 | 0.198 | 0.923 | 0.999 | — |
| B_soft | 10 | 20 | growth | 30 | 15 | -0.41 | 0.37 | 0.17 | [-1.25, +0.43] | — | — | 0.943 | 0.999 | — |
| B_soft | 5 | 10 | growth | 30 | 20 | -0.74 | 0.47 | 0.30 | [-2.95, +1.07] | 0.493 | 0.447 | 0.912 | 0.995 | — |
| B_soft | 5 | 20 | growth | 15 | 6 | -0.35 | 0.53 | 0.20 | [-1.55, +0.91] | — | — | 0.837 | 0.980 | — |
| B3 | 10 | 10 | growth | 60 | 55 | -0.26 | 0.48 | 0.25 | [-1.54, +0.56] | 0.650 | 0.613 | 0.715 | 0.957 | — |
| B3 | 10 | 20 | growth | 30 | 28 | -0.01 | 0.50 | 0.27 | [-0.95, +0.93] | — | — | 0.679 | 0.893 | — |
| B3 | 5 | 10 | growth | 30 | 28 | -1.40 | 0.33 | 0.13 | [-2.42, -0.43] | 0.000 | 0.000 | 0.995 | 0.999 | — |
| B3 | 5 | 20 | growth | 15 | 13 | -0.73 | 0.40 | 0.20 | [-1.97, +0.49] | — | — | 0.958 | 0.968 | — |
| A | 10 | 10 | growth | 60 | 45 | +1.04 | 0.70 | 0.43 | [+0.26, +1.85] | 0.000 | 0.000 | 0.001 | 0.000 | — |
| A | 10 | 20 | growth | 30 | 19 | +1.00 | 0.77 | 0.43 | [+0.01, +1.92] | — | — | 0.011 | 0.002 | — |
| A | 5 | 10 | growth | 30 | 23 | +1.35 | 0.70 | 0.47 | [+0.53, +2.31] | 0.000 | 0.000 | 0.002 | 0.001 | — |
| A | 5 | 20 | growth | 15 | 11 | +1.46 | 0.87 | 0.53 | [+0.76, +2.25] | — | — | 0.009 | 0.003 | — |
| C | 10 | 10 | growth | 60 | 54 | +0.01 | 0.47 | 0.25 | [-0.61, +0.62] | 0.977 | 0.973 | 0.430 | 0.518 | — |
| C | 10 | 20 | growth | 30 | 26 | -0.17 | 0.43 | 0.20 | [-0.74, +0.42] | — | — | 0.817 | 0.666 | — |
| C | 5 | 10 | growth | 30 | 28 | -0.22 | 0.50 | 0.27 | [-1.15, +0.69] | 0.222 | 0.282 | 0.639 | 0.561 | — |
| C | 5 | 20 | growth | 15 | 13 | +0.09 | 0.40 | 0.27 | [-0.67, +0.98] | — | — | 0.545 | 0.232 | — |
| N4 | 10 | 10 | growth | 60 | 44 | +1.57 | 0.73 | 0.50 | [+0.39, +2.64] | 0.005 | 0.001 | 0.000 | 0.000 | — |
| N4 | 10 | 20 | growth | 30 | 18 | +1.68 | 0.77 | 0.47 | [+0.60, +2.82] | — | — | 0.000 | 0.000 | — |
| N4 | 5 | 10 | growth | 30 | 21 | +1.98 | 0.80 | 0.57 | [+0.45, +3.39] | 0.010 | 0.005 | 0.000 | 0.000 | — |
| N4 | 5 | 20 | growth | 15 | 9 | +2.23 | 0.80 | 0.53 | [+0.64, +3.94] | — | — | 0.000 | 0.000 | — |
| B | 10 | 10 | returns | 1 | 1 | -18.46 | 0.00 | 0.00 | [-18.46, -18.46] (degenerate) | — | — | 1.000 | — | liquidated_in_window 1, no_fund_at_entry 4, no_fund_ever 35 |
| B | 5 | 10 | returns | 1 | 1 | -18.46 | 0.00 | 0.00 | [-18.46, -18.46] (degenerate) | — | — | 1.000 | — | liquidated_in_window 1, no_fund_at_entry 1, no_fund_ever 18 |
| B_soft | 10 | 10 | returns | 1 | 1 | -18.46 | 0.00 | 0.00 | [-18.46, -18.46] (degenerate) | — | — | 1.000 | — | liquidated_in_window 1, no_fund_at_entry 3, no_fund_ever 36 |
| B_soft | 5 | 10 | returns | 1 | 1 | -18.46 | 0.00 | 0.00 | [-18.46, -18.46] (degenerate) | — | — | 1.000 | — | liquidated_in_window 1, no_fund_at_entry 2, no_fund_ever 17 |
| B3 | 10 | 10 | returns | 4 | 4 | +0.72 | 0.75 | 0.50 | [-10.96, +11.76] | 0.945 | — | 0.000 | — | investable 3, liquidated_in_window 1, no_fund_at_entry 1, no_fund_ever 35 |
| B3 | 5 | 10 | returns | 2 | 2 | +7.89 | 1.00 | 0.50 | [+0.15, +15.62] | — | — | 0.000 | — | investable 2, no_fund_at_entry 1, no_fund_ever 17 |
| A | 10 | 10 | returns | 7 | 6 | -3.96 | 0.29 | 0.43 | [-9.19, +9.09] | 0.995 | 0.994 | 0.999 | — | investable 6, liquidated_in_window 1, no_fund_at_entry 6, no_fund_ever 27 |
| A | 5 | 10 | returns | 2 | 1 | -4.11 | 0.00 | 0.50 | [-4.11, -4.11] (degenerate) | — | — | 0.973 | — | investable 2, no_fund_at_entry 3, no_fund_ever 15 |
| C | 10 | 10 | returns | 3 | 3 | +3.36 | 0.67 | 0.33 | [-10.11, +15.62] | — | — | 0.000 | — | investable 3, no_fund_at_entry 6, no_fund_ever 31 |
| C | 5 | 10 | returns | 2 | 2 | -2.77 | 0.50 | 0.00 | [-10.11, +4.57] | — | — | 0.751 | — | investable 2, no_fund_at_entry 3, no_fund_ever 15 |
| N4 | 10 | 10 | returns | 7 | 5 | -1.73 | 0.43 | 0.29 | [-7.35, +8.56] | 0.791 | 0.748 | 0.319 | — | investable 7, no_fund_at_entry 4, no_fund_ever 29 |
| N4 | 5 | 10 | returns | 3 | 2 | +0.20 | 0.33 | 0.33 | [-6.75, +14.10] | 0.968 | — | 0.012 | — | investable 3, no_fund_at_entry 1, no_fund_ever 16 |

The 36 rows (24 growth + 12 returns) are reported without any multiple-comparison adjustment; only Query B k = 10 h = 10 is confirmatory (P1, P3 and the §8 decision rules read it), every other row is secondary or informational, and an isolated small p among them (Query A growth, N4 momentum) is what a family of this size produces by chance and is not a finding.

### N3 — 42-vector Query B minus the three-band comparator (paired bootstrap, same resamples)

| k | h | μ̂ 42-vector | μ̂ 3-band | Δ (pp/yr) | CI country cluster | CI T blocks | headline CI | one-sided p (Δ ≤ 0) |
|---|---|---|---|---|---|---|---|---|
| 10 | 10 | -0.19 | -0.26 | +0.07 | [-0.92, +1.18] | [-0.79, +0.89] | [-0.92, +1.18] | 0.449 |
| 10 | 20 | +0.33 | -0.01 | +0.35 | [-0.73, +1.53] | [+0.35, +0.35] (degenerate: block length ≥ n_T) | [-0.73, +1.53] | 0.268 |
| 5 | 10 | -0.75 | -1.40 | +0.65 | [-0.54, +2.14] | [-1.09, +3.33] | [-1.09, +3.33] | 0.284 |
| 5 | 20 | -0.49 | -0.73 | +0.24 | [-0.99, +1.78] | [+0.24, +0.24] (degenerate: block length ≥ n_T) | [-0.99, +1.78] | 0.355 |

For h = 20 the circular T-block scheme has three T's and block length 4, so every resample is the full series and the T-block 'interval' is the point estimate; the country-cluster CI is the only informative scheme and is the headline for those rows.

### Query B — PRIMARY: min blend distance to the prototype set P(T) — k = 10, h = 10, growth

n = 60 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 43** · partial (T = 2015) rows: 10

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.48 |
| top-quartile rate (chance .25) | 0.28 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.19 (per-T average -0.19) |
| naive SE / p | 0.43 / 0.659 |
| Hansen–Hodrick SE (L = 1) / p | 0.68 / 0.779 |
| Newey–West SE L = 2 / p | 0.57 / 0.738 |
| Newey–West SE L = 4 / p | 0.37 / 0.611 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.42 / 0.653 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.49 / 0.696 |
| bootstrap 95 % CI — country cluster | [-0.99, +0.66] |
| bootstrap 95 % CI — circular T blocks | [-1.47, +1.20] |
| **headline CI (wider)** | **[-1.47, +1.20]** — includes 0 |
| N_eff | 43 |

Per T: 1990: -2.09 (n 10, hit 0.40); 1995: -0.44 (n 10, hit 0.40); 2000: +0.77 (n 10, hit 0.40); 2005: +1.88 (n 10, hit 0.90); 2010: +0.39 (n 10, hit 0.50); 2015: -1.65 (n 10, hit 0.30)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.650 | 0.643 | -0.06 | 0.65 | 5000 |
| N2 | 0.983 | 0.962 | +0.51 | 0.98 | 5000 |
| N4 (paired bootstrap Δ vs comparator) | 0.994 | — | +1.57 | Δ = -1.76 CI [-3.16, -0.25] | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (-2.6), SLE (-10.0), COD (-10.5), CMR (-1.5), PSE (+2.2), LBR (-1.6), GIN (-0.2), LAO (+2.1), NPL (+1.0), BOL (+0.2)
- 1995: SLE (-4.7), MWI (-2.0), PSE (-0.8), GIN (-0.9), COD (-5.5), LAO (+1.8), AFG (+1.6), NGA (+0.5), LBR (+6.6), BOL (-1.1)
- 2000: COD (-1.3), GIN (-2.0), SLE (+2.3), AFG (+9.0), ECU (-0.4), MWI (-0.8), IDN (+1.0), TUR (+0.0), AGO (+2.0), BEN (-2.1)
- 2005: SLE (+0.8), LBR (+5.8), COD (+0.7), SOM (+2.7), AFG (+4.4), NGA (+0.6), AGO (-0.1), TCD (+2.2), TZA (+0.8), BOL (+0.8)
- 2010: NGA (-1.3), SLE (+4.7), LBR (+1.3), TCD (-0.7), TZA (+2.0), SOM (+3.1), COD (+0.9), AGO (-3.7), ECU (-0.6), MDG (-1.8)
- 2015: NGA (-2.2), AFG (-6.4), COD (+0.3), BOL (-0.5), AGO (-5.4), CMR (-0.9), BEN (+1.5), SOM (-0.2), TCD (-3.3), NER (+0.5)

### Query B — PRIMARY: min blend distance to the prototype set P(T) — k = 10, h = 20, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 17**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.53 |
| top-quartile rate (chance .25) | 0.27 |
| mean excess μ̂ (pp/yr) vs candidate median | +0.33 (per-T average +0.33) |
| naive SE / p | 0.43 / 0.436 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.48 / 0.484 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.47 / 0.476 |
| bootstrap 95 % CI — country cluster | [-0.53, +1.28] |
| bootstrap 95 % CI — circular T blocks | [+0.33, +0.33] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-0.53, +1.28]** — includes 0 |
| N_eff | 17 |

Per T: 1990: -0.64 (n 10, hit 0.50); 1995: +0.65 (n 10, hit 0.50); 2000: +0.99 (n 10, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.307 | 0.422 | +0.16 | 0.31 | 5000 |
| N2 | 0.836 | 0.940 | +0.73 | 0.84 | 5000 |
| N4 (paired bootstrap Δ vs comparator) | 1.000 | — | +1.68 | Δ = -1.35 CI [-2.83, +0.16] | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (+0.2), SLE (-3.5), COD (-5.6), CMR (-1.3), PSE (+1.0), LBR (-0.9), GIN (-0.7), LAO (+2.7), NPL (+1.5), BOL (+0.1)
- 1995: SLE (-2.0), MWI (+0.3), PSE (-0.5), GIN (-1.1), COD (-2.4), LAO (+2.7), AFG (+3.0), NGA (+0.5), LBR (+6.2), BOL (-0.2)
- 2000: COD (-0.2), GIN (+0.1), SLE (+3.5), AFG (+4.7), ECU (-0.5), MWI (+1.2), IDN (+1.6), TUR (+1.1), AGO (-0.9), BEN (-0.7)

### Query B — PRIMARY: min blend distance to the prototype set P(T) — k = 5, h = 10, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 23** · partial (T = 2015) rows: 5

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.40 |
| top-quartile rate (chance .25) | 0.30 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.75 (per-T average -0.75) |
| naive SE / p | 0.78 / 0.332 |
| Hansen–Hodrick SE (L = 1) / p | 1.43 / 0.598 |
| Newey–West SE L = 2 / p | 1.19 / 0.528 |
| Newey–West SE L = 4 / p | 0.84 / 0.373 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.66 / 0.257 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.86 / 0.385 |
| bootstrap 95 % CI — country cluster | [-1.88, +0.76] |
| bootstrap 95 % CI — circular T blocks | [-3.65, +2.09] |
| **headline CI (wider)** | **[-3.65, +2.09]** — includes 0 |
| N_eff | 23 |

Per T: 1990: -4.51 (n 5, hit 0.20); 1995: -2.77 (n 5, hit 0.00); 2000: +1.51 (n 5, hit 0.40); 2005: +2.89 (n 5, hit 1.00); 2010: +1.19 (n 5, hit 0.60); 2015: -2.82 (n 5, hit 0.20)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.914 | 0.899 | -0.06 | 0.91 | 5000 |
| N2 | 0.996 | 0.995 | +0.59 | 1.00 | 5000 |
| N4 (paired bootstrap Δ vs comparator) | 0.994 | — | +1.98 | Δ = -2.73 CI [-6.06, +0.56] | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (-2.6), SLE (-10.0), COD (-10.5), CMR (-1.5), PSE (+2.2)
- 1995: SLE (-4.7), MWI (-2.0), PSE (-0.8), GIN (-0.9), COD (-5.5)
- 2000: COD (-1.3), GIN (-2.0), SLE (+2.3), AFG (+9.0), ECU (-0.4)
- 2005: SLE (+0.8), LBR (+5.8), COD (+0.7), SOM (+2.7), AFG (+4.4)
- 2010: NGA (-1.3), SLE (+4.7), LBR (+1.3), TCD (-0.7), TZA (+2.0)
- 2015: NGA (-2.2), AFG (-6.4), COD (+0.3), BOL (-0.5), AGO (-5.4)

### Query B — PRIMARY: min blend distance to the prototype set P(T) — k = 5, h = 20, growth

n = 15 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 9**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.40 |
| top-quartile rate (chance .25) | 0.13 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.49 (per-T average -0.49) |
| naive SE / p | 0.65 / 0.452 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.58 / 0.402 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.62 / 0.430 |
| bootstrap 95 % CI — country cluster | [-1.48, +0.81] |
| bootstrap 95 % CI — circular T blocks | [-0.49, -0.49] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-1.48, +0.81]** — includes 0 |
| N_eff | 9 |

Per T: 1990: -1.82 (n 5, hit 0.40); 1995: -1.15 (n 5, hit 0.20); 2000: +1.51 (n 5, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.892 | 0.855 | +0.15 | 0.89 | 5000 |
| N2 | 0.986 | 0.992 | +0.79 | 0.99 | 5000 |
| N4 (paired bootstrap Δ vs comparator) | 1.000 | — | +2.23 | Δ = -2.71 CI [-4.67, -0.52] | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (+0.2), SLE (-3.5), COD (-5.6), CMR (-1.3), PSE (+1.0)
- 1995: SLE (-2.0), MWI (+0.3), PSE (-0.5), GIN (-1.1), COD (-2.4)
- 2000: COD (-0.2), GIN (+0.1), SLE (+3.5), AFG (+4.7), ECU (-0.5)

### Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P) — k = 10, h = 10, growth

n = 60 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 35** · partial (T = 2015) rows: 10

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.43 |
| top-quartile rate (chance .25) | 0.23 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.55 (per-T average -0.55) |
| naive SE / p | 0.39 / 0.162 |
| Hansen–Hodrick SE (L = 1) / p | 0.45 / 0.223 |
| Newey–West SE L = 2 / p | 0.43 / 0.198 |
| Newey–West SE L = 4 / p | 0.35 / 0.114 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.38 / 0.146 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.44 / 0.207 |
| bootstrap 95 % CI — country cluster | [-1.24, +0.25] |
| bootstrap 95 % CI — circular T blocks | [-1.47, +0.33] |
| **headline CI (wider)** | **[-1.47, +0.33]** — includes 0 |
| N_eff | 35 |

Per T: 1990: -2.27 (n 10, hit 0.30); 1995: -0.62 (n 10, hit 0.40); 2000: -0.74 (n 10, hit 0.30); 2005: +0.59 (n 10, hit 0.50); 2010: +0.52 (n 10, hit 0.60); 2015: -0.78 (n 10, hit 0.50)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.923 | 0.878 | -0.06 | 0.92 | 5000 |
| N2 | 0.999 | 0.998 | +0.56 | 1.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (-2.6), LBR (-1.6), SLE (-10.0), COD (-10.5), LAO (+2.1), GIN (-0.2), GTM (-0.1), HTI (+0.7), CMR (-1.5), NPL (+1.0)
- 1995: SLE (-4.7), GIN (-0.9), COD (-5.5), NGA (+0.5), LAO (+1.8), LBR (+6.6), GTM (-1.5), NPL (+0.4), CMR (-0.8), MRT (-2.1)
- 2000: SLE (+2.3), GIN (-2.0), COD (-1.3), NGA (+2.2), LBR (-0.9), AGO (+2.0), BEN (-2.1), MRT (-1.7), MDG (-3.2), CAF (-2.8)
- 2005: SLE (+0.8), COD (+0.7), LBR (+5.8), AGO (-0.1), BEN (-1.4), NGA (+0.6), MDG (-2.6), GIN (-1.3), ETH (+4.9), MRT (-1.6)
- 2010: NGA (-1.3), COD (+0.9), LBR (+1.3), SOM (+3.1), SLE (+4.7), BEN (+0.7), AGO (-3.7), TCD (-0.7), MDG (-1.8), TZA (+2.0)
- 2015: NGA (-2.2), BEN (+1.5), COD (+0.3), AGO (-5.4), SOM (-0.2), TCD (-3.3), SEN (+0.9), BFA (+0.7), LBR (-1.8), MLI (+1.6)

### Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P) — k = 10, h = 20, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 15**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.37 |
| top-quartile rate (chance .25) | 0.17 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.41 (per-T average -0.41) |
| naive SE / p | 0.41 / 0.324 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.44 / 0.354 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.44 / 0.354 |
| bootstrap 95 % CI — country cluster | [-1.25, +0.43] |
| bootstrap 95 % CI — circular T blocks | [-0.41, -0.41] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-1.25, +0.43]** — includes 0 |
| N_eff | 15 |

Per T: 1990: -0.87 (n 10, hit 0.30); 1995: +0.09 (n 10, hit 0.40); 2000: -0.45 (n 10, hit 0.40)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.943 | 0.956 | +0.16 | 0.94 | 5000 |
| N2 | 0.999 | 1.000 | +0.89 | 1.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (+0.2), LBR (-0.9), SLE (-3.5), COD (-5.6), LAO (+2.7), GIN (-0.7), GTM (-0.6), HTI (-0.6), CMR (-1.3), NPL (+1.5)
- 1995: SLE (-2.0), GIN (-1.1), COD (-2.4), NGA (+0.5), LAO (+2.7), LBR (+6.2), GTM (-1.2), NPL (+1.2), CMR (-1.1), MRT (-1.9)
- 2000: SLE (+3.5), GIN (+0.1), COD (-0.2), NGA (+0.5), LBR (+0.2), AGO (-0.9), BEN (-0.7), MRT (-1.1), MDG (-2.5), CAF (-3.3)

### Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P) — k = 5, h = 10, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 20** · partial (T = 2015) rows: 5

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.47 |
| top-quartile rate (chance .25) | 0.30 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.74 (per-T average -0.74) |
| naive SE / p | 0.67 / 0.266 |
| Hansen–Hodrick SE (L = 1) / p | 1.09 / 0.493 |
| Newey–West SE L = 2 / p | 0.98 / 0.447 |
| Newey–West SE L = 4 / p | 0.80 / 0.351 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.53 / 0.163 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.75 / 0.320 |
| bootstrap 95 % CI — country cluster | [-1.66, +0.42] |
| bootstrap 95 % CI — circular T blocks | [-2.95, +1.07] |
| **headline CI (wider)** | **[-2.95, +1.07]** — includes 0 |
| N_eff | 20 |

Per T: 1990: -4.52 (n 5, hit 0.20); 1995: -1.75 (n 5, hit 0.40); 2000: +0.08 (n 5, hit 0.40); 2005: +1.17 (n 5, hit 0.60); 2010: +1.75 (n 5, hit 0.80); 2015: -1.19 (n 5, hit 0.40)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.912 | 0.702 | -0.06 | 0.91 | 5000 |
| N2 | 0.995 | 0.947 | +0.63 | 1.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (-2.6), LBR (-1.6), SLE (-10.0), COD (-10.5), LAO (+2.1)
- 1995: SLE (-4.7), GIN (-0.9), COD (-5.5), NGA (+0.5), LAO (+1.8)
- 2000: SLE (+2.3), GIN (-2.0), COD (-1.3), NGA (+2.2), LBR (-0.9)
- 2005: SLE (+0.8), COD (+0.7), LBR (+5.8), AGO (-0.1), BEN (-1.4)
- 2010: NGA (-1.3), COD (+0.9), LBR (+1.3), SOM (+3.1), SLE (+4.7)
- 2015: NGA (-2.2), BEN (+1.5), COD (+0.3), AGO (-5.4), SOM (-0.2)

### Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P) — k = 5, h = 20, growth

n = 15 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 6**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.53 |
| top-quartile rate (chance .25) | 0.20 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.35 (per-T average -0.35) |
| naive SE / p | 0.62 / 0.572 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.65 / 0.589 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.66 / 0.595 |
| bootstrap 95 % CI — country cluster | [-1.55, +0.91] |
| bootstrap 95 % CI — circular T blocks | [-0.35, -0.35] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-1.55, +0.91]** — includes 0 |
| N_eff | 6 |

Per T: 1990: -1.41 (n 5, hit 0.40); 1995: -0.45 (n 5, hit 0.40); 2000: +0.81 (n 5, hit 0.80)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.837 | 0.495 | +0.15 | 0.84 | 5000 |
| N2 | 0.980 | 0.952 | +0.97 | 0.98 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: NGA (+0.2), LBR (-0.9), SLE (-3.5), COD (-5.6), LAO (+2.7)
- 1995: SLE (-2.0), GIN (-1.1), COD (-2.4), NGA (+0.5), LAO (+2.7)
- 2000: SLE (+3.5), GIN (+0.1), COD (-0.2), NGA (+0.5), LBR (+0.2)

### N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector — k = 10, h = 10, growth

n = 60 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 55** · partial (T = 2015) rows: 10

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.48 |
| top-quartile rate (chance .25) | 0.25 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.26 (per-T average -0.26) |
| naive SE / p | 0.47 / 0.582 |
| Hansen–Hodrick SE (L = 1) / p | 0.57 / 0.650 |
| Newey–West SE L = 2 / p | 0.51 / 0.613 |
| Newey–West SE L = 4 / p | 0.45 / 0.570 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.47 / 0.583 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.47 / 0.582 |
| bootstrap 95 % CI — country cluster | [-1.22, +0.67] |
| bootstrap 95 % CI — circular T blocks | [-1.54, +0.56] |
| **headline CI (wider)** | **[-1.54, +0.56]** — includes 0 |
| N_eff | 55 |

Per T: 1990: -3.10 (n 10, hit 0.40); 1995: -0.21 (n 10, hit 0.50); 2000: +1.45 (n 10, hit 0.50); 2005: -0.40 (n 10, hit 0.40); 2010: +0.57 (n 10, hit 0.60); 2015: +0.14 (n 10, hit 0.50)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.715 | 0.643 | -0.06 | 0.71 | 5000 |
| N2 | 0.957 | 0.976 | +0.34 | 0.96 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: COG (-1.4), KGZ (-6.8), NZL (+0.2), COL (-0.8), COD (-10.5), IRN (+0.5), DZA (-1.7), PAK (+1.6), CRI (+0.9), TJK (-12.8)
- 1995: COG (-3.2), TZA (+0.4), PRY (-1.8), ETH (-0.3), SDN (+1.5), CHN (+5.5), SOM (+0.1), MDG (-2.7), TGO (-2.7), MUS (+1.0)
- 2000: BRA (-0.3), TZA (+0.9), SYR (-0.8), LAO (+2.7), EGY (-0.1), HND (-1.2), ZWE (-0.9), SLE (+2.3), AZE (+10.0), LKA (+1.8)
- 2005: NER (-0.9), YEM (-10.8), MEX (-2.0), BEN (-1.4), DOM (+1.7), MYS (+0.4), SEN (-1.7), AGO (-0.1), ZWE (+4.8), LBR (+5.8)
- 2010: GMB (-1.7), AFG (+0.5), LBR (+1.3), SDN (-1.6), COD (+0.9), KHM (+3.8), TGO (+1.2), CMR (-0.2), MRT (-0.6), TZA (+2.0)
- 2015: COD (+0.3), NAM (-3.7), ECU (-0.8), PRY (-0.3), HTI (-3.2), EGY (+1.3), SLE (+4.7), ETH (+2.7), CMR (-0.9), TZA (+1.2)

### N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector — k = 10, h = 20, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 28**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.50 |
| top-quartile rate (chance .25) | 0.27 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.01 (per-T average -0.01) |
| naive SE / p | 0.46 / 0.978 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.47 / 0.978 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.46 / 0.978 |
| bootstrap 95 % CI — country cluster | [-0.95, +0.93] |
| bootstrap 95 % CI — circular T blocks | [-0.01, -0.01] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-0.95, +0.93]** — includes 0 |
| N_eff | 28 |

Per T: 1990: -1.37 (n 10, hit 0.30); 1995: +0.54 (n 10, hit 0.60); 2000: +0.79 (n 10, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.679 | 0.577 | +0.16 | 0.68 | 5000 |
| N2 | 0.893 | 0.917 | +0.45 | 0.89 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: COG (-1.9), KGZ (-2.9), NZL (-0.2), COL (-0.2), COD (-5.6), IRN (+0.9), DZA (-0.8), PAK (+0.7), CRI (+0.8), TJK (-4.5)
- 1995: COG (-2.2), TZA (+0.6), PRY (-0.5), ETH (+2.3), SDN (+0.1), CHN (+5.8), SOM (+1.4), MDG (-2.7), TGO (-0.6), MUS (+1.2)
- 2000: BRA (-1.0), TZA (+1.4), SYR (-4.2), LAO (+3.2), EGY (+0.1), HND (-1.0), ZWE (-0.3), SLE (+3.5), AZE (+4.3), LKA (+1.9)

### N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector — k = 5, h = 10, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 28** · partial (T = 2015) rows: 5

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.33 |
| top-quartile rate (chance .25) | 0.13 |
| mean excess μ̂ (pp/yr) vs candidate median | -1.40 (per-T average -1.40) |
| naive SE / p | 0.57 / 0.015 |
| Hansen–Hodrick SE (L = 1) / p | 0.35 / 0.000 |
| Newey–West SE L = 2 / p | 0.39 / 0.000 |
| Newey–West SE L = 4 / p | 0.34 / 0.000 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.50 / 0.005 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.57 / 0.014 |
| bootstrap 95 % CI — country cluster | [-2.43, -0.49] |
| bootstrap 95 % CI — circular T blocks | [-2.42, -0.43] |
| **headline CI (wider)** | **[-2.42, -0.43]** — excludes 0 |
| N_eff | 28 |

Per T: 1990: -3.89 (n 5, hit 0.20); 1995: -0.68 (n 5, hit 0.40); 2000: +0.48 (n 5, hit 0.40); 2005: -2.66 (n 5, hit 0.20); 2010: -0.11 (n 5, hit 0.60); 2015: -1.53 (n 5, hit 0.20)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.995 | 0.980 | -0.06 | 0.99 | 5000 |
| N2 | 0.999 | 1.000 | +0.34 | 1.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: COG (-1.4), KGZ (-6.8), NZL (+0.2), COL (-0.8), COD (-10.5)
- 1995: COG (-3.2), TZA (+0.4), PRY (-1.8), ETH (-0.3), SDN (+1.5)
- 2000: BRA (-0.3), TZA (+0.9), SYR (-0.8), LAO (+2.7), EGY (-0.1)
- 2005: NER (-0.9), YEM (-10.8), MEX (-2.0), BEN (-1.4), DOM (+1.7)
- 2010: GMB (-1.7), AFG (+0.5), LBR (+1.3), SDN (-1.6), COD (+0.9)
- 2015: COD (+0.3), NAM (-3.7), ECU (-0.8), PRY (-0.3), HTI (-3.2)

### N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector — k = 5, h = 20, growth

n = 15 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 13**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.40 |
| top-quartile rate (chance .25) | 0.20 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.73 (per-T average -0.73) |
| naive SE / p | 0.61 / 0.231 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.62 / 0.240 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.61 / 0.234 |
| bootstrap 95 % CI — country cluster | [-1.97, +0.49] |
| bootstrap 95 % CI — circular T blocks | [-0.73, -0.73] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-1.97, +0.49]** — includes 0 |
| N_eff | 13 |

Per T: 1990: -2.14 (n 5, hit 0.00); 1995: +0.05 (n 5, hit 0.60); 2000: -0.08 (n 5, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.958 | 0.855 | +0.15 | 0.96 | 5000 |
| N2 | 0.968 | 0.960 | +0.36 | 0.97 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: COG (-1.9), KGZ (-2.9), NZL (-0.2), COL (-0.2), COD (-5.6)
- 1995: COG (-2.2), TZA (+0.6), PRY (-0.5), ETH (+2.3), SDN (+0.1)
- 2000: BRA (-1.0), TZA (+1.4), SYR (-4.2), LAO (+3.2), EGY (+0.1)

### Query A — China 1990 anchor (search.similar, blend) — k = 10, h = 10, growth

n = 60 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 45** · partial (T = 2015) rows: 10

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.70 |
| top-quartile rate (chance .25) | 0.43 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.04 (per-T average +1.04) |
| naive SE / p | 0.31 / 0.001 |
| Hansen–Hodrick SE (L = 1) / p | 0.17 / 0.000 |
| Newey–West SE L = 2 / p | 0.22 / 0.000 |
| Newey–West SE L = 4 / p | 0.20 / 0.000 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.40 / 0.009 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.35 / 0.003 |
| bootstrap 95 % CI — country cluster | [+0.26, +1.85] |
| bootstrap 95 % CI — circular T blocks | [+0.57, +1.53] |
| **headline CI (wider)** | **[+0.26, +1.85]** — excludes 0 |
| N_eff | 45 |

Per T: 1990: +2.21 (n 10, hit 0.90); 1995: +0.67 (n 10, hit 0.60); 2000: +0.97 (n 10, hit 0.60); 2005: +1.33 (n 10, hit 0.70); 2010: -0.15 (n 10, hit 0.70); 2015: +1.22 (n 10, hit 0.70)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.001 | 0.001 | -0.06 | 0.00 | 5000 |
| N2 | 0.000 | 0.001 | -0.07 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: MUS (+2.4), CHL (+3.5), THA (+1.5), ALB (-0.0), LKA (+1.9), KOR (+4.8), TTO (+2.2), TWN (+4.0), TUR (+0.5), ISR (+1.4)
- 1995: LKA (+0.5), TUR (+0.6), MUS (+1.0), IDN (-1.3), BRA (-1.4), PAN (-0.1), TUN (+0.9), MMR (+6.4), CHL (+0.9), THA (-0.7)
- 2000: TUR (+0.0), IDN (+1.0), MMR (+7.8), PAN (+1.1), TUN (+0.4), BRA (-0.3), LBN (+1.2), COL (-0.2), CRI (+0.1), VEN (-1.3)
- 2005: MMR (+5.6), DZA (-1.5), IDN (+1.7), PAN (+3.3), MAR (+1.9), MYS (+0.4), PER (+2.3), VEN (-2.0), IND (+2.6), LBN (-1.1)
- 2010: DZA (-0.5), UZB (+2.9), MAR (+0.6), IND (+2.6), ECU (-0.6), DOM (+1.6), LBY (-10.3), PRY (+0.4), KGZ (+0.7), MYS (+1.0)
- 2015: PRY (-0.3), UZB (+2.0), BOL (-0.5), IND (+2.9), TKM (+1.7), DOM (+1.9), LAO (+2.1), ECU (-0.8), EGY (+1.3), PHL (+1.8)

### Query A — China 1990 anchor (search.similar, blend) — k = 10, h = 20, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 19**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.77 |
| top-quartile rate (chance .25) | 0.43 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.00 (per-T average +1.00) |
| naive SE / p | 0.43 / 0.019 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.48 / 0.039 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.47 / 0.033 |
| bootstrap 95 % CI — country cluster | [+0.01, +1.92] |
| bootstrap 95 % CI — circular T blocks | [+1.00, +1.00] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[+0.01, +1.92]** — excludes 0 |
| N_eff | 19 |

Per T: 1990: +1.97 (n 10, hit 1.00); 1995: +1.13 (n 10, hit 0.80); 2000: -0.11 (n 10, hit 0.50)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.011 | 0.002 | +0.16 | 0.01 | 5000 |
| N2 | 0.002 | 0.004 | +0.16 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: MUS (+1.9), CHL (+2.3), THA (+1.5), ALB (+2.0), LKA (+2.2), KOR (+3.4), TTO (+2.7), TWN (+2.8), TUR (+0.6), ISR (+0.3)
- 1995: LKA (+1.9), TUR (+0.8), MUS (+1.2), IDN (+0.2), BRA (-1.0), PAN (+1.6), TUN (+0.5), MMR (+6.0), CHL (+0.6), THA (-0.3)
- 2000: TUR (+1.1), IDN (+1.6), MMR (+5.5), PAN (+1.0), TUN (-0.1), BRA (-1.0), LBN (-1.9), COL (-0.1), CRI (+0.3), VEN (-7.5)

### Query A — China 1990 anchor (search.similar, blend) — k = 5, h = 10, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 23** · partial (T = 2015) rows: 5

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.70 |
| top-quartile rate (chance .25) | 0.47 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.35 (per-T average +1.35) |
| naive SE / p | 0.37 / 0.000 |
| Hansen–Hodrick SE (L = 1) / p | 0.17 / 0.000 |
| Newey–West SE L = 2 / p | 0.17 / 0.000 |
| Newey–West SE L = 4 / p | 0.14 / 0.000 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.46 / 0.003 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.41 / 0.001 |
| bootstrap 95 % CI — country cluster | [+0.53, +2.31] |
| bootstrap 95 % CI — circular T blocks | [+0.92, +1.92] |
| **headline CI (wider)** | **[+0.53, +2.31]** — excludes 0 |
| N_eff | 23 |

Per T: 1990: +1.82 (n 5, hit 0.80); 1995: -0.13 (n 5, hit 0.60); 2000: +2.04 (n 5, hit 0.80); 2005: +2.20 (n 5, hit 0.80); 2010: +1.00 (n 5, hit 0.60); 2015: +1.18 (n 5, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.002 | 0.020 | -0.06 | 0.00 | 5000 |
| N2 | 0.001 | 0.022 | -0.09 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: MUS (+2.4), CHL (+3.5), THA (+1.5), ALB (-0.0), LKA (+1.9)
- 1995: LKA (+0.5), TUR (+0.6), MUS (+1.0), IDN (-1.3), BRA (-1.4)
- 2000: TUR (+0.0), IDN (+1.0), MMR (+7.8), PAN (+1.1), TUN (+0.4)
- 2005: MMR (+5.6), DZA (-1.5), IDN (+1.7), PAN (+3.3), MAR (+1.9)
- 2010: DZA (-0.5), UZB (+2.9), MAR (+0.6), IND (+2.6), ECU (-0.6)
- 2015: PRY (-0.3), UZB (+2.0), BOL (-0.5), IND (+2.9), TKM (+1.7)

### Query A — China 1990 anchor (search.similar, blend) — k = 5, h = 20, growth

n = 15 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 11**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.87 |
| top-quartile rate (chance .25) | 0.53 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.46 (per-T average +1.46) |
| naive SE / p | 0.37 / 0.000 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.36 / 0.000 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.36 / 0.000 |
| bootstrap 95 % CI — country cluster | [+0.76, +2.25] |
| bootstrap 95 % CI — circular T blocks | [+1.46, +1.46] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[+0.76, +2.25]** — excludes 0 |
| N_eff | 11 |

Per T: 1990: +1.97 (n 5, hit 1.00); 1995: +0.61 (n 5, hit 0.80); 2000: +1.80 (n 5, hit 0.80)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.009 | 0.003 | +0.15 | 0.01 | 5000 |
| N2 | 0.003 | 0.007 | +0.18 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: MUS (+1.9), CHL (+2.3), THA (+1.5), ALB (+2.0), LKA (+2.2)
- 1995: LKA (+1.9), TUR (+0.8), MUS (+1.2), IDN (+0.2), BRA (-1.0)
- 2000: TUR (+1.1), IDN (+1.6), MMR (+5.5), PAN (+1.0), TUN (-0.1)

### Query C — 10-year motion nearest China 1980→1990 (trend metric, informational) — k = 10, h = 10, growth

n = 60 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 54** · partial (T = 2015) rows: 10

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.47 |
| top-quartile rate (chance .25) | 0.25 |
| mean excess μ̂ (pp/yr) vs candidate median | +0.01 (per-T average +0.01) |
| naive SE / p | 0.33 / 0.981 |
| Hansen–Hodrick SE (L = 1) / p | 0.27 / 0.977 |
| Newey–West SE L = 2 / p | 0.23 / 0.973 |
| Newey–West SE L = 4 / p | 0.22 / 0.972 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.31 / 0.980 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.32 / 0.981 |
| bootstrap 95 % CI — country cluster | [-0.61, +0.62] |
| bootstrap 95 % CI — circular T blocks | [-0.51, +0.40] |
| **headline CI (wider)** | **[-0.61, +0.62]** — includes 0 |
| N_eff | 54 |

Per T: 1990: +0.73 (n 10, hit 0.90); 1995: -0.20 (n 10, hit 0.30); 2000: +0.09 (n 10, hit 0.30); 2005: +0.89 (n 10, hit 0.50); 2010: -0.45 (n 10, hit 0.40); 2015: -1.01 (n 10, hit 0.40)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.430 | 0.738 | -0.06 | 0.43 | 5000 |
| N2 | 0.518 | 0.946 | +0.01 | 0.52 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: CUB (-3.2), NLD (+1.0), NZL (+0.2), PAN (+1.3), CHL (+3.5), ITA (+0.1), THA (+1.5), NOR (+1.5), AUS (+0.8), GBR (+0.7)
- 1995: NAM (-0.5), PRT (-0.6), MEX (-0.8), ESP (+0.1), KOR (+2.2), ITA (-1.2), JOR (-0.3), URY (-1.7), DOM (+0.9), PAN (-0.1)
- 2000: LKA (+1.8), IRL (-1.8), PRT (-2.4), ESP (-2.1), IDN (+1.0), TUR (+0.0), LBY (+8.1), GRC (-1.0), KWT (-2.4), BRA (-0.3)
- 2005: RWA (+2.5), LBY (-3.7), BWA (-1.5), BGD (+4.2), IRL (-0.1), KEN (-0.1), ZWE (+4.8), GHA (+1.5), EGY (-0.2), TGO (+1.5)
- 2010: DZA (-0.5), ZAF (-1.9), MNG (+3.1), TKM (+1.3), SYR (-7.6), BDI (-0.8), BWA (-0.1), SWZ (+0.2), GAB (-1.1), UZB (+2.9)
- 2015: NAM (-3.7), PSE (-2.9), LAO (+2.1), SLV (+0.7), TKM (+1.7), PRY (-0.3), NIC (-0.3), YEM (-7.7), UZB (+2.0), JOR (-1.7)

### Query C — 10-year motion nearest China 1980→1990 (trend metric, informational) — k = 10, h = 20, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 26**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.43 |
| top-quartile rate (chance .25) | 0.20 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.17 (per-T average -0.17) |
| naive SE / p | 0.27 / 0.519 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.30 / 0.565 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.29 / 0.553 |
| bootstrap 95 % CI — country cluster | [-0.74, +0.42] |
| bootstrap 95 % CI — circular T blocks | [-0.17, -0.17] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-0.74, +0.42]** — includes 0 |
| N_eff | 26 |

Per T: 1990: +0.37 (n 10, hit 0.50); 1995: -0.37 (n 10, hit 0.40); 2000: -0.51 (n 10, hit 0.40)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.817 | 0.825 | +0.16 | 0.82 | 5000 |
| N2 | 0.666 | 0.560 | -0.06 | 0.67 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: CUB (-0.2), NLD (-0.1), NZL (-0.2), PAN (+1.6), CHL (+2.3), ITA (-1.1), THA (+1.5), NOR (+0.0), AUS (+0.2), GBR (-0.3)
- 1995: NAM (-0.1), PRT (-1.6), MEX (-1.4), ESP (-1.3), KOR (+1.3), ITA (-2.3), JOR (-1.5), URY (+0.4), DOM (+1.3), PAN (+1.6)
- 2000: LKA (+1.9), IRL (+1.2), PRT (-1.8), ESP (-1.8), IDN (+1.6), TUR (+1.1), LBY (-1.1), GRC (-2.2), KWT (-3.0), BRA (-1.0)

### Query C — 10-year motion nearest China 1980→1990 (trend metric, informational) — k = 5, h = 10, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 28** · partial (T = 2015) rows: 5

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.50 |
| top-quartile rate (chance .25) | 0.27 |
| mean excess μ̂ (pp/yr) vs candidate median | -0.22 (per-T average -0.22) |
| naive SE / p | 0.47 / 0.633 |
| Hansen–Hodrick SE (L = 1) / p | 0.18 / 0.222 |
| Newey–West SE L = 2 / p | 0.21 / 0.282 |
| Newey–West SE L = 4 / p | 0.19 / 0.251 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.47 / 0.634 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.46 / 0.630 |
| bootstrap 95 % CI — country cluster | [-1.15, +0.69] |
| bootstrap 95 % CI — circular T blocks | [-0.62, +0.15] |
| **headline CI (wider)** | **[-1.15, +0.69]** — includes 0 |
| N_eff | 28 |

Per T: 1990: +0.56 (n 5, hit 0.80); 1995: +0.08 (n 5, hit 0.40); 2000: -0.70 (n 5, hit 0.40); 2005: +0.27 (n 5, hit 0.40); 2010: -1.12 (n 5, hit 0.40); 2015: -0.42 (n 5, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.639 | 0.562 | -0.06 | 0.64 | 5000 |
| N2 | 0.561 | 0.602 | -0.17 | 0.56 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: CUB (-3.2), NLD (+1.0), NZL (+0.2), PAN (+1.3), CHL (+3.5)
- 1995: NAM (-0.5), PRT (-0.6), MEX (-0.8), ESP (+0.1), KOR (+2.2)
- 2000: LKA (+1.8), IRL (-1.8), PRT (-2.4), ESP (-2.1), IDN (+1.0)
- 2005: RWA (+2.5), LBY (-3.7), BWA (-1.5), BGD (+4.2), IRL (-0.1)
- 2010: DZA (-0.5), ZAF (-1.9), MNG (+3.1), TKM (+1.3), SYR (-7.6)
- 2015: NAM (-3.7), PSE (-2.9), LAO (+2.1), SLV (+0.7), TKM (+1.7)

### Query C — 10-year motion nearest China 1980→1990 (trend metric, informational) — k = 5, h = 20, growth

n = 15 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 13**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.40 |
| top-quartile rate (chance .25) | 0.27 |
| mean excess μ̂ (pp/yr) vs candidate median | +0.09 (per-T average +0.09) |
| naive SE / p | 0.37 / 0.809 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.43 / 0.832 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.41 / 0.826 |
| bootstrap 95 % CI — country cluster | [-0.67, +0.98] |
| bootstrap 95 % CI — circular T blocks | [+0.09, +0.09] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-0.67, +0.98]** — includes 0 |
| N_eff | 13 |

Per T: 1990: +0.68 (n 5, hit 0.40); 1995: -0.61 (n 5, hit 0.20); 2000: +0.21 (n 5, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.545 | 0.855 | +0.15 | 0.55 | 5000 |
| N2 | 0.232 | 0.628 | -0.16 | 0.23 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: CUB (-0.2), NLD (-0.1), NZL (-0.2), PAN (+1.6), CHL (+2.3)
- 1995: NAM (-0.1), PRT (-1.6), MEX (-1.4), ESP (-1.3), KOR (+1.3)
- 2000: LKA (+1.9), IRL (+1.2), PRT (-1.8), ESP (-1.8), IDN (+1.6)

### N4 comparator — prior-10-year growth momentum — k = 10, h = 10, growth

n = 60 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 44** · partial (T = 2015) rows: 10

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.73 |
| top-quartile rate (chance .25) | 0.50 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.57 (per-T average +1.57) |
| naive SE / p | 0.45 / 0.000 |
| Hansen–Hodrick SE (L = 1) / p | 0.56 / 0.005 |
| Newey–West SE L = 2 / p | 0.49 / 0.001 |
| Newey–West SE L = 4 / p | 0.42 / 0.000 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.58 / 0.006 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.49 / 0.001 |
| bootstrap 95 % CI — country cluster | [+0.39, +2.64] |
| bootstrap 95 % CI — circular T blocks | [+0.52, +2.53] |
| **headline CI (wider)** | **[+0.39, +2.64]** — excludes 0 |
| N_eff | 44 |

Per T: 1990: +2.39 (n 10, hit 0.90); 1995: +1.17 (n 10, hit 0.60); 2000: +3.25 (n 10, hit 0.90); 2005: +2.57 (n 10, hit 0.90); 2010: -0.61 (n 10, hit 0.50); 2015: +0.65 (n 10, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.000 | 0.000 | -0.06 | 0.00 | 5000 |
| N2 | 0.000 | 0.000 | -0.13 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: KOR (+4.8), BWA (+0.7), CHN (+7.4), TWN (+4.0), THA (+1.5), HKG (+0.4), SGP (+2.4), MUS (+2.4), IDN (+1.0), JPN (-0.6)
- 1995: KOR (+2.2), CHN (+5.5), THA (-0.7), TWN (+1.6), CHL (+0.9), MLI (+3.6), SGP (+0.6), KWT (-0.3), BWA (-0.5), IDN (-1.3)
- 2000: BIH (+1.6), CHN (+6.6), MLI (+2.7), LBY (+8.1), KOR (+1.3), IRL (-1.8), VNM (+4.9), TWN (+0.9), MMR (+7.8), CHL (+0.4)
- 2005: BIH (+1.2), ARM (+1.8), LBR (+5.8), MMR (+5.6), LBY (-3.7), AZE (+5.0), GEO (+3.3), CHN (+6.0), LVA (+0.3), IRQ (+0.4)
- 2010: AZE (-1.5), AFG (+0.5), LBY (-10.3), MMR (+3.2), CHN (+4.9), GNQ (-8.0), ARM (+2.3), TCD (-0.7), VNM (+3.7), BLR (-0.1)
- 2015: CHN (+3.9), LBR (-1.8), MMR (+0.8), DJI (+1.9), AZE (-1.1), ETH (+2.7), ZWE (-1.1), VNM (+3.3), AFG (-6.4), BGD (+4.2)

### N4 comparator — prior-10-year growth momentum — k = 10, h = 20, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 18**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.77 |
| top-quartile rate (chance .25) | 0.47 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.68 (per-T average +1.68) |
| naive SE / p | 0.42 / 0.000 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.57 / 0.003 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.53 / 0.001 |
| bootstrap 95 % CI — country cluster | [+0.60, +2.82] |
| bootstrap 95 % CI — circular T blocks | [+1.68, +1.68] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[+0.60, +2.82]** — excludes 0 |
| N_eff | 18 |

Per T: 1990: +1.95 (n 10, hit 0.80); 1995: +0.87 (n 10, hit 0.70); 2000: +2.22 (n 10, hit 0.80)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.000 | 0.002 | +0.16 | 0.00 | 5000 |
| N2 | 0.000 | 0.000 | -0.18 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: KOR (+3.4), BWA (-0.3), CHN (+7.3), TWN (+2.8), THA (+1.5), HKG (+0.9), SGP (+1.8), MUS (+1.9), IDN (+1.3), JPN (-1.1)
- 1995: KOR (+1.3), CHN (+5.8), THA (-0.3), TWN (+1.2), CHL (+0.6), MLI (+3.4), SGP (+0.5), KWT (-3.0), BWA (-1.0), IDN (+0.2)
- 2000: BIH (+1.8), CHN (+5.7), MLI (+2.6), LBY (-1.1), KOR (+1.1), IRL (+1.2), VNM (+4.3), TWN (+1.2), MMR (+5.5), CHL (+0.0)

### N4 comparator — prior-10-year growth momentum — k = 5, h = 10, growth

n = 30 lookalike-windows over T ∈ {1990, 1995, 2000, 2005, 2010, 2015} · **N_eff = 21** · partial (T = 2015) rows: 5

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.80 |
| top-quartile rate (chance .25) | 0.57 |
| mean excess μ̂ (pp/yr) vs candidate median | +1.98 (per-T average +1.98) |
| naive SE / p | 0.67 / 0.003 |
| Hansen–Hodrick SE (L = 1) / p | 0.77 / 0.010 |
| Newey–West SE L = 2 / p | 0.71 / 0.005 |
| Newey–West SE L = 4 / p | 0.63 / 0.002 |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.79 / 0.012 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 0.73 / 0.007 |
| bootstrap 95 % CI — country cluster | [+0.45, +3.39] |
| bootstrap 95 % CI — circular T blocks | [+0.51, +3.03] |
| **headline CI (wider)** | **[+0.45, +3.39]** — excludes 0 |
| N_eff | 21 |

Per T: 1990: +3.67 (n 5, hit 1.00); 1995: +1.91 (n 5, hit 0.80); 2000: +4.07 (n 5, hit 1.00); 2005: +2.14 (n 5, hit 0.80); 2010: -0.65 (n 5, hit 0.60); 2015: +0.74 (n 5, hit 0.60)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.000 | 0.000 | -0.06 | 0.00 | 5000 |
| N2 | 0.000 | 0.001 | -0.04 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: KOR (+4.8), BWA (+0.7), CHN (+7.4), TWN (+4.0), THA (+1.5)
- 1995: KOR (+2.2), CHN (+5.5), THA (-0.7), TWN (+1.6), CHL (+0.9)
- 2000: BIH (+1.6), CHN (+6.6), MLI (+2.7), LBY (+8.1), KOR (+1.3)
- 2005: BIH (+1.2), ARM (+1.8), LBR (+5.8), MMR (+5.6), LBY (-3.7)
- 2010: AZE (-1.5), AFG (+0.5), LBY (-10.3), MMR (+3.2), CHN (+4.9)
- 2015: CHN (+3.9), LBR (-1.8), MMR (+0.8), DJI (+1.9), AZE (-1.1)

### N4 comparator — prior-10-year growth momentum — k = 5, h = 20, growth

n = 15 lookalike-windows over T ∈ {1990, 1995, 2000} · **N_eff = 9**

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.80 |
| top-quartile rate (chance .25) | 0.53 |
| mean excess μ̂ (pp/yr) vs candidate median | +2.23 (per-T average +2.23) |
| naive SE / p | 0.63 / 0.000 |
| Hansen–Hodrick SE (L = 3) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.89 / 0.013 |
| within-country Bartlett kernel SE (L = 3 grid steps; not the plain cluster SE) / p | 0.81 / 0.006 |
| bootstrap 95 % CI — country cluster | [+0.64, +3.94] |
| bootstrap 95 % CI — circular T blocks | [+2.23, +2.23] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[+0.64, +3.94]** — excludes 0 |
| N_eff | 9 |

Per T: 1990: +2.95 (n 5, hit 0.80); 1995: +1.71 (n 5, hit 0.80); 2000: +2.01 (n 5, hit 0.80)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1 | 0.000 | 0.017 | +0.15 | 0.00 | 5000 |
| N2 | 0.000 | 0.005 | -0.03 | 0.00 | 5000 |

Lookalikes per T (excess growth vs the candidate median, pp/yr):
- 1990: KOR (+3.4), BWA (-0.3), CHN (+7.3), TWN (+2.8), THA (+1.5)
- 1995: KOR (+1.3), CHN (+5.8), THA (-0.3), TWN (+1.2), CHL (+0.6)
- 2000: BIH (+1.8), CHN (+5.7), MLI (+2.6), LBY (-1.1), KOR (+1.1)

### Query B — PRIMARY: min blend distance to the prototype set P(T) — k = 10, h = 10, returns

n = 1 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 1** · status counts: liquidated_in_window 1, no_fund_at_entry 4, no_fund_ever 35 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.00 |
| top-quartile rate (chance .25) | 0.00 |
| mean excess μ̂ (pp/yr) vs VT | -18.46 (per-T average -18.46) |
| naive SE / p | — / — |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | — / — |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | — / — |
| bootstrap 95 % CI — country cluster | [-18.46, -18.46] |
| bootstrap 95 % CI — circular T blocks | [-18.46, -18.46] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-18.46, -18.46]** — degenerate (n < 2 or a single country): no interval, 0 not evaluable |
| N_eff | 1 |

Per T: 2015: -18.46 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 1.000 | 1.000 | -2.04 | 1.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 1.000 | — | -1.51 | Δ = -16.95 CI [-20.48, -12.37] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 1 | -14.64 | — | 0.00 | [-14.64, -14.64] |
| SPY | 1 | -21.07 | — | 0.00 | [-21.07, -21.07] |
| EFA | 1 | -15.25 | — | 0.00 | [-15.25, -15.25] |
| EEM | 1 | -14.86 | — | 0.00 | [-14.86, -14.86] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -18.46 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.00, 2005: 0.00, 2010: 0.00, 2015: 0.10.
Status counts per T: 2000: no_fund_at_entry 2, no_fund_ever 8; 2005: no_fund_at_entry 1, no_fund_ever 9; 2010: no_fund_at_entry 1, no_fund_ever 9; 2015: liquidated_in_window 1, no_fund_ever 9.
NAV-ladder gaps (liquidated funds whose manual ladder does not cover the whole window; the uncovered span is held at 0 % — value carried, never dropped): NGA 2015 NGE [2024-01-31..2024-03-29 (final stub not transcribed)].

Lookalikes per T (excess vs VT, pp/yr):
- 2000: COD (no_fund_ever), GIN (no_fund_ever), SLE (no_fund_ever), AFG (no_fund_ever), ECU (no_fund_ever), MWI (no_fund_ever), IDN (no_fund_at_entry), TUR (no_fund_at_entry), AGO (no_fund_ever), BEN (no_fund_ever)
- 2005: SLE (no_fund_ever), LBR (no_fund_ever), COD (no_fund_ever), SOM (no_fund_ever), AFG (no_fund_ever), NGA (no_fund_at_entry), AGO (no_fund_ever), TCD (no_fund_ever), TZA (no_fund_ever), BOL (no_fund_ever)
- 2010: NGA (no_fund_at_entry), SLE (no_fund_ever), LBR (no_fund_ever), TCD (no_fund_ever), TZA (no_fund_ever), SOM (no_fund_ever), COD (no_fund_ever), AGO (no_fund_ever), ECU (no_fund_ever), MDG (no_fund_ever)
- 2015: NGA (NGE -18.5), AFG (no_fund_ever), COD (no_fund_ever), BOL (no_fund_ever), AGO (no_fund_ever), CMR (no_fund_ever), BEN (no_fund_ever), SOM (no_fund_ever), TCD (no_fund_ever), NER (no_fund_ever)

### Query B — PRIMARY: min blend distance to the prototype set P(T) — k = 5, h = 10, returns

n = 1 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 1** · status counts: liquidated_in_window 1, no_fund_at_entry 1, no_fund_ever 18 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.00 |
| top-quartile rate (chance .25) | 0.00 |
| mean excess μ̂ (pp/yr) vs VT | -18.46 (per-T average -18.46) |
| naive SE / p | — / — |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | — / — |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | — / — |
| bootstrap 95 % CI — country cluster | [-18.46, -18.46] |
| bootstrap 95 % CI — circular T blocks | [-18.46, -18.46] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-18.46, -18.46]** — degenerate (n < 2 or a single country): no interval, 0 not evaluable |
| N_eff | 1 |

Per T: 2015: -18.46 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 1.000 | 1.000 | -2.05 | 1.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 1.000 | — | -1.48 | Δ = -16.98 CI [-20.93, -11.89] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 1 | -14.64 | — | 0.00 | [-14.64, -14.64] |
| SPY | 1 | -21.07 | — | 0.00 | [-21.07, -21.07] |
| EFA | 1 | -15.25 | — | 0.00 | [-15.25, -15.25] |
| EEM | 1 | -14.86 | — | 0.00 | [-14.86, -14.86] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -18.46 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.00, 2005: 0.00, 2010: 0.00, 2015: 0.20.
Status counts per T: 2000: no_fund_ever 5; 2005: no_fund_ever 5; 2010: no_fund_at_entry 1, no_fund_ever 4; 2015: liquidated_in_window 1, no_fund_ever 4.
NAV-ladder gaps (liquidated funds whose manual ladder does not cover the whole window; the uncovered span is held at 0 % — value carried, never dropped): NGA 2015 NGE [2024-01-31..2024-03-29 (final stub not transcribed)].

Lookalikes per T (excess vs VT, pp/yr):
- 2000: COD (no_fund_ever), GIN (no_fund_ever), SLE (no_fund_ever), AFG (no_fund_ever), ECU (no_fund_ever)
- 2005: SLE (no_fund_ever), LBR (no_fund_ever), COD (no_fund_ever), SOM (no_fund_ever), AFG (no_fund_ever)
- 2010: NGA (no_fund_at_entry), SLE (no_fund_ever), LBR (no_fund_ever), TCD (no_fund_ever), TZA (no_fund_ever)
- 2015: NGA (NGE -18.5), AFG (no_fund_ever), COD (no_fund_ever), BOL (no_fund_ever), AGO (no_fund_ever)

### Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P) — k = 10, h = 10, returns

n = 1 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 1** · status counts: liquidated_in_window 1, no_fund_at_entry 3, no_fund_ever 36 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.00 |
| top-quartile rate (chance .25) | 0.00 |
| mean excess μ̂ (pp/yr) vs VT | -18.46 (per-T average -18.46) |
| naive SE / p | — / — |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | — / — |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | — / — |
| bootstrap 95 % CI — country cluster | [-18.46, -18.46] |
| bootstrap 95 % CI — circular T blocks | [-18.46, -18.46] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-18.46, -18.46]** — degenerate (n < 2 or a single country): no interval, 0 not evaluable |
| N_eff | 1 |

Per T: 2015: -18.46 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 1.000 | 1.000 | -2.04 | 1.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 1.000 | — | -1.51 | Δ = -16.95 CI [-20.48, -12.37] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 1 | -14.64 | — | 0.00 | [-14.64, -14.64] |
| SPY | 1 | -21.07 | — | 0.00 | [-21.07, -21.07] |
| EFA | 1 | -15.25 | — | 0.00 | [-15.25, -15.25] |
| EEM | 1 | -14.86 | — | 0.00 | [-14.86, -14.86] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -18.46 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.00, 2005: 0.00, 2010: 0.00, 2015: 0.10.
Status counts per T: 2000: no_fund_at_entry 1, no_fund_ever 9; 2005: no_fund_at_entry 1, no_fund_ever 9; 2010: no_fund_at_entry 1, no_fund_ever 9; 2015: liquidated_in_window 1, no_fund_ever 9.
NAV-ladder gaps (liquidated funds whose manual ladder does not cover the whole window; the uncovered span is held at 0 % — value carried, never dropped): NGA 2015 NGE [2024-01-31..2024-03-29 (final stub not transcribed)].

Lookalikes per T (excess vs VT, pp/yr):
- 2000: SLE (no_fund_ever), GIN (no_fund_ever), COD (no_fund_ever), NGA (no_fund_at_entry), LBR (no_fund_ever), AGO (no_fund_ever), BEN (no_fund_ever), MRT (no_fund_ever), MDG (no_fund_ever), CAF (no_fund_ever)
- 2005: SLE (no_fund_ever), COD (no_fund_ever), LBR (no_fund_ever), AGO (no_fund_ever), BEN (no_fund_ever), NGA (no_fund_at_entry), MDG (no_fund_ever), GIN (no_fund_ever), ETH (no_fund_ever), MRT (no_fund_ever)
- 2010: NGA (no_fund_at_entry), COD (no_fund_ever), LBR (no_fund_ever), SOM (no_fund_ever), SLE (no_fund_ever), BEN (no_fund_ever), AGO (no_fund_ever), TCD (no_fund_ever), MDG (no_fund_ever), TZA (no_fund_ever)
- 2015: NGA (NGE -18.5), BEN (no_fund_ever), COD (no_fund_ever), AGO (no_fund_ever), SOM (no_fund_ever), TCD (no_fund_ever), SEN (no_fund_ever), BFA (no_fund_ever), LBR (no_fund_ever), MLI (no_fund_ever)

### Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P) — k = 5, h = 10, returns

n = 1 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 1** · status counts: liquidated_in_window 1, no_fund_at_entry 2, no_fund_ever 17 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.00 |
| top-quartile rate (chance .25) | 0.00 |
| mean excess μ̂ (pp/yr) vs VT | -18.46 (per-T average -18.46) |
| naive SE / p | — / — |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | — / — |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | — / — |
| bootstrap 95 % CI — country cluster | [-18.46, -18.46] |
| bootstrap 95 % CI — circular T blocks | [-18.46, -18.46] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-18.46, -18.46]** — degenerate (n < 2 or a single country): no interval, 0 not evaluable |
| N_eff | 1 |

Per T: 2015: -18.46 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 1.000 | 1.000 | -2.05 | 1.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 1.000 | — | -1.48 | Δ = -16.98 CI [-20.93, -11.89] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 1 | -14.64 | — | 0.00 | [-14.64, -14.64] |
| SPY | 1 | -21.07 | — | 0.00 | [-21.07, -21.07] |
| EFA | 1 | -15.25 | — | 0.00 | [-15.25, -15.25] |
| EEM | 1 | -14.86 | — | 0.00 | [-14.86, -14.86] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -18.46 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.00, 2005: 0.00, 2010: 0.00, 2015: 0.20.
Status counts per T: 2000: no_fund_at_entry 1, no_fund_ever 4; 2005: no_fund_ever 5; 2010: no_fund_at_entry 1, no_fund_ever 4; 2015: liquidated_in_window 1, no_fund_ever 4.
NAV-ladder gaps (liquidated funds whose manual ladder does not cover the whole window; the uncovered span is held at 0 % — value carried, never dropped): NGA 2015 NGE [2024-01-31..2024-03-29 (final stub not transcribed)].

Lookalikes per T (excess vs VT, pp/yr):
- 2000: SLE (no_fund_ever), GIN (no_fund_ever), COD (no_fund_ever), NGA (no_fund_at_entry), LBR (no_fund_ever)
- 2005: SLE (no_fund_ever), COD (no_fund_ever), LBR (no_fund_ever), AGO (no_fund_ever), BEN (no_fund_ever)
- 2010: NGA (no_fund_at_entry), COD (no_fund_ever), LBR (no_fund_ever), SOM (no_fund_ever), SLE (no_fund_ever)
- 2015: NGA (NGE -18.5), BEN (no_fund_ever), COD (no_fund_ever), AGO (no_fund_ever), SOM (no_fund_ever)

### N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector — k = 10, h = 10, returns

n = 4 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 4** · status counts: investable 3, liquidated_in_window 1, no_fund_at_entry 1, no_fund_ever 35 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.75 |
| top-quartile rate (chance .25) | 0.50 |
| mean excess μ̂ (pp/yr) vs VT | +0.72 (per-T average +0.51) |
| naive SE / p | 6.37 / 0.910 |
| Hansen–Hodrick SE (L = 1) / p | 7.32 / 0.945 |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 5.52 / 0.897 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 5.52 / 0.897 |
| bootstrap 95 % CI — country cluster | [-10.96, +11.76] |
| bootstrap 95 % CI — circular T blocks | [-7.05, +8.49] |
| **headline CI (wider)** | **[-10.96, +11.76]** — includes 0 |
| N_eff | 4 |

Per T: 2000: +15.62 (n 1, hit 1.00); 2005: +1.35 (n 2, hit 1.00); 2015: -15.46 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.000 | 0.000 | -2.04 | 0.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.338 | — | -1.51 | Δ = +2.23 CI [-12.38, +16.22] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 4 | +0.47 | 4.32 | 0.75 | [-7.82, +6.80] |
| SPY | 4 | -0.72 | 7.16 | 0.50 | [-13.47, +12.18] |
| EFA | 3 | -1.85 | 5.24 | 0.67 | [-12.25, +4.55] |
| EEM | 3 | -1.74 | 5.11 | 0.67 | [-11.86, +4.52] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -15.46 pp/yr, same sign as pooled: False.
Investable share per T: 2000: 0.10, 2005: 0.20, 2010: 0.00, 2015: 0.10.
Status counts per T: 2000: investable 1, no_fund_at_entry 1, no_fund_ever 8; 2005: investable 2, no_fund_ever 8; 2010: no_fund_ever 10; 2015: liquidated_in_window 1, no_fund_ever 9.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: BRA (EWZ +15.6), TZA (no_fund_ever), SYR (no_fund_ever), LAO (no_fund_ever), EGY (no_fund_at_entry), HND (no_fund_ever), ZWE (no_fund_ever), SLE (no_fund_ever), AZE (no_fund_ever), LKA (no_fund_ever)
- 2005: NER (no_fund_ever), YEM (no_fund_ever), MEX (EWW +0.1), BEN (no_fund_ever), DOM (no_fund_ever), MYS (EWM +2.6), SEN (no_fund_ever), AGO (no_fund_ever), ZWE (no_fund_ever), LBR (no_fund_ever)
- 2010: GMB (no_fund_ever), AFG (no_fund_ever), LBR (no_fund_ever), SDN (no_fund_ever), COD (no_fund_ever), KHM (no_fund_ever), TGO (no_fund_ever), CMR (no_fund_ever), MRT (no_fund_ever), TZA (no_fund_ever)
- 2015: COD (no_fund_ever), NAM (no_fund_ever), ECU (no_fund_ever), PRY (no_fund_ever), HTI (no_fund_ever), EGY (EGPT -15.5), SLE (no_fund_ever), ETH (no_fund_ever), CMR (no_fund_ever), TZA (no_fund_ever)

### N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector — k = 5, h = 10, returns

n = 2 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 2** · status counts: investable 2, no_fund_at_entry 1, no_fund_ever 17 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 1.00 |
| top-quartile rate (chance .25) | 0.50 |
| mean excess μ̂ (pp/yr) vs VT | +7.89 (per-T average +7.89) |
| naive SE / p | 7.74 / 0.308 |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 5.47 / 0.150 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 5.47 / 0.150 |
| bootstrap 95 % CI — country cluster | [+0.15, +15.62] |
| bootstrap 95 % CI — circular T blocks | [+7.89, +7.89] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[+0.15, +15.62]** — excludes 0 |
| N_eff | 2 |

Per T: 2000: +15.62 (n 1, hit 1.00); 2005: +0.15 (n 1, hit 1.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.000 | 0.000 | -2.05 | 0.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.039 | — | -1.48 | Δ = +9.37 CI [-0.46, +19.09] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 2 | +4.94 | 3.71 | 1.00 | [+1.23, +8.66] |
| SPY | 2 | +7.42 | 9.51 | 0.50 | [-2.08, +16.93] |
| EFA | 1 | +2.14 | — | 1.00 | [+2.14, +2.14] |
| EEM | 1 | +2.11 | — | 1.00 | [+2.11, +2.11] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 0, mean excess vs VT n/a pp/yr, same sign as pooled: False.
Investable share per T: 2000: 0.20, 2005: 0.20, 2010: 0.00, 2015: 0.00.
Status counts per T: 2000: investable 1, no_fund_at_entry 1, no_fund_ever 3; 2005: investable 1, no_fund_ever 4; 2010: no_fund_ever 5; 2015: no_fund_ever 5.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: BRA (EWZ +15.6), TZA (no_fund_ever), SYR (no_fund_ever), LAO (no_fund_ever), EGY (no_fund_at_entry)
- 2005: NER (no_fund_ever), YEM (no_fund_ever), MEX (EWW +0.1), BEN (no_fund_ever), DOM (no_fund_ever)
- 2010: GMB (no_fund_ever), AFG (no_fund_ever), LBR (no_fund_ever), SDN (no_fund_ever), COD (no_fund_ever)
- 2015: COD (no_fund_ever), NAM (no_fund_ever), ECU (no_fund_ever), PRY (no_fund_ever), HTI (no_fund_ever)

### Query A — China 1990 anchor (search.similar, blend) — k = 10, h = 10, returns

n = 7 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 6** · status counts: investable 6, liquidated_in_window 1, no_fund_at_entry 6, no_fund_ever 27 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.29 |
| top-quartile rate (chance .25) | 0.43 |
| mean excess μ̂ (pp/yr) vs VT | -3.96 (per-T average +0.04) |
| naive SE / p | 4.03 / 0.326 |
| Hansen–Hodrick SE (L = 1) / p | 6.19 / 0.995 |
| Newey–West SE L = 2 / p | 5.28 / 0.994 |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 3.49 / 0.256 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 3.62 / 0.273 |
| bootstrap 95 % CI — country cluster | [-10.84, +4.35] |
| bootstrap 95 % CI — circular T blocks | [-9.19, +9.09] |
| **headline CI (wider)** | **[-9.19, +9.09]** — includes 0 |
| N_eff | 6 |

Per T: 2000: +15.62 (n 1, hit 1.00); 2005: +2.55 (n 1, hit 1.00); 2010: -8.10 (n 2, hit 0.00); 2015: -9.91 (n 3, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.999 | 0.909 | -2.04 | 1.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.816 | — | -1.51 | Δ = -2.45 CI [-11.57, +7.42] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 7 | -1.52 | 2.72 | 0.43 | [-4.59, +6.15] |
| SPY | 7 | -6.34 | 4.58 | 0.29 | [-12.33, +8.63] |
| EFA | 6 | -4.06 | 2.66 | 0.33 | [-10.99, -0.59] |
| EEM | 6 | -3.10 | 2.63 | 0.33 | [-10.60, +0.66] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 5, mean excess vs VT -9.19 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.10, 2005: 0.10, 2010: 0.20, 2015: 0.30.
Status counts per T: 2000: investable 1, no_fund_at_entry 3, no_fund_ever 6; 2005: investable 1, no_fund_at_entry 3, no_fund_ever 6; 2010: investable 2, no_fund_ever 8; 2015: investable 2, liquidated_in_window 1, no_fund_ever 7.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: TUR (no_fund_at_entry), IDN (no_fund_at_entry), MMR (no_fund_ever), PAN (no_fund_ever), TUN (no_fund_ever), BRA (EWZ +15.6), LBN (no_fund_ever), COL (no_fund_at_entry), CRI (no_fund_ever), VEN (no_fund_ever)
- 2005: MMR (no_fund_ever), DZA (no_fund_ever), IDN (no_fund_at_entry), PAN (no_fund_ever), MAR (no_fund_ever), MYS (EWM +2.6), PER (no_fund_at_entry), VEN (no_fund_ever), IND (no_fund_at_entry), LBN (no_fund_ever)
- 2010: DZA (no_fund_ever), UZB (no_fund_ever), MAR (no_fund_ever), IND (EPI -6.9), ECU (no_fund_ever), DOM (no_fund_ever), LBY (no_fund_ever), PRY (no_fund_ever), KGZ (no_fund_ever), MYS (EWM -9.3)
- 2015: PRY (no_fund_ever), UZB (no_fund_ever), BOL (no_fund_ever), IND (EPI -1.3), TKM (no_fund_ever), DOM (no_fund_ever), LAO (no_fund_ever), ECU (no_fund_ever), EGY (EGPT -15.5), PHL (EPHE -12.9)

### Query A — China 1990 anchor (search.similar, blend) — k = 5, h = 10, returns

n = 2 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 1** · status counts: investable 2, no_fund_at_entry 3, no_fund_ever 15 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.00 |
| top-quartile rate (chance .25) | 0.50 |
| mean excess μ̂ (pp/yr) vs VT | -4.11 (per-T average -4.11) |
| naive SE / p | 2.79 / 0.140 |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 0.00 / — |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 1.39 / 0.003 |
| bootstrap 95 % CI — country cluster | [-4.11, -4.11] |
| bootstrap 95 % CI — circular T blocks | [-4.11, -4.11] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-4.11, -4.11]** — degenerate (n < 2 or a single country): no interval, 0 not evaluable |
| N_eff | 1 |

Per T: 2010: -6.90 (n 1, hit 0.00); 2015: -1.32 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.973 | 1.000 | -2.05 | 0.97 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.945 | — | -1.48 | Δ = -2.63 CI [-6.56, +2.46] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 2 | +0.68 | 1.82 | 0.50 | [+0.68, +0.68] |
| SPY | 2 | -7.39 | 3.47 | 0.00 | [-7.39, -7.39] |
| EFA | 2 | -0.66 | 2.54 | 0.50 | [-0.66, -0.66] |
| EEM | 2 | +0.70 | 1.58 | 0.50 | [+0.70, +0.70] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 2, mean excess vs VT -4.11 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.00, 2005: 0.00, 2010: 0.20, 2015: 0.20.
Status counts per T: 2000: no_fund_at_entry 2, no_fund_ever 3; 2005: no_fund_at_entry 1, no_fund_ever 4; 2010: investable 1, no_fund_ever 4; 2015: investable 1, no_fund_ever 4.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: TUR (no_fund_at_entry), IDN (no_fund_at_entry), MMR (no_fund_ever), PAN (no_fund_ever), TUN (no_fund_ever)
- 2005: MMR (no_fund_ever), DZA (no_fund_ever), IDN (no_fund_at_entry), PAN (no_fund_ever), MAR (no_fund_ever)
- 2010: DZA (no_fund_ever), UZB (no_fund_ever), MAR (no_fund_ever), IND (EPI -6.9), ECU (no_fund_ever)
- 2015: PRY (no_fund_ever), UZB (no_fund_ever), BOL (no_fund_ever), IND (EPI -1.3), TKM (no_fund_ever)

### Query C — 10-year motion nearest China 1980→1990 (trend metric, informational) — k = 10, h = 10, returns

n = 3 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 3** · status counts: investable 3, no_fund_at_entry 6, no_fund_ever 31 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.67 |
| top-quartile rate (chance .25) | 0.33 |
| mean excess μ̂ (pp/yr) vs VT | +3.36 (per-T average -0.01) |
| naive SE / p | 7.45 / 0.652 |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 6.09 / 0.581 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 6.09 / 0.581 |
| bootstrap 95 % CI — country cluster | [-10.11, +15.62] |
| bootstrap 95 % CI — circular T blocks | [+3.36, +3.36] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-10.11, +15.62]** — includes 0 |
| N_eff | 3 |

Per T: 2000: +10.10 (n 2, hit 1.00); 2010: -10.11 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.000 | 0.000 | -2.04 | 0.00 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.250 | — | -1.51 | Δ = +4.87 CI [-9.20, +17.97] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 3 | +0.64 | 4.05 | 0.33 | [-4.35, +8.66] |
| SPY | 3 | +2.91 | 9.07 | 0.67 | [-14.07, +16.93] |
| EFA | 1 | -6.41 | — | 0.00 | [-6.41, -6.41] |
| EEM | 1 | -4.10 | — | 0.00 | [-4.10, -4.10] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -10.11 pp/yr, same sign as pooled: False.
Investable share per T: 2000: 0.20, 2005: 0.00, 2010: 0.10, 2015: 0.00.
Status counts per T: 2000: investable 2, no_fund_at_entry 4, no_fund_ever 4; 2005: no_fund_at_entry 2, no_fund_ever 8; 2010: investable 1, no_fund_ever 9; 2015: no_fund_ever 10.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: LKA (no_fund_ever), IRL (no_fund_at_entry), PRT (no_fund_ever), ESP (EWP +4.6), IDN (no_fund_at_entry), TUR (no_fund_at_entry), LBY (no_fund_ever), GRC (no_fund_at_entry), KWT (no_fund_ever), BRA (EWZ +15.6)
- 2005: RWA (no_fund_ever), LBY (no_fund_ever), BWA (no_fund_ever), BGD (no_fund_ever), IRL (no_fund_at_entry), KEN (no_fund_ever), ZWE (no_fund_ever), GHA (no_fund_ever), EGY (no_fund_at_entry), TGO (no_fund_ever)
- 2010: DZA (no_fund_ever), ZAF (EZA -10.1), MNG (no_fund_ever), TKM (no_fund_ever), SYR (no_fund_ever), BDI (no_fund_ever), BWA (no_fund_ever), SWZ (no_fund_ever), GAB (no_fund_ever), UZB (no_fund_ever)
- 2015: NAM (no_fund_ever), PSE (no_fund_ever), LAO (no_fund_ever), SLV (no_fund_ever), TKM (no_fund_ever), PRY (no_fund_ever), NIC (no_fund_ever), YEM (no_fund_ever), UZB (no_fund_ever), JOR (no_fund_ever)

### Query C — 10-year motion nearest China 1980→1990 (trend metric, informational) — k = 5, h = 10, returns

n = 2 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 2** · status counts: investable 2, no_fund_at_entry 3, no_fund_ever 15 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.50 |
| top-quartile rate (chance .25) | 0.00 |
| mean excess μ̂ (pp/yr) vs VT | -2.77 (per-T average -2.77) |
| naive SE / p | 7.34 / 0.706 |
| Hansen–Hodrick SE (L = 1) / p | — / — |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 5.19 / 0.593 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 5.19 / 0.593 |
| bootstrap 95 % CI — country cluster | [-10.11, +4.57] |
| bootstrap 95 % CI — circular T blocks | [-2.77, -2.77] — degenerate: block length ≥ number of T's, every resample is the full series; the country-cluster CI is the only informative scheme |
| **headline CI (wider)** | **[-10.11, +4.57]** — includes 0 |
| N_eff | 2 |

Per T: 2000: +4.57 (n 1, hit 1.00); 2010: -10.11 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.751 | 0.048 | -2.05 | 0.75 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.757 | — | -1.48 | Δ = -1.29 CI [-10.72, +7.98] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 2 | -3.37 | 0.97 | 0.00 | [-4.35, -2.40] |
| SPY | 2 | -4.10 | 9.97 | 0.50 | [-14.07, +5.87] |
| EFA | 1 | -6.41 | — | 0.00 | [-6.41, -6.41] |
| EEM | 1 | -4.10 | — | 0.00 | [-4.10, -4.10] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 1, mean excess vs VT -10.11 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.20, 2005: 0.00, 2010: 0.20, 2015: 0.00.
Status counts per T: 2000: investable 1, no_fund_at_entry 2, no_fund_ever 2; 2005: no_fund_at_entry 1, no_fund_ever 4; 2010: investable 1, no_fund_ever 4; 2015: no_fund_ever 5.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: LKA (no_fund_ever), IRL (no_fund_at_entry), PRT (no_fund_ever), ESP (EWP +4.6), IDN (no_fund_at_entry)
- 2005: RWA (no_fund_ever), LBY (no_fund_ever), BWA (no_fund_ever), BGD (no_fund_ever), IRL (no_fund_at_entry)
- 2010: DZA (no_fund_ever), ZAF (EZA -10.1), MNG (no_fund_ever), TKM (no_fund_ever), SYR (no_fund_ever)
- 2015: NAM (no_fund_ever), PSE (no_fund_ever), LAO (no_fund_ever), SLV (no_fund_ever), TKM (no_fund_ever)

### N4 comparator — prior-10-year growth momentum — k = 10, h = 10, returns

n = 7 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 5** · status counts: investable 7, no_fund_at_entry 4, no_fund_ever 29 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.43 |
| top-quartile rate (chance .25) | 0.29 |
| mean excess μ̂ (pp/yr) vs VT | -1.73 (per-T average -1.18) |
| naive SE / p | 3.33 / 0.603 |
| Hansen–Hodrick SE (L = 1) / p | 4.44 / 0.791 |
| Newey–West SE L = 2 / p | 3.66 / 0.748 |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 3.29 / 0.598 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 3.27 / 0.597 |
| bootstrap 95 % CI — country cluster | [-7.35, +8.56] |
| bootstrap 95 % CI — circular T blocks | [-7.99, +6.61] |
| **headline CI (wider)** | **[-7.35, +8.56]** — includes 0 |
| N_eff | 5 |

Per T: 2000: +8.56 (n 2, hit 1.00); 2005: +2.70 (n 1, hit 1.00); 2010: -8.36 (n 2, hit 0.00); 2015: -7.62 (n 2, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.319 | 0.029 | -2.04 | 0.32 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.682 | — | -1.51 | Δ = -0.22 CI [-6.24, +13.94] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 7 | -0.83 | 1.78 | 0.43 | [-4.27, +3.55] |
| SPY | 7 | -3.55 | 4.07 | 0.43 | [-10.10, +9.87] |
| EFA | 5 | -2.69 | 2.04 | 0.20 | [-5.77, -0.63] |
| EEM | 5 | -1.61 | 1.84 | 0.40 | [-4.42, +0.26] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 4, mean excess vs VT -7.99 pp/yr, same sign as pooled: True.
Investable share per T: 2000: 0.20, 2005: 0.10, 2010: 0.20, 2015: 0.20.
Status counts per T: 2000: investable 2, no_fund_at_entry 4, no_fund_ever 4; 2005: investable 1, no_fund_ever 9; 2010: investable 2, no_fund_ever 8; 2015: investable 2, no_fund_ever 8.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: BIH (no_fund_ever), CHN (no_fund_at_entry), MLI (no_fund_ever), LBY (no_fund_ever), KOR (EWY +14.1), IRL (no_fund_at_entry), VNM (no_fund_at_entry), TWN (EWT +3.0), MMR (no_fund_ever), CHL (no_fund_at_entry)
- 2005: BIH (no_fund_ever), ARM (no_fund_ever), LBR (no_fund_ever), MMR (no_fund_ever), LBY (no_fund_ever), AZE (no_fund_ever), GEO (no_fund_ever), CHN (FXI +2.7), LVA (no_fund_ever), IRQ (no_fund_ever)
- 2010: AZE (no_fund_ever), AFG (no_fund_ever), LBY (no_fund_ever), MMR (no_fund_ever), CHN (FXI -5.6), GNQ (no_fund_ever), ARM (no_fund_ever), TCD (no_fund_ever), VNM (VNM -11.1), BLR (no_fund_ever)
- 2015: CHN (FXI -7.9), LBR (no_fund_ever), MMR (no_fund_ever), DJI (no_fund_ever), AZE (no_fund_ever), ETH (no_fund_ever), ZWE (no_fund_ever), VNM (VNM -7.3), AFG (no_fund_ever), BGD (no_fund_ever)

### N4 comparator — prior-10-year growth momentum — k = 5, h = 10, returns

n = 3 lookalike-windows over T ∈ {2000, 2005, 2010, 2015} · **N_eff = 2** · status counts: investable 3, no_fund_at_entry 1, no_fund_ever 16 · benchmark: vt, vt_proxy

| statistic | value |
|---|---|
| hit rate (e > 0; chance .5) | 0.33 |
| top-quartile rate (chance .25) | 0.33 |
| mean excess μ̂ (pp/yr) vs VT | +0.20 (per-T average +0.20) |
| naive SE / p | 6.98 / 0.977 |
| Hansen–Hodrick SE (L = 1) / p | 5.00 / 0.968 |
| Newey–West SE L = 2 / p | — / — |
| Newey–West SE L = 4 / p | — / — |
| country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p | 6.55 / 0.975 |
| within-country Bartlett kernel SE (L = 1 grid step; not the plain cluster SE) / p | 6.14 / 0.974 |
| bootstrap 95 % CI — country cluster | [-6.75, +14.10] |
| bootstrap 95 % CI — circular T blocks | [-7.13, +7.54] |
| **headline CI (wider)** | **[-6.75, +14.10]** — includes 0 |
| N_eff | 2 |

Per T: 2000: +14.10 (n 1, hit 1.00); 2010: -5.60 (n 1, hit 0.00); 2015: -7.90 (n 1, hit 0.00)

| null model | one-sided p (mean excess) | p (hit rate) | null / comparator mean (pp/yr) | share of draws ≥ observed / Δ | B |
|---|---|---|---|---|---|
| N1_investable | 0.012 | 0.609 | -2.05 | 0.01 | 5000 |
| N4_investable (paired bootstrap Δ vs comparator) | 0.399 | — | -1.48 | Δ = +1.68 CI [-6.25, +16.81] | 5000 |

| vs benchmark | n | mean excess (pp/yr) | naive SE | hit rate | headline CI |
|---|---|---|---|---|---|
| EW | 3 | +1.08 | 3.27 | 0.67 | [-1.95, +7.13] |
| SPY | 3 | -1.55 | 8.48 | 0.33 | [-10.03, +15.41] |
| EFA | 2 | -3.29 | 1.39 | 0.00 | [-3.29, -3.29] |
| EEM | 2 | -1.94 | 2.36 | 0.50 | [-1.94, -1.94] |

Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = 2, mean excess vs VT -6.75 pp/yr, same sign as pooled: False.
Investable share per T: 2000: 0.20, 2005: 0.00, 2010: 0.20, 2015: 0.20.
Status counts per T: 2000: investable 1, no_fund_at_entry 1, no_fund_ever 3; 2005: no_fund_ever 5; 2010: investable 1, no_fund_ever 4; 2015: investable 1, no_fund_ever 4.

Lookalikes per T (excess vs VT, pp/yr):
- 2000: BIH (no_fund_ever), CHN (no_fund_at_entry), MLI (no_fund_ever), LBY (no_fund_ever), KOR (EWY +14.1)
- 2005: BIH (no_fund_ever), ARM (no_fund_ever), LBR (no_fund_ever), MMR (no_fund_ever), LBY (no_fund_ever)
- 2010: AZE (no_fund_ever), AFG (no_fund_ever), LBY (no_fund_ever), MMR (no_fund_ever), CHN (FXI -5.6)
- 2015: CHN (FXI -7.9), LBR (no_fund_ever), MMR (no_fund_ever), DJI (no_fund_ever), AZE (no_fund_ever)

## 5. Experiment 2 — shape → growth panel

Sample: n = 7561 country-years, 156 countries, t ∈ [1960, 2013], **N_eff = 871** (distinct (country, floor((t − 1950)/10)) pairs); sources {'pwt': 6792, 'maddison': 769}; |P_train| = 118 (top-decile 10-year windows ending ≤ 2003). Dropped: {'no_window': 0, 'no_level': 0, 'no_dwa': 1142}.

Pooled OLS with SDG-region × decade effects; Driscoll–Kraay (bandwidth 10) primary, two-way (country, year) cluster secondary. Coefficients per unit regressor on g in log points/yr.

| spec | term | β | SE DK | p DK | SE 2-way | p 2-way | R² (in-sample) | n |
|---|---|---|---|---|---|---|---|---|
| S0 | lny | -0.00669 | 0.00164 | 0.000 | 0.00139 | 0.000 | 0.2849 | 7561 |
| S1 | lny | -0.00936 | 0.00252 | 0.000 | 0.00162 | 0.000 | 0.3003 | 7561 |
| S1 | WA | +0.09384 | 0.03603 | 0.009 | 0.03255 | 0.004 | 0.3003 | 7561 |
| S1 | dWA | +0.05142 | 0.03679 | 0.162 | 0.04574 | 0.261 | 0.3003 | 7561 |
| S2 | lny | -0.00591 | 0.00167 | 0.000 | 0.00136 | 0.000 | 0.3110 | 7561 |
| S2 | D | -0.00240 | 0.00023 | 0.000 | 0.00021 | 0.000 | 0.3110 | 7561 |
| S3 | lny | -0.00859 | 0.00258 | 0.001 | 0.00160 | 0.000 | 0.3261 | 7561 |
| S3 | WA | +0.09618 | 0.03615 | 0.008 | 0.03137 | 0.002 | 0.3261 | 7561 |
| S3 | dWA | +0.04127 | 0.03173 | 0.193 | 0.04449 | 0.354 | 0.3261 | 7561 |
| S3 | D | -0.00239 | 0.00021 | 0.000 | 0.00021 | 0.000 | 0.3261 | 7561 |
| S4 | lny | -0.00929 | 0.00235 | 0.000 | 0.00162 | 0.000 | 0.3339 | 7561 |
| S4 | WA | +0.10565 | 0.03287 | 0.001 | 0.03174 | 0.001 | 0.3339 | 7561 |
| S4 | dWA | +0.05787 | 0.03411 | 0.090 | 0.04556 | 0.204 | 0.3339 | 7561 |
| S4 | D | -0.01244 | 0.00366 | 0.001 | 0.00331 | 0.000 | 0.3339 | 7561 |
| S4 | D_feat | +0.00957 | 0.00337 | 0.005 | 0.00313 | 0.002 | 0.3339 | 7561 |

ΔR²(S3 − S1) = 0.0258.

**Prototype self-matching — mandatory note on the in-sample coefficient on D.** `P_train` is drawn from the same country-years that form the regression sample (PREREG §4 fixes it that way, so this is not a deviation — but it makes the in-sample coefficient on D a partial tautology). 88 sample rows are their own nearest prototype (min d = 0, D = ln 1e-09 = -20.72 — an extreme leverage value; 92 % of them are top-decile g by construction, all have t ≤ 1993), and 1234 rows (16.3 %) share their 10-year outcome window with an own-country prototype window (|t − y| < 10; mean g 3.81 vs 1.33 pp/yr for the rest). D quantiles: 0.01: -20.72, 0.05: -2.57, 0.5: -1.55, 0.95: -0.69. 0 self-match rows and 0 own-overlap rows sit in the 2003–2013 test block.

| refit | n | S2 β_D (DK) | S3 β_D (DK) | S3 R² |
|---|---|---|---|---|
| full sample (primary, as pre-registered) | 7561 | -0.00240 (SE 0.00023, p 0.000) | -0.00239 (SE 0.00021, p 0.000) | 0.3261 |
| `ex_selfmatch` — drop the exact self-match rows (the row's (iso3, t) is a prototype; D = ln 1e-9) | 7473 | -0.00774 (SE 0.00298, p 0.010) | -0.00967 (SE 0.00208, p 0.000) | 0.3182 |
| `ex_overlap` — drop every row whose outcome window shares years with an own-country prototype window (|t − y| < 10) | 6327 | +0.00359 (SE 0.00142, p 0.012) | +0.00101 (SE 0.00232, p 0.664) | 0.2958 |
| `floor` — full sample, D floored at the smallest non-zero min-distance instead of 1e-9 (no −20.72 leverage points) | 7561 | -0.00951 (SE 0.00202, p 0.000) | -0.01048 (SE 0.00132, p 0.000) | 0.3362 |

Reading: the pre-registered in-sample sign (P7's first clause, the L1 condition `panel_s3_d_lt_0_dk_p_lt_05`) holds on the full sample and is recorded as such, but it is an artifact of the prototype rows sitting inside their own regression sample — dropping the rows whose outcome overlaps an own-country prototype window removes it. The in-sample coefficient on D is therefore **not evidence** of a shape → growth association; the fixed holdout below, which contains no self-match, is the only evidentiary test here (OOS R² S2 vs S0 -0.0099, S3 vs S1 -0.0021). The `_ex_selfmatch`, `_ex_overlap` and `_floor` rows are in `tables/panel_coefs.csv`.

Fixed holdout: train t ≤ 1993 (n = 4512), test t ∈ [2003, 2013] (n = 1693, 0 rows dropped for a region absent from training). region × decade effects for unseen test decades carried forward from the region's latest training decade.

| spec | OOS R² vs training mean | vs S0 | vs S1 | mean per-t Spearman | share of t with ρ > 0 |
|---|---|---|---|---|---|
| S0 | -0.0317 | +0.0000 | -0.0512 | +0.079 | 0.91 |
| S1 | +0.0186 | +0.0487 | +0.0000 | +0.079 | 1.00 |
| S2 | -0.0419 | -0.0099 | -0.0616 | +0.092 | 1.00 |
| S3 | +0.0165 | +0.0467 | -0.0021 | +0.099 | 1.00 |
| S4 | +0.0252 | +0.0551 | +0.0067 | +0.109 | 1.00 |

Per-t OOS Spearman, S3: 2003: +0.15, 2004: +0.09, 2005: +0.09, 2006: +0.07, 2007: +0.06, 2008: +0.07, 2009: +0.08, 2010: +0.08, 2011: +0.13, 2012: +0.15, 2013: +0.11

Implementation notes: (1) dWA needs t − 10 ≥ 1950, so every specification is estimated on t ≥ 1960 (same sample for all specs). (2) region × decade effects for unseen test decades carried forward from the region's latest training decade. (3) D_feat standardises the 13 numeric features once over the pooled sample rows plus the prototypes. (4) D = ln(max(min d, 1e-09)): PREREG §4 writes ln min d, and a country-year that is itself a prototype has min d = 0, so the clip makes D finite (ln 1e-09 = -20.72); the smallest non-zero min-distance (0.006506, ln = -5.04) is the documented alternative floor, reported as the 'floor' refit. (5) Prototype self-matching (P_train is drawn from the sample's own country-years, as §4 specifies): the in-sample coefficient on D is reported together with three refits (drop exact self-matches; drop rows whose outcome window shares years with an own-country prototype window; smallest-non-zero floor) and is not treated as evidence — only the fixed holdout, which contains no self-match, is.

## 6. Experiment 3 — disconnect table

| iso3 | t | kind | median age | u15 / wa / o65 | s0/s20 | TFR | d_blend to CHN 1990 | y multiples | MSCI facts (cited) | fund vs SPY / EEM / VT |
|---|---|---|---|---|---|---|---|---|---|---|
| CHN | 1990 | history | 24.7 | 0.288 / 0.659 / 0.053 | 0.99 | 2.51 | 0.000 (the anchor itself, pct 0.01) | 10y ×2.44 / 20y ×5.77 / 30y ×9.39 | MSCI China Index: +1.55 %/yr gross since 1992-12-31 (clipped to index history); max DD 88.6 % (net +7.33 %/yr since 2000-12-29); accessed 2026-09-04 | FXI 2004-10-08→2020-12-31 (16.23 y): +8.04 pp/yr log (CAGR +8.38 %), max DD -73 % · VT over the same window +7.39 pp/yr (vt_proxy) · SPY +9.41 · EEM +7.91 |
| KOR | 1975 | history | 19.9 | 0.385 / 0.579 / 0.036 | 1.43 | 3.31 | 0.688 (nearest quarter, pct 0.10) | 10y ×1.76 / 20y ×5.28 / 30y ×7.65 | MSCI Korea Index: +8.74 %/yr gross since 1994-05-31 (clipped to index history); max DD 82.2 % (net +13.61 %/yr since 2000-12-29); accessed 2026-09-04 | EWY 2000-05-12→2005-12-30 (5.63 y): +15.04 pp/yr log (CAGR +16.24 %), max DD -51 % · VT over the same window +1.13 pp/yr (vt_proxy) · SPY -0.85 · EEM — |
| KOR | 1990 | history | 26.7 | 0.258 / 0.693 / 0.049 | 0.75 | 1.60 | 0.380 (nearest 5 %, pct 0.05) | 10y ×1.92 / 20y ×2.84 / 30y ×3.42 | MSCI Korea Index: +8.74 %/yr gross since 1994-05-31 (clipped to index history); max DD 82.2 % (net +13.61 %/yr since 2000-12-29); accessed 2026-09-04 | EWY 2000-05-12→2020-12-31 (20.64 y): +8.25 pp/yr log (CAGR +8.60 %), max DD -74 % · VT over the same window +5.27 pp/yr (vt_proxy) · SPY +6.56 · EEM — |
| JPN | 1960 | history | 25.8 | 0.298 / 0.644 / 0.057 | 0.92 | 1.98 | 0.578 (nearest 5 %, pct 0.02) | 10y ×2.40 / 20y ×3.65 / 30y ×5.07 | MSCI Japan Index: +3.33 %/yr gross since 1994-05-31 (clipped to index history); max DD 62.8 % (net +3.10 %/yr since 1994-05-31); accessed 2026-09-04 | no US-listed single-country fund existed inside the window (EWJ, inception 1996-03-12) |
| TWN | 1970 | history | 18.8 | 0.409 / 0.564 / 0.027 | 1.69 | 3.98 | 0.952 (nearest half, pct 0.35) | 10y ×2.07 / 20y ×3.85 / 30y ×6.45 | MSCI Taiwan Index: +9.35 %/yr gross since 1994-05-31 (clipped to index history); max DD 77.9 % (net +12.11 %/yr since 2000-12-29); accessed 2026-09-04 | EWT 2000-06-23→2000-12-29 (0.52 y — window under 1 y, not annualised): total return -42.87 % over the span (log -55.98 pp), max DD -47 % · VT over the same span -9.02 pp total (vt_proxy) · SPY -9.02 · EEM — (totals, not per year) |
| THA | 1985 | history | 21.9 | 0.341 / 0.623 / 0.035 | 1.03 | 2.45 | 0.509 (nearest 10 %, pct 0.07) | 10y ×2.01 / 20y ×2.38 / 30y ×3.78 | MSCI Thailand Index: +2.29 %/yr gross since 1994-05-31 (clipped to index history); max DD 92.3 % (net +11.21 %/yr since 2000-12-29); accessed 2026-09-04 | THD 2008-04-01→2015-12-31 (7.75 y): +4.31 pp/yr log (CAGR +4.40 %), max DD -64 % · VT over the same window +3.21 pp/yr (vt_proxy) · SPY +7.28 · EEM -2.67 |
| VNM | 2000 | history | 23.7 | 0.315 / 0.625 / 0.060 | 0.92 | 2.03 | 0.476 (nearest quarter, pct 0.10) | 10y ×2.49 / 20y ×4.59 (→ 2023: ×5.12, clipped) | MSCI Vietnam Index: +2.70 %/yr gross since 2006-11-30 (clipped to index history); max DD 78.4 % (net +2.70 %/yr since 2006-11-30); accessed 2026-09-04 | VNM 2009-08-14→2025-12-31 (16.38 y): -0.26 pp/yr log (CAGR -0.26 %), max DD -63 % · VT over the same window +10.04 pp/yr (vt) · SPY +13.49 · EEM +4.74 |
| IND | 2005 | history | 23.3 | 0.336 / 0.618 / 0.047 | 1.25 | 2.96 | 0.376 (nearest 10 %, pct 0.06) | 10y ×1.88 (→ 2023: ×2.76, clipped) | MSCI India Index: +7.64 %/yr gross since 1994-05-31; max DD 72.6 % (net +10.05 %/yr since 2000-12-29); accessed 2026-09-04 | EPI 2008-02-26→2025-12-31 (17.85 y): +4.31 pp/yr log (CAGR +4.41 %), max DD -66 % · VT over the same window +7.59 pp/yr (vt_proxy) · SPY +10.81 · EEM +2.81 |
| PHL | 2024 | now | 26.8 | 0.279 / 0.666 / 0.055 | 0.85 | 1.89 | 0.455 (nearest 10 %, pct 0.09) | no level at 2024 (level series ends 2023) | no MSCI figure transcribed | EPHE 2024-12-31→2025-12-31 (1.0 y): +1.55 pp/yr log (CAGR +1.56 %), max DD -16 % · VT over the same window +20.25 pp/yr (vt) · SPY +16.32 · EEM +29.27 |
| BGD | 2024 | now | 26.7 | 0.280 / 0.655 / 0.065 | 1.04 | 2.14 | 0.457 (nearest 10 %, pct 0.10) | no level at 2024 (level series ends 2023) | no MSCI figure transcribed | no US-listed single-country fund |
| NPL | 2024 | now | 26.0 | 0.284 / 0.651 / 0.065 | 0.95 | 1.96 | 0.547 (nearest quarter, pct 0.14) | no level at 2024 (level series ends 2023) | no MSCI figure transcribed | no US-listed single-country fund |
| LAO | 2024 | now | 25.6 | 0.302 / 0.651 / 0.047 | 1.11 | 2.40 | 0.300 (nearest 5 %, pct 0.01) | no level at 2024 (level series ends 2023) | no MSCI figure transcribed | no US-listed single-country fund |
| KHM | 2024 | now | 27.0 | 0.298 / 0.640 / 0.062 | 1.29 | 2.55 | 0.515 (nearest quarter, pct 0.11) | no level at 2024 (level series ends 2023) | no MSCI figure transcribed | no US-listed single-country fund |

MSCI figures are hand-transcribed facts from `msci_citations.yaml` (factsheets as of 2026-08-31, accessed 2026-09-04); no index series was downloaded. Fund statistics come from daily adjusted closes over the window shown, clipped to the fund's history and the last complete calendar year. Fund windows under 1 full year are shown as raw total returns over the span (never annualised; the row is kept).

## 7. Vintage statement (PREREG §8)

**Vintage statement (PREREG §8).** The pyramids used to select lookalikes as of T are WPP 2024 back-series, i.e. today's estimates of what the age structure *was* — not what was known at T. The selection is therefore hindsight-free with respect to the **outcome** (prototype windows end ≤ T; growth and returns are observed after T) but not with respect to the **demographic input**. The optional `--vintage` re-run (WPP 2010 / WPP 2000 archive files as the input for T ≤ 2010 / T ≤ 2000, pre-registered check: k = 10 Jaccard overlap ≥ 0.6 at every T where an archive exists) was not performed in this run: the WPP 2010 / WPP 2000 archive files were not obtained, so this paragraph stands as the caveat.

**Growth-data vintage (additional disclosure, same logic as the demographic caveat).** The GDP-per-capita series behind the prototype sets P(T), the N4 momentum ranking and the N2 income match are PWT 11.0 / Maddison 2023 revised back-series, i.e. today's estimates of past growth, not the national-accounts data available at T; PPP benchmark revisions (ICP 2011, 2017, 2021) have moved levels and growth rates of exactly the low-income countries this backtest selects. **Publication lag.** Every quantity conditioned 'as of T' uses y_T, the GDP of calendar year T, which is not published on the entry date (the last trading day of T): the prototype rule takes windows ending ≤ T (y + 10 ≤ T), N4 ranks on g_{c,T−10,10} and N2 matches on ln y_T, so all three see roughly one year of data a real-time selector would not have had. N4's growth result (+1.57 pp/yr vs the candidate median, p_N1 0.000, k = 10, h = 10) is the row most exposed to this; Query B's prototype membership and N2's caliper matches are exposed at the margin (a window ending in T could move in or out of the top decile). The return rows are unaffected in their outcome (prices are known at T) but inherit the selection's look-ahead.

## 8. Decision levels (PREREG §7)

- **L0 — what happened next: GRANTED.** Always allowed.
- **L1 — growth association: not granted.** Failed conditions: mu_eg_gt_0, ci_headline_excludes_0, p_n1_lt_05, p_n2_lt_05.
- **L2 — returns signal: not granted.** Failed conditions: mu_er_vs_vt_gt_0, ci_er_headline_excludes_0, hh_p_lt_05, nw_p_lt_05, mu_er_vs_ew_gt_0, beats_n1_investable_p_lt_05, beats_n4_p_lt_05, n_eff_returns_ge_20. Unavailable inputs: hh_p_lt_05, nw_p_lt_05. _pre-registered expectation NOT met; the UI may never predict returns. L2 requires beating VT._

| condition | observed | holds | read from |
|---|---|---|---|
| mu_eg_gt_0 | -0.190 | no | B|10|10|growth.stats.mean_excess (pp/yr) |
| ci_headline_excludes_0 | [-1.47, +1.20] | no | B|10|10|growth.stats.ci_headline |
| p_n1_lt_05 | 0.650 | no | B|10|10|growth.nulls.N1.p_mean_excess |
| p_n2_lt_05 | 0.983 | no | B|10|10|growth.nulls.N2.p_mean_excess |
| n_eff_ge_20 | 43.000 | yes | B|10|10|growth.stats.n_eff |
| panel_s3_d_lt_0_dk_p_lt_05 | beta = -0.002, p_dk = 0.000 | yes | panel.specs.S3.coef.D (in-sample, full sample as pre-registered; contaminated by prototype self-matching — RESULTS §5 note) |
| oos_r2_s3_gt_s0 | S3 = 0.016, S0 = -0.032 | yes | panel.holdout.oos_r2.{S3,S0}.vs_mean |
| p2_met | 0.068 | yes | n3.10|10.delta (pp/yr) |
| mu_er_vs_vt_gt_0 | -18.463 | no | B|10|10|returns.stats.mean_excess (vs VT, pp/yr) |
| ci_er_headline_excludes_0 | [-18.46, -18.46] | no | B|10|10|returns.stats.ci_headline |
| hh_p_lt_05 | n/a | n/a | B|10|10|returns.stats.hh_p |
| nw_p_lt_05 | L2 = n/a, L4 = n/a | n/a | B|10|10|returns.stats.nw2_p and nw4_p |
| mu_er_vs_ew_gt_0 | -14.641 | no | B|10|10|returns.vs.ew.mean_excess |
| beats_n1_investable_p_lt_05 | 1.000 | no | B|10|10|returns.nulls.N1_investable.p_mean_excess |
| beats_n4_p_lt_05 | 1.000 | no | B|10|10|returns.nulls.N4_investable.p_one_sided (paired bootstrap) |
| n_eff_returns_ge_20 | 1.000 | no | B|10|10|returns.stats.n_eff |
| oos_block_same_sign | -18.463 | yes | B|10|10|returns.oos_block_T_ge_2010 |

Allowed sentence ids: L0.disconnect, L0.investability, L0.null, L0.vs_vt, L0.what_happened. Deny-list violations in rendered sentences / templates: 0.

Units in the rendered sentences: every `%/yr` market figure (`L0.vs_vt`) is a compound annual growth rate, 100·(e^r − 1), while the tables in §4 and §6 carry annualised log returns in pp/yr (r = ln(exit/entry)/years) — e.g. NGE 2015–2025 -7.34 pp/yr log is -7.08 %/yr CAGR and VT +11.12 pp/yr log is +11.76 %/yr. In `L0.what_happened` N_eff is that T's own support (the distinct countries at T, = n); the pooled N_eff stands on the §4 row, and the T = 2015 sentence names the span actually observed (8 years for PWT rows, 7 for the Maddison fallback).

Rendered sentences (the only econ text the UI may show):

- `L0.what_happened`: Among the 10 countries whose pyramid in 1990 most resembled the pre-boom prototypes, GDP per capita grew -0.5 %/yr over the following 10 years, against +1.6 %/yr for the median of all 148 candidates (N_eff = 10; 40% of them beat the median).
- `L0.what_happened`: Among the 10 countries whose pyramid in 1995 most resembled the pre-boom prototypes, GDP per capita grew +2.1 %/yr over the following 10 years, against +2.6 %/yr for the median of all 150 candidates (N_eff = 10; 40% of them beat the median).
- `L0.what_happened`: Among the 10 countries whose pyramid in 2000 most resembled the pre-boom prototypes, GDP per capita grew +3.6 %/yr over the following 10 years, against +2.8 %/yr for the median of all 151 candidates (N_eff = 10; 40% of them beat the median).
- `L0.what_happened`: Among the 10 countries whose pyramid in 2005 most resembled the pre-boom prototypes, GDP per capita grew +4.4 %/yr over the following 10 years, against +2.5 %/yr for the median of all 152 candidates (N_eff = 10; 90% of them beat the median).
- `L0.what_happened`: Among the 10 countries whose pyramid in 2010 most resembled the pre-boom prototypes, GDP per capita grew +1.6 %/yr over the following 10 years, against +1.2 %/yr for the median of all 156 candidates (N_eff = 10; 50% of them beat the median).
- `L0.what_happened`: Among the 10 countries whose pyramid in 2015 most resembled the pre-boom prototypes, GDP per capita grew -0.3 %/yr over the following 7–8 years, against +1.4 %/yr for the median of all 157 candidates (N_eff = 10; 30% of them beat the median).
- `L0.null`: Random sets of 10 countries did at least as well in 65% of 5000 draws (p = 0.65); sets of equally poor countries did at least as well in 98% of draws (p = 0.98).
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund existed in 2000.
- `L0.investability`: No US-listed single-country fund existed in 2000.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: No US-listed single-country fund exists for this country.
- `L0.investability`: … 28 more
- `L0.vs_vt`: NGE total return 2015–2025: -7.1 %/yr · VT over the same window: +11.8 %/yr.
- `L0.disconnect`: China 1990: GDP per capita 9.4× in 30 years; the MSCI China index returned +1.6 %/yr (USD) since 1992-12-31, with a maximum drawdown of 89 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: South Korea 1975: GDP per capita 7.6× in 30 years; the MSCI Korea index returned +8.7 %/yr (USD) since 1994-05-31, with a maximum drawdown of 82 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: South Korea 1990: GDP per capita 3.4× in 30 years; the MSCI Korea index returned +8.7 %/yr (USD) since 1994-05-31, with a maximum drawdown of 82 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: Japan 1960: GDP per capita 5.1× in 30 years; the MSCI Japan index returned +3.3 %/yr (USD) since 1994-05-31, with a maximum drawdown of 63 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: Taiwan 1970: GDP per capita 6.5× in 30 years; the MSCI Taiwan index returned +9.3 %/yr (USD) since 1994-05-31, with a maximum drawdown of 78 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: Thailand 1985: GDP per capita 3.8× in 30 years; the MSCI Thailand index returned +2.3 %/yr (USD) since 1994-05-31, with a maximum drawdown of 92 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: Vietnam 2000: GDP per capita 5.1× in 23 years; the MSCI Vietnam index returned +2.7 %/yr (USD) since 2006-11-30, with a maximum drawdown of 78 % (MSCI factsheet, accessed 2026-09-04).
- `L0.disconnect`: India 2005: GDP per capita 2.8× in 18 years; the MSCI India index returned +7.6 %/yr (USD) since 1994-05-31, with a maximum drawdown of 73 % (MSCI factsheet, accessed 2026-09-04).

## 9. Implementation notes (pre-specified gaps filled before looking at results; not deviations)

- Prototype top decile is taken over windows with pop ≥ 1 M ending ≤ T (the same set the prototypes are drawn from).
- The N4 comparator's p-value is a paired block bootstrap of μ̂(lookalikes) − μ̂(N4) on the same resamples (both schemes; the larger p is reported) — PREREG names the comparison but not the test.
- Kernel SEs (Hansen–Hodrick, Newey–West) are reported as n/a when the T-aggregated series has no more points than lags + 1 (h = 20 rows have three T's).
- N2 is computed for growth outcomes; return outcomes use N1-investable and N4-investable as pre-registered.
- The T = 2015 partial growth window (h = 8 / 7) is pooled into the h = 10 rows and flagged; n_partial is printed on every row.
- PREREG §3.6 item 6 ('country-cluster HAC SE, cluster = country across T') is reported as the plain one-way country-cluster SE (every within-country pair weight 1, 'country-cluster SE'); the within-country Bartlett-kernel variant truncated at L = h/5 − 1 grid steps (same-country pairs ≥ 2 steps apart get weight 0) is printed beside it under its own label. Neither is the headline.
- For h = 20 rows the circular T-block bootstrap is degenerate by construction (three T's, block length 4 ≥ n_T: every resample is the full series), so its 'interval' is a point; such cells are flagged, and the country-cluster CI — the wider one — is the headline.
- The 36 statistic rows (24 growth + 12 returns, every query × k × h × outcome) are reported without a multiple-comparison adjustment; only Query B k = 10 h = 10 is confirmatory (P1, P3 and the decision rules read it), every other row is secondary or informational.
- dWA needs t − 10 ≥ 1950, so every specification is estimated on t ≥ 1960 (same sample for all specs)
- region × decade effects for unseen test decades carried forward from the region's latest training decade
- D_feat standardises the 13 numeric features once over the pooled sample rows plus the prototypes
- D = ln(max(min d, 1e-09)): PREREG §4 writes ln min d, and a country-year that is itself a prototype has min d = 0, so the clip makes D finite (ln 1e-09 = -20.72); the smallest non-zero min-distance (0.006506, ln = -5.04) is the documented alternative floor, reported as the 'floor' refit
- Prototype self-matching (P_train is drawn from the sample's own country-years, as §4 specifies): the in-sample coefficient on D is reported together with three refits (drop exact self-matches; drop rows whose outcome window shares years with an own-country prototype window; smallest-non-zero floor) and is not treated as evidence — only the fixed holdout, which contains no self-match, is
- Disconnect fund windows under 1 full year (window_years rounded to two decimals < 1.00; a fund whose history starts inside the row's last calendar year, e.g. EWT for TWN 1970: 2000-06-23 → 2000-12-29, 0.52 y) are flagged too_short_to_annualise and shown as the raw total return over the span; the annualised figure stays in disconnect.json but is never printed as pp/yr. The row is never dropped.

## 10. Deviations from PREREG

- Disconnect table (PREREG §5): the VT proxy of §3.5 is pre-registered only for the T = 2000 and T = 2005 windows; the fund windows CHN 1990 (FXI 2004-10-08→2020-12-31: 2000 rule); KOR 1975 (EWY 2000-05-12→2005-12-30: 2000 rule); KOR 1990 (EWY 2000-05-12→2020-12-31: 2000 rule); TWN 1970 (EWT 2000-06-23→2000-12-29: 2000 rule); THA 1985 (THD 2008-04-01→2015-12-31: 2005 rule); IND 2005 (EPI 2008-02-26→2025-12-31: 2005 rule) begin before VT's first bar (2008-06-26) on other dates, so vt_benchmark applied the nearest pre-registered weights (2000 rule for entries before 2005, else the 2005 rule) until VT's first bar — an extension of §3.5, flagged vt_proxy on every such number.
- Survivorship guard (PREREG §6, assertion 4): Yahoo's daily range=max endpoint served a full multi-year history for 4 delisted ticker(s) (EGPT, FM, NGE, PAK) instead of refusing (the one-bar / no-data signature seen with the monthly interval during curation). PREREG says any assertion failure stops the build; the recorded run was `make backtest DEAD_SERIES=ok` (i.e. `scripts/fetch_etf.py --dead-series ok`), which records the failure per ticker below, DISCARDS every dead series and takes those funds' returns only from etf_manual.yaml — no number in this file uses a served dead series. The Makefile default is `DEAD_SERIES ?= fail`, the strict pre-registered stop (exit 1 after 4 A4 failures), so plain `make backtest` refuses and the deviation has to be chosen explicitly on every run.
- EGPT: Yahoo served 3558 daily bars (2010-02-16 → 2024-04-04) for delisted EGPT (yaml last trading day 2024-03-21); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. (guard report)
- FM: Yahoo served 3100 daily bars (2012-09-12 → 2025-01-08) for delisted FM (yaml last trading day 2025-01-06); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. (guard report)
- NGE: Yahoo served 2768 daily bars (2013-04-02 → 2024-03-28) for delisted NGE (yaml last trading day 2023-07-28); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. (guard report)
- PAK: Yahoo served 2233 daily bars (2015-04-22 → 2024-03-05) for delisted PAK (yaml last trading day 2024-02-16); PREREG §6 A4 asserted a refusal. Series discarded; returns from etf_manual.yaml. (guard report)
- etf_manual.yaml: NGE delisting date: etf_universe.yaml (frozen) says 2023-07-28; 497 supplements dated 2023-07-14 / 2023-08-07 / 2023-09-19 / 2024-03-01 moved the closing date to 2024-03-25 (liquidation ~2024-03-29), so NGE 2023 is a full calendar year (-27.27 %) and the window arithmetic uses 2024-03-25. Yahoo's stale bar dated 2024-03-25 was the real last trade; the PREREG §6 remark about a bar 'eight months after the real last trade' was wrong about the date, not about the routing.
- etf_manual.yaml: ERUS / RSX liquidating distributions: the universe knows only ERUS 2022-08-17 and the three RSX 2024 dates; four more ERUS distributions (2023-12-27, 2024-06-17, 2024-11-06, 2024-12-20; $4.098728/share in total incl. 2022) and RSX $0.0119 declared 2025-12-22 (held at DTCC pending an OFAC licence) were transcribed. Issuer 'total return' figures after the trading halts assume reinvestment at a residual NAV of cents (RSX 2023 +296.65 %, 2024 +421.94 %) and are flagged reinvestment_artifact — the window arithmetic uses the cash_ladder (NAV at the last regular year-end, then distributions as 0 % cash plus residual NAV) instead of compounding them.
- etf_manual.yaml: Sources beyond N-CSR + liquidation notice (PREREG §6 names those two): PAK 2023 (+27.914 %) and ERUS 2022 (-99.844 %) and 2025 (+4.615 %) are twelve N-PORT Item B.5.a monthly returns compounded; NGE / PAK / FM / ERUS calendar years come from 485BPOS prospectus bar charts (iXBRL rr:AnnualReturnYYYY); EGPT and RSX from N-CSR financial highlights.
- etf_manual.yaml: Not available from any issuer source: FM 2024 (December N-PORT never filed; 2024 null → the 2024-01-01..2025-01-09 span is a ladder gap), the NGE (2024-03-29) and PAK (2024-02-23) cash-out NAVs per share (final stubs after 2024-01-31 are ladder gaps), and an ERUS 2021-12-31 NAV (so the ERUS cash ladder cannot be expressed in return space after 2022; the 2022 -99.844 % mark is applied and the post-halt span is a ladder gap). Ladder gaps are held at 0 % and reported, never dropped.
- Manual NAV ladder (PREREG §6): the ladder does not cover every day of some windows — ERUS T = 2015: 2022-12-31..2025-12-31 (post-halt cash distributions: reference NAV not transcribed); FM T = 2015: 2024-11-30..2024-12-31 (calendar year not transcribed); 2025-01-01..2025-01-09 (final stub not transcribed); NGE T = 2015: 2024-01-31..2024-03-29 (final stub not transcribed); PAK T = 2015: 2024-01-31..2024-02-23 (final stub not transcribed). Each uncovered span is held at 0 % nominal and the row is carried with status liquidated_in_window (Experiment 1) / manual_incomplete (etf_returns.csv) — never dropped, never silently completed.
- ERUS T = 2015 ladder gap, quantified: the row carries the 2022 N-PORT mark (-99.844 %) with the post-halt span at 0 %, i.e. 0.39 % of the start value (-55.40 pp/yr log); against the transcriber's implied but UNSOURCED 2021-12-31 NAV of $46.00 the cash actually paid ($4.098728) plus the residual NAV ($0.0352) is 9.0 % of that NAV, i.e. 22.60 % of the start value (-14.87 pp/yr log) — the mark understates recovery by 22.2 pp of start value; the T = 2015 equal-weight basket (n = 48) would move from +7.300 to +7.322 pp/yr (+0.022 pp/yr, < 0.05 pp/yr). The implied NAV enters no statistic; sourcing a `nav_2021_12_31` would put ERUS on the same cash-ladder arithmetic as RSX.
