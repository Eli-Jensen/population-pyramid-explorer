"""UN World Population Prospects 2024 loaders (A1).

Reads the manifest-pinned raw files under ``data/raw/wpp2024/`` and the committed
``pipeline/locations.parquet``. All population figures are thousands of persons (1 July).
Every location with a ``LocTypeName`` is returned (countries AND aggregates); the 234 special
agency aggregates whose ``LocTypeName`` is blank in the CSV are dropped.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from pyramid_explorer.paths import DATA_RAW, LAST_OBSERVED_YEAR, PIPELINE, YEARS

RAW_DIR = DATA_RAW / "wpp2024"
FILES = {
    "population": "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz",
    "indicators": "WPP2024_Demographic_Indicators_Medium.csv.gz",
    "update_zip": "WPP2024_CSV_files_update.zip",
    "population_update": "WPP2024_PopulationByAge5GroupSex_Medium_Update.csv",
    "indicators_update": "WPP2024_Demographic_Indicators_Medium_Update.csv",
    "locations": "WPP2024_F01_LOCATIONS.xlsx",
}
LOCATIONS_PARQUET = PIPELINE / "locations.parquet"

POP_COLS = {"LocID": "locid", "Location": "name", "ISO3_code": "iso3", "LocTypeName": "loctype",
            "Time": "year", "AgeGrpStart": "age_start", "PopMale": "pop_male", "PopFemale": "pop_female"}
IND_COLS = {"LocID": "locid", "ISO3_code": "iso3", "LocTypeName": "loctype", "Time": "year",
            "TPopulation1July": "pop_total", "TPopulationMale1July": "pop_male",
            "TPopulationFemale1July": "pop_female", "MedianAgePop": "median_age", "TFR": "tfr",
            "LEx": "life_expectancy", "LExMale": "life_expectancy_male", "LExFemale": "life_expectancy_female",
            "NetMigrations": "net_migration", "CNMR": "net_migration_rate", "PopGrowthRate": "pop_growth",
            "CBR": "birth_rate", "CDR": "death_rate", "IMR": "infant_mortality", "PopSexRatio": "sex_ratio"}
# indicator id -> (column, name, unit)
WPP_INDICATORS = {
    "pop_total_wpp": ("pop_total", "Total population, 1 July", "thousands"),
    "pop_male_wpp": ("pop_male", "Male population, 1 July", "thousands"),
    "pop_female_wpp": ("pop_female", "Female population, 1 July", "thousands"),
    "median_age_wpp": ("median_age", "Median age", "years"),
    "tfr_wpp": ("tfr", "Total fertility rate", "births per woman"),
    "life_expectancy_wpp": ("life_expectancy", "Life expectancy at birth, both sexes", "years"),
    "life_expectancy_male_wpp": ("life_expectancy_male", "Life expectancy at birth, male", "years"),
    "life_expectancy_female_wpp": ("life_expectancy_female", "Life expectancy at birth, female", "years"),
    "net_migration_wpp": ("net_migration", "Net number of migrants", "thousands"),
    "net_migration_rate_wpp": ("net_migration_rate", "Crude net migration rate", "per 1000"),
    "pop_growth_wpp": ("pop_growth", "Population growth rate", "percent"),
    "birth_rate_wpp": ("birth_rate", "Crude birth rate", "per 1000"),
    "death_rate_wpp": ("death_rate", "Crude death rate", "per 1000"),
    "infant_mortality_wpp": ("infant_mortality", "Infant mortality rate", "per 1000 live births"),
    "sex_ratio_wpp": ("sex_ratio", "Population sex ratio", "males per 100 females"),
}
_CSV_KW = dict(keep_default_na=False, na_values=[""], low_memory=False)  # "NA" is Namibia's ISO2


def load_locations() -> pd.DataFrame:
    """The committed ``pipeline/locations.parquet`` (WPP2024_F01_LOCATIONS.xlsx sheet DB, 326 rows)."""
    return pd.read_parquet(LOCATIONS_PARQUET)


def locations_from_xlsx(xlsx: Path) -> pd.DataFrame:
    """Convert sheet ``DB`` of WPP2024_F01_LOCATIONS.xlsx to a frame (original column names kept)."""
    import openpyxl  # light, only used by fetch_data

    wb = openpyxl.load_workbook(xlsx, read_only=True)
    rows = list(wb["DB"].iter_rows(values_only=True))
    df = pd.DataFrame(rows[1:], columns=[str(c) for c in rows[0]])
    df = df[df["LocID"].notna()].copy()
    for c in ("Index", "LocID", "LocType", "ParentID"):
        df[c] = df[c].astype("int64")
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None else str(v)).astype("string")
    return df.reset_index(drop=True)


def _read_population(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=list(POP_COLS), **_CSV_KW).rename(columns=POP_COLS)
    df = df[df["loctype"].notna()]
    df["iso3"] = df["iso3"].astype(object).where(df["iso3"].notna(), None)
    df["name"] = df["name"].astype(object)
    df["loctype"] = df["loctype"].astype(object)
    df = df.astype({"locid": "int64", "year": "int64", "age_start": "int64"})
    return df[list(POP_COLS.values())].sort_values(["locid", "year", "age_start"]).reset_index(drop=True)


def togo_update_csv(name: str = "population_update") -> Path:
    """Path to an extracted ``*_Update.csv`` from the Togo zip (extracted on first use)."""
    out = RAW_DIR / FILES[name]
    if not out.exists():
        with zipfile.ZipFile(RAW_DIR / FILES["update_zip"]) as z:
            z.extract(FILES[name], RAW_DIR)
    return out


def load_raw_population(patched: bool = True) -> pd.DataFrame:
    """Long frame ``locid, name, iso3, loctype, year, age_start, pop_male, pop_female`` for ALL
    locations, 1950..2100, 21 bins. ``patched=True`` applies the Togo interim update and recomputes
    every aggregate containing Togo (see :func:`pyramid_explorer.patches.apply_togo_patch`)."""
    raw = _read_population(RAW_DIR / FILES["population"])
    if not patched:
        return raw
    from pyramid_explorer.patches import apply_togo_patch

    return apply_togo_patch(raw, togo_update_csv(), load_locations())[0]


def _read_indicators(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=list(IND_COLS), **_CSV_KW).rename(columns=IND_COLS)
    df = df[df["loctype"].notna() & df["year"].between(YEARS[0], YEARS[-1])].copy()  # the file runs to 2101
    df["iso3"] = df["iso3"].astype(object).where(df["iso3"].notna(), None)
    df["loctype"] = df["loctype"].astype(object)
    df = df.astype({"locid": "int64", "year": "int64"})
    df["is_forecast"] = df["year"] > LAST_OBSERVED_YEAR
    return df[list(IND_COLS.values()) + ["is_forecast"]].sort_values(["locid", "year"]).reset_index(drop=True)


def load_indicators() -> pd.DataFrame:
    """Demographic indicators (vanilla) for every location-year: median age, TFR, life expectancy,
    net migration, and ``TPopulation1July`` totals by sex (for the bin-sum check)."""
    return _read_indicators(RAW_DIR / FILES["indicators"])


def load_indicators_update() -> pd.DataFrame:
    """Same columns as :func:`load_indicators` from the Togo interim update (LocID 768 only)."""
    return _read_indicators(togo_update_csv("indicators_update"))
