# population-pyramid-explorer

Find any country's demographic twins and opposites. A population-pyramid explorer built on the
UN World Population Prospects 2024 (medium variant, 1950–2100) with a headline feature no other
pyramid site has: **similarity search by shape**, with adjustable constraints (same year, a range of
years, or any year), plus "most different", time-shift matching ("South Korea 2026 ≈ Japan 2008"),
**trajectory matching** (which country is on the same 5/10/20-year path) and a two-pyramid compare
page with overlay / diff / side views and PNG · SVG · CSV export.

Status: **M0–M3 built** — data pipeline + evaluation, country page, twins & opposites, compare page,
export/share and the About page all run locally against the committed shards and pass the browser
checklist in [SMOKE.md](SMOKE.md). Plan in [docs/PLAN.md](docs/PLAN.md); research behind it in
[docs/research/](docs/research/); the evaluation record in [evals/RESULTS.md](evals/RESULTS.md).

Live: <https://eli-jensen.github.io/population-pyramid-explorer/> (GitHub Pages; see Hosting).

## Layout

- `src/pyramid_explorer/` — Python pipeline (uv, Python 3.12): ingest → shares → DuckDB store → shards; metrics, search, bands, evaluation, canonical renders + image embeddings.
- `scripts/` — `fetch_data.py`, `build_data.py`, `export_evals.py`, `eval_similarity.py`, `query.py`, `render_canonical.py`, `embed_images.py`, `check_upstream.py`, …
- `web/` — Svelte 5 + Vite static site (GitHub Pages). Built data snapshots live in `web/public/data/` and are committed; `web/src/data/{entities,meta,evals}.json` are generated too.
- `evals/` — pre-registered protocol, frozen external label sets, results, verdicts.
- `docs/` — the plan and the research reports.

## Develop

Everything runs through the `Makefile` (`make help` lists targets):

```bash
make setup            # python (uv) + web (npm) dependencies
make data             # copy/fetch raw inputs: WPP 2024 + Togo update + LOCATIONS; Maddison, PWT, WDI + OGHIST
                      # (all shipped, CC BY 4.0) and IMF WEO (build-time only, never exported) — sha256-pinned
make build            # rebuild the DuckDB store, corpus, web shards and build report, then web/src/data/evals.json
make test             # fast pytest (make test-slow for the full-corpus checks, make test-all for everything)
make eval             # similarity evaluation protocol → evals/RESULTS.md + evals/verdicts.json
make query Q="JPN 2026"                                      # twins, opposites, time-shift table
make query Q="KOR 2026 --mode any"                           # time-shift: Japan best 2008 (−18 y), d 0.435
make query Q="CHN 1990 --mode today --trend motion --L 10"   # who is on China-1990's 10-year path today
make sql Q="SELECT count(*) FROM pyramid"                    # read-only SQL against data/processed/explorer.duckdb
make web              # vite dev server → http://localhost:5173/population-pyramid-explorer/
make web-check web-test web-build                            # svelte-check + tsc · vitest · production build (+ 404.html)
make smoke            # print SMOKE.md, the browser checklist run before a milestone is called done
make deploy           # gate (check/test/build) then push main → GitHub Pages via .github/workflows/deploy.yml
```

The web gate that must stay green before any push is `cd web && npm run check && npm test && npm run build`.
The Browser pane launch config `dev` (`.claude/launch.json`) starts the same Vite server; the pane reads
the launch.json of the *session root*, so when a session is opened one directory up, start Vite yourself
and attach the pane by URL.

`make data` copies raw files from a sibling `pyramid-econ` checkout when present (`WPP_FROM=` /
`ECON_FROM=`), else downloads them; every file is sha256-pinned in `pipeline/*manifest.json`. `make m0`
runs the whole M0 chain (data → build → test → render → embed → eval → build-emb). `make build` ends by
running `scripts/export_evals.py`, which folds `evals/verdicts.json` (+ `RESULTS.md` and
`image_embeddings.md`) into `web/src/data/evals.json` so the About page renders the evaluation numbers
rather than quoting them; `scripts/export_evals.py --check` fails when that file is stale.

## Refresh (WPP 2027)

WPP 2027 is due 2027-07-11 (PLAN §3.7). `make check-upstream` (manual, `scripts/check_upstream.py`) says
whether WPP, Maddison, PWT, WDI or an instrument list changed upstream. To refresh: add the new files to
`pipeline/manifest.json` (url, sha256, bytes), switch `meta.revision` / the output directory to
`web/public/data/wpp2027/`, run `make data build test` — the build report diffs the entity list against
the previous build, refits σ and the percentile bands, and re-asserts `last_observed_year + 1 ≤ built_year`
— then `make eval` (labels are frozen; only the corpus moved) and `make render embed build-emb` only if a
`visual` verdict still needs the image spaces. The old `wpp2024/` directory is deleted on refresh: URLs
carry no revision, so keeping it would double the deploy for nothing. No "January ritual" exists — the
current year comes from the visitor's clock.

## Smoke checklist

[SMOKE.md](SMOKE.md) is the integration-test story without CI: a numbered, per-milestone checklist run
through the Browser pane against the dev/preview server (and, after deploy, the live site) before a
milestone is called done — alias/case/trailing-slash redirects, scrubber history semantics, keyboard,
reduced motion, dark mode, mobile preset, copy-link round trips, `best` → concrete URL, the projected-query
chip, the blob decode path, exports. Pure-function behaviour lives in vitest instead (`web/src/**/*.test.ts`,
430+ cases incl. parity against `evals/fixtures/parity_500.json` and `search_cases.json`).

## The math (short)

Shape = the 42-vector of five-year age × sex shares of total population (size-invariant, shift-aware,
sex-aware). Default metric **Shape** (`blend`):
`d = ½·‖s42_a − s42_b‖₂ / σ_L2 + ½·W1sex(a, b) / σ_W1`, where W1sex is the per-sex cumulative-share
(earth-mover) distance in years and each σ is the median distance between random same-year country pairs
≥ 100k, fitted at build (`meta.sigma`). Also in the menu: age-shift `w1` (years, ≈ |Δ mean age|, sex-blind,
failed the continuity gate — not the default), bin-by-bin `l2`, and under advanced `l2s`, `hel`, `feat`,
`w1sex`, `w1bal`; **Trend** motion/path over L ∈ {5, 10, 20}; **Visual** = cosine on PCA-64 SigLIP 2
embeddings of canonical renders (rejected by the pre-registered gates — C1 0.55 vs 0.95 — shipped anyway
as an experiment by the owner's decision, both methods available). Opposites = farthest-k diversified by
MMR (β 0 / 0.5 / 2; raw rank always shown). Bands = percentile of d against the right null (same-year per
year, cross-year per decade × era, best-year for time-shift). Time-shift `y*(c) = argmin_y d(q, c_y)` over
the allowed era. Explanations decompose d into its L2 and W1 halves + top bins, and z-score summary features
against the *query year's* country set for both members of a pair. Everything is in PLAN §4–§6 and, with
the measured numbers, on `/about` and in `evals/RESULTS.md`.

## Web

`web/` is a Svelte 5 (runes) + Vite 8 + TypeScript 6 + Tailwind v4 single-page app, hand-written SVG, no
chart library, no server. It is a GitHub Pages **project site**, so Vite's `base` is
`/population-pyramid-explorer/` (`VITE_BASE=/ npm run build` for a root deploy); every route and fetch goes
through `import.meta.env.BASE_URL`, and `404.html` is a copy of `index.html` so deep links work.

**URL schema** (`lib/router.ts` parses, `canonical()` emits; defaults elided; slugs case-insensitive, ISO3 /
ISO2 / aliases redirect via `replaceState`):

| route | meaning |
|---|---|
| `/` | home: search, "continue with…", start with World / your country |
| `/{slug}` → `/{slug}/{currentYear}` | hub redirect (client clock) |
| `/{slug}/{year}` | country page, 1950–2100; display `?axis=pin10\|noclip &unit=abs\|pctsex`; search `?mode=same\|near\|range\|any &n= &from= &to= &via=today &era=obs\|all &scope=c\|all &minpop= &metric= &sex=2\|1 &k=3\|5\|10\|20 &div=0\|0.5\|2 &trend=motion\|path &L=5\|10\|20` (`mode=today` is sugar for `range&from=Y&to=Y&via=today`; `era` is written only when it differs from the J8 default: `obs` for a query year ≤ the current year, else `all`) |
| `/compare/{a}/{ya}/{b}/{yb\|best}` | two pyramids; `?view=overlay\|diff\|side` (+ axis/unit/era/metric/sex). `best` is input sugar: resolved client-side to B's best-matching year, then `replaceState` to the concrete year + `?from=best` so the "B → best year" button stays lit and Copy link never emits an unresolved `best`. Demo: `/compare/south-korea/2026/japan/best` → `/compare/south-korea/2026/japan/2008?from=best` |
| `/about` | how similarity works, the evaluation record (from `evals.json`), data notes, hosting, attribution |
| `/evidence`, `/eval/…` | reserved (M5 / dev-only) |

Year scrubbing is `replaceState` while dragging / playing and one `pushState` on release, so Back returns
to the pre-drag year. **Export** (`lib/export.ts`, `ExportMenu.svelte`) is client-side from the live SVG:
PNG 2× with the footer band `{Name} · {Year} · Pop {N} · Source: UN WPP 2024 · Population Pyramid Explorer`
(theme colours inlined), SVG, and CSV — the pyramid (`age_start, male, female, male_pct, female_pct` per
pyramid, focal + overlay) or a results list (`rank, raw_rank, id, name, year, d, band, dy`). Filenames follow
`japan-2026-pyramid.png`. **Share** (`ShareButton.svelte`) = Copy link (clipboard, textarea fallback) + the
Web Share sheet where available; all state is in the URL. Downloads are inert inside some sandboxed viewers
(artifact iframes) — the menu says so when it cannot tell.

**Search engine.** `lib/search.ts`, `bands.ts`, `explain.ts` reproduce `src/pyramid_explorer/{metrics,search,bands}.py`
in float64 from the u16 shares and are fixture-tested against `evals/fixtures/search_cases.json` (max |Δd|
5e-10); `scripts/query.py` prints the same numbers for any query. Same-year, today and trend searches run
over the 25 KB year shards (no blob); near / range / any, the time-shift panel and `best` load the whole
corpus once. The metric menu is built from `meta.verdicts` (merged from `evals/verdicts.json` by the build;
an evaluation-only metric without shipped bands is capped at `lab`).

**Data layer (`lib/data.ts`, three tiers).** Tier 1 paints the page: `entities.json` + `meta.json`
(bundled), the entity shard `pyramids.{sha8}/{ISO3}.u16` (151 years × 42 Uint16 shares + 151 float32
totals, 13 KB — scrubbing never fetches), the year shard `years.{sha8}/{YYYY}.u16` (25 KB) and
`bands_default.{sha8}.bin`. Tier 2 = `bands.{sha8}.bin` (all percentile tables, 594 KB). Tier 3 =
`shares.{sha8}.d16z` + `totals.{sha8}.f32` (the whole corpus, 1.6 MB, gzip sniffed by magic bytes and
inflated with `DecompressionStream`, delta-decoded in `math/delta.ts`) and `emb/*.f16` (5.4 MB, only for
`metric=visual`). The TypeScript math is checked against the Python twins on `evals/fixtures/parity_500.json`.
File names carry the build hash, so `/data/**` can be cached immutably; `meta.json.files` is the only place
that knows them.

**Measurements** (production build via `vite preview`, localhost, M4 Max, Chrome; per-item checklists in
[SMOKE.md](SMOKE.md)). M1: first paint of `/japan/2026` moved **113 KB** on the wire; the shards land ~40 ms
after navigation start; a year change while scrubbing costs 1.0 ms median / 2.9 ms p90 of main-thread time.
M2: first paint is **134 KB** (JS 78 KB gz, CSS 5 KB, entity shard 11 KB gz, year shard 20 KB gz,
`bands_default` 19 KB) against the 175 KB budget; a same-year search with explanations takes 3–4 ms; an
any-year search over 29,239 rows takes **24–44 ms warm** and ~157 ms cold; the 1.6 MB blob is fetched in
~60 ms and decoded in 74–117 ms. M3: the compare page and `/about` are lazy chunks (`Compare-*.js` 11.7 KB gz,
`About-*.js` 16.1 KB gz, loaded on first visit of their route), so the country page's first paint is **145 KB**
(JS 88.7 KB gz, CSS 5.7 KB, HTML 0.6 KB, year shard 20.2 KB gz, entity shard 10.9 KB gz, `bands_default` 19.0 KB);
a same-year compare (`/compare/japan/2026/qatar/2026`) adds only the second entity shard, while `…/best` also
pulls the 1.6 MB corpus + 157 KB totals + the 594 KB cross-year band tables it needs for the best-year null.
Phone measurements against the deployed site (PLAN §10) and the PLAN §8 Worker decision are still open.

## Hosting

GitHub Pages project site, deployed by `.github/workflows/deploy.yml` on every push to `main` (the workflow
runs `npm run check && npm test && npm run build`, then `actions/deploy-pages`); `make deploy` runs the same
gate locally first and pushes, `make deploy-status` watches the run. The `deploy` job is gated on the repo
variable `PAGES_ENABLED=true` so the build job alone runs as CI until Pages is switched on.

**Private-repo caveat.** GitHub Pages on a *private* repository requires GitHub Pro / Team; on a Free plan the
deploy waits until the repository is made public (the code is MIT and the data CC BY, so nothing blocks
that) — check with `gh api user --jq .plan.name`. Pages serves static files only, which is all this site
needs: no server, no API, no database; the largest object is the 1.6 MB corpus blob and it is fetched only
for cross-year searches. `/data/**` file names are content-hashed, so they are safe to cache forever; Pages
does not honour custom cache headers, but a changed build produces new names.

## Credits & licences

- **Population data:** United Nations, Department of Economic and Social Affairs, Population Division (2024).
  *World Population Prospects 2024, Online Edition* (medium variant), including the 19 January 2026 interim
  update for Togo (aggregates containing Togo recomputed from members by this site; the UN did not revise
  aggregates). <https://population.un.org/wpp/> — © 2024 United Nations, licensed under
  [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/). Files under `web/public/data/` are
  reshaped, share-normalised and 16-bit-quantised derivatives, not the original UN files; the UN does not
  endorse this site. The full notice is `web/public/data/wpp2024/NOTICE` (also on `/about`).
- **Economic context (build-time, for the later evidence page):** Maddison Project Database 2023, Penn World
  Table 11.0, World Bank WDI + OGHIST — all CC BY 4.0. IMF WEO is used at build time only and never exported.
- **Evaluation labels:** transcribed from Korenjak-Černe et al., Hahn-Klimroth 2025, populationpyramids.org
  thresholds, RIETI, Yoshida et al. 2019 — `evals/labels/*.yaml` with page references and vintages.
- **Image encoders (offline experiment only):** SigLIP 2 (`google/siglip2-base-patch16-naflex`) and DINOv2
  (`facebook/dinov2-base`), Apache-2.0.
- **Design inspiration:** [populationpyramid.net](https://www.populationpyramid.net) — the fixed-axis,
  youngest-at-the-bottom pyramid and the year scrubber; no data or code is used from it.
- **Code:** MIT ([LICENSE](LICENSE)).
