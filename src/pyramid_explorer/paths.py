"""Repository paths (single source of truth)."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Sibling checkout holding already-downloaded raw inputs (WPP CSVs, PWT xlsx, the WEO parquet); the econ
# loaders copy from here before downloading. Override with PYRAMID_ECON_ROOT or `make data ECON_FROM=DIR`.
PYRAMID_ECON_ROOT = Path(os.environ.get("PYRAMID_ECON_ROOT", Path.home() / "Projects" / "pyramid-econ"))
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
DATA_RENDERS = REPO_ROOT / "data" / "renders"
DATA_OUT = REPO_ROOT / "data" / "out"
PIPELINE = REPO_ROOT / "pipeline"
EVALS = REPO_ROOT / "evals"
ECON_EVALS = EVALS / "econ"            # economic-lens backtest (PREREG.md and its outputs)
DATA_RAW_ETF = DATA_RAW / "etf"        # Yahoo adjusted closes per ticker (gitignored, never shipped)
WEB = REPO_ROOT / "web"
WEB_DATA = WEB / "public" / "data"
WEB_SRC_DATA = WEB / "src" / "data"

REVISION = "wpp2024"
YEARS = list(range(1950, 2101))          # 151 years
N_YEARS = len(YEARS)
AGE_STARTS = list(range(0, 101, 5))      # 21 bins, 100 = 100+
N_BINS = len(AGE_STARTS)
N_DIMS = 2 * N_BINS                      # 42 = 21 male + 21 female shares of total
LAST_OBSERVED_YEAR = 2023
