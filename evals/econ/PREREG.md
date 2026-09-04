# Economic-lens backtest — pre-registered protocol (PREREG)

**Project:** population-pyramid-explorer · **Written:** 2026-09-04 · **Status:** FROZEN on commit.
**Authoritative source:** `~/.claude/plans/moonlit-wandering-cocoa.md` §6 (protocol) and §2 decisions 7, 8, 10; `docs/PLAN.md` DECISIONS 10.
**Companion files committed together with this one:** `evals/econ/etf_universe.yaml`, `evals/econ/ui_sentences.yaml`, `evals/econ/msci_citations.yaml`, `evals/econ/etf_crosscheck.yaml`, `evals/econ/NOTICE`.

## 0. Immutability

1. This file is committed **before** `scripts/fetch_econ.py`, `scripts/fetch_etf.py` or any backtest script is run for the first time. `make backtest` refuses to run unless `evals/econ/PREREG.md` is committed (Makefile target `backtest`; test `test_prereg_hash`).
2. **Nothing in this file changes after the ETF fetch.** Every number, rule, threshold, weight, date and prediction below is fixed now. If the implementation must deviate (a data source is unavailable, a bug), the deviation is listed in a "Deviations from PREREG" section of `evals/econ/RESULTS.md`; this file is not edited.
3. `evals/econ/RESULTS.md` cites this file's commit hash: `git log -1 --format=%H -- evals/econ/PREREG.md`, and `decision.json` carries the same hash in `prereg_commit`. A test (`tests/test_econ_*.py::test_prereg_hash`) fails if the hash recorded in `RESULTS.md`/`decision.json` does not match the file's last commit.
4. Pre-specified defaults that the plan left implicit are marked **[PSD]** ("pre-specified default") below. They are fixed here, before any fetch, precisely so that they cannot be chosen after seeing results.

## 1. What is being tested

Eli's question, stated as testable claims: *"Countries whose population pyramid today looks like China's in 1990 (or, more generally, like the pyramids that preceded the fastest growth spells on record) went on to grow faster — and their equity markets went on to beat a passive global portfolio ("VT and chill")."* Two outcomes (real GDP-per-capita growth; USD ETF total returns), one lookalike rule fixed as of each T, one headline benchmark (VT), pre-registered predictions, and decision rules that map results to the only sentences the UI is allowed to show.

Placement: `src/pyramid_explorer/econ/{data,etf,stats,lookalike,panel,disconnect,decide}.py`; `scripts/{fetch_econ,fetch_etf,backtest_lookalikes,panel_shape_growth,disconnect_table,decide_econ}.py`; outputs in `evals/econ/`. Zero new dependencies (HAC and bootstrap in numpy; statsmodels optional cross-check only). Order: commit this file + companions → `fetch_econ` → `fetch_etf` → backtests → `decide` → `RESULTS.md`. Blocking for any econ text in the M3 About page and for M5.

## 2. Data definitions

### 2.1 Growth series `y` (real GDP per capita)

- **Primary:** PWT 11.0, `y = rgdpna / pop` (file `pwt110.xlsx`, sheet `Data`, columns `countrycode, year, rgdpna, rgdpe, pop`; `rgdpna` = real GDP at constant 2021 national prices, millions; `pop` = population, millions). Licence CC BY 4.0.
- **Fallback:** Maddison Project Database 2023, `gdppc` (dataverse file 421302, sheet `Full data`, columns `countrycode, year, gdppc, pop`; 2011 international dollars). Used for a country only when PWT does not provide **both** endpoints of a window.
- **Never mixed within a window:** `y_T` and `y_{T+h}` for one (c, T, h) come from the same source. If PWT has both endpoints, PWT is used; else if Maddison has both, Maddison is used; else the window is missing and the country is not a candidate for that (T, h). The source is recorded per row (`y_source ∈ {pwt, maddison}`).
- **Level series** (for income matching, the panel's `ln y`, and the disconnect table): PWT `rgdpe / pop` (expenditure-side, current PPPs) where available, else Maddison `gdppc`. Level and growth may come from different sources for the same country (the level is only used as a covariate / matching variable, never inside a growth window).
- **Cross-check only (never a primary input):** World Bank WDI (API v2, no key) `NY.GDP.PCAP.PP.KD`, `SP.POP.1564.TO.ZS`, `NY.GDP.TOTL.RT.ZS` for 1990+ agreement checks and as the only source for Kosovo (XKX). IMF WEO 2025-04 is used at build time solely as a tail check (last observed year sanity); it is never exported and never enters a window.
- **Growth:** `g_{c,t,h} = (1/h) · ln( y_{t+h} / y_t )`, `h ∈ {10, 20}`, in log points per year (reported in pp/yr = ×100).
- **ISO3 handling:** WEO `UVK → XKX`, `WBG → drop`; Maddison drop `{CSK, SUN, YUG}` and assert every remaining code against a fixed allowlist (`pipeline/econ_iso3.yaml`); PWT needs no remap (185 codes, all in WPP; TWN present in PWT and WEO). All joins go through `shapes.row_index((iso3, year))`.
- **Population** for the ≥ 1 M floor: WPP 2024 medium-variant total population of the country in year T (the same quantity `search.Query.minpop` uses, in thousands: `minpop=1000`). **[PSD]**
- **Last observed year:** PWT 11.0 ends 2023; Maddison 2023 ends 2022. **[PSD]** For T = 2015 the growth window therefore ends at 2023 (PWT, h = 8) or 2022 (Maddison fallback, h = 7); both are flagged `partial=true` and the actual span is used in the `1/h` normalisation.

### 2.2 Pyramid shapes

`s42_{c,t}` = the two-sex 42-vector of age-sex shares from the M0 corpus (WPP 2024, medium variant, Togo patch applied), distance `d_blend` = the corpus default metric (½·L2/σ + ½·per-sex W1/σ, σ from `sigma.json`), exactly as `search.similar` uses it. Three-band vector for N3: `(u15, wa, o65)` shares (0–14, 15–64, 65+), z-scored on the T cross-section, Euclidean distance. **[PSD]**

### 2.3 Committed derived tables

`evals/econ/tables/gdp_pc.parquet` (iso3, year, y_growth_source, y_level_source, y_growth, y_level), `evals/econ/tables/windows.parquet` (iso3, T, h, g, source, partial), `evals/econ/tables/etf_returns.csv` (derived statistics only — never prices), `evals/econ/NOTICE` (attribution).

## 3. Experiment 1 — lookalike-as-of-T

### 3.1 T grid and horizons

| T | growth h = 10 | growth h = 20 | returns h = 10 |
|---|---|---|---|
| 1990 | yes (1990→2000) | yes (1990→2010) | no — no US-listed single-country ETF existed at entry (first WEBS 1996-03) |
| 1995 | yes (1995→2005) | yes (1995→2015) | no — same statement |
| 2000 | yes (2000→2010) | yes (2000→2020) | yes (entry 2000-12-29, exit last trading day of 2010) — benchmark = VT proxy |
| 2005 | yes (2005→2015) | no | yes (entry last trading day of 2005, exit last trading day of 2015) — benchmark = VT proxy until 2008-06-24, then VT |
| 2010 | yes (2010→2020) | no | yes (entry last trading day of 2010, exit last trading day of 2020) — benchmark = VT |
| 2015 | partial: h = 8 (2015→2023; Maddison fallback h = 7), flagged `partial` | no | yes (entry last trading day of 2015, exit last trading day of 2025) — benchmark = VT |

"No ETF existed" rows are reported as status counts only; closed-end funds, ADRs and non-US listings are out of scope by pre-registration and are never substituted.

### 3.2 Candidates `C(T)`

Countries only (scope `c`, no aggregates), WPP population at T ≥ 1 M, with `y_T` and `y_{T+h}` available from a single source (§2.1). The query country itself (CHN for Query A) is excluded from its own candidate set. Every candidate set is written to `tables/backtest_picks.csv` with a `role` column (pick / candidate / prototype).

### 3.3 Lookalike rules

- **Query A — "China 1990 lookalikes" (Eli's question as stated):** `search.similar(Query(id='CHN', year=1990, mode='range', from_year=T, to_year=T, k=k, scope='c', minpop=1000, metric='blend'))`, candidates restricted to `C(T)` (i.e. the search result is post-filtered to countries with growth data; k nearest **after** the filter). Informational/secondary: it is a single-anchor query and inherits hindsight (we know China grew).
- **Query B — PRIMARY, hindsight-free prototype set.** For each T build `P(T)` = the set of (country c, year y) with `y ≤ T − 10`, WPP pop at y ≥ 1 M, and `g_{c,y,10}` in the **top decile** of all 10-year windows ending ≤ T (i.e. `y + 10 ≤ T`, so every prototype's outcome was fully observed at T). Deduplicate to at most **3 windows per country**, at least **5 years apart**, keeping the highest-growth windows first **[PSD]**. Distance of a candidate `x = s42_{c,T}` to the prototype set: `D_P(x) = min_{p ∈ P(T)} d_blend(x, s42_p)`. Robustness row: soft-min `D_P^τ(x) = −τ · ln Σ_p exp(−d_blend(x, p)/τ)` with `τ = 0.25 · median_{x ∈ C(T)} D_P(x)` **[PSD]**. `L(T)` = the k candidates with the smallest `D_P` (ties broken by the second-smallest prototype distance **[PSD]**).
- **Query C — trend/motion version (informational):** the candidates in `C(T)` whose 10-year motion `Δ_c = s42(c,T) − s42(c,T−10)` is nearest (metric `trend`, `L=10`, `d_trend = ‖Δ_q − Δ_c‖₂ / σ_Δ,10`) to China's 1980→1990 motion, as of T.
- **k:** k = 10 primary; k = 5 secondary. Both are always reported; the predictions and decision rules refer to k = 10.

### 3.4 Outcomes

- **Growth:** `g_{c,T,h}` per §2.1. Excess `eg_{c,T,h} = g_{c,T,h} − median_{C(T)} g_{·,T,h}`.
- **Returns:** `r_{c,T,h} = ln( adjclose_exit / adjclose_entry )`, in USD, from the daily adjusted close of the country's ETF in `etf_universe.yaml` (adjusted close = total return with distributions reinvested, as Yahoo computes it). Entry = the ETF's adjusted close on the **last trading day of calendar year T** (NYSE calendar; if the ETF has no bar that day, the last bar on or before it, ≤ 5 trading days earlier, else the row is `not_investable` **[PSD]**). Exit = adjusted close on the last trading day of calendar year T + h; if the fund was liquidated before that, the return compounds to the liquidation date (manual NAV ladder, §6) and is held at 0 % nominal cash thereafter, flagged `liquidated_in_window=true`.
- **Investable ⇔ ETF inception ≤ entry date.** A country with more than one ETF in the universe uses the one with the **earliest inception that is still ≤ entry** (CHN: FXI for T ≤ 2010, since MCHI's inception 2011-03-29 > entry 2010-12-31; IND: EPI for T = 2010, INDA is a duplicate; RUS: RSX) **[PSD]**. Status per pick ∈ {investable, no_fund_at_entry, no_fund_ever, liquidated_in_window} — **status counts are always reported** next to every return statistic.
- **Excess return (HEADLINE):** `er_{c,T,h} = r_{c,T,h} − r^{VT}_{T,h}` over the identical window (same entry and exit days).

### 3.5 Benchmarks

- **HEADLINE = VT** (Vanguard Total World Stock ETF, inception 2008-06-24; the "VT and chill" passive default). Same entry/exit days as the pick.
- **VT proxy for windows entered before VT existed** (weights fixed here from FTSE All-World regional weights at T; annually rebalanced on the last trading day of each calendar year; `benchmark=vt_proxy` flagged on every row whose window contains any proxy day):
  - **T = 2000 window (2000-12-29 → last trading day 2010):** SPY 100 % from entry until EFA's first bar (EFA inception 2001-08-14; if the fetched series begins later, the first available EFA bar is used and the date is recorded in RESULTS), then SPY 60 / EFA 40; switching to VT itself from 2008-06-24 (first VT bar on or after that date).
  - **T = 2005 window (last trading day 2005 → last trading day 2015):** SPY 50 / EFA 40 / EEM 10 from entry, annually rebalanced; switching to VT itself from 2008-06-24.
  - **T = 2010 and T = 2015:** VT itself, no proxy.
  - Switch mechanics **[PSD]:** on the switch day the proxy's accumulated value is carried into VT at VT's adjusted close (no gap, no cost); rebalancing and switching are frictionless.
- **Secondary:** `r̄^EW_T` = the equal-weight log return of **all** single-country ETFs in `etf_universe.yaml` investable at T (inception ≤ entry), same window, liquidations handled as in §3.4 — "did pyramid selection beat random selection among what you could buy". Benchmark rows are also reported for **SPY, EFA, EEM** (reference only, never headline).
- The same VT / VT-proxy rule applies to the disconnect table (§5) and to every market row in the UI ("vs VT over the same window").

### 3.6 Statistics (computed on every row: each query × k × h × outcome)

Let the sample be the picks pooled over the T grid, with residual `e_i` = `eg_i` (growth) or `er_i` (returns).
1. **Hit rate** = share of picks with `e_i > 0` (chance 0.5).
2. **Top-quartile rate** = share of picks whose outcome lies in the top quartile of `C(T)` (growth) or of the investable-at-T ETF set (returns) (chance 0.25).
3. **Mean excess** `μ̂` (pp/yr) and **naive SE** = `sd(e)/√n`.
4. **Hansen–Hodrick** SE with truncation `L = h/5 − 1` (h=10 → L=1, h=20 → L=3) on **T-aggregated residuals** (per-T means `ē_T`, ordered by T, 5-year spacing).
5. **Newey–West** (Bartlett kernel) SE with `L = 2` and `L = 4` on the same T-aggregated residuals.
6. **Country-cluster HAC** SE (cluster = country across T).
7. **HEADLINE = block bootstrap**, `B = 5,000`, seed 20260904 **[PSD]**, two schemes: (a) **country-cluster** — resample countries with replacement, keep all their (T, pick) rows; (b) **circular block over T** — block length `h/5` consecutive T's (2 for h=10, 4 for h=20), circular over the ordered T grid. Report the 95 % percentile CI of `μ̂` from **both**, and use the **wider** CI as the headline (`ci_headline`); the CI excludes 0 iff both bounds have the same sign.
8. **`N_eff`** = number of distinct (country, non-overlapping h-block) pairs among the picks, blocks = `floor((T − 1990) / h)` (h=10: {1990–1999, 2000–2009, 2010–2019}; h=20: {1990–2009, 2010–2029}) — printed next to every statistic, everywhere.

### 3.7 Null models (each 5,000 draws, seed 20260904; one-sided p = (#draws with statistic ≥ observed + 1)/(B + 1) **[PSD]**)

- **N1 random-country:** for each T draw k countries uniformly without replacement from `C(T)`; recompute the pooled statistic.
- **N2 income-matched:** for each pick draw a non-pick from `C(T)` whose `ln y_T` lies within a caliper of **0.35 log points** (1:1, without replacement within a draw); if no match exists, draw from the same `ln y_T` decile of `C(T)` (decile-stratified fallback). Statistic recomputed per draw. Tests whether "looks like a pre-boom pyramid" adds anything beyond "is poor".
- **N3 three-band comparator:** the entire Query B pipeline with `d_blend` on the 42-vector replaced by the Euclidean distance on the z-scored `(u15, wa, o65)` vector (§2.2). Reported as a paired difference `Δ_3band = μ̂_eg(42) − μ̂_eg(3-band)` with its bootstrap CI (same resamples).
- **N4 prior-10-year growth momentum:** picks = the top k of `C(T)` by `g_{c,T−10,10}` (requires `y_{T−10}`, same source rule). Same statistics.
- **N1-investable (returns only):** N1 restricted to countries investable at T. Returns are also compared to N4 restricted to investable countries.

### 3.8 Pre-registered predictions (primary = Query B, h = 10, k = 10) — verbatim from the plan

- **P1** growth `μ̂_eg ∈ [+0.3, +1.5]` pp/yr, hit rate H .55–.70, N1 p < .05 plausible, N2 p likely > .05, `N_eff` 20–30.
- **P2** |shape − 3-band| < 0.3 pp (the 42-vector adds little beyond `u15/wa/o65`).
- **P3** returns (vs VT / VT-proxy): investable share < 40 % at T = 2000/05, 60–75 % at 2010/15; `μ̂_er ∈ [−4, +3]` pp/yr vs VT; CI width > 8 pp; zero not rejected; `N_eff` < 15; ≥ 1 liquidation in the 2015 cohort.
- **P3b** the equal-weight investable basket itself does not beat VT over 2010–2025 (EM/frontier country funds lagged VT that decade) — reported so that "beat the basket but lost to VT" cannot be misread as a win.
- **P4** h = 20 growth positive with CI including 0.
- **P5** Query A same signs as Query B, wider CIs.
- **P6** (Experiment 2) WA, ΔWA > 0 (Driscoll–Kraay p < .05).
- **P7** (Experiment 2) D < 0 in-sample but ΔR²(S3 − S1) < .03 and OOS gain < .02.
- **P8** (Experiment 2) OOS R²(S1 over S0) ∈ [.02, .10].

`RESULTS.md` evaluates every one of P1–P8 with the observed value and **met / not met**; a prediction is never re-worded after the fact.

### 3.9 Outputs

`evals/econ/backtest_lookalikes.json` (every row of §3.6–3.7 for every query × k × h × outcome, with `N_eff`, status counts and `benchmark` flags) and `evals/econ/tables/backtest_picks.csv` (T, query, k, iso3, role, d, y_T, g, eg, ticker, status, r, r_vt, er, benchmark).

## 4. Experiment 2 — shape → growth panel

- **Sample:** (c, t) country-years, WPP pop ≥ 1 M, `t ∈ [1950, 2013]`, outcome `g_{c,t,10}` (single-source windows, §2.1); ≈ 8–10 k observations, `N_eff` ≈ 900–1,100 (distinct (country, non-overlapping 10-year block) pairs).
- **Regressors:** `D = ln min_{p ∈ P_train} d_blend(s42_{c,t}, p)` with the prototype set `P_train` **fixed** at top-decile 10-year windows ending ≤ 2003 (same dedupe as §3.3); `WA` = working-age (15–64) share; `ΔWA` = 10-year change in WA (t − 10 → t); `ln y` = log level (§2.1); region × decade fixed effects (WPP SDG regions **[PSD]**). `D_feat` = the same min-distance statistic computed with the `feat` metric (L2 on z-scored `features.py` columns) **[PSD]**.
- **Specifications:** S0 `ln y + FE`; S1 = S0 + `WA + ΔWA`; S2 = S0 + `D`; S3 = S0 + `WA + ΔWA + D`; S4 = S3 + `D_feat`.
- **Estimation:** pooled OLS; **Driscoll–Kraay** SE with bandwidth 10 (primary); two-way (country, year) cluster SE (secondary).
- **Fixed holdout:** train `t ≤ 1993`, test `t ∈ [2003, 2013]` (a ten-year gap so that no training outcome overlaps a test window). Report in-sample R², ΔR²(S3 − S1), out-of-sample R² of each spec against three baselines (the training mean, S0, S1), and per-t OOS Spearman correlation between predicted and realised `g`.
- **Predictions:** P6, P7, P8 (§3.8).
- **Output:** `evals/econ/panel_shape_growth.json`.

## 5. Experiment 3 — disconnect table

Rows (country, year t): **CHN 1990, KOR 1975, KOR 1990, JPN 1960, TWN 1970, THA 1985, VNM 2000, IND 2005**, plus "now" rows **PHL 2024, BGD 2024, NPL 2024, LAO 2024, KHM 2024**.
Columns per row: pyramid statistics (median age, u15, wa, o65 shares, s0/s20 ratio, TFR); `d_blend` to CHN 1990 and its percentile band; `y_t … y_{t+30}` multiples (level series, clipped to the last observed year); MSCI country index annualised USD return over `[t, t + 30]` clipped to the index's history — **hand-transcribed facts with URLs from `evals/econ/msci_citations.yaml`, never series**; ETF CAGR and maximum drawdown computed at build from daily adjusted closes, each against SPY, EEM **and VT / VT-proxy over the identical window**. Rows for which no fact or fund exists show the explicit state ("no MSCI figure transcribed", "no US-listed single-country fund"). Output `evals/econ/disconnect.json`.

## 6. ETF universe and the survivorship guard

- The universe is `evals/econ/etf_universe.yaml`, hand-curated from issuer launch history **before any fetch** (17 WEBS/iShares MSCI country funds of 1996-03; the later iShares, VanEck, Global X, WisdomTree single-country funds through KSA 2015; benchmarks SPY, EFA, EEM, VWO, ACWI, VT). Each entry records the issuer inception date (verified against the issuer page where possible, marked `inception_verified`), the first Yahoo monthly bar, and any discrepancy > 45 days. Delisted funds carry the liquidation date and the issuer press-release URL. **No ticker is added or removed after the fetch.**
- Fetch: Yahoo chart v8 `range=max&interval=1d`, `adjclose`, into `data/raw/etf/` (gitignored). Stooq is behind a JS challenge and the iShares CSV endpoint returns HTML — not scriptable; not used.
- **Assertions per ticker (the guard; any failure stops the build):**
  1. `n_bars ≥ 250`;
  2. first bar ≤ inception + 45 days;
  3. `live` ⇒ last bar ≥ today − 10 days;
  4. `delisted` ⇒ Yahoo **refused** — the one-bar stale signature (a single bar carrying the last quote, `firstTradeDate` often garbage) is asserted, and the ticker is routed to `evals/econ/etf_manual.yaml` (calendar-year NAV total returns transcribed from N-CSR filings + the liquidation press release; a window that runs past the liquidation compounds to the liquidation date, then 0 % cash);
  5. no gap > 45 days between consecutive bars.
- **Never infer "live" from a Yahoo quote.** Yahoo returns either a single stale bar (with a price and even volume) for liquidated tickers — EGPT, NGE, PAK, FM did on 2026-09-04 — or no data at all (ERUS, RSX); the 'Yahoo refused' branch must accept BOTH signatures and route the ticker to the manual ladder. Two more traps found while curating the universe (2026-09-04): Yahoo's PAK series ends 2025-06-11 although the fund's last trading day was 2024-02-16, and Yahoo's NORW series starts 2009-08-24 although the fund's inception is 2010-11-09 — so the fetch drops bars before the yaml inception and after the yaml delisting date, never the reverse. GXG was renamed COLO on 2025-06-23; the yaml's `yahoo_symbol` wins over `ticker` when present. Yahoo's raw chart endpoint rate-limits unauthenticated bursts (HTTP 429); fetch through a cookie/crumb session (yfinance) with backoff. Liveness comes only from the yaml (`delisted: null`) **and** assertion 3; any disagreement between the yaml and the fetched series fails the build.
- **Cross-check:** `evals/econ/etf_crosscheck.yaml` — issuer-factsheet 10-year (or since-inception) annualised NAV total returns for EWJ, EWY, EWZ, FXI, EEM, SPY, VT as of a stated quarter-end; the computed annualised total return from adjusted closes over the same period must agree within **|Δ| ≤ 0.5 pp/yr** for every verified entry, otherwise the build fails.

## 7. Decision rules → UI language

Levels are evaluated by `decide.py` from `backtest_lookalikes.json` and `panel_shape_growth.json`, written to `evals/econ/decision.json`, and rendered only through the sentence bank `evals/econ/ui_sentences.yaml`. The rules, verbatim from the plan:

- **L0 "what happened next" — always allowed.** Past tense, numeric, `N_eff` shown, the disconnect row adjacent, the null result shown, and "vs VT over the same window" on every market number.
- **L1 "growth association" — only if** `μ̂_eg > 0`, the headline CI excludes 0, N1 **and** N2 p < .05, `N_eff ≥ 20`, and the panel's S3 coefficient on D is < 0 with Driscoll–Kraay p < .05 and OOS R²(S3) > OOS R²(S0). The sentence embeds μ̂, the CI, `N_eff`, p_N1 and p_N2, and adds "the working-age share alone accounts for this" if |shape − 3-band| < 0.3 pp (P2 met).
- **L2 "returns signal" — only if** `μ̂_er > 0` **against VT** (headline), the headline CI excludes 0, Hansen–Hodrick **and** Newey–West p < .05, μ̂ is also positive against the equal-weight investable basket, the picks beat N1-investable **and** N4 at p < .05, `N_eff ≥ 20`, **and** the sign is the same in the out-of-sample block (T ≥ 2010, where VT itself is the benchmark and no proxy is involved). **L2 requires beating VT.** Pre-registered expectation: **not met** — the UI may never predict returns.
- **Deny-list** (enforced by pytest over the sentence bank and by vitest over `web/src/**`): `\b(buy|sell|short|overweight|underweight|allocate|position|picks?)\b`, `outsized`, `expect(ed)?\s+(to\s+)?(return|outperform)`, `should\s+invest`, `(will|would)\s+(rise|outperform|boom)`, `top\s+\d+`, `opportunit`, `alpha`, `undervalued` (case-insensitive). The regexes live in `ui_sentences.yaml` and are the single source for both test suites.
- `scripts/build_data.py` merges `decision.json` + `disconnect.json` into `web/src/data/econ.json` under the one-writer/hash rule; the UI never combines shape distance and any econ number into a score, never sorts by return, never shows a price or a forecast.

## 8. Vintage statement (mandatory paragraph in RESULTS.md)

The pyramids used to select lookalikes as of T are WPP 2024 back-series, i.e. today's estimates of what the age structure *was* — not what was known at T. The selection is therefore hindsight-free with respect to the **outcome** (prototype windows end ≤ T; growth and returns are observed after T) but not with respect to the **demographic input**. An optional `--vintage` re-run uses WPP 2010 / WPP 2000 archive files (discovered via `downloads.json`) as the input for T ≤ 2010 / T ≤ 2000 respectively; pre-registered check: top-10 Jaccard overlap between the WPP 2024 picks and the vintage picks ≥ 0.6 at every T where the archive exists. If the archives cannot be obtained, RESULTS says so and the paragraph stands.

## 9. Tests that guard the protocol

- HAC/bootstrap **coverage** on simulated overlapping panels: coverage of the headline CI ∈ [.90, .98] at nominal 95 %; the naive SE must show coverage < .90 (documents why the naive SE is never the headline).
- **Planted-prototype synthetic corpus:** hit rate > .8 when the signal is planted; p uniform under independence.
- **NGE one-bar fixture** trips the survivorship guard (assertion 4); a fixture with a 60-day gap trips assertion 5.
- ISO3 remap fixtures; decision rules exercised by table-driven cases (every L1/L2 condition individually false ⇒ level not granted).
- **PREREG hash check** (§0.3). Sentence-bank deny-list check (§7).

## 10. Reporting

`evals/econ/RESULTS.md` contains, in this order: the PREREG commit hash; data vintages and fetch dates; the universe with verification status and every discrepancy; the guard's per-ticker result; P1–P8 with observed values and met/not-met; every statistic row with `N_eff` and status counts; the null-model table; Experiment 2 and 3 outputs; the vintage paragraph; the decision levels granted; and the "Deviations from PREREG" section (empty if none). Effort budget ≈ 23.5 agent-hours + ≈ 1 h of Eli's review; the budget is not a reason to drop any pre-registered row.
