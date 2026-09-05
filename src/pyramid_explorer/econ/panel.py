"""Experiment 2 — shape → growth panel (evals/econ/PREREG.md §4).

Sample: country-years (c, t), WPP population ≥ 1 M, t ∈ [1950, 2013], outcome ``g_{c,t,10}`` from single-source
windows.  Regressors: ``D`` = ln of the minimum blend distance to the fixed prototype set ``P_train`` (top-decile
10-year windows ending ≤ 2003, deduped as in Experiment 1), ``WA`` = working-age share, ``dWA`` = its 10-year
change, ``lny`` = log level, SDG-region × decade fixed effects; ``D_feat`` = the same statistic under the L2
distance on z-scored ``features.py`` columns.  Specifications S0–S4, pooled OLS with Driscoll–Kraay SEs
(bandwidth 10, primary) and two-way (country, year) cluster SEs (secondary), a fixed holdout (train t ≤ 1993,
test t ∈ [2003, 2013]) with out-of-sample R² against three baselines and per-t Spearman correlations.

Implementation notes (gaps the protocol left, fixed here and reported in RESULTS.md):
* ``dWA`` needs t − 10 ≥ 1950, so the estimation sample starts at t = 1960 for every specification.
* Region × decade effects for a test decade never seen in training are carried forward from the region's latest
  training decade (the 1990s); test rows of a region absent from training are dropped and counted.
* The ``feat`` standardisation uses the pooled sample rows plus prototypes (a single reference), not per-year.
* ``D = ln(max(min d, 1e-9))``: PREREG §4 writes ``D = ln min d`` and a country-year that IS a prototype has
  ``min d = 0``, so the clip is what makes ``D`` finite.  Prototype self-matching is a property of the protocol
  (P_train is drawn from the same country-years that form the sample): ``prototype_overlap`` counts the exact
  self-matches and the rows whose outcome window shares years with an own-country prototype window, and
  ``run`` refits every specification without them (and with the smallest non-zero distance as the floor) — the
  in-sample coefficient on ``D`` is reported WITH those refits and is not, by itself, evidence; the fixed
  holdout (no self-match reaches the test block) is.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.features import NUMERIC_FEATURES
from pyramid_explorer.metrics import distances

T_RANGE = (1950, 2013)
H = 10
TRAIN_END = 1993
TEST_RANGE = (2003, 2013)
PROTO_TRAIN_END = 2003
BANDWIDTH = 10
SPECS: dict[str, list[str]] = {
    "S0": ["lny"],
    "S1": ["lny", "WA", "dWA"],
    "S2": ["lny", "D"],
    "S3": ["lny", "WA", "dWA", "D"],
    "S4": ["lny", "WA", "dWA", "D", "D_feat"],
}
REGRESSOR_NAMES = {"lny": "ln y (level at t)", "WA": "working-age share (15–64) at t", "dWA": "10-year change in WA",
                   "D": "ln min blend distance to P_train", "D_feat": "ln min feat distance to P_train"}


# ----------------------------------------------------------------------------------------------- sample
def prototypes_train(corpus: lk.Corpus, gd: lk.GrowthData, T_end: int = PROTO_TRAIN_END) -> pd.DataFrame:
    """``P_train``: Experiment 1's prototype rule evaluated once at T = 2003 (PREREG §4)."""
    return lk.prototype_set(corpus, gd, T_end)


D_CLIP = 1e-9                     # the floor under min d in the primary D (ln 1e-9 = −20.72 for an exact self-match)


def _log_min_dist(D: np.ndarray, floor: float = D_CLIP) -> np.ndarray:
    """``ln(max(min_p d, floor))`` column-wise; ``floor`` defaults to the primary clip ``D_CLIP``."""
    m = D.min(0) if D.shape[0] else np.full(D.shape[1], np.nan)
    return np.log(np.maximum(m, floor))


def smallest_nonzero(m: np.ndarray) -> float:
    """The smallest strictly positive finite value of ``m`` (the documented alternative floor); ``D_CLIP`` if none."""
    v = m[np.isfinite(m) & (m > 0)]
    return float(v.min()) if len(v) else D_CLIP


def prototype_overlap(df: pd.DataFrame, P: pd.DataFrame, *, h: int = H) -> tuple[np.ndarray, np.ndarray]:
    """Two boolean masks over ``df`` rows: ``self_match`` — the row's (iso3, t) is itself a member of ``P``
    (min d = 0, D = ln clip); ``own_overlap`` — the row's outcome window ``[t, t + h]`` shares at least one year
    with a prototype window ``[y, y + h]`` of the SAME country (``|t − y| < h``; includes the self-matches).
    Rows in ``own_overlap`` have an outcome that is partly the prototype's own top-decile growth spell."""
    by_iso = {iso: grp["year"].to_numpy(dtype=int) for iso, grp in P.groupby("iso3")}
    t = df["t"].to_numpy(dtype=int)
    iso = df["iso3"].to_numpy()
    self_match = np.zeros(len(df), dtype=bool)
    own_overlap = np.zeros(len(df), dtype=bool)
    for i in range(len(df)):
        ys = by_iso.get(iso[i])
        if ys is None:
            continue
        gap = np.abs(ys - t[i])
        self_match[i] = bool((gap == 0).any())
        own_overlap[i] = bool((gap < h).any())
    return self_match, own_overlap


def build_sample(corpus: lk.Corpus, gd: lk.GrowthData, *, t_range: tuple[int, int] = T_RANGE, minpop: float = lk.MINPOP,
                 protos: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The estimation frame ``iso3, t, g, src, lny, WA, dWA, D, D_feat, region, decade`` plus ``P_train`` and a
    coverage report.  Rows need a single-source window, a level at t, and WA at t − 10."""
    P = prototypes_train(corpus, gd) if protos is None else protos
    region = {e["id"]: str(e.get("sdg_region_locid")) for e in corpus.entities}
    parts = []
    drop = {"no_window": 0, "no_level": 0, "no_dwa": 0}
    for t in range(t_range[0], t_range[1] + 1):
        g = gd.g(t, H)
        ids = [i for i in corpus.country_ids(t, minpop) if i in set(g["iso3"])]
        if not ids:
            continue
        gi = g.set_index("iso3").loc[ids]
        rows = corpus.rows(ids, t)
        f = corpus.feats.iloc[rows]
        df = pd.DataFrame({"iso3": ids, "t": t, "g": gi["g"].to_numpy(dtype=np.float64), "src": gi["src"].to_numpy(),
                           "row": rows, "WA": f["wa"].to_numpy(dtype=np.float64)})
        df["lny"] = gd.lny(ids, t)
        if t - H >= corpus.keys["year"].min():
            df["dWA"] = df["WA"].to_numpy() - corpus.feats.iloc[corpus.rows(ids, t - H)]["wa"].to_numpy(dtype=np.float64)
        else:
            df["dWA"] = np.nan
        parts.append(df)
    s = pd.concat(parts, ignore_index=True)
    drop["no_level"] = int(s["lny"].isna().sum())
    drop["no_dwa"] = int(s["dWA"].isna().sum() - (s["lny"].isna() & s["dWA"].isna()).sum())
    s = s.dropna(subset=["lny", "dWA"]).reset_index(drop=True)
    # distances to the fixed prototype set
    prow = P["row"].to_numpy()
    Dm = lk.proto_distance_matrix(corpus, prow, s["row"].to_numpy())
    s["D"] = _log_min_dist(Dm)
    dmin = Dm.min(0) if Dm.shape[0] else np.full(Dm.shape[1], np.nan)
    d_floor = smallest_nonzero(dmin)
    s["D_floor"] = _log_min_dist(Dm, d_floor)                     # robustness: smallest non-zero distance as the floor
    s["self_match"], s["own_overlap"] = prototype_overlap(s, P)
    F = corpus.feats[NUMERIC_FEATURES].to_numpy(dtype=np.float64)
    ref = np.concatenate([s["row"].to_numpy(), prow])
    mu, sd = np.nanmean(F[ref], 0), np.nanstd(F[ref], 0)
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)
    Zs, Zp = (F[s["row"].to_numpy()] - mu) / sd, (F[prow] - mu) / sd
    Zs, Zp = np.nan_to_num(Zs), np.nan_to_num(Zp)
    Df = np.sqrt(((Zp[:, None, :] - Zs[None, :, :]) ** 2).sum(-1))
    s["D_feat"] = _log_min_dist(Df)
    s["region"] = s["iso3"].map(region).fillna("none")
    s["decade"] = (s["t"] // 10) * 10
    s["fe"] = s["region"] + "|" + s["decade"].astype(str)
    g_top = float(np.quantile(s["g"], 0.9))
    sm = s["self_match"].to_numpy()
    report = {"n": int(len(s)), "n_countries": int(s["iso3"].nunique()), "t_min": int(s["t"].min()), "t_max": int(s["t"].max()),
              "n_prototypes": int(len(P)), "dropped": drop, "src_counts": {str(k): int(v) for k, v in s["src"].value_counts().items()},
              # prototype self-matching diagnostics (see the module docstring): counts, shares, leverage
              "n_self_match": int(sm.sum()), "share_self_match_top_decile_g": float((s.loc[sm, "g"] >= g_top).mean()) if sm.any() else float("nan"),
              "n_own_prototype_overlap": int(s["own_overlap"].sum()), "share_own_prototype_overlap": float(s["own_overlap"].mean()),
              "self_match_t_max": int(s.loc[sm, "t"].max()) if sm.any() else None,
              "d_clip": D_CLIP, "D_at_clip": float(np.log(D_CLIP)), "d_floor_smallest_nonzero": d_floor, "D_at_floor": float(np.log(d_floor)),
              "D_quantiles": {str(q): float(np.quantile(s["D"], q)) for q in (0.01, 0.05, 0.5, 0.95)},
              "mean_g_own_overlap": float(s.loc[s["own_overlap"], "g"].mean()) if s["own_overlap"].any() else float("nan"),
              "mean_g_other": float(s.loc[~s["own_overlap"], "g"].mean())}
    return s, P, report


# ----------------------------------------------------------------------------------------------- estimation
def design(df: pd.DataFrame, spec: str, fe_levels: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    """Design matrix: the spec's continuous regressors followed by one dummy per region×decade cell (no intercept).
    ``fe_levels`` fixes the dummy columns (holdout); rows whose cell is not a level get all-zero dummies."""
    cont = SPECS[spec]
    levels = fe_levels if fe_levels is not None else sorted(df["fe"].unique())
    pos = {l: i for i, l in enumerate(levels)}
    Dm = np.zeros((len(df), len(levels)))
    idx = df["fe"].map(pos)
    ok = idx.notna().to_numpy()
    Dm[np.flatnonzero(ok), idx[ok].astype(int).to_numpy()] = 1.0
    X = np.column_stack([df[cont].to_numpy(dtype=np.float64), Dm])
    return X, cont + [f"fe:{l}" for l in levels]


def fit_specs(df: pd.DataFrame, *, stats=None, bandwidth: int = BANDWIDTH, d_col: str = "D") -> dict[str, dict]:
    """Pooled OLS per spec with Driscoll–Kraay (primary) and two-way cluster (secondary) inference.  Returns
    ``{spec: {'coef': {name: {beta, se_dk, p_dk, se_2way, p_2way}}, 'r2', 'n', 'n_fe'}}`` (continuous terms only
    in ``coef``; the FE dummies are estimated but not reported).  ``d_col`` swaps the column used for ``D``
    (``'D_floor'`` for the smallest-non-zero-floor robustness refit); the term keeps the name ``D``."""
    st = lk._stats(stats)
    if d_col != "D":
        df = df.drop(columns=["D"]).rename(columns={d_col: "D"})
    y = df["g"].to_numpy(dtype=np.float64)
    out: dict[str, dict] = {}
    for spec, cont in SPECS.items():
        X, names = design(df, spec)
        dk = st.driscoll_kraay_ols(X, y, df["t"].to_numpy(), bandwidth)
        tw = st.twoway_cluster_ols(X, y, df["iso3"].to_numpy(), df["t"].to_numpy())
        coef = {}
        for j, name in enumerate(cont):
            coef[name] = {"beta": float(dk["beta"][j]), "se_dk": float(dk["se"][j]), "p_dk": float(dk["p"][j]),
                          "se_2way": float(tw["se"][j]), "p_2way": float(tw["p"][j])}
        out[spec] = {"coef": coef, "r2": float(dk["r2"]), "n": int(len(y)), "n_fe": len(names) - len(cont), "regressors": cont}
    return out


def _ols_fit_predict(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray) -> np.ndarray:
    beta = np.linalg.pinv(Xtr.T @ Xtr) @ Xtr.T @ ytr
    return Xte @ beta


def holdout(df: pd.DataFrame, *, train_end: int = TRAIN_END, test_range: tuple[int, int] = TEST_RANGE) -> dict[str, Any]:
    """Fixed holdout: fit every spec on t ≤ train_end, predict t ∈ test_range.  Region × decade effects unseen in
    training are carried forward from the region's latest training decade.  Reports OOS R² of each spec against
    the training mean, S0 and S1 (``1 − SSE_spec / SSE_baseline``), and per-t Spearman(pred, realised)."""
    tr = df[df["t"] <= train_end].copy()
    te = df[(df["t"] >= test_range[0]) & (df["t"] <= test_range[1])].copy()
    latest = tr.groupby("region")["decade"].max()
    te["fe"] = te["region"].map(lambda r: f"{r}|{int(latest[r])}" if r in latest.index else "__none__")
    n_dropped = int((te["fe"] == "__none__").sum())
    te = te[te["fe"] != "__none__"]
    levels = sorted(tr["fe"].unique())
    ytr, yte = tr["g"].to_numpy(dtype=np.float64), te["g"].to_numpy(dtype=np.float64)
    preds: dict[str, np.ndarray] = {"mean": np.full(len(te), ytr.mean())}
    for spec in SPECS:
        Xtr, _ = design(tr, spec, levels)
        Xte, _ = design(te, spec, levels)
        preds[spec] = _ols_fit_predict(Xtr, ytr, Xte)
    sse = {k: float(((yte - p) ** 2).sum()) for k, p in preds.items()}
    oos_r2 = {spec: {"vs_mean": 1 - sse[spec] / sse["mean"], "vs_s0": 1 - sse[spec] / sse["S0"], "vs_s1": 1 - sse[spec] / sse["S1"]}
              for spec in SPECS}
    spearman: dict[str, dict] = {}
    for spec in SPECS:
        per_t = {}
        for t, g in te.groupby("t"):
            idx = g.index
            pos = te.index.get_indexer(idx)
            if len(pos) >= 3:
                rho = spearmanr(preds[spec][pos], yte[pos]).statistic
                per_t[int(t)] = float(rho) if np.isfinite(rho) else float("nan")
        vals = [v for v in per_t.values() if np.isfinite(v)]
        spearman[spec] = {"per_t": per_t, "mean": float(np.mean(vals)) if vals else float("nan"),
                          "share_positive": float(np.mean([v > 0 for v in vals])) if vals else float("nan")}
    return {"train": {"t_max": train_end, "n": int(len(tr)), "n_countries": int(tr["iso3"].nunique())},
            "test": {"t_range": list(test_range), "n": int(len(te)), "n_countries": int(te["iso3"].nunique()), "n_dropped_no_region_fe": n_dropped},
            "fe_rule": "region × decade effects for unseen test decades carried forward from the region's latest training decade",
            "sse": sse, "oos_r2": oos_r2, "spearman": spearman}


# ----------------------------------------------------------------------------------------------- predictions
ROBUSTNESS = {"ex_selfmatch": "drop the exact self-match rows (the row's (iso3, t) is a prototype; D = ln 1e-9)",
              "ex_overlap": "drop every row whose outcome window shares years with an own-country prototype window (|t − y| < 10)",
              "floor": "full sample, D floored at the smallest non-zero min-distance instead of 1e-9 (no −20.72 leverage points)"}


def robustness_refits(df: pd.DataFrame, *, stats=None, bandwidth: int = BANDWIDTH) -> dict[str, dict]:
    """The three prototype-self-matching refits of :data:`ROBUSTNESS`, each ``{'rule', 'n', 'specs'}`` with the same
    layout as :func:`fit_specs`.  Reported next to the primary coefficients, never in their place."""
    out = {}
    for key, rule in ROBUSTNESS.items():
        if key == "ex_selfmatch":
            sub, d_col = df[~df["self_match"]], "D"
        elif key == "ex_overlap":
            sub, d_col = df[~df["own_overlap"]], "D"
        else:
            sub, d_col = df, "D_floor"
        out[key] = {"rule": rule, "n": int(len(sub)), "specs": fit_specs(sub, stats=stats, bandwidth=bandwidth, d_col=d_col)}
    return out


def evaluate_predictions(specs: dict, ho: dict, robustness: dict | None = None, sample: dict | None = None) -> dict:
    """P6–P8 (PREREG §3.8) with observed values and ``met``.  P6 is evaluated on S3 (the spec named by L1) and S1
    is reported beside it.  P7's first clause is evaluated exactly as pre-registered (S3 β_D < 0 on the full
    sample) and carries a ``note`` naming it an artifact of prototype self-matching, with the ``ex_overlap`` refit
    beside it when ``robustness`` is given."""
    out = {}
    s3, s1 = specs["S3"]["coef"], specs["S1"]["coef"]
    comps = {name: {"beta": s3[name]["beta"], "p_dk": s3[name]["p_dk"], "ok": bool(s3[name]["beta"] > 0 and s3[name]["p_dk"] < 0.05)}
             for name in ("WA", "dWA")}
    out["P6"] = {"statement": "WA, ΔWA > 0 (Driscoll–Kraay p < .05)", "spec": "S3", "components": comps,
                 "S1": {name: {"beta": s1[name]["beta"], "p_dk": s1[name]["p_dk"]} for name in ("WA", "dWA")},
                 "met": all(c["ok"] for c in comps.values())}
    d_r2 = specs["S3"]["r2"] - specs["S1"]["r2"]
    oos_gain = ho["oos_r2"]["S3"]["vs_s1"]
    d_comp = {"beta": s3["D"]["beta"], "p_dk": s3["D"]["p_dk"], "ok": bool(s3["D"]["beta"] < 0)}
    note = "artifact — see §5 note: the in-sample coefficient on D is driven by prototype self-matching and is not evidence"
    if robustness and "ex_overlap" in robustness:
        ex = robustness["ex_overlap"]["specs"]["S3"]["coef"]["D"]
        sm = sample or {}
        note += (f" ({sm.get('n_self_match', '?')} rows are their own nearest prototype, {100 * float(sm.get('share_own_prototype_overlap', float('nan'))):.1f} % "
                 f"share an outcome window with an own-country prototype window; without the latter β_D = {ex['beta']:+.5f}, DK p = {ex['p_dk']:.3f})")
    d_comp["note"] = note
    comps7 = {"D_lt_0_in_sample": d_comp,
              "delta_r2_s3_s1_lt_.03": {"value": d_r2, "ok": bool(d_r2 < 0.03)},
              "oos_gain_s3_over_s1_lt_.02": {"value": oos_gain, "ok": bool(oos_gain < 0.02)}}
    out["P7"] = {"statement": "D < 0 in-sample but ΔR²(S3 − S1) < .03 and OOS gain < .02", "components": comps7,
                 "met": all(c["ok"] for c in comps7.values())}
    v = ho["oos_r2"]["S1"]["vs_s0"]
    out["P8"] = {"statement": "OOS R²(S1 over S0) ∈ [.02, .10]", "value": v, "met": bool(np.isfinite(v) and 0.02 <= v <= 0.10)}
    return out


def run(corpus: lk.Corpus, gd: lk.GrowthData, *, stats=None, log=None) -> tuple[dict, pd.DataFrame]:
    """Experiment 2 end to end → ``(panel_shape_growth.json dict, tables/panel_coefs.csv frame)``."""
    st = lk._stats(stats)
    say = log or (lambda s: None)
    say("[exp2] sample")
    df, P, report = build_sample(corpus, gd)
    say(f"[exp2] n={report['n']} countries={report['n_countries']} prototypes={report['n_prototypes']}")
    n_eff = int(st.n_eff(df.rename(columns={"t": "T"})[["iso3", "T"]], H, T0=T_RANGE[0]))
    say("[exp2] specs")
    specs = fit_specs(df, stats=st)
    say("[exp2] holdout")
    ho = holdout(df)
    say(f"[exp2] self-match refits (n_self_match={report['n_self_match']}, own-overlap={report['n_own_prototype_overlap']})")
    rob = robustness_refits(df, stats=st)
    # no exact self-match may sit in the test block (train ≤ 1993, test ≥ 2003, P_train windows end ≤ 2003 → y ≤ 1993)
    te = df[(df["t"] >= TEST_RANGE[0]) & (df["t"] <= TEST_RANGE[1])]
    report["n_self_match_in_test_block"] = int(te["self_match"].sum())
    report["n_own_prototype_overlap_in_test_block"] = int(te["own_overlap"].sum())
    preds = evaluate_predictions(specs, ho, rob, report)
    corr = df[["g", "lny", "WA", "dWA", "D", "D_feat"]].corr().round(4)
    result = {
        "_meta": {"t_range": list(T_RANGE), "h": H, "minpop_thousands": lk.MINPOP, "bandwidth_dk": BANDWIDTH,
                  "prototype_train_end": PROTO_TRAIN_END, "specs": SPECS, "regressor_names": REGRESSOR_NAMES,
                  "fe": "SDG region (WPP sdg_region_locid) × decade", "units": "g in log points/yr; coefficients per unit regressor",
                  "implementation_notes": [
                      "dWA needs t − 10 ≥ 1950, so every specification is estimated on t ≥ 1960 (same sample for all specs)",
                      ho["fe_rule"],
                      "D_feat standardises the 13 numeric features once over the pooled sample rows plus the prototypes",
                      f"D = ln(max(min d, {D_CLIP:g})): PREREG §4 writes ln min d, and a country-year that is itself a prototype has min d = 0, "
                      f"so the clip makes D finite (ln {D_CLIP:g} = {np.log(D_CLIP):.2f}); the smallest non-zero min-distance "
                      f"({report['d_floor_smallest_nonzero']:.4g}, ln = {np.log(report['d_floor_smallest_nonzero']):.2f}) is the documented alternative floor, reported as the 'floor' refit",
                      "Prototype self-matching (P_train is drawn from the sample's own country-years, as §4 specifies): the in-sample coefficient on D "
                      "is reported together with three refits (drop exact self-matches; drop rows whose outcome window shares years with an own-country "
                      "prototype window; smallest-non-zero floor) and is not treated as evidence — only the fixed holdout, which contains no self-match, is",
                  ]},
        "sample": {**report, "n_eff": n_eff, "n_eff_rule": "distinct (country, floor((t − 1950)/10)) pairs"},
        "prototypes_train": P[["iso3", "year", "g"]].to_dict("records"),
        "specs": specs,
        "robustness": rob,
        "delta_r2_s3_s1": specs["S3"]["r2"] - specs["S1"]["r2"],
        "holdout": ho,
        "correlations": {c: corr[c].to_dict() for c in corr.columns},
        "predictions": preds,
    }
    rows = [{"spec": spec, "term": name, **vals, "r2": specs[spec]["r2"], "n": specs[spec]["n"]}
            for spec in SPECS for name, vals in specs[spec]["coef"].items()]
    for key, r in rob.items():                       # robustness refits: spec suffix _ex_selfmatch / _ex_overlap / _floor
        rows += [{"spec": f"{spec}_{key}", "term": name, **vals, "r2": r["specs"][spec]["r2"], "n": r["specs"][spec]["n"]}
                 for spec in SPECS for name, vals in r["specs"][spec]["coef"].items()]
    return result, pd.DataFrame(rows)
