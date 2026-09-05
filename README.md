# population-pyramid-explorer

Find any country's demographic twins and opposites. A population-pyramid explorer
built on the UN World Population Prospects 2024 (medium variant, 1950–2100) with a
headline feature no other pyramid site has: **similarity search by shape**, with
adjustable constraints (same year, a range of years, or any year), plus "most
different", time-shift matching ("South Korea 2026 ≈ Japan 2005") and
**trajectory matching** — which country is on the same 5/10/20-year path
(`--trend motion` compares the change in shape, `--trend path` the aligned snapshots).

Status: **M0 done, M1 built** — the country page (`/{slug}/{year}`) runs locally against the
committed shards and passes the browser checklist in [SMOKE.md](SMOKE.md); the GitHub Pages
deploy is the remaining M1 step. Plan in [docs/PLAN.md](docs/PLAN.md); research behind it in
[docs/research/](docs/research/).

## Layout

- `src/pyramid_explorer/` — Python pipeline (uv, Python 3.12): ingest → shares → shards, metrics, search, evaluation, rendering + image embeddings.
- `scripts/` — `fetch_data.py`, `build_data.py`, `eval_similarity.py`, `render_canonical.py`, `embed_images.py`, …
- `web/` — Svelte 5 + Vite static site (GitHub Pages). Built data snapshots live in `web/public/data/` and are committed.
- `evals/` — pre-registered protocol, frozen external label sets, results.
- `docs/` — the plan and the research reports.

## Develop

Everything runs through the `Makefile` (`make help` lists targets):

```bash
make setup            # python (uv) + web (npm) dependencies
make data             # copy/fetch raw inputs: WPP 2024 + Togo update + LOCATIONS; Maddison, PWT, WDI + OGHIST income
                      # classes (all shipped, CC BY 4.0) and IMF WEO (build-time only, never exported)
make build            # rebuild the DuckDB store, corpus, web shards and build report
make test             # fast pytest (make test-slow for the full-corpus checks, make test-all for everything)
make query Q="JPN 2026"                                      # twins, opposites, time-shift table
make query Q="CHN 1990 --mode today --trend motion --L 10"   # who is on China-1990's 10-year path today
make sql Q="SELECT count(*) FROM pyramid"                    # read-only SQL against data/processed/explorer.duckdb
make web              # vite dev server → http://localhost:5173/population-pyramid-explorer/
make web-check web-test web-build                            # svelte-check + tsc · vitest · production build (+ 404.html)
make smoke            # print SMOKE.md, the browser checklist run before a milestone is called done
make deploy           # gate (check/test/build) then push main → GitHub Pages via .github/workflows/deploy.yml
```

The web gate that must stay green before any push is
`cd web && npm run check && npm test && npm run build`. The Browser pane launch config `dev`
(`.claude/launch.json`) starts the same Vite server; the pane reads the launch.json of the *session
root*, so when a session is opened one directory up, start Vite yourself and attach the pane by URL.

`make data` copies raw files from a sibling `pyramid-econ` checkout when present
(`WPP_FROM=` / `ECON_FROM=` or `PYRAMID_ECON_ROOT`), else downloads them; every
file is sha256-pinned in `pipeline/*manifest.json`. `make m0` runs the whole
M0 chain (data → build → test → render → embed → eval → build-emb).

## Web

`web/` is a Svelte 5 (runes) + Vite 8 + TypeScript 6 + Tailwind v4 single-page app, hand-written SVG,
no chart library, no server. It is a GitHub Pages **project site**, so Vite's `base` is
`/population-pyramid-explorer/` (`VITE_BASE=/ npm run build` for a root deploy); every route and fetch
goes through `import.meta.env.BASE_URL`, and `404.html` is a copy of `index.html` so deep links work.

**Routes.** `/` home (search, "continue with…", start with World / your country) ·
`/{slug}` → `/{slug}/{currentYear}` (client clock, `replaceState`) · `/{slug}/{year}` the country page,
1950–2100. Slugs are case-insensitive and accept ISO3, ISO2 and aliases (`/USA/`, `/jpn`,
`/united-states-of-america/2026` all `replaceState` to the canonical `/united-states/2026`). Display
options ride in the query with defaults elided: `?axis=pin10|noclip` (default `fit` = the entity's
build-time `axis_pct`) and `?unit=abs|pctsex` (default `% of total`). Year scrubbing is
`replaceState` while dragging / playing and one `pushState` on release, so Back returns to the
pre-drag year. `/compare`, `/about`, `/evidence`, `/eval` are reserved for M3.

**Search (M2, PLAN §4–§6).** Below the pyramid the country page shows the *k* most similar and *k* most
different pyramids under the active metric, an own-trajectory row, and a collapsed time-shift panel
("{Name} {year} across time": the best-matching year of every other country). The constraints ride in
the URL after `axis`/`unit`, defaults elided, in this order:
`?mode=same|near|range|any &n= &from= &to= &via=today &era=obs|all &scope=c|all &minpop=<persons>
&metric=blend|w1|l2|l2s|hel|feat|w1sex|w1bal|visual &sex=2|1 &k=3|5|10|20 &div=0|0.5|2
&trend=motion|path &L=5|10|20`. `mode=today` is input sugar for `mode=range&from=Y&to=Y&via=today`;
`era` is elided when it equals the J8 default (`obs` for a query year ≤ the current year, else `all`), so
`/japan/2050?mode=any&era=obs` is the explicit "observed only" view of a projected query. The engine
(`lib/search.ts`, `bands.ts`, `explain.ts`) reproduces `src/pyramid_explorer/{metrics,search,bands}.py`
in float64 from the u16 shares and is fixture-tested against `evals/fixtures/search_cases.json`
(22 cases; max |Δd| 5e-10); `scripts/query.py` prints the same numbers for any query. Same-year, today
and trend searches run over the 25 KB year shards (no blob); near / range / any and the time-shift panel
load the whole corpus once. "Most different" is MMR-diversified (presets strict 0 · balanced 0.5 ·
spread 2) with the raw farthest rank on every card and a "strictly farthest" strip; every card carries
the band against the random-pair null, the L2/W1 decomposition and "similar because / differs in"
sentences from `lib/explain.ts`. `metric=visual` (SigLIP2 PCA-64 image embeddings) is in the menu as an
experiment labelled by its evaluation verdict.

**Data layer (`web/src/lib/data.ts`, three tiers).** Tier 1 paints the page: `entities.json` +
`meta.json` (bundled), the entity shard `pyramids.{sha8}/{ISO3}.u16` (151 years × 42 Uint16 shares +
151 float32 totals, 13 KB — scrubbing never fetches), the year shard `years.{sha8}/{YYYY}.u16` (all
entities × 42 + totals, 25 KB) and `bands_default.{sha8}.bin` (the same-year Shape percentile tables).
Tier 2 = `bands.{sha8}.bin` (all percentile tables, 594 KB — first non-default metric / mode or the
time-shift panel), tier 3 = `shares.{sha8}.d16z` + `totals.{sha8}.f32` (the whole corpus, 1.6 MB, gzip
sniffed by magic bytes and inflated with `DecompressionStream`, delta-decoded in `math/delta.ts`) and
`emb/*.f16` (4.9 MB, only for `metric=visual`). The TypeScript math (`math/features.ts`, `cdf.ts`,
`smooth.ts`, `delta.ts`) is checked against the Python twins on `evals/fixtures/parity_500.json` in
vitest. File names carry the build hash, so `/data/**` can be cached immutably; `meta.json.files` is the
only place that knows them.

**Measurements** (production build via `vite preview`, localhost, M4 Max, Chrome; per-item checklists in
[SMOKE.md](SMOKE.md)). M1: first paint of `/japan/2026` moved **113 KB** on the wire; the shards land
~40 ms after navigation start; a year change while scrubbing costs 1.0 ms median / 2.9 ms p90 of
main-thread time. M2: first paint is **134 KB** (JS 78 KB gz, CSS 5 KB, entity shard 11 KB gz, year shard
20 KB gz, `bands_default` 19 KB) against the 175 KB budget, still tier 1 only; a same-year search with
explanations takes 3–4 ms; an any-year search over 29,239 rows takes **24–44 ms warm** and ~157 ms on its
first, cold evaluation; the 1.6 MB blob is fetched in ~60 ms and decoded in 74–117 ms wall time (printed
in the results footer). Phone measurements (real iPhone + Android against the deployed site, PLAN §10) and
the PLAN §8 Worker decision — the cold any-year run and the blob decode are the two figures near the
100 ms rule — are still open.

## Data & attribution

Population data: United Nations, Department of Economic and Social Affairs, Population
Division (2024). *World Population Prospects 2024, Online Edition* (medium variant),
including the 19 January 2026 interim update for Togo. https://population.un.org/wpp/ —
© 2024 United Nations, licensed under [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/).
Files under `web/public/data/` are reshaped, share-normalised and 16-bit-quantised
derivatives, not the original UN files; the UN does not endorse this site.
Design inspiration: [populationpyramid.net](https://www.populationpyramid.net). Code: MIT.
