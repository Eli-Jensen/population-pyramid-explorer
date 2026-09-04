# population-pyramid-explorer

Find any country's demographic twins and opposites. A population-pyramid explorer
built on the UN World Population Prospects 2024 (medium variant, 1950–2100) with a
headline feature no other pyramid site has: **similarity search by shape**, with
adjustable constraints (same year, a range of years, or any year), plus "most
different" and time-shift matching ("South Korea 2026 ≈ Japan 2005").

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
make data             # copy/fetch raw inputs (WPP 2024, Togo update, LOCATIONS, Maddison, PWT, WDI)
make build            # rebuild the DuckDB store, corpus, web shards and build report
make test             # pytest
make query Q="JPN 2026"
make web              # vite dev server
```

## Data & attribution

Population data: United Nations, Department of Economic and Social Affairs, Population
Division (2024). *World Population Prospects 2024, Online Edition* (medium variant),
including the 19 January 2026 interim update for Togo. https://population.un.org/wpp/ —
© 2024 United Nations, licensed under [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/).
Files under `web/public/data/` are reshaped, share-normalised and 16-bit-quantised
derivatives, not the original UN files; the UN does not endorse this site.
Design inspiration: [populationpyramid.net](https://www.populationpyramid.net). Code: MIT.
