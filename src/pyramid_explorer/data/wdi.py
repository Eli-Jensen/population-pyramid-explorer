"""World Bank: WDI indicators (API v2, no key) and OGHIST historical income classes.

WDI (CC BY 4.0, https://datacatalog.worldbank.org/public-licenses#cc-by): one raw JSON
file per indicator under ``data/raw/econ/wdi/`` holding the API pages verbatim, plus
``countries.json`` (the ``/country`` endpoint) used to drop aggregates (region == "Aggregates").

OGHIST (World Bank "historical classification by income", xlsx): sheet "Country Analytical
History" gives each economy's class per Bank fiscal year FY89.. (FY = calendar-year data
two years earlier).  ``income_class_wb`` is keyed by the FISCAL year (FY89 -> 1989) and
encoded ordinally via :data:`INCOME_CLASS` (L=1, LM=2, UM=3, H=4); ``..`` is missing and a
trailing ``*`` (provisional) is ignored.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import openpyxl
import pandas as pd

from pyramid_explorer.data.base import download
from pyramid_explorer.data.econ_manifest import RAW_ECON, record

SOURCE = "wdi"
SOURCE_OGHIST = "oghist"
API = "https://api.worldbank.org/v2"
WDI_DIR = RAW_ECON / "wdi"
COUNTRIES_FILE = WDI_DIR / "countries.json"
OGHIST_URL = "https://datacatalogfiles.worldbank.org/ddh-published/0037712/DR0090754/OGHIST.xlsx"
OGHIST_FILE = RAW_ECON / "OGHIST.xlsx"
OGHIST_SHEET = "Country Analytical History"
DATE = "1960:2025"
INDICATORS = {
    "NY.GDP.PCAP.PP.KD": "gdppc_ppp_wdi",     # GDP per capita, PPP (constant 2021 int. $)
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_wdi",    # GDP growth (annual %)
    "SP.POP.TOTL": "pop_wdi",                 # population, total (persons)
    "SP.POP.1564.TO.ZS": "wa_share_wdi",      # population ages 15-64 (% of total)
    "NY.GDP.TOTL.RT.ZS": "rents_wdi",         # total natural-resource rents (% of GDP)
}
INCOME_CLASS = {"L": 1, "LM": 2, "UM": 3, "H": 4}
INCOME_INDICATOR = "income_class_wb"
LICENCE = "CC BY 4.0"
REDISTRIBUTABLE = True


def _get_pages(client: httpx.Client, url: str, params: dict) -> list:
    """Follow ``page`` until ``pages`` is exhausted; return the raw page payloads."""
    pages, page = [], 1
    while True:
        r = client.get(url, params={**params, "page": page})
        r.raise_for_status()
        payload = r.json()
        pages.append(payload)
        if page >= int(payload[0].get("pages", 1)):
            return pages
        page += 1


def fetch(*, force: bool = False) -> Path:
    """Download every WDI indicator + the country list + OGHIST; record each in the manifest."""
    WDI_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        targets = {COUNTRIES_FILE: (f"{API}/country", {"format": "json", "per_page": 400})}
        for code in INDICATORS:
            targets[WDI_DIR / f"{code}.json"] = (
                f"{API}/country/all/indicator/{code}", {"format": "json", "per_page": 20000, "date": DATE})
        for file, (url, params) in targets.items():
            if force or not file.exists():
                file.write_text(json.dumps(_get_pages(client, url, params)))
            entry = "wdi:countries" if file == COUNTRIES_FILE else f"wdi:{file.stem}"
            record(entry, file, url=f"{url}?{httpx.QueryParams(params)}", source=SOURCE, licence=LICENCE,
                   redistributable=REDISTRIBUTABLE, notes="WDI API v2 pages verbatim")
    if force and OGHIST_FILE.exists():
        OGHIST_FILE.unlink()
    download(OGHIST_URL, OGHIST_FILE)
    record(SOURCE_OGHIST, OGHIST_FILE, url=OGHIST_URL, source=SOURCE_OGHIST, licence=LICENCE,
           redistributable=REDISTRIBUTABLE,
           notes="WB historical income classification; income_class_wb keyed by fiscal year, L=1 LM=2 UM=3 H=4")
    return WDI_DIR


def aggregate_codes(countries_file: Path = COUNTRIES_FILE) -> set[str]:
    """ISO3 codes the World Bank flags as aggregates (region == "Aggregates")."""
    pages = json.loads(countries_file.read_text())
    return {c["id"] for page in pages for c in page[1] if c["region"]["value"] == "Aggregates"}


def load_long(wdi_dir: Path = WDI_DIR, countries_file: Path | None = None) -> pd.DataFrame:
    """WDI ``DataFrame[code, year, indicator_id, value, is_forecast]`` with aggregates removed."""
    aggregates = aggregate_codes(countries_file or wdi_dir / "countries.json")
    rows = []
    for code, indicator_id in INDICATORS.items():
        for page in json.loads((wdi_dir / f"{code}.json").read_text()):
            for obs in page[1] or []:
                iso3 = obs.get("countryiso3code") or ""
                if obs["value"] is not None and iso3 and iso3 not in aggregates:
                    rows.append((iso3, int(obs["date"]), indicator_id, float(obs["value"])))
    long = pd.DataFrame(rows, columns=["code", "year", "indicator_id", "value"])
    long["is_forecast"] = False
    return long.sort_values(["code", "indicator_id", "year"]).reset_index(drop=True)


def load_income_long(path: Path = OGHIST_FILE) -> pd.DataFrame:
    """OGHIST ``DataFrame[code, year, indicator_id, value, is_forecast]`` (year = fiscal year)."""
    # data_only: some FY header cells are formulas (FY18-FY21 in the 2025 file); read their cached values
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[OGHIST_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    fy_row = next(r for r in rows if r[1] == "Bank's fiscal year:")
    years = {j: 1900 + int(v[2:]) + (100 if int(v[2:]) < 50 else 0)
             for j, v in enumerate(fy_row) if isinstance(v, str) and v.startswith("FY")}
    cols = sorted(years)
    if [years[j] for j in cols] != list(range(years[cols[0]], years[cols[0]] + len(cols))) or \
            cols != list(range(cols[0], cols[0] + len(cols))):
        raise ValueError("OGHIST fiscal-year header is not contiguous; inspect the sheet")
    out = []
    for r in rows:
        code = r[0]
        if not (isinstance(code, str) and len(code) == 3 and code.isupper()):
            continue
        for j, year in years.items():
            v = str(r[j]).rstrip("*") if r[j] is not None else ""
            if v in INCOME_CLASS:
                out.append((code, year, INCOME_INDICATOR, float(INCOME_CLASS[v])))
    long = pd.DataFrame(out, columns=["code", "year", "indicator_id", "value"])
    long["is_forecast"] = False
    return long.sort_values(["code", "indicator_id", "year"]).reset_index(drop=True)
