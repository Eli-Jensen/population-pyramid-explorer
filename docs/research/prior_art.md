# Prior art: population-pyramid tools, "similar pyramid" search, chart similarity, shape typologies, presentation ideas

Surveyed 2026-09-04. Scope: (1) every notable pyramid site/tool, (2) does anyone offer "similar pyramids" search, (3) chart-similarity / reverse-chart-search prior art, (4) shape typologies usable as labels/text queries, (5) presentation ideas to borrow.

---

## 1. Pyramid sites and tools

### 1.1 populationpyramid.net (the reference)
- **Data**: UN WPP 2024 revision, medium variant, updated July 2024; 1950–2100; 5-year bins 0-4 … 100+; ~237 countries/areas + UN regions/aggregates. CC BY 3.0 IGO attribution to UN.
- **URL scheme**: `/{country-slug}/{year}/` (e.g. `/japan/2026/`); adjacent-year links; 10+ language mirrors (`/de/`, `/ja/` …).
- **Public CSV API (undocumented but live, verified 2026-09-04)**: `https://www.populationpyramid.net/api/pp/{UN_LocID}/{year}/?csv=true` → `Age,M,F` rows per 5-year bin (e.g. Japan 2026: `0-4,1968258,1879422`). Useful as a cross-check against the local parquet (their values are per-person, WPP bulk is thousands).
- **Controls**: year navigation buttons (−5, −1, [year], +1, +5) — no continuous scrubber and no play/animate on the main page; alphabetized country dropdown with region groups marked ⓘ.
- **Per-page stats**: total population (+ % change since 10 yrs earlier), median age, youth dependency (per 100 working-age), old-age dependency.
- **Auto-generated shape sentence** (this is new since the 2021 open-source snapshot): e.g. Japan 2026: "The narrow base of the pyramid marks a constrictive age structure: fertility below replacement level and a rising share of older people." World 2026: "near-vertical sides of the pyramid indicate a stationary age structure". So they already do rule-based expansive/stationary/constrictive labelling per (country, year).
- **Export/share**: Download image (PNG), Excel download, embed `<iframe>` code with copy button.
- **Sibling tools** linked from every page: immigration statistics per country, migrant-stock origins, population density, population projections, growth map per year, country ranking by population, "What is a population pyramid?" explainer.
- **Not present**: no compare/overlay of two countries, no % vs absolute toggle (axis is absolute persons; labels say "0.5%" style? — the axis units are not stated on the page text; treat as absolute), no single-year ages, no animation, **no similar-country search**.
- **Open source (historic)**: github.com/madewulf/PopulationPyramid.net — MIT, Python Flask + JS, 74★, last push 2021-03-19; README: "Full code of the site … python scrapper scripts, plus some utilities to translate the data into JSON." Route pattern `/<country>/<int:year>/`, years `range(1950,2101,5)` at the time, pickled dicts from `UNPop.csv`. The live site has since diverged (annual years, shape sentence, multilingual), so treat the repo as a pipeline reference only.
- **Borrow**: URL-per-(country,year) permalinks; the ⓘ region marker; the four headline stats; the shape sentence idea (but computed, and with the rule made explicit); PNG/Excel/embed trio.

### 1.2 populationpyramids.org (plural, .org) — the most feature-complete competitor
- UN WPP 2024, 195 UN member states, 21 bins, Chart.js. Year slider 1950–2025 with **play/pause and speed 0.5×–4×** on the world pyramid; per-country pages `/{country}` with 2025 data + 2026-27 projections.
- **Compare**: `/compare/{a}-vs-{b}` side-by-side any two countries (age structure, sex ratio, trends). Also a "Population Pyramid Maker" (custom data → pyramid).
- Publishes a "types complete guide" with **explicit thresholds**: expansive = TFR 3+, median age <25, growth 2–4%/yr (Nigeria 47% under 15); stationary = TFR ≈2.1, median age 35–40, growth 0–0.5%; constrictive = TFR <2, median age 40+ (Japan 29% over 65). Example sets: expansive {Nigeria, Uganda, Niger, DRC}, stationary {US, France, UK, Canada}, constrictive {Japan, S. Korea, Italy, Germany}.
- **No similar-country feature**; no time-shift matching. Operator anonymous; ad-supported SEO-style site.
- Borrow: the compare URL scheme; the animation speed control; the threshold table as a baseline labeler to evaluate against.

### 1.3 populationpyramid.org (singular .org) and population-pyramid.net (hyphen)
- Both are 2025-26 SEO clones on WPP 2024. Singular-.org: "slide through history and UN projections" 1950–2100 for world/continents/countries; shows total, median age, sex ratio. Hyphenated-.net: a sortable table (population, growth rate, elderly %) → per-country pages `/en/pp/{country}`, multilingual. Neither has compare, overlay, or similarity. Ignore except as evidence of how crowded the "plain pyramid viewer" niche is — the headline feature must be the differentiator.

### 1.4 Our World in Data
- No pyramid *chart type* in Grapher. Age-structure topic page has 18 charts (population by age group stacked-area/bar, dependency ratios, median age vs TFR, etc.) — all country-switchable, embeddable, downloadable (CSV + PNG/SVG), with URL-encoded state (`?country=…&time=…`). Their signature static "Demography of the world population 1950–2100" pyramid overlays decades as shaded layers (2100 outer, 1950 inner) — a good **ghost-overlay** reference. Data currently WPP 2024 (the topic page text cached "2017" is stale).
- Borrow: URL-state-as-share-link; SVG+CSV download from the same button; the layered-decades overlay; the "population by age group" stacked area as a companion view.

### 1.5 US Census Bureau International Database (IDB)
- Own cohort-component estimates/projections (not UN), 200+ countries ≥5,000 pop + subnational areas, **single-year ages 0–100+**, base year → 2100, annual releases (last Dec 2025). Full REST API (`api.census.gov/data/timeseries/idb/1year` and `/5year`), bulk download, R package `idbr`.
- Web tool: select multiple countries × multiple years → grid of pyramids "grouped and boxed per country"; Dashboard tab has **pyramid animation** with start/end/increment and play/pause; downloads PDF/JPEG/CSV. No overlay, no similarity.
- Borrow: single-year data as an alternative source (finer shape); the multi-year small-multiple grid per country.

### 1.6 Gapminder "Ages" (Vizabi pop-by-age)
- 1950–2100 forecast; horizontal axis can be **raw or relative frequencies**; **"lock" a year's pyramid as a black outline reference line** and compare other years against it; groups selectable; time play. Vizabi is open source (Encharted Media), Observable examples exist. Gapminder's own age framework uses 15-year groups for storytelling.
- Borrow: the lock-a-reference-outline interaction is exactly the "ghost" overlay Eli wants; relative-vs-absolute toggle.

### 1.7 Eurostat / ESPON / Eustat (Basque)
- Eurostat interactive pyramid (2019): filled blocks = current population, **bordered outline = EUROPOP2018 projection year**, member state/EFTA selector, up to 2100. ESPON dashboard: browse median age and 5-year groups over time with tailored comparisons (fetch blocked, 403).
- Eustat (Basque statistics office) pyramid help page is the richest feature list found: play/pause/repeat/speed animation; year pick via slider **or by clicking a bar on a total-population evolution mini-chart**; hover shows count + sex ratio per age; **"show the difference between males and females"** mode; adjustable age grouping slider; single-year vs 5-year depending on population size.
- Borrow: outline-vs-fill encoding for projection vs estimate; the mini timeline as year picker; sex-difference mode.

### 1.8 Japan
- IPSS (National Institute of Population and Social Security Research) has long published an animated pyramid 1920/1965→2060/2070 (`ipss.go.jp/site-ad/TopPageData/Pyramid_a.html`, 404 today; successors on the 2023 projection pages with 2020/2045/2070 graphs + CSV). Statistics Bureau publishes census pyramids (2005, 2020) and Commons hosts "Japan animated population pyramid.gif" from Stat Bureau data 2016-19. digitviz.jp: 1920–2115 auto-animate + slider, Stat Bureau (1920–2021) + IPSS (2022–2115).
- Borrow: nothing technical; but Japanese school typology (§4) is a good label set.

### 1.9 Wolfram|Alpha
- "China age distribution 2030", "US, China, India population fraction age 65 in 2030" → pyramid + table, "Show history" buttons; UN Population Division data. Multi-country side by side via query; **no similarity**.

### 1.10 Worldometers, Statista, PRB, CIA Factbook
- Worldometers: static pyramid per country on demographics pages (UN WPP), tables of age groups; not interactive (fetch 403).
- Statista: editorial "From Pyramids to Skyscrapers" world-pyramid chart; paywalled; no tool.
- PRB: World Population Data Sheet (annual since 1962), International Data Center map/table; pyramids appear as lesson plans/Population Handbook explainer, not an interactive tool (`/resources/interactive-population-pyramids/` = 404).
- CIA World Factbook "Population pyramids by region" was a small-multiples reference page; the Factbook is being sunset in 2026 (page now shows a farewell notice).

### 1.11 Wikipedia / Wikimedia Commons
- `Category:Population pyramids`: 200+ subcats, incl. "SVG population pyramids" (62), "Animated population pyramids" (42), "World population pyramids" (29); massive per-country batches (Poland 3,459 files; Japan 95; Spain 85). Many country SVGs (USA, Germany, Norway, Japan…) are hand/script-made from national statistics offices, not one UN template. `File:Population_pyramid_forms.svg` (Kopiersperre, CC BY-SA 3.0, after Burgdörfer's *Volk ohne Jugend*, per-country pyramids by Delphi234) defines six forms: **Triangle (Israel), Modified triangle (Angola), Beehive (USA), Bell (Ireland), Urn (Germany), Christmas tree (Nepal)**.
- Wikipedia "Population pyramid" article: expansive / stationary / constrictive + an "unbalanced" example (Qatar — the gulf-migrant-worker bulge); maps demographic transition: stages 1-2 = broad base pyramid, stage 3 "tombstone", stage 4 base narrows, stage 5 "kite".

### 1.12 GitHub / Observable / Svelte-D3
- **Observable**: `@d3/population-pyramid` (US 1850–2000, year slider; Bostock's original gist 4062085 also had an overlaid-transparent-bars variant), `@observablehq/plot-population-pyramid` (Plot, BiB Germany data), `@herbps10/population-pyramids` (UN Population Division data + projections), `@ericmauviere/population-pyramid-with-plot` (Germany 1991–2021), `@neocartocnrs/…age-pyramid-at-different-levels-of-aggregation` (France 2020), `@categorise/population-pyramid-plot`, `@didoesdigital/15-july-2020-about-population-pyramids`, `@sarah37/population-pyramid-scotland-2019`.
- **GitHub repos** (gh search "population pyramid", by stars): `madewulf/PopulationPyramid.net` (74★, above); `z3tt/BiB-population-pyramids` (23★, Cédric Scherer's ggplot pyramids for the German BiB report — best-in-class styling reference); `doylek/D3-Population-Pyramid` (14★, D3 v4 component); `JuanGaleano/Population-pyramids-ggplot2` (overlapped + composed pyramids in R); `timriffe/Pyramid` (R); `JoanPeturPetersen/pop-pyramid` (matplotlib animate); `ar-puuk/population-pyramid-explorer` (US states); `edyhsgr/CACountyPyramids`; `Buddhi19/DevisingPoPStat` + `PoP_Pyramid_UI` (**the only repo quantifying pyramid shape as a scalar** — see §2); `cmvdemo/population-pyramid-gif` (pulls UN data, gganimate). No Svelte-specific pyramid repo of note; Svelte+D3 starters: `connorrothschild/svelte-visualization-template`, `RoyNij/svelte-d3`, `bakkenbaeck/data-visualisation-svelte-d3`.
- **Dataset repos**: none packaging WPP2024 age×sex×year as a tidy artifact with stars; the local parquet is already better than anything found.
- Other design refs: id.com.au "animated population pyramids" (benchmark region overlaid, toggled from legend, play across census years, proportion of pop per group, compare any two small areas); freerangestats "animated population pyramids for the Pacific" (R, 2025); StatCan animated pyramid; Excelcharts "Beautiful but terrible population pyramids" (Camões: overlaying 1981–2050 layers causes moiré; fix with fewer intervals, restored axes, sex-separated panels, opacity ramp).

---

## 2. Does anyone offer "similar pyramids" / "which country looked like X in year Y"?

**Products/sites: NO.** Explicit negatives after targeted searches ("similar age structure", "similar population pyramid", "looks like … in year", "countries with a similar age structure", site-by-site feature checks): populationpyramid.net, populationpyramids.org (has compare but you must pick both countries), populationpyramid.org, population-pyramid.net, OWID, Census IDB, Gapminder, Eurostat, Wolfram|Alpha, Worldometers, PRB, Statista, Wikipedia — none has nearest/farthest-shape search, none has time-shifted matching, none ranks by shape. The closest things are (a) hand-picked "three types" galleries (Visual Capitalist 2023 "Population pyramids compared", WEF 2023 "visual guide"), and (b) prose comparisons in policy writing (RIETI 2022: "the current age structure of China's population is similar to that of Japan around 1990"; China 2020 child/elderly shares ≈ Japan 1990, working-age share ≈ Japan 1989, median age ≈ Japan 1991). That RIETI framing — **"country A today ≈ country B N years ago"** — is exactly the time-shift feature and nobody has productized it.

**Research: YES, a small but direct lineage** (all use the data vector, none use images):
- Korenjak-Černe, Kejžar, Batagelj, *Clustering of Population Pyramids*, Informatica 32 (2008) 157–167 — hierarchical clustering of world countries on pyramid shape (Euclidean on age-share vectors), 1996/2001/2006, tracks countries moving between clusters.
- Košmelj & Billard (2011), *Clustering of population pyramids using Mallows' L2 distance* (Metodološki zvezki) — Wasserstein-2 between age histograms; East Europe 1995–2015 converging toward aging shape. Irpino's R package **HistDAWass** ships the 228-country Census IDB 2014 age-sex pyramid dataset (`arXiv:1605.00513`, fuzzy clustering with adaptive L2 Wasserstein).
- Korenjak-Černe et al., *A weighted clustering of population pyramids for the world's countries, 1996, 2001, 2006*, Population Studies 2015 (PubMed 25309982) — discrete-distribution clustering including both sexes; yields representative age-sex structure per cluster.
- Ono et al., *Which country epitomizes the world?* (arXiv 1810.00210; Sustainability 2019, 11, 6404) — **Aitchison (compositional/CLR) distance** between age-share vectors; matches the *world's* pyramid in each future period to the 2015 country it most resembles (India/N. Africa in 1990s → South America 2015–30 → Oceania/N. America 2040 → Uruguay/Puerto Rico 2050–60 → Italy/Japan later). This is time-shift matching, done once for the world.
- Buddhi19 et al., *Devising PoPStat* (arXiv 2501.11514, 2025) — **PoPDivergence = KL divergence between a country's pyramid and a reference pyramid (Japan or Singapore)**, correlated with GBD cause-specific mortality (NCDs r=−0.84 vs Japan-reference). Code on GitHub. Shows a 1-D shape scalar is already useful.
- Lee, *How can population pyramids be used to explore the past?* (arXiv 1803.07776) — pyramids as "tree rings"; birth-rate dips as event signatures (N. vs S. Korea). Suggests **residual/cohort-anomaly features** (notches) matter for similarity beyond overall envelope.
- Sketch/shape query systems for time series are the closest interaction precedent: **Qetch** (scale-free hand-drawn sketch matching, CHI 2018), **Zenvisage** (ZQL, "find visualizations that look like this"), **ShapeSearch** (shape algebra: sketch, NL, visual regex), **TimeSearcher**, **DeepSketch** (2024). A pyramid is a 21- or 42-point profile, so "draw a shape → nearest pyramids" is feasible with the same machinery.

Net: the headline feature is genuinely novel as a product; its mathematical substrate (distance on age-share vectors, Aitchison/Wasserstein/KL/Euclidean, clustering) is well established and should be the baseline that any image-embedding approach must beat in evaluation.

---

## 3. "Find similar chart" / chart reverse-image-search prior art

- **No consumer product** does shape-similarity search over charts. Google Lens / Bing Visual Search / Mixpeek-style reverse image search return visually similar *images* (dominated by layout, color, text), not data-shape neighbors. Datawrapper/Flourish/Observable have no "similar chart" feature; Observable's Plot has a population-pyramid recipe only.
- **Research systems**:
  - Hoque & Agrawala, *Searching the Visual Style and Structure of D3 Visualizations* (IEEE VIS 2019, arXiv 1907.11265): 7,860 D3 charts; deconstructs each into data + marks + encodings and searches **structurally, not by pixels**; user study preferred it to keyword search. Lesson: when the underlying data is available, structural features beat pixels.
  - Beagle (Battle et al. 2018): mines 41k SVG charts, classifies type at 85%. ChartSeer (Zhao et al. 2020): VAE embeddings of Vega-Lite specs for recommendation/steering. VizNet (31M data points corpus). VisImages (annotated viz images).
  - Multimodal Chart Retrieval (NAACL 2024): text→chart-image retrieval comparing OCR, DePlot derender→table, PaLI-3 image encoder; **derendering to a table (300M params) matched/beat the 3B image model in-distribution**; "DePlot struggles with complex charts." I.e., for retrieval of charts, recovering the data is the strong baseline.
  - Chart-capable embedders: jina-embeddings-v4 (2025; single space for text+image, strong on "tables, charts, diagrams"), ColPali/ColQwen (late-interaction visual document retrieval), SigLIP-2, Nomic Embed Vision. These embed *documents* semantically; none is evaluated for fine-grained *bar-length shape* sensitivity.
  - Evidence that pixel models are weak at exactly this: CharXiv (NeurIPS 2024) GPT-4o 47.1% vs humans 80.5% on real charts; "Do MLLMs really understand the charts?" (arXiv 2509.04457); CLIP has more shape bias than ImageNet CNNs but still keys on style/texture/text, and fine-tuning erodes it (Geirhos 2019; CLIP robustness 2402.07410). For pyramids all images share identical style, so an embedder's variance will come partly from label text/tick values (which encode population size, not shape) unless those are stripped.
- **Engaging Eli's image-embedding idea seriously**: it is a legitimate *zero-feature-engineering* baseline and the only route that would also let a user query with a sketch or a screenshot of a chart from elsewhere. But the prior art says: (i) render identically-styled, label-free, percent-normalized pyramids so the embedder can only see shape; (ii) compare against the trivial vector baseline (42-dim age×sex shares, Aitchison/Wasserstein/L2) on a held-out sanity suite — Aitchison nearest neighbors, "China 2020 ≈ Japan 1990" (RIETI), the Ono epitome sequence, textbook type sets (§1.2), and same-country adjacent-year monotonicity; (iii) expect the vector baseline to win on shape fidelity and cost (36k × 42 floats is 6 MB — client-side brute force in a static Svelte app), with the embedding worth keeping only if it adds something measurable (sketch/screenshot query, or a learned metric that matches human judgments better).

---

## 4. Shape typologies usable as labels or text queries

| Family | Terms | Source / notes |
|---|---|---|
| Anglophone textbook | **expansive** (triangle), **stationary** (rectangle/"tombstone"), **constrictive** (inverted/beehive/urn), + **unbalanced** (Qatar-type migrant bulge) | Wikipedia; PRB Handbook; populationpyramids.org thresholds (§1.2) |
| Demographic transition | Stage 1-2 broad pyramid → Stage 3 rounding "tombstone" → Stage 4 narrowing base → **Stage 5 "kite"** | Wikipedia; also Japan's projected 2050+ shape "kite" |
| Burgdörfer (German, 1930s) | **Pyramide**, **Glocke** (bell), **Urne**; extended school set: **Bienenkorb/Zwiebel** (beehive/onion = stationary), **Tannenbaum/Tropfen** (fir tree/drop = very narrow young stem widening at 20+ — migrant-worker cities), **Pilz** (mushroom = collapse) | de.wikipedia Altersstruktur; geohilfe.de; studyflix |
| Commons "forms" figure | Triangle (Israel), Modified triangle (Angola), Beehive (USA), Bell (Ireland), Urn (Germany), **Christmas tree** (Nepal) | File:Population_pyramid_forms.svg |
| Japanese school set | **富士山型** Mt-Fuji (pyramid), **釣鐘型** bell, **つぼ型** pot/urn (also 紡錘型 spindle), **星型** star (urban, young inflow), **ひょうたん型** gourd (rural, young outflow) | Daiichi Gakushusha GEO p.128; kotobank |
| Folk / journalism | Christmas tree, beehive, coffin/urn, kite, skyscraper (Statista "From Pyramids to Skyscrapers"), bulb, tombstone, onion, hourglass (post-famine/war notches), "diamond" (Gulf states) | various |

Use: (a) as **computed labels** with published thresholds (median age, share <15, share 65+, TFR proxy via 0-4/20-39 ratio); (b) as **prototype vectors** — average the pyramids of the canonical example countries/years and let users type "beehive" or "kite" to retrieve nearest to that prototype; (c) as a small **evaluation set** for any similarity metric (a good metric should keep Nigeria near Uganda, Japan near Italy, Qatar/UAE off on their own).

Descriptive words worth attaching to matches: median age, dependency ratios, sex ratio, "notch" cohorts (the Korean, Chinese 1960, German 1945 dips), migration bulge (working-age male excess), baby-boom bulge age.

---

## 5. Presentation ideas worth adopting (with where seen)

1. **Ghost/overlay of a second pyramid**: Gapminder "lock year" black outline; Eurostat fill-vs-bordered projection; OWID decade layers; id.com.au benchmark toggled from the legend; Bostock's transparent-overlaid-bars gist; Galeano "overlapped and composed" ggplot pyramids. Recommendation: fill = focal pyramid, stroke-only outline = match, both **percent of total** so shapes are comparable regardless of size; optional "mirror" mode showing the match in the male half and the focal in the female half.
2. **Animation scrubber**: populationpyramids.org play + 0.5–4× speed; IDB start/end/increment; Eustat play/pause/repeat/speed and year-picking by clicking a total-population mini timeline; IPSS/digitviz auto-animate. Recommendation: slider 1950–2100 with play; a **thin sparkline of median age or total pop under the slider** that doubles as a year picker; keyboard ←/→.
3. **Small multiples**: IDB country×year grid; CIA Factbook regional sheets; Visual Capitalist/WEF type galleries; z3tt/BiB report pyramids (styling). Recommendation: top-k matches as a row of mini pyramids, each captioned "Country YEAR · d=0.031" with the focal outline ghosted inside each.
4. **Time-shift matching UI** (novel; grounded in RIETI/Ono): constraints as three radio modes — *same year* (default, current year), *year range* (dual slider), *any year* — plus "exclude same country" and "exclude aggregates/regions" toggles; result caption phrased as "Japan 1990 (−36 yrs)" so the lag is explicit. Also a "trajectory" mode: for the focal country, show which (country, year) it will resemble in 2050 (Ono's epitome idea inverted).
5. **Shape label sentence** (populationpyramid.net) — but show the rule and the numbers behind it; add the folk name as a tag chip.
6. **Sex-difference mode** (Eustat): shade male–female excess per bin; surfaces Gulf-state migrant bulges and elderly female excess.
7. **Share/embed/export**: URL state for country, year, mode, constraints (OWID/Grapher pattern, `?c=JPN&y=2026&mode=any&k=8`); PNG (and SVG) download rendered client-side; embed iframe snippet; Excel/CSV of the focal + matches (populationpyramid.net trio).
8. **Percent vs absolute toggle** (Gapminder): default percent for comparison, absolute for a single country's story; single scale across compared pyramids.
9. **Region/aggregate marker** (ⓘ on populationpyramid.net) and an "exclude aggregates" default in similarity results so "Southern Asia" never outranks a country.
10. **Avoid**: many-layer overlays without opacity ramp (Camões moiré critique); label-less "art" pyramids; hand-picked three-type galleries as the only classification.

---

## Sources
- https://www.populationpyramid.net/ · /world/2024/ · /japan/2026/ · API `https://www.populationpyramid.net/api/pp/392/2026/?csv=true`
- https://github.com/madewulf/PopulationPyramid.net
- https://www.populationpyramids.org/ · /compare · /blog/population-pyramid-types-complete-guide · /population-pyramid-maker
- https://www.populationpyramid.org/ · https://population-pyramid.net/
- https://ourworldindata.org/age-structure · https://ourworldindata.org/grapher/population-by-age-group
- https://www.census.gov/programs-surveys/international-programs/about/idb.html · https://www.census.gov/data-tools/demo/idb/assets/resources/help/help.html · https://www.census.gov/data/developers/data-sets/international-database.html
- https://www.gapminder.org/tools/#$chart-type=popbyage · https://link.springer.com/chapter/10.1007/978-3-031-20748-8_8 · https://vizabi.com/
- https://ec.europa.eu/eurostat/web/products-eurostat-news/-/EDN-20190711-1 · https://www.espon.eu/news/population-structure-and-ageing-visual-comparison · https://www.eustat.eus/graficosJS-operaciones/ayuda-piramide/html/ayuda_i.asp
- https://blog.wolframalpha.com/2011/04/18/new-age-pyramids-enhance-population-data/
- https://www.worldometers.info/demographics/world-demographics/ · https://www.statista.com/chart/10366/age-structure-of-world-population/ · https://www.prb.org/resource/2024-world-population-data-sheet/ · https://www.cia.gov/the-world-factbook/references/population-pyramids-by-region/
- https://en.wikipedia.org/wiki/Population_pyramid · https://commons.wikimedia.org/wiki/Category:Population_pyramids · https://commons.wikimedia.org/wiki/File:Population_pyramid_forms.svg · https://de.wikipedia.org/wiki/Altersstruktur · https://geohilfe.de/humangeographie/bevoelkerungsgeographie/definitionen-bevolkerungsgeographie/alterspyramide-definition-grundformen/ · https://www.daiichi-g.co.jp/geo/contents/data/matome/kaitou/223_人口ピラミッドの種類.pdf · https://kotobank.jp/word/人口ぴらみっど-3155844
- https://www.ipss.go.jp/pp-zenkoku/j/zenkoku2023/db_zenkoku2023/db_zenkoku2023gaiyo.html · https://digitviz.jp/pyramid-age-population/ · https://www.stat.go.jp/english/data/kokusei/2005/kihon1/00/00.html
- https://observablehq.com/@d3/population-pyramid · https://observablehq.com/@observablehq/plot-population-pyramid · https://observablehq.com/@herbps10/population-pyramids · https://observablehq.com/@ericmauviere/population-pyramid-with-plot · https://observablehq.com/@neocartocnrs/how-to-draw-an-age-pyramid-at-different-levels-of-aggregatio · https://gist.github.com/mbostock/4062085
- https://github.com/z3tt/BiB-population-pyramids · https://github.com/doylek/D3-Population-Pyramid · https://github.com/JuanGaleano/Population-pyramids-ggplot2 · https://github.com/Buddhi19/DevisingPoPStat · https://github.com/timriffe/Pyramid · https://github.com/connorrothschild/svelte-visualization-template
- https://www.id.com.au/insights/articles/animated-population-pyramids-now-in-community-profile/ · https://freerangestats.info/blog/2025/05/17/animated-population-pyramids · https://excelcharts.com/beautiful-but-terrible-population-pyramids/ · https://www.visualcapitalist.com/population-pyramids-compared/ · https://www.weforum.org/stories/2023/06/visual-guide-global-population-pyramids-demographics/ · https://www.ageing.ox.ac.uk/population-horizons/data/gpt
- https://www.rieti.go.jp/en/china/22102701.html
- https://www.informatica.si/index.php/informatica/article/view/188 · https://repozitorij.uni-lj.si/IzpisGradiva.php?id=56041&lang=eng · https://pubmed.ncbi.nlm.nih.gov/25309982/ · https://arxiv.org/abs/1810.00210 · https://www.mdpi.com/2071-1050/11/22/6404 · https://arxiv.org/abs/2501.11514 · https://arxiv.org/abs/1803.07776 · https://arxiv.org/pdf/1605.00513
- https://arxiv.org/abs/1907.11265 · https://aclanthology.org/2024.naacl-long.307/ · https://github.com/jeffjianzhao/ChartSeer · https://arxiv.org/pdf/2406.18521 · https://arxiv.org/html/2509.04457v1 · https://arxiv.org/abs/2506.18902 · https://arxiv.org/html/2407.01449v5 · https://arxiv.org/pdf/2402.07410 · https://dblp.org/rec/conf/iclr/GeirhosRMBWB19.html
- https://www.researchgate.net/publication/325374842_Qetch_Time_Series_Querying_with_Expressive_Sketches · https://www.researchgate.net/publication/312873311_Effortless_data_exploration_with_zenvisage · https://www.researchgate.net/publication/341750686_ShapeSearch
