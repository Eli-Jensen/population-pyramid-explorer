"""WPP loaders (A1) + the synthetic world shared by test_{patches,entities,shapes,db}.py.

``synthetic_world`` mimics the raw WPP layout with three countries (AAA, BBB and a fake Togo, LocID
768) and two aggregates (World 900 containing everyone, region 903 = {AAA, BBB}); aggregates are exact
member sums rounded to 3 decimals like the UN files. A Togo ``_Update.csv`` scales TGO by 1.1.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer.data import wpp
from pyramid_explorer.paths import AGE_STARTS, LAST_OBSERVED_YEAR, N_BINS, N_YEARS, YEARS

RAW_PRESENT = (wpp.RAW_DIR / wpp.FILES["population"]).exists()
COUNTRIES = [  # locid, name, iso3, iso2, scale (thousands at age 0), dev flag col, income col
    (1, "Aaaland", "AAA", "AA", 900.0, "MoreDev", "WB_HIC"),
    (2, "Beeland", "BBB", "BB", 2500.0, "LessDev", "WB_MLIC"),
    (768, "Togo", "TGO", "TG", 600.0, "LeastDev", "WB_LIC"),
]
NAMES = {"short_names": {"TGO": "Togo", "agg-900": "World"}, "aliases": {"AAA": ["aaa-land", "aa-land"]},
         "drop_aliases": {}, "deny_aggregates": {}}
NA = np.nan


def _block(rng: np.random.Generator, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """(male, female) [151, 21] thousands: an ageing population, 3-decimal like the UN."""
    ages = np.arange(N_BINS) * 5.0
    k = 0.045 + 0.0002 * (np.arange(N_YEARS))[:, None]           # older every year
    base = scale * np.exp(-k * ages[None, :]) * (1 + 0.004 * np.arange(N_YEARS))[:, None]
    m = np.round(base * 0.51 * rng.uniform(0.95, 1.05, base.shape), 3)
    f = np.round(base * 0.49 * rng.uniform(0.95, 1.05, base.shape), 3)
    return m, f


def _long(locid: int, name: str, iso3: str | None, loctype: str, m: np.ndarray, f: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"locid": locid, "name": name, "iso3": iso3, "loctype": loctype,
                         "year": np.repeat(YEARS, N_BINS), "age_start": np.tile(AGE_STARTS, N_YEARS),
                         "pop_male": m.ravel(), "pop_female": f.ravel()})


def _indicators(blocks: dict[int, tuple[np.ndarray, np.ndarray]], loc: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    meta = loc.set_index("LocID")
    for locid, (m, f) in blocks.items():
        pm, pf = np.round(m.sum(1), 3), np.round(f.sum(1), 3)
        d = {"locid": locid, "iso3": meta.at[locid, "ISO3_Code"], "loctype": meta.at[locid, "LocTypeName"],
             "year": YEARS, "pop_total": np.round(pm + pf, 3), "pop_male": pm, "pop_female": pf}
        for col in wpp.IND_COLS.values():
            if col not in d:
                d[col] = rng.uniform(1, 50, N_YEARS)
        rows.append(pd.DataFrame(d))
    df = pd.concat(rows, ignore_index=True)
    df["iso3"] = df["iso3"].astype(object).where(df["iso3"].notna(), None)
    df["is_forecast"] = df["year"] > LAST_OBSERVED_YEAR
    return df[list(wpp.IND_COLS.values()) + ["is_forecast"]]


def synthetic_world(tmp_dir: Path, seed: int = 0) -> SimpleNamespace:
    """Raw frame, locations, Togo update CSV, indicators (+ update), names — all deterministic."""
    rng = np.random.default_rng(seed)
    loc_rows = [
        {"LocID": 900, "Location": "World", "ISO3_Code": None, "ISO2_Code": None, "LocTypeName": "World", "LocType": 1,
         "ParentID": 0, "WorldID": NA, "GeoRegID": NA, "SubRegID": NA, "SDGRegID": NA, "Notes": None},
        {"LocID": 903, "Location": "Africa", "ISO3_Code": None, "ISO2_Code": None, "LocTypeName": "Geographic region",
         "LocType": 2, "ParentID": 900, "WorldID": NA, "GeoRegID": NA, "SubRegID": NA, "SDGRegID": NA, "Notes": None},
    ]
    flags = ["MoreDev", "LessDev", "LeastDev", "WB_HIC", "WB_MUIC", "WB_MLIC", "WB_LIC"]
    flag_ids = {"MoreDev": 901, "LessDev": 902, "LeastDev": 941, "WB_HIC": 1503, "WB_MUIC": 1502, "WB_MLIC": 1501, "WB_LIC": 1500}
    for locid, name, iso3, iso2, _, dev, inc in COUNTRIES:
        r = {"LocID": locid, "Location": name, "ISO3_Code": iso3, "ISO2_Code": iso2, "LocTypeName": "Country/Area",
             "LocType": 4, "ParentID": 903, "WorldID": 900, "GeoRegID": 903 if iso3 != "TGO" else NA, "SubRegID": NA,
             "SDGRegID": NA, "Notes": "1, 2" if iso3 == "TGO" else None}
        r.update({c: NA for c in flags})
        r[dev], r[inc] = flag_ids[dev], flag_ids[inc]
        if dev == "LeastDev":
            r["LessDev"] = flag_ids["LessDev"]
        loc_rows.append(r)
    loc = pd.DataFrame(loc_rows)
    for c in ("Index",):
        loc[c] = range(len(loc))
    for c in flags:
        loc[c] = loc[c].astype(float)

    blocks: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for locid, _, _, _, scale, _, _ in COUNTRIES:
        blocks[locid] = _block(rng, scale)
    blocks[900] = tuple(np.round(sum(blocks[l][i] for l in (1, 2, 768)), 3) for i in range(2))
    blocks[903] = tuple(np.round(blocks[1][i] + blocks[2][i], 3) for i in range(2))
    parts = [_long(l, n, i, "Country/Area", *blocks[l]) for l, n, i, *_ in COUNTRIES]
    parts += [_long(900, "World", None, "World", *blocks[900]), _long(903, "Africa", None, "Geographic region", *blocks[903])]
    raw = pd.concat(parts, ignore_index=True).sort_values(["locid", "year", "age_start"]).reset_index(drop=True)

    up_m, up_f = (np.round(b * 1.1, 3) for b in blocks[768])
    update_csv = tmp_dir / wpp.FILES["population_update"]
    pd.DataFrame({"LocID": 768, "Location": "Togo", "ISO3_code": "TGO", "LocTypeName": "Country/Area",
                  "Time": np.repeat(YEARS, N_BINS), "AgeGrpStart": np.tile(AGE_STARTS, N_YEARS),
                  "PopMale": up_m.ravel(), "PopFemale": up_f.ravel()}).to_csv(update_csv, index=False)
    ind = _indicators(blocks, loc, rng)
    ind_update = _indicators({768: (up_m, up_f)}, loc, rng)
    return SimpleNamespace(loc=loc, raw=raw, update_csv=update_csv, indicators=ind, indicators_update=ind_update,
                           names=NAMES, blocks=blocks, update=(up_m, up_f))


@pytest.fixture(scope="session")
def world(tmp_path_factory) -> SimpleNamespace:
    return synthetic_world(tmp_path_factory.mktemp("world"))


# ----------------------------------------------------------------------------- synthetic layout

def test_synthetic_world_matches_contract_layout(world):
    assert list(world.raw.columns) == ["locid", "name", "iso3", "loctype", "year", "age_start", "pop_male", "pop_female"]
    assert world.raw.groupby("locid").size().eq(N_YEARS * N_BINS).all()
    assert world.raw.loc[world.raw["locid"] == 900, "iso3"].isna().all()
    assert set(world.indicators.columns) == set(wpp.IND_COLS.values()) | {"is_forecast"}
    assert set(world.indicators_update["locid"]) == {768}


def test_synthetic_aggregates_are_member_sums(world):
    r = world.raw
    key = ["year", "age_start"]
    val = ["pop_male", "pop_female"]
    members = r[r["iso3"].notna()].groupby(key)[val].sum()
    world_ = r[r["locid"] == 900].set_index(key)[val]
    assert np.allclose(members.to_numpy(), world_.to_numpy(), atol=0.002)


# ----------------------------------------------------------------------------- committed locations

def test_load_locations_committed_parquet():
    loc = wpp.load_locations()
    assert len(loc) == 326
    countries = loc[loc["LocTypeName"] == "Country/Area"]
    assert len(countries) == 237
    assert countries["ISO3_Code"].notna().all() and countries["ISO3_Code"].is_unique
    assert {"TWN", "XKX", "NAM"} <= set(countries["ISO3_Code"])
    assert loc.loc[loc["LocID"] == 900, "LocTypeName"].item() == "World"
    for c in ("GeoRegID", "SubRegID", "SDGRegID", "WB_HIC", "LeastDev"):
        assert c in loc.columns


@pytest.mark.skipif(not (wpp.RAW_DIR / wpp.FILES["locations"]).exists(), reason="LOCATIONS.xlsx not fetched")
def test_locations_from_xlsx_equals_committed_parquet():
    fresh = wpp.locations_from_xlsx(wpp.RAW_DIR / wpp.FILES["locations"])
    loc = wpp.load_locations()
    assert len(fresh) == len(loc)
    assert fresh["LocID"].tolist() == loc["LocID"].tolist()
    assert fresh["ISO3_Code"].fillna("").tolist() == loc["ISO3_Code"].fillna("").tolist()


# ----------------------------------------------------------------------------- real files (slow)

@pytest.mark.slow
@pytest.mark.skipif(not RAW_PRESENT, reason="raw WPP files not fetched (make data)")
def test_load_raw_population_all_locations():
    raw = wpp.load_raw_population(patched=False)
    assert list(raw.columns) == ["locid", "name", "iso3", "loctype", "year", "age_start", "pop_male", "pop_female"]
    assert raw["loctype"].notna().all()
    sizes = raw.groupby("locid").size()
    assert (sizes == N_YEARS * N_BINS).all()
    countries = raw[raw["loctype"] == "Country/Area"]
    assert countries["iso3"].nunique() == 237 and countries["iso3"].notna().all()
    assert raw.loc[raw["locid"] == 900, "iso3"].isna().all()
    assert (raw[["pop_male", "pop_female"]] >= 0).all().all()
    assert raw["year"].min() == 1950 and raw["year"].max() == 2100


@pytest.mark.slow
@pytest.mark.skipif(not RAW_PRESENT, reason="raw WPP files not fetched (make data)")
def test_load_indicators_and_update():
    ind = wpp.load_indicators()
    assert {"locid", "year", "pop_total", "pop_male", "pop_female", "median_age", "tfr", "life_expectancy",
            "net_migration", "is_forecast"} <= set(ind.columns)
    assert ind.groupby("locid").size().eq(N_YEARS).all()
    assert (ind["is_forecast"] == (ind["year"] > LAST_OBSERVED_YEAR)).all()
    up = wpp.load_indicators_update()
    assert set(up["locid"]) == {768} and len(up) == N_YEARS
    assert list(up.columns) == list(ind.columns)
