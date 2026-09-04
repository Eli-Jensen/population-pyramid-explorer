"""Maddison Project Database 2023 (Bolt & van Zanden), CC BY 4.0.

Source: https://www.rug.nl/ggdc/historicaldevelopment/maddison/ (dataverse.nl file 421302,
``mpd2023_web.xlsx``).  Sheet "Full data": countrycode, country, region, year, gdppc
(2011 int. $), pop (thousands).  Codes are left as upstream (CSK/SUN/YUG dropped later
by ``econ_iso3``).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from pyramid_explorer.data.base import download
from pyramid_explorer.data.econ_manifest import RAW_ECON, record

SOURCE = "maddison2023"
URL = "https://dataverse.nl/api/access/datafile/421302"
FILE = RAW_ECON / "mpd2023_web.xlsx"
SHEET = "Full data"
INDICATORS = {"gdppc": "gdppc_maddison", "pop": "pop_maddison"}
LICENCE = "CC BY 4.0"
REDISTRIBUTABLE = True


def fetch(*, force: bool = False) -> Path:
    """Download ``mpd2023_web.xlsx`` (skipped when present) and record it in the manifest."""
    if force and FILE.exists():
        FILE.unlink()
    download(URL, FILE)
    record(SOURCE, FILE, url=URL, source=SOURCE, licence=LICENCE, redistributable=REDISTRIBUTABLE,
           notes="Maddison Project Database 2023; gdppc in 2011 int. $, pop in thousands")
    return FILE


def load_long(path: Path = FILE) -> pd.DataFrame:
    """``DataFrame[code, year, indicator_id, value, is_forecast]``; all rows are observed."""
    raw = pd.read_excel(path, sheet_name=SHEET, usecols=["countrycode", "year", *INDICATORS])
    long = raw.melt(id_vars=["countrycode", "year"], value_vars=list(INDICATORS),
                    var_name="indicator_id", value_name="value").dropna(subset=["value"])
    long["indicator_id"] = long["indicator_id"].map(INDICATORS)
    long = long.rename(columns={"countrycode": "code"})
    long["year"] = long["year"].astype(int)
    long["value"] = long["value"].astype(float)
    long["is_forecast"] = False
    return long.sort_values(["code", "indicator_id", "year"]).reset_index(drop=True)
