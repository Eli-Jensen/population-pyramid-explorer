"""Percentile calibration tables (CONTRACT §3 bands, PLAN §3.4a, AMENDMENTS §B) — owner A2.

Three families of tables, all on the 24-point ``GRID`` of percentiles:

* ``same[metric][sex][year]``            random same-year COUNTRY pairs (pop ≥ 100k), per year;
* ``cross[metric][sex][era][decade]``    pairs (q in decade, c in any year allowed by ``era``);
* ``best[metric][sex][era][decade]``     ``min_y d(q, c_y)`` over random (q, c) — the time-shift null.

``metric`` may be any name ``pyramid_explorer.metrics.distances`` accepts plus ``trend@L``
(L ∈ {5, 10, 20}; rows with ``year − L < 1950`` are excluded on both sides). Distances are
computed through a ``dist_fn(metric, q_row, cand_rows, sex) -> float[n]`` so the tables can be
built (and tested) with any distance implementation; the default adapter calls B's ``metrics``.

Pair sampling is deterministic (``seed``): per table cell, ``n_pairs // 10`` query rows are drawn
without replacement and each gets ``ceil(n_pairs / n_queries)`` candidates from a different entity,
so a cell holds ≈ ``n_pairs`` random pairs at ≈ ``n_pairs / 10`` distance calls.

Binary layout (``serialize_bands``): ``uint32 LE`` byte length of a UTF-8 JSON index
``{"same/blend/2/1990": [offset, count], …}`` followed by that JSON, followed by all table values
as ``float32 LE``. ``offset`` and ``count`` are in float32 ELEMENTS from the start of the values
section (so byte offset = 4 + json_len + 4 * offset). Names are ``/``-joined dict paths. Identical
tables share one values slot (two index names → the same offset): sex-blind metrics (``w1``, ``feat``,
``visual:*``) are built once and their ``'1'`` tables alias the ``'2'`` tables, so a reader may ask for
either name.
"""
from __future__ import annotations

import json
import logging
import math
import struct
from collections.abc import Callable

import numpy as np
import pandas as pd

from pyramid_explorer.paths import N_YEARS, YEARS

log = logging.getLogger(__name__)

GRID: list[float] = [0, 1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 97, 98, 99, 99.5, 99.9, 100]
DECADES: list[int] = list(range(YEARS[0], YEARS[-1] + 1, 10))  # 1950 … 2100 (16)
ERAS: tuple[str, ...] = ("obs", "all")
SEXES: tuple[str, ...] = ("2", "1")
MINPOP = 100.0  # thousands
TREND_WINDOWS: tuple[int, ...] = (5, 10, 20)

DistFn = Callable[[str, int, np.ndarray, str], np.ndarray]


def trend_window(metric: str) -> int | None:
    """``'trend@10'`` → 10; any other metric name → None."""
    if metric.startswith("trend@"):
        return int(metric.split("@", 1)[1])
    return None


SEX_BLIND: frozenset[str] = frozenset({"w1", "feat"})


def sex_blind(metric: str) -> bool:
    """True when ``distances`` ignores ``sex`` for this metric (``w1`` and ``feat`` work on totals/features,
    ``visual:*`` on an image embedding), so its sex='1' and sex='2' tables are identical by construction."""
    return metric in SEX_BLIND or metric.startswith("visual:")


def default_dist_fn(X: np.ndarray, sigma: dict, *, keys: pd.DataFrame | None = None,
                    emb: dict[str, np.ndarray] | None = None, minpop: float = MINPOP) -> DistFn:
    """Adapter over ``pyramid_explorer.metrics.distances`` (B). The only place that touches B's API.

    ``feat`` z-scores both members against the QUERY year's country set ≥ ``minpop`` (PLAN §3.3), so
    ``keys`` is required for that metric; ``visual:<model>`` reads ``emb[model]`` (aligned with ``X``).
    """
    # lazy: B's module may be absent in unit tests (the tests inject dist_fn instead)
    from pyramid_explorer import metrics as M
    from pyramid_explorer.features import NUMERIC_FEATURES, features, zscores

    cache: dict = {}

    def year_stats(y: int) -> tuple[np.ndarray, np.ndarray]:
        if y not in cache:
            if keys is None:
                raise ValueError("metric 'feat' needs keys for the per-year reference set")
            if "feat" not in cache:
                cache["feat"] = features(X)
            ref = np.flatnonzero((keys["type"].to_numpy() == "country") & (keys["year"].to_numpy() == y)
                                 & (keys["pop_total"].to_numpy() >= minpop))
            z = zscores(cache["feat"].iloc[ref], np.arange(len(ref)))
            cache[y] = (z.attrs["mu"], z.attrs["sd"])
        return cache[y]

    def fn(metric: str, q_row: int, rows: np.ndarray, sex: str) -> np.ndarray:
        L = trend_window(metric)
        if L is not None:
            d = M.distances("trend", X[q_row], X[rows], L=L, X_prev=X[rows - L], q_prev=X[q_row - L],
                            sex=sex, sigma=sigma)
        elif metric.startswith("visual:"):
            e = (emb or {})[metric.split(":", 1)[1]]
            stacked = np.vstack([e[[q_row]], e[rows]])  # query first, so q_row=0 in the stacked space
            d = M.distances(metric, X[q_row], X[rows], sex=sex, sigma=sigma, emb=stacked, q_row=0)[1:]
        elif metric == "feat":
            mu, sd = year_stats(YEARS[0] + int(q_row) % N_YEARS)
            z = pd.DataFrame((cache["feat"].iloc[rows][NUMERIC_FEATURES].to_numpy(dtype=np.float64) - mu) / sd,
                             columns=NUMERIC_FEATURES)
            z.attrs["mu"], z.attrs["sd"] = mu, sd
            d = M.distances(metric, X[q_row], X[rows], sex=sex, sigma=sigma, feats=z)
        else:
            d = M.distances(metric, X[q_row], X[rows], sex=sex, sigma=sigma)
        return np.asarray(d, dtype=np.float64)

    return fn


def _quantiles(d: np.ndarray) -> list[float]:
    return [float(v) for v in np.percentile(np.asarray(d, dtype=np.float64), GRID)]


def _sample(rng: np.random.Generator, q_rows: np.ndarray, n_pairs: int) -> tuple[np.ndarray, int]:
    """Query rows drawn without replacement and the number of candidates each one gets."""
    n_q = max(1, min(len(q_rows), n_pairs // 10))
    return rng.choice(q_rows, n_q, replace=False), math.ceil(n_pairs / n_q)


def build_bands(X: np.ndarray, keys: pd.DataFrame, entities: list[dict], sigma: dict, metrics: list[str], *,
                seed: int = 0, n_pairs: int = 2000, current_year: int = 2026, last_observed_year: int = 2023,
                dist_fn: DistFn | None = None, emb: dict[str, np.ndarray] | None = None,
                minpop: float = MINPOP) -> dict:
    """Build the ``same`` / ``cross`` / ``best`` tables for every ``metric × sex``.

    ``entities`` is accepted for the contract signature; eligibility uses ``keys`` (``type``,
    ``pop_total``, ``year``). Cells with no eligible pair (e.g. ``trend@20`` before 1970) are omitted.
    Sex-blind metrics (:func:`sex_blind`) are computed once; their ``'1'`` entry is the same dict object as
    ``'2'`` (``serialize_bands`` then stores the values once).
    """
    if dist_fn is None:
        dist_fn = default_dist_fn(X, sigma, keys=keys, emb=emb, minpop=minpop)
    year = keys["year"].to_numpy()
    pop = keys["pop_total"].to_numpy(dtype=np.float64)
    ent = (keys["row"].to_numpy() // N_YEARS)
    ok_base = (keys["type"].to_numpy() == "country") & (pop >= minpop)
    obs_max = max(last_observed_year, current_year)
    era_mask = {"obs": year <= obs_max, "all": np.ones(len(keys), dtype=bool)}
    out: dict = {"same": {}, "cross": {}, "best": {}}

    for metric in metrics:
        L = trend_window(metric) or 0
        ok = ok_base & (year - L >= YEARS[0])
        for sex in (SEXES[:1] if sex_blind(metric) else SEXES):
            rng = np.random.default_rng(seed)  # same pairs for every metric × sex → comparable tables
            same = out["same"].setdefault(metric, {}).setdefault(sex, {})
            for y in YEARS:
                rows = np.flatnonzero(ok & (year == y))
                d = _pairs(rng, dist_fn, metric, sex, rows, rows, ent, n_pairs)
                if d is not None:
                    same[y] = _quantiles(d)
            cross = out["cross"].setdefault(metric, {}).setdefault(sex, {})
            best = out["best"].setdefault(metric, {}).setdefault(sex, {})
            for era in ERAS:
                cand = np.flatnonzero(ok & era_mask[era])
                cross[era], best[era] = {}, {}
                for dec in DECADES:
                    q_rows = np.flatnonzero(ok & (year >= dec) & (year < dec + 10))
                    d = _pairs(rng, dist_fn, metric, sex, q_rows, cand, ent, n_pairs)
                    if d is not None:
                        cross[era][dec] = _quantiles(d)
                    d = _best_pairs(rng, dist_fn, metric, sex, q_rows, cand, ent, n_pairs)
                    if d is not None:
                        best[era][dec] = _quantiles(d)
            log.info("bands %s sex=%s done", metric, sex)
        if sex_blind(metric):
            for fam in out.values():
                fam[metric][SEXES[1]] = fam[metric][SEXES[0]]  # alias, not a copy
    return out


def _pairs(rng, dist_fn, metric, sex, q_rows, cand, ent, n_pairs) -> np.ndarray | None:
    if len(q_rows) == 0 or len(cand) == 0:
        return None
    qs, m = _sample(rng, q_rows, n_pairs)
    cand_ent = ent[cand]
    out = []
    for q in qs:
        pool = cand[cand_ent != ent[q]]
        if len(pool) == 0:
            continue
        out.append(dist_fn(metric, int(q), rng.choice(pool, m), sex))
    return np.concatenate(out) if out else None


def _best_pairs(rng, dist_fn, metric, sex, q_rows, cand, ent, n_pairs) -> np.ndarray | None:
    """``min_y d(q, c_y)`` for random (q, c): one call per query over the concatenated rows of m entities."""
    if len(q_rows) == 0 or len(cand) == 0:
        return None
    cand_ent = ent[cand]
    entities = np.unique(cand_ent)
    order = np.argsort(cand_ent, kind="stable")
    cand_sorted, ent_sorted = cand[order], cand_ent[order]
    starts = np.searchsorted(ent_sorted, entities)
    ends = np.append(starts[1:], len(cand_sorted))
    qs, m = _sample(rng, q_rows, n_pairs)
    out = []
    for q in qs:
        pool = entities[entities != ent[q]]
        if len(pool) == 0:
            continue
        picks = np.searchsorted(entities, rng.choice(pool, m))
        rows = np.concatenate([cand_sorted[starts[p]:ends[p]] for p in picks])
        seg = np.cumsum([0] + [ends[p] - starts[p] for p in picks[:-1]])
        out.append(np.minimum.reduceat(dist_fn(metric, int(q), rows, sex), seg))
    return np.concatenate(out) if out else None


# ---------------------------------------------------------------------------------------------- serialisation
def flatten_bands(bands: dict) -> dict[str, list[float]]:
    """Nested tables → ``{"same/blend/2/1990": [24 floats], …}`` in sorted name order."""
    flat: dict[str, list[float]] = {}

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k)])
        else:
            flat["/".join(path)] = [float(v) for v in node]

    walk(bands, [])
    return dict(sorted(flat.items()))


def serialize_bands(bands: dict) -> bytes:
    """uint32 LE json-index length + JSON ``{name: [offset, count]}`` + float32 LE values.
    Tables with identical values (the sex-blind aliases) are stored once and indexed twice."""
    flat = flatten_bands(bands)
    index, values, off, seen = {}, [], 0, {}
    for name, vals in flat.items():
        key = tuple(np.asarray(vals, dtype="<f4").tolist())
        if key in seen:
            index[name] = [seen[key], len(vals)]
            continue
        seen[key] = off
        index[name] = [off, len(vals)]
        values.extend(vals)
        off += len(vals)
    js = json.dumps(index, separators=(",", ":")).encode("utf-8")
    return struct.pack("<I", len(js)) + js + np.asarray(values, dtype="<f4").tobytes()


def deserialize_bands(buf: bytes) -> dict[str, np.ndarray]:
    """Inverse of :func:`serialize_bands` (flat names → float32 arrays); the web reader's twin."""
    (n,) = struct.unpack_from("<I", buf, 0)
    index = json.loads(buf[4:4 + n].decode("utf-8"))
    values = np.frombuffer(buf, dtype="<f4", offset=4 + n)
    return {name: values[off:off + cnt] for name, (off, cnt) in index.items()}


def default_subset(bands: dict, metric: str = "blend", sex: str = "2") -> dict:
    """The first-paint table: ``same[metric][sex]`` only (→ ``bands_default.{sha8}.bin``)."""
    table = bands.get("same", {}).get(metric, {}).get(sex, {})
    return {"same": {metric: {sex: table}}} if table else {}


def band_label(d: float, quantiles: list[float]) -> str:
    """'very_close' ≤ p5 · 'close' ≤ p25 · 'typical' · 'far' ≥ p75 · 'extreme' ≥ p95 (on ``GRID``)."""
    if len(quantiles) != len(GRID):
        raise ValueError(f"expected {len(GRID)} quantiles, got {len(quantiles)}")
    p = {g: quantiles[GRID.index(g)] for g in (5, 25, 75, 95)}
    if d >= p[95]:
        return "extreme"
    if d >= p[75]:
        return "far"
    if d <= p[5]:
        return "very_close"
    if d <= p[25]:
        return "close"
    return "typical"
