"""Patches (A1): the UN's 19 Jan 2026 interim update for Togo (PLAN §3.2 five-step rule).

1. (caller) member sums verified on the unpatched frame;
2. the ``_Update.csv`` must contain only LocID 768 and exactly 151 x 21 rows — replace TGO rows;
3. every aggregate whose membership contains TGO is recomputed as the sum of patched members;
4. identity ``patched_agg − vanilla_agg == patched_TGO − vanilla_TGO`` per year and bin, within the
   3-decimal rounding bound of the member sum (checked here and again in the DB);
5. the patch record is returned for ``meta.patches`` / the ``patch`` table.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer.data.wpp import POP_COLS, _CSV_KW
from pyramid_explorer.entities import memberships
from pyramid_explorer.paths import N_BINS, N_YEARS

TOGO_LOCID, TOGO_ISO3 = 768, "TGO"
PATCH_ID, PATCH_SOURCE = "togo-2026-01-19", "wpp2024-togo-update"
KEY = ["year", "age_start"]
VAL = ["pop_male", "pop_female"]


def read_update(update_csv: Path) -> pd.DataFrame:
    """The Togo update rows in the raw-frame layout; asserts LocID 768 only and 151 x 21 rows."""
    up = pd.read_csv(update_csv, usecols=list(POP_COLS), **_CSV_KW).rename(columns=POP_COLS)
    if set(up["locid"]) != {TOGO_LOCID}:
        raise ValueError(f"update must contain only LocID {TOGO_LOCID}, got {sorted(set(up['locid']))}")
    if len(up) != N_YEARS * N_BINS or up["year"].nunique() != N_YEARS or up["age_start"].nunique() != N_BINS:
        raise ValueError(f"update must have {N_YEARS} x {N_BINS} rows, got {len(up)}")
    up = up.astype({"locid": "int64", "year": "int64", "age_start": "int64"})
    return up[list(POP_COLS.values())].sort_values(KEY).reset_index(drop=True)


def _sum_members(countries: pd.DataFrame, members: list[str]) -> pd.DataFrame:
    return countries[countries["iso3"].isin(members)].groupby(KEY)[VAL].sum().sort_index()


def recompute_tolerance(n_members: int) -> float:
    """Per-bin rounding bound: members are published to 3 decimals (±0.0005k each)."""
    return 0.001 * n_members


def apply_togo_patch(raw: pd.DataFrame, update_csv: Path, locations: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return (patched frame, patch record). Aggregates whose members contain TGO are recomputed."""
    update = read_update(update_csv)
    vanilla_tgo = raw[raw["locid"] == TOGO_LOCID].sort_values(KEY).set_index(KEY)[VAL]
    if len(vanilla_tgo) != N_YEARS * N_BINS:
        raise ValueError("raw frame has no complete TGO block to patch")
    meta = raw.loc[raw["locid"] == TOGO_LOCID, ["name", "iso3", "loctype"]].iloc[0]
    update[["name", "iso3", "loctype"]] = meta.values
    out = pd.concat([raw[raw["locid"] != TOGO_LOCID], update[raw.columns]], ignore_index=True)

    countries = out[out["iso3"].notna()]
    delta_tgo = update.set_index(KEY)[VAL] - vanilla_tgo  # patched − vanilla
    recomputed: list[int] = []
    pieces = [out]
    present = set(out["locid"])
    for locid, members in memberships(locations).items():
        if TOGO_ISO3 not in members or locid not in present:
            continue
        agg = out[out["locid"] == locid]
        new = _sum_members(countries, members)
        old = agg.set_index(KEY)[VAL].sort_index()
        diff = (new - old) - delta_tgo.reindex(new.index)  # (patched−vanilla)_agg − (patched−vanilla)_TGO
        tol = recompute_tolerance(len(members))
        if not (diff.abs().to_numpy() <= tol).all():
            raise ValueError(f"patch identity failed for aggregate {locid}: max |diff| {diff.abs().max().max():.4f} > {tol}")
        rep = agg.sort_values(KEY).copy()
        rep[VAL] = new.to_numpy()
        pieces.append(rep)
        out = out[out["locid"] != locid]
        pieces[0] = out
        recomputed.append(locid)
    patched = pd.concat(pieces, ignore_index=True).sort_values(["locid", "year", "age_start"]).reset_index(drop=True)
    if not np.isfinite(patched[VAL].to_numpy()).all() or (patched[VAL].to_numpy() < 0).any():
        raise ValueError("patched frame has negative or non-finite populations")
    record = {"id": PATCH_ID, "source_id": PATCH_SOURCE, "applied": True, "locids": [TOGO_LOCID],
              "recomputed_aggregates": sorted(recomputed),
              "note": "UN interim update for Togo (2022 census); aggregates containing Togo recomputed from "
                      "members by this site — the UN did not revise aggregates. Demographic indicators of the "
                      "recomputed aggregates (pop_total_wpp, median_age_wpp, …) remain the UN's vanilla values."}
    return patched, record


def restrict_to_entities(record: dict, entities: list[dict]) -> dict:
    """Keep only entity locids in ``recomputed_aggregates`` (the frame recomputes every aggregate containing
    Togo, incl. deny-listed unions the site never ships); the rest move to ``recomputed_non_entities``. No-op
    when the entities carry no locids (fixtures)."""
    known = {e["locid"] for e in entities if "locid" in e}
    if not known:
        return record
    rec = dict(record)
    rec["recomputed_aggregates"] = [l for l in record["recomputed_aggregates"] if l in known]
    rec["recomputed_non_entities"] = [l for l in record["recomputed_aggregates"] if l not in known]
    return rec
