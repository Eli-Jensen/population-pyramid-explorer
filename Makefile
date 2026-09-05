# population-pyramid-explorer — the only command surface.
# Every target echoes the command it runs so the underlying tools stay learnable.
SHELL := /bin/zsh
UV    := uv run
NPM   := npm --prefix web
WPP_FROM  ?= $(HOME)/Projects/pyramid-econ/data/raw/wpp2024
ECON_FROM ?= $(HOME)/Projects/pyramid-econ
# Survivorship guard assertion 4 (PREREG §6): `fail` = the pre-registered stop (default — `make backtest` IS the strict run).
# Yahoo served full dead histories for EGPT/NGE/PAK/FM on 2026-09-04, so the recorded run was `make backtest DEAD_SERIES=ok`,
# which records the A4 failure per ticker, DISCARDS those series and takes the funds from etf_manual.yaml; RESULTS.md §10 lists
# the deviation and the exact command. The deviation is therefore an explicit choice on every run, never inherited.
DEAD_SERIES ?= fail
Q ?=

.DEFAULT_GOAL := help
.PHONY: help setup setup-embed setup-econ data build build-nopatch build-emb test test-slow test-all render embed eval m0 labels backtest \
        query sql web web-check web-test web-build smoke deploy deploy-status check-upstream clean distclean

help: ## list targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## python (dev group) + web deps
	uv sync --group dev
	$(NPM) ci

setup-embed: ## python embed group (torch, transformers, scikit-learn)
	uv sync --group dev --group embed

setup-econ: ## python econ group (yfinance, statsmodels) for the backtest
	uv sync --group dev --group econ

data: ## fetch/copy raw inputs (WPP 2024 + Togo update + LOCATIONS; Maddison, PWT, WDI + OGHIST, WEO) — sha256-verified, idempotent
	$(UV) scripts/fetch_data.py --from $(WPP_FROM)
	$(UV) scripts/fetch_econ.py --from $(ECON_FROM)

build: ## rebuild DuckDB + corpus + web shards + build report (+ web/src/data/evals.json for the About page)
	$(UV) scripts/build_data.py
	$(UV) scripts/export_evals.py
	$(UV) --group econ scripts/build_econ.py

build-nopatch: ## same, without the Togo interim update
	$(UV) scripts/build_data.py --no-patches

build-emb: ## same, also exporting the image-embedding spaces (needs `make embed`)
	$(UV) scripts/build_data.py --emb evals/embeddings/siglip2-base-naflex.pca64.npy --emb evals/embeddings/dinov2-base.pca64.npy

test: ## pytest, fast: skips slow (full-corpus) + network (a command-line -m replaces pyproject's, so both are spelled out)
	$(UV) pytest -q -m "not slow and not network"

test-slow: ## full-corpus evaluations only (needs `make build`)
	$(UV) pytest -q -m "slow and not network"

test-all: ## everything incl. network
	$(UV) pytest -q -m "slow or network or not (slow or network)" --override-ini addopts=""

render: ## canonical pyramid renders for the image experiment
	$(UV) scripts/render_canonical.py --kind canon2 --size 336
	$(UV) scripts/render_canonical.py --kind canon2 --size 294
	$(UV) scripts/render_canonical.py --kind canon1 --size 294

embed: ## embed renders with SigLIP 2 + DINOv2 (local, MPS) and load them into the DB
	$(UV) --group embed scripts/embed_images.py --model siglip2-base-naflex --model dinov2-base --db

eval: ## similarity evaluation protocol → evals/RESULTS.md + evals/verdicts.json
	$(UV) scripts/eval_similarity.py --full

m0: data build test render embed eval build-emb ## the whole M0 chain, in order (ends by merging verdicts + emb/ into the shards)

labels: ## retrieve/transcribe external label sets → evals/labels/
	$(UV) scripts/fetch_labels.py

backtest: ## economic-lens backtest → evals/econ/RESULTS.md (strict PREREG guard; the recorded run was `make backtest DEAD_SERIES=ok`, see RESULTS §10)
	$(UV) --group econ scripts/fetch_etf.py --dead-series $(DEAD_SERIES)
	$(UV) --group econ scripts/backtest_lookalikes.py
	$(UV) --group econ scripts/panel_shape_growth.py
	$(UV) --group econ scripts/disconnect_table.py
	$(UV) --group econ scripts/decide_econ.py

query: ## twins/opposites/time-shift for a query, e.g. make query Q="JPN 2026 --mode today"
	$(UV) scripts/query.py $(Q)

sql: ## read-only SQL against the DuckDB file, e.g. make sql Q="SELECT count(*) FROM pyramid"
	$(UV) scripts/sql.py "$(Q)"

web: ## vite dev server (prefer the Browser pane launch config "dev")
	$(NPM) run dev

web-check: ## svelte-check + tsc
	$(NPM) run check

web-test: ## vitest
	$(NPM) run test

web-build: ## production build (+ 404.html fallback)
	$(NPM) run build

smoke: ## print the SMOKE.md checklist
	@cat SMOKE.md 2>/dev/null || echo "SMOKE.md arrives with M1"

deploy: web-check web-test web-build ## push main → GitHub Pages via .github/workflows/deploy.yml
	git push origin main

deploy-status: ## watch the latest Pages deploy
	gh run watch

check-upstream: ## has WPP / Maddison / PWT / WDI / any instrument changed upstream?
	$(UV) scripts/check_upstream.py

clean: ## remove rebuildable outputs
	rm -rf data/processed data/renders data/out web/dist

distclean: clean ## also raw data, venv, node_modules
	rm -rf data/raw .venv web/node_modules

# ---- M4 human triplets (PLAN §4.6 item 8; owner Z1) — appended targets, nothing above is touched
.PHONY: triplets-select triplets-fit

triplets-select: ## select the 88 triplet items (seed 0) → evals/triplets_selection.json + web/src/data copy
	$(UV) scripts/select_triplets.py

triplets-fit: ## fit the rater's answers (evals/triplets.json) → evals/TRIPLETS.md + triplets_fit.json; SYNTHETIC=1 for a noisy oracle
	$(UV) scripts/fit_params.py $(if $(SYNTHETIC),--synthetic,)
