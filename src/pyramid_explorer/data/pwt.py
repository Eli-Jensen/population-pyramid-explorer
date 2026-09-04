"""Penn World Table 11.0 (Feenstra, Inklaar & Timmer), CC BY 4.0; 185 countries, 1950-2023.

Source: https://www.rug.nl/ggdc/productivity/pwt/ (dataverse.nl file 554105, ``pwt110.xlsx``).
``fetch()`` prefers the copy already on disk in the pyramid-econ checkout (``paths.PYRAMID_ECON_ROOT``,
or ``fetch_econ.py --from DIR``) and downloads otherwise.  Sheet "Data": countrycode, year, rgdpna/rgdpe (mil. 2021 US$), pop and emp
(millions), hc (index).  All 185 codes are WPP ids (no remap needed).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from pyramid_explorer.data.base import download
from pyramid_explorer.data.econ_manifest import RAW_ECON, record
from pyramid_explorer.paths import PYRAMID_ECON_ROOT

SOURCE = "pwt110"
URL = "https://dataverse.nl/api/access/datafile/554105"
LOCAL_REL = Path("data") / "raw" / "pwt" / "pwt110.xlsx"      # relative to a pyramid-econ checkout
LOCAL_COPY = PYRAMID_ECON_ROOT / LOCAL_REL
FILE = RAW_ECON / "pwt110.xlsx"
SHEET = "Data"
INDICATORS = {"rgdpna": "rgdpna_pwt", "rgdpe": "rgdpe_pwt", "pop": "pop_pwt", "hc": "hc_pwt", "emp": "emp_pwt"}
LICENCE = "CC BY 4.0"
REDISTRIBUTABLE = True


def fetch(*, force: bool = False, local_copy: Path = LOCAL_COPY) -> Path:
    """Copy ``pwt110.xlsx`` from the pyramid-econ checkout, else download; record in the manifest."""
    if force and FILE.exists():
        FILE.unlink()
    if not FILE.exists():
        FILE.parent.mkdir(parents=True, exist_ok=True)
        if local_copy.exists():
            shutil.copyfile(local_copy, FILE)
        else:
            download(URL, FILE)
    record(SOURCE, FILE, url=URL, source=SOURCE, licence=LICENCE, redistributable=REDISTRIBUTABLE,
           notes="PWT 11.0 sheet Data; rgdpna/rgdpe mil. 2021 US$, pop/emp millions, hc index")
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
