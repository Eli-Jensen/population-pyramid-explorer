"""Demographic-dividend stage per (country, year) — the World Bank GMR 2015/16 typology (Ahmed, Cruz, Quillin &
Schellekens 2016, PRWP 7893, Table 1) ADAPTED to every year; thresholds and the citation live in
``pipeline/typology.yaml`` (the yaml is the single source of the numbers, this module only applies them).

Rule for year y (report: y = 2015, look-ahead 2030, generation-ago 1985):
    Δ = working-age share(y + horizon) − working-age share(y)   (medium variant)
    Δ <= 0 and TFR(y − generation) <  replacement → post (4)
    Δ <= 0 and TFR(y − generation) >= replacement → late (3)
    Δ >  0 and TFR(y)              <  high        → early (2)
    Δ >  0 and TFR(y)              >= high        → pre (1)
    otherwise (a needed input unobserved)          → n/a (0)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pyramid_explorer.paths import PIPELINE

TYPOLOGY_YAML = PIPELINE / "typology.yaml"
CODES = {"n/a": 0, "pre": 1, "early": 2, "late": 3, "post": 4}
NAMES = {v: k for k, v in CODES.items()}


def load_thresholds(path: Path = TYPOLOGY_YAML) -> dict:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    t = dict(doc["thresholds"])
    t["_doc"] = doc
    return t


def working_age_share(con, *, lo: int = 15, hi: int = 64) -> pd.Series:
    """``(iso3, year) -> share`` of ages lo..hi in the total population (patched ``pop_age5``, countries only,
    every year 1950–2100 so the look-ahead reaches the medium-variant projection)."""
    sql = f"""
        SELECT p.entity_id AS iso3, p.year::INTEGER AS year,
               sum(CASE WHEN p.age_start BETWEEN {int(lo)} AND {int(hi)} THEN p.pop_male + p.pop_female END)
               / sum(p.pop_male + p.pop_female) AS share
        FROM pop_age5 p JOIN entity e ON e.id = p.entity_id
        WHERE e.type = 'country' GROUP BY 1, 2"""
    df = con.execute(sql).df()
    return df.set_index(["iso3", "year"])["share"].sort_index()


def assign(wa: pd.Series, tfr: pd.Series, years: range, thresholds: dict) -> pd.DataFrame:
    """Stage codes for every (country in ``wa``'s index, year in ``years``) → long frame
    ``iso3, year, stage, wa_share, wa_share_ahead, tfr, tfr_generation``."""
    h, gen = int(thresholds["horizon_years"]), int(thresholds["generation_years"])
    repl, high = float(thresholds["tfr_replacement"]), float(thresholds["tfr_high"])
    ids = sorted(wa.index.get_level_values(0).unique())
    W = wa.unstack("year").reindex(index=ids)
    T = tfr.unstack("year").reindex(index=ids)
    rows = []
    for y in years:
        w0 = W[y] if y in W.columns else pd.Series(np.nan, index=ids)
        w1 = W[y + h] if (y + h) in W.columns else pd.Series(np.nan, index=ids)
        t0 = T[y] if y in T.columns else pd.Series(np.nan, index=ids)
        tg = T[y - gen] if (y - gen) in T.columns else pd.Series(np.nan, index=ids)
        d = (w1 - w0).to_numpy()
        growing = d > 0
        stage = np.zeros(len(ids), dtype=np.uint8)
        t0v, tgv = t0.to_numpy(dtype=float), tg.to_numpy(dtype=float)
        ok_grow = growing & np.isfinite(t0v)
        stage[ok_grow & (t0v < high)] = CODES["early"]
        stage[ok_grow & (t0v >= high)] = CODES["pre"]
        ok_shrink = np.isfinite(d) & ~growing & np.isfinite(tgv)
        stage[ok_shrink & (tgv < repl)] = CODES["post"]
        stage[ok_shrink & (tgv >= repl)] = CODES["late"]
        rows.append(pd.DataFrame({"iso3": ids, "year": y, "stage": stage, "wa_share": w0.to_numpy(dtype=float),
                                  "wa_share_ahead": w1.to_numpy(dtype=float), "tfr": t0v, "tfr_generation": tgv}))
    return pd.concat(rows, ignore_index=True).sort_values(["iso3", "year"]).reset_index(drop=True)


def build_stages(con=None, *, years: range = range(1950, 2025), thresholds: dict | None = None,
                 tfr: pd.Series | None = None) -> pd.DataFrame:
    """Stages for every country and year from the read-only store (``tfr`` may be supplied to save a query)."""
    from pyramid_explorer import db
    from pyramid_explorer.econ.splice import tfr_series

    thresholds = thresholds or load_thresholds()
    own = con is None
    con = con or db.connect(read_only=True)
    try:
        wa = working_age_share(con, lo=int(thresholds["working_age_lo"]), hi=int(thresholds["working_age_hi"]))
        tfr = tfr if tfr is not None else tfr_series(con)
    finally:
        if own:
            con.close()
    return assign(wa, tfr, years, thresholds)


def distribution(stages: pd.DataFrame, year: int) -> dict[str, int]:
    s = stages[stages["year"] == year]["stage"]
    return {NAMES[int(k)]: int(v) for k, v in s.value_counts().sort_index().items()}


def reproduction_report(stages: pd.DataFrame, doc: dict | None = None, *, year: int = 2015) -> dict:
    """Compare the ``year`` assignments with ``reproduction_2015.table_a1`` of the yaml."""
    doc = doc or load_thresholds()["_doc"]
    table = doc["reproduction_2015"]["table_a1"]
    named = doc["reproduction_2015"]["named"]
    ours = stages[stages["year"] == year].set_index("iso3")
    rows, agree = {}, 0
    for iso3, ref in table.items():
        got = NAMES[int(ours.at[iso3, "stage"])] if iso3 in ours.index else None
        ok = got == ref["stage"]
        agree += ok
        rows[iso3] = {"report": ref["stage"], "ours": got, "agree": ok,
                      "wa_change_pct_ours": (None if iso3 not in ours.index or not np.isfinite(ours.at[iso3, "wa_share"]) else
                                             round(100 * (ours.at[iso3, "wa_share_ahead"] / ours.at[iso3, "wa_share"] - 1), 2)),
                      "wa_change_pct_report": ref["wa_change"], "tfr_ours": None if iso3 not in ours.index else round(float(ours.at[iso3, "tfr"]), 2),
                      "tfr_report": ref["tfr_2015"]}
    return {"year": year, "n": len(table), "agree": agree, "rate": agree / len(table),
            "named_all_agree": all(rows[i]["agree"] for i in named), "named_disagree": [i for i in named if not rows[i]["agree"]],
            "disagreements": {k: v for k, v in rows.items() if not v["agree"]}, "rows": rows}
