"""Togo interim-update patch (A1, PLAN §3.2 five-step rule)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pyramid_explorer import patches
from pyramid_explorer.data import wpp
from pyramid_explorer.paths import N_BINS, N_YEARS
from tests.test_wpp import RAW_PRESENT, synthetic_world

KEY, VAL = ["year", "age_start"], ["pop_male", "pop_female"]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return synthetic_world(tmp_path_factory.mktemp("patch"))


@pytest.fixture(scope="module")
def applied(world):
    return patches.apply_togo_patch(world.raw, world.update_csv, world.loc)


def _block(df: pd.DataFrame, locid: int) -> pd.DataFrame:
    return df[df["locid"] == locid].sort_values(KEY).set_index(KEY)[VAL]


def test_read_update_rejects_wrong_locid(world, tmp_path):
    bad = pd.read_csv(world.update_csv)
    bad["LocID"] = 4
    p = tmp_path / "bad_locid.csv"
    bad.to_csv(p, index=False)
    with pytest.raises(ValueError, match="only LocID 768"):
        patches.read_update(p)


def test_read_update_rejects_wrong_row_count(world, tmp_path):
    bad = pd.read_csv(world.update_csv).iloc[:-1]
    p = tmp_path / "bad_rows.csv"
    bad.to_csv(p, index=False)
    with pytest.raises(ValueError, match=f"{N_YEARS} x {N_BINS}"):
        patches.read_update(p)


def test_togo_rows_replaced_and_frame_shape_kept(world, applied):
    patched, record = applied
    assert len(patched) == len(world.raw) and list(patched.columns) == list(world.raw.columns)
    up_m, up_f = world.update
    tgo = _block(patched, 768)
    assert np.array_equal(tgo["pop_male"].to_numpy(), up_m.ravel())
    assert np.array_equal(tgo["pop_female"].to_numpy(), up_f.ravel())
    assert not np.array_equal(tgo["pop_male"].to_numpy(), _block(world.raw, 768)["pop_male"].to_numpy())
    assert patched.loc[patched["locid"] == 768, "iso3"].eq("TGO").all()


def test_record_fields(applied):
    _, record = applied
    assert record["id"] == "togo-2026-01-19" and record["locids"] == [768] and record["applied"]
    assert record["recomputed_aggregates"] == [900]         # region 903 does not contain TGO
    assert record["source_id"] == "wpp2024-togo-update"


def test_identity_patched_minus_vanilla(world, applied):
    """patched_agg − vanilla_agg == patched_TGO − vanilla_TGO per year and bin (rounding bound)."""
    patched, _ = applied
    d_tgo = _block(patched, 768) - _block(world.raw, 768)
    d_world = _block(patched, 900) - _block(world.raw, 900)
    tol = patches.recompute_tolerance(3)
    assert (np.abs(d_world.to_numpy() - d_tgo.to_numpy()) <= tol).all()
    assert np.abs(d_tgo.to_numpy()).max() > 1.0  # the patch actually changed something


def test_untouched_aggregates_and_countries_are_byte_identical(world, applied):
    patched, _ = applied
    for locid in (1, 2, 903):
        assert _block(patched, locid).equals(_block(world.raw, locid))


def test_recomputed_aggregate_equals_member_sum(world, applied):
    patched, _ = applied
    members = patched[patched["iso3"].notna()].groupby(KEY)[VAL].sum().sort_index()
    assert np.allclose(_block(patched, 900).to_numpy(), members.to_numpy(), atol=1e-9)


def test_restrict_to_entities(applied):
    _, record = applied
    ents = [{"id": "TGO", "locid": 768}, {"id": "agg-900", "locid": 900}, {"id": "agg-903", "locid": 903}]
    kept = patches.restrict_to_entities(record, ents)
    assert kept["recomputed_aggregates"] == [900] and kept["recomputed_non_entities"] == []
    dropped = patches.restrict_to_entities({**record, "recomputed_aggregates": [900, 948, 5504]}, ents)
    assert dropped["recomputed_aggregates"] == [900] and dropped["recomputed_non_entities"] == [948, 5504]
    assert record["recomputed_aggregates"] == [900]                       # input untouched
    assert patches.restrict_to_entities(record, [{"id": "AAA"}]) is record  # fixtures without locids: no-op
    assert "remain the UN's vanilla values" in record["note"]              # indicators of recomputed aggregates


def test_missing_togo_block_raises(world):
    with pytest.raises(ValueError, match="no complete TGO block"):
        patches.apply_togo_patch(world.raw[world.raw["locid"] != 768], world.update_csv, world.loc)


# ----------------------------------------------------------------------------- real files (slow)

@pytest.mark.slow
@pytest.mark.skipif(not RAW_PRESENT or not (wpp.RAW_DIR / wpp.FILES["update_zip"]).exists(), reason="raw WPP files not fetched")
def test_real_togo_patch():
    raw = wpp.load_raw_population(patched=False)
    patched, record = patches.apply_togo_patch(raw, wpp.togo_update_csv(), wpp.load_locations())
    before = _block(raw, 768).loc[2022].sum().sum()
    after = _block(patched, 768).loc[2022].sum().sum()
    assert 8000 < after < 8500 and abs(after - before) > 100          # ≈ 8.2 M after the 2022 census
    assert {900, 903, 914, 1834, 902, 941, 1500} <= set(record["recomputed_aggregates"])
    assert len(patched) == len(raw)
    d_tgo = _block(patched, 768) - _block(raw, 768)
    for locid in record["recomputed_aggregates"]:
        d_agg = _block(patched, locid) - _block(raw, locid)
        assert (np.abs(d_agg.to_numpy() - d_tgo.to_numpy()) <= 0.001 * 237).all(), locid
    untouched = sorted(set(raw["locid"]) - set(record["recomputed_aggregates"]) - {768})
    v = raw[raw["locid"].isin(untouched)].sort_values(["locid", *KEY])[VAL].to_numpy()
    p = patched[patched["locid"].isin(untouched)].sort_values(["locid", *KEY])[VAL].to_numpy()
    assert np.array_equal(v, p)
