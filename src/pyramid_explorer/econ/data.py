"""GDP-per-capita panel and growth windows for the economic-lens backtest (PREREG.md §2.1, §2.3).

Growth series ``y``: PWT 11.0 ``rgdpna / pop`` (constant 2021 national prices), with Maddison 2023
``gdppc`` (2011 international $) as the fallback **per window** — a window uses one source at both
endpoints, never a mix (:func:`growth_windows`). Level series: PWT ``rgdpe / pop`` else Maddison
``gdppc``. Everything is read from the DuckDB store (``indicator_value``) through
:func:`pyramid_explorer.db.connect`; WEO is never read here (it is not redistributable and never
enters a window). Countries only (``entity.type = 'country'``, ids = ISO3).

Column names: the in-memory frames use the shared-interface names (``src_growth``, ``t``, ``src``);
the committed parquet tables use the PREREG §2.3 names (``y_growth_source``, ``T``, ``source``) —
:func:`write_tables` renames on the way out and :func:`read_tables` renames on the way back in.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer.paths import ECON_EVALS

PWT_SOURCE, MADDISON_SOURCE = "pwt-11.0", "maddison-2023"
IND_GROWTH_PWT = ("rgdpna_pwt", "pop_pwt")
IND_LEVEL_PWT = ("rgdpe_pwt", "pop_pwt")
IND_MADDISON = "gdppc_maddison"
LAST_YEAR = {"pwt": 2023, "maddison": 2022}        # PREREG §2.1 [PSD]: last observed year per source
T_MAX = {10: 2013, 20: 2003}                         # windows end <= 2023 (the last PWT year)
T_MIN = 1950
TABLES_DIR = ECON_EVALS / "tables"
PANEL_COLS = ["iso3", "year", "y_growth", "src_growth", "y_level", "src_level", "y_growth_pwt", "y_growth_maddison"]
WINDOW_COLS = ["iso3", "t", "h", "g", "src", "partial"]


# ------------------------------------------------------------------------------------------------ panel
def _wide(con, indicator_ids: tuple[str, ...], source_id: str, countries: pd.Series | None) -> pd.DataFrame:
    """``entity_id, year`` × one column per indicator (countries only), from ``indicator_value``."""
    ids = ", ".join("?" for _ in indicator_ids)
    sql = (f"SELECT entity_id AS iso3, year::BIGINT AS year, indicator_id, value FROM indicator_value "
           f"WHERE indicator_id IN ({ids}) AND source_id = ? AND value IS NOT NULL "
           "AND entity_id IN (SELECT id FROM entity WHERE type = 'country')")
    long = con.execute(sql, [*indicator_ids, source_id]).df()
    if countries is not None:
        long = long[long["iso3"].isin(set(countries))]
    wide = long.pivot_table(index=["iso3", "year"], columns="indicator_id", values="value", aggfunc="first")
    return wide.reset_index()


def load_gdp_panel(con=None) -> pd.DataFrame:
    """Per (iso3, year): ``y_growth`` (PWT ``rgdpna/pop``, Maddison ``gdppc`` where PWT is missing),
    ``src_growth`` ∈ {pwt, maddison}, ``y_level`` (PWT ``rgdpe/pop`` else Maddison), ``src_level``,
    plus the two raw growth series ``y_growth_pwt`` / ``y_growth_maddison`` that :func:`growth_windows`
    needs to keep every window single-source (the fallback is decided per window, not per row).

    Opens the store read-only when ``con`` is None. Rows with neither source are dropped."""
    from pyramid_explorer import db  # the only module importing duckdb

    own = con is None
    con = con or db.connect(read_only=True)
    try:
        pwt = _wide(con, tuple(sorted(set(IND_GROWTH_PWT + IND_LEVEL_PWT))), PWT_SOURCE, None)
        mad = _wide(con, (IND_MADDISON,), MADDISON_SOURCE, None)
    finally:
        if own:
            con.close()
    for c in ("rgdpna_pwt", "rgdpe_pwt", "pop_pwt"):
        if c not in pwt:
            pwt[c] = np.nan
    pop = pwt["pop_pwt"].where(pwt["pop_pwt"] > 0)
    pwt = pwt.assign(y_growth_pwt=pwt["rgdpna_pwt"] / pop, y_level_pwt=pwt["rgdpe_pwt"] / pop)[
        ["iso3", "year", "y_growth_pwt", "y_level_pwt"]]
    mad = mad.rename(columns={IND_MADDISON: "y_growth_maddison"})[["iso3", "year", "y_growth_maddison"]]
    mad = mad[mad["y_growth_maddison"] > 0]
    panel = pwt.merge(mad, on=["iso3", "year"], how="outer")
    has_pwt_g = panel["y_growth_pwt"].notna()
    has_pwt_l = panel["y_level_pwt"].notna()
    panel["y_growth"] = panel["y_growth_pwt"].where(has_pwt_g, panel["y_growth_maddison"])
    panel["src_growth"] = np.where(has_pwt_g, "pwt", np.where(panel["y_growth_maddison"].notna(), "maddison", None))
    panel["y_level"] = panel["y_level_pwt"].where(has_pwt_l, panel["y_growth_maddison"])
    panel["src_level"] = np.where(has_pwt_l, "pwt", np.where(panel["y_growth_maddison"].notna(), "maddison", None))
    panel = panel[panel["y_growth"].notna() | panel["y_level"].notna()]
    panel = panel[PANEL_COLS].sort_values(["iso3", "year"]).reset_index(drop=True)
    panel["year"] = panel["year"].astype(int)
    panel.columns.name = None
    return panel


# ------------------------------------------------------------------------------------------------ windows
def _series(panel: pd.DataFrame, col: str) -> pd.Series:
    s = panel.set_index(["iso3", "year"])[col]
    return s[s.notna()]


def _log_growth(s: pd.Series, t: pd.Index, span: int) -> pd.Series:
    """(1/span)·ln(y_{t+span}/y_t) for the (iso3, t) pairs where both endpoints exist in ``s``."""
    start = s.reindex(t)
    end = s.reindex(pd.MultiIndex.from_arrays([t.get_level_values(0), t.get_level_values(1) + span]))
    g = (np.log(end.to_numpy()) - np.log(start.to_numpy())) / span
    return pd.Series(g, index=t)


def growth_windows(panel: pd.DataFrame, h: int, *, t_min: int = T_MIN, t_max: int | None = None) -> pd.DataFrame:
    """Single-source growth windows ``iso3, t, h, g, src, partial`` with ``g = (1/h)·ln(y_{t+h}/y_t)``.

    Source rule (PREREG §2.1): PWT when PWT has **both** endpoints; else Maddison when Maddison has
    both; else the window is missing. ``t`` runs over ``[t_min, t_max]`` (default ``T_MAX[h]``, i.e.
    windows end at or before 2023). Full-span windows carry ``partial=False``; see
    :func:`partial_windows` for the T = 2015 tail."""
    t_max = T_MAX.get(h, LAST_YEAR["pwt"] - h) if t_max is None else t_max
    frames = []
    for src, col in (("pwt", "y_growth_pwt"), ("maddison", "y_growth_maddison")):
        s = _series(panel, col)
        idx = s.index[(s.index.get_level_values(1) >= t_min) & (s.index.get_level_values(1) <= t_max)]
        g = _log_growth(s, idx, h).dropna()
        frames.append(pd.DataFrame({"iso3": g.index.get_level_values(0), "t": g.index.get_level_values(1).astype(int),
                                    "h": h, "g": g.to_numpy(), "src": src}))
    out = pd.concat(frames, ignore_index=True)
    # PWT preferred: keep the first source per (iso3, t) in the order pwt, maddison
    out = out.drop_duplicates(["iso3", "t"], keep="first")
    out["partial"] = False
    return out[WINDOW_COLS].sort_values(["iso3", "t"]).reset_index(drop=True)


def partial_windows(panel: pd.DataFrame, T: int = 2015, *, last_year: dict[str, int] | None = None) -> pd.DataFrame:
    """The PREREG §2.1 tail for T = 2015: PWT runs to 2023 (span 8), Maddison to 2022 (span 7); both are
    flagged ``partial=True`` and the actual span is used as ``h`` in the ``1/h`` normalisation. PWT
    preferred, Maddison only for countries without both PWT endpoints."""
    last_year = last_year or LAST_YEAR
    frames = []
    for src, col in (("pwt", "y_growth_pwt"), ("maddison", "y_growth_maddison")):
        span = last_year[src] - T
        s = _series(panel, col)
        idx = s.index[s.index.get_level_values(1) == T]
        g = _log_growth(s, idx, span).dropna()
        frames.append(pd.DataFrame({"iso3": g.index.get_level_values(0), "t": T, "h": span, "g": g.to_numpy(), "src": src}))
    out = pd.concat(frames, ignore_index=True).drop_duplicates(["iso3", "t"], keep="first")
    out["partial"] = True
    return out[WINDOW_COLS].sort_values(["iso3", "t"]).reset_index(drop=True)


def all_windows(panel: pd.DataFrame) -> pd.DataFrame:
    """h = 10 and h = 20 full windows plus the partial T = 2015 windows — the ``windows`` table."""
    return pd.concat([growth_windows(panel, 10), growth_windows(panel, 20), partial_windows(panel)],
                     ignore_index=True)


# ------------------------------------------------------------------------------------------------ population
def pop_at(keys: pd.DataFrame, iso3: str, year: int) -> float:
    """WPP 2024 total population (thousands) of ``iso3`` in ``year`` from ``corpus_keys``; NaN if absent.
    ``Query.minpop=1000`` is the PREREG ≥ 1 M floor in these units."""
    m = (keys["id"].to_numpy() == iso3) & (keys["year"].to_numpy() == year)
    hit = keys.loc[m, "pop_total"]
    return float(hit.iloc[0]) if len(hit) else float("nan")


def pop_table(keys: pd.DataFrame) -> pd.Series:
    """``(iso3, year) -> pop_total`` (thousands) for vectorised floors; countries only."""
    k = keys[keys["type"] == "country"]
    return pd.Series(k["pop_total"].to_numpy(), index=pd.MultiIndex.from_arrays([k["id"], k["year"].astype(int)]))


# ------------------------------------------------------------------------------------------------ tables
def write_tables(out_dir: Path = TABLES_DIR, *, con=None) -> dict[str, Path]:
    """Write the PREREG §2.3 derived tables: ``gdp_pc.parquet`` (iso3, year, y_growth_source,
    y_level_source, y_growth, y_level) and ``windows.parquet`` (iso3, T, h, g, source, partial).
    ``NOTICE`` is untouched. Returns ``{name: path}``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel = load_gdp_panel(con)
    gdp = panel.rename(columns={"src_growth": "y_growth_source", "src_level": "y_level_source"})[
        ["iso3", "year", "y_growth_source", "y_level_source", "y_growth", "y_level"]]
    gdp_path = out_dir / "gdp_pc.parquet"
    gdp.to_parquet(gdp_path, index=False)
    win = all_windows(panel).rename(columns={"t": "T", "src": "source"})[["iso3", "T", "h", "g", "source", "partial"]]
    win_path = out_dir / "windows.parquet"
    win.to_parquet(win_path, index=False)
    return {"gdp_pc": gdp_path, "windows": win_path}


def read_tables(out_dir: Path = TABLES_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The committed tables back in interface names: ``(gdp_pc, windows)`` with ``src_growth``,
    ``src_level`` / ``t``, ``src``."""
    out_dir = Path(out_dir)
    gdp = pd.read_parquet(out_dir / "gdp_pc.parquet").rename(columns={"y_growth_source": "src_growth", "y_level_source": "src_level"})
    win = pd.read_parquet(out_dir / "windows.parquet").rename(columns={"T": "t", "source": "src"})
    return gdp, win


__all__ = ["load_gdp_panel", "growth_windows", "partial_windows", "all_windows", "pop_at", "pop_table",
           "write_tables", "read_tables", "PANEL_COLS", "WINDOW_COLS", "LAST_YEAR", "T_MAX", "TABLES_DIR"]
