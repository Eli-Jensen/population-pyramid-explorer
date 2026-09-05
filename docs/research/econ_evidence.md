# Economic-lens evidence notes (research phase, 2026-09-04)

Condensed from the research agent's report that preceded the plan. **[V]** = the agent fetched and read the primary source that day; **[M]** = from memory / secondary reporting, not verified. Numbers here feed `evals/evidence.yaml` → `web/src/data/evidence.json`; every UI figure must trace back to a line in this file, `evals/econ/RESULTS.md`, `evals/econ/decision.json` or `evals/econ/msci_citations.yaml`.

## Link 1 — age structure → GDP growth (real, conditional)

- Bloom, Canning & Sevilla (2001/2003): the demographic dividend accounts for "as much as one-third" of East Asia's economic miracle; Bloom, Canning & Malaney (1999) give "a third to a half". **[V]** NBER WP 8685 https://www.nber.org/system/files/working_papers/w8685/w8685.pdf ; CID WP 15 https://www.hks.harvard.edu/sites/default/files/centers/cid/files/publications/faculty-working-papers/015.pdf ; RAND MR-1274 https://www.rand.org/pubs/monograph_reports/MR1274.html
- Bloom & Williamson (1998), *World Bank Economic Review* 12(3):419–455 — the original one-third attribution. **[M]** https://academic.oup.com/wber/article-abstract/12/3/419/1632238
- Mechanism (East Asia 1965–90): per-capita income > 6 %/yr; working-age population grew ≈ 2.4 %/yr, nearly four times the dependent population; working-age share ≈ 57 % (1965) → ≈ 68 % (2000). **[V]** (w8685)
- Effect sizes: Cruz & Ahmed (2018), *World Development* 105:95–106 — +1 pp working-age share ≈ +1.5 pp GDP-per-capita growth **[M]** https://www.sciencedirect.com/science/article/abs/pii/S0305750X17304114 ; companion typology paper World Bank WPS7893 **[V]** https://documents1.worldbank.org/curated/en/867951479745020851/pdf/WPS7893.pdf
- Conditions, verbatim from w8685: "The demographic dividend is not, however, automatic." / "this demographic dividend is not inevitable. It has to be earned." Named policy areas: public health, family planning, education, labour-market flexibility, openness to trade, savings. Openness triples the effect: a working-age population growing 1.5 % faster than total adds ≈ 0.5 %/yr growth in a closed economy but ≈ 1.5 %/yr in an open one. **[V]**
- Failure cases **[V]** (w8685 unless noted): Latin America grew 0.7 %/yr per capita 1975–95 vs East Asia 6.8 % with favourable demographics from 1970; direct age-structure effects explain ≈ 11 % of the gap, ≈ 50 % once the policy interaction is included; only 12 % of the region counted as open by 1980. Egypt's transition through 1990 accounted for ≈ one-sixth of income growth 1965–90. Sub-Saharan Africa: DRC TFR 6.1 (1960) → 6.0 (2024); Nigeria 6.4 → 4.4; Uganda 6.9 → 4.2; DRC dependency ratio rose 84.8 → 96.5 (WDI).
- This project's own backcast (pyramid-econ, `reports/backcast_2000_2020.csv`): effective-labour growth vs realised 2000–2020 GDP growth over 69 countries — corr 0.47, slope 0.76, MAE 1.5 pp; worst misses CHN, VNM, ETH (catch-up growth dominates).

## Link 2 — GDP growth → equity returns (negative across countries)

| Study | Sample | Correlation of real GDP/cap growth with real equity returns |
|---|---|---|
| Dimson, Marsh & Staunton, *Triumph of the Optimists* (2002) | 16 countries, 1900–2001 | negative **[M]** |
| Ritter (2005), *Pacific-Basin Finance Journal* 13:489–503 | 16 countries, 1900–2002 | −0.37 **[V]** https://site.warrington.ufl.edu/ritter/files/2015/04/Economic-growth-and-equity-returns-2005.pdf |
| Ritter (2012), *Journal of Applied Corporate Finance* | 19 countries, 1900–2011 | −0.39 (p ≈ .10); USD-adjusted −0.32 **[V]** https://static.twentyoverten.com/5980d16bbfb1c93238ad9c24/r1RMU0DFQ/Is-Economic-Growth-Good-for-Investors-Jay-Ritter.pdf |
| Ritter (2012) | 15 emerging markets, 1988–2011 | −0.41 **[V]** |
| DMS 2010 yearbook | 44 countries | no significant relationship **[M]** |

- Ritter's abstract: "the cross-country correlation of real stock returns and per capita GDP growth over 1900–2002 is negative." Mechanism: growth from added capital/labour accrues to new shareholders (dilution); "investors overpay for expected growth, and this overpayment more than offsets the benefits of unexpected growth." **[V]**
- MSCI Barra (May 2010), "Is There a Link Between GDP Growth and Equity Returns?": confirms the negative cross-country correlation; 1969–2009 mean slippage GDP growth → EPS growth 2.3 pp, offset by 2.0 pp P/E expansion; Sweden's index beat GDP growth by 3.5 pp/yr, Spain's trailed by 4.5 pp/yr; results flip with a one-year endpoint shift. **[V]** https://www.msci.com/documents/10199/a134c5d5-dca0-420d-875d-06adb948f578
- MSCI China since 31 Dec 1992: +1.55 %/yr annualised (USD), max drawdown −88.63 % (1993-12-31 → 2001-09-12); MSCI EM +7.89 %/yr; MSCI ACWI +9.24 %/yr (factsheet as of 2026-08-31). **[V]** https://www.msci.com/documents/10199/255599/msci-china-index.pdf — see `evals/econ/msci_citations.yaml` for the transcribed values actually used. China GDP/cap PPP (constant 2021 $, WDI) $1,667 (1990) → $23,841 (2024), 14.3×.

## Link 3 — demographics → equity returns directly (weak, poor out-of-sample record)

- Arnott & Chaves (2012), *Financial Analysts Journal* 68(1):23–46: polynomial cohort-share model; +1 % in the 50–54 cohort ≈ +1 pp annual equity return, +1 % in 70+ ≈ −1.5 pp. **[M]** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1810985
- Poterba (2001), *REStat* 83(4):565–584: "statistical tests have limited power based on the few effective degrees of freedom in the historical record"; no sharp prospective decline implied. **[M]** http://piketty.pse.ens.fr/files/PoterbaRESta2001.pdf
- Geanakoplos, Magill & Quinzii (2004), *BPEA*: MY ratio (40–49 / 20–29) and stock prices. **[M]** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=329840
- Liu & Spiegel (2011), FRBSF Economic Letter: M/O ratio forecast of US P/E falling to ≈ 8.4 by 2025 — failed out of sample. **[M]** https://www.frbsf.org/economic-research/publications/economic-letter/2011/august/boomer-retirement-us-equity-markets/ (follow-ups 2014, later blog)

## Link 4 — investability (fails for the young countries)

- 2024 age split closest to China 1990 (0–14 28.8 % / 15–64 65.9 % / 65+ 5.3 %): Philippines, Bangladesh, Nepal, Laos, Cambodia, Jordan — not Nigeria/Ethiopia/DRC (younger than China ever was; DRC median age 15.9, Uganda 17.1 vs China's 1975 trough 19.1). **[V]** computed from WDI.
- No US-listed single-country ETF: Bangladesh, Pakistan (since 2024), Nigeria (since 2023/24), Ethiopia, Kenya, Egypt (since 2024), Tanzania, Uganda, DR Congo, Nepal, Laos, Cambodia. Live: INDA (0.61 % ER, $6.8 bn), EPHE, EIDO, VNM (frontier), THD, EWY, MCHI, KSA, EPOL, AFK. **[V]** where live quotes were checked. Authoritative dates now live in `evals/econ/etf_universe.yaml` (issuer-verified) — e.g. NGE last trading day 2024-03-25 (universe file's 2023-07-28 was corrected by the manual ladder), EGPT 2024-03-21, PAK 2024-02-16, FM 2025-01-06.
- MSCI (Feb 2024): "MSCI will delete each Nigerian security from the MSCI Frontier Markets Indexes at a price that is effectively zero as of the close of February 29, 2024" (FX repatriation failure since 2020); Nigeria reclassified Frontier → Standalone. **[V]** https://www.msci.com/documents/10199/09a7d0cc-1500-711d-c437-4df67fb05609
- MSCI classification snapshot (Aug 2023) **[V]**: EM = India, Indonesia, Philippines, Egypt, Turkey, Saudi Arabia, Korea, China, Thailand, Brazil, Mexico; Frontier/Standalone = Vietnam, Bangladesh, Kenya, Pakistan, Nigeria, Sri Lanka, Morocco, Jordan, Kazakhstan; not in the MSCI universe: Ethiopia, Uganda, Tanzania, DR Congo, Nepal, Laos, Cambodia. https://www.msci.com/documents/1296102/1330218/MSCI-Country-Classification-Standard-cfs-en.pdf
- Yahoo Finance serves stale metadata (and, for some funds, full dead histories) for delisted tickers — the survivorship trap; see PREREG §6 and the guard report.

## China 1990 vs today's lookalikes (WDI, OWID/UN WPP) **[V]**

| Economy & year | WA % | Dependency | Median age | TFR | GDP/cap PPP (2021 $) |
|---|---|---|---|---|---|
| China 1990 | 65.9 | 51.8 | 23.7 | 2.5 | 1,667 |
| China 2024 | 69.3 | 44.2 | 40.6 (2026) | 1.0 | 23,841 |
| Korea 1990 | 69.3 | 44.3 | 25.8 | 1.6 | 14,378 |
| Vietnam 2000 | 62.5 | 59.9 | 22.7 | 2.0 | 4,349 |
| India 2024 | 68.2 | 46.6 | 29.2 | 2.0 | 9,416 |
| Bangladesh 2024 | 65.5 | 52.6 | 26.3 | 2.1 | 8,487 |
| Philippines 2024 | 66.6 | 50.1 | 26.6 | 1.9 | 10,378 |
| Nigeria 2024 | 55.9 | 78.8 | 18.3 | 4.4 | 7,994 (flat since 2010) |
| Ethiopia 2024 | 57.7 | 73.3 | 19.3 | 3.9 | 2,892 |
| DR Congo 2024 | 50.9 | 96.5 | 15.9 | 6.0 | 1,602 |

Reading: nobody today matches China 1990 on both age structure and income; today's structural matches are 5–6× richer, today's income matches carry dependency ratios 73–97. Egypt 1990 GDP/cap ($8,007) and Nigeria 1990 ($5,424) were 4.8× / 3.3× China's and are barely richer today.

## Prior art — negative

No tool offers pyramid similarity search across time or pairs pyramids with GDP/returns: populationpyramid.net (no comparison), populationpyramids.org (two-country side-by-side only), Our World in Data age-structure pages, Gapminder, UNFPA Demographic Dividend Atlas, World Bank Ahmed–Cruz four-group typology (static PDF), Visual Capitalist explainer. **[V]**

## Data licences (for the site)

Maddison Project Database 2023 — CC BY 4.0 (cite Bolt & van Zanden 2024). PWT 11.0 — CC BY 4.0 (Feenstra, Inklaar & Timmer 2015). World Bank WDI — CC BY 4.0 (verify the dataset page). OWID — its own content CC BY but underlying data keeps the provider's licence. IMF WEO — no systematic redistribution/derivative works (build-time only). MSCI index data — may not be redistributed; cite factsheet facts only. Yahoo/Stooq prices — personal use; ship derived statistics only.
