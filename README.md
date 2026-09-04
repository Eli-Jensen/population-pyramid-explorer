# population-pyramid-explorer

Find any country's demographic twins and opposites. A population-pyramid explorer
built on the UN World Population Prospects 2024 (medium variant, 1950–2100) with a
headline feature no other pyramid site has: **similarity search by shape**, with
adjustable constraints (same year, a range of years, or any year), plus "most
different", time-shift matching ("South Korea 2026 ≈ Japan 2005") and
**trajectory matching** — which country is on the same 5/10/20-year path
(`--trend motion` compares the change in shape, `--trend path` the aligned snapshots).

Status: **M0 in progress** (data pipeline, metrics, evaluation harness). Plan in
[docs/PLAN.md](docs/PLAN.md); research behind it in [docs/research/](docs/research/).

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
make web              # vite dev server
```

`make data` copies raw files from a sibling `pyramid-econ` checkout when present
(`WPP_FROM=` / `ECON_FROM=` or `PYRAMID_ECON_ROOT`), else downloads them; every
file is sha256-pinned in `pipeline/*manifest.json`. `make m0` runs the whole
M0 chain (data → build → test → render → embed → eval → build-emb).

## Data & attribution

Population data: United Nations, Department of Economic and Social Affairs, Population
Division (2024). *World Population Prospects 2024, Online Edition* (medium variant),
including the 19 January 2026 interim update for Togo. https://population.un.org/wpp/ —
© 2024 United Nations, licensed under [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/).
Files under `web/public/data/` are reshaped, share-normalised and 16-bit-quantised
derivatives, not the original UN files; the UN does not endorse this site.
Design inspiration: [populationpyramid.net](https://www.populationpyramid.net). Code: MIT.
