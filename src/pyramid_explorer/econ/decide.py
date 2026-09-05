"""Decision rules → UI language (evals/econ/PREREG.md §7), pure JSON → JSON.

``decide`` evaluates every condition named in ``evals/econ/ui_sentences.yaml`` from ``backtest_lookalikes.json``
and ``panel_shape_growth.json`` (primary row = Query B, h = 10, k = 10), grants a level only when EVERY listed
condition holds (L0 always; L2 requires beating VT), lists the sentence ids the UI may render, renders them with
the observed numbers, and runs the deny-list over every rendered sentence and every raw template.  Nothing here
reads a file or the clock; ``scripts/decide_econ.py`` does the I/O and writes ``decision.json`` + ``RESULTS.md``.
"""
from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

PRIMARY_GROWTH = "B|10|10|growth"
PRIMARY_RETURNS = "B|10|10|returns"
PRIMARY_N3 = "10|10"
P_THRESHOLD = 0.05
PARTIAL_T, PARTIAL_H = 2015, {"pwt": 8, "maddison": 7}   # PREREG §2.1: the T = 2015 growth window ends 2023 (PWT) / 2022 (Maddison)
DUMMY = {"k": 10, "T": 2000, "h": 10, "mu_g": 2.5, "median_g": 1.5, "n_candidates": 120, "n_eff": 30, "hit_rate": 0.6,
         "country": "Country", "year": 1990, "multiple": 3.2, "n_years": 30, "index_name": "MSCI Index", "r_msci": 1.5,
         "msci_since": "1992-12-31", "max_dd": 88.6, "access_date": "2026-09-04", "ticker": "TCK", "issuer": "Issuer",
         "inception": "2000-01-01", "delisted": "2020-01-01", "B": 5000, "share_n1": 0.4, "p_n1": 0.4, "share_n2": 0.5,
         "p_n2": 0.5, "y1": 2010, "y2": 2020, "r": 3.0, "r_vt": 9.0, "benchmark_note": "", "mu": 0.5, "ci_lo": -0.5,
         "ci_hi": 1.5, "wa_addendum": "", "mu_er": -2.0, "n_investable": 12, "n_lookalikes": 40}


# ----------------------------------------------------------------------------------------------- deny list
def compile_deny_list(sentences: dict) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in sentences.get("deny_list", [])]


def scan_deny_list(text: str, patterns: list[re.Pattern], *, context: int = 30) -> list[dict]:
    """Every deny-list hit in ``text``: pattern, matched text, a little context."""
    hits = []
    for pat in patterns:
        for m in pat.finditer(text):
            a, b = max(0, m.start() - context), min(len(text), m.end() + context)
            hits.append({"pattern": pat.pattern, "match": m.group(0), "context": text[a:b].replace("\n", " ")})
    return hits


def all_templates(sentences: dict) -> dict[str, str]:
    """Every raw template string in the sentence bank keyed by ``<sentence id>[.variant]``."""
    out = {}
    for sid, s in (sentences.get("sentences") or {}).items():
        if "template" in s:
            out[sid] = s["template"]
        for key in ("fallback_no_msci", "wa_addendum_if_p2_met", "wa_addendum_otherwise"):
            if key in s:
                out[f"{sid}.{key}"] = s[key]
        for name, t in (s.get("variants") or {}).items():
            out[f"{sid}.{name}"] = t
        for name, t in (s.get("benchmark_note_values") or {}).items():
            out[f"{sid}.note.{name}"] = t
    return out


def render_template(template: str, values: dict) -> str:
    return " ".join(template.format(**values).split())


# ----------------------------------------------------------------------------------------------- conditions
def _get(d: Any, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _cond(value, ok: bool, detail: str, available: bool = True) -> dict:
    return {"value": value, "ok": bool(ok and available), "available": available, "detail": detail}


def evaluate_conditions(backtest: dict, panel: dict) -> dict[str, dict]:
    """Every condition of ``ui_sentences.yaml`` → ``{value, ok, available, detail}``.  A missing input makes the
    condition unavailable (and therefore false); the detail says which row was read."""
    g = _get(backtest, "rows", PRIMARY_GROWTH) or {}
    r = _get(backtest, "rows", PRIMARY_RETURNS) or {}
    n3 = _get(backtest, "n3", PRIMARY_N3) or {}
    gs, rs = g.get("stats") or {}, r.get("stats") or {}
    out: dict[str, dict] = {}

    mu = _num(gs.get("mean_excess"))
    out["mu_eg_gt_0"] = _cond(mu, mu > 0, f"{PRIMARY_GROWTH}.stats.mean_excess (pp/yr)", np.isfinite(mu))
    ci = gs.get("ci_headline") or [None, None]
    out["ci_headline_excludes_0"] = _cond(ci, bool(gs.get("ci_excludes_0", False)), f"{PRIMARY_GROWTH}.stats.ci_headline", ci[0] is not None)
    p1 = _num(_get(g, "nulls", "N1", "p_mean_excess"))
    out["p_n1_lt_05"] = _cond(p1, p1 < P_THRESHOLD, f"{PRIMARY_GROWTH}.nulls.N1.p_mean_excess", np.isfinite(p1))
    p2 = _num(_get(g, "nulls", "N2", "p_mean_excess"))
    out["p_n2_lt_05"] = _cond(p2, p2 < P_THRESHOLD, f"{PRIMARY_GROWTH}.nulls.N2.p_mean_excess", np.isfinite(p2))
    ne = _num(gs.get("n_eff"))
    out["n_eff_ge_20"] = _cond(ne, ne >= 20, f"{PRIMARY_GROWTH}.stats.n_eff", np.isfinite(ne))
    bD, pD = _num(_get(panel, "specs", "S3", "coef", "D", "beta")), _num(_get(panel, "specs", "S3", "coef", "D", "p_dk"))
    out["panel_s3_d_lt_0_dk_p_lt_05"] = _cond({"beta": bD, "p_dk": pD}, bD < 0 and pD < P_THRESHOLD,
                                              "panel.specs.S3.coef.D (in-sample, full sample as pre-registered; contaminated by prototype self-matching — RESULTS §5 note)",
                                              np.isfinite(bD) and np.isfinite(pD))
    o3, o0 = _num(_get(panel, "holdout", "oos_r2", "S3", "vs_mean")), _num(_get(panel, "holdout", "oos_r2", "S0", "vs_mean"))
    out["oos_r2_s3_gt_s0"] = _cond({"S3": o3, "S0": o0}, o3 > o0, "panel.holdout.oos_r2.{S3,S0}.vs_mean", np.isfinite(o3) and np.isfinite(o0))
    d3 = _num(n3.get("delta"))
    out["p2_met"] = _cond(d3, abs(d3) < 0.3, f"n3.{PRIMARY_N3}.delta (pp/yr)", np.isfinite(d3))

    mur = _num(rs.get("mean_excess"))
    out["mu_er_vs_vt_gt_0"] = _cond(mur, mur > 0, f"{PRIMARY_RETURNS}.stats.mean_excess (vs VT, pp/yr)", np.isfinite(mur))
    cir = rs.get("ci_headline") or [None, None]
    out["ci_er_headline_excludes_0"] = _cond(cir, bool(rs.get("ci_excludes_0", False)), f"{PRIMARY_RETURNS}.stats.ci_headline", cir[0] is not None)
    hh = _num(rs.get("hh_p"))
    out["hh_p_lt_05"] = _cond(hh, hh < P_THRESHOLD, f"{PRIMARY_RETURNS}.stats.hh_p", np.isfinite(hh))
    nw2, nw4 = _num(rs.get("nw2_p")), _num(rs.get("nw4_p"))
    out["nw_p_lt_05"] = _cond({"L2": nw2, "L4": nw4}, nw2 < P_THRESHOLD and nw4 < P_THRESHOLD, f"{PRIMARY_RETURNS}.stats.nw2_p and nw4_p",
                              np.isfinite(nw2) and np.isfinite(nw4))
    ew = _num(_get(r, "vs", "ew", "mean_excess"))
    out["mu_er_vs_ew_gt_0"] = _cond(ew, ew > 0, f"{PRIMARY_RETURNS}.vs.ew.mean_excess", np.isfinite(ew))
    pn1 = _num(_get(r, "nulls", "N1_investable", "p_mean_excess"))
    out["beats_n1_investable_p_lt_05"] = _cond(pn1, pn1 < P_THRESHOLD, f"{PRIMARY_RETURNS}.nulls.N1_investable.p_mean_excess", np.isfinite(pn1))
    pn4 = _num(_get(r, "nulls", "N4_investable", "p_one_sided"))
    out["beats_n4_p_lt_05"] = _cond(pn4, pn4 < P_THRESHOLD, f"{PRIMARY_RETURNS}.nulls.N4_investable.p_one_sided (paired bootstrap)", np.isfinite(pn4))
    ner = _num(rs.get("n_eff"))
    out["n_eff_returns_ge_20"] = _cond(ner, ner >= 20, f"{PRIMARY_RETURNS}.stats.n_eff", np.isfinite(ner))
    oos = _get(r, "oos_block_T_ge_2010") or {}
    out["oos_block_same_sign"] = _cond(oos.get("mean_excess_vs_vt"), bool(oos.get("same_sign_as_pooled", False)),
                                       f"{PRIMARY_RETURNS}.oos_block_T_ge_2010", bool(oos) and oos.get("n", 0) > 0)
    return out


def grant_levels(sentences: dict, conds: dict[str, dict]) -> dict[str, dict]:
    """``{level: {granted, requires, failed, unavailable}}`` — a level needs every listed condition true."""
    out = {}
    for lvl, spec in (sentences.get("levels") or {}).items():
        req = list(spec.get("requires") or [])
        unknown = [c for c in req if c not in conds]
        failed = [c for c in req if c in conds and not conds[c]["ok"]]
        unavailable = [c for c in req if c in conds and not conds[c]["available"]]
        out[lvl] = {"name": spec.get("name"), "granted": not failed and not unknown, "requires": req, "failed": failed,
                    "unavailable": unavailable, "unknown_conditions": unknown, "note": spec.get("note")}
    return out


# ----------------------------------------------------------------------------------------------- rendering
def _fmt_date(s) -> str:
    return str(s)[:10] if s else ""


def cagr_pct(r_ann_log) -> float:
    """Annualised log return (log points/yr) → compound annual growth rate in % (``100·(e^r − 1)``).  The sentence
    bank's ``%/yr`` placeholders are fed CAGRs; the RESULTS tables carry log pp/yr."""
    return 100.0 * (math.exp(_num(r_ann_log)) - 1.0)


def span_years(picks: list[dict], T: int, h: int) -> int | str:
    """The horizon actually spanned by the T growth windows: ``h`` except at ``PARTIAL_T``, where PWT rows run 8 years
    and Maddison-fallback rows 7 (PREREG §2.1) — a single value when every row has the same source, else '7–8'."""
    if int(T) != PARTIAL_T:
        return h
    hs = sorted({PARTIAL_H[str(p.get("src"))] for p in picks if int(p.get("T", -1)) == PARTIAL_T and str(p.get("src")) in PARTIAL_H})
    if len(hs) == 1:
        return hs[0]
    return f"{min(PARTIAL_H.values())}–{max(PARTIAL_H.values())}"


def render_sentences(sentences: dict, levels: dict, backtest: dict, disconnect: dict | None, conds: dict) -> dict[str, list[str]]:
    """Fill the sentence bank with the observed numbers for every granted level; returns ``{sentence id: [texts]}``.
    L0 sentences are rendered per T (what_happened), once (null), per lookalike with a fund (vs_vt, investability)
    and per disconnect row; L1/L2 only when granted.  Placeholder conventions: ``N_eff`` in a per-T sentence is that
    T's own support (distinct countries = n at that T; the pooled N_eff belongs to the pooled statistics), ``h`` is the
    span actually observed, and every ``%/yr`` market placeholder receives a CAGR (:func:`cagr_pct`), not a log return."""
    bank = sentences.get("sentences") or {}
    granted = {l for l, v in levels.items() if v["granted"]}
    out: dict[str, list[str]] = {}
    g = _get(backtest, "rows", PRIMARY_GROWTH) or {}
    r = _get(backtest, "rows", PRIMARY_RETURNS) or {}
    gs = g.get("stats") or {}

    def add(sid: str, text: str) -> None:
        out.setdefault(sid, []).append(text)

    if "L0" in granted and g:
        s = bank["L0.what_happened"]
        for T, pt in sorted((gs.get("per_T") or {}).items(), key=lambda kv: int(kv[0])):
            med = _get(g, "median_g_per_T", str(T), default=_get(g, "median_g_per_T", int(T)))
            add("L0.what_happened", render_template(s["template"], {
                "k": g["k"], "T": int(T), "h": span_years(g.get("picks") or [], int(T), int(g.get("h", 10))),
                "mu_g": _num(pt["mean_excess"]) + _num(med), "median_g": _num(med),
                "n_candidates": _get(g, "candidates_per_T", str(T), default=_get(g, "candidates_per_T", int(T), default=0)),
                "n_eff": pt.get("n", gs.get("n_eff")), "hit_rate": _num(pt.get("hit_rate"))}))
        s = bank["L0.null"]
        n1, n2 = _get(g, "nulls", "N1") or {}, _get(g, "nulls", "N2") or {}
        if n1 and n2:
            add("L0.null", render_template(s["template"], {"k": g["k"], "B": n1.get("B"), "share_n1": _num(n1.get("share_at_least_as_good")),
                                                           "p_n1": _num(n1.get("p_mean_excess")), "share_n2": _num(n2.get("share_at_least_as_good")),
                                                           "p_n2": _num(n2.get("p_mean_excess"))}))
        if r:
            sv, si = bank["L0.vs_vt"], bank["L0.investability"]
            notes = sv.get("benchmark_note_values") or {}
            for p in r.get("picks") or []:
                st = p.get("status")
                if p.get("r") is not None and st in ("investable", "liquidated_in_window"):
                    add("L0.vs_vt", render_template(sv["template"], {"ticker": p.get("ticker"), "y1": int(p["T"]), "y2": int(p["T"]) + r["h"],
                                                                     "r": cagr_pct(p["r"]), "r_vt": cagr_pct(p["r_vt"]),
                                                                     "benchmark_note": notes.get(str(p.get("benchmark")), "")}))
                var = {"investable": "liquidated" if p.get("delisted") else "live", "liquidated_in_window": "liquidated",
                       "no_fund_at_entry": "none_at_T", "no_fund_ever": "none_ever"}.get(st, "none_ever")
                add("L0.investability", render_template(si["variants"][var], {"ticker": p.get("ticker"), "issuer": p.get("issuer") or "issuer",
                                                                                "inception": _fmt_date(p.get("inception")),
                                                                                "delisted": _fmt_date(p.get("delisted")), "T": int(p["T"])}))
        if disconnect:
            sd = bank["L0.disconnect"]
            for row in disconnect.get("rows") or []:
                lv, m = row.get("levels") or {}, row.get("msci") or {}
                mult = (lv.get("multiples") or {}).get(30) or (lv.get("multiples") or {}).get("30") or lv.get("mult_last")
                n_years = 30 if ((lv.get("multiples") or {}).get(30) or (lv.get("multiples") or {}).get("30")) else (
                    (lv.get("y_last_year") or row["year"]) - row["year"])
                if mult is None or not n_years:
                    continue
                vals = {"country": row.get("name") or row["iso3"], "year": row["year"], "multiple": _num(mult), "n_years": int(n_years)}
                if m.get("state") == "ok" and m.get("ann_pct_gross_since") is not None:
                    name = str(m.get("index_name") or "MSCI")
                    name = name[:-6] if name.endswith(" Index") else name          # the template already says "index"
                    vals.update({"index_name": name, "r_msci": _num(m.get("ann_pct_gross_since")), "msci_since": m.get("since"),
                                 "max_dd": _num(m.get("max_drawdown_pct_gross")), "access_date": m.get("accessed")})
                    add("L0.disconnect", render_template(sd["template"], vals))
                else:
                    add("L0.disconnect", render_template(sd["fallback_no_msci"], vals))
    if "L1" in granted and g:
        s = bank["L1.growth_association"]
        add("L1.growth_association", render_template(s["template"], {
            "mu": gs["mean_excess"], "ci_lo": gs["ci_headline"][0], "ci_hi": gs["ci_headline"][1], "h": g["h"], "n_eff": gs["n_eff"],
            "p_n1": _get(g, "nulls", "N1", "p_mean_excess"), "p_n2": _get(g, "nulls", "N2", "p_mean_excess"),
            "wa_addendum": s["wa_addendum_if_p2_met"] if conds.get("p2_met", {}).get("ok") else s["wa_addendum_otherwise"]}))
    if "L2" in granted and r:
        s = bank["L2.returns_signal"]
        rs = r["stats"]
        add("L2.returns_signal", render_template(s["template"], {
            "mu_er": rs["mean_excess"], "ci_lo": rs["ci_headline"][0], "ci_hi": rs["ci_headline"][1], "h": r["h"], "n_eff": rs["n_eff"],
            "n_investable": rs["n"], "n_lookalikes": r.get("n_picks")}))
    return out


# ----------------------------------------------------------------------------------------------- decide
def decide(backtest: dict, panel: dict, sentences: dict, *, prereg_commit: str, disconnect: dict | None = None) -> dict:
    """The ``decision.json`` document: conditions, levels, allowed sentence ids, rendered sentences, deny-list scan."""
    conds = evaluate_conditions(backtest, panel)
    levels = grant_levels(sentences, conds)
    granted = [l for l, v in levels.items() if v["granted"]]
    bank = sentences.get("sentences") or {}
    allowed = sorted(sid for sid, s in bank.items() if s.get("level") in granted)
    rendered = render_sentences(sentences, levels, backtest, disconnect, conds)
    patterns = compile_deny_list(sentences)
    violations = []
    for sid, texts in rendered.items():
        for t in texts:
            for hit in scan_deny_list(t, patterns):
                violations.append({"where": f"rendered:{sid}", **hit})
    for sid, tpl in all_templates(sentences).items():
        for hit in scan_deny_list(tpl, patterns):
            violations.append({"where": f"template:{sid}", **hit})
        try:
            for hit in scan_deny_list(render_template(tpl, DUMMY), patterns):
                violations.append({"where": f"template-dummy:{sid}", **hit})
        except (KeyError, IndexError, ValueError):
            violations.append({"where": f"template:{sid}", "pattern": None, "match": None, "context": "template failed to render with dummy values"})
    primary = {"growth_row": PRIMARY_GROWTH, "returns_row": PRIMARY_RETURNS, "n3_row": PRIMARY_N3}
    return {"prereg_commit": prereg_commit, "primary": primary, "conditions": conds, "levels": levels, "levels_granted": granted,
            "allowed_sentence_ids": allowed, "rendered": rendered, "deny_list": [p.pattern for p in patterns],
            "deny_list_violations": violations,
            "predictions": {**(backtest.get("predictions") or {}), **(panel.get("predictions") or {})},
            "rules": {"L1": "growth association: every condition of ui_sentences.yaml levels.L1.requires",
                      "L2": "returns signal: every condition of levels.L2.requires — L2 requires beating VT (headline)",
                      "L0": "what happened next: always allowed"}}
