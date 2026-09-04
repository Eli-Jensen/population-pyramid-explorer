"""Entities (A1): slugify, build_entities on the synthetic world, and the real entities.json (slow)."""
from __future__ import annotations

import json

import pytest

from pyramid_explorer import entities as E
from pyramid_explorer.paths import DATA_PROCESSED
from tests.test_wpp import synthetic_world

SLUG_TABLE = [
    ("Réunion", "reunion"), ("Côte d'Ivoire", "cote-d-ivoire"), ("Curaçao", "curacao"),
    ("São Tomé and Príncipe", "sao-tome-and-principe"), ("Türkiye", "turkiye"), ("Saint Barthélemy", "saint-barthelemy"),
    ("Bolivia (Plurinational State of)", "bolivia-plurinational-state-of"), ("  China, Hong Kong SAR ", "china-hong-kong-sar"),
    ("Lao People's Democratic Republic", "lao-people-s-democratic-republic"), ("100+", "100"),
]
# populationpyramid.net-style ASCII slugs (UN names slugified, or names.yaml aliases) that must resolve
PPNET_SAMPLE = ["united-states-of-america", "republic-of-korea", "viet-nam", "russian-federation", "china", "india",
                "japan", "germany", "france", "brazil", "nigeria", "turkiye", "cote-divoire",
                "democratic-republic-of-the-congo", "united-republic-of-tanzania", "bolivia-plurinational-state-of",
                "iran-islamic-republic-of", "lao-people-s-democratic-republic", "syrian-arab-republic",
                "venezuela-bolivarian-republic-of", "republic-of-moldova", "world"]


@pytest.mark.parametrize("name,slug", SLUG_TABLE)
def test_slugify_table(name, slug):
    assert E.slugify(name) == slug


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return synthetic_world(tmp_path_factory.mktemp("ent"))


@pytest.fixture(scope="module")
def ents(world):
    return E.build_entities(world.raw, world.loc, names=world.names, n_agg_range=None)


def test_corpus_order_and_types(ents):
    assert [e["id"] for e in ents] == ["AAA", "BBB", "TGO", "agg-900", "agg-903"]
    assert [e["type"] for e in ents] == ["country"] * 3 + ["aggregate"] * 2


def test_country_fields(ents):
    tgo = next(e for e in ents if e["id"] == "TGO")
    assert tgo["locid"] == 768 and tgo["iso2"] == "TG" and tgo["name"] == "Togo" and tgo["short_name"] == "Togo"
    assert tgo["slug"] == "togo" and tgo["aliases"][:2] == ["tgo", "tg"] and "togo" in tgo["aliases"]
    assert tgo["income_group"] == "LIC" and tgo["dev_group"] == "least" and tgo["notes"] == ["1", "2"]
    assert tgo["region_locid"] is None and tgo["subregion_locid"] is None and tgo["sdg_region_locid"] is None
    aaa = next(e for e in ents if e["id"] == "AAA")
    assert aaa["income_group"] == "HIC" and aaa["dev_group"] == "more" and aaa["region_locid"] == 903
    assert {"aaa-land", "aa-land", "aaaland"} <= set(aaa["aliases"])
    bbb = next(e for e in ents if e["id"] == "BBB")
    assert bbb["income_group"] == "LMIC" and bbb["dev_group"] == "less"
    for e in ents:
        assert set(e) >= {"id", "locid", "iso2", "name", "short_name", "slug", "aliases", "type", "subregion_locid",
                          "region_locid", "sdg_region_locid", "income_group", "dev_group", "pop_2026", "is_micro",
                          "axis_pct", "notes"}
        assert e["axis_pct"] in E.AXIS_CHOICES and isinstance(e["is_micro"], bool)


def test_aggregate_fields_and_members(ents):
    w = next(e for e in ents if e["id"] == "agg-900")
    assert w["agg_kind"] == "world" and w["members"] == ["AAA", "BBB", "TGO"] and w["iso2"] is None
    assert w["slug"] == "world" and w["parent_locid"] == 0
    a = next(e for e in ents if e["id"] == "agg-903")
    assert a["agg_kind"] == "region" and a["members"] == ["AAA", "BBB"] and a["parent_locid"] == 900


def test_axis_pct_and_is_micro(world, ents):
    """axis_pct = smallest of {10,12,14,17} covering the max single-sex bin share; is_micro on pop_2026."""
    r = world.raw
    tot = r.groupby(["locid", "year"])[["pop_male", "pop_female"]].transform("sum").sum(axis=1)
    mx = (r[["pop_male", "pop_female"]].max(axis=1) / tot).groupby(r["locid"]).max()
    for e in ents:
        expect = next(p for p in E.AXIS_CHOICES if mx[e["locid"]] * 100 <= p)
        assert e["axis_pct"] == expect
        y26 = r[(r["locid"] == e["locid"]) & (r["year"] == 2026)]
        pop = float(y26["pop_male"].sum() + y26["pop_female"].sum())
        assert e["pop_2026"] == pytest.approx(pop, abs=1e-3) and e["is_micro"] == (pop < 100)


def test_duplicate_alias_fails(world):
    names = {**world.names, "aliases": {"AAA": ["beeland"]}}   # collides with BBB's UN-name slug
    with pytest.raises(ValueError, match="duplicate slug/alias"):
        E.build_entities(world.raw, world.loc, names=names, n_agg_range=None)


def test_deny_list_and_count_guard(world):
    names = {**world.names, "deny_aggregates": {903: "test"}}
    with pytest.raises(ValueError, match="not entities"):          # AAA/BBB point at region 903: denying it dangles them
        E.build_entities(world.raw, world.loc, names=names, n_agg_range=None)
    loc = world.loc.copy()
    loc["GeoRegID"] = float("nan")
    ents = E.build_entities(world.raw, loc, names=names, n_agg_range=None)
    assert [e["id"] for e in ents if e["type"] == "aggregate"] == ["agg-900"]
    assert all(e["region_locid"] is None for e in ents if e["type"] == "country")
    with pytest.raises(ValueError, match="aggregates"):
        E.build_entities(world.raw, world.loc, names=world.names, n_agg_range=(40, 44))


def test_dangling_group_reference_fails(world):
    """A country whose region/subregion/SDG id is not an entity (deny-listed or absent) fails the build."""
    loc = world.loc.copy()
    loc.loc[loc["ISO3_Code"] == "AAA", "GeoRegID"] = 999
    with pytest.raises(ValueError, match="not entities"):
        E.build_entities(world.raw, loc, names=world.names, n_agg_range=None)
    assert E.SDG_ALIAS == {1830: 904, 1836: 927}                       # deny-listed SDG duplicates → the shipped twin
    assert set(E.SDG_ALIAS) <= {int(k) for k in E.load_names()["deny_aggregates"]}


def test_missing_years_fails(world):
    raw = world.raw[~((world.raw["locid"] == 2) & (world.raw["year"] == 2100))]
    with pytest.raises(ValueError, match="151 years x 21 bins"):
        E.build_entities(raw, world.loc, names=world.names, n_agg_range=None)


def test_save_and_load_roundtrip(ents, tmp_path, monkeypatch):
    p = E.save_entities(ents, tmp_path / "entities.json")
    monkeypatch.setattr(E, "ENTITIES_JSON", p)
    import pyramid_explorer.db as db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "absent.duckdb")
    assert E.load_entities() == ents


def test_real_names_yaml_deny_list_has_reasons():
    names = E.load_names()
    deny = names["deny_aggregates"]
    assert {1518, 5502, 5503, 5504, 1859, 1517, 934, 948, 5505} <= {int(k) for k in deny}
    assert all(isinstance(v, str) and v for v in deny.values())
    for key in ("TWN", "XKX", "KOR", "PRK", "USA", "RUS", "IRN", "VNM", "LAO", "SYR", "BOL", "VEN", "TZA", "TUR",
                "FSM", "HKG", "MAC", "REU", "CIV", "COD", "PSE", "MDA", "BRN"):
        assert key in names["short_names"], key


# ----------------------------------------------------------------------------- real entities (slow)

REAL = DATA_PROCESSED / "entities.json"


def _real() -> list[dict]:
    ents = json.loads(REAL.read_text())
    if any("PROVISIONAL" in e.get("notes", []) for e in ents):
        pytest.skip("entities.json is the provisional corpus")
    return ents


@pytest.mark.slow
@pytest.mark.skipif(not REAL.exists(), reason="entities.json not built")
def test_real_entities_counts_and_order():
    ents = _real()
    countries = [e for e in ents if e["type"] == "country"]
    aggs = [e for e in ents if e["type"] == "aggregate"]
    assert len(countries) == 237 and 40 <= len(aggs) <= 44
    assert [e["id"] for e in ents] == sorted(e["id"] for e in countries) + sorted(e["id"] for e in aggs)
    assert {"TWN", "XKX"} <= {e["id"] for e in countries}
    deny = {int(k) for k in E.load_names()["deny_aggregates"]}
    assert not {e["locid"] for e in aggs} & deny
    assert all(len(e["id"]) == 3 and e["iso2"] for e in countries)
    assert {e["agg_kind"] for e in aggs} == set(E.AGG_KINDS.values())
    agg_locids = {e["locid"] for e in aggs}
    for c in countries:                                                  # every group reference is a shipped entity
        for col in E.REF_COLS:
            assert c[col] is None or c[col] in agg_locids, (c["id"], col, c[col])
    sdg = {c["sdg_region_locid"] for c in countries}
    assert not sdg & set(E.SDG_ALIAS) and {904, 927} <= sdg              # LAC / Australia-NZ point at the real rows


@pytest.mark.slow
@pytest.mark.skipif(not REAL.exists(), reason="entities.json not built")
def test_real_aliases_unique_and_ppnet_sample_resolves():
    ents = _real()
    seen: dict[str, str] = {}
    for e in ents:
        for a in [e["slug"], *e["aliases"]]:
            assert seen.setdefault(a, e["id"]) == e["id"], a
    for slug in PPNET_SAMPLE:
        assert slug in seen, slug
    assert seen["usa"] == "USA" and seen["south-korea"] == "KOR" and seen["turkey"] == "TUR"
    assert seen["ivory-coast"] == "CIV" and seen["dr-congo"] == "COD" and seen["palestine"] == "PSE"
    by = {e["id"]: e for e in ents}
    assert by["TWN"]["short_name"] == "Taiwan" and by["XKX"]["short_name"] == "Kosovo"
    assert by["KOR"]["short_name"] == "South Korea" and by["TUR"]["short_name"] == "Türkiye"
    assert by["agg-900"]["members"] and len(by["agg-900"]["members"]) == 237
