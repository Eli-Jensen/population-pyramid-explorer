"""Twins, opposites, time-shift and isolation queries over the corpus (CONTRACT §3 `search.py`, PLAN §5–§6).

A `Query` names a (entity, year) plus its constraints; `candidate_mask` turns the constraints into a boolean
row mask; `similar` / `different` / `best_year_per_entity` rank the masked rows under the query's metric
(snapshot metrics from `metrics.py`, or the trajectory metrics when ``trend`` is set).  Results are
deduplicated per entity (best year per country) and always exclude the query's own entity.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from pyramid_explorer.features import features, zscores
from pyramid_explorer.metrics import distances, lagged
from pyramid_explorer.paths import DATA_PROCESSED, LAST_OBSERVED_YEAR, YEARS

YEAR_MODES = ("same", "near", "range", "any", "today")
TREND_KINDS = ("motion", "path")
MAX_POOL = 2000
POOL_FRAC = 0.25
# MMR diversity presets (PLAN §5). Calibrated on the real corpus (199 anchors ≥ 100k at 2026, blend): the
# diversity term saturates early because the pool is already the farthest quartile, so β = 2 and β = 4 pick the
# same five countries for 85 % of anchors. Mean top-5 Jaccard vs strict: β 0.25 → 0.77, 0.5 → 0.66, 1 → 0.47,
# 2 → 0.37, 4 → 0.35; balanced (0.5) and spread (2) differ on 99 % of anchors.
DIV_PRESETS: dict[str, float] = {"strict": 0.0, "balanced": 0.5, "spread": 2.0}


@dataclass
class Query:
    """One search request. Years in ``from_year``/``to_year`` are inclusive; ``minpop`` in thousands."""
    id: str
    year: int
    mode: str = "same"                 # same | near | range | any | today
    n: int = 10                        # half-width of the `near` window
    from_year: int | None = None
    to_year: int | None = None
    era: str = "obs"                   # obs | all
    scope: str = "c"                   # c (countries) | all (countries + aggregates)
    minpop: float = 100.0
    metric: str = "blend"
    sex: str = "2"
    k: int = 5
    div: float = DIV_PRESETS["balanced"]   # MMR diversity β for `different` (strict 0 · balanced 0.5 · spread 2)
    current_year: int = 2026
    trend: str | None = None           # None | motion | path
    L: int = 10                        # trend window in years


@dataclass
class Result:
    id: str
    year: int
    row: int
    d: float
    rank_raw: int                      # 1-based position in the plain (undiversified) ordering
    dy: int                            # year − query year


# --------------------------------------------------------------------------------------------- inputs
def load_inputs() -> tuple[np.ndarray, pd.DataFrame, list[dict]]:
    """(s42, keys, entities) via `shapes.load_corpus` / `entities.load_entities` when A1's loaders work,
    else straight from the ``data/processed`` exports (so B/D are never blocked by an unbuilt DuckDB)."""
    try:
        from pyramid_explorer import entities as ent_mod, shapes  # noqa: WPS433 — optional at M0
        X, keys = shapes.load_corpus()
        ents = ent_mod.load_entities()
    except Exception:  # noqa: BLE001 — stub module, missing DB file, unbuilt corpus: all mean "use the exports"
        if not (DATA_PROCESSED / "corpus_s42.npy").exists():
            raise
        X = np.load(DATA_PROCESSED / "corpus_s42.npy")
        keys = pd.read_parquet(DATA_PROCESSED / "corpus_keys.parquet")
        ents = json.loads((DATA_PROCESSED / "entities.json").read_text())
    return X, keys, ents


def row_of(keys: pd.DataFrame, id: str, year: int) -> int:
    """Corpus row of (id, year); raises KeyError when absent."""
    hit = np.flatnonzero((keys["id"].to_numpy() == id) & (keys["year"].to_numpy() == year))
    if len(hit) != 1:
        raise KeyError(f"({id}, {year}) not in corpus")
    return int(keys["row"].iloc[hit[0]])


# --------------------------------------------------------------------------------------------- mask
def candidate_mask(keys: pd.DataFrame, entities: list[dict], q: Query,
                   last_observed_year: int = LAST_OBSERVED_YEAR) -> np.ndarray:
    """Boolean ``[n_rows]``: year mode ∧ era ∧ scope ∧ minpop (candidate's own-year pop) ∧ not own entity
    ∧ (trend: ``year − L ≥ 1950``).  Era ``obs`` keeps ``year ≤ max(last_observed_year, current_year)``
    unless the query year is itself a projection (``q.year > current_year``), which flips it to ``all``."""
    if q.mode not in YEAR_MODES:
        raise ValueError(f"mode must be one of {YEAR_MODES}, got {q.mode!r}")
    if q.trend is not None and q.trend not in TREND_KINDS:
        raise ValueError(f"trend must be one of {TREND_KINDS} or None, got {q.trend!r}")
    year = keys["year"].to_numpy()
    if q.mode == "same":
        m = year == q.year
    elif q.mode == "today":
        m = year == q.current_year
    elif q.mode == "near":
        m = np.abs(year - q.year) <= q.n
    elif q.mode == "range":
        lo = YEARS[0] if q.from_year is None else q.from_year
        hi = YEARS[-1] if q.to_year is None else q.to_year
        m = (year >= lo) & (year <= hi)
    else:
        m = np.ones(len(keys), bool)
    if q.era == "obs" and q.year <= q.current_year:
        m &= year <= max(last_observed_year, q.current_year)
    elif q.era not in ("obs", "all"):
        raise ValueError(f"era must be obs|all, got {q.era!r}")
    if q.scope == "c":
        m &= keys["type"].to_numpy() == "country"
    elif q.scope != "all":
        raise ValueError(f"scope must be c|all, got {q.scope!r}")
    m &= keys["pop_total"].to_numpy() >= q.minpop
    m &= keys["id"].to_numpy() != q.id
    if q.trend is not None:
        m &= year - q.L >= YEARS[0]
    return m


# --------------------------------------------------------------------------------------------- space
class _Space:
    """Distances under the query's metric from any corpus row to the whole corpus (lags prebuilt for trend)."""

    def __init__(self, X, keys, entities, q: Query, sigma: dict, feats=None, emb=None):
        self.X, self.keys, self.q, self.sigma, self.emb = np.asarray(X, np.float64), keys, q, sigma, emb
        self.qrow = row_of(keys, q.id, q.year)
        self.metric = q.metric if q.trend is None else {"motion": "trend", "path": "path"}[q.trend]
        self.X_prev = None
        if q.trend is not None:
            if q.year - q.L < YEARS[0]:
                raise ValueError(f"trend window {q.L} y reaches before {YEARS[0]} for {q.id} {q.year}")
            if q.trend == "path" and q.L % 5:
                raise ValueError("path needs L to be a multiple of 5")
            lags = [q.L] if q.trend == "motion" else list(range(5, q.L + 1, 5))
            self.X_prev = np.stack([lagged(self.X, s) for s in lags])
        self.feats = feats
        if self.metric == "feat" and (feats is None or "mu" not in feats.attrs):
            # z-score against the focal-year country set in scope (own entity included)
            ref = candidate_mask(keys, entities, replace(q, mode="same", trend=None, id=""))
            self.feats = zscores(features(self.X) if feats is None else feats, np.flatnonzero(ref))

    def from_row(self, row: int) -> np.ndarray:
        q_prev = None if self.X_prev is None else self.X_prev[:, row]
        return distances(self.metric, self.X[row], self.X, sex=self.q.sex, sigma=self.sigma, feats=self.feats,
                         emb=self.emb, q_row=row, L=self.q.L, X_prev=self.X_prev, q_prev=q_prev)


def _table(sp: _Space, mask: np.ndarray) -> pd.DataFrame:
    rows = np.flatnonzero(mask)
    d = sp.from_row(sp.qrow)[rows]
    t = pd.DataFrame({"row": rows, "id": sp.keys["id"].to_numpy()[rows], "year": sp.keys["year"].to_numpy()[rows],
                      "d": d.astype(np.float64)})
    t["dy"] = t["year"] - sp.q.year
    return t[np.isfinite(t["d"])]


def _dedupe(t: pd.DataFrame, farthest: bool) -> pd.DataFrame:
    """One row per entity: min (or max) d, ties broken by year proximity; sorted the same way."""
    t = t.assign(_ady=t["dy"].abs()).sort_values(["d", "_ady", "year"], ascending=[not farthest, True, True])
    return t.drop_duplicates("id").drop(columns="_ady").reset_index(drop=True)


def _results(t: pd.DataFrame, ranks: np.ndarray) -> list[Result]:
    return [Result(str(r.id), int(r.year), int(r.row), float(r.d), int(rk), int(r.dy))
            for r, rk in zip(t.itertuples(index=False), ranks)]


# --------------------------------------------------------------------------------------------- queries
def similar(X, keys, entities, q: Query, sigma: dict, *, feats=None, emb=None) -> list[Result]:
    """The ``k`` nearest entities (best year each) under the query's metric, sorted by d."""
    sp = _Space(X, keys, entities, q, sigma, feats, emb)
    t = _dedupe(_table(sp, candidate_mask(keys, entities, q)), farthest=False).head(q.k)
    return _results(t, np.arange(1, len(t) + 1))


def different(X, keys, entities, q: Query, sigma: dict, *, feats=None, emb=None) -> list[Result]:
    """Diversified farthest-k (MMR): pool = min(⌈0.25·|cand|⌉, 2000) farthest after per-entity dedupe
    (floored at k so tiny candidate sets still return k); greedy ``argmax d(q,x) + div·min_{s∈S} d(x,s)``;
    ``div=0`` reproduces plain farthest-k.  ``rank_raw`` is the plain farthest rank; sorted by d descending.
    Diversity is over SHAPE distance only: the pool for an old anchor is all young 'pyramid'-class countries,
    so no β delivers Hahn-Klimroth-class or UN-region coverage (see ``DIV_PRESETS`` and evals/RESULTS.md)."""
    sp = _Space(X, keys, entities, q, sigma, feats, emb)
    t = _dedupe(_table(sp, candidate_mask(keys, entities, q)), farthest=True)
    if t.empty:
        return []
    pool = t.head(min(max(math.ceil(POOL_FRAC * len(t)), q.k), MAX_POOL)).reset_index(drop=True)
    dq = pool["d"].to_numpy()
    prow = pool["row"].to_numpy()
    chosen = [0]
    min_ds = np.full(len(pool), np.inf)
    while len(chosen) < min(q.k, len(pool)):
        s = chosen[-1]
        min_ds = np.minimum(min_ds, sp.from_row(int(prow[s]))[prow].astype(np.float64))
        score = dq + q.div * min_ds
        score[chosen] = -np.inf
        chosen.append(int(np.argmax(score)))
    sel = sorted(chosen)                       # pool is sorted by d desc ⇒ ascending index = descending d
    return _results(pool.iloc[sel], np.asarray(sel) + 1)


def best_year_per_entity(X, keys, entities, q: Query, sigma: dict, **kw) -> pd.DataFrame:
    """Time-shift table: for every other entity in scope, ``y* = argmin_y d(q, c_y)`` over the allowed era.
    Columns ``id, best_year, d, dy, boundary_hit`` (``boundary_hit``: y* sits on the edge of the entity's
    allowed years, i.e. the match is "not reached" inside the era); sorted by d."""
    sp = _Space(X, keys, entities, q, sigma, kw.get("feats"), kw.get("emb"))
    t = _table(sp, candidate_mask(keys, entities, replace(q, mode="any")))
    edges = t.groupby("id")["year"].agg(["min", "max"])
    best = _dedupe(t, farthest=False)
    lo, hi = edges.loc[best["id"], "min"].to_numpy(), edges.loc[best["id"], "max"].to_numpy()
    return pd.DataFrame({"id": best["id"], "best_year": best["year"], "d": best["d"], "dy": best["dy"],
                         "boundary_hit": (best["year"].to_numpy() == lo) | (best["year"].to_numpy() == hi)})


def isolation(X, keys, entities, year: int, metric: str, sigma: dict, *, sex: str = "2", k: int = 5,
              minpop: float = 100.0, feats=None, emb=None) -> pd.DataFrame:
    """Per country of ``year`` with pop ≥ minpop: mean distance to its ``k`` nearest same-year countries.
    Sorted descending (most isolated first)."""
    m = ((keys["year"].to_numpy() == year) & (keys["type"].to_numpy() == "country")
         & (keys["pop_total"].to_numpy() >= minpop))
    rows = np.flatnonzero(m)
    Xs = np.asarray(X, np.float64)[rows]
    fs = None
    if metric == "feat":
        fs = zscores(features(Xs) if feats is None or "mu" in feats.attrs else feats.iloc[rows], np.arange(len(rows)))
    es = None if emb is None else np.asarray(emb)[rows]
    iso = []
    for i in range(len(rows)):
        d = distances(metric, Xs[i], Xs, sex=sex, sigma=sigma, feats=fs, emb=es, q_row=i).astype(np.float64)
        d[i] = np.inf
        iso.append(float(np.sort(d)[:k].mean()))
    out = pd.DataFrame({"id": keys["id"].to_numpy()[rows], "isolation": iso})
    return out.sort_values("isolation", ascending=False).reset_index(drop=True)
