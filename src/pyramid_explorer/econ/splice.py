"""Spliced per-country annual economic series 1950–2024 for the economic-context tier (plan §7, M5.1).

Every number comes from ``indicator_value`` rows of REDISTRIBUTABLE sources only (Maddison 2023, PWT 11.0,
WDI, OGHIST, WPP 2024); the store is opened read-only and the module asserts that no WEO row is ever read.

Series (index ``(iso3, year)``, ``year`` ∈ [1950, 2024]):

* ``gdppc``        GDP per capita, Maddison 2011 int. $ level through 2022 (the last Maddison year), extended
                   past 2022 year by year with the growth of WDI ``NY.GDP.PCAP.PP.KD`` (``gdppc_ppp_wdi``),
                   else PWT ``rgdpna / pop`` growth. Countries absent from Maddison but present in WDI carry the
                   WDI level rescaled to Maddison 2011 $ by the cross-country MEDIAN of Maddison/WDI in
                   :data:`RESCALE_YEAR`; ``gdppc_flag`` names the rule per row (``maddison`` / ``wdi_growth`` /
                   ``pwt_growth`` / ``wdi_rescaled``).
* ``g_rgdp``       annual real GDP growth, 100·ln(rgdpna_t / rgdpna_{t-1}) from PWT (≤ 2023); WDI ``NY.GDP.MKTP.KD.ZG``
                   (converted to the same log form) for 2024 and for years PWT lacks; ``g_flag`` ∈ {pwt, wdi}.
* ``g10``          trailing 10-year real GDP PER CAPITA growth ending in t, %/yr = 100·ln(pc_t / pc_{t-10}) / 10, with
                   pc = PWT ``rgdpna / pop`` (≤ 2023) extended to 2024 by WDI ``NY.GDP.PCAP.PP.KD`` growth; ``g10_flag`` ∈
                   {pwt, wdi_ext} (the latter when the window's end year is the WDI extension). This is the series the
                   web's ``growth10`` accessor reads (plan §7 "10-y real growth").
* ``income_class`` World Bank OGHIST group by fiscal year, 1 = L, 2 = LM, 3 = UM, 4 = H; 0 = n/a (before FY1989
                   or not classified).
* ``tfr``          WPP 2024 total fertility rate (medium variant for 2024).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

YEAR_MIN, YEAR_MAX = 1950, 2024
MADDISON_LAST = 2022          # last Maddison 2023 year
RESCALE_YEAR = 2017           # ICP 2017 benchmark year: Maddison 2011 $ / WDI 2021 $ ratio taken here
INCOME_FIRST_FY = 1989
SOURCES = {"maddison": "maddison-2023", "pwt": "pwt-11.0", "wdi": "wdi", "oghist": "oghist", "wpp": "wpp2024"}
SPLICE_COLS = ["iso3", "year", "gdppc", "gdppc_flag", "g_rgdp", "g_flag", "g10", "g10_flag", "income_class", "tfr"]
G10_SPAN = 10


class LicenceError(RuntimeError):
    """A non-redistributable source reached the splice."""


# ------------------------------------------------------------------------------------------------ store
def _assert_redistributable(con, source_ids: list[str]) -> None:
    rows = con.execute("SELECT id, redistributable FROM source WHERE id IN (SELECT unnest(?::TEXT[]))", [source_ids]).fetchall()
    bad = [r[0] for r in rows if not r[1]]
    if bad or any("weo" in s.lower() for s in source_ids):
        raise LicenceError(f"non-redistributable source in the splice: {bad or source_ids}")


def _long(con, indicator_id: str, source_id: str, *, forecast_ok: bool = True) -> pd.Series:
    """``(iso3, year) -> value`` for one indicator of one source, countries only, via ``indicator_public``."""
    sql = ("SELECT iv.entity_id AS iso3, iv.year::INTEGER AS year, iv.value FROM indicator_public iv "
           "JOIN entity e ON e.id = iv.entity_id WHERE e.type = 'country' AND iv.indicator_id = ? AND iv.source_id = ? "
           "AND iv.value IS NOT NULL" + ("" if forecast_ok else " AND NOT iv.is_forecast"))
    df = con.execute(sql, [indicator_id, source_id]).df()
    if df.empty:
        return pd.Series(dtype=float, index=pd.MultiIndex.from_arrays([[], []], names=["iso3", "year"]))
    return df.set_index(["iso3", "year"])["value"].sort_index()


def _long_family(con, indicator_id: str, family: str, *, base_source: str) -> pd.Series:
    """Like :func:`_long` over every redistributable source of ``family``; where a patch source (e.g. the Togo interim
    update) and the base source both carry a row, the patch wins."""
    sql = ("SELECT iv.entity_id AS iso3, iv.year::INTEGER AS year, iv.value, iv.source_id FROM indicator_public iv "
           "JOIN entity e ON e.id = iv.entity_id JOIN source s ON s.id = iv.source_id "
           "WHERE e.type = 'country' AND iv.indicator_id = ? AND s.family = ? AND iv.value IS NOT NULL")
    df = con.execute(sql, [indicator_id, family]).df()
    if df.empty:
        return pd.Series(dtype=float, index=pd.MultiIndex.from_arrays([[], []], names=["iso3", "year"]))
    df["_patch"] = (df["source_id"] != base_source).astype(int)
    df = df.sort_values(["iso3", "year", "_patch"]).drop_duplicates(["iso3", "year"], keep="last")
    return df.set_index(["iso3", "year"])["value"].sort_index()


def tfr_series(con) -> pd.Series:
    """WPP total fertility rate, countries only, patched sources winning."""
    return _long_family(con, "tfr_wpp", "wpp", base_source=SOURCES["wpp"])


def countries(con) -> list[str]:
    """Country ids in corpus order (``corpus_entity``: countries first, sorted by id)."""
    return [r[0] for r in con.execute("SELECT entity_id FROM corpus_entity WHERE type = 'country' ORDER BY entity_idx").fetchall()]


def load_inputs(con=None) -> dict[str, pd.Series]:
    """Raw input series from the store (read-only): maddison, wdi_pc, pwt_rgdpna, pwt_pop, wdi_g, income, tfr."""
    from pyramid_explorer import db  # the only module importing duckdb

    own = con is None
    con = con or db.connect(read_only=True)
    try:
        _assert_redistributable(con, list(SOURCES.values()))
        out = {
            "maddison": _long(con, "gdppc_maddison", SOURCES["maddison"]),
            "wdi_pc": _long(con, "gdppc_ppp_wdi", SOURCES["wdi"]),
            "pwt_rgdpna": _long(con, "rgdpna_pwt", SOURCES["pwt"]),
            "pwt_pop": _long(con, "pop_pwt", SOURCES["pwt"]),
            "wdi_g": _long(con, "gdp_growth_wdi", SOURCES["wdi"]),
            "income": _long(con, "income_class_wb", SOURCES["oghist"]),
            "tfr": tfr_series(con),
            "_countries": countries(con),
        }
    finally:
        if own:
            con.close()
    return out


# ------------------------------------------------------------------------------------------------ splice
def _wide(s: pd.Series, ids: list[str], years: range) -> pd.DataFrame:
    """``iso3 × year`` frame (NaN where missing), restricted to ``ids`` and ``years``."""
    if s.empty:
        return pd.DataFrame(np.nan, index=ids, columns=list(years))
    w = s.unstack("year").reindex(index=ids, columns=list(years))
    return w.astype(float)


def rescale_ratio(mad: pd.DataFrame, wdi: pd.DataFrame, year: int = RESCALE_YEAR) -> tuple[float, int]:
    """Median over countries of Maddison / WDI GDP per capita in ``year`` (both present, both > 0) and its n."""
    a, b = mad.get(year), wdi.get(year)
    if a is None or b is None:
        return float("nan"), 0
    m = (a > 0) & (b > 0)
    r = (a[m] / b[m])
    return (float(r.median()) if len(r) else float("nan")), int(len(r))


def splice_gdppc(mad: pd.DataFrame, wdi: pd.DataFrame, pwt_pc: pd.DataFrame, *, ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Level + flag frames (iso3 × year). Maddison level ≤ MADDISON_LAST; growth extension after it; WDI-only
    countries rescaled by ``ratio``. A country with neither Maddison nor WDI stays NaN (PWT alone is not a level here)."""
    years = list(mad.columns)
    level = pd.DataFrame(np.nan, index=mad.index, columns=years)
    flag = pd.DataFrame(None, index=mad.index, columns=years, dtype=object)
    has_mad = mad.notna().any(axis=1)
    for iso3 in mad.index:
        if has_mad[iso3]:
            base = mad.loc[iso3]
            level.loc[iso3, base.notna()] = base[base.notna()]
            flag.loc[iso3, base.notna()] = "maddison"
            # gaps INSIDE the Maddison span stay missing; only the post-2022 tail is extended
            last = int(base.last_valid_index()) if base.notna().any() else None
            if last is None:
                continue
            for y in years:
                if y <= last:
                    continue
                prev = level.at[iso3, y - 1] if (y - 1) in level.columns else np.nan
                if not np.isfinite(prev):
                    break
                w0, w1 = wdi.at[iso3, y - 1] if (y - 1) in wdi.columns else np.nan, wdi.at[iso3, y] if y in wdi.columns else np.nan
                if np.isfinite(w0) and np.isfinite(w1) and w0 > 0 and w1 > 0:
                    level.at[iso3, y], flag.at[iso3, y] = prev * (w1 / w0), "wdi_growth"
                    continue
                p0, p1 = pwt_pc.at[iso3, y - 1] if (y - 1) in pwt_pc.columns else np.nan, pwt_pc.at[iso3, y] if y in pwt_pc.columns else np.nan
                if np.isfinite(p0) and np.isfinite(p1) and p0 > 0 and p1 > 0:
                    level.at[iso3, y], flag.at[iso3, y] = prev * (p1 / p0), "pwt_growth"
                    continue
                break
        elif np.isfinite(ratio):
            w = wdi.loc[iso3]
            m = w.notna() & (w > 0)
            if m.any():
                level.loc[iso3, m] = w[m] * ratio
                flag.loc[iso3, m] = "wdi_rescaled"
    return level, flag


def growth_series(pwt_rgdpna: pd.DataFrame, wdi_g: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """100·ln growth: PWT year-on-year where both endpoints exist, WDI KD.ZG (converted to log) elsewhere."""
    years = list(pwt_rgdpna.columns)
    g = pd.DataFrame(np.nan, index=pwt_rgdpna.index, columns=years)
    flag = pd.DataFrame(None, index=pwt_rgdpna.index, columns=years, dtype=object)
    prev = pwt_rgdpna.shift(1, axis=1)
    ok = pwt_rgdpna.notna() & prev.notna() & (pwt_rgdpna > 0) & (prev > 0)
    g[ok] = 100.0 * np.log(pwt_rgdpna[ok] / prev[ok])
    flag[ok] = "pwt"
    w = wdi_g.reindex(index=g.index, columns=years)
    fill = ~ok & w.notna() & (w > -100)
    g[fill] = 100.0 * np.log1p(w[fill] / 100.0)
    flag[fill] = "wdi"
    return g, flag


def growth10_series(pwt_pc: pd.DataFrame, wdi: pd.DataFrame, *, span: int = G10_SPAN) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trailing ``span``-year per-capita growth (%/yr, log form). PWT per-capita levels are extended past their last
    year with WDI per-capita PPP growth so the 2024 window exists; a window is ``pwt`` when both endpoints are PWT."""
    years = list(pwt_pc.columns)
    pc = pwt_pc.copy()
    ext = pd.DataFrame(False, index=pc.index, columns=years)
    for iso3 in pc.index:
        row = pc.loc[iso3]
        last = row.last_valid_index()
        if last is None:
            continue
        for y in years:
            if y <= last:
                continue
            prev = pc.at[iso3, y - 1]
            w0 = wdi.at[iso3, y - 1] if (y - 1) in wdi.columns else np.nan
            w1 = wdi.at[iso3, y] if y in wdi.columns else np.nan
            if np.isfinite(prev) and np.isfinite(w0) and np.isfinite(w1) and w0 > 0 and w1 > 0:
                pc.at[iso3, y], ext.at[iso3, y] = prev * (w1 / w0), True
            else:
                break
    lag = pc.shift(span, axis=1)
    ok = pc.notna() & lag.notna() & (pc > 0) & (lag > 0)
    g = pd.DataFrame(np.nan, index=pc.index, columns=years)
    g[ok] = 100.0 * np.log(pc[ok] / lag[ok]) / span
    flag = pd.DataFrame(None, index=pc.index, columns=years, dtype=object)
    flag[ok & ~ext] = "pwt"
    flag[ok & ext] = "wdi_ext"
    return g, flag


def build_splice(inputs: dict[str, pd.Series] | None = None, con=None) -> pd.DataFrame:
    """The spliced long table (:data:`SPLICE_COLS`), one row per (country in corpus order, year 1950–2024)."""
    inputs = inputs or load_inputs(con)
    ids = list(inputs["_countries"])
    years = range(YEAR_MIN, YEAR_MAX + 1)
    mad = _wide(inputs["maddison"], ids, years)
    wdi = _wide(inputs["wdi_pc"], ids, years)
    rg, pop = _wide(inputs["pwt_rgdpna"], ids, years), _wide(inputs["pwt_pop"], ids, years)
    pwt_pc = rg / pop.where(pop > 0)
    ratio, n_ratio = rescale_ratio(mad, wdi)
    level, lflag = splice_gdppc(mad, wdi, pwt_pc, ratio=ratio)
    g, gflag = growth_series(rg, _wide(inputs["wdi_g"], ids, years))
    g10, g10flag = growth10_series(pwt_pc, wdi)
    inc = _wide(inputs["income"], ids, years).fillna(0).astype(int)
    inc.loc[:, [y for y in years if y < INCOME_FIRST_FY]] = 0
    tfr = _wide(inputs["tfr"], ids, years)
    out = pd.DataFrame({
        "iso3": np.repeat(ids, len(years)), "year": np.tile(list(years), len(ids)),
        "gdppc": level.to_numpy().ravel(), "gdppc_flag": lflag.to_numpy().ravel(),
        "g_rgdp": g.to_numpy().ravel(), "g_flag": gflag.to_numpy().ravel(),
        "g10": g10.to_numpy().ravel(), "g10_flag": g10flag.to_numpy().ravel(),
        "income_class": inc.to_numpy().ravel(), "tfr": tfr.to_numpy().ravel(),
    })[SPLICE_COLS]
    out.attrs["rescale"] = {"year": RESCALE_YEAR, "ratio_maddison_over_wdi": ratio, "n_countries": n_ratio}
    return out


def coverage(splice: pd.DataFrame, *, min_years: int = 30) -> dict:
    """Per-country gdppc year counts; which countries fall below ``min_years``; flag counts."""
    n = splice.groupby("iso3")["gdppc"].apply(lambda s: int(s.notna().sum()))
    return {"n_countries": int(len(n)), "gdppc_ge_min": int((n >= min_years).sum()), "min_years": min_years,
            "below_min": sorted(n[n < min_years].index.tolist()), "none": sorted(n[n == 0].index.tolist()),
            "flags": {k: int(v) for k, v in splice["gdppc_flag"].value_counts().items()},
            "g_flags": {k: int(v) for k, v in splice["g_flag"].value_counts().items()},
            "g10_flags": {k: int(v) for k, v in splice["g10_flag"].value_counts().items()},
            "rescale": splice.attrs.get("rescale")}
