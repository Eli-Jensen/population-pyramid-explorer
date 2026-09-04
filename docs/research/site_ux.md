# populationpyramid.net — product/implementation review (2026-09-04)

Method: in-app Browser pane (tab `seed`) on home, /japan/2026/, /niger/2026/, /world/2050/, /republic-of-korea/2050/ (via embed), immigration-statistics, mobile preset 375×812; curl of ~25 URLs incl. all API endpoints; DOM/JS inspection; network log. Saved HTML/JSON/XLSX/PNG under `/private/tmp/claude-501/-Users-elijensen-Projects/d786032f-481e-46d5-993f-907c938b43fe/scratchpad/research/` (japan2026.html, pp.js = pyramid draw code, vars.js = inline page data, pp_392_2026.json/.xlsx, capture.png, entities.json = 236 id→slug map).

## 0. One-paragraph verdict
A 2011 Django + d3 v4 side project (author Martin De Wulf, operator Red Teapot SRL, Brussels) that renders ONE UN WPP2024 medium-variant pyramid per page in % of total population on a FIXED 0–10% axis, with a 151-year population line as the year picker, auto-generated narrative (median age, dependency ratios, shape class), 12 locales, server-side PNG capture for sharing/og:image, Excel/CSV/JSON endpoints, and an iframe embed. It has NO comparison, overlay, similarity, animation, absolute-count mode, or variant selection; the only "vs" is an outbound link to the sister site woatlas.com which just juxtaposes two capture PNGs. It is heavy (415 KB HTML, 258 KB inline JS, ~190 requests, Raptive ads incl. a sticky outstream video that covers the pyramid's bottom rows on desktop) and has weak accessibility (SVG with no aria, year buttons are non-focusable `<span>`s). The data model, URL scheme, fixed-scale presentation, callouts and structured data are the parts worth copying.

## 1. Feature inventory

| Feature | What it does | Verdict | Why |
|---|---|---|---|
| Pyramid chart (d3 SVG) | 21 five-year bins 0-4…100+, male left / female right, % of TOTAL population, fixed 0–10 % axis both sides, % label at every bar end | **keep** | Fixed axis makes every country/year visually comparable — essential for a "similar shape" tool. Percent-of-total normalises size away. |
| Hover on a bar row | Hides the row's bars+% labels (opacity 0) and prints absolute counts (male steelblue, female pink) centred on the row | adapt | Showing counts on hover is right; making the bars vanish is wrong. Use a tooltip or a side readout instead. |
| Total population callout | "Population: 122,427,731" top right, large | keep | Numbers in thousands ×1000, formatted with commas; also repeated on the line chart. |
| Population line chart 1950–2100 | 151 annual points, dotted crosshair at (year, pop), hover previews other years, **click sets year** | adapt | Good idea as a year scrubber; but there is no drag, no play, no keyboard. Replace with a real range input + optional play; keep the line as context. |
| Year -5 / -1 / [2026] / +1 / +5 | Increments year; pushState to /slug/year/; fetches /api/pp JSON + re-downloads the entire HTML page to swap the narrative | adapt | Step buttons are handy; the implementation is wasteful (≈110 KB gz per step) and `<span>`s are not keyboard-reachable. |
| Age-shares chart | 3 lines (Under 15 / 15–64 / 65+) 1950–2100 at 5-yr steps, dashed marker at current year, crosshair with values | keep | Cheap, informative, ties shape to the dependency narrative. Compute from the parquet in seconds. |
| Auto narrative paragraph | Per (entity, year): population, 10-yr % change, median age, youth & old-age dependency per 100, shape class (expansive / constrictive / stationary) with varied templates; translated | keep | Great for SEO and comprehension; trivially generated from your parquet. Add the *numbers* behind the shape class (e.g. 0-14 share vs 15-29 share). |
| Country picker A: header dropdown | Name ▾ opens a scrollable list with substring search box; countries and 35 aggregates mixed alphabetically | adapt | Search box good; mixing "Africa" between Afghanistan and Albania is confusing — group aggregates separately, show flags/ISO3. |
| Country picker B: A–Z letter index | 26 letter links reveal that letter's list; region entries carry an ⓘ icon → /regions#anchor + hover/focus tooltip listing member countries | skip / adapt | Redundant with search; the region-members tooltip is worth keeping (regionMembers map inlined). |
| Regions / aggregates | 35 UN M49 aggregates (World, continents, sub-regions, SDG/development groups, LDCs) as first-class entities with the same URL scheme | keep | Your parquet already has 237 entities; treat aggregates as entities, but flag them (id ≥ 900) and exclude from "most similar country" by default. |
| Download image | Link to `images.populationpyramid.net/capture/?selector=%23pyramid-share-container&url=<page>?share=true` → server-side headless screenshot PNG 575×581 with branded footer | adapt | Do client-side SVG→PNG (canvas) instead; zero server. Keep the branded footer (name, year, population, source). |
| Excel / CSV | `/api/pp/{id}/{year}/?excel=true` xlsx (sheet Age,M,F in persons); `?csv=true` text/csv | keep | Trivial; serve pre-built static CSV/JSON per entity instead. |
| Embed | Modal with iframe snippet → `/embed/population_pyramid/{lang}/{slug}/{year}/` (no ads, no controls, static pyramid + "Source:" link; still 81 KB gz because d3 is inlined) | adapt | Nice for teachers (their stated audience). A static-site route with query params does the same. |
| Hub page `/{slug}/` | Canonical "current year" page titled "Japan Population Pyramid (1950–2100)" + "by year" link block (1950…2010 by decade, 2016–2026 annual, 2030–2100 by decade) | keep | Cheap SEO surface; year pages link back to it via `.hub-uplink`. |
| 12 locales | ar de en es fr it ja ko nl pl pt ru zh with localized slugs (/fr/japon/2026/, /ja/日本/2026/), hreflang, translated labels, RTL classes for Arabic | skip (v1) | Big effort; English-only is fine for a personal tool. |
| "Japan vs. other countries" | Outbound link to woatlas.com/compare/japan/united-states/ (same operator) which embeds the two capture PNGs side by side | **skip — this is the gap** | No in-site comparison exists at all. Your headline feature has no precedent here. |
| Migrants link | `/immigration-statistics/{lang}/{slug}/2024/` treemap of migrant stock by origin (HTML div treemap, years 1990–2024) | skip | Off-scope. |
| Other visualizations | population-size-per-country/2024 (ranked list), population-density/2024, population-projections/{slug+slug…}/ (multi-line chart, API `api/population-projections/?countries=903&countries=935`), migrants-stock-origin, hnp/population-growth/2015 (World Bank) | skip | Off-scope; the `slug+slug+slug` URL pattern for multi-entity selections is worth noting. |
| Mailing list | eepurl (Mailchimp) link | skip | — |
| Blog | One post (2017 "Declaration of intent"): started 2011, rewritten on Django+d3 April 2017, target audience = teachers/students. No feature announcements since. | skip | Confirms the site is in maintenance mode; the 2024-data narrative/age-shares features shipped silently (privacy policy dated 2026-04-01, so still maintained). |
| Ads (Raptive/AdThrive) | 18 ad containers, prebid + GPT + ~15 ID-sync vendors, sticky outstream video bottom-left (desktop) that overlaps the 0-4 / 5-9 rows, sticky footer + video on mobile | skip | Your tool is free/static; the ad-free experience is itself a differentiator. |
| Structured data | JSON-LD BreadcrumbList + Dataset (name, description, temporalCoverage 1950/2100, license CC BY 3.0 IGO, creator UN DESA Population Division, distribution = the PNG) | keep | Copy verbatim pattern; add `variableMeasured`. |
| What-is page + FAQ | Explains reading a pyramid, 3 classic shapes, bulges/notches (China 1961 famine, Germany WW), dependency, momentum; FAQ on sex ratio and data | keep (short) | One explainer page is worth having; link the shape classes to your similarity feature. |

## 2. Presentation details worth copying precisely

- **Unit:** each bar = sex-bin count / total population (both sexes) → male 0-4 for Japan 2026 = 1.6 %, female 1.5 %. Not "% of that sex". Sum of all 42 bars = 100 %.
- **Fixed x-domain 0 → 10 % per side** (`maleX = scaleLinear().domain([0,0.1])`, `femaleX.domain([0.1,0])`), 4 ticks each ("0% 2% 4% 6% 8% 10%"), centre tick "0%" bold. Niger's 8.6 % base and Japan's 4.0 % bulge sit on the same ruler. Only ~3 extreme entities (Niger 0-4 F 8.6 %, Qatar 30-34 M ~10.5 %) approach/exceed 10 %; consider clamping at 10 % with an overflow marker, or 12 %.
- **Male left, female right** (culture-standard); sex labels "Male"/"Female" 16 px at ¼ and ¾ width; **age labels on the LEFT edge only** (0-4 … 100+, `pp-y-axis`), youngest at bottom.
- **Bin labels:** `0-4, 5-9, … 95-99, 100+` (hyphen, no spaces; "100+" top). 21 bins matches your parquet's age_start 0..100 step 5.
- **Colors:** male `steelblue` (#4682B4), female `#EE7989` (salmon-pink); hover count text female `#DE5285`; ink/text `#12162D` (navy); axis/grid `#e5e5e5`, `#999`; age-shares lines: youth steelblue, working `seagreen`, elderly `#EE7989`; link hover `orange`. Font: system stack, 10 px sans-serif inside SVG, chart text fill #12162D.
- **Geometry:** margin {top 2, right 20, bottom 10, left 33}; `barHeight = containerWidth/25`, rects `barHeight-1` tall (1 px gap); SVG width = container (507 px desktop, 355 px mobile); `%` labels sit 3 px outside each bar end (text-anchor end/start).
- **Callouts:** total population (persons, comma-formatted) top-right; narrative gives median age, youth dependency (0-14 per 100 aged 15-64), old-age dependency (65+ per 100), 10-year change, shape class. Meta description repeats "Median age: 51.1 years".
- **Animation:** 750 ms d3 transition of bar widths/x and % labels on year/country change (`transitionDuration=750`); population line path also tweens 750 ms; first render is instant (no transition).
- **Tooltips:** row-level (whole-width invisible white `pp-hover-bar` rect as hit target — copy this: the hit target spans the full row, not just the visible bar). Age-shares chart: full-area `pointer-events:all` rect with crosshair + 3 value labels + year label.
- **Comparison overlays:** none exist. (For your tool: draw the comparison pyramid as an outline/step path over the filled bars, same fixed axis.)
- **Share PNG composition** (capture.png, 575×581): pyramid + bottom band with "PopulationPyramid.net" (white on navy) left and "Japan - 2026 / Population: 122,427,731" right. Good template for a client-side export.

## 3. Weaknesses / gaps a new tool can fix

1. **No comparison of any kind** — no overlay, no side-by-side, no "similar/different", no diff vs. same country other year. (Headline opportunity.)
2. **Year navigation is clumsy:** ±1/±5 spans + click-on-line-chart; no slider, no play/animate through 1950-2100, no keyboard, no touch drag. Every step = JSON fetch + full-page HTML refetch (~110 KB gz) to swap narrative text.
3. **Hover destroys the bars** (opacity 0) to show counts; no persistent readout; no sex-ratio or cohort-size display.
4. **Percent-only.** No absolute-count mode, no "% of sex" mode, no 1-year ages, no custom bin merge, only the medium variant (WPP2024 also has low/high/constant-fertility etc.; your bulk CSVs may include them).
5. **Page weight & noise:** 415 KB HTML (104 KB gz) with 211 KB d3 + 22 KB data + country lists inlined twice; ~190 requests; Raptive ad stack; sticky video overlays the pyramid's lowest rows on desktop; mobile loses ~30 % of viewport to sticky ads. A static Svelte build with a 50 KB gz data pack per entity would be an order of magnitude lighter.
6. **Accessibility:** SVG has no role/title/aria, no data table, `.inc-button` are `<span>` (tabIndex -1), letter links have empty `href`, no sr-only text, no reduced-motion handling. Region ⓘ icons DO handle focus (good).
7. **Aggregates mixed with countries** in pickers; no flags/ISO codes; no "recently viewed"; search is substring on `innerHTML`.
8. **No context metrics beyond the narrative:** no sex ratio, no cohort bulge/notch annotation, no historical events, no comparison to region/world average.
9. **Stale ancillary data** (migrant stock 2013 rev on Sources, CO2 from CDIAC 2016) and the Sources page is a bare list; blog dead since 2017.
10. **Embed page** ships the full d3 bundle and lays out badly outside its iframe.
11. **SEO oddities:** sitemap index of 47×5000 URLs but year pages only link to the hub + 2024 migrants; case-sensitive slugs (`/Japan/2026/` 404), no alias slugs (`/usa/` 404); `/api/` and `/embed/` disallowed in robots.txt.

## 4. Data endpoints and schemas (all GET, `cache-control: max-age=3600`, Cloudflare, no CORS headers observed, robots-disallowed)

Entity id = UN M49 numeric code (Japan 392, Niger 562, Qatar 634, Rep. Korea 410, USA 840, China 156, World 900; aggregates 900–957 plus 5500 Central Asia, 5501 Southern Asia; "Other non-specified areas" = 158 i.e. Taiwan). 236 entities = 201 countries/areas + 35 aggregates (`entities.json`). Values are **thousands** (floats).

- `GET /api/pp/{id}/{year}/` → `{"male":[{"k":"0-4","v":1968.2585},…21 bins…,{"k":"100+","v":18.413}],"female":[…],"populationFormatted":"122,427,731","population":122427.731}`. Out-of-range year (2101) → 200 with empty arrays and population 0. Content-type application/json, 1.4 KB.
- `GET /api/pp/{id}/{year}/?excel=true` → xlsx, `Content-Disposition: attachment; filename="Japan-2026.xlsx"`, one sheet, header `Age | M | F`, 21 rows, integer persons (1968258, 1879422 …).
- `GET /api/pp/{id}/{year}/?csv=true` → text/csv `Age,M,F` same rows (undocumented; `?format=csv` is ignored).
- `GET /api/pg/{id}/` → `[{"y":1950,"p":86443.2765},…,{"y":2100,"p":…}]` 151 annual totals (thousands).
- `GET /api/ageshares/{id}/` → `{"years":[1950,1955,…,2100] (31), "youth":[35.2,…], "working":[59.9,…], "elderly":[4.9,…]}` percentages, 1 dp.
- `GET /api/population-projections/?countries=903&countries=935` → `{"population-lines-container2":[{name,code,values:[{year,value}]}], "country-list-picker-container":{"allCountries":[{translation,code,slug}]}}` (the multi-country projections page; the `allCountries` list is a handy id/slug/name dump).
- Other: `api/population-size-per-country/`, `api/hnp/`, `api/migrants-treemap/`, `api/migrants-treemap-excel/` (built from `vizData['API_URL'] + '?' + serialize(args)`).
- Same data is also inlined in every page: `var json = {...}` (current pyramid), `var pgJSON`, `var ageSharesJSON`, `var regionMembers` (35 aggregates → member names), `var woatlasSlugMap`.
- Image capture: `https://images.populationpyramid.net/capture/?selector=%23pyramid-share-container&url=https%3A%2F%2Fwww.populationpyramid.net%2F{slug}%2F{year}%2F%3Fshare%3Dtrue` → PNG 575×581 (49 KB); `?share=true` serves the page ad-free for the headless capturer.
- Cross-check vs. Eli's parquet: 236 entities here vs 237 in `wpp2024_population_age5.parquet` (WPP2024 "PopulationByAge5GroupSex" has 237 locations incl. e.g. Holy See/Kosovo-less variants; expect ≥1 extra like "Vatican" or an SDG group). Japan 2026 M 0-4 = 1968.2585 thousand — match this against the parquet to confirm identical vintage (July 2024 release).

## 5. Attribution / licensing text (verbatim)

- Footer on every page: `© 2026 by PopulationPyramid.net, made available under a Creative Commons license CC BY 3.0 IGO: http://creativecommons.org/licenses/by/3.0/igo/`
- Under the age-shares chart: `Data source: United Nations World Population Prospects, 2024 revision (medium variant) — last updated July 2024.`
- Sources page: `United Nations, Department of Economic and Social Affairs, Population Division. World Population Prospects: The 2024 Revision. (Medium variant)` (+ UN migrant stock POP/DB/MIG/Stock/Rev.2013; CDIAC CO2 2016).
- JSON-LD Dataset: `"license": "https://creativecommons.org/licenses/by/3.0/igo/"`, `"creator": {"@type":"Organization","name":"United Nations, Department of Economic and Social Affairs, Population Division"}`.
- Embed page footer: `Source: https://www.populationpyramid.net`; capture PNG banner: `PopulationPyramid.net`.
- FAQ: "All pyramids on this site are drawn from the United Nations World Population Prospects, 2024 revision (medium variant)…"
- Note: CC BY 3.0 IGO is the UN's own licence for WPP; the site simply passes it through. Your tool should credit "United Nations, DESA, Population Division (2024). World Population Prospects 2024, Online Edition. Licensed under CC BY 3.0 IGO" — attribution to populationpyramid.net is only needed if you reuse their derived content/images.

## 6. URL design worth mirroring

- `/{slug}/{year}/` — lowercase kebab slug of the UN name (`republic-of-korea`, `united-states-of-america`, `china-hong-kong-sar`→ check), 4-digit year 1950–2100 (any year valid, 2027 works, 1949 → 404); trailing slash canonical (no-slash 301s). Case-sensitive, no aliases.
- `/{slug}/` — hub = current year, canonical, `<title>Japan Population Pyramid (1950–2100)</title>`, contains the "by year" link block; every year page links up to it.
- `/{lang}/{localized-slug}/{year}/` for 11 non-English locales; `/en/…` 301s to root; full `hreflang` set incl. `x-default`.
- `<title>Japan Population Pyramid 2026 | PopulationPyramid.net</title>`; `og:title` "Japan Population Pyramid 2026"; `og:image` = capture PNG; meta description = "A population pyramid shows the age and sex distribution of a population. Japan in 2026: total population 122,427,731. Median age: 51.1 years. Interactive charts from 1950 to 2100."
- H1 = "{Name} Population Pyramid {Year}", H2 = "{Name} in {Year}", H3 = "Share of the population by age group, 1950–2100".
- pushState keeps the URL in sync while stepping years (state = {slug, year, countryId, countryName}); back/forward handled via `onpopstate`.
- Multi-entity selections encoded as `slug+slug+slug` path segment (projections page) — a good pattern for `/compare/japan+niger/2026/` or `/japan/2026/vs/niger/2026/`.
- Sitemap: index → 47 files × 5000 URLs; per entity hub + years {1950,1960,1961,1962,1970,1979,1980,1990,2000,2005,2010,2015–2026 annual,2030–2100 by 5} across locales. For a static Svelte site, pre-render hub + a sparse year set and hydrate the rest client-side.
- Suggested additions for the new tool: `/{slug}/{year}/?mode=abs|pct`, `/{slug}/{year}/similar?scope=same-year|±10|any`, and hash state for hover/selected bin.

## 7. Implementation notes (for reference)

- Backend Django (`/en/jsi18n/` catalog, blog post confirms), Cloudflare in front, `cf-cache-status: DYNAMIC`, HTML 415 KB raw / ~104 KB transferred; 11 `<script>`s, d3 v4 UMD inlined (211 KB), page script 22 KB, pyramid/graph code 22 KB, inline `<style>` 18 KB; no external CSS; GA4 `G-8DGP7KMNP3`; Cloudflare RUM + bot challenge.
- Rendering: `document.querySelectorAll('svg').length` = 9 on a country page, of which 3 are charts: pyramid (`#pyramid-container > svg` → `g#pp-graph` → 21 × `g.pp-hbar` each with `rect.pp-hover-bar`, `rect.pp-male`, `rect.pp-female`, `text.malePercentage`, `text.femalePercentage`; plus two `g` x-axes and `g.pp-y-axis`), `svg#pg-chart` (population line, 151 invisible `rect.pg-mouseover-rect` hit columns), age-shares svg. No canvas.
- Responsive breakpoints: 1050 px (two-column → stacked), 768 px, 450 px, 400 px; `#pyramid-share-container` 50 % width desktop, 100 % below 1050. Mobile (375 px): pyramid 355 px wide, 14 px bars, all labels legible, population graph x-labels rotated 45°, order pyramid → links → population graph → year → country → narrative → age-shares.
- Ads: `adthrive` sticky outstream video bottom-left overlaps rows 0-4/5-9 of the pyramid at 1280×720; Raptive footer ad; `ESNF` errors logged for missing ad placement selectors.
