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
