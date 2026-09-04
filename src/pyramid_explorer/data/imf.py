"""IMF World Economic Outlook (vintage 2025-04) via DBnomics — NOT redistributable.

DBnomics mirrors every WEO vintage as ``IMF/WEO:{vintage}`` (imf.org blocks scripted
downloads).  ``fetch()`` copies the tidy parquet already built by pyramid-econ
(``weo_202504.parquet``: iso3, year, indicator, value, vintage) and falls back to
:func:`fetch_vintage` (copied from pyramid-econ) when the copy is absent.

WEO rows are build-time/citation only: the manifest and ``source.redistributable``
carry ``False`` and ``db.export_processed`` must never emit them.  ``is_forecast``
= ``year > LAST_ACTUAL_YEAR`` (2024 for the 2025-04 vintage).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import httpx
import pandas as pd

from pyramid_explorer.data.econ_manifest import RAW_ECON, record
from pyramid_explorer.paths import PYRAMID_ECON_ROOT

SOURCE = "weo_2025-04"
API = "https://api.db.nomics.world/v22/series/IMF/WEO%3A{vintage}"
VINTAGE = "2025-04"
LAST_ACTUAL_YEAR = 2024
LOCAL_REL = Path("data") / "processed" / "weo_202504.parquet"  # relative to a pyramid-econ checkout
LOCAL_COPY = PYRAMID_ECON_ROOT / LOCAL_REL
FILE = RAW_ECON / "weo_202504.parquet"
SUBJECTS = {  # WEO subject code -> pyramid-econ indicator name (as stored in the parquet)
    "NGDP_RPCH": "real_gdp_growth", "NGDPD": "gdp_usd", "NGDPRPPPPC": "gdp_pc_ppp",
    "PCPIPCH": "inflation", "LUR": "unemployment", "LP": "population",
    "GGXWDG_NGDP": "debt_gdp", "GGXONLB_NGDP": "primary_balance_gdp",
    "GGXCNL_NGDP": "overall_balance_gdp", "BCA_NGDPD": "current_account_gdp",
}
INDICATORS = {"gdp_pc_ppp": "gdppc_ppp_weo", "gdp_usd": "gdp_usd_weo", "population": "population_weo",
              **{name: f"{name}_weo" for name in SUBJECTS.values()
                 if name not in ("gdp_pc_ppp", "gdp_usd", "population")}}
LICENCE = "IMF terms of use (no redistribution)"
REDISTRIBUTABLE = False


def fetch_vintage(vintage: str = VINTAGE) -> pd.DataFrame:
    """All selected subjects, all countries, one WEO vintage -> tidy frame (pyramid-econ copy)."""
    rows = []
    dims = json.dumps({"weo-subject": list(SUBJECTS)})
    with httpx.Client(timeout=120) as client:
        offset = 0
        while True:
            r = client.get(API.format(vintage=vintage),
                           params={"observations": 1, "dimensions": dims, "limit": 1000, "offset": offset})
            r.raise_for_status()
            payload = r.json()["series"]
            for s in payload["docs"]:
                iso3, subject, _unit = s["series_code"].split(".")
                for period, value in zip(s["period"], s["value"]):
                    if value is not None:
                        rows.append((iso3, int(period), SUBJECTS[subject], value))
            offset += 1000
            if offset >= payload["num_found"]:
                break
    df = pd.DataFrame(rows, columns=["iso3", "year", "indicator", "value"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["vintage"] = vintage
    return df


def fetch(*, force: bool = False, local_copy: Path = LOCAL_COPY) -> Path:
    """Copy ``weo_202504.parquet`` from pyramid-econ (else DBnomics); record as non-redistributable."""
    if force and FILE.exists():
        FILE.unlink()
    if not FILE.exists():
        FILE.parent.mkdir(parents=True, exist_ok=True)
        if local_copy.exists():
            shutil.copyfile(local_copy, FILE)
        else:
            fetch_vintage().to_parquet(FILE, index=False)
    record(SOURCE, FILE, url=API.format(vintage=VINTAGE), source=SOURCE, licence=LICENCE,
           redistributable=REDISTRIBUTABLE,
           notes=f"IMF WEO {VINTAGE} via DBnomics; build-time only, never exported; forecast when year > {LAST_ACTUAL_YEAR}")
    return FILE


def to_long(raw: pd.DataFrame, last_actual_year: int = LAST_ACTUAL_YEAR) -> pd.DataFrame:
    """pyramid-econ tidy frame (iso3, year, indicator, value[, vintage]) -> loader long schema.

    Use this on :func:`fetch_vintage` output for a non-default ``--weo-vintage``; ``last_actual_year``
    should then be that vintage's last actual year (WEO April vintages: previous calendar year).
    """
    long = pd.DataFrame({
        "code": raw["iso3"].astype(str), "year": raw["year"].astype(int),
        "indicator_id": raw["indicator"].map(INDICATORS), "value": raw["value"].astype(float),
    }).dropna(subset=["indicator_id", "value"])
    long["is_forecast"] = long["year"] > last_actual_year
    return long.sort_values(["code", "indicator_id", "year"]).reset_index(drop=True)


def load_long(path: Path = FILE) -> pd.DataFrame:
    """``DataFrame[code, year, indicator_id, value, is_forecast]``; upstream codes (UVK, WBG) untouched."""
    return to_long(pd.read_parquet(path))
