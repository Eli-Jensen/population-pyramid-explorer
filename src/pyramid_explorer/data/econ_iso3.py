"""Upstream ISO3 codes -> WPP entity ids, per source family (pipeline/econ_iso3.yaml).

Loaders keep upstream codes untouched; ``db.ingest_indicators`` calls
:func:`apply_remap` and stores the returned orphans in ``source_orphan`` so
no code is ever dropped silently.
"""
from __future__ import annotations

import json

import pandas as pd
import yaml

from pyramid_explorer.paths import DATA_PROCESSED, PIPELINE

RULES = PIPELINE / "econ_iso3.yaml"
FAMILIES = ("maddison", "pwt", "wdi", "oghist", "weo")


def load_rules(path=RULES) -> dict[str, dict]:
    """``{family: {"remap": {}, "drop": [], "expected_orphans": []}}`` with defaults filled in."""
    raw = yaml.safe_load(path.read_text())["families"]
    return {
        fam: {"remap": dict(r.get("remap") or {}), "drop": list(r.get("drop") or []),
              "expected_orphans": list(r.get("expected_orphans") or [])}
        for fam, r in raw.items()
    }


def entity_ids() -> set[str]:
    """Entity ids of the current corpus (``entities.json`` export; never a hardcoded count)."""
    return {e["id"] for e in json.loads((DATA_PROCESSED / "entities.json").read_text())}


def apply_remap(df: pd.DataFrame, family: str, *, ids: set[str] | None = None,
                strict: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Map ``df.code`` to entity ids for ``family``; split off rows with no entity.

    Returns ``(mapped, orphans)``: ``mapped`` is ``df`` with an ``entity_id`` column (upstream
    ``code`` kept) restricted to known entities; ``orphans`` has one row per removed code
    (``code, reason ('drop'|'unknown'), n_rows, first_year, last_year``).  With ``strict``
    an orphan outside the family's ``expected_orphans`` allowlist raises ``ValueError``.
    """
    rules = load_rules()[family]
    ids = entity_ids() if ids is None else ids
    out = df.copy()
    out["entity_id"] = out["code"].map(lambda c: rules["remap"].get(c, c))
    dropped = out["code"].isin(rules["drop"])
    known = out["entity_id"].isin(ids)
    orphan_rows = out[dropped | ~known]
    orphans = (
        orphan_rows.groupby("code", sort=True)
        .agg(n_rows=("year", "size"), first_year=("year", "min"), last_year=("year", "max"))
        .reset_index()
    )
    orphans.insert(1, "reason", orphans["code"].map(lambda c: "drop" if c in rules["drop"] else "unknown"))
    unexpected = sorted(set(orphans["code"]) - set(rules["expected_orphans"]))
    if strict and unexpected:
        raise ValueError(f"{family}: unexpected orphan codes {unexpected}; extend pipeline/econ_iso3.yaml")
    mapped = out[~dropped & known].reset_index(drop=True)
    return mapped, orphans
