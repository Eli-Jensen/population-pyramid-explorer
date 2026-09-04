"""Entities (A1): the corpus entity list per CONTRACT §1–2 and PLAN §3.2.

Countries = every WPP ``Country/Area`` row keyed by ISO3 (incl. TWN, XKX), sorted by id; then
aggregates ``agg-<locid>`` from the six kept ``LocTypeName`` kinds minus the deny-list in
``pipeline/names.yaml``, sorted by id. Memberships come from the flag columns of
``pipeline/locations.parquet`` (verified equal to the xlsx ``Aggregation_Lists`` sheet).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pyramid_explorer.paths import DATA_PROCESSED, N_BINS, N_YEARS, PIPELINE

NAMES_YAML = PIPELINE / "names.yaml"
ENTITIES_JSON = DATA_PROCESSED / "entities.json"
AXIS_CHOICES = (10, 12, 14, 17)
MICRO_THRESHOLD = 100.0  # thousands
AGG_KINDS = {"World": "world", "Geographic region": "region", "Subregion": "subregion",
             "SDG region": "sdg", "Income group": "income", "Development group": "dev"}
# locations.parquet flag column -> aggregate locid (value stored in the column is the locid itself)
FLAG_COLS = ["MoreDev", "LessDev", "LeastDev", "oLessDev", "LessDev_ExcludingChina", "LLDC", "SIDS",
             "WB_HUMIC", "WB_LLMIC", "WB_HIC", "WB_LMIC", "WB_MIC", "WB_MUIC", "WB_MLIC", "WB_LIC", "WB_NoIncomeGroup"]
SDG_ID_FIX = {947: 1834, 921: 1831, 927: 1836}  # SDGRegID uses legacy ids for three SDG regions
# SDG regions that duplicate a geographic region / subregion member-for-member are deny-listed in names.yaml
# (1830 ≙ 904 Latin America and the Caribbean, 1836 ≙ 927 Australia/New Zealand); a country's
# ``sdg_region_locid`` points at the entity that exists, never at a deny-listed row.
SDG_ALIAS = {1830: 904, 1836: 927}
REF_COLS = ("subregion_locid", "region_locid", "sdg_region_locid")
INCOME = {"WB_HIC": "HIC", "WB_MUIC": "UMIC", "WB_MLIC": "LMIC", "WB_LIC": "LIC"}


def slugify(name: str) -> str:
    """NFKD → strip combining marks → lowercase → ``[^a-z0-9]+`` → ``-`` → trim."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def load_names() -> dict:
    return yaml.safe_load(NAMES_YAML.read_text())


def _countries(locations: pd.DataFrame) -> pd.DataFrame:
    return locations[locations["LocTypeName"] == "Country/Area"]


def memberships(locations: pd.DataFrame) -> dict[int, list[str]]:
    """locid -> sorted ISO3 members for every aggregate of the six kept kinds (54 in WPP2024)."""
    c = _countries(locations)
    iso = c["ISO3_Code"].astype(str)
    mem: dict[int, set[str]] = {}
    for col, fix in (("GeoRegID", {}), ("SubRegID", {}), ("SDGRegID", SDG_ID_FIX)):
        for v, g in iso.groupby(c[col]):
            mem.setdefault(fix.get(int(v), int(v)), set()).update(g)
    for col in FLAG_COLS:
        if col in c:
            for v, g in iso.groupby(c[col]):
                mem.setdefault(int(v), set()).update(g)
    for wid, g in iso.groupby(c["WorldID"]):
        mem.setdefault(int(wid), set()).update(g)
    # unions that exist as UN rows but have no flag of their own
    if 904 in mem and 905 in mem:
        mem[5505] = mem[904] | mem[905]
    if 1829 in mem and 1836 in mem:
        mem[5502] = mem[1829] | mem[1836]
    return {k: sorted(v) for k, v in sorted(mem.items())}


def _axis_pct(max_share: float) -> int:
    for p in AXIS_CHOICES:
        if max_share * 100 <= p:
            return p
    raise ValueError(f"max single-sex bin share {max_share:.4f} exceeds the largest axis choice")


def _shape_stats(raw: pd.DataFrame) -> pd.DataFrame:
    """Per locid: pop_2026 (thousands) and max single-sex bin share over all years."""
    tot = raw.groupby(["locid", "year"])[["pop_male", "pop_female"]].transform("sum").sum(axis=1)
    share = raw[["pop_male", "pop_female"]].max(axis=1) / tot
    max_share = share.groupby(raw["locid"]).max().rename("max_share")
    y26 = raw[raw["year"] == 2026]
    pop26 = (y26["pop_male"] + y26["pop_female"]).groupby(y26["locid"]).sum().rename("pop_2026")
    return pd.concat([max_share, pop26], axis=1)


def _int_or_none(v) -> int | None:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v) else int(v)


def _notes(v) -> list[str]:
    return [] if v is None or pd.isna(v) else [s.strip() for s in str(v).split(",") if s.strip()]


def build_entities(raw: pd.DataFrame, locations: pd.DataFrame, *, names: dict | None = None,
                   n_agg_range: tuple[int, int] | None = (40, 44)) -> list[dict]:
    """Entity dicts in corpus order (countries by id, then aggregates by id). Reads names.yaml unless
    ``names`` is given; ``n_agg_range`` is the 42 ± 2 aggregate-count guard (None to skip, for fixtures)."""
    names = load_names() if names is None else names
    short_names, extra = names.get("short_names", {}), names.get("aliases", {})
    drop_aliases = names.get("drop_aliases", {}) or {}
    deny = {int(k) for k in names.get("deny_aggregates", {})}
    loc = locations.set_index("LocID")
    raw_names = raw.drop_duplicates("locid").set_index("locid")["name"]
    stats = _shape_stats(raw)
    mem = memberships(locations)
    years_per = raw.groupby("locid")["year"].nunique()
    bins_per = raw.groupby(["locid", "year"])["age_start"].nunique()

    def common(locid: int, key: str, name: str) -> dict:
        if years_per.get(locid, 0) != N_YEARS or (bins_per.loc[locid] != N_BINS).any():
            raise ValueError(f"{key}: expected {N_YEARS} years x {N_BINS} bins in the raw frame")
        short = short_names.get(key, name)
        slug = slugify(short)
        aliases = [key.lower(), slugify(name), slug] + [str(a) for a in extra.get(key, [])]
        aliases = [a for a in aliases if a not in set(drop_aliases.get(key, []))]
        st = stats.loc[locid]
        return {"id": key, "locid": int(locid), "name": name, "short_name": short, "slug": slug,
                "aliases": list(dict.fromkeys(a for a in aliases if a)),
                "pop_2026": round(float(st["pop_2026"]), 3),
                "is_micro": bool(st["pop_2026"] < MICRO_THRESHOLD), "axis_pct": _axis_pct(float(st["max_share"])),
                "notes": _notes(loc.at[locid, "Notes"]) if locid in loc.index else []}

    countries, aggregates = [], []
    for locid, r in _countries(locations).set_index("LocID").iterrows():
        iso3 = str(r["ISO3_Code"])
        if not iso3 or iso3 == "<NA>":
            raise ValueError(f"country locid {locid} has no ISO3")
        if locid not in raw_names.index:
            raise ValueError(f"country {iso3} (locid {locid}) missing from the raw population frame")
        e = common(int(locid), iso3, str(raw_names[locid]))
        iso2 = None if pd.isna(r["ISO2_Code"]) else str(r["ISO2_Code"])
        if iso2:
            e["aliases"] = list(dict.fromkeys([iso3.lower(), iso2.lower(), *e["aliases"]]))
        dev = "least" if not pd.isna(r["LeastDev"]) else ("more" if not pd.isna(r["MoreDev"]) else "less")
        income = next((v for col, v in INCOME.items() if not pd.isna(r[col])), None)
        sdg = SDG_ID_FIX.get(_int_or_none(r["SDGRegID"]), _int_or_none(r["SDGRegID"]))
        e.update({"iso2": iso2, "type": "country",
                  "subregion_locid": _int_or_none(r["SubRegID"]), "region_locid": _int_or_none(r["GeoRegID"]),
                  "sdg_region_locid": SDG_ALIAS.get(sdg, sdg), "income_group": income, "dev_group": dev})
        countries.append(e)
    for locid, r in loc[loc["LocTypeName"].isin(AGG_KINDS)].iterrows():
        locid = int(locid)
        if locid in deny or locid not in raw_names.index:
            continue
        e = common(locid, f"agg-{locid}", str(raw_names[locid]))
        e.update({"iso2": None, "type": "aggregate", "agg_kind": AGG_KINDS[str(r["LocTypeName"])],
                  "parent_locid": _int_or_none(r["ParentID"]), "members": mem[locid],
                  "subregion_locid": None, "region_locid": None, "sdg_region_locid": None,
                  "income_group": None, "dev_group": None})
        aggregates.append(e)

    entities = sorted(countries, key=lambda e: e["id"]) + sorted(aggregates, key=lambda e: e["id"])
    seen: dict[str, str] = {}
    for e in entities:
        for a in [e["slug"], *e["aliases"]]:
            if seen.setdefault(a, e["id"]) != e["id"]:
                raise ValueError(f"duplicate slug/alias {a!r}: {seen[a]} and {e['id']}")
    n_agg = len(aggregates)
    if n_agg_range and not n_agg_range[0] <= n_agg <= n_agg_range[1]:
        raise ValueError(f"expected {n_agg_range[0]}..{n_agg_range[1]} aggregates, got {n_agg}")
    agg_locids = {e["locid"] for e in aggregates}
    dangling = sorted({(c, e[c]) for e in countries for c in REF_COLS if e[c] is not None and e[c] not in agg_locids})
    if dangling:
        raise ValueError(f"country group references that are not entities (deny-listed or absent): {dangling}")
    return entities


def save_entities(entities: list[dict], path: Path | None = None) -> Path:
    path = path or ENTITIES_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entities, ensure_ascii=False, indent=0) + "\n")
    return path


def load_entities() -> list[dict]:
    """Entity dicts in corpus order: from the DuckDB store when it exists, else entities.json."""
    from pyramid_explorer import db

    if db.DB_PATH.exists():
        with db.connect(read_only=True) as con:
            return db.load_entities(con)
    return json.loads(ENTITIES_JSON.read_text())
