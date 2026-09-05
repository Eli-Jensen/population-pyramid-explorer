"""Experiment 1 — lookalike-as-of-T (evals/econ/PREREG.md §3).

For every T on the grid the module builds the candidate set ``C(T)`` (countries, WPP population at T ≥ 1 M,
growth window available from one source), selects k lookalikes under each pre-registered rule —
Query A (China-1990 anchor via ``search.similar``), Query B (PRIMARY: min blend distance to the hindsight-free
prototype set ``P(T)``; soft-min robustness row), Query C (10-year motion nearest China 1980→1990), and the N4
momentum comparator — then pools the outcomes over T and computes the §3.6 statistics, the §3.7 null models and the
§3.8 predictions.  Outcomes are real GDP-per-capita growth (``g``, log points/yr) and, for T ∈ {2000…2015}, USD
ETF total returns (``r``) with excess against VT / VT-proxy as the headline.

Everything is a pure function of the inputs handed in (:class:`Corpus`, :class:`GrowthData`, an optional
returns provider) so the unit tests run on a synthetic corpus with fakes; ``scripts/backtest_lookalikes.py``
wires the real corpus, ``econ.data`` and ``econ.etf``.  Statistics helpers (HAC SEs, block bootstrap, N_eff)
come from ``econ.stats`` and are injected via ``stats=`` (resolved lazily when None).

Language rule (PREREG §7): the outputs describe what happened; nothing here is a forecast.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.stats import norm

from pyramid_explorer.features import features
from pyramid_explorer.metrics import distances
from pyramid_explorer.search import Query, similar

SEED = 20260904                 # PREREG §3.6 item 7 / §3.7 [PSD]
B_DEFAULT = 5000
T_GRID = (1990, 1995, 2000, 2005, 2010, 2015)
GROWTH_T = {10: (1990, 1995, 2000, 2005, 2010, 2015), 20: (1990, 1995, 2000)}   # 2015 is the partial h=8/7 row
RETURNS_T = (2000, 2005, 2010, 2015)
RETURNS_H = 10
KS = (10, 5)
K_PRIMARY = 10
MINPOP = 1000.0                 # thousands (PREREG §2.1 [PSD])
CALIPER = 0.35                  # log points (N2)
PROTO_MAX_PER_COUNTRY = 3
PROTO_MIN_GAP = 5
PROTO_DECILE = 0.90
SOFTMIN_TAU_FRAC = 0.25
ANCHOR_ID, ANCHOR_YEAR = "CHN", 1990
MOTION_L = 10
PARTIAL_T = 2015
PARTIAL_H = {"pwt": 8, "maddison": 7}
QUERIES = ("A", "B", "B_soft", "B3", "C", "N4")
QUERY_NAMES = {
    "A": "Query A — China 1990 anchor (search.similar, blend)",
    "B": "Query B — PRIMARY: min blend distance to the prototype set P(T)",
    "B_soft": "Query B robustness — soft-min distance to P(T) (τ = 0.25 · median D_P)",
    "B3": "N3 comparator — Query B pipeline on the z-scored (u15, wa, o65) vector",
    "C": "Query C — 10-year motion nearest China 1980→1990 (trend metric, informational)",
    "N4": "N4 comparator — prior-10-year growth momentum",
}
PICK_COLUMNS = ["T", "query", "k", "h", "outcome", "iso3", "year", "role", "d", "y_T", "g", "eg",
                "ticker", "status", "r", "r_vt", "er", "benchmark", "partial"]
STATS = None                    # injectable ``econ.stats`` namespace (tests); None → lazy import


def _stats(stats):
    if stats is not None:
        return stats
    if STATS is not None:
        return STATS
    from pyramid_explorer.econ import stats as real_stats
    return real_stats


# ----------------------------------------------------------------------------------------------- inputs
@dataclass
class Corpus:
    """The pyramid corpus plus the lookups Experiment 1 needs (all derived once)."""
    X: np.ndarray
    keys: pd.DataFrame
    entities: list[dict]
    sigma: dict
    countries: set[str] = field(init=False)
    row_wide: pd.DataFrame = field(init=False)
    pop_wide: pd.DataFrame = field(init=False)
    feats: pd.DataFrame = field(init=False)

    def __post_init__(self) -> None:
        self.X = np.asarray(self.X, dtype=np.float64)
        self.countries = {e["id"] for e in self.entities if e.get("type") == "country"}
        k = self.keys
        self.row_wide = k.pivot(index="id", columns="year", values="row")
        self.pop_wide = k.pivot(index="id", columns="year", values="pop_total")
        self.feats = features(self.X)

    def row(self, iso3: str, year: int) -> int:
        return int(self.row_wide.at[iso3, year])

    def rows(self, iso3s, year: int) -> np.ndarray:
        return self.row_wide.loc[list(iso3s), year].to_numpy(dtype=np.int64)

    def pop(self, iso3s, year: int) -> np.ndarray:
        return self.pop_wide.reindex(list(iso3s))[year].to_numpy(dtype=np.float64)

    def country_ids(self, year: int, minpop: float = MINPOP) -> list[str]:
        p = self.pop_wide[year]
        return sorted(i for i in p.index[p >= minpop] if i in self.countries)


@dataclass
class GrowthData:
    """Growth windows (``iso3, t, h, g, src[, partial]``) and the level series (``iso3, year, y_level``)."""
    windows: pd.DataFrame
    levels: pd.DataFrame

    def __post_init__(self) -> None:
        w = self.windows.copy()
        if "partial" not in w:
            w["partial"] = False
        self.windows = w
        self._lv = self.levels.set_index(["iso3", "year"])["y_level"].sort_index()

    @classmethod
    def from_panel(cls, panel: pd.DataFrame, growth_windows: Callable[[pd.DataFrame, int], pd.DataFrame]) -> "GrowthData":
        """PREREG §2.1/§3.1: full h = 10 / 20 windows plus the partial T = 2015 row (PWT h = 8, else Maddison h = 7)."""
        parts = []
        for h in (10, 20):
            w = growth_windows(panel, h).copy()
            w["partial"] = False
            parts.append(w)
        w8 = growth_windows(panel, PARTIAL_H["pwt"])
        w8 = w8[w8["t"] == PARTIAL_T].copy()
        w7 = growth_windows(panel, PARTIAL_H["maddison"])
        w7 = w7[(w7["t"] == PARTIAL_T) & (w7["src"] == "maddison") & ~w7["iso3"].isin(w8["iso3"])].copy()
        for w in (w8, w7):
            w["partial"] = True
            parts.append(w)
        windows = pd.concat(parts, ignore_index=True)
        levels = panel[["iso3", "year", "y_level"]].dropna().drop_duplicates(["iso3", "year"])
        return cls(windows, levels)

    def g(self, T: int, h: int) -> pd.DataFrame:
        """``iso3, g, src, h, partial`` for windows starting at T with horizon h (T = 2015, h = 10 → the partial rows)."""
        w = self.windows
        if h == 10 and T == PARTIAL_T:
            sel = w[(w["t"] == T) & w["partial"]]
        else:
            sel = w[(w["t"] == T) & (w["h"] == h) & ~w["partial"]]
        return sel.drop_duplicates("iso3")[["iso3", "g", "src", "h", "partial"]].reset_index(drop=True)

    def lny(self, iso3s, T: int) -> np.ndarray:
        idx = pd.MultiIndex.from_product([list(iso3s), [T]])
        v = self._lv.reindex(idx).to_numpy(dtype=np.float64)
        return np.log(np.where(v > 0, v, np.nan))

    def windows10_ending_by(self, T: int) -> pd.DataFrame:
        """All complete 10-year windows whose outcome was observed at T (y + 10 ≤ T)."""
        w = self.windows
        return w[(w["h"] == 10) & ~w["partial"] & (w["t"] + 10 <= T)].copy()


# ----------------------------------------------------------------------------------------------- candidates
def candidates(corpus: Corpus, gd: GrowthData, T: int, h: int, *, exclude: str | None = None) -> pd.DataFrame:
    """``C(T)`` for horizon h: countries, pop_T ≥ 1 M, single-source window; columns
    ``iso3, row, g, y_T, lny, src, partial, h_actual``.  ``exclude`` drops the anchor for Query A/C."""
    g = gd.g(T, h)
    g = g[g["iso3"].isin(corpus.country_ids(T))]
    if exclude:
        g = g[g["iso3"] != exclude]
    g = g.sort_values("iso3").reset_index(drop=True)
    out = pd.DataFrame({"iso3": g["iso3"], "row": corpus.rows(g["iso3"], T), "g": g["g"].to_numpy(dtype=np.float64),
                        "src": g["src"], "partial": g["partial"].to_numpy(bool), "h_actual": g["h"].to_numpy(int)})
    out["lny"] = gd.lny(out["iso3"], T)
    out["y_T"] = np.exp(out["lny"])
    return out


def prototype_set(corpus: Corpus, gd: GrowthData, T: int, *, max_per_country: int = PROTO_MAX_PER_COUNTRY,
                  min_gap: int = PROTO_MIN_GAP, decile: float = PROTO_DECILE) -> pd.DataFrame:
    """``P(T)``: (c, y) with y + 10 ≤ T, pop_y ≥ 1 M and g_{c,y,10} in the top decile of those windows, deduplicated
    to ≤ 3 per country ≥ 5 years apart keeping the highest-growth windows first (PREREG §3.3).  Columns
    ``iso3, year, g, row``."""
    w = gd.windows10_ending_by(T)
    w = w[w["iso3"].isin(corpus.countries)].copy()
    if w.empty:
        return pd.DataFrame(columns=["iso3", "year", "g", "row"])
    pop = np.array([corpus.pop_wide.at[c, int(y)] if c in corpus.pop_wide.index else np.nan
                    for c, y in zip(w["iso3"], w["t"])])
    w = w[pop >= MINPOP]
    cut = np.quantile(w["g"].to_numpy(dtype=np.float64), decile)
    top = w[w["g"] >= cut].sort_values(["g", "iso3", "t"], ascending=[False, True, True])
    kept: dict[str, list[int]] = {}
    rows = []
    for r in top.itertuples(index=False):
        ys = kept.setdefault(r.iso3, [])
        if len(ys) >= max_per_country or any(abs(int(r.t) - y) < min_gap for y in ys):
            continue
        ys.append(int(r.t))
        rows.append({"iso3": r.iso3, "year": int(r.t), "g": float(r.g)})
    out = pd.DataFrame(rows, columns=["iso3", "year", "g"])
    out["row"] = [corpus.row(c, y) for c, y in zip(out["iso3"], out["year"])]
    return out.sort_values(["g"], ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------------------------- distances
def proto_distance_matrix(corpus: Corpus, proto_rows: np.ndarray, cand_rows: np.ndarray) -> np.ndarray:
    """``[n_proto, n_cand]`` blend distances from every prototype row to every candidate row."""
    Xc = corpus.X[np.asarray(cand_rows)]
    return np.stack([distances("blend", corpus.X[int(p)], Xc, sigma=corpus.sigma).astype(np.float64) for p in proto_rows])


def three_band(corpus: Corpus, rows: np.ndarray) -> np.ndarray:
    """``(u15, wa, o65)`` shares of the given corpus rows, ``[n, 3]``."""
    return corpus.feats.iloc[np.asarray(rows)][["u15", "wa", "o65"]].to_numpy(dtype=np.float64)


def three_band_distance_matrix(corpus: Corpus, proto_rows: np.ndarray, cand_rows: np.ndarray) -> np.ndarray:
    """N3: Euclidean distance on the three-band vector z-scored on the T cross-section (the candidates)."""
    C = three_band(corpus, cand_rows)
    P = three_band(corpus, proto_rows)
    mu, sd = C.mean(0), C.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    Cz, Pz = (C - mu) / sd, (P - mu) / sd
    return np.sqrt(((Pz[:, None, :] - Cz[None, :, :]) ** 2).sum(-1))


def min_distances(D: np.ndarray, tau_frac: float = SOFTMIN_TAU_FRAC) -> dict[str, np.ndarray]:
    """From a ``[n_proto, n_cand]`` matrix: ``D_P`` (min), ``D2`` (second smallest, tie-break), ``soft`` (soft-min
    with τ = tau_frac · median D_P over the candidates) and ``argmin`` (nearest prototype index)."""
    if D.shape[0] == 0:
        n = D.shape[1]
        nan = np.full(n, np.nan)
        return {"D": nan, "D2": nan, "soft": nan, "argmin": np.full(n, -1)}
    s = np.sort(D, axis=0)
    d1 = s[0]
    d2 = s[1] if D.shape[0] > 1 else s[0]
    tau = tau_frac * float(np.median(d1))
    if not np.isfinite(tau) or tau <= 0:
        soft = d1.copy()
    else:
        z = -D / tau
        m = z.max(0)
        soft = -tau * (m + np.log(np.exp(z - m).sum(0)))
    return {"D": d1, "D2": d2, "soft": soft, "argmin": D.argmin(0)}


# ----------------------------------------------------------------------------------------------- selection rules
def _rank_pick(cand: pd.DataFrame, primary: np.ndarray, secondary: np.ndarray, k: int) -> pd.DataFrame:
    t = cand.assign(d=primary, _d2=secondary)
    t = t[np.isfinite(t["d"])].sort_values(["d", "_d2", "iso3"]).head(k)
    return t.drop(columns="_d2").reset_index(drop=True)


def query_A(corpus: Corpus, cand: pd.DataFrame, T: int, k: int, *, trend: str | None = None) -> pd.DataFrame:
    """Query A (``trend=None``) / Query C (``trend='motion'``): ``search.similar`` from CHN 1990 over year T, then
    post-filtered to ``C(T)`` and cut to the k nearest (PREREG §3.3)."""
    q = Query(id=ANCHOR_ID, year=ANCHOR_YEAR, mode="range", from_year=T, to_year=T, k=len(corpus.keys), scope="c",
              minpop=MINPOP, metric="blend", trend=trend, L=MOTION_L)
    res = similar(corpus.X, corpus.keys, corpus.entities, q, corpus.sigma)
    d = {r.id: float(r.d) for r in res}
    dd = cand["iso3"].map(d).to_numpy(dtype=np.float64)
    return _rank_pick(cand, dd, dd, k)


def query_B(cand: pd.DataFrame, md: dict[str, np.ndarray], k: int, *, soft: bool = False) -> pd.DataFrame:
    """Query B: the k candidates with the smallest ``D_P`` (ties by the second-smallest prototype distance);
    ``soft=True`` ranks by the soft-min instead."""
    return _rank_pick(cand, md["soft"] if soft else md["D"], md["D2"], k)


def query_N4(cand: pd.DataFrame, gd: GrowthData, T: int, k: int) -> pd.DataFrame:
    """N4: the k candidates with the highest prior-10-year growth ``g_{c,T−10,10}`` (single-source rule)."""
    prev = gd.g(T - 10, 10).set_index("iso3")["g"]
    mom = cand["iso3"].map(prev).to_numpy(dtype=np.float64)
    return _rank_pick(cand, -mom, -mom, k)


# ----------------------------------------------------------------------------------------------- outcomes
def growth_outcomes(picks: pd.DataFrame, cand: pd.DataFrame) -> pd.DataFrame:
    """Attach ``eg = g − median_C(T) g`` (log points/yr) and the top-quartile flag over ``C(T)``."""
    med = float(np.median(cand["g"]))
    q3 = float(np.quantile(cand["g"], 0.75))
    out = picks.copy()
    out["eg"] = out["g"] - med
    out["top_q"] = out["g"] >= q3
    out["median_g"] = med
    return out


class ReturnsProvider:
    """What Experiment 1 needs from ``econ.etf`` for one T (entry = last trading day of T, exit = of T + 10):

    ``etf_table(T)`` → one row per country with a single-country fund whose inception ≤ entry — the fund with the
    earliest inception — ``iso3, ticker, inception, status, r, max_dd`` (``r`` = annualised log return, USD;
    status ∈ {investable, liquidated_in_window}); plus, for every other country in the universe,
    ``status = no_fund_at_entry`` with ``r = NaN``.  ``vt(T)`` → ``{'r_ann', 'benchmark', 'legs'}``;
    ``ew(T)`` → ``{'r_ann', 'n'}``; ``refs(T)`` → ``{'SPY': r, 'EFA': r, 'EEM': r}`` (NaN when absent).
    """

    def etf_table(self, T: int) -> pd.DataFrame:  # pragma: no cover — interface
        raise NotImplementedError

    def vt(self, T: int) -> dict:  # pragma: no cover
        raise NotImplementedError

    def ew(self, T: int) -> dict:  # pragma: no cover
        raise NotImplementedError

    def refs(self, T: int) -> dict:  # pragma: no cover
        raise NotImplementedError


class EtfReturns(ReturnsProvider):
    """The real provider over ``econ.etf`` (prices cached by ``scripts/fetch_etf.py``)."""

    DEFAULT_FETCH_KW = {"dead_series": "ok"}   # the policy scripts/fetch_etf.py ran with: a multi-bar Yahoo series for a
    #                                             delisted ticker is recorded as a deviation and DISCARDED (NAV ladder used)

    def __init__(self, etf_mod=None, h: int = RETURNS_H, fetch_kw: dict | None = None):
        if etf_mod is None:
            from pyramid_explorer.econ import etf as etf_mod
        self.etf = etf_mod
        self.h = h
        self.universe = etf_mod.load_universe()
        self.fetch_kw = dict(self.DEFAULT_FETCH_KW if fetch_kw is None else fetch_kw)
        self._cache: dict[int, pd.DataFrame] = {}

    def window(self, T: int) -> tuple[pd.Timestamp, pd.Timestamp]:
        return self.etf.last_trading_day(T, **self.fetch_kw), self.etf.last_trading_day(T + self.h, **self.fetch_kw)

    def etf_table(self, T: int) -> pd.DataFrame:
        if T in self._cache:
            return self._cache[T]
        entry, exit_ = self.window(T)
        u = self.universe
        u = u[(u["role"].astype(str).str.replace("single_country", "country") == "country") & u["iso3"].notna()].copy()
        u["inception"] = pd.to_datetime(u["inception"])
        rows = []
        guard_error = getattr(self.etf, "EtfGuardError", Exception)
        for iso3, grp in u.sort_values("inception").groupby("iso3"):
            ok = grp[(grp["inception"] <= entry) & (grp["delisted"].isna() | (pd.to_datetime(grp["delisted"]) > entry))] if "delisted" in grp else grp[grp["inception"] <= entry]
            if ok.empty:
                rows.append({"iso3": iso3, "ticker": None, "inception": grp["inception"].min().date().isoformat(),
                             "status": "no_fund_at_entry", "r": np.nan, "max_dd": np.nan, "issuer": None, "delisted": None})
                continue
            e = ok.iloc[0]                       # earliest inception still trading at entry (PREREG §3.4 [PSD])
            try:
                wr = self.etf.window_return(str(e["ticker"]), entry, exit_, **self.fetch_kw)
            except guard_error as exc:           # a delisted fund whose NAV ladder is missing: reported, never dropped silently
                wr = {"status": f"manual_missing:{getattr(exc, 'assertion', 'guard')}", "r_ann": np.nan, "max_dd": np.nan}
            status = str(wr.get("status", "ok"))
            status = {"ok": "investable", "manual": "investable"}.get(status, status)
            # PREREG §3.4 vocabulary: a fund liquidated inside the window is `liquidated_in_window` whatever the
            # completeness of its NAV ladder; the uncovered spans (held at 0 %, econ.etf) travel in `incomplete`.
            if wr.get("liquidated_in_window"):
                status = "liquidated_in_window"
            incomplete = [str(x) for x in (wr.get("incomplete") or [])]
            r = wr.get("r_ann")
            rows.append({"iso3": iso3, "ticker": str(e["ticker"]), "inception": e["inception"].date().isoformat(), "status": status,
                         "r": float(r) if r is not None and np.isfinite(float(r)) else np.nan,
                         "max_dd": wr.get("max_dd", np.nan), "issuer": e.get("issuer"),
                         "delisted": (str(e["delisted"])[:10] if pd.notna(e.get("delisted")) else None),
                         "incomplete": "; ".join(incomplete) if incomplete else None})
        t = pd.DataFrame(rows)
        self._cache[T] = t
        return t

    def vt(self, T: int) -> dict:
        return self.etf.vt_benchmark(*self.window(T), **self.fetch_kw)

    def ew(self, T: int) -> dict:
        """Equal-weight basket of every single-country fund investable at T.  ``strict=False`` keeps a delisted member
        whose NAV ladder does not reach the exit at its last known value (0 % thereafter — PREREG §3.4) instead of
        dropping it (which would reintroduce survivorship); such members are listed under ``incomplete``."""
        out = self.etf.ew_basket(T, *self.window(T), strict=False, **self.fetch_kw)
        return {k: v for k, v in out.items() if k != "members"} | {"members": [m.get("ticker") for m in out.get("members", [])]}

    def refs(self, T: int) -> dict:
        out = {}
        entry, exit_ = self.window(T)
        for tk in ("SPY", "EFA", "EEM"):
            try:
                out[tk] = float(self.etf.window_return(tk, entry, exit_, **self.fetch_kw)["r_ann"])
            except Exception as exc:  # noqa: BLE001 — a missing reference row is reported, never fatal
                out[tk] = np.nan
                out[f"{tk}_note"] = str(exc)
        return out


def returns_outcomes(picks: pd.DataFrame, table: pd.DataFrame, bench: dict, universe_iso3: set[str]) -> pd.DataFrame:
    """Attach ``ticker, status, r, r_vt, er, top_q`` to a pick set for one T.  ``status`` ∈ {investable,
    liquidated_in_window, no_fund_at_entry, no_fund_ever} (a liquidated fund whose NAV ladder has gaps keeps
    ``liquidated_in_window`` and lists the gaps in ``incomplete``); ``er`` (vs VT / VT-proxy) only where ``r`` exists;
    ``top_q`` is the top quartile of the investable-at-T fund set."""
    t = table.set_index("iso3")
    inv = t[t["r"].notna()]
    q3 = float(np.quantile(inv["r"], 0.75)) if len(inv) else np.nan
    out = picks.copy()
    out["ticker"] = out["iso3"].map(t["ticker"]) if "ticker" in t else None
    st = out["iso3"].map(t["status"]) if "status" in t else pd.Series([None] * len(out), index=out.index)
    st = st.where(st.notna(), np.where(out["iso3"].isin(universe_iso3), "no_fund_at_entry", "no_fund_ever"))
    out["status"] = st
    out["r"] = out["iso3"].map(t["r"]).astype(float) if "r" in t else np.nan
    for extra in ("inception", "issuer", "delisted", "incomplete"):
        if extra in t:
            out[extra] = out["iso3"].map(t[extra]).astype(object).where(lambda v: v.notna(), None)
    out["r_vt"] = float(bench["vt"]["r_ann"])
    out["er"] = out["r"] - out["r_vt"]
    out["r_ew"] = float(bench["ew"]["r_ann"]) if bench.get("ew") else np.nan
    for tk in ("SPY", "EFA", "EEM"):
        out[f"r_{tk.lower()}"] = float(bench.get("refs", {}).get(tk, np.nan))
    out["benchmark"] = bench["vt"].get("benchmark", "vt")
    out["top_q"] = out["r"] >= q3
    return out


# ----------------------------------------------------------------------------------------------- statistics
def _p_two_sided(est: float, se: float) -> float:
    if not (np.isfinite(se) and se > 0 and np.isfinite(est)):
        return float("nan")
    return float(2.0 * (1.0 - norm.cdf(abs(est) / se)))


def _safe(fn, *a, **kw):
    try:
        v = fn(*a, **kw)
        return v
    except Exception:  # noqa: BLE001 — degenerate samples (e.g. 3 T's with L = 3) are reported as NaN, not crashes
        return float("nan")


def _ci_pair(v) -> list[float]:
    try:
        lo, hi = v
        return [float(lo), float(hi)]
    except Exception:  # noqa: BLE001
        return [float("nan"), float("nan")]


def pooled_statistics(df: pd.DataFrame, h: int, *, stats=None, B: int = B_DEFAULT, seed: int = SEED,
                      pp: float = 100.0) -> dict[str, Any]:
    """PREREG §3.6 items 1–8 on a pooled sample ``df`` with columns ``iso3, T, e`` (log points/yr) and ``top_q``.

    Returns pp/yr numbers: hit rate, top-quartile rate, mean excess, naive / Hansen–Hodrick / Newey–West (L = 2, 4) SEs,
    the plain one-way country-cluster SE (``cluster_se``, PREREG §3.6 item 6) and its within-country Bartlett-kernel
    variant (``cluster_hac_se``, L = h/5 − 1) with two-sided normal p-values, the two block-bootstrap 95 % CIs and
    the wider headline, ``ci_block_T_degenerate`` (block length ≥ number of T's: the T-block interval is a point),
    ``n``, ``n_eff`` and the per-T means.  HH/NW run on the T-aggregated residuals (per-T means, ordered by T)."""
    st = _stats(stats)
    d = df[np.isfinite(df["e"].to_numpy(dtype=np.float64))].copy()
    n = int(len(d))
    out: dict[str, Any] = {"n": n, "n_T": int(d["T"].nunique()) if n else 0}
    if n == 0:
        out.update({k: float("nan") for k in ("hit_rate", "top_quartile_rate", "mean_excess", "naive_se", "naive_p",
                                                "mean_excess_T_avg", "hh_se", "hh_p", "nw2_se", "nw2_p", "nw4_se", "nw4_p",
                                                "cluster_se", "cluster_p", "cluster_hac_se", "cluster_hac_p")})
        out.update({"ci_country_cluster": [float("nan")] * 2, "ci_block_T": [float("nan")] * 2, "ci_block_T_degenerate": False,
                    "ci_headline": [float("nan")] * 2, "ci_excludes_0": False, "n_eff": 0, "per_T": {}})
        return out
    e = d["e"].to_numpy(dtype=np.float64) * pp
    d["e"] = e
    mu = float(e.mean())
    sd = float(e.std(ddof=1)) if n > 1 else float("nan")
    naive = sd / math.sqrt(n) if n > 1 else float("nan")
    per_T = d.groupby("T")["e"].agg(["mean", "count", lambda v: float((v > 0).mean())]).sort_index()
    per_T.columns = ["mean", "count", "hit"]
    ebar = per_T["mean"].to_numpy(dtype=np.float64)
    mu_T = float(ebar.mean())
    L_hh = max(h // 5 - 1, 0)
    # a kernel SE needs more T's than lags (+1); otherwise the estimate is degenerate and reported as NaN
    hh = float(_safe(st.hansen_hodrick_se, ebar, L_hh)) if len(ebar) > L_hh + 1 else float("nan")
    nw2 = float(_safe(st.newey_west_se, ebar, 2)) if len(ebar) > 3 else float("nan")
    nw4 = float(_safe(st.newey_west_se, ebar, 4)) if len(ebar) > 5 else float("nan")
    resid = d.rename(columns={"e": "u"})[["iso3", "T", "u"]]
    cl = float(_safe(st.cluster_hac_se, resid, L_hh, h))
    # PREREG §3.6 item 6 "cluster = country across T": the plain one-way cluster SE (all within-country pairs weight 1);
    # the kernel version above is reported beside it under its own label (a fakes namespace without cluster_se → NaN)
    cl_plain = float(_safe(getattr(st, "cluster_se", lambda r: float("nan")), resid))
    block_len = max(h // 5, 1)
    boot = _safe(st.block_bootstrap_ci, d[["iso3", "T", "e"]], B=B, block_len=block_len, seed=seed, level=0.95)
    if isinstance(boot, dict):
        cc, bt = _ci_pair(boot.get("country_cluster")), _ci_pair(boot.get("block_T"))
        head = _ci_pair(boot.get("headline")) if boot.get("headline") is not None else None
    else:
        cc, bt, head = [float("nan")] * 2, [float("nan")] * 2, None
    # block length ≥ number of T's: every circular block is the whole series and the T-block CI collapses to a point
    bt_degenerate = bool(block_len >= out["n_T"])
    if head is None or not all(np.isfinite(head)):
        widths = [(hi - lo, [lo, hi]) for lo, hi in (cc, bt) if np.isfinite(lo) and np.isfinite(hi)]
        head = max(widths, key=lambda w: w[0])[1] if widths else [float("nan")] * 2
    out.update({
        "hit_rate": float((e > 0).mean()),
        "top_quartile_rate": float(d["top_q"].astype(float).mean()) if "top_q" in d else float("nan"),
        "mean_excess": mu, "sd": sd, "naive_se": naive, "naive_p": _p_two_sided(mu, naive),
        "mean_excess_T_avg": mu_T,
        "hh_L": L_hh, "hh_se": hh, "hh_p": _p_two_sided(mu_T, hh),
        "nw2_se": nw2, "nw2_p": _p_two_sided(mu_T, nw2), "nw4_se": nw4, "nw4_p": _p_two_sided(mu_T, nw4),
        "cluster_se": cl_plain, "cluster_p": _p_two_sided(mu, cl_plain),
        "cluster_hac_se": cl, "cluster_hac_p": _p_two_sided(mu, cl), "cluster_hac_L": L_hh,
        "ci_country_cluster": cc, "ci_block_T": bt, "ci_block_T_degenerate": bt_degenerate, "ci_headline": head,
        # a CI needs at least two rows and two countries to mean anything; degenerate samples never "exclude 0"
        "ci_excludes_0": bool(n >= 2 and d["iso3"].nunique() >= 2 and np.isfinite(head[0]) and np.isfinite(head[1]) and head[0] * head[1] > 0),
        "ci_degenerate": bool(n < 2 or d["iso3"].nunique() < 2),
        "n_eff": int(_safe(st.n_eff, d[["iso3", "T"]], h)) if np.isfinite(_safe(st.n_eff, d[["iso3", "T"]], h)) else 0,
        "per_T": {int(T): {"mean_excess": float(r["mean"]), "n": int(r["count"]), "hit_rate": float(r["hit"])} for T, r in per_T.iterrows()},
        "bootstrap": {"B": B, "seed": seed, "block_len": block_len},
    })
    return out


def null_p(null_stats: np.ndarray, observed: float) -> float:
    """One-sided p = (#draws with statistic ≥ observed + 1) / (B + 1) (PREREG §3.7 [PSD])."""
    ns = np.asarray(null_stats, dtype=np.float64)
    ns = ns[np.isfinite(ns)]
    if not np.isfinite(observed) or len(ns) == 0:
        return float("nan")
    return float(((ns >= observed).sum() + 1) / (len(ns) + 1))


def _pool_draw_stats(draw_sums: np.ndarray, draw_hits: np.ndarray, draw_n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = np.where(draw_n > 0, draw_n, np.nan)
    return draw_sums / n, draw_hits / n


def null_N1(per_T: dict[int, dict], k: int, *, B: int = B_DEFAULT, seed: int = SEED, pp: float = 100.0) -> dict:
    """N1 random-country null: per T draw k candidates uniformly without replacement from ``C(T)`` (restricted
    to the eligible set given), pool, recompute mean excess and hit rate.  ``per_T[T] = {'e': array}`` with the
    candidate residuals (log points/yr).  Returns the null distributions' summaries and the p-values against
    ``observed`` supplied later via :func:`null_p`."""
    rng = np.random.default_rng(seed)
    sums = np.zeros(B)
    hits = np.zeros(B)
    ns = np.zeros(B)
    for T in sorted(per_T):
        e = np.asarray(per_T[T]["e"], dtype=np.float64) * pp
        e = e[np.isfinite(e)]
        m = min(k, len(e))
        if m == 0:
            continue
        idx = np.argsort(rng.random((B, len(e))), axis=1)[:, :m]
        drawn = e[idx]
        sums += drawn.sum(1)
        hits += (drawn > 0).sum(1)
        ns += m
    mu, hit = _pool_draw_stats(sums, hits, ns)
    return {"mu": mu, "hit": hit}


def null_N2(per_T: dict[int, dict], *, B: int = B_DEFAULT, seed: int = SEED, caliper: float = CALIPER,
            pp: float = 100.0) -> dict:
    """N2 income-matched null: for each lookalike draw a non-lookalike from ``C(T)`` with |ln y_T − ln y_pick| ≤ caliper
    (1:1, without replacement within a draw); with no match, draw from the same ln y decile of ``C(T)`` (decile-
    stratified fallback).  ``per_T[T] = {'e', 'lny', 'is_pick'}`` over the candidates of T.  Pools and recomputes
    mean excess and hit rate per draw; also returns the match diagnostics."""
    rng = np.random.default_rng(seed)
    sums = np.zeros(B)
    hits = np.zeros(B)
    ns = np.zeros(B)
    diag = {"n_picks": 0, "n_caliper_matched": 0, "n_decile_fallback": 0, "n_unmatched": 0, "max_abs_gap_caliper": 0.0}
    for T in sorted(per_T):
        e = np.asarray(per_T[T]["e"], dtype=np.float64) * pp
        lny = np.asarray(per_T[T]["lny"], dtype=np.float64)
        is_pick = np.asarray(per_T[T]["is_pick"], dtype=bool)
        ok = np.isfinite(e)
        pool = np.flatnonzero(ok & ~is_pick)
        picks = np.flatnonzero(is_pick)
        if len(pool) == 0 or len(picks) == 0:
            continue
        fin = np.isfinite(lny)
        dec = np.full(len(lny), -1)
        if fin.sum() >= 2:
            qs = np.quantile(lny[fin], np.linspace(0, 1, 11)[1:-1])
            dec[fin] = np.searchsorted(qs, lny[fin], side="right")
        elig: list[np.ndarray] = []
        for i in picks:
            diag["n_picks"] += 1
            if np.isfinite(lny[i]):
                gap = np.abs(lny[pool] - lny[i])
                cal = pool[gap <= caliper]
            else:
                cal = np.array([], dtype=int)
            if len(cal):
                diag["n_caliper_matched"] += 1
                diag["max_abs_gap_caliper"] = max(diag["max_abs_gap_caliper"], float(np.abs(lny[cal] - lny[i]).max()))
                elig.append(cal)
                continue
            same_dec = pool[dec[pool] == dec[i]] if dec[i] >= 0 else np.array([], dtype=int)
            if len(same_dec):
                diag["n_decile_fallback"] += 1
                elig.append(same_dec)
            else:
                diag["n_unmatched"] += 1
                elig.append(pool)          # last resort: any candidate (recorded)
        # vectorised without-replacement: draw all, then re-draw duplicates within a draw (a few rounds suffice)
        choice = np.stack([el[rng.integers(0, len(el), B)] for el in elig])       # [n_picks, B]
        for _ in range(60):
            dup = np.zeros_like(choice, dtype=bool)
            srt = np.sort(choice, axis=0)
            has_dup = (srt[1:] == srt[:-1]).any(0) if len(elig) > 1 else np.zeros(B, bool)
            if not has_dup.any():
                break
            for b in np.flatnonzero(has_dup):
                col = choice[:, b]
                _, first = np.unique(col, return_index=True)
                mask = np.ones(len(col), bool)
                mask[first] = False
                dup[mask, b] = True
            for i in range(len(elig)):
                cols = np.flatnonzero(dup[i])
                if len(cols):
                    choice[i, cols] = elig[i][rng.integers(0, len(elig[i]), len(cols))]
        drawn = e[choice]                                                          # [n_picks, B]
        sums += drawn.sum(0)
        hits += (drawn > 0).sum(0)
        ns += len(picks)
    mu, hit = _pool_draw_stats(sums, hits, ns)
    return {"mu": mu, "hit": hit, "diag": diag}


def paired_bootstrap(a: pd.DataFrame, b: pd.DataFrame, h: int, *, B: int = B_DEFAULT, seed: int = SEED,
                     pp: float = 100.0, T_grid: tuple[int, ...] = T_GRID) -> dict:
    """Paired difference Δ = μ̂(a) − μ̂(b) between two pooled samples (columns ``iso3, T, e``) with the two
    block-bootstrap schemes of §3.6.7 applied to BOTH samples on the same resamples: (a) country cluster over the
    union of countries, (b) circular blocks of h/5 consecutive T's over the ordered grid.  Returns Δ, both 95 %
    percentile CIs, the wider headline, and the one-sided p that Δ ≤ 0 (share of resamples + 1)/(B + 1)."""
    rng = np.random.default_rng(seed)
    A = a[np.isfinite(a["e"])].copy()
    Bd = b[np.isfinite(b["e"])].copy()
    A["e"] = A["e"] * pp
    Bd["e"] = Bd["e"] * pp
    if A.empty or Bd.empty:
        return {"delta": float("nan"), "ci_country_cluster": [float("nan")] * 2, "ci_block_T": [float("nan")] * 2,
                "ci_headline": [float("nan")] * 2, "p_one_sided": float("nan")}
    delta = float(A["e"].mean() - Bd["e"].mean())
    # (a) country cluster
    countries = sorted(set(A["iso3"]) | set(Bd["iso3"]))
    ga = {c: g["e"].to_numpy() for c, g in A.groupby("iso3")}
    gb = {c: g["e"].to_numpy() for c, g in Bd.groupby("iso3")}
    sa = np.array([ga.get(c, np.zeros(0)).sum() for c in countries]); na = np.array([len(ga.get(c, ())) for c in countries])
    sb = np.array([gb.get(c, np.zeros(0)).sum() for c in countries]); nb = np.array([len(gb.get(c, ())) for c in countries])
    idx = rng.integers(0, len(countries), (B, len(countries)))
    da = sa[idx].sum(1) / np.maximum(na[idx].sum(1), 1) - sb[idx].sum(1) / np.maximum(nb[idx].sum(1), 1)
    da = da[(na[idx].sum(1) > 0) & (nb[idx].sum(1) > 0)]
    # (b) circular T blocks
    Ts = [T for T in T_grid if T in set(A["T"]) | set(Bd["T"])]
    blk = max(h // 5, 1)
    ta = A.groupby("T")["e"].agg(["sum", "count"]).reindex(Ts).fillna(0)
    tb = Bd.groupby("T")["e"].agg(["sum", "count"]).reindex(Ts).fillna(0)
    nT = len(Ts)
    n_blocks = math.ceil(nT / blk)
    starts = rng.integers(0, nT, (B, n_blocks))
    pos = (starts[:, :, None] + np.arange(blk)[None, None, :]).reshape(B, -1)[:, :nT] % nT
    sA, cA = ta["sum"].to_numpy()[pos].sum(1), ta["count"].to_numpy()[pos].sum(1)
    sB, cB = tb["sum"].to_numpy()[pos].sum(1), tb["count"].to_numpy()[pos].sum(1)
    ok = (cA > 0) & (cB > 0)
    db = sA[ok] / cA[ok] - sB[ok] / cB[ok]
    def ci(x):
        return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) else [float("nan")] * 2
    cc, bt = ci(da), ci(db)
    head = max((cc, bt), key=lambda c: (c[1] - c[0]) if all(np.isfinite(c)) else -1)
    p = max(float(((da <= 0).sum() + 1) / (len(da) + 1)) if len(da) else float("nan"),
            float(((db <= 0).sum() + 1) / (len(db) + 1)) if len(db) else float("nan"))
    return {"delta": delta, "ci_country_cluster": cc, "ci_block_T": bt, "ci_block_T_degenerate": bool(blk >= nT),
            "ci_headline": head, "p_one_sided": p, "B": B, "seed": seed}


# ----------------------------------------------------------------------------------------------- the experiment
def _status_counts(df: pd.DataFrame) -> dict[str, int]:
    return {str(k): int(v) for k, v in df["status"].value_counts().items()} if "status" in df else {}


def run(corpus: Corpus, gd: GrowthData, returns: ReturnsProvider | None = None, *, stats=None, B: int = B_DEFAULT,
        seed: int = SEED, ks: tuple[int, ...] = KS, growth_T: dict[int, tuple[int, ...]] | None = None,
        returns_T: tuple[int, ...] = RETURNS_T, queries: tuple[str, ...] = QUERIES,
        log: Callable[[str], None] | None = None) -> tuple[dict, pd.DataFrame]:
    """Run Experiment 1 end to end.  Returns ``(result, picks_table)`` — ``result`` follows the
    ``backtest_lookalikes.json`` layout (``rows`` keyed by ``query|k|h|outcome``, ``n3``, ``predictions``,
    ``candidates``, ``prototypes``) and ``picks_table`` is ``tables/backtest_picks.csv``."""
    st = _stats(stats)
    growth_T = growth_T or GROWTH_T
    say = log or (lambda s: None)
    universe_iso3: set[str] = set()
    if returns is not None and hasattr(returns, "universe"):
        u = returns.universe
        universe_iso3 = set(u.loc[u["iso3"].notna(), "iso3"].astype(str))
    table_rows: list[dict] = []
    picks_by: dict[tuple, list[pd.DataFrame]] = {}        # (query, k, h, outcome) -> per-T pick frames
    cands_by: dict[tuple, dict[int, pd.DataFrame]] = {}    # (h, outcome) -> {T: candidates with outcome cols}
    protos: dict[int, pd.DataFrame] = {}
    bench: dict[int, dict] = {}
    etf_tables: dict[int, pd.DataFrame] = {}
    if returns is not None:
        for T in returns_T:
            say(f"[exp1] returns inputs T={T}")
            etf_tables[T] = returns.etf_table(T)
            vt = returns.vt(T)
            try:
                ew = returns.ew(T)
            except Exception as exc:  # noqa: BLE001
                ew = {"r_ann": float("nan"), "n": 0, "note": str(exc)}
            bench[T] = {"vt": vt, "ew": ew, "refs": returns.refs(T)}

    for h, Ts in growth_T.items():
        for T in Ts:
            say(f"[exp1] T={T} h={h}")
            cand_all = candidates(corpus, gd, T, h)
            if cand_all.empty:
                continue
            P = prototype_set(corpus, gd, T)
            protos[T] = P
            Dm = proto_distance_matrix(corpus, P["row"].to_numpy(), cand_all["row"].to_numpy())
            md = min_distances(Dm)
            D3 = three_band_distance_matrix(corpus, P["row"].to_numpy(), cand_all["row"].to_numpy())
            md3 = min_distances(D3)
            cand_all = cand_all.assign(D_P=md["D"], D_P_soft=md["soft"], D_3band=md3["D"])
            do_returns = returns is not None and T in returns_T and h == RETURNS_H
            for outcome in (["growth", "returns"] if do_returns else ["growth"]):
                cands_by.setdefault((h, outcome), {})[T] = cand_all
            # candidate rows (role=candidate), once per (T, h)
            cg = growth_outcomes(cand_all, cand_all)
            for r in cg.itertuples(index=False):
                table_rows.append({"T": T, "query": "candidates", "k": None, "h": h, "outcome": "growth", "iso3": r.iso3,
                                   "year": T, "role": "candidate", "d": float(r.D_P), "y_T": r.y_T, "g": r.g, "eg": r.eg,
                                   "partial": bool(r.partial)})
            if T in protos and h == 10:
                for r in P.itertuples(index=False):
                    table_rows.append({"T": T, "query": "B", "k": None, "h": 10, "outcome": "growth", "iso3": r.iso3,
                                       "year": int(r.year), "role": "prototype", "g": r.g})
            for q in queries:
                cand_q = cand_all[cand_all["iso3"] != ANCHOR_ID].reset_index(drop=True) if q in ("A", "C") else cand_all
                for k in ks:
                    if q == "A":
                        picks = query_A(corpus, cand_q, T, k)
                    elif q == "C":
                        try:
                            picks = query_A(corpus, cand_q, T, k, trend="motion")
                        except Exception as exc:  # noqa: BLE001 — informational query; report and continue
                            say(f"[exp1] Query C failed at T={T}: {exc}")
                            continue
                    elif q == "B":
                        picks = query_B(cand_q, {"D": cand_q["D_P"].to_numpy(), "D2": md["D2"], "soft": cand_q["D_P_soft"].to_numpy()}, k)
                    elif q == "B_soft":
                        picks = query_B(cand_q, {"D": cand_q["D_P"].to_numpy(), "D2": md["D2"], "soft": cand_q["D_P_soft"].to_numpy()}, k, soft=True)
                    elif q == "B3":
                        picks = query_B(cand_q, {"D": cand_q["D_3band"].to_numpy(), "D2": md3["D2"], "soft": cand_q["D_3band"].to_numpy()}, k)
                    elif q == "N4":
                        picks = query_N4(cand_q, gd, T, k)
                    else:
                        raise ValueError(q)
                    picks = growth_outcomes(picks, cand_all)
                    picks["T"] = T
                    picks_by.setdefault((q, k, h, "growth"), []).append(picks)
                    for r in picks.itertuples(index=False):
                        table_rows.append({"T": T, "query": q, "k": k, "h": h, "outcome": "growth", "iso3": r.iso3, "year": T,
                                           "role": "pick", "d": float(r.d), "y_T": r.y_T, "g": r.g, "eg": r.eg,
                                           "partial": bool(r.partial)})
                    if do_returns:
                        pr = returns_outcomes(picks, etf_tables[T], bench[T], universe_iso3)
                        picks_by.setdefault((q, k, h, "returns"), []).append(pr)
                        for r in pr.itertuples(index=False):
                            table_rows.append({"T": T, "query": q, "k": k, "h": h, "outcome": "returns", "iso3": r.iso3,
                                               "year": T, "role": "pick", "d": float(r.d), "y_T": r.y_T, "g": r.g, "eg": r.eg,
                                               "ticker": r.ticker, "status": r.status, "r": r.r, "r_vt": r.r_vt, "er": r.er,
                                               "benchmark": r.benchmark, "partial": bool(r.partial)})

    # ---- statistics + nulls per row
    rows: dict[str, dict] = {}
    for (q, k, h, outcome), frames in sorted(picks_by.items(), key=lambda kv: (kv[0][3], kv[0][0], -kv[0][1], kv[0][2])):
        say(f"[exp1] statistics {q} k={k} h={h} {outcome}")
        df = pd.concat(frames, ignore_index=True)
        row: dict[str, Any] = {"query": q, "query_name": QUERY_NAMES.get(q, q), "k": k, "h": h, "outcome": outcome,
                               "T_values": sorted(int(t) for t in df["T"].unique()),
                               "n_picks": int(len(df)), "n_partial": int(df["partial"].sum()) if ("partial" in df and outcome == "growth") else 0}
        cands = cands_by[(h, outcome)]
        pick_cols = [c for c in ("T", "iso3", "d", "y_T", "g", "eg", "partial", "src", "ticker", "status", "r", "r_vt", "er", "benchmark",
                                 "inception", "issuer", "delisted", "incomplete") if c in df]
        row["picks"] = df[pick_cols].sort_values(["T", "d"]).to_dict("records")
        if outcome == "growth":
            s = df.rename(columns={"eg": "e"})[["iso3", "T", "e", "top_q"]]
            row["stats"] = pooled_statistics(s, h, stats=st, B=B, seed=seed)
            perT_all = {T: {"e": (c["g"] - np.median(c["g"])).to_numpy()} for T, c in cands.items()}
            n1 = null_N1(perT_all, k, B=B, seed=seed)
            row["nulls"] = {"N1": {"p_mean_excess": null_p(n1["mu"], row["stats"]["mean_excess"]),
                                   "p_hit_rate": null_p(n1["hit"], row["stats"]["hit_rate"]),
                                   "null_mean": float(np.nanmean(n1["mu"])), "null_sd": float(np.nanstd(n1["mu"])),
                                   "share_at_least_as_good": float(np.nanmean(n1["mu"] >= row["stats"]["mean_excess"])),
                                   "B": B}}
            perT_n2 = {}
            for T, c in cands.items():
                pk = set(df.loc[df["T"] == T, "iso3"])
                perT_n2[T] = {"e": (c["g"] - np.median(c["g"])).to_numpy(), "lny": c["lny"].to_numpy(),
                              "is_pick": c["iso3"].isin(pk).to_numpy()}
            n2 = null_N2(perT_n2, B=B, seed=seed)
            row["nulls"]["N2"] = {"p_mean_excess": null_p(n2["mu"], row["stats"]["mean_excess"]),
                                  "p_hit_rate": null_p(n2["hit"], row["stats"]["hit_rate"]),
                                  "null_mean": float(np.nanmean(n2["mu"])), "null_sd": float(np.nanstd(n2["mu"])),
                                  "share_at_least_as_good": float(np.nanmean(n2["mu"] >= row["stats"]["mean_excess"])),
                                  "caliper": CALIPER, "B": B, **n2["diag"]}
            row["candidates_per_T"] = {int(T): int(len(c)) for T, c in cands.items()}
            row["median_g_per_T"] = {int(T): float(np.median(c["g"])) * 100 for T, c in cands.items()}
        else:
            row["status_counts"] = _status_counts(df)
            row["status_counts_per_T"] = {int(T): _status_counts(g) for T, g in df.groupby("T")}
            # NAV-ladder gaps (delisted funds whose manual ladder does not reach the exit; uncovered span held at 0 %)
            inc = df[df["incomplete"].notna()] if "incomplete" in df else df.iloc[0:0]
            row["ladder_incomplete"] = [{"T": int(r.T), "iso3": r.iso3, "ticker": r.ticker, "status": r.status, "spans": r.incomplete}
                                        for r in inc.itertuples(index=False)]
            row["n_ladder_incomplete"] = int(len(inc))
            row["investable_share_per_T"] = {int(T): float(g["r"].notna().mean()) for T, g in df.groupby("T")}
            row["benchmark_per_T"] = {int(T): str(g["benchmark"].iloc[0]) for T, g in df.groupby("T")}
            row["benchmark"] = sorted(set(df["benchmark"].astype(str)))
            row["r_vt_per_T"] = {int(T): float(g["r_vt"].iloc[0]) * 100 for T, g in df.groupby("T")}
            row["r_ew_per_T"] = {int(T): float(g["r_ew"].iloc[0]) * 100 for T, g in df.groupby("T")}
            row["ew_n_per_T"] = {int(T): int(bench[T]["ew"].get("n", 0)) for T in df["T"].unique()}
            inv = df[df["r"].notna()]
            s = inv.rename(columns={"er": "e"})[["iso3", "T", "e", "top_q"]]
            row["stats"] = pooled_statistics(s, h, stats=st, B=B, seed=seed)
            row["mean_r"] = float(inv["r"].mean() * 100) if len(inv) else float("nan")
            row["vs"] = {}
            for name, col in (("ew", "r_ew"), ("spy", "r_spy"), ("efa", "r_efa"), ("eem", "r_eem")):
                ee = inv.assign(e=inv["r"] - inv[col])[["iso3", "T", "e", "top_q"]]
                sub = pooled_statistics(ee, h, stats=st, B=B, seed=seed)
                row["vs"][name] = {kk: sub[kk] for kk in ("n", "mean_excess", "naive_se", "hit_rate", "ci_headline", "ci_excludes_0")}
            oos = inv[inv["T"] >= 2010]
            row["oos_block_T_ge_2010"] = {"n": int(len(oos)), "mean_excess_vs_vt": float(oos["er"].mean() * 100) if len(oos) else float("nan"),
                                          "same_sign_as_pooled": bool(len(oos) and np.sign(oos["er"].mean()) == np.sign(inv["er"].mean()))}
            # N1-investable: draws among investable candidates only
            perT_inv = {}
            for T, c in cands.items():
                t = etf_tables[T].set_index("iso3")["r"]
                r = c["iso3"].map(t).to_numpy(dtype=np.float64)
                perT_inv[T] = {"e": r - float(bench[T]["vt"]["r_ann"])}
            n1 = null_N1(perT_inv, k, B=B, seed=seed)
            row["nulls"] = {"N1_investable": {"p_mean_excess": null_p(n1["mu"], row["stats"]["mean_excess"]),
                                              "p_hit_rate": null_p(n1["hit"], row["stats"]["hit_rate"]),
                                              "null_mean": float(np.nanmean(n1["mu"])), "null_sd": float(np.nanstd(n1["mu"])),
                                              "share_at_least_as_good": float(np.nanmean(n1["mu"] >= row["stats"]["mean_excess"])),
                                              "B": B}}
            # N4-investable comparator: momentum among investable candidates; paired bootstrap p
            n4_frames = []
            for T, c in cands.items():
                t = etf_tables[T].set_index("iso3")["r"]
                ci = c[c["iso3"].map(t).notna()].reset_index(drop=True)
                if ci.empty:
                    continue
                p4 = growth_outcomes(query_N4(ci, gd, T, k), c)
                p4["T"] = T
                n4_frames.append(returns_outcomes(p4, etf_tables[T], bench[T], universe_iso3))
            if n4_frames:
                n4 = pd.concat(n4_frames, ignore_index=True)
                n4 = n4[n4["r"].notna()]
                s4 = n4.rename(columns={"er": "e"})[["iso3", "T", "e", "top_q"]]
                row["nulls"]["N4_investable"] = {"stats": pooled_statistics(s4, h, stats=st, B=B, seed=seed),
                                                 "paired_vs_picks": paired_bootstrap(s, s4, h, B=B, seed=seed)}
                row["nulls"]["N4_investable"]["p_one_sided"] = row["nulls"]["N4_investable"]["paired_vs_picks"]["p_one_sided"]
            row["candidates_per_T"] = {int(T): int(len(c)) for T, c in cands.items()}
            row["investable_candidates_per_T"] = {int(T): int(etf_tables[T]["r"].notna().sum()) for T in cands}
        rows[f"{q}|{k}|{h}|{outcome}"] = row

    # ---- N3 paired comparison (42-vector Query B vs the three-band pipeline), growth rows
    n3: dict[str, dict] = {}
    for k in ks:
        for h in growth_T:
            a = picks_by.get(("B", k, h, "growth"))
            b = picks_by.get(("B3", k, h, "growth"))
            if a and b:
                fa = pd.concat(a).rename(columns={"eg": "e"})[["iso3", "T", "e"]]
                fb = pd.concat(b).rename(columns={"eg": "e"})[["iso3", "T", "e"]]
                n3[f"{k}|{h}"] = {"k": k, "h": h, **paired_bootstrap(fa, fb, h, B=B, seed=seed),
                                  "mean_excess_42": rows[f"B|{k}|{h}|growth"]["stats"]["mean_excess"],
                                  "mean_excess_3band": rows[f"B3|{k}|{h}|growth"]["stats"]["mean_excess"]}
    # ---- N4 (growth) paired against Query B
    for key, row in rows.items():
        q, k, h, outcome = key.split("|")
        if q == "B" and outcome == "growth" and f"N4|{k}|{h}|growth" in rows:
            fa = pd.concat(picks_by[("B", int(k), int(h), "growth")]).rename(columns={"eg": "e"})[["iso3", "T", "e"]]
            fb = pd.concat(picks_by[("N4", int(k), int(h), "growth")]).rename(columns={"eg": "e"})[["iso3", "T", "e"]]
            row["nulls"]["N4"] = {"paired_vs_picks": paired_bootstrap(fa, fb, int(h), B=B, seed=seed),
                                  "mean_excess_N4": rows[f"N4|{k}|{h}|growth"]["stats"]["mean_excess"]}
            row["nulls"]["N4"]["p_one_sided"] = row["nulls"]["N4"]["paired_vs_picks"]["p_one_sided"]

    result = {
        "_meta": {"seed": seed, "B": B, "ks": list(ks), "T_grid": list(T_GRID), "growth_T": {str(h): list(v) for h, v in growth_T.items()},
                  "returns_T": list(returns_T) if returns is not None else [], "minpop_thousands": MINPOP, "caliper": CALIPER,
                  "prototype_rule": {"decile": PROTO_DECILE, "max_per_country": PROTO_MAX_PER_COUNTRY, "min_gap_years": PROTO_MIN_GAP},
                  "softmin_tau_frac": SOFTMIN_TAU_FRAC, "queries": list(queries), "query_names": QUERY_NAMES,
                  "units": "pp/yr (log points × 100) for mean excess, SEs and CIs; g, r, eg, er in the picks table are log points/yr",
                  "returns_note": "returns rows: entry = last NYSE trading day of T, exit = of T + 10; excess vs VT (VT proxy before 2008-06-24) is the headline; status counts are reported beside every return statistic",
                  "no_etf_rows": {str(T): "no US-listed single-country ETF existed at entry (first WEBS 1996-03)" for T in (1990, 1995)}},
        "rows": rows,
        "n3": n3,
        "prototypes": {int(T): P[["iso3", "year", "g"]].to_dict("records") for T, P in protos.items()},
        "candidates": {f"{h}|{outcome}": {int(T): int(len(c)) for T, c in cands.items()} for (h, outcome), cands in cands_by.items()},
        "benchmarks": {int(T): {"vt": {kk: (vv if not isinstance(vv, float) else float(vv)) for kk, vv in b["vt"].items() if kk != "legs"},
                                "vt_legs": b["vt"].get("legs"), "ew": b["ew"], "refs": b["refs"]} for T, b in bench.items()},
    }
    result["predictions"] = evaluate_predictions(result)
    table = pd.DataFrame(table_rows)
    for c in PICK_COLUMNS:
        if c not in table:
            table[c] = np.nan
    table = table[PICK_COLUMNS]
    return result, table


# ----------------------------------------------------------------------------------------------- predictions
def _row(result: dict, q: str, k: int, h: int, outcome: str) -> dict | None:
    return result.get("rows", {}).get(f"{q}|{k}|{h}|{outcome}")


def _in(x: float, lo: float, hi: float) -> bool:
    return bool(np.isfinite(x) and lo <= x <= hi)


def evaluate_predictions(result: dict) -> dict:
    """PREREG §3.8 P1–P5 and P3b with observed values and ``met``.  Soft clauses ("plausible", "likely") are
    reported as observed but do not enter ``met``; every hard numeric clause does."""
    out: dict[str, dict] = {}
    B = _row(result, "B", K_PRIMARY, 10, "growth")
    B3 = result.get("n3", {}).get(f"{K_PRIMARY}|10")
    if B:
        s, nl = B["stats"], B["nulls"]
        comps = {"mu_eg_in_[0.3,1.5]": {"value": s["mean_excess"], "ok": _in(s["mean_excess"], 0.3, 1.5)},
                 "hit_rate_in_[.55,.70]": {"value": s["hit_rate"], "ok": _in(s["hit_rate"], 0.55, 0.70)},
                 "n_eff_in_[20,30]": {"value": s["n_eff"], "ok": _in(s["n_eff"], 20, 30)}}
        soft = {"p_N1_lt_05_plausible": {"value": nl["N1"]["p_mean_excess"], "observed_true": bool(nl["N1"]["p_mean_excess"] < 0.05)},
                "p_N2_gt_05_likely": {"value": nl["N2"]["p_mean_excess"], "observed_true": bool(nl["N2"]["p_mean_excess"] > 0.05)}}
        out["P1"] = {"statement": "growth μ̂_eg ∈ [+0.3, +1.5] pp/yr, hit rate .55–.70, N1 p < .05 plausible, N2 p likely > .05, N_eff 20–30",
                     "row": "B|10|10|growth", "components": comps, "soft": soft, "met": all(c["ok"] for c in comps.values())}
    if B3:
        d = B3["delta"]
        out["P2"] = {"statement": "|shape − 3-band| < 0.3 pp (the 42-vector adds little beyond u15/wa/o65)",
                     "value": d, "ci_headline": B3["ci_headline"], "met": bool(np.isfinite(d) and abs(d) < 0.3)}
    R = _row(result, "B", K_PRIMARY, 10, "returns")
    if R:
        s = R["stats"]
        inv = R["investable_share_per_T"]
        width = s["ci_headline"][1] - s["ci_headline"][0] if all(np.isfinite(s["ci_headline"])) else float("nan")
        liq2015 = R["status_counts_per_T"].get(2015, {}).get("liquidated_in_window", 0)
        comps = {
            "investable_share_lt_40pct_at_2000_2005": {"value": {str(T): inv.get(T) for T in (2000, 2005)},
                                                       "ok": all(inv.get(T, 1.0) < 0.40 for T in (2000, 2005) if T in inv) and any(T in inv for T in (2000, 2005))},
            "investable_share_60_75pct_at_2010_2015": {"value": {str(T): inv.get(T) for T in (2010, 2015)},
                                                       "ok": all(_in(inv.get(T, float("nan")), 0.60, 0.75) for T in (2010, 2015) if T in inv) and any(T in inv for T in (2010, 2015))},
            "mu_er_in_[-4,3]_vs_vt": {"value": s["mean_excess"], "ok": _in(s["mean_excess"], -4, 3)},
            "ci_width_gt_8": {"value": width, "ok": bool(np.isfinite(width) and width > 8)},
            "zero_not_rejected": {"value": s["ci_headline"], "ok": not s["ci_excludes_0"]},
            "n_eff_lt_15": {"value": s["n_eff"], "ok": bool(s["n_eff"] < 15)},
            "ge_1_liquidation_in_2015_cohort": {"value": liq2015, "ok": bool(liq2015 >= 1)},
        }
        out["P3"] = {"statement": "returns vs VT / VT-proxy: investable share < 40 % at T = 2000/05, 60–75 % at 2010/15; μ̂_er ∈ [−4, +3] pp/yr; CI width > 8 pp; zero not rejected; N_eff < 15; ≥ 1 liquidation in the 2015 cohort",
                     "row": "B|10|10|returns", "components": comps, "met": all(c["ok"] for c in comps.values())}
        ew_vs_vt = {str(T): R["r_ew_per_T"][T] - R["r_vt_per_T"][T] for T in (2010, 2015) if T in R["r_ew_per_T"] and T in R["r_vt_per_T"]}
        vals = [v for v in ew_vs_vt.values() if np.isfinite(v)]
        out["P3b"] = {"statement": "the equal-weight investable basket itself does not beat VT over 2010–2025 (T = 2010 and T = 2015 windows)",
                      "ew_minus_vt_pp_per_yr": ew_vs_vt, "met": bool(vals) and all(v <= 0 for v in vals)}
    B20 = _row(result, "B", K_PRIMARY, 20, "growth")
    if B20:
        s = B20["stats"]
        out["P4"] = {"statement": "h = 20 growth positive with CI including 0", "row": "B|10|20|growth",
                     "value": s["mean_excess"], "ci_headline": s["ci_headline"],
                     "met": bool(np.isfinite(s["mean_excess"]) and s["mean_excess"] > 0 and not s["ci_excludes_0"])}
    A = _row(result, "A", K_PRIMARY, 10, "growth")
    if A and B:
        sa, sb = A["stats"], B["stats"]
        comps = {"same_sign_growth": {"A": sa["mean_excess"], "B": sb["mean_excess"],
                                      "ok": bool(np.sign(sa["mean_excess"]) == np.sign(sb["mean_excess"]))},
                 "wider_ci_growth": {"A": sa["ci_headline"], "B": sb["ci_headline"],
                                     "ok": bool((sa["ci_headline"][1] - sa["ci_headline"][0]) > (sb["ci_headline"][1] - sb["ci_headline"][0]))}}
        Ar, Br = _row(result, "A", K_PRIMARY, 10, "returns"), _row(result, "B", K_PRIMARY, 10, "returns")
        if Ar and Br and Ar["stats"]["n"] and Br["stats"]["n"]:
            comps["same_sign_returns"] = {"A": Ar["stats"]["mean_excess"], "B": Br["stats"]["mean_excess"],
                                          "ok": bool(np.sign(Ar["stats"]["mean_excess"]) == np.sign(Br["stats"]["mean_excess"]))}
        out["P5"] = {"statement": "Query A same signs as Query B, wider CIs", "components": comps,
                     "met": all(c["ok"] for c in comps.values())}
    return out


# ----------------------------------------------------------------------------------------------- io
def to_jsonable(o):
    """Recursively convert numpy / pandas scalars (and NaN → None) for ``json.dump``."""
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return [to_jsonable(v) for v in o.tolist()]
    return o


def dump_json(obj: dict, path) -> None:
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_jsonable(obj), indent=1, ensure_ascii=False))


# ----------------------------------------------------------------------------------------------- real inputs
def load_real_corpus() -> Corpus:
    """The built corpus: ``shapes.load_corpus`` + ``entities.load_entities`` + ``metrics.load_sigma``."""
    from pyramid_explorer.entities import load_entities
    from pyramid_explorer.metrics import load_sigma
    from pyramid_explorer.shapes import load_corpus

    X, keys = load_corpus()
    return Corpus(X, keys, load_entities(), load_sigma())


def load_real_growth() -> GrowthData:
    """Growth windows and levels through ``econ.data`` (E1): ``load_gdp_panel`` + ``growth_windows``."""
    from pyramid_explorer.econ import data

    panel = data.load_gdp_panel()
    if hasattr(data, "all_windows"):
        levels = panel[["iso3", "year", "y_level"]].dropna().drop_duplicates(["iso3", "year"])
        return GrowthData(data.all_windows(panel), levels)
    return GrowthData.from_panel(panel, data.growth_windows)
