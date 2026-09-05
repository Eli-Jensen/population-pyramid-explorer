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

**Routes (M1).** `/` home (search, "continue with…", start with World / your country) ·
`/{slug}` → `/{slug}/{currentYear}` (client clock, `replaceState`) · `/{slug}/{year}` the country page,
1950–2100. Slugs are case-insensitive and accept ISO3, ISO2 and aliases (`/USA/`, `/jpn`,
`/united-states-of-america/2026` all `replaceState` to the canonical `/united-states/2026`). Display
options ride in the query with defaults elided: `?axis=pin10|noclip` (default `fit` = the entity's
build-time `axis_pct`) and `?unit=abs|pctsex` (default `% of total`). Year scrubbing is
`replaceState` while dragging / playing and one `pushState` on release, so Back returns to the
pre-drag year. `/compare`, `/about`, `/evidence`, `/eval` are reserved for M2/M3.

**Data layer (`web/src/lib/data.ts`, three tiers).** Tier 1 paints the page: `entities.json` +
`meta.json` (bundled), the entity shard `pyramids.{sha8}/{ISO3}.u16` (151 years × 42 Uint16 shares +
151 float32 totals, 13 KB — scrubbing never fetches), the year shard `years.{sha8}/{YYYY}.u16` (all
entities × 42 + totals, 25 KB) and `bands_default.{sha8}.bin`. Tier 2 = `bands.{sha8}.bin` (all
percentile tables), tier 3 = `shares.{sha8}.d16z` + `totals.{sha8}.f32` (the whole corpus, gzip
sniffed by magic bytes and inflated with `DecompressionStream`, delta-decoded in `math/delta.ts`).
The TypeScript math (`math/features.ts`, `cdf.ts`, `smooth.ts`, `delta.ts`) is checked against the
Python twins on `evals/fixtures/parity_500.json` in vitest. File names carry the build hash, so
`/data/**` can be cached immutably; `meta.json.files` is the only place that knows them.

**M1 measurements** (production build via `vite preview`, localhost, M4 Max, Chrome; details and the
per-item checklist in [SMOKE.md](SMOKE.md)): first paint of `/japan/2026` moves **113 KB** on the wire
(JS 57 KB gz incl. the 280-entity table, CSS 5 KB, entity shard 11 KB gz, year shard 21 KB gz,
`bands_default` 19 KB) against the 175 KB budget; the shards land ~40 ms after navigation start and the
pyramid is built in the same task; a year change while scrubbing costs 1.0 ms median / 2.9 ms p90 /
10.6 ms max of main-thread time. Phone measurements (real iPhone + Android against the deployed site,
PLAN §10) and the blob-path Worker decision are still open.

## Data & attribution

Population data: United Nations, Department of Economic and Social Affairs, Population
Division (2024). *World Population Prospects 2024, Online Edition* (medium variant),
including the 19 January 2026 interim update for Togo. https://population.un.org/wpp/ —
© 2024 United Nations, licensed under [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/).
Files under `web/public/data/` are reshaped, share-normalised and 16-bit-quantised
derivatives, not the original UN files; the UN does not endorse this site.
Design inspiration: [populationpyramid.net](https://www.populationpyramid.net). Code: MIT.
