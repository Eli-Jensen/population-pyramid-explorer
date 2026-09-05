# SMOKE.md — the browser checklist

Pure-function behaviour (router, URL canonicalisation, era rules, shard decoders, feature math) lives in
vitest (`cd web && npm test`). This file covers only what needs a real browser, per `docs/PLAN.md` §10:
one numbered list per milestone, each item with its URL and the expected text, run through the in-app
Browser pane (or any browser) before the milestone is called done. `make smoke` prints this file.

## How to run

- Dev server: `cd web && npm run dev` → `http://localhost:5173/population-pyramid-explorer/`.
  The Browser pane launch config `dev` (`.claude/launch.json`) does the same — but the pane reads the
  launch.json of the *session root*, so when the session is opened one level up, start Vite yourself and
  attach the pane by URL.
- Production build: `cd web && npm run build && npx vite preview --port 4174 --strictPort` →
  `http://localhost:4174/population-pyramid-explorer/` (serves `dist/`, including the `404.html` SPA
  fallback — `/USA/` must resolve here too).
- Deployed: `https://<user>.github.io/population-pyramid-explorer/…` (GitHub Pages; the same paths).
- Reference numbers: `uv run python scripts/query.py JPN 2026` — the header line carries the stage and
  median age; `web/src/data/entities.json` carries `pop_2026` and `axis_pct`.
- The current year is the *client clock* (`/japan` → `/japan/2026` today, `/japan/2027` next year).

Legend: **PASS** verified in the run named in the section heading · **NOT RUN** needs a real device or the
deployed site · dispatched events are noted where the pane was hidden (it cannot draw pointer gestures).

## M1 — country page (run 2026-09-04, Chrome Browser pane, dev :5173 + preview :4174)

| # | Step | URL | Expected | Result |
|---|------|-----|----------|--------|
| 1 | First paint | `/japan/2026` | Header `🇯🇵 JPN Japan 2026 nowcast`, `122,427,734 people`; pyramid with 42 bars, male left (blue) / female right (magenta), youngest at the bottom, fixed 0–10 % axis; readout strip defaults to the modal band `50–54` (`4,933,725 · 4.03%` / `4,866,472 · 3.97%` / `101 males per 100 females`); callouts `51.1 years`, youth `19 per 100`, old-age `51 per 100`, `−3.7% since 2016`, `Constrictive`; "In words" paragraphs; age-shares chart with tooltip `2026 · nowcast`. | PASS |
| 2 | First-paint network | same | `read_network_requests`: besides the JS/CSS (entities + meta are bundled), exactly `pyramids.*/JPN.u16`, `years.*/2026.u16`, `bands_default.*.bin`. No `shares.*.d16z`, no `totals.*.f32`, no `bands.*.bin`. | PASS |
| 3 | Numbers match the pipeline | same | `uv run python scripts/query.py JPN 2026` header: `stage constrictive, median age 51.1`; population equals `entities.json` `pop_2026` × 1000 = 122,427,733 (page shows the float32 total, 122,427,734). | PASS |
| 4 | Drag the scrubber | same | While dragging, the URL follows the year (`/japan/1990`) with **replaceState only** — `history.length` unchanged; the header year, pyramid and callouts update live. | PASS (dispatched `input` ×3) |
| 5 | Release | same | Exactly **one pushState** (`history.length` +1) at the released year; the year shard for that year is fetched. **Back** returns to the pre-drag year (`/japan/2026`). | PASS |
| 6 | Keyboard on the slider | same | Focus the range: `→`/`←` ±1 year, one pushState each; `⇧→`/`⇧←` ±5 (`/japan/2031`); `Home`/`End` → 1950/2100; `−5 −1 +1 +5` buttons do the same. | PASS (`→` native key, `⇧` dispatched) |
| 7 | Play / pause | same | `▶` steps 6 yr/s (×1/2/4) with replaceState only (no history growth), button reads `Pause` / `aria-pressed=true`; `❚❚` pushes one entry; the polite live region announces `Year 2028, projected` at most twice a second. | PASS (1 yr/s in the hidden pane — background-tab timer throttling) |
| 8 | Axis menu | `/japan/2029` | `fit entity (10 %)` default; `pin 10 %` → `?axis=pin10`; `never clip (0–17 %)` → `?axis=noclip` with ticks `4 8 12 16 %`; back to fit clears the query. All replaceState (no history growth). | PASS |
| 9 | Unit toggle | same | `people` → `?unit=abs`, ticks `2.4M 4.9M 7.3M 9.8M 12.2M`, bar-end labels in persons, sr-only table cells `1,927,573`; `% of sex` → `?unit=pctsex`, ticks `4 … 21%`; the bar **geometry does not change** (same path `d`). | PASS |
| 10 | Readout | same | Hover/tap a row → `Age band 0–4 · Male 1,927,573 · 1.60% · Female 1,843,127 · 1.53% · Sex ratio 105 males per 100 females`; `↑`/`↓` on the focused pyramid walk the bands. | PASS (dispatched `pointerenter` / `click`) |
| 11 | Hub redirect | `/japan` | replaceState to `/japan/{currentYear}` (`/japan/2026`), one history entry for the navigation only; title `Japan 2026 · Population Pyramid Explorer`. | PASS |
| 12 | Alias + trailing slash | `/USA/` | replaceState to `/united-states/2026`; subtitle `United States of America · 349,035,500 people`; median `39.7`, `Stationary`. Also `/jpn`, `/United-States-Of-America/2026` (vitest). | PASS |
| 13 | Fit axis 12 % | `/niger/1990` | Chips `NER` · `observed`; axis `fit entity (12 %)` with ticks to `12%` and no clip note (the 0–4 bars ≈ 8.6 % fit); median `16.5`, `Expansive`, `+35.0% since 1980`, `8,286,059 people`. | PASS |
| 14 | Fit axis 17 % | `/qatar/2026` | Axis `fit entity (17 %)`, ticks `4 8 12 16 %`, no clip; male 35–39 bar `12.2%` (readout `388,227 · 12.23%`, `329 males per 100 females`); median `34.4`, `Stationary`; narrative `Men outnumber women 3.15 to 1 at working ages…`. | PASS |
| 15 | Pasted link reproduces | `/qatar/2026?axis=pin10&unit=abs` | `pin 10 %` selected, `people` pressed; clamp markers `▸377.9K` / `▸388.2K` with the note `▸ marks a bar longer than the 10% axis (clamped)…`; ticks `63.5K … 317.4K`. | PASS |
| 16 | Aggregate | `/world/2050` | Chips `world` · `projected`; `ⓘ 237 members` disclosure; `9,662,754,000 people`; median `37.1`, `Stationary`; caveat `Figures after 2023 are UN medium-variant projections — distant years converge…`; no flag glyph. | PASS |
| 17 | Unknown slug | `/atlantis/1999` | `Nothing here` view: `/atlantis/1999 is not a country, region or year we know…`, picker, `← Home`; title `Not found · …`. | PASS |
| 18 | Dark mode | `/japan/2026`, colour scheme dark | Body `#0d0d0d`, cards `#1a1a19`, male `#3987e5`, female `#d55181`, muted ticks legible, no unstyled white blocks. | PASS |
| 19 | Light mode | same, colour scheme light | Body `#f9f9f7`, cards `#fcfcfb`, text `#0b0b0b`, male `#2a78d6`, female `#e87ba4`. | PASS |
| 20 | Mobile 375 px | `/qatar/2026`, mobile preset | No horizontal scroll (`scrollWidth == innerWidth`); single column: header, picker, unit + axis controls, pyramid in **compact layout** (viewBox 400×520, labels ≥ 11 px tall), readout 2×2, scrubber with 32 px buttons, callouts, prose, age shares. | PASS |
| 21 | Console | every page above | No errors or warnings (Vite's `connecting…/connected` only). | PASS |
| 22 | Reduced motion | any country page, `prefers-reduced-motion: reduce` | `▶` disabled with title `Play is off because your system prefers reduced motion`; no bar tween on year change. | NOT RUN — the pane cannot emulate the media query; toggle macOS Accessibility → Reduce motion in a real browser |
| 23 | Deployed site | `curl -sI https://<user>.github.io/population-pyramid-explorer/data/wpp2024/shares.<sha8>.d16z` | `content-type: application/octet-stream`, body starts `1f 8b`; on the site the tier-3 loader's sniff branch is `gzip-stream` (or `inflated-body` if a proxy inflates — both are accepted). | NOT RUN — deploy pending (Pages needs the repo public or a Pro plan) |

### M1 measurements (production build on `vite preview`, localhost, M4 Max, Chrome; pane hidden — paint entries do not fire in a hidden tab)

| what | value |
|------|-------|
| First-paint bytes on the wire (`/japan/2026`) | **113.4 KB** vs the 175 KB budget: JS 57.1 KB gz (211 KB raw; `entities.json` 16.3 KB gz + `meta.json` 2.3 KB gz are inside it), CSS 5.2 KB gz, `JPN.u16` 11.2 KB gz (13.3 KB raw), `2026.u16` 20.5 KB gz (24.6 KB raw), `bands_default.*.bin` 19.3 KB (served uncompressed by `vite preview`; 14.3 KB if the host gzips it), HTML 0.9 KB |
| Entity shard → paint | shards `responseEnd` 40–43 ms after navigation start (dev server: 31–33 ms); the pyramid DOM (45 paths) is built in the same task, so ≈ 45–50 ms to pyramid on localhost. Phone numbers (real iPhone Safari + mid-range Android) still to be taken against the deployed site — PLAN §10 |
| Year change while scrubbing | synchronous update (Svelte flush + style/layout) per `input` event: median **1.0 ms**, p90 2.9 ms, max 10.6 ms (dev build: 10.1 / 12.7 / 18.6 ms) — comfortably inside a 16.7 ms frame |
| Blob fetch + decode (tier 3) | not on the M1 path; the vitest integration run reports `loadCorpus_total` 28 ms in node (7 ms gunzip + 5 ms delta decode) |

### Fixes made during the M1 run

- Age-shares tooltip called nowcast years (2024–2026) `projected`; now `nowcast` / `projected` by era, matching the header chip.
- Pyramid labels were ~5 px on phones (640-unit viewBox scaled to ~309 px); a compact layout (viewBox 400 wide, 22-unit rows, 12-unit type) kicks in under 480 px.

## M2 — twins, opposites, time-shift (run 2026-09-04, Chrome Browser pane, production build on `vite preview` :4174; pane hidden → DOM/network/console-verified)

Reference numbers: `uv run python scripts/query.py JPN 2026` · `… JPN 2026 --sex 1` · `… JPN 2026 --mode any [--era all]` ·
`… JPN 2050 --mode any` · `… CHN 1990 --mode today --trend motion --L 10` · `… KOR 2026 --mode any` ·
`… JPN 2026 --k 10 --div 2` · `… JPN 2026 --metric visual:siglip2-base-naflex --emb evals/embeddings/siglip2-base-naflex.pca64.npy`.
Every id, year, `d`, raw rank and band below was compared with those outputs (the TS engine is fixture-tested against the
same Python in `web/src/lib/search.integration.test.ts`). The pane was hidden for this run: text, URLs, network, computed
styles and timings come from `javascript_tool` / `read_network_requests` / `read_console_messages`; pixel checks are NOT RUN.

| # | Step | URL | Expected | Result |
|---|------|-----|----------|--------|
| 1 | Same-year twins + opposites | `/japan/2026` | Sentence `5 most similar and 5 most different pyramids of 2026 · countries ≥ 100k · excluding Japan · Shape`. Twins Italy `d 0.34 · close · 6 % · #1`, Greece `0.43 · 10 %`, Portugal `0.44 · 11 %`, Puerto Rico `0.53 · 17 %`, Spain `0.54 · 18 %`, each with `similar because Alike in …`, `differs in Differs most in 65+ share (30.2 % vs 25.6 %)`, `Only 1.93 years of average age movement separate them` and `L2 0.21 + W1 0.13`. Opposites (balanced) Central African Republic `3.75 · extreme · 99.8 % · #1 farthest`, Qatar `3.74 · #2`, Chad `3.54 · #3`, Niger `3.53 · #4`, **Oman `3.14 · #27 farthest`**; headline `Japan 2026 vs Central African Republic 2026: farther than 99.8 % of random pairs`; strip `strictly farthest: Central African Republic, Qatar, Chad, Niger, Somalia`. | PASS |
| 2 | First-paint network | same | Besides JS/CSS/HTML exactly `years.*/2026.u16`, `bands_default.*.bin`, `pyramids.*/JPN.u16` — no `shares.*.d16z`, `totals.*.f32`, `bands.*.bin`, `emb/*`. Footer `198 candidate rows · year shards · 3.1 ms`. | PASS |
| 3 | Distinctiveness chip | `/japan/2026`, `/south-korea/2026`, `/china/1990` | Header chip `more isolated than 91 % of countries this year` (tooltip names the metric); South Korea `86 %`; China 1990 `82 %`; Japan under `metric=visual` `69 %`. | PASS |
| 4 | Total only | `/japan/2026?sex=1` | `More` auto-opens, `Total only` pressed, sentence ends `· total only`. Twins Italy `0.37`, Portugal `0.45`, Greece `0.46`, Puerto Rico `0.51`, Martinique `0.59`; opposites become Sahel: Central African Republic `4.24`, Chad `3.99`, Somalia `3.98`, Niger `3.97`, Uganda `#7 farthest 3.87`; strip `… Central African Republic, Chad, Somalia, Niger, Mali`. | PASS |
| 5 | Any year (observed) | `/japan/2026?mode=any` | Skeleton (5 pulsing cards) until `shares.*.d16z` + `totals.*.f32` + `bands.*.bin` land — fetched **once**; label `Any year (1950–2026)`; twins unchanged (Italy 2026 … Spain 2026 — Japan's 2026 twins are all same-year); own-trajectory row `Japan's closest other year: 2021 (−5 y) · very close · 2 % · d 0.28`; opposites `United Arab Emirates 1979 (−47 y) 4.59`, `Qatar 2008 (−18 y) 4.57`, `Niger 1950 (−76 y) 3.89`, `Kuwait 1966 (−60 y) #6`, `Macao 1965 (−61 y) #14`; strip `… United Arab Emirates, Qatar, Niger, Rwanda, Kenya`; footer `14,626 candidate rows · all years`. | PASS (the skeleton phase lasts < 300 ms on localhost with a warm HTTP cache; the caption `loading all years… 1.6 MB` is the same string the time-shift panel shows in step 12) |
| 6 | Include projections | `/japan/2026?mode=any&era=all` | `Any year (1950–2100)`; sentence ends `· projections included`; chip `projections included · hide`; twins Latvia `2066 (+40 y) · projected · very close · 0.4 % · 0.15`, Thailand `2058 (+32 y)`, Grenada `2068 (+42 y)`, North Macedonia `2066 (+40 y)`, Croatia `2060 (+34 y)`, every card with the `projected` badge; own row `2031 (+5 y)`; opposites as in step 5; `29,239 candidate rows`. | PASS |
| 7 | J8: query from a projected year | `/japan/2050?mode=any` | `Today (2026)` segment appears; `Any year (1950–2100)`; sentence `… · projections included`; under More the chip is inverted: `projections included (query is a projection) · observed only`. Twins Spain `2053 (+3 y) 0.12`, Uruguay `2086 (+36 y) 0.16`, Italy `2050 0.16`, Latvia `2091 (+41 y) 0.17`, Thailand `2085 (+35 y) 0.18`; opposites UAE 1979 `#1`, Qatar 2008 `#2`, Niger 1950 `#4`, Kuwait 1966 `#10`, Macao 1965 `#15`; own row `2055 (+5 y)`. | PASS |
| 8 | J8: `observed only` | click the chip's action | URL → `?mode=any&era=obs` (kept: it is not the default for 2050); chip `projections hidden (74 years) · include`; `Any year (1950–2026)`; sentence `… · observed years only`; twins Italy / Portugal / Greece / Puerto Rico / Germany `2026 (−24 y)` (nowcast badges); own row `2026 (−24 y) · close · 7 %`; `14,626 candidate rows`. | PASS — **fixed in this run**: `search.ts candidateMask`/`toResults` flipped an explicit `obs` back to `all` for projected query years (Python-CLI semantics); the engine now takes the resolved era and `router.effectiveEra` owns the J8 default (vitest: synthetic + real-corpus cases) |
| 9 | Today + trend | `/china/1990?mode=today&trend=motion&L=10` | replaceState to `?mode=range&from=2026&to=2026&via=today&trend=motion` (`L=10` is the default → elided); `Today (2026)` pressed; network `years.*/{1980,1990,2016,2026}.u16` + `bands.*.bin`, no blob; sentence `… pyramids of 2026 (today) · … · trend (motion, 10 y)`; twins Ethiopia `1.18 · typical · 41 %`, Bangladesh `1.25`, Timor-Leste `1.29`, Eritrea `1.29`, Djibouti `1.29` with `movement, focal vs this U15 −7.3 vs −3.8 pts · 65+ +1.0 vs +0.4 pts · median age +3.1 vs +2.0 y · WA sex ratio −0.01 vs +0.00`; opposites Qatar `3.41`, Maldives `3.41`, Oman `3.04`, Mongolia `2.99`, Macao `2.76`; metric select disabled while trend is on; footer `198 candidate rows · year shards · 1.0 ms`. | PASS |
| 10 | Visual metric | `/japan/2026?metric=visual` | `emb/siglip2-base-naflex.*.f16` (4.96 MB) fetched once; select shows `Visual (experimental: what a vision model thinks looks alike)`, option tooltip ends `— evaluation: rejected`; sentence `… · Visual (experimental)`; twins Hong Kong `0.14 · very close · 3 %`, Puerto Rico `0.18`, Martinique `0.19`, Slovakia `0.20`, Taiwan `0.21`; opposites Kazakhstan `1.74`, South Africa `1.74`, Tajikistan `1.73`, Djibouti `#9`, Botswana `#10`. | PASS |
| 11 | k + diversity | `/japan/2026?k=10&div=2` | Sentence `10 most similar and 10 most different pyramids of 2026 · … · spread opposites`; 10 twins (… Finland `#8`, Bosnia and Herzegovina `#9`, Bulgaria `#10 · 23 %`); opposites CAR `#1`, Qatar `#2`, Somalia `#5`, Afghanistan `#10`, Mayotte `#20`, UAE `#24`, Oman `#27`, South Sudan `#37`, Equatorial Guinea `#44`, Saudi Arabia `#50 · far · 95 %`; strip lists the strict ten. In-page: `Results 10` → `&k=10`, `strict` → `&div=0` and the cards equal the strip (UAE, Qatar, Niger, Rwanda, Kenya on `/japan/2026?mode=any&era=all`), `spread` → `&div=2` (… Kuwait, Macao), `balanced` elides `div`. | PASS |
| 12 | Time-shift panel | `/south-korea/2026`, open `South Korea 2026 across time` | Opening fetches `shares.*.d16z` (0 → 1 request) with `loading all years… 1.6 MB`; rows `Taiwan 2026 ±0 y 0.226 close`, `Spain 2026 0.342 typical`, `Italy 2022 −4 y 0.377`, `Jersey 2026`, `Austria 2026`, `Slovenia 2025 −1 y`, `Germany 2023 −3 y`, **`Japan 2008 −18 y 0.435`**, `Bosnia and Herzegovina 2026`, `Greece 2025 −1 y`; `show all 200`; edge rows read `not reached before 1950` (Gabon, Equatorial Guinea, Benin, CAR, Uganda: −76 y) and `not reached before 2015` (US Virgin Islands — below the 100k floor before 2015); the Japan row links to `/japan/2008`. | PASS |
| 13 | Reset | `/japan/2026?k=10&div=2` → Reset | URL → `/japan/2026` via replaceState (`history.length` unchanged), sentence back to the default, 5 cards, Reset disabled. | PASS |
| 14 | Shared URL reproduces the view | `/japan/2026?mode=near&n=5&metric=w1&sex=1&k=3&minpop=1000000&scope=all` | Canonical order `?mode=near&n=5&scope=all&minpop=1000000&metric=w1&sex=1&k=3`; `Within ±N` pressed with `± 5 y`, selects `countries + regions` / `1M` / `Age-shift (years)`, `Total only`, `3`; sentence `3 most similar and 3 most different pyramids of 2021–2026 · countries and regions ≥ 1M · excluding Japan · Age-shift (years) · total only`; twins Italy 2026, Hong Kong 2026, Greece 2026; `1,206 candidate rows`. | PASS |
| 15 | Keyboard | `/japan/2026`, More open | The section holds 27 native controls (`button`/`select`/`input`/`a`/`summary`), none with `tabindex=-1`, only Reset disabled at defaults; 3 `:focus-visible` rules in the stylesheet. | DOM-verified; real Tab keystrokes are NOT RUN (the hidden pane does not deliver key events — `activeElement` stayed `BODY`) |
| 16 | Dark / light | `/japan/2026`, colour scheme dark | Body `#0d0d0d`, cards `#1a1a19`, text `#fff`, muted `#898781`, male `#3987e5`; close-band chip border = `--wa` at 60 %, far/extreme = `--u15`. Light as in M1. | PASS (computed styles) |
| 17 | Mobile 375 px | `/japan/2026?mode=any`, mobile preset | No horizontal scroll (`scrollWidth == innerWidth`); one card per row (343 px); year-mode segments wrap; segment buttons 28 px tall, More/Reset 32 px, era action link ≥ 24 px (padded in this run — was 20 px). | PASS |
| 18 | Console | every page above | No errors, no warnings. | PASS |
| 19 | Pixels: mini pyramids with the focal ghosted, DiffBars highlights, band chip colours, projected/nowcast badges, skeleton pulse | `/japan/2026`, `/south-korea/2026?mode=any` | Candidate bars filled, focal outline behind at a shared axis; accent columns on the top bins; green-ish border for close bands / orange for far. | NOT RUN — pane hidden (only the pre-scroll header screenshot paints; needs a visible pane) |
| 20 | Scrub with results | `/japan/2026`, drag the slider | Cards re-rank ≤ 30 ms after the slider settles (`searchYear` trails `year`); one year shard per settled year; no history growth during the drag. | NOT RUN in browser (vitest covers the debounce and the shard fetches) |

### M2 measurements (production build on `vite preview`, localhost, M4 Max, Chrome; pane hidden)

| what | value |
|------|-------|
| First-paint bytes on the wire (`/japan/2026`) | **134 KB** vs the 175 KB budget: JS 78.2 KB gz (278 KB raw — +21 KB over M1 for search/bands/explain + the result components), CSS 5.4 KB gz, HTML 0.6 KB, `2026.u16` 20.1 KB gz, `JPN.u16` 10.8 KB gz, `bands_default` 19.0 KB (uncompressed by `vite preview`; 14.3 KB if the host gzips it → 129 KB). Still tier 1 only: no blob, no `bands.bin`, no embedding |
| Same-year search (198 rows: scan + dedupe + MMR + 10 explanations) | **3.1–3.9 ms**; trend/motion over year shards 1.0 ms; visual 1.7 ms |
| Any-year scan + MMR (29,239 rows, `era=all`; footer `ms`, main thread) | **cold 157 ms** (first evaluation after the blob lands — includes JIT warm-up), **warm 24–44 ms** on k / diversity changes. 14,626 rows (`era=obs`): cold 126–134 ms. Before this run's single-scan refactor (`search.ts search()` — one distance pass instead of `similar` + `different` + `distances` for the own-trajectory row) the same page read 248–380 ms cold / 54–98 ms warm |
| Blob fetch + decode (tier 3, `shares.*.d16z` 1,589 KB + `totals.*.f32` 154 KB) | fetched **59 ms** cold (11–14 ms from the HTTP cache), decoded **74–117 ms** wall time (`DecompressionStream('gzip')` + delta decode; path `gzip-stream`) — now printed in the results footer as `all-years blob 1.6 MB fetched in … ms, decoded in … ms (gzip-stream)` |
| Embedding (tier `emb`, 4.96 MB) | 109 ms fetch on localhost |
| PLAN §8 Worker rule (100 ms of main-thread time) | Warm any-year searches sit at 24–44 ms and the same-year path at ≤ 4 ms, but the **cold** any-year evaluation (157 ms) and the blob decode (74–117 ms wall, mostly the off-thread gunzip) exceed the rule on this desktop; the rule was written for the phone measurements (PLAN §10 M1), which are still open. Decision deferred to those numbers — `search.ts` stays pure functions over typed arrays, so a `search.worker.ts` needs no rewrite |
