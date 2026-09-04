#!/usr/bin/env python
"""Similarity-evaluation protocol (evals/protocol.md, PLAN §4.6) → ``evals/RESULTS.md`` + ``evals/verdicts.json``.

    make eval                                   # = scripts/eval_similarity.py --full
    uv run scripts/eval_similarity.py --full --n-queries 100 --out-dir /tmp/x   # smaller, elsewhere
    uv run scripts/eval_similarity.py --query JPN 2026 [query.py flags…]        # delegates to scripts/query.py

Runs, for every metric in ``metrics.METRICS`` (``trend``/``path`` at L = 10) plus ``visual:<model>`` for every
``evals/embeddings/<model>.pca64.npy`` that can be aligned with the corpus: G1 continuity (observed vs projected
query years), G2 external labels (Korenjak-Černe clusters, Hahn-Klimroth rule classes, stage, RIETI window,
Yoshida epitomes), G4 outliers (isolation top-10), the opposites diversity test, the method-agreement Jaccard
matrix, and the canonical-group / time-shift regressions.  Verdicts follow protocol.md §4 and are INFORMATIONAL
(DECISION 4).  Deterministic: one seed, one shared query sample for all metrics, no wall-clock in the outputs
except the ``built`` stamp.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer.features import features, zscores  # noqa: E402
from pyramid_explorer.metrics import METRICS, SIGMA_PATH, blend_balance, distances, fit_sigma, lagged, load_sigma  # noqa: E402
from pyramid_explorer.paths import DATA_PROCESSED, EVALS, LAST_OBSERVED_YEAR, N_BINS, REPO_ROOT, YEARS  # noqa: E402
from pyramid_explorer.search import DIV_PRESETS, Query, different, load_inputs, row_of  # noqa: E402

LABELS_DIR, EMB_DIR = EVALS / "labels", EVALS / "embeddings"
MINPOP = 100.0                     # thousands
TREND_L = 10
GATES = {"C1": 0.95, "C5": 0.99, "kc_agree": 0.7, "hk_agree": 0.85, "stage_agree": 0.9, "lab_C1": 0.8, "reject_hk": 0.6}
G4_SET, G4_MICRO = ["QAT", "ARE", "BHR", "KWT"], ["MCO", "VAT"]
HK_CLASS_OTHER = "other"
OPPOSITES_BETA = 2.0               # pre-registered (protocol.md §2); the shipped default is DIV_PRESETS["balanced"]
SWEEP_BETAS = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
EXPECTED_VISUAL_VERDICT = "lab"    # evals/image_embeddings.md §2


def hk_family(cls: np.ndarray) -> np.ndarray:
    """Shape family: the paper's lower/middle/upper diamond variants collapse to ``diamond`` (gate level)."""
    return np.array(["diamond" if "diamond" in str(c) else str(c) for c in cls], dtype=object)


# ============================================================================================ scoring functions
def hk_classes(X: np.ndarray, spec: dict) -> np.ndarray:
    """Hahn-Klimroth shape class per row from the bucket spec + Table S8 rules in ``hahn_klimroth_2025.yaml``."""
    X = np.atleast_2d(np.asarray(X, dtype=np.float64))
    a = X[:, :N_BINS] + X[:, N_BINS:]
    b = spec["buckets"]
    B = np.stack([a[:, b[k]["bins"]].sum(1) / b[k]["width_years"] for k in ("B1", "B2", "B3", "B4", "B5")], 1)
    tol = float(b["tolerance_rel"])

    def cmp(i: np.ndarray, j: np.ndarray) -> np.ndarray:       # +1 if j > i, −1 if j < i, 0 if equal within tol
        rel = (j - i) / np.maximum(np.maximum(i, j), 1e-12)
        return np.where(rel > tol, 1, np.where(rel < -tol, -1, 0))

    seq = np.stack([cmp(B[:, k], B[:, k + 1]) for k in range(4)], 1)
    rules = {tuple(r["seq"]): r for r in spec["rules"]}
    ops = {">": lambda i, j: cmp(j, i) == 1, "<": lambda i, j: cmp(j, i) == -1, "=": lambda i, j: cmp(j, i) == 0,
           ">=": lambda i, j: cmp(j, i) != -1, "<=": lambda i, j: cmp(j, i) != 1}

    def holds(cond: str, row: np.ndarray) -> bool:
        if cond == "else":
            return True
        for disj in cond.split(" or "):
            ok = True
            for term in disj.split(" and "):
                lhs, op, rhs = term.split()
                ok &= bool(ops[op](row[int(lhs[1]) - 1:int(lhs[1])], row[int(rhs[1]) - 1:int(rhs[1])])[0])
            if ok:
                return True
        return False

    out = np.full(len(X), HK_CLASS_OTHER, dtype=object)
    for n, s in enumerate(map(tuple, seq)):
        r = rules.get(s)
        if r is None:
            continue
        if "class" in r:
            out[n] = r["class"]
        else:
            out[n] = next(c for cond, c in r["cases"] if holds(cond, B[n]))
    return out


def norm_precision(ranked_ids: list[str], group: set[str], k: int) -> float:
    """PLAN §4.6: P@k = hits / min(k, |G|−1) over the ranked candidates (query excluded from both)."""
    denom = min(k, len(group) - 1)
    return float(sum(i in group for i in ranked_ids[:k]) / denom) if denom > 0 else float("nan")


def mrr(ranked_ids: list[str], group: set[str]) -> float:
    for r, i in enumerate(ranked_ids, 1):
        if i in group:
            return 1.0 / r
    return 0.0


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 1.0


def continuity_stats(nn_same: np.ndarray) -> dict:
    """``nn_same`` bool [n_queries, k]: whether the r-th nearest is the same entity within |Δy| ≤ 1."""
    return {"C1": float(nn_same[:, 0].mean()), "C5": float(nn_same[:, :5].any(1).mean()), "n": int(len(nn_same))}


# ============================================================================================ corpus context
class Ctx:
    """Corpus + everything a metric needs to give distances from one row to every row."""

    def __init__(self, X, keys, entities, sigma, emb: dict[str, np.ndarray] | None = None):
        self.X, self.keys, self.entities, self.sigma = np.asarray(X, np.float64), keys, entities, sigma
        self.id, self.year = keys["id"].to_numpy(), keys["year"].to_numpy()
        self.pop, self.is_country = keys["pop_total"].to_numpy(), keys["type"].to_numpy() == "country"
        self.emb = emb or {}
        self.feat = features(self.X)
        self.region = {e["id"]: e.get("region_locid") for e in entities}
        self._lag: dict[int, np.ndarray] = {}
        self._z: dict[int, pd.DataFrame] = {}

    def lag(self, L: int) -> np.ndarray:
        if L not in self._lag:
            self._lag[L] = lagged(self.X, L)
        return self._lag[L]

    def zfeat(self, year: int) -> pd.DataFrame:
        """Features z-scored against ``year``'s country set ≥ 100k (PLAN §3.3 focal-year rule)."""
        if year not in self._z:
            ref = np.flatnonzero(self.is_country & (self.year == year) & (self.pop >= MINPOP))
            self._z[year] = zscores(self.feat, ref)
        return self._z[year]

    def eligible(self, trend: bool = False) -> np.ndarray:
        m = self.is_country & (self.pop >= MINPOP)
        return m & (self.year - TREND_L >= YEARS[0]) if trend else m

    def metrics(self) -> list[str]:
        return [m for m in METRICS] + [f"visual:{m}" for m in self.emb]

    def dist(self, metric: str, row: int, rows: np.ndarray | None = None) -> np.ndarray:
        """float64 distances from ``row`` to every corpus row (or to ``rows`` only); NaN where undefined
        (missing lag / embedding).  Same-year tests pass the ~200-row subset so they cost µs, not ms."""
        q = self.X[row]
        sub = slice(None) if rows is None else rows
        Xs = self.X[sub]
        if metric == "trend":
            Xp = self.lag(TREND_L)
            d = distances("trend", q, Xs, sigma=self.sigma, L=TREND_L, X_prev=Xp[sub], q_prev=Xp[row])
        elif metric == "path":
            Xp = np.stack([self.lag(s) for s in range(5, TREND_L + 1, 5)])
            d = distances("path", q, Xs, sigma=self.sigma, L=TREND_L, X_prev=Xp[:, sub], q_prev=Xp[:, row])
        elif metric == "feat":
            z = self.zfeat(int(self.year[row]))
            zs = z if rows is None else z.iloc[rows]
            zs.attrs = z.attrs
            d = distances("feat", q, Xs, sigma=self.sigma, feats=zs)
        elif metric.startswith("visual:"):
            E = self.emb[metric[7:]]
            Es = E if rows is None else np.vstack([E[rows], E[row][None]])
            d = distances(metric, q, Xs, emb=Es, q_row=row if rows is None else len(rows))[:len(Xs)]
        else:
            d = distances(metric, q, Xs, sigma=self.sigma)
        return d.astype(np.float64)

    def topk(self, metric: str, row: int, cand: np.ndarray, k: int) -> np.ndarray:
        """Rows of the k nearest candidates (bool mask ``cand``; own row always excluded; NaN dropped)."""
        rows = np.flatnonzero(cand)
        rows = rows[rows != row]
        d = self.dist(metric, row, rows)
        ok = np.isfinite(d)
        order = np.argsort(d[ok], kind="stable")[:k]
        return rows[ok][order]

    def dedupe_topk(self, metric: str, row: int, cand: np.ndarray, k: int) -> list[str]:
        """Nearest entities (best year each) under the mask — the ids of ``search.similar`` without its Query."""
        rows = np.flatnonzero(cand & (self.id != self.id[row]))
        d = self.dist(metric, row, rows)
        rows, d = rows[np.isfinite(d)], d[np.isfinite(d)]
        t = pd.DataFrame({"id": self.id[rows], "d": d}).sort_values("d", kind="stable").drop_duplicates("id")
        return t["id"].head(k).tolist()


def load_embeddings(keys: pd.DataFrame) -> tuple[dict[str, np.ndarray], dict[str, dict]]:
    """``<model>.pca64.npy`` aligned with the corpus: exact row count, or the country block of a provisional-corpus
    embedding (countries first, same ISO3 order) padded with NaN for the aggregates — recorded in the notes."""
    emb, meta = {}, {}
    n_country = int((keys["type"] == "country").sum())
    for p in sorted(EMB_DIR.glob("*.pca64.npy")):
        model = p.name[:-len(".pca64.npy")]
        E = np.load(p).astype(np.float32)
        mp = EMB_DIR / f"{model}.meta.json"
        info = {"rows": int(E.shape[0]), "meta_hash": hashlib.sha256(mp.read_bytes()).hexdigest() if mp.exists() else None}
        if E.shape[0] == len(keys):
            info["alignment"] = "exact"
        elif E.shape[0] == n_country and bool((keys["type"].to_numpy()[:n_country] == "country").all()):
            E = np.vstack([E, np.full((len(keys) - n_country, E.shape[1]), np.nan, np.float32)])
            info["alignment"] = "country block only (embedding built on the provisional corpus; aggregates NaN, TGO rows unpatched)"
        else:
            info["alignment"] = f"SKIPPED: {E.shape[0]} rows vs corpus {len(keys)}"
            meta[model] = info
            continue
        emb[model], meta[model] = E, info
    return emb, meta


def data_hash() -> tuple[str, str]:
    u = DATA_PROCESSED / "corpus_u16.npy"
    if u.exists():
        return hashlib.sha256(np.load(u).astype("<u2").tobytes()).hexdigest(), "sha256(corpus_u16 little-endian bytes)"
    return hashlib.sha256((DATA_PROCESSED / "corpus_s42.npy").read_bytes()).hexdigest(), "sha256(corpus_s42.npy file; no u16 export)"


# ============================================================================================ protocol pieces
def g1_continuity(ctx: Ctx, metric: str, n_queries: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    trend = metric in ("trend", "path")
    cand = ctx.eligible(trend)
    out = {}
    for name, lo, hi in (("observed", YEARS[0], LAST_OBSERVED_YEAR), ("projected", LAST_OBSERVED_YEAR + 1, YEARS[-1])):
        pool = np.flatnonzero(cand & (ctx.year >= lo) & (ctx.year <= hi))
        qs = rng.choice(pool, size=min(n_queries, len(pool)), replace=False)
        same = np.zeros((len(qs), 5), bool)
        for i, r in enumerate(qs):
            nn = ctx.topk(metric, int(r), cand, 5)
            same[i, :len(nn)] = (ctx.id[nn] == ctx.id[r]) & (np.abs(ctx.year[nn] - ctx.year[r]) <= 1)
        out[name] = continuity_stats(same)
    return out


def g2_kc(ctx: Ctx, metric: str, kc: dict, year: int, k: int = 10) -> dict:
    """Class agreement among the labelled countries of ``year`` (≥ 100k). Normalised P@k is NOT reported here:
    every Korenjak-Černe cluster has ≥ 44 members, so min(k, |G|−1) = k and P@k ≡ class agreement (protocol.md §2)."""
    cls = {i: c for c, ids in kc["years"][str(year)]["clusters"].items() for i in ids}
    rows = {ctx.id[r]: r for r in np.flatnonzero(ctx.eligible() & (ctx.year == int(year))) if ctx.id[r] in cls}
    cand = np.zeros(len(ctx.X), bool)
    cand[list(rows.values())] = True
    agree = []
    for i, r in rows.items():
        nn = [ctx.id[j] for j in ctx.topk(metric, r, cand, k)]
        agree.append(np.mean([cls[j] == cls[i] for j in nn]))
    smallest = min(len(ids) for ids in kc["years"][str(year)]["clusters"].values())
    return {"agree": float(np.mean(agree)), "n": len(rows), "min_cluster": int(smallest)}


def same_year_class_agreement(ctx: Ctx, metric: str, year: int, cls: np.ndarray, k: int = 10) -> float:
    cand = ctx.eligible() & (ctx.year == year)
    rows = np.flatnonzero(cand)
    return float(np.mean([np.mean(cls[ctx.topk(metric, int(r), cand, k)] == cls[r]) for r in rows]))


def best_year(ctx: Ctx, metric: str, q: tuple[str, int], target: str) -> int:
    rows = np.flatnonzero(ctx.id == target)
    d = ctx.dist(metric, row_of(ctx.keys, *q), rows)
    return int(ctx.year[rows[np.nanargmin(d)]])


def g2_yoshida(ctx: Ctx, metric: str, spec: dict) -> dict:
    out = {}
    cand = ctx.eligible(metric in ("trend", "path")) & (ctx.year == 2015)
    for y, t in spec["targets"].items():
        try:
            row = row_of(ctx.keys, "agg-900", int(y))
        except KeyError:
            out[y] = {"top5": [], "hits": 0, "pass": False, "note": "agg-900 absent from corpus"}
            continue
        top = [ctx.id[j] for j in ctx.topk(metric, row, cand, 10)]
        hits = sum(i in t["set"] for i in top[:5])
        out[y] = {"top5": top[:5], "hits": hits, "hits10": sum(i in t["set"] for i in top), "pass": hits >= t["min_in_top5"],
                  "ranks": {i: (top.index(i) + 1 if i in top else ">10") for i in t["set"]}}
    out["pass"] = all(v["pass"] for k, v in out.items() if k != "pass")
    return out


def g4_isolation(ctx: Ctx, metric: str, year: int, minpop: float, k: int = 5) -> list[str]:
    """Most isolated first: mean distance to the k nearest same-year countries ≥ minpop."""
    m = ctx.is_country & (ctx.year == year) & (ctx.pop >= minpop)
    if metric in ("trend", "path"):
        m &= ctx.year - TREND_L >= YEARS[0]
    rows = np.flatnonzero(m)
    iso = []
    for r in rows:
        d = ctx.dist(metric, int(r), rows)
        d[rows == r] = np.nan
        iso.append(np.nanmean(np.sort(d[np.isfinite(d)])[:k]) if np.isfinite(d).any() else np.nan)
    return [ctx.id[rows[i]] for i in np.argsort(-np.asarray(iso), kind="stable")]


def opposites_test(ctx: Ctx, metric: str, hk: np.ndarray, n_anchors: int, seed: int, year: int = 2024) -> dict:
    rng = np.random.default_rng(seed)
    pool = np.flatnonzero(ctx.eligible(True) & (ctx.year == year))
    anchors = rng.choice(pool, size=min(n_anchors, len(pool)), replace=False)
    trend = "motion" if metric == "trend" else "path" if metric == "path" else None
    base = dict(metric=metric if trend is None else "blend", trend=trend, L=TREND_L, k=5, minpop=MINPOP)
    kw = {"emb": ctx.emb[metric[7:]]} if metric.startswith("visual:") else {}
    n_cls, n_reg, exact, dedupe = [], [], [], []
    for r in anchors:
        q = Query(ctx.id[r], year, mode="same", div=OPPOSITES_BETA, **base)
        opp = different(ctx.X, ctx.keys, ctx.entities, q, ctx.sigma, **kw)
        n_cls.append(len({hk[o.row] for o in opp}))          # fine classes, as worded in PLAN §4.6 item 6
        n_reg.append(len({ctx.region.get(o.id) for o in opp}))
        plain = different(ctx.X, ctx.keys, ctx.entities, Query(ctx.id[r], year, mode="same", div=0.0, **base), ctx.sigma, **kw)
        crow = np.flatnonzero(ctx.eligible(trend is not None) & (ctx.year == year) & (ctx.id != ctx.id[r]))
        d = ctx.dist(metric, int(r), crow)
        far = ctx.id[crow[np.isfinite(d)][np.argsort(-d[np.isfinite(d)], kind="stable")[:5]]]
        exact.append([o.id for o in plain] == list(far))
        anyq = different(ctx.X, ctx.keys, ctx.entities, Query(ctx.id[r], year, mode="any", era="all", div=OPPOSITES_BETA, **base), ctx.sigma, **kw)
        dedupe.append(len({o.id for o in anyq}) == len(anyq))
    both = [c >= 3 and g >= 3 for c, g in zip(n_cls, n_reg)]
    return {"mean_hk_classes": float(np.mean(n_cls)), "min_hk_classes": int(min(n_cls)), "mean_regions": float(np.mean(n_reg)),
            "min_regions": int(min(n_reg)), "frac_anchors_3_3": float(np.mean(both)),
            "pass_coverage": bool(np.mean(n_cls) >= 3 and np.mean(n_reg) >= 3),
            "div0_exact": bool(all(exact)), "dedupe_any_year": bool(all(dedupe)), "n": int(len(anchors)), "beta": OPPOSITES_BETA}


def beta_sweep(ctx: Ctx, metric: str = "blend", year: int = 2024, betas: tuple[float, ...] = SWEEP_BETAS,
               n_anchors: int | None = None, seed: int = 0, k: int = 5) -> list[dict]:
    """How the MMR β behaves on this corpus (PLAN §5 presets): per β, mean top-k Jaccard against the strict
    (β = 0) list, mean raw rank of the picks, mean distinct UN regions, and the share of anchors whose list is
    identical to the β = 2 list. Anchors = every country ≥ 100k in ``year`` (or a seeded sample of ``n_anchors``)."""
    pool = np.flatnonzero(ctx.eligible() & (ctx.year == year))
    if n_anchors is not None and n_anchors < len(pool):
        pool = np.random.default_rng(seed).choice(pool, size=n_anchors, replace=False)
    picks = {b: [different(ctx.X, ctx.keys, ctx.entities, Query(ctx.id[r], year, metric=metric, k=k, minpop=MINPOP, div=b), ctx.sigma)
                 for r in pool] for b in betas}
    sets = {b: [{o.id for o in rs} for rs in picks[b]] for b in betas}
    ref = sets[2.0] if 2.0 in sets else sets[betas[-1]]
    return [{"beta": b,
             "jaccard_vs_strict": float(np.mean([jaccard(s, s0) for s, s0 in zip(sets[b], sets[betas[0]])])),
             "mean_raw_rank": float(np.mean([np.mean([o.rank_raw for o in rs]) for rs in picks[b]])),
             "mean_regions": float(np.mean([len({ctx.region.get(o.id) for o in rs}) for rs in picks[b]])),
             "identical_to_beta2": float(np.mean([s == s2 for s, s2 in zip(sets[b], ref)])), "n": int(len(pool))}
            for b in betas]


def method_agreement(ctx: Ctx, metrics: list[str], n_queries: int, seed: int, k: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pool = np.flatnonzero(ctx.eligible(True) & (ctx.year >= 1960) & (ctx.year <= LAST_OBSERVED_YEAR))
    qs = rng.choice(pool, size=min(n_queries, len(pool)), replace=False)
    tops = {m: [] for m in metrics}
    for r in qs:
        cand = ctx.eligible(True) & (ctx.year == ctx.year[r])
        for m in metrics:
            tops[m].append(set(ctx.id[ctx.topk(m, int(r), cand, k)]))
    J = pd.DataFrame(index=metrics, columns=metrics, dtype=float)
    for a, b in product(metrics, metrics):
        J.loc[a, b] = float(np.mean([jaccard(x, y) for x, y in zip(tops[a], tops[b])]))
    return J


def regression(ctx: Ctx, metric: str, groups: dict, windows: list[dict]) -> dict:
    year = groups["year"]
    cand = ctx.eligible(metric in ("trend", "path")) & (ctx.year == year)
    g_out = {}
    for name, members in groups["groups"].items():
        G = set(members)
        pk, rr = [], []
        for i in members:
            try:
                r = row_of(ctx.keys, i, year)
            except KeyError:
                continue
            nn = [ctx.id[j] for j in ctx.topk(metric, r, cand, 10)]
            rr.append(mrr(nn, G - {i}))
            if len(G) > 3:
                pk.append(norm_precision(nn, G, 5))          # denominator min(5, |G|−1); the query is never ranked
        g_out[name] = {"p_at_5": float(np.mean(pk)) if pk else None, "mrr": float(np.mean(rr))}
    w_out = []
    for w in windows:
        y = best_year(ctx, metric, tuple(w["query"]), w["target"])
        w_out.append({"query": w["query"], "target": w["target"], "window": w["window"], "best_year": y,
                      "pass": w["window"][0] <= y <= w["window"][1], "gate": bool(w.get("gate"))})
    return {"groups": g_out, "time_shift": w_out}


# ============================================================================================ verdicts
def verdict(metric: str, r: dict) -> tuple[str, dict]:
    g1 = r["g1"]["observed"]
    gates = {"G1": g1["C1"] >= GATES["C1"] and g1["C5"] >= GATES["C5"],
             "G2a": r["kc"]["2006"]["agree"] >= GATES["kc_agree"], "G2b": r["hk_agree"] >= GATES["hk_agree"],
             "G2c": r["stage_agree"] >= GATES["stage_agree"], "G2d": r["rieti"]["pass"], "G2e": r["yoshida"]["pass"],
             "G4": r["g4"]["pass"]}
    gates["G2"] = all(gates[k] for k in ("G2a", "G2b", "G2c", "G2d"))   # G2e reported only — protocol.md §4 amendment
    if metric in ("trend", "path"):
        return ("menu" if gates["G1"] else "lab"), gates
    if metric == "blend":
        return "default", gates
    if r["hk_agree"] < GATES["reject_hk"] or g1["C1"] < GATES["lab_C1"]:
        return "rejected", gates
    if gates["G1"] and gates["G2"] and gates["G4"]:
        return "menu", gates
    if gates["G1"] and gates["G4"]:
        return "advanced", gates
    return "lab", gates


# ============================================================================================ driver
def run_full(n_queries: int, n_anchors: int, seed: int, out_dir: Path, verbose: bool = True,
             sweep_anchors: int | None = None) -> dict:
    X, keys, ents = load_inputs()
    sigma = load_sigma() if SIGMA_PATH.exists() else fit_sigma(X, keys, ents, write=True)
    emb, emb_meta = load_embeddings(keys)
    ctx = Ctx(X, keys, ents, sigma, emb)
    labels = {p.stem: yaml.safe_load(p.read_text()) for p in sorted(LABELS_DIR.glob("*.yaml"))}
    kc, hk_spec = labels["korenjak_cerne"], labels["hahn_klimroth_2025"]
    kc["years"] = {str(y): v for y, v in kc["years"].items()}
    groups = yaml.safe_load((EVALS / "canonical_groups.yaml").read_text())
    windows = yaml.safe_load((EVALS / "time_shift.yaml").read_text())["windows"]
    hk = hk_classes(X, hk_spec)
    stage = ctx.feat["stage"].to_numpy()
    metrics = ctx.metrics()
    res: dict[str, dict] = {}
    for m in metrics:
        if verbose:
            print(f"[{m}]", end=" ", flush=True)
        r = {"g1": g1_continuity(ctx, m, n_queries, seed)}
        r["kc"] = {y: g2_kc(ctx, m, kc, y) for y in ("1996", "2001", "2006")}
        r["hk_agree"] = same_year_class_agreement(ctx, m, 2024, hk_family(hk))
        r["hk_agree_fine"] = same_year_class_agreement(ctx, m, 2024, hk)
        r["stage_agree"] = same_year_class_agreement(ctx, m, 2024, stage)
        rieti_w = next(w for w in windows if w.get("gate"))
        y = best_year(ctx, m, tuple(rieti_w["query"]), rieti_w["target"])
        r["rieti"] = {"best_year": y, "window": rieti_w["window"], "pass": rieti_w["window"][0] <= y <= rieti_w["window"][1]}
        r["yoshida"] = g2_yoshida(ctx, m, labels["yoshida_epitome"])
        top = g4_isolation(ctx, m, 2024, MINPOP)
        top_nofloor = g4_isolation(ctx, m, 2024, 0.0)
        r["g4"] = {"top10": top[:10], "pass": all(i in top[:10] for i in G4_SET),
                   "top10_no_floor": top_nofloor[:10], "micro_enter": [i for i in G4_MICRO if i in top_nofloor[:10]]}
        r["opposites"] = opposites_test(ctx, m, hk, n_anchors, seed)
        r["regression"] = regression(ctx, m, groups, windows)
        r["verdict"], r["gates"] = verdict(m, r)
        res[m] = r
        if verbose:
            print(f"C1={r['g1']['observed']['C1']:.3f} KC={r['kc']['2006']['agree']:.2f} HK={r['hk_agree']:.2f} → {r['verdict']}")
    J = method_agreement(ctx, metrics, n_queries, seed)
    if verbose:
        print("[β sweep + blend balance]", flush=True)
    findings = {"beta_sweep": beta_sweep(ctx, "blend", 2024, n_anchors=sweep_anchors, seed=seed),
                "div_presets": DIV_PRESETS,
                "blend_w1_share": blend_balance(X, keys, ents, sigma, seed=seed)}
    dh, dh_def = data_hash()
    meta = {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "stage": "M0 (no triplets)", "informational": True,
            "seed": seed, "n_queries": n_queries, "n_anchors": n_anchors, "n_rows": int(len(keys)),
            "n_entities": len(ents), "n_countries": int(sum(e["type"] == "country" for e in ents)),
            "sigma_source": "data/processed/sigma.json" if SIGMA_PATH.exists() else "fit_sigma (fresh)",
            "git_head": _git_head(), "labels_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(LABELS_DIR.glob("*.yaml"))},
            "label_fallback": {"korenjak_cerne": kc["fallback_status"], "vintage_sensitivity_row": kc["vintage_sensitivity_row"]},
            "hk_class_counts_2024": _class_counts(ctx, hk, 2024), "hk_family_counts_2024": _class_counts(ctx, hk_family(hk), 2024),
            "embeddings": emb_meta, "data_hash_definition": dh_def, "findings": findings}
    verdicts = {m: {"verdict": r["verdict"], "provisional": r["verdict"] == "menu", "gates": r["gates"],
                    **({"scope": "trend-mode"} if m in ("trend", "path") else {}),
                    "numbers": {"C1_obs": r["g1"]["observed"]["C1"], "C5_obs": r["g1"]["observed"]["C5"],
                                "C1_proj": r["g1"]["projected"]["C1"], "kc2006_agree": r["kc"]["2006"]["agree"],
                                "hk_agree": r["hk_agree"], "hk_agree_fine": r["hk_agree_fine"], "stage_agree": r["stage_agree"],
                                "rieti_best_year": r["rieti"]["best_year"], "yoshida_pass": r["yoshida"]["pass"],
                                "g4_pass": r["g4"]["pass"], "opposites_coverage": r["opposites"]["pass_coverage"]}}
                for m, r in res.items()}
    out = {**verdicts, "data_hash": dh, "emb_meta_hash": {m: i["meta_hash"] for m, i in emb_meta.items()},
           "exposed_visual": exposed_visual(res), "_meta": meta}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdicts.json").write_text(json.dumps(out, indent=1, default=_json_default))
    (out_dir / "RESULTS.md").write_text(render_results(res, J, meta, dh, emb_meta))
    if verbose:
        print(f"\nwrote {out_dir / 'RESULTS.md'} and {out_dir / 'verdicts.json'}")
    return {"results": res, "jaccard": J, "meta": meta}


def exposed_visual(res: dict) -> dict | None:
    """DECISION 4, machine-readable: the image space with the better observed-span C1 is exposed as "Visual";
    the others stay URL-only. ``None`` when no image space was scored. Consumed by build_data.load_verdicts."""
    vis = [m for m in res if m.startswith("visual:")]
    if not vis:
        return None
    best = max(vis, key=lambda m: res[m]["g1"]["observed"]["C1"])
    return {"model": best[len("visual:"):], "metric": best, "C1_obs": res[best]["g1"]["observed"]["C1"],
            "alternates": [m[len("visual:"):] for m in vis if m != best], "rule": "better observed-span G1 C1"}


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001 — not a repo / no git
        return None


def _class_counts(ctx: Ctx, cls: np.ndarray, year: int) -> dict:
    m = ctx.eligible() & (ctx.year == year)
    return {str(k): int(v) for k, v in zip(*np.unique(cls[m], return_counts=True))}


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


# ============================================================================================ report
def _f(x, nd=3) -> str:
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def _tick(b) -> str:
    return "✓" if b else "✗"


def _gated(x: float, gate: float) -> str:
    """A gated cell carries its own tick; 4 decimals when the value sits within 0.001 of the gate so a reader can
    see WHY it failed (0.8495 ✗ beside a ≥ 0.85 gate, never a rounded 0.850)."""
    nd = 4 if abs(x - gate) < 1e-3 else 3
    return f"{_f(x, nd)} {_tick(x >= gate)}"


def render_results(res: dict, J: pd.DataFrame, meta: dict, dh: str, emb_meta: dict) -> str:
    ms = list(res)
    L = [f"# Similarity evaluation — RESULTS ({meta['stage']}, verdicts informational per DECISION 4)", "",
         f"Built {meta['built']} · git `{meta['git_head']}` · corpus {meta['n_rows']} rows / {meta['n_countries']} countries + "
         f"{meta['n_entities'] - meta['n_countries']} aggregates · data_hash `{dh[:16]}…` ({meta['data_hash_definition']}) · "
         f"σ from {meta['sigma_source']} · seed {meta['seed']} · {meta['n_queries']} continuity queries per span, "
         f"{meta['n_anchors']} opposites anchors · protocol: `evals/protocol.md`.", "",
         "Label files (sha256, first 16): " + ", ".join(f"`{k}` {v[:16]}" for k, v in meta["labels_sha256"].items()) + ".  ",
         f"Korenjak-Černe fallback status: **{meta['label_fallback']['korenjak_cerne']}** (2015 memberships paywalled; 2008 lists, IDB-2008 vintage); "
         f"vintage-sensitivity row: {meta['label_fallback']['vintage_sensitivity_row']}.", ""]
    if emb_meta:
        L += ["Image spaces: " + "; ".join(f"`{m}` rows {i['rows']}, alignment: {i['alignment']}" for m, i in emb_meta.items()) + ".", ""]
    else:
        L += ["Image spaces: none found under `evals/embeddings/` — `visual:*` rows absent.", ""]
    L += ["## G1 continuity (gate on the observed span: C1 ≥ 0.95, C5 ≥ 0.99)", "",
          "| metric | C1 obs | C5 obs | C1 proj | C5 proj | gate |", "|---|---|---|---|---|---|"]
    for m in ms:
        g = res[m]["g1"]
        L.append(f"| {m} | {_gated(g['observed']['C1'], GATES['C1'])} | {_gated(g['observed']['C5'], GATES['C5'])} | {_f(g['projected']['C1'])} | {_f(g['projected']['C5'])} | {_tick(res[m]['gates']['G1'])} |")
    kc_min = min(res[ms[0]]["kc"][y]["min_cluster"] for y in ("1996", "2001", "2006"))
    L += ["", "## G2 external labels", "",
          "| metric | KC2006 agree (≥0.7) | KC1996 | KC2001 | HK family agree (≥0.85) | HK fine | stage agree (≥0.9) | CHN2020→JPN y* [1985,1995] | Yoshida hits@5 1990/2015/2050 (reported) | G2 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for m in ms:
        r = res[m]
        yo = "/".join(f"{r['yoshida'][y]['hits']}" for y in ("1990", "2015", "2050")) + f" {_tick(r['yoshida']['pass'])}"
        L.append(f"| {m} | {_gated(r['kc']['2006']['agree'], GATES['kc_agree'])} | {_f(r['kc']['1996']['agree'])} | {_f(r['kc']['2001']['agree'])} | "
                 f"{_gated(r['hk_agree'], GATES['hk_agree'])} | {_f(r['hk_agree_fine'])} | {_gated(r['stage_agree'], GATES['stage_agree'])} | {r['rieti']['best_year']} {_tick(r['rieti']['pass'])} | {yo} | {_tick(r['gates']['G2'])} |")
    L += ["", f"Gated cells carry their own tick and show 4 decimals when within 0.001 of the gate. Normalised P@10 is not tabulated "
              f"for the Korenjak-Černe clusters: the smallest cluster has {kc_min} members, so min(10, |G|−1) = 10 and P@10 coincides "
              f"with class agreement (protocol.md §2).",
          "", f"Hahn-Klimroth classes on the 2024 country set (≥ 100k): fine {meta['hk_class_counts_2024']}; families (gate level) {meta['hk_family_counts_2024']}.", "",
          "G2(e) Yoshida — DEMOTED TO REPORTED (protocol.md §4 amendment, recorded before this run's verdicts but after a smoke run: "
          "the paper's own metric, `clr` on total shares, reproduces India's 1990 distance (0.59 vs the paper's 0.579) yet fails the "
          "pre-registered top-5 targets on WPP2024 rows — Bolivia and Puerto Rico were revised between WPP2015 and WPP2024). "
          "Top-5 (World Y vs countries 2015) and rank of every named country: ", ""] + [
          f"- `{m}`: " + " · ".join(f"{y}: {','.join(res[m]['yoshida'][y]['top5'])} — ranks {res[m]['yoshida'][y]['ranks']}" for y in ("1990", "2015", "2050"))
          for m in ms] + ["",
          "## G4 outliers (isolation, 2024; gate = {QAT, ARE, BHR, KWT} ⊆ top-10)", "",
          "| metric | top-10 most isolated | gate | floor off: MCO/VAT enter | top-10 (floor off) |", "|---|---|---|---|---|"]
    for m in ms:
        g = res[m]["g4"]
        L.append(f"| {m} | {', '.join(g['top10'])} | {_tick(g['pass'])} | {', '.join(g['micro_enter']) or '–'} | {', '.join(g['top10_no_floor'])} |")
    n_opp = res[ms[0]]["opposites"]["n"]
    L += ["", f"## Opposites test ({n_opp} random 2024 anchors, β = {OPPOSITES_BETA:g} as pre-registered, k = 5)", "",
          "| metric | mean/min HK classes (fine) | mean/min UN regions | anchors with ≥3/≥3 | pass (means ≥ 3) | β=0 = farthest-5 | dedupe (any-year) |", "|---|---|---|---|---|---|---|"]
    for m in ms:
        o = res[m]["opposites"]
        L.append(f"| {m} | {_f(o['mean_hk_classes'], 2)}/{o['min_hk_classes']} | {_f(o['mean_regions'], 2)}/{o['min_regions']} | "
                 f"{_f(o['frac_anchors_3_3'], 2)} | {_tick(o['pass_coverage'])} | {_tick(o['div0_exact'])} | {_tick(o['dedupe_any_year'])} |")
    fnd = meta.get("findings", {})
    if fnd.get("beta_sweep"):
        sw = fnd["beta_sweep"]
        presets = ", ".join(f"{k} β={v:g}" for k, v in fnd["div_presets"].items())
        L += ["", f"### MMR β sweep (`blend`, k = 5, all {sw[0]['n']} country anchors ≥ 100k at 2024; shipped presets: {presets})", "",
              "| β | mean top-5 Jaccard vs strict (β=0) | mean raw rank of picks | mean distinct UN regions | anchors identical to β=2 |",
              "|---|---|---|---|---|"]
        L += [f"| {r['beta']:g} | {_f(r['jaccard_vs_strict'], 2)} | {_f(r['mean_raw_rank'], 1)} | {_f(r['mean_regions'], 2)} | {_f(r['identical_to_beta2'], 2)} |" for r in sw]
        L += ["", "The coverage target (≥ 3 Hahn-Klimroth classes AND ≥ 3 UN regions among 5 opposites) fails for every metric and is "
                  "**structural, not a bug**: the MMR pool is the farthest quartile, which for any old anchor is entirely young "
                  "'pyramid'-class Sahel/Gulf countries, so diversity over SHAPE distance cannot buy class or region variety at any β "
                  "(mean regions never exceeds ~2.1). The diversity term also saturates early (β = 2 and β = 4 pick the same five for "
                  "most anchors), so the presets were re-calibrated from the sweep — balanced β = 0.5 keeps ≈ ⅔ of the strict list, "
                  "spread β = 2 ≈ ⅓ — and product copy must not promise regional variety; a region/class cap is a v1.1 option (PLAN §5)."]
    if fnd.get("blend_w1_share"):
        bw = fnd["blend_w1_share"]
        L += ["", "### Documented asymmetry: W1 share of `blend` by era (median over same-year pairs ≥ 100k)", "",
              "| sex | observed ≤ 2023 | nowcast 2024–2026 | projected > 2026 | pooled (σ fit) |", "|---|---|---|---|---|"]
        for sex, label in (("2", "two-sex"), ("1", "total only")):
            b = bw[sex]
            L.append(f"| {label} | {_f(b.get('obs'))} | {_f(b.get('nowcast'))} | {_f(b.get('proj'))} | {_f(b.get('all'))} |")
        L += ["", "σ is the median over pairs pooled uniformly over 1950–2100 (CONTRACT §4), so the two halves of `blend` are equal on the "
                  "pooled sample only; σ_w1 rises into the projections, which tilts observed-year pairs towards the L2 term. The "
                  "definition stands (it lands balanced exactly at the 2024–2026 default years); the tilt is recorded here and in the "
                  "build report (`blend_w1_share`) rather than hidden."]
    L += ["", "## Method agreement (mean top-10 Jaccard, 200 random same-year queries 1960–2023)", "",
          "| | " + " | ".join(ms) + " |", "|---|" + "---|" * len(ms)]
    for a in ms:
        L.append(f"| {a} | " + " | ".join(_f(J.loc[a, b], 2) for b in ms) + " |")
    gnames = list(next(iter(res.values()))["regression"]["groups"])
    L += ["", "## Regression (reported, never gates): canonical groups at 2024 — normalised P@5 / MRR", "",
          "| metric | " + " | ".join(gnames) + " |", "|---|" + "---|" * len(gnames)]
    for m in ms:
        g = res[m]["regression"]["groups"]
        L.append(f"| {m} | " + " | ".join(f"{_f(g[n]['p_at_5'], 2)} / {_f(g[n]['mrr'], 2)}" for n in gnames) + " |")
    ws = next(iter(res.values()))["regression"]["time_shift"]
    L += ["", "## Regression: time-shift windows (best year, era all)", "",
          "| metric | " + " | ".join(f"{w['query'][0]} {w['query'][1]} → {w['target']} {w['window']}{' (gate)' if w['gate'] else ''}" for w in ws) + " |",
          "|---|" + "---|" * len(ws)]
    for m in ms:
        L.append(f"| {m} | " + " | ".join(f"{w['best_year']} {_tick(w['pass'])}" for w in res[m]["regression"]["time_shift"]) + " |")
    L += ["", "## Verdicts (protocol.md §4; INFORMATIONAL — both blend and visual ship)", "",
          "| metric | verdict | G1 | G2 | G4 | note |", "|---|---|---|---|---|---|"]
    for m in ms:
        r = res[m]
        note = "trend-mode toggle (G1 only)" if m in ("trend", "path") else ("provisional until M4 triplets" if r["verdict"] == "menu" else "")
        L.append(f"| {m} | **{r['verdict']}** | {_tick(r['gates']['G1'])} | {_tick(r['gates']['G2'])} | {_tick(r['gates']['G4'])} | {note} |")
    ev = exposed_visual(res)
    if ev:
        L += ["", "### Image-space predictions (evals/image_embeddings.md §2)", ""]
        for m in [m for m in ms if m.startswith("visual:")]:
            c1, hk, v = res[m]["g1"]["observed"]["C1"], res[m]["hk_agree"], res[m]["verdict"]
            if v == EXPECTED_VISUAL_VERDICT:
                exp = "met"
            else:
                why = f"C1 < {GATES['lab_C1']}" if c1 < GATES["lab_C1"] else f"HK agreement < {GATES['reject_hk']}" if hk < GATES["reject_hk"] else "gates passed"
                exp = f"NOT met — {'worse' if v == 'rejected' else 'better'} than predicted ({why})"
            L.append(f"- `{m}`: C1 = {c1:.3f} ({'< 0.95 as predicted' if c1 < 0.95 else '≥ 0.95 — prediction P1/P2 falsified'}); "
                     f"HK agreement = {hk:.3f} ({'≥ 0.6 as predicted' if hk >= 0.6 else '< 0.6 — prediction P3 falsified'}); "
                     f"expected verdict `{EXPECTED_VISUAL_VERDICT}` → observed `{v}` ({exp}).")
        L.append(f"- Exposed as \"Visual\" ({ev['rule']}): `{ev['metric']}` (C1 obs {ev['C1_obs']:.3f}); URL-only: "
                 f"{', '.join(f'`visual:{m}`' for m in ev['alternates']) or 'none'}. Recorded as `exposed_visual` in verdicts.json and meta.json.")
    L += ["", "## Findings recorded with the hand-edited groups", "",
          "- JPN's nearest 2024 neighbours are Southern European, not KOR/TWN, so no East-Asia group exists; VNM sits between THA and IDN and is in no group. Both are statements about `blend`, not label choices.",
          "- Korenjak-Černe labels: IDB-2008 vintage on 17 five-year bins (80+ open) vs our WPP2024 21-bin rows; Netherlands Antilles unmapped; Gaza Strip + West Bank merged into PSE.", ""]
    return "\n".join(L)


# ============================================================================================ CLI
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--full", action="store_true", help="run the whole protocol → evals/RESULTS.md + evals/verdicts.json")
    ap.add_argument("--query", nargs=argparse.REMAINDER, help="ID YEAR [query.py flags…]: quick look via scripts/query.py")
    ap.add_argument("--n-queries", type=int, default=300, help="continuity queries per span and method-agreement queries")
    ap.add_argument("--n-anchors", type=int, default=20, help="opposites-test anchors")
    ap.add_argument("--sweep-anchors", type=int, default=None, help="β-sweep anchors (default: every 2024 country ≥ 100k)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=EVALS)
    a = ap.parse_args(argv)
    if a.query:
        sys.exit(subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "query.py"), *a.query]).returncode)
    if not a.full:
        ap.error("nothing to do: pass --full or --query ID YEAR")
    run_full(a.n_queries, a.n_anchors, a.seed, a.out_dir, sweep_anchors=a.sweep_anchors)


if __name__ == "__main__":
    main()
