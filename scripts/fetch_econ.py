#!/usr/bin/env python
"""Fetch every economic source into data/raw/econ/ and report coverage after ISO3 remap.

    uv run scripts/fetch_econ.py [--force] [--skip weo,wdi,...] [--from DIR]

Idempotent: files already on disk are kept (``--force`` re-downloads); every file's
sha256/bytes/fetched_at lands in pipeline/econ_manifest.json.  ``--from DIR`` names a
pyramid-econ checkout whose PWT xlsx / WEO parquet are copied instead of downloaded
(default ``paths.PYRAMID_ECON_ROOT``).  The coverage table uses ``econ_iso3.apply_remap``
exactly as ``db.ingest_indicators`` will.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from pyramid_explorer.data import imf, maddison, pwt, wdi
from pyramid_explorer.data.econ_iso3 import apply_remap

SANITY_IDS = ["CHN", "PHL", "BGD", "NGA"]
SANITY_YEARS = [1990, 2024]
GDPPC = {"maddison": "gdppc_maddison", "wdi": "gdppc_ppp_wdi", "weo": "gdppc_ppp_weo"}

FAMILIES = {  # family -> (fetch, load_long)
    "maddison": (maddison.fetch, maddison.load_long),
    "pwt": (pwt.fetch, pwt.load_long),
    "wdi": (wdi.fetch, wdi.load_long),
    "oghist": (lambda **kw: None, wdi.load_income_long),   # fetched by wdi.fetch
    "weo": (imf.fetch, imf.load_long),
}
LOCAL = {"pwt": pwt.LOCAL_REL, "weo": imf.LOCAL_REL}       # families with a copy in the pyramid-econ checkout


def coverage(family: str, long: pd.DataFrame) -> dict:
    """Coverage summary of one family after remap (counts derived from the data, never hardcoded)."""
    mapped, orphans = apply_remap(long, family)
    obs = mapped[~mapped["is_forecast"]]
    row = {
        "family": family, "rows": len(mapped), "countries": mapped["entity_id"].nunique(),
        "years": f"{obs['year'].min()}-{obs['year'].max()}",
        "orphans": ",".join(f"{c}({r})" for c, r in zip(orphans["code"], orphans["reason"])) or "-",
        "indicators": ",".join(sorted(mapped["indicator_id"].unique())),
    }
    if family == "pwt":  # per-capita from rgdpna / pop (both PWT), sanity only
        wide = mapped.pivot_table(index=["entity_id", "year"], columns="indicator_id", values="value")
        pc = (wide["rgdpna_pwt"] / wide["pop_pwt"]).rename("gdppc")
        for e in SANITY_IDS:
            for y in SANITY_YEARS + [wide.index.get_level_values("year").max()]:
                row[f"{e}@{y}"] = round(float(pc.get((e, y), float("nan"))), 1)
    elif family in GDPPC:
        s = mapped[mapped["indicator_id"] == GDPPC[family]].set_index(["entity_id", "year"])["value"]
        for e in SANITY_IDS:
            for y in SANITY_YEARS:
                row[f"{e}@{y}"] = round(float(s.get((e, y), float("nan"))), 1)
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download even when the raw file exists")
    ap.add_argument("--skip", default="", help="comma-separated families to skip (maddison,pwt,wdi,oghist,weo)")
    ap.add_argument("--from", dest="src", type=Path, default=None,
                    help="pyramid-econ checkout to copy PWT/WEO files from (default: paths.PYRAMID_ECON_ROOT)")
    args = ap.parse_args(argv)
    skip = {s for s in args.skip.split(",") if s}
    rows = []
    for family, (fetch, load_long) in FAMILIES.items():
        if family in skip:
            continue
        kw = {"local_copy": args.src / LOCAL[family]} if args.src and family in LOCAL else {}
        fetch(force=args.force, **kw)
        rows.append(coverage(family, load_long()))
        print(f"[fetch_econ] {family}: {rows[-1]['rows']} rows, {rows[-1]['countries']} countries, "
              f"{rows[-1]['years']}, orphans {rows[-1]['orphans']}", file=sys.stderr)
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(pd.DataFrame(rows).fillna("").to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
