"""Human-triplet selection and fitting (PLAN §4.6 item 8, evals/protocol.md §3, M4).

Selection (`select_triplets`, seed 0, deterministic): 80 unique items stratified as 32 *visual* (top-1 same-year
twin of ``blend`` vs the exposed image space differ), 38 *numeric* (top-1 of two continuity-passing numeric
metrics differ; the pair is recorded) and 10 *opposite* (strict farthest under two metrics differ; question
variant "which is more different"), plus 8 duplicates (4 / 3 / 1) with the A/B sides swapped and placed ≥ 30
slots after their original → 88 items.  Anchors are random 2024 countries ≥ 1 M (each used once while the pool
lasts); candidates follow the product default (same year, countries ≥ 100k, own entity excluded).  Every item
carries the u16 share rows of anchor / A / B (text-free identical-scale renders need no further fetch), the
distance d(anchor, A) and d(anchor, B) under every recorded metric, and the raw blend / w1bal components the
grid fit re-weights.

Fitting (`fit`): self-agreement on the 8 duplicate pairs (gate 6/8 — below it nothing may be promoted on
triplet evidence and every verdict is *informational*), pairwise agreement per metric (a metric agrees with a
judgment when it ranks the chosen item closer — farther for the opposite variant), exact two-sided sign tests
(McNemar on discordant items) for blend-vs-visual and for every numeric pair, and a leave-one-out grid over the
blend weight w ∈ {0.3 … 0.7} × smoothing σ ∈ {0, 1 bin} (and λ for ``w1bal``) on the numeric strata only.

Wording rule (evals/econ/ui_sentences.yaml deny list) applies to everything written here, including JSON keys.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from pyramid_explorer.features import features, zscores
from pyramid_explorer.metrics import (BIN_WIDTH, W1BAL_LAMBDA, cdf_per_sex, distances, lagged, smooth)
from pyramid_explorer.paths import EVALS, N_BINS, WEB_SRC_DATA
from pyramid_explorer.quantise import shares_to_u16

SELECTION_PATH = EVALS / "triplets_selection.json"
SELECTION_WEB_PATH = WEB_SRC_DATA / "triplets_selection.json"
RESPONSES_PATH = EVALS / "triplets.json"
FIT_PATH = EVALS / "triplets_fit.json"
REPORT_PATH = EVALS / "TRIPLETS.md"
VERDICTS_PATH = EVALS / "verdicts.json"

TREND_L = 10
TREND_METRIC = f"trend@{TREND_L}"
# Numeric candidates for the numeric / opposite strata (PLAN §4.6: pairs among these); filtered by verdicts G1.
NUMERIC_CANDIDATES: list[str] = ["blend", "l2", "l2s", "hel", "w1sex", "w1bal", TREND_METRIC]
# Every metric whose d(anchor, A/B) is recorded per item (visual metrics are appended per embedding present).
RECORDED_METRICS: list[str] = ["blend", "l2", "w1", "l2s", "hel", "feat", "w1sex", "w1bal", "clr", TREND_METRIC]
STRATA: dict[str, int] = {"visual": 32, "numeric": 38, "opposite": 10}
DUPLICATES: dict[str, int] = {"visual": 4, "numeric": 3, "opposite": 1}
MIN_DUP_GAP = 30
SELF_AGREEMENT_GATE = 6                      # of 8 duplicate pairs
P_THRESHOLD = 0.05
QUESTIONS = {"similar": "Which of A or B is more similar in shape to the anchor?",
             "different": "Which of A or B is more different from the anchor?"}
VARIANT_OF = {"visual": "similar", "numeric": "similar", "opposite": "different"}
W_GRID: tuple[float, ...] = (0.5, 0.3, 0.4, 0.6, 0.7)      # default first: argmax ties resolve to the shipped value
SIGMA_GRID: tuple[int, ...] = (0, 1)                        # smoothing in bins; the as-built blend smooths nothing (0), default first
LAMBDA_GRID: tuple[float, ...] = (W1BAL_LAMBDA, 0.0, 10.0, 25.0, 100.0)
CHOICES = ("A", "B", "tie")


# ============================================================================================ corpus context
@dataclass
class Space:
    """Corpus + everything a metric needs to give distances from an anchor row to candidate rows."""
    X: np.ndarray
    keys: pd.DataFrame
    entities: list[dict]
    sigma: dict
    emb: dict[str, np.ndarray] = field(default_factory=dict)
    cand_minpop: float = 100.0

    def __post_init__(self) -> None:
        self.X = np.asarray(self.X, np.float64)
        self.id = self.keys["id"].to_numpy()
        self.year = self.keys["year"].to_numpy()
        self.pop = self.keys["pop_total"].to_numpy()
        self.is_country = self.keys["type"].to_numpy() == "country"
        self.names = {e["id"]: e.get("name", e["id"]) for e in self.entities}
        self._lag: np.ndarray | None = None
        self._feat: pd.DataFrame | None = None
        self._z: dict[int, pd.DataFrame] = {}

    @property
    def lag(self) -> np.ndarray:
        if self._lag is None:
            self._lag = lagged(self.X, TREND_L)
        return self._lag

    def zfeat(self, year: int) -> pd.DataFrame:
        if self._feat is None:
            self._feat = features(self.X)
        if year not in self._z:
            ref = np.flatnonzero(self.is_country & (self.year == year) & (self.pop >= self.cand_minpop))
            self._z[year] = zscores(self._feat, ref)
        return self._z[year]

    @property
    def visual_metrics(self) -> list[str]:
        return [f"visual:{m}" for m in self.emb]

    @property
    def recorded_metrics(self) -> list[str]:
        return RECORDED_METRICS + self.visual_metrics

    def candidates(self, row: int) -> np.ndarray:
        """Product default: same year, countries ≥ cand_minpop, own entity excluded."""
        m = (self.year == self.year[row]) & self.is_country & (self.pop >= self.cand_minpop) & (self.id != self.id[row])
        return np.flatnonzero(m)

    def dist(self, metric: str, row: int, rows: np.ndarray) -> np.ndarray:
        """float64 d(row, rows[i]) under ``metric`` (NaN where undefined)."""
        q, Xs = self.X[row], self.X[rows]
        if metric == TREND_METRIC:
            d = distances("trend", q, Xs, sigma=self.sigma, L=TREND_L, X_prev=self.lag[rows], q_prev=self.lag[row])
        elif metric == "feat":
            z = self.zfeat(int(self.year[row]))
            zs = z.iloc[rows]
            zs.attrs = z.attrs
            d = distances("feat", q, Xs, sigma=self.sigma, feats=zs)
        elif metric.startswith("visual:"):
            E = self.emb[metric[7:]]
            Es = np.vstack([E[rows], E[row][None]])
            d = distances(metric, q, Xs, emb=Es, q_row=len(rows))[: len(rows)]
        else:
            d = distances(metric, q, Xs, sigma=self.sigma)
        return d.astype(np.float64)

    def extreme(self, metric: str, row: int, rows: np.ndarray, farthest: bool = False) -> int:
        """Row of the nearest (or farthest) candidate; NaN distances ignored; ties → lowest row (stable)."""
        d = self.dist(metric, row, rows)
        ok = np.isfinite(d)
        if not ok.any():
            raise ValueError(f"{metric}: no finite distance from row {row}")
        d, rows = d[ok], rows[ok]
        order = np.argsort(-d if farthest else d, kind="stable")
        return int(rows[order[0]])


# ============================================================================================ components
def components(a: np.ndarray, x: np.ndarray) -> dict[str, float]:
    """Raw pieces the grid fit re-weights: L2 and per-sex W1 on raw and 1-bin-smoothed shares, W1 on total
    shares and the symmetric sex-ratio term of ``w1bal`` (metrics.py definitions, sex="2")."""
    a, x = np.asarray(a, np.float64).reshape(-1), np.asarray(x, np.float64).reshape(-1)
    sa, sx = smooth(a)[0], smooth(x)[0]
    a21, x21 = a[:N_BINS] + a[N_BINS:], x[:N_BINS] + x[N_BINS:]
    ra = np.divide(a[:N_BINS], a21, out=np.full_like(a21, 0.5), where=a21 > 0)
    rx = np.divide(x[:N_BINS], x21, out=np.full_like(x21, 0.5), where=x21 > 0)
    return {
        "l2": float(np.linalg.norm(a - x)),
        "w1sex": float(BIN_WIDTH * np.abs(cdf_per_sex(a) - cdf_per_sex(x)).sum()),
        "l2_s1": float(np.linalg.norm(sa - sx)),
        "w1sex_s1": float(BIN_WIDTH * np.abs(cdf_per_sex(sa) - cdf_per_sex(sx)).sum()),
        "w1_s21": float(BIN_WIDTH * np.abs(np.cumsum(a21) - np.cumsum(x21)).sum()),
        "bal": float((0.5 * (a21 + x21) * np.abs(ra - rx)).sum()),
    }


def blend_from(c: dict[str, float], w: float, s: int, sigma: dict) -> float:
    """Blend distance re-weighted: ``w·l2/σ_L2 + (1−w)·w1sex/σ_W1``; ``s = 1`` uses the smoothed pieces with
    σ_L2 = σ(l2s) (the W1 of smoothed shares keeps σ(w1sex): smoothing moves little mass)."""
    if s == 0:
        return w * c["l2"] / sigma["l2"]["2"] + (1 - w) * c["w1sex"] / sigma["w1sex"]["2"]
    return w * c["l2_s1"] / sigma["l2s"]["2"] + (1 - w) * c["w1sex_s1"] / sigma["w1sex"]["2"]


def w1bal_from(c: dict[str, float], lam: float) -> float:
    return c["w1_s21"] + lam * c["bal"]


# ============================================================================================ selection
def numeric_metrics_from_verdicts(verdicts: dict | None) -> list[str]:
    """NUMERIC_CANDIDATES that passed G1 in ``verdicts.json`` (all of them when no verdicts exist)."""
    if not verdicts:
        return list(NUMERIC_CANDIDATES)
    out = []
    for m in NUMERIC_CANDIDATES:
        key = "trend" if m == TREND_METRIC else m
        v = verdicts.get(key)
        if isinstance(v, dict) and v.get("gates", {}).get("G1") is False:
            continue
        out.append(m)
    return out


def exposed_visual_from_verdicts(verdicts: dict | None, available: list[str]) -> str:
    """``verdicts.exposed_visual.metric`` when present and available, else the first available image space."""
    if not available:
        raise ValueError("no image space available for the visual stratum")
    want = ((verdicts or {}).get("exposed_visual") or {}).get("metric")
    return want if want in available else available[0]


def _anchor_stream(anchors: np.ndarray, rng: np.random.Generator, used: set[int], passes: int = 3):
    """Anchors in a seeded order; the first pass skips anchors already used by any stratum, later passes allow
    reuse (only reached when the pool is exhausted, e.g. on a small synthetic corpus)."""
    for k in range(passes):
        for r in rng.permutation(anchors):
            if k == 0 and int(r) in used:
                continue
            yield int(r)


def _pair_order(pairs: list[tuple[str, str]], uses: dict, rng: np.random.Generator) -> list[tuple[str, str]]:
    """Least-used pairs first (even coverage), random among equals."""
    jitter = rng.random(len(pairs))
    return [pairs[i] for i in np.lexsort((jitter, np.array([uses[p] for p in pairs])))]


def _item(sp: Space, stratum: str, anchor: int, a: tuple[str, int], b: tuple[str, int], rng: np.random.Generator,
          uid: int) -> dict:
    """One item record; A/B labelling and left/right side are both randomised."""
    if rng.random() < 0.5:
        a, b = b, a
    (ma, ra), (mb, rb) = a, b
    rows = np.array([ra, rb])
    dists = {}
    for m in sp.recorded_metrics:
        d = sp.dist(m, anchor, rows)
        dists[m] = {"A": _num(d[0]), "B": _num(d[1])}
    u16 = shares_to_u16(sp.X[[anchor, ra, rb]])
    left = "A" if rng.random() < 0.5 else "B"

    def ent(row: int, metric: str | None = None) -> dict:
        e = {"id": str(sp.id[row]), "year": int(sp.year[row]), "name": sp.names.get(str(sp.id[row]), str(sp.id[row]))}
        return e if metric is None else {**e, "metric": metric}

    return {"uid": uid, "stratum": stratum, "variant": VARIANT_OF[stratum], "question": QUESTIONS[VARIANT_OF[stratum]],
            "anchor": ent(anchor), "A": ent(ra, ma), "B": ent(rb, mb), "pair": [ma, mb],
            "side_map": {"left": left, "right": "B" if left == "A" else "A"}, "duplicate_of": None,
            "shares": {"anchor": u16[0].tolist(), "A": u16[1].tolist(), "B": u16[2].tolist()},
            "distances": dists,
            "components": {"A": components(sp.X[anchor], sp.X[ra]), "B": components(sp.X[anchor], sp.X[rb])}}


def _num(x) -> float | None:
    return None if not np.isfinite(x) else float(x)


def select_triplets(sp: Space, *, seed: int = 0, anchor_year: int = 2024, anchor_minpop: float = 1000.0,
                    numeric_metrics: list[str] | None = None, visual_metric: str | None = None,
                    strata: dict[str, int] = STRATA, duplicates: dict[str, int] = DUPLICATES,
                    min_gap: int = MIN_DUP_GAP, data_hash: str | None = None) -> dict:
    """The selection document (see module docstring). Deterministic in ``seed``."""
    rng = np.random.default_rng(seed)
    numeric = list(numeric_metrics or NUMERIC_CANDIDATES)
    visual = visual_metric or (sp.visual_metrics[0] if sp.visual_metrics else None)
    if strata.get("visual", 0) and visual is None:
        raise ValueError("visual stratum requested but no image space is loaded")
    anchors = np.flatnonzero(sp.is_country & (sp.year == anchor_year) & (sp.pop >= anchor_minpop))
    if len(anchors) == 0:
        raise ValueError(f"no anchors: countries ≥ {anchor_minpop} at {anchor_year}")
    pairs = list(combinations(numeric, 2))
    uses = {"numeric": {p: 0 for p in pairs}, "opposite": {p: 0 for p in pairs}}
    items: list[dict] = []
    uid = 0
    used: set[int] = set()
    for stratum in ("visual", "numeric", "opposite"):
        need = strata.get(stratum, 0)
        stream = _anchor_stream(anchors, rng, used)
        while need > 0:
            try:
                anchor = next(stream)
            except StopIteration:
                raise RuntimeError(f"stratum {stratum}: anchors exhausted with {need} items still needed") from None
            cand = sp.candidates(anchor)
            if len(cand) < 2:
                continue
            if stratum == "visual":
                ta, tb = sp.extreme("blend", anchor, cand), sp.extreme(visual, anchor, cand)
                if ta == tb:
                    continue
                items.append(_item(sp, stratum, anchor, ("blend", ta), (visual, tb), rng, uid))
            else:
                far = stratum == "opposite"
                hit = None
                for p in _pair_order(pairs, uses[stratum], rng):
                    ta, tb = sp.extreme(p[0], anchor, cand, far), sp.extreme(p[1], anchor, cand, far)
                    if ta != tb:
                        hit = (p, ta, tb)
                        break
                if hit is None:
                    continue
                p, ta, tb = hit
                uses[stratum][p] += 1
                items.append(_item(sp, stratum, anchor, (p[0], ta), (p[1], tb), rng, uid))
            used.add(anchor)
            uid += 1
            need -= 1
    # order: shuffle the uniques, then insert swapped duplicates ≥ min_gap slots after their original
    seq = [items[i] for i in rng.permutation(len(items))]
    n_unique = len(seq)
    horizon = n_unique - min_gap
    if horizon < 1:
        raise ValueError(f"min_gap {min_gap} leaves no room for duplicates among {n_unique} items")
    dups: list[dict] = []
    for stratum, k in duplicates.items():
        pool = [it for it in seq[:horizon] if it["stratum"] == stratum]
        if len(pool) < k:
            raise ValueError(f"stratum {stratum}: only {len(pool)} items in the first {horizon} slots, need {k} duplicates")
        for it in (pool[i] for i in rng.choice(len(pool), size=k, replace=False)):
            d = json.loads(json.dumps(it))
            d["uid"], d["duplicate_of_uid"] = None, it["uid"]
            d["side_map"] = {"left": it["side_map"]["right"], "right": it["side_map"]["left"]}
            dups.append(d)
    for d in (dups[i] for i in rng.permutation(len(dups))):
        pos = next(i for i, it in enumerate(seq) if it.get("uid") == d["duplicate_of_uid"])
        seq.insert(int(rng.integers(pos + min_gap, len(seq) + 1)), d)
    index_of_uid = {it["uid"]: i for i, it in enumerate(seq) if it.get("uid") is not None}
    for i, it in enumerate(seq):
        it["item"] = i
        it["duplicate_of"] = index_of_uid[it.pop("duplicate_of_uid")] if "duplicate_of_uid" in it else None
        it.pop("uid", None)
        assert it["duplicate_of"] is None or i - it["duplicate_of"] >= min_gap
    n_anchor_reuse = len(items) - len({it["anchor"]["id"] for it in items})
    return {
        "version": 1, "seed": seed, "protocol": "evals/protocol.md §3 / PLAN §4.6 item 8", "data_hash": data_hash,
        "anchor_year": anchor_year, "anchor_minpop_thousands": anchor_minpop, "cand_minpop_thousands": sp.cand_minpop,
        "n_anchor_pool": int(len(anchors)), "n_anchor_reused": int(n_anchor_reuse),
        "questions": QUESTIONS, "choices": list(CHOICES),
        "response_format": {"rater": "str", "started": "ISO-8601", "finished": "ISO-8601",
                            "items": [{"item": "int (index into items)", "choice": "A | B | tie (the A/B labels, not the side)",
                                       "rt_ms": "int"}]},
        "visual_metric": visual, "numeric_metrics": numeric, "recorded_metrics": sp.recorded_metrics,
        "sigma": {m: sp.sigma[m] for m in ("l2", "l2s", "w1sex", "w1bal") if m in sp.sigma},
        "strata": dict(strata), "duplicates": dict(duplicates), "min_duplicate_gap": min_gap,
        "n_unique": n_unique, "n_items": len(seq),
        "pair_uses": {s: {" vs ".join(p): n for p, n in u.items() if n} for s, u in uses.items()},
        "items": seq,
    }


def corpus_hash(X: np.ndarray) -> str:
    """sha256 of the little-endian u16 corpus (matches eval_similarity's ``data_hash`` when ``corpus_u16`` exists)."""
    return hashlib.sha256(shares_to_u16(np.asarray(X, np.float64)).astype("<u2").tobytes()).hexdigest()


def write_selection(sel: dict, path: Path = SELECTION_PATH, web_path: Path | None = SELECTION_WEB_PATH) -> None:
    text = json.dumps(sel, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if web_path is not None:
        web_path.parent.mkdir(parents=True, exist_ok=True)
        web_path.write_text(text, encoding="utf-8")


# ============================================================================================ responses
def responses_by_item(responses: dict) -> dict[int, dict]:
    """First response per item (a repeated item index keeps its first answer)."""
    out: dict[int, dict] = {}
    for r in responses.get("items", []):
        if r.get("choice") not in CHOICES:
            raise ValueError(f"item {r.get('item')}: choice must be one of {CHOICES}, got {r.get('choice')!r}")
        out.setdefault(int(r["item"]), r)
    return out


def _chosen_other(item: dict, choice: str) -> tuple[str, str]:
    return ("A", "B") if choice == "A" else ("B", "A")


def metric_agrees(item: dict, metric: str, choice: str) -> bool | None:
    """True when ``metric`` ranks the chosen item closer (farther for the opposite variant); None when undefined
    (tie choice, missing distance, or the metric's two distances are equal)."""
    if choice == "tie":
        return None
    dA, dB = item["distances"][metric]["A"], item["distances"][metric]["B"]
    if dA is None or dB is None or dA == dB:
        return None
    ch, ot = _chosen_other(item, choice)
    d_ch, d_ot = (dA, dB) if ch == "A" else (dB, dA)
    return d_ch > d_ot if item["variant"] == "different" else d_ch < d_ot


def metric_prefers(item: dict, metric: str) -> str | None:
    """Which label the metric itself favours for this item's question (A / B / None if undefined or equal)."""
    dA, dB = item["distances"][metric]["A"], item["distances"][metric]["B"]
    if dA is None or dB is None or dA == dB:
        return None
    closer = "A" if dA < dB else "B"
    return closer if item["variant"] == "similar" else ("B" if closer == "A" else "A")


# ============================================================================================ analyses
def self_agreement(sel: dict, resp: dict[int, dict], gate: int = SELF_AGREEMENT_GATE) -> dict:
    """Agreement on the duplicate pairs (ties count as disagreement unless both are ties)."""
    pairs = []
    for it in sel["items"]:
        if it["duplicate_of"] is None:
            continue
        a, b = resp.get(it["duplicate_of"]), resp.get(it["item"])
        if a is None or b is None:
            pairs.append({"dup": it["item"], "orig": it["duplicate_of"], "stratum": it["stratum"], "agree": None})
            continue
        pairs.append({"dup": it["item"], "orig": it["duplicate_of"], "stratum": it["stratum"],
                      "choice_orig": a["choice"], "choice_dup": b["choice"], "agree": a["choice"] == b["choice"]})
    judged = [p for p in pairs if p["agree"] is not None]
    n_agree = sum(p["agree"] for p in judged)
    return {"n_pairs": len(pairs), "n_judged": len(judged), "n_agree": int(n_agree), "gate": gate,
            "passes": bool(len(judged) == len(pairs) and n_agree >= gate), "pairs": pairs}


def unique_items(sel: dict) -> list[dict]:
    return [it for it in sel["items"] if it["duplicate_of"] is None]


def pairwise_agreement(sel: dict, resp: dict[int, dict]) -> dict[str, dict]:
    """Per recorded metric: judged / tie / undefined counts and agreement fraction, overall and per stratum."""
    out = {}
    for m in sel["recorded_metrics"]:
        rec = {"n_items": 0, "n_tie": 0, "n_undefined": 0, "n_judged": 0, "n_agree": 0, "by_stratum": {}}
        for it in unique_items(sel):
            r = resp.get(it["item"])
            if r is None:
                continue
            rec["n_items"] += 1
            s = rec["by_stratum"].setdefault(it["stratum"], {"n_judged": 0, "n_agree": 0})
            if r["choice"] == "tie":
                rec["n_tie"] += 1
                continue
            ag = metric_agrees(it, m, r["choice"])
            if ag is None:
                rec["n_undefined"] += 1
                continue
            rec["n_judged"] += 1
            rec["n_agree"] += int(ag)
            s["n_judged"] += 1
            s["n_agree"] += int(ag)
        rec["agreement"] = rec["n_agree"] / rec["n_judged"] if rec["n_judged"] else None
        for s in rec["by_stratum"].values():
            s["agreement"] = s["n_agree"] / s["n_judged"] if s["n_judged"] else None
        out[m] = rec
    return out


def sign_test(wins_a: int, wins_b: int) -> dict:
    """Exact two-sided binomial (McNemar on discordant pairs): P(X ≤ min | n, ½)·2, capped at 1."""
    n = wins_a + wins_b
    p = float(binomtest(wins_a, n, 0.5, alternative="two-sided").pvalue) if n else None
    return {"n_discordant": n, "wins_a": wins_a, "wins_b": wins_b, "p": p,
            "winner": None if not n or p is None or p >= P_THRESHOLD else ("a" if wins_a > wins_b else "b")}


def paired_test(sel: dict, resp: dict[int, dict], ma: str, mb: str, items: list[dict]) -> dict:
    """Sign test between two metrics over the non-tie items of ``items`` on which they disagree."""
    wa = wb = 0
    n_tie = 0
    for it in items:
        r = resp.get(it["item"])
        if r is None:
            continue
        if r["choice"] == "tie":
            n_tie += 1
            continue
        pa, pb = metric_prefers(it, ma), metric_prefers(it, mb)
        if pa is None or pb is None or pa == pb:
            continue
        if r["choice"] == pa:
            wa += 1
        else:
            wb += 1
    t = sign_test(wa, wb)
    return {"a": ma, "b": mb, "n_items": len(items), "n_tie": n_tie, **t,
            "winner": {None: None, "a": ma, "b": mb}[t["winner"]]}


def _numeric_items(sel: dict) -> list[dict]:
    return [it for it in unique_items(sel) if it["stratum"] in ("numeric", "opposite")]


def grid_fit(sel: dict, resp: dict[int, dict]) -> dict:
    """Leave-one-out grid over blend (w, σ) and w1bal λ on the numeric strata (never the visual items).

    For every held-out non-tie item the best grid cell on the other items (ties → the shipped default, listed
    first) is evaluated on it; ``loo_agreement`` is that mean.  ``table`` gives in-sample agreement per cell.
    """
    sigma = sel["sigma"]
    items = [it for it in _numeric_items(sel) if it["item"] in resp and resp[it["item"]]["choice"] != "tie"]

    def agree_matrix(score) -> tuple[np.ndarray, list]:
        cells = list(score)
        M = np.zeros((len(cells), len(items)), dtype=np.int8)     # 1 agree, 0 disagree, −1 undefined (equal)
        for j, it in enumerate(items):
            ch = resp[it["item"]]["choice"]
            for i, c in enumerate(cells):
                dA, dB = score[c](it["components"]["A"]), score[c](it["components"]["B"])
                if dA == dB:
                    M[i, j] = -1
                    continue
                d_ch, d_ot = (dA, dB) if ch == "A" else (dB, dA)
                ok = d_ch > d_ot if it["variant"] == "different" else d_ch < d_ot
                M[i, j] = int(ok)
        return M, cells

    def loo(M: np.ndarray, cells: list, as_dict) -> dict:
        """Cell 0 is the shipped default (as-built ``blend`` = w 0.5 on raw shares; ``w1bal`` λ = 50)."""
        n = M.shape[1]
        A = (M == 1).astype(float)
        table = [{**as_dict(c), "n_judged": int((M[i] >= 0).sum()), "n_agree": int(A[i].sum()),
                  "agreement": float(A[i].sum() / (M[i] >= 0).sum()) if (M[i] >= 0).any() else None}
                 for i, c in enumerate(cells)]
        if n == 0:
            return {"n_items": 0, "loo_agreement": None, "loo_selected": [], "in_sample_best": as_dict(cells[0]),
                    "_best": cells[0], "table": table}
        tot = A.sum(1)
        hits, chosen = [], []
        for j in range(n):
            other = tot - A[:, j]
            best = int(np.argmax(other))                      # first max → the default cell wins ties
            hits.append(A[best, j])
            chosen.append(as_dict(cells[best]))
        selected: list[dict] = []
        for c in chosen:
            hit = next((x for x in selected if x["cell"] == c), None)
            if hit is None:
                selected.append({"cell": c, "n": 1})
            else:
                hit["n"] += 1
        return {"n_items": n, "loo_agreement": float(np.mean(hits)), "loo_selected": selected,
                "in_sample_best": as_dict(cells[int(np.argmax(tot))]), "_best": cells[int(np.argmax(tot))], "table": table}

    blend_cells = {(w, s): (lambda c, w=w, s=s: blend_from(c, w, s, sigma)) for s in SIGMA_GRID for w in W_GRID}
    Mb, cb = agree_matrix(blend_cells)
    rb = loo(Mb, cb, lambda c: {"w_l2": c[0], "sigma_bins": c[1]})
    lam_cells = {lam: (lambda c, lam=lam: w1bal_from(c, lam)) for lam in LAMBDA_GRID}
    Ml, cl = agree_matrix(lam_cells)
    rl = loo(Ml, cl, lambda c: {"lambda": c})

    def versus_default(M: np.ndarray, cells: list, best) -> dict:
        """Sign test of the in-sample best cell (a) against the shipped default (b, cell 0) on their discordant items."""
        i0, i1 = 0, cells.index(best)
        both = (M[i0] >= 0) & (M[i1] >= 0)
        disc = both & (M[i0] != M[i1])
        return sign_test(int(((M[i1] == 1) & disc).sum()), int(((M[i0] == 1) & disc).sum()))

    rb["best_vs_default"], rl["best_vs_default"] = versus_default(Mb, cb, rb.pop("_best")), versus_default(Ml, cl, rl.pop("_best"))
    return {
        "n_items": len(items), "grid": {"w_l2": list(W_GRID), "sigma_bins": list(SIGMA_GRID), "lambda": list(LAMBDA_GRID)},
        "blend": {"default": {"w_l2": 0.5, "sigma_bins": 0}, **rb},
        "w1bal": {"default": {"lambda": W1BAL_LAMBDA}, **rl},
    }


def fit(sel: dict, responses: dict, verdicts: dict | None = None) -> dict:
    """Everything `fit_params.py` reports, as one JSON-able dict (see module docstring)."""
    resp = responses_by_item(responses)
    n_expected = sel["n_items"]
    answered = sorted(i for i in resp if 0 <= i < n_expected)
    sa = self_agreement(sel, resp)
    agreement = pairwise_agreement(sel, resp)
    visual_items = [it for it in unique_items(sel) if it["stratum"] == "visual"]
    numeric_items = _numeric_items(sel)
    visual = sel["visual_metric"]
    tests = {"blend_vs_visual": paired_test(sel, resp, "blend", visual, visual_items)}
    for m in sel["recorded_metrics"]:
        if m.startswith("visual:") and m != visual:
            tests[f"visual_pair:{visual}_vs_{m}"] = paired_test(sel, resp, visual, m, visual_items)
    numeric_pairs = {}
    for a, b in combinations(sel["numeric_metrics"], 2):
        numeric_pairs[f"{a} vs {b}"] = paired_test(sel, resp, a, b, numeric_items)
    grid = grid_fit(sel, resp)
    gate_ok = sa["passes"]
    # decisions — every one is informational (DECISION 4); the gate blocks promotion, never reporting
    bv = tests["blend_vs_visual"]
    visual_gates = (verdicts or {}).get(visual, {}).get("gates", {}) if verdicts else {}
    visual_passes_gates = all(visual_gates.get(g) for g in ("G1", "G2", "G4")) if visual_gates else False
    default_rec = "blend"
    if gate_ok and bv["winner"] == visual and visual_passes_gates:
        default_rec = visual
    exposed_rec = {"current": visual, "recommended": visual, "reason": "no change"}
    for k, t in tests.items():
        if k.startswith("visual_pair:") and gate_ok and t["winner"] not in (None, visual):
            exposed_rec = {"current": visual, "recommended": t["winner"],
                           "reason": f"{t['winner']} won the paired test on the {t['n_items']} visual items "
                                     f"({t['wins_b']}–{t['wins_a']}, p = {t['p']:.3f}); G1 still decides in verdicts.json"}
    bl, wb = grid["blend"], grid["w1bal"]
    params_rec = {"w_l2": 0.5, "sigma_bins": 0, "lambda": W1BAL_LAMBDA, "changed": False}
    if gate_ok and bl["best_vs_default"]["winner"] == "a":
        params_rec.update(bl["in_sample_best"], changed=True)
    if gate_ok and wb["best_vs_default"]["winner"] == "a":
        params_rec.update(wb["in_sample_best"], changed=True)
    status = "informational (self-agreement gate met)" if gate_ok else "informational (self-agreement below 6/8: nothing may be promoted on triplet evidence)"
    return {
        "version": 1, "rater": responses.get("rater"), "started": responses.get("started"), "finished": responses.get("finished"),
        "synthetic": bool(responses.get("synthetic", False)), "oracle": responses.get("oracle"),
        "n_items": n_expected, "n_answered": len(answered), "n_missing": n_expected - len(answered),
        "n_tie": sum(1 for r in resp.values() if r["choice"] == "tie"),
        "median_rt_ms": _median_rt(resp), "selection_data_hash": sel.get("data_hash"),
        "self_agreement": sa, "status": status, "promotion_allowed": gate_ok,
        "agreement": agreement, "tests": tests, "numeric_pair_tests": numeric_pairs, "grid": grid,
        "mde": {"blend_vs_visual": "pre-registered: with 32 items one side must win ≥ 22 of the non-tie discordant items (≈ 69 %); "
                                   "the exact two-sided binomial gives p = 0.050 at 22/32 (one-sided 0.025), so 23/32 is the first count called here",
                "numeric": "with 48 numeric/opposite items the pairwise comparisons resolve gaps ≥ ~20 points"},
        "recommendations": {"default_metric": default_rec, "exposed_visual": exposed_rec, "blend_params": params_rec,
                            "verdicts_json": "not modified by fit_params.py — apply by hand after review"},
    }


def _median_rt(resp: dict[int, dict]) -> float | None:
    rts = [r["rt_ms"] for r in resp.values() if isinstance(r.get("rt_ms"), (int, float))]
    return float(np.median(rts)) if rts else None


# ============================================================================================ synthetic rater
def synthetic_responses(sel: dict, *, seed: int = 0, metric: str = "blend", w_l2: float | None = None,
                        sigma_bins: int | None = None, lam: float | None = None, noise: float = 0.1,
                        tie_rate: float = 0.05, dup_noise: float | None = None) -> dict:
    """A noisy oracle: answers every item by ``metric`` (or a re-weighted blend when ``w_l2``/``sigma_bins`` are
    given, or w1bal with ``lam``), flips with probability ``noise``, ties with ``tie_rate``.  Duplicates repeat
    the original's answer, flipped with ``dup_noise`` (defaults to ``noise``).  Marked ``synthetic: true``."""
    rng = np.random.default_rng(seed)
    sigma = sel["sigma"]
    dup_noise = noise if dup_noise is None else dup_noise

    def prefers(it: dict) -> str | None:
        if w_l2 is not None or sigma_bins is not None:
            w, s = 0.5 if w_l2 is None else w_l2, 1 if sigma_bins is None else sigma_bins
            dA, dB = blend_from(it["components"]["A"], w, s, sigma), blend_from(it["components"]["B"], w, s, sigma)
        elif lam is not None:
            dA, dB = w1bal_from(it["components"]["A"], lam), w1bal_from(it["components"]["B"], lam)
        else:
            return metric_prefers(it, metric)
        if dA == dB:
            return None
        closer = "A" if dA < dB else "B"
        return closer if it["variant"] == "similar" else ("B" if closer == "A" else "A")

    answers: dict[int, str] = {}
    out = []
    for it in sel["items"]:
        if it["duplicate_of"] is not None:
            base = answers[it["duplicate_of"]]
            if base != "tie" and rng.random() < dup_noise:
                base = "B" if base == "A" else "A"
            choice = base
        else:
            pref = prefers(it)
            if pref is None or rng.random() < tie_rate:
                choice = "tie"
            else:
                choice = pref if rng.random() >= noise else ("B" if pref == "A" else "A")
        answers[it["item"]] = choice
        out.append({"item": it["item"], "choice": choice, "rt_ms": int(rng.integers(2500, 9000))})
    oracle = {"metric": metric, "w_l2": w_l2, "sigma_bins": sigma_bins, "lambda": lam, "noise": noise, "tie_rate": tie_rate,
              "dup_noise": dup_noise, "seed": seed}
    return {"rater": "synthetic-oracle", "started": None, "finished": None, "synthetic": True, "oracle": oracle,
            "items": out}


# ============================================================================================ report
def _pct(x) -> str:
    return "—" if x is None else f"{100 * x:.0f} %"


def _p(x) -> str:
    return "—" if x is None else (f"{x:.3f}" if x >= 0.001 else "< 0.001")


def render_report(f: dict, sel: dict) -> str:
    """evals/TRIPLETS.md — tables only, past tense, no forecasts."""
    L = [f"# Human triplets — fit ({'SYNTHETIC ORACLE, not a human judgment' if f['synthetic'] else 'rater: ' + str(f['rater'])})", ""]
    L += [f"Selection: seed {sel['seed']}, {sel['n_unique']} unique items + {sel['n_items'] - sel['n_unique']} swapped duplicates "
          f"(gap ≥ {sel['min_duplicate_gap']}), anchors = {sel['anchor_year']} countries ≥ {sel['anchor_minpop_thousands'] / 1000:g} M "
          f"({sel['n_anchor_pool']} in the pool, {sel['n_anchor_reused']} reused), candidates = same-year countries ≥ "
          f"{sel['cand_minpop_thousands']:g}k; corpus hash `{(sel.get('data_hash') or '—')[:12]}`.",
          f"Responses: {f['n_answered']}/{f['n_items']} answered, {f['n_tie']} ties, median response {f['median_rt_ms'] or '—'} ms.", ""]
    if f["synthetic"]:
        L += [f"Oracle: `{json.dumps(f['oracle'])}` — these numbers only exercise the pipeline.", ""]
    sa = f["self_agreement"]
    L += ["## 1. Self-agreement (pre-registered gate: ≥ 6 of 8 duplicate pairs)", "",
          f"**{sa['n_agree']} / {sa['n_pairs']}** pairs agreed → **{'gate met' if sa['passes'] else 'gate NOT met'}**. Status: {f['status']}.", "",
          "| dup item | original | stratum | original answer | duplicate answer | agree |", "|---|---|---|---|---|---|"]
    for p in sa["pairs"]:
        L.append(f"| {p['dup']} | {p['orig']} | {p['stratum']} | {p.get('choice_orig', '—')} | {p.get('choice_dup', '—')} | "
                 f"{'yes' if p['agree'] else ('no' if p['agree'] is False else '—')} |")
    L += ["", "## 2. Pairwise agreement per metric (unique items; ties and equal-distance items excluded)", "",
          "| metric | judged | agree | overall | visual (32) | numeric (38) | opposite (10) |", "|---|---|---|---|---|---|---|"]
    for m, r in f["agreement"].items():
        bs = r["by_stratum"]
        L.append(f"| `{m}` | {r['n_judged']} | {r['n_agree']} | {_pct(r['agreement'])} | "
                 + " | ".join(_pct(bs.get(s, {}).get('agreement')) for s in ("visual", "numeric", "opposite")) + " |")
    L += ["", "## 3. Paired sign tests (exact two-sided binomial on discordant items, α = 0.05)", "",
          f"MDE: {f['mde']['blend_vs_visual']}; {f['mde']['numeric']}.", "",
          "| comparison | items | ties | discordant | wins a | wins b | p | called |", "|---|---|---|---|---|---|---|---|"]
    for t in list(f["tests"].values()) + list(f["numeric_pair_tests"].values()):
        L.append(f"| `{t['a']}` (a) vs `{t['b']}` (b) | {t['n_items']} | {t['n_tie']} | {t['n_discordant']} | {t['wins_a']} | "
                 f"{t['wins_b']} | {_p(t['p'])} | {t['winner'] or 'no'} |")
    g = f["grid"]
    L += ["", f"## 4. Leave-one-out grid on the {g['n_items']} non-tie numeric items (visual items never enter)", "",
          "### blend weight w (on L2) × smoothing σ", "", "| w_l2 | σ (bins) | judged | agree | in-sample |", "|---|---|---|---|---|"]
    for r in g["blend"]["table"]:
        L.append(f"| {r['w_l2']} | {r['sigma_bins']} | {r['n_judged']} | {r['n_agree']} | {_pct(r['agreement'])} |")
    b = g["blend"]
    L += ["", f"LOO agreement {_pct(b['loo_agreement'])}; LOO-selected cells `{json.dumps(b['loo_selected'])}`; in-sample best "
          f"w = {b['in_sample_best']['w_l2']}, σ = {b['in_sample_best']['sigma_bins']} bin; best vs shipped default (0.5, 0 — the as-built "
          f"`blend` smooths nothing; PLAN's 'σ = 1 bin' names the `l2s` kernel): "
          f"{b['best_vs_default']['wins_a']}–{b['best_vs_default']['wins_b']}, p = {_p(b['best_vs_default']['p'])}.", "",
          "### w1bal λ", "", "| λ | judged | agree | in-sample |", "|---|---|---|---|"]
    for r in g["w1bal"]["table"]:
        L.append(f"| {r['lambda']:g} | {r['n_judged']} | {r['n_agree']} | {_pct(r['agreement'])} |")
    wb = g["w1bal"]
    L += ["", f"LOO agreement {_pct(wb['loo_agreement'])}; in-sample best λ = {wb['in_sample_best']['lambda']}; best vs shipped "
          f"λ = {W1BAL_LAMBDA:g}: {wb['best_vs_default']['wins_a']}–{wb['best_vs_default']['wins_b']}, p = {_p(wb['best_vs_default']['p'])}.", ""]
    r = f["recommendations"]
    L += ["## 5. Recommendations (informational per DECISION 4; verdicts.json is never edited by this script)", "",
          f"- default metric: `{r['default_metric']}`",
          f"- exposed image space: `{r['exposed_visual']['current']}` → `{r['exposed_visual']['recommended']}` ({r['exposed_visual']['reason']})",
          f"- blend / w1bal parameters: w_l2 = {r['blend_params']['w_l2']}, σ = {r['blend_params']['sigma_bins']} bin, "
          f"λ = {r['blend_params']['lambda']:g} ({'changed by the fit' if r['blend_params']['changed'] else 'shipped defaults kept'})",
          f"- {r['verdicts_json']}", ""]
    return "\n".join(L)


__all__ = ["Space", "select_triplets", "write_selection", "corpus_hash", "components", "blend_from", "w1bal_from",
           "numeric_metrics_from_verdicts", "exposed_visual_from_verdicts", "responses_by_item", "metric_agrees",
           "metric_prefers", "self_agreement", "pairwise_agreement", "sign_test", "paired_test", "grid_fit", "fit",
           "synthetic_responses", "render_report"]
