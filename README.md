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
make build            # rebuild the DuckDB store, corpus, web shards and build report, then web/src/data/evals.json,
                      # then the econ export (scripts/build_econ.py → econ.{sha8}.ecz + evidence.json, idempotent)
make test             # fast pytest (make test-slow for the full-corpus checks, make test-all for everything)
make eval             # similarity evaluation protocol → evals/RESULTS.md + evals/verdicts.json
make query Q="JPN 2026"                                      # twins, opposites, time-shift table
make query Q="KOR 2026 --mode any"                           # time-shift: Japan best 2008 (−18 y), d 0.435
make query Q="CHN 1990 --mode today --trend motion --L 10"   # who is on China-1990's 10-year path today
make sql Q="SELECT count(*) FROM pyramid"                    # read-only SQL against data/processed/explorer.duckdb
make web              # vite dev server → http://localhost:5173/population-pyramid-explorer/
make web-check web-test web-build                            # svelte-check + tsc · vitest · production build (+ 404.html)
make smoke            # print SMOKE.md, the browser checklist run before a milestone is called done
make triplets-select  # the 88 human-triplet items (seed 0) → evals/triplets_selection.json (+ web/src/data copy)
make triplets-fit     # fit Eli's answers in evals/triplets.json → evals/TRIPLETS.md; SYNTHETIC=1 = noisy oracle
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
chip, the blob decode path, exports, the economic lens (M5: first paint unchanged, strip numbers against
DuckDB, then-what / cohort / pair rows, the evidence page's numbers against `evals/econ/RESULTS.md`, language
grep) and the triplet tool (M4, dev server). Pure-function behaviour lives in vitest instead
(`web/src/**/*.test.ts`, 600+ cases incl. parity against `evals/fixtures/parity_500.json` and
`search_cases.json`, the `.ecz` decoder against the shipped file, and the language deny-list over every string
literal under `web/src`).

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
| `/evidence` | the economic-lens evidence page (M5): the four literature links with effect sizes and citations, the China 1990 row, this site's pre-registered backtest (growth and returns beside VT, decision levels, the only sentences the UI may render), the investability table, the vintage caveat, sources & licences — every number from `web/src/data/evidence.json` |
| `?lens=econ` | market lens on a country or compare page (M5; elided when off, remembered in localStorage): "then what happened ▸" on historical result cards, econ columns in the time-shift table, econ rows in the pair card, cohort outcomes under the twins in cross-year modes. The econ context strip (GDP/cap, 10-y growth, income group then, dividend stage) is always on. Tier 2b `econ.{sha8}.ecz` loads after the first paint |
| `/eval/triplets` | dev-only human-triplet tool (M4; `npm run dev` only, never linked) |

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
M5: the country page's first paint is **154 KB** (JS 97.6 KB gz, CSS 6.0, HTML 0.6, shards 50.1; the lens
toggle, router and tier-2b loader cost +9 KB over M3); the econ file `econ.{sha8}.ecz` (108.6 KB gz) and the
`econ-*.js` chunk (11.7 KB gz) are fetched only after the shards settle; `/evidence` is its own chunk
(49.5 KB gz). Phone measurements against the deployed site (PLAN §10) and the PLAN §8 Worker decision are still open.

## Economic lens

Two tiers (PLAN §7; the decisions in `evals/econ/decision.json`, the pre-registration in
`evals/econ/PREREG.md`, the results in `evals/econ/RESULTS.md`):

- **Econ context, always on.** Under the callouts of every country page, `EconStrip` shows GDP per capita
  (Maddison Project Database 2023, 2011 international $, spliced past 2022 with WDI / PWT growth — `$38,809
  (2024)` for Japan), 10-year real GDP growth (PWT 11.0 `rgdpna`, WDI for the last year), the World Bank
  income group *of that year* (OGHIST; "n/a before 1987"), the demographic-dividend stage (the Ahmed–Cruz
  / WPS7893 typology applied to every year from the WPP working-age trajectory and the TFR a generation
  earlier; thresholds + citation in `pipeline/typology.yaml`, reproduced 112/132 against the report's Table
  A1) and the TFR. The compare page's `PairCard` adds the same five series for both members, z-scored against
  A's year cross-section with `n` printed.
- **Market lens, `?lens=econ`, off by default.** The nav toggle (country and compare pages) turns it on with a
  one-time dismissible banner; the choice is remembered in `localStorage` (`ppe:lens`) and carried onto in-app
  links, never onto history entries, and a pasted URL never writes the memory. With it on: result cards of a
  historical year (≤ last econ year − 5) gain **"then what happened ▸"** — GDP per capita ×N and %/yr at
  +10/+20/+30 years (clipped horizons say so), the working-age-share peak year ("dividend window") and the
  market row; current-era cards carry the **investability badge** (`live FXI (iShares, since 2004)` /
  `liquidated NGE 2024-03-25` / "No US-listed single-country fund exists for this country" + MSCI class +
  capital-mobility flag); the time-shift table gains `GDP/cap then · next 20 y · index vs VT` (still ordered by
  d); cross-year twins get a **cohort strip** (20-year GDP/cap growth of every match after its own year, median
  / IQR / the focal's rank, and "n = k with a fund; too few to conclude" under 10).
- **Rules the code enforces.** Every market number stands beside VT over the identical window (VT proxy
  flagged before 2008-06-24, "VT did not exist" earlier); every growth or market *claim* — "what happened", the
  null result, "vs VT", investability, the disconnect sentences — comes from the sentence ids in
  `decision.json#allowed_sentence_ids` (the five `L0.*`) through the `ui_sentences.yaml` templates
  (`lib/econ/lang.ts`; L1/L2 throw in dev) or verbatim from `decision.json`. Table cells and chips (time-shift
  columns, the cohort fund strip, the badge, the Evidence tables) print numbers with their window and VT beside
  them without a template; `lib/econ/lang.test.ts` fails the build on any deny-listed word in a string literal
  under `web/src` or in the shipped JSON, which is the check those strings get. Nothing combines shape distance
  with an econ number, sorts a result list by return or growth (the cohort strip reports the focal's rank
  among its lookalikes' growth rates, in shape order), shows a price or a forecast, or links to a broker (issuer
  notices and factsheets only). The badge's liquidation date is the shipped econ file's, i.e. `etf_manual.yaml`'s
  SEC-filing date (NGE 2024-03-25); the frozen `decision.json` sentence carries the universe file's 2023-07-28 and
  `/evidence` annotates it. The footer disclaimer stands on every page and links to `/evidence`.
- **Evidence page** (`/evidence`): the question, the four literature links with effect sizes and citations
  (`docs/research/econ_evidence.md` → `evals/evidence.yaml`), the China 1990 row and its 2024 lookalikes, this
  site's backtest (primary row B|10|10: mean excess growth −0.19 pp/yr, N_eff 43, CI [−1.47, +1.20]; returns
  beside VT; EW basket − VT −5.77 pp/yr from 2010), the decision levels with every condition, the allowed
  sentences, predictions P1–P8, the investability table (liquidations with dates and issuer notices), the
  vintage caveat (Jaccard 4 of 15 cells), sources & licences. Every number is read from
  `web/src/data/evidence.json`; nothing is typed into the page.
- **Data.** `scripts/build_econ.py` (also the last step of `make build`) runs `econ/{splice,typology,
  instruments,evidence,export_econ}.py`: one lazy file `web/public/data/wpp2024/econ.{sha8}.ecz` (u32 header
  length + JSON header + typed arrays: gdppc u16 log-encoded, 10-y and 1-y growth i16 ×0.01, TFR u16 ×0.001,
  income u8, stage u8; 237 countries × 1950–2024; instruments, the VT ladder, events and sources in the header;
  108.6 KB gz against a 160 KB budget), `web/src/data/{econ_entities,econ_decision,ui_sentences,evidence}.json`,
  a paragraph in `NOTICE`, and `meta.json.files.econ`. Deterministic: a rerun is byte-identical. Shipped
  sources are CC BY 4.0 (Maddison 2023, PWT 11.0, WDI, OGHIST) plus WPP TFR; IMF WEO and MSCI series are
  build-time / citation only and a licence guard refuses to write anything naming them (`tests/test_econ_export.py`).

## Evaluation: human triplets (M4)

`evals/protocol.md` pre-registers the design; `scripts/select_triplets.py` (`make triplets-select`, seed 0,
`src/pyramid_explorer/triplets.py`) draws **88 items** from the real corpus: 80 unique — 32 where `blend`
and the exposed image space disagree, 38 numeric-vs-numeric disagreements spread over all 21 metric pairs,
10 "which is more different" opposites — plus 8 swapped duplicates ≥ 30 positions later; anchors are random
2024 countries ≥ 1 M, every one used once; A/B labels and left/right sides are randomised per item. The
selection (`evals/triplets_selection.json`, copied to `web/src/data/`) carries the distances under 12 metrics
and the raw components the fit re-weights, and reproduces byte-for-byte.

**How Eli runs it (~75 min, one sitting):**

1. `cd web && npm run dev`, open `http://localhost:5173/population-pyramid-explorer/eval/triplets` (dev-only
   route; the production build shows a placeholder). Enter a rater name, press **Start**.
2. Each item shows the anchor above two text-free pyramids at one fixed scale — no names, years or metrics
   anywhere in the DOM. Answer with the buttons or `A` / `B` / `T` then `Enter`; `Backspace` re-asks the
   previous item. Response times are recorded; every answer autosaves (`localStorage`), so closing the tab
   and coming back resumes at the next item.
3. On the done screen, **Copy JSON** or **Download** → save as `evals/triplets.json`
   (`{rater, started, finished, items:[{item, choice, rt_ms}]}`) and commit it.
4. `make triplets-fit` → `evals/TRIPLETS.md` + `evals/triplets_fit.json`: self-agreement on the 8 repeats
   first (below 6/8 nothing may be promoted and every result is marked informational), pairwise agreement per
   metric and stratum, exact two-sided sign tests (blend vs the exposed image space on the 32; every numeric
   pair on the 48), the leave-one-out grid for `blend`'s `w_l2` × σ and `w1bal`'s λ on the numeric strata only,
   and recommendations — a change of the exposed image space is *printed*, never applied; `blend` parameters
   change only when the best cell beats the shipped default on a sign test and the gate holds. Until the real
   file exists, `make triplets-fit SYNTHETIC=1` exercises the whole chain on a noisy oracle and labels its
   output SYNTHETIC.

Two notes recorded by the fit: the protocol's "≥ 22 of 32" MDE is one-sided — the exact two-sided binomial
first calls at 23/32 (p = 0.0501 at 22) — and the as-built `blend` smooths nothing, so the grid's shipped
default is (w 0.5, σ 0); PLAN's "σ = 1 bin" names the `l2s` kernel.

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
- **Economic context (`econ.*.ecz`, the strip, the lens and `/evidence`):** Maddison Project Database 2023,
  Penn World Table 11.0, World Bank WDI + OGHIST — all CC BY 4.0; UN WPP 2024 TFR. Fund statistics are
  derived from daily adjusted closes / issuer NAV returns and named only as examples of what exists or existed;
  MSCI figures are hand-transcribed factsheet citations (`evals/econ/msci_citations.yaml`); IMF WEO is used at
  build time only and never exported. The site is not investment advice and makes no forecasts.
- **Evaluation labels:** transcribed from Korenjak-Černe et al., Hahn-Klimroth 2025, populationpyramids.org
  thresholds, RIETI, Yoshida et al. 2019 — `evals/labels/*.yaml` with page references and vintages.
- **Image encoders (offline experiment only):** SigLIP 2 (`google/siglip2-base-patch16-naflex`) and DINOv2
  (`facebook/dinov2-base`), Apache-2.0.
- **Design inspiration:** [populationpyramid.net](https://www.populationpyramid.net) — the fixed-axis,
  youngest-at-the-bottom pyramid and the year scrubber; no data or code is used from it.
- **Code:** MIT ([LICENSE](LICENSE)).
