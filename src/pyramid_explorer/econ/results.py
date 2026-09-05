"""Render ``evals/econ/RESULTS.md`` (PREREG §10 order) from the experiment documents.

Pure text generation: ``render_results(ctx)`` takes the loaded JSON documents plus run metadata and returns the
Markdown.  The wording follows the sentence-bank rules (past tense, numeric, N_eff beside every statistic, VT over
the same window on every market number); ``scripts/decide_econ.py`` runs the deny-list over the rendered file.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np

VINTAGE_PARAGRAPH = (
    "**Vintage statement (PREREG §8).** The pyramids used to select lookalikes as of T are WPP 2024 back-series, i.e. "
    "today's estimates of what the age structure *was* — not what was known at T. The selection is therefore "
    "hindsight-free with respect to the **outcome** (prototype windows end ≤ T; growth and returns are observed after T) "
    "but not with respect to the **demographic input**. The optional `--vintage` re-run (WPP 2010 / WPP 2000 archive "
    "files as the input for T ≤ 2010 / T ≤ 2000, pre-registered check: k = 10 Jaccard overlap ≥ 0.6 at every T where an "
    "archive exists) {vintage_status}"
)


def _f(x, nd: int = 2, sign: bool = False, pct: bool = False) -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if not np.isfinite(v):
        return "n/a"
    if pct:
        return f"{100 * v:.{nd if nd != 2 else 0}f} %"
    return f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"


def _pp(x, nd: int = 2) -> str:
    """A fraction (log return / share) as signed pp; None-safe."""
    return "—" if x is None else _f(100 * float(x), nd, True)


def _ci(c) -> str:
    if not c or c[0] is None or c[1] is None:
        return "n/a"
    return f"[{_f(c[0], 2, True)}, {_f(c[1], 2, True)}]"


def _p(x) -> str:
    return _f(x, 3)


def _met(b) -> str:
    return "**met**" if b else "**not met**"


def _table(header: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _counts(d: dict | None) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted((d or {}).items())) or "—"


# ----------------------------------------------------------------------------------------------- sections
def _sec_header(ctx: dict) -> str:
    m = ctx.get("run") or {}
    lines = ["# Economic-lens backtest — RESULTS", "",
             f"**PREREG commit:** `{ctx['prereg_commit']}` (`evals/econ/PREREG.md`, frozen; this file cites it and `decision.json` carries it as `prereg_commit`).",
             f"**Generated:** {m.get('generated_at', 'n/a')} · code revision `{m.get('git_rev', 'n/a')}` · seed {m.get('seed', 20260904)} · B = {m.get('B', 5000)}.",
             "", "Everything below is past tense and numeric. Every market number stands next to VT over the same window "
             "(VT proxy before 2008-06-24, PREREG §3.5); N_eff (distinct country × non-overlapping h-block pairs) is printed beside every statistic; "
             "status counts stand beside every return statistic. Nothing here is a forecast.", ""]
    return "\n".join(lines)


def _sec_data(ctx: dict) -> str:
    rows = []
    for s in ctx.get("sources") or []:
        rows.append([s.get("id"), s.get("family"), s.get("vintage") or "—", s.get("licence") or "—",
                     "yes" if s.get("redistributable") else "no", str(s.get("fetched_at") or "—"), (s.get("sha256") or "—")[:12]])
    lines = ["## 1. Data vintages and fetch dates", ""]
    if rows:
        lines.append(_table(["source", "family", "vintage", "licence", "shipped", "fetched", "sha256"], rows))
    else:
        lines.append("_No source table available in this run (DuckDB store absent)._")
    bt = ctx.get("backtest") or {}
    meta = bt.get("_meta") or {}
    lines += ["", f"Growth series: PWT 11.0 `rgdpna/pop` (primary), Maddison 2023 `gdppc` (fallback, never mixed inside a window); "
              f"level: PWT `rgdpe/pop` else Maddison. Population floor {meta.get('minpop_thousands', 1000):.0f} k (WPP 2024). "
              f"T = 2015 growth windows are partial (PWT h = 8 → 2023, Maddison h = 7 → 2022) and flagged.", ""]
    cands = bt.get("candidates") or {}
    if cands:
        keys = sorted(cands)
        Ts = sorted({int(t) for k in keys for t in cands[k]})
        lines.append(_table(["candidate set C(T)", *[str(t) for t in Ts]],
                            [[k.replace("|", ", "), *[cands[k].get(str(t), cands[k].get(t, "—")) for t in Ts]] for k in keys]))
        lines.append("")
    return "\n".join(lines)


def _sec_universe(ctx: dict) -> str:
    u = ctx.get("universe") or {}
    entries = u.get("entries") or []
    rows = [[e.get("ticker"), e.get("iso3") or "—", e.get("role"), e.get("inception"), e.get("inception_verified", "—"),
             e.get("status"), e.get("delisted") or "—", "—" if e.get("discrepancy_days") is None else e.get("discrepancy_days"), e.get("yahoo_symbol") or "—"] for e in entries]
    lines = ["## 2. ETF universe and the survivorship guard", "",
             f"{len(entries)} instruments, hand-curated before any fetch (`etf_universe.yaml`, as of {u.get('as_of', 'n/a')}); no ticker was added or removed.", "",
             _table(["ticker", "iso3", "role", "inception", "verified", "status", "delisted", "Δ days (Yahoo − issuer)", "yahoo symbol"], rows), ""]
    disc = [e for e in entries if isinstance(e.get("discrepancy_days"), (int, float)) and abs(e["discrepancy_days"]) > 45]
    lines.append("Discrepancies > 45 days between the issuer inception and Yahoo's first bar: " +
                 (", ".join(f"{e['ticker']} ({e['discrepancy_days']} d — {e.get('note') or 'see yaml'})" for e in disc) if disc else "none recorded in the yaml."))
    lines.append("")
    g = ctx.get("guard")
    lines.append("### Guard report (per ticker)")
    lines.append("")
    if isinstance(g, dict) and g:
        per = g.get("tickers") or g.get("per_ticker") or g
        rows = []
        for tk, v in sorted(per.items()):
            if not isinstance(v, dict):
                continue
            res = "passed" if v.get("passed") is True else ("FAILED" if v.get("passed") is False else v.get("status", v.get("result", "—")))
            rows.append([tk, res, v.get("n_bars", "—"), str(v.get("first_bar", "—"))[:10], str(v.get("last_bar", "—"))[:10],
                         ", ".join(v.get("violations") or v.get("failed") or []) or "—", v.get("route", v.get("source", "—")), v.get("deviation") or "—"])
        lines.append(_table(["ticker", "result", "bars", "first bar", "last bar", "assertions noted", "route", "deviation"], rows) if rows else "_guard report present but empty_")
        run = g.get("run") or {}
        if run:
            lines += ["", f"Guard run {run.get('at', g.get('generated_at', ''))}: {run.get('n_tickers', len(rows))} tickers, failures {run.get('failures', [])}, "
                      f"cross-check failures {run.get('crosscheck_failures', 'n/a')}. 'Assertions noted' lists A4 signatures for delisted tickers routed to the manual NAV ladder; "
                      f"a ticker passes when every applicable assertion holds."]
        if g.get("crosscheck"):
            lines += ["", "Cross-check vs issuer factsheets (`etf_crosscheck.yaml`, |Δ| ≤ 0.5 pp/yr):", "",
                      _table(["ticker", "figure", "as of", "published %/yr", "computed %/yr", "Δ pp", "passed"],
                             [[c.get("ticker"), c.get("figure"), str(c.get("as_of", ""))[:10], _f(c.get("published_pct", c.get("published"))),
                               _f(c.get("computed_pct", c.get("computed"))), _f(c.get("delta_pp", c.get("delta")), 3, True), c.get("passed", c.get("ok"))] for c in g["crosscheck"]])]
    else:
        lines.append(f"_{ctx.get('guard_note') or 'No guard report file was found; see the fetch_etf console output.'}_")
    lines.append("")
    return "\n".join(lines)


def _sec_predictions(ctx: dict) -> str:
    preds = (ctx.get("decision") or {}).get("predictions") or {}
    lines = ["## 3. Pre-registered predictions (P1–P8, PREREG §3.8) — observed vs stated", ""]
    rows = []
    for pid in ("P1", "P2", "P3", "P3b", "P4", "P5", "P6", "P7", "P8"):
        p = preds.get(pid)
        if not p:
            rows.append([pid, "—", "not evaluated (input missing)", "—"])
            continue
        obs = []
        for k in ("value", "delta", "ci_headline", "ew_minus_vt_pp_per_yr"):
            if k in p and p[k] is not None:
                obs.append(f"{k} = {_ci(p[k]) if k == 'ci_headline' else (p[k] if isinstance(p[k], dict) else _f(p[k], 3))}")
        for k, c in (p.get("components") or {}).items():
            v = c.get("value", {kk: vv for kk, vv in c.items() if kk not in ("ok", "note")})
            if isinstance(v, dict):
                v = ", ".join(f"{a}={_ci(b) if isinstance(b, list) else (_f(b, 3) if isinstance(b, (int, float)) else b)}" for a, b in v.items())
            elif isinstance(v, list):
                v = _ci(v)
            else:
                v = _f(v, 3)
            obs.append(f"{k}: {v} → {'ok' if c.get('ok') else 'no'}" + (f" ({c['note']})" if c.get("note") else ""))
        for k, c in (p.get("soft") or {}).items():
            obs.append(f"{k}: {_f(c.get('value'), 3)} (observed {'true' if c.get('observed_true') else 'false'}; soft clause, not in met)")
        rows.append([pid, p.get("statement", ""), "<br>".join(obs) or "—", _met(p.get("met"))])
    lines.append(_table(["id", "pre-registered statement", "observed", "verdict"], rows))
    lines.append("")
    return "\n".join(lines)


def _row_block(key: str, row: dict) -> list[str]:
    s = row.get("stats") or {}
    lines = [f"### {row.get('query_name', row.get('query'))} — k = {row['k']}, h = {row['h']}, {row['outcome']}", ""]
    head = (f"n = {s.get('n')} lookalike-windows over T ∈ {{{', '.join(str(t) for t in row.get('T_values', []))}}} · **N_eff = {s.get('n_eff')}**"
            + (f" · partial (T = 2015) rows: {row.get('n_partial')}" if row.get("n_partial") else ""))
    if row["outcome"] == "returns":
        head += f" · status counts: {_counts(row.get('status_counts'))} · benchmark: {', '.join(row.get('benchmark') or [])}"
    lines += [head, ""]
    lines.append(_table(["statistic", "value"], [
        ["hit rate (e > 0; chance .5)", _f(s.get("hit_rate"), 2)],
        ["top-quartile rate (chance .25)", _f(s.get("top_quartile_rate"), 2)],
        ["mean excess μ̂ (pp/yr)" + (" vs VT" if row["outcome"] == "returns" else " vs candidate median"), f"{_f(s.get('mean_excess'), 2, True)} (per-T average {_f(s.get('mean_excess_T_avg'), 2, True)})"],
        ["naive SE / p", f"{_f(s.get('naive_se'))} / {_p(s.get('naive_p'))}"],
        [f"Hansen–Hodrick SE (L = {s.get('hh_L', '—')}) / p", f"{_f(s.get('hh_se'))} / {_p(s.get('hh_p'))}"],
        ["Newey–West SE L = 2 / p", f"{_f(s.get('nw2_se'))} / {_p(s.get('nw2_p'))}"],
        ["Newey–West SE L = 4 / p", f"{_f(s.get('nw4_se'))} / {_p(s.get('nw4_p'))}"],
        ["country-cluster SE (one-way, cluster = country across T; PREREG §3.6 item 6) / p", f"{_f(s.get('cluster_se'))} / {_p(s.get('cluster_p'))}"],
        [f"within-country Bartlett kernel SE (L = {s.get('cluster_hac_L', s.get('hh_L', '—'))} grid step{'s' if s.get('cluster_hac_L', 1) != 1 else ''}; not the plain cluster SE) / p",
         f"{_f(s.get('cluster_hac_se'))} / {_p(s.get('cluster_hac_p'))}"],
        ["bootstrap 95 % CI — country cluster", _ci(s.get("ci_country_cluster"))],
        ["bootstrap 95 % CI — circular T blocks", _ci(s.get("ci_block_T")) + (" — degenerate: block length ≥ number of T's, every resample is the full series; "
                                                                             "the country-cluster CI is the only informative scheme" if s.get("ci_block_T_degenerate") else "")],
        ["**headline CI (wider)**", f"**{_ci(s.get('ci_headline'))}** — " + ("degenerate (n < 2 or a single country): no interval, 0 not evaluable"
                                                                             if s.get("ci_degenerate") else ("excludes 0" if s.get("ci_excludes_0") else "includes 0"))],
        ["N_eff", str(s.get("n_eff"))],
    ]))
    per = s.get("per_T") or {}
    if per:
        lines += ["", "Per T: " + "; ".join(f"{T}: {_f(v.get('mean_excess'), 2, True)} (n {v.get('n')}, hit {_f(v.get('hit_rate'), 2)})" for T, v in sorted(per.items(), key=lambda kv: int(kv[0])))]
    nulls = row.get("nulls") or {}
    nrows = []
    for name, nv in nulls.items():
        if "p_mean_excess" in nv:
            nrows.append([name, _p(nv.get("p_mean_excess")), _p(nv.get("p_hit_rate")), _f(nv.get("null_mean"), 2, True), _f(nv.get("share_at_least_as_good"), 2), nv.get("B", "—")])
        elif "p_one_sided" in nv:
            pb = nv.get("paired_vs_picks") or {}
            nrows.append([name + " (paired bootstrap Δ vs comparator)", _p(nv.get("p_one_sided")), "—", _f(nv.get("mean_excess_N4", (nv.get("stats") or {}).get("mean_excess")), 2, True),
                          f"Δ = {_f(pb.get('delta'), 2, True)} CI {_ci(pb.get('ci_headline'))}", pb.get("B", "—")])
    if nrows:
        lines += ["", _table(["null model", "one-sided p (mean excess)", "p (hit rate)", "null / comparator mean (pp/yr)", "share of draws ≥ observed / Δ", "B"], nrows)]
    if row["outcome"] == "returns":
        vs = row.get("vs") or {}
        lines += ["", _table(["vs benchmark", "n", "mean excess (pp/yr)", "naive SE", "hit rate", "headline CI"],
                             [[k.upper(), v.get("n"), _f(v.get("mean_excess"), 2, True), _f(v.get("naive_se")), _f(v.get("hit_rate"), 2), _ci(v.get("ci_headline"))] for k, v in vs.items()])]
        oos = row.get("oos_block_T_ge_2010") or {}
        lines += ["", f"Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = {oos.get('n')}, mean excess vs VT {_f(oos.get('mean_excess_vs_vt'), 2, True) if oos.get('mean_excess_vs_vt') is not None else 'n/a'} pp/yr, "
                  f"same sign as pooled: {oos.get('same_sign_as_pooled')}.",
                  f"Investable share per T: " + ", ".join(f"{T}: {_f(v, 2)}" for T, v in sorted((row.get('investable_share_per_T') or {}).items(), key=lambda kv: int(kv[0]))) + ".",
                  f"Status counts per T: " + "; ".join(f"{T}: {_counts(v)}" for T, v in sorted((row.get('status_counts_per_T') or {}).items(), key=lambda kv: int(kv[0]))) + "."]
        inc = row.get("ladder_incomplete") or []
        if inc:
            lines.append("NAV-ladder gaps (liquidated funds whose manual ladder does not cover the whole window; the uncovered span is held at 0 % — value carried, never dropped): "
                         + "; ".join(f"{i.get('iso3')} {i.get('T')} {i.get('ticker')} [{i.get('spans')}]" for i in inc) + ".")
    picks = row.get("picks") or []
    if picks:
        byT: dict[int, list[str]] = {}
        for p in picks:
            tag = p["iso3"]
            if row["outcome"] == "returns":
                tag += f" ({p.get('ticker') or p.get('status')}" + (f" {_pp(p['er'], 1)}" if p.get("er") is not None else "") + ")"
            else:
                tag += f" ({_pp(p.get('eg'), 1)})"
            byT.setdefault(int(p["T"]), []).append(tag)
        lines += ["", "Lookalikes per T (" + ("excess vs VT, pp/yr" if row["outcome"] == "returns" else "excess growth vs the candidate median, pp/yr") + "):"]
        lines += [f"- {T}: " + ", ".join(v) for T, v in sorted(byT.items())]
    lines.append("")
    return lines


def _sec_exp1(ctx: dict) -> str:
    bt = ctx.get("backtest") or {}
    rows = bt.get("rows") or {}
    lines = ["## 4. Experiment 1 — lookalike-as-of-T", ""]
    if not rows:
        lines.append("_Not run._")
        return "\n".join(lines)
    meta = bt.get("_meta") or {}
    lines += [f"T grid {meta.get('T_grid')}; growth horizons {meta.get('growth_T')}; returns for T ∈ {meta.get('returns_T') or 'not computed in this run'} (h = 10). "
              f"{meta.get('returns_note', '').rstrip('.')}. Rows for T = 1990 and 1995 have no return statistic: no US-listed single-country ETF existed at entry (first WEBS 1996-03).", ""]
    protos = bt.get("prototypes") or {}
    if protos:
        lines += ["### Prototype sets P(T) (Query B)", ""]
        lines.append(_table(["T", "|P(T)|", "members (country year), highest growth first"],
                            [[T, len(P), ", ".join(f"{p['iso3']} {p['year']}" for p in P)] for T, P in sorted(protos.items(), key=lambda kv: int(kv[0]))]))
        lines.append("")
    bench = bt.get("benchmarks") or {}
    if bench:
        lines += ["### Benchmarks per returns window (annualised log return, pp/yr)", ""]
        lines.append(_table(["T", "VT / proxy", "benchmark", "equal-weight investable basket (n)", "SPY", "EFA", "EEM"],
                            [[T, _pp(b['vt'].get('r_ann')), b["vt"].get("benchmark"),
                              f"{_pp((b.get('ew') or {}).get('r_ann'))} ({(b.get('ew') or {}).get('n')})",
                              *[_pp((b.get('refs') or {}).get(tk)) for tk in ("SPY", "EFA", "EEM")]]
                             for T, b in sorted(bench.items(), key=lambda kv: int(kv[0]))]))
        lines.append("")
        legs = []
        for T, b in sorted(bench.items(), key=lambda kv: int(kv[0])):
            v = b.get("vt") or {}
            for leg in b.get("vt_legs") or []:
                legs.append([T, str(leg.get("from", ""))[:10], str(leg.get("to", ""))[:10],
                             ", ".join(f"{tk} {int(round(100 * w))} %" for tk, w in (leg.get("weights") or {}).items())])
            if not b.get("vt_legs"):
                legs.append([T, str(v.get("entry_used", ""))[:10], str(v.get("exit_used", ""))[:10], "VT 100 %"])
        lines += ["VT / VT-proxy legs actually used (PREREG §3.5; first available bars: " +
                  ", ".join(f"T = {T}: EFA first bar {str(b['vt'].get('efa_start'))[:10]}" for T, b in sorted(bench.items(), key=lambda kv: int(kv[0])) if (b.get('vt') or {}).get('efa_start')) +
                  "; VT switch on its first bar " +
                  ", ".join(sorted({str(b['vt'].get('switch_date'))[:10] for b in bench.values() if (b.get('vt') or {}).get('switch_date')}) or ["n/a"]) +
                  "; year-end rebalancing on SPY's last bar of each calendar year):", "",
                  _table(["T", "from", "to", "weights"], legs), ""]
        inc = {T: (b.get("ew") or {}).get("incomplete") for T, b in bench.items() if (b.get("ew") or {}).get("incomplete")}
        if inc:
            lines += ["Equal-weight basket members whose NAV ladder does not reach the exit (kept at their last known value, 0 % thereafter, never dropped): "
                      + "; ".join(f"T = {T}: {', '.join(v)}" for T, v in sorted(inc.items(), key=lambda kv: int(kv[0]))) + ".", ""]
    order = sorted(rows, key=lambda k: (k.split("|")[3], {"B": 0, "B_soft": 1, "B3": 2, "A": 3, "C": 4, "N4": 5}.get(k.split("|")[0], 9), -int(k.split("|")[1]), int(k.split("|")[2])))
    summary = []
    for key in order:
        r = rows[key]
        s = r.get("stats") or {}
        n1 = (r.get("nulls") or {}).get("N1") or (r.get("nulls") or {}).get("N1_investable") or {}
        n2 = (r.get("nulls") or {}).get("N2") or {}
        summary.append([r.get("query"), r["k"], r["h"], r["outcome"], s.get("n"), s.get("n_eff"), _f(s.get("mean_excess"), 2, True), _f(s.get("hit_rate"), 2),
                        _f(s.get("top_quartile_rate"), 2), _ci(s.get("ci_headline")) + (" (degenerate)" if s.get("ci_degenerate") else ""), _p(s.get("hh_p")), _p(s.get("nw2_p")), _p(n1.get("p_mean_excess")), _p(n2.get("p_mean_excess")),
                        _counts(r.get("status_counts")) if r["outcome"] == "returns" else "—"])
    n_growth = sum(1 for k in rows if k.split("|")[3] == "growth")
    n_ret = len(rows) - n_growth
    lines += ["### Summary of every row (details follow)", "",
              _table(["query", "k", "h", "outcome", "n", "N_eff", "μ̂ (pp/yr)", "hit", "top-Q", "headline CI", "p HH", "p NW2", "p N1", "p N2", "status counts"], summary), "",
              f"The {len(rows)} rows ({n_growth} growth + {n_ret} returns) are reported without any multiple-comparison adjustment; only Query B k = 10 h = 10 "
              "is confirmatory (P1, P3 and the §8 decision rules read it), every other row is secondary or informational, and an isolated small p among them "
              "(Query A growth, N4 momentum) is what a family of this size produces by chance and is not a finding.", ""]
    n3 = bt.get("n3") or {}
    if n3:
        lines += ["### N3 — 42-vector Query B minus the three-band comparator (paired bootstrap, same resamples)", "",
                  _table(["k", "h", "μ̂ 42-vector", "μ̂ 3-band", "Δ (pp/yr)", "CI country cluster", "CI T blocks", "headline CI", "one-sided p (Δ ≤ 0)"],
                         [[v.get("k", k.split("|")[0]), v.get("h", k.split("|")[-1]), _f(v.get("mean_excess_42"), 2, True), _f(v.get("mean_excess_3band"), 2, True), _f(v.get("delta"), 2, True),
                           _ci(v.get("ci_country_cluster")), _ci(v.get("ci_block_T")) + (" (degenerate: block length ≥ n_T)" if v.get("ci_block_T_degenerate") else ""),
                           _ci(v.get("ci_headline")), _p(v.get("p_one_sided"))] for k, v in n3.items()]), ""]
        if any(v.get("ci_block_T_degenerate") for v in n3.values()):
            lines += ["For h = 20 the circular T-block scheme has three T's and block length 4, so every resample is the full series and the T-block "
                      "'interval' is the point estimate; the country-cluster CI is the only informative scheme and is the headline for those rows.", ""]
    for key in order:
        lines += _row_block(key, rows[key])
    return "\n".join(lines)


def _exp2_self_match_note(pn: dict) -> list[str]:
    """The mandatory §5 paragraph on prototype self-matching: counts, the overlap share and the three refits beside the
    primary S2/S3 coefficients on D.  Rendered whenever the panel document carries the diagnostics."""
    smp, rob, specs = pn.get("sample") or {}, pn.get("robustness") or {}, pn.get("specs") or {}
    if "n_self_match" not in smp:
        return []
    ho = (pn.get("holdout") or {}).get("oos_r2") or {}
    d_at_clip = smp.get("D_at_clip")
    lines = ["**Prototype self-matching — mandatory note on the in-sample coefficient on D.** `P_train` is drawn from the same country-years "
             "that form the regression sample (PREREG §4 fixes it that way, so this is not a deviation — but it makes the in-sample coefficient on D "
             f"a partial tautology). {smp.get('n_self_match')} sample rows are their own nearest prototype (min d = 0, D = ln {smp.get('d_clip', 1e-9):g} = "
             f"{_f(d_at_clip, 2)} — an extreme leverage value; {_f(smp.get('share_self_match_top_decile_g'), 0, pct=True)} of them are top-decile g by construction, "
             f"all have t ≤ {smp.get('self_match_t_max')}), and {smp.get('n_own_prototype_overlap')} rows ({100 * float(smp.get('share_own_prototype_overlap', float('nan'))):.1f} %) "
             f"share their 10-year outcome window with an own-country prototype window (|t − y| < 10; mean g {_f(100 * float(smp.get('mean_g_own_overlap', float('nan'))), 2)} vs "
             f"{_f(100 * float(smp.get('mean_g_other', float('nan'))), 2)} pp/yr for the rest). D quantiles: "
             + ", ".join(f"{q}: {_f(v, 2)}" for q, v in (smp.get("D_quantiles") or {}).items())
             + f". {smp.get('n_self_match_in_test_block', 0)} self-match rows and {smp.get('n_own_prototype_overlap_in_test_block', 0)} own-overlap rows sit in the 2003–2013 test block.", ""]
    if rob:
        def cell(sp: dict, spec: str) -> str:
            c = ((sp.get(spec) or {}).get("coef") or {}).get("D") or {}
            return f"{_f(c.get('beta'), 5, True)} (SE {_f(c.get('se_dk'), 5)}, p {_p(c.get('p_dk'))})"
        table = [["full sample (primary, as pre-registered)", (specs.get("S3") or {}).get("n"), cell(specs, "S2"), cell(specs, "S3"), _f((specs.get("S3") or {}).get("r2"), 4)]]
        for key, r in rob.items():
            table.append([f"`{key}` — {r.get('rule')}", r.get("n"), cell(r.get("specs") or {}, "S2"), cell(r.get("specs") or {}, "S3"), _f(((r.get("specs") or {}).get("S3") or {}).get("r2"), 4)])
        lines += [_table(["refit", "n", "S2 β_D (DK)", "S3 β_D (DK)", "S3 R²"], table), ""]
    lines += ["Reading: the pre-registered in-sample sign (P7's first clause, the L1 condition `panel_s3_d_lt_0_dk_p_lt_05`) holds on the full sample and is "
              "recorded as such, but it is an artifact of the prototype rows sitting inside their own regression sample — dropping the rows whose outcome "
              "overlaps an own-country prototype window removes it. The in-sample coefficient on D is therefore **not evidence** of a shape → growth "
              f"association; the fixed holdout below, which contains no self-match, is the only evidentiary test here (OOS R² S2 vs S0 {_f((ho.get('S2') or {}).get('vs_s0'), 4, True)}, "
              f"S3 vs S1 {_f((ho.get('S3') or {}).get('vs_s1'), 4, True)}). The `_ex_selfmatch`, `_ex_overlap` and `_floor` rows are in `tables/panel_coefs.csv`.", ""]
    return lines


def _sec_exp2(ctx: dict) -> str:
    pn = ctx.get("panel") or {}
    lines = ["## 5. Experiment 2 — shape → growth panel", ""]
    if not pn:
        lines.append("_Not run._")
        return "\n".join(lines)
    smp = pn.get("sample") or {}
    lines += [f"Sample: n = {smp.get('n')} country-years, {smp.get('n_countries')} countries, t ∈ [{smp.get('t_min')}, {smp.get('t_max')}], "
              f"**N_eff = {smp.get('n_eff')}** ({smp.get('n_eff_rule')}); sources {smp.get('src_counts')}; |P_train| = {smp.get('n_prototypes')} "
              f"(top-decile 10-year windows ending ≤ {(pn.get('_meta') or {}).get('prototype_train_end')}). Dropped: {smp.get('dropped')}.", ""]
    specs = pn.get("specs") or {}
    rows = []
    for spec, v in specs.items():
        for term, c in (v.get("coef") or {}).items():
            rows.append([spec, term, _f(c.get("beta"), 5, True), _f(c.get("se_dk"), 5), _p(c.get("p_dk")), _f(c.get("se_2way"), 5), _p(c.get("p_2way")), _f(v.get("r2"), 4), v.get("n")])
    lines += ["Pooled OLS with SDG-region × decade effects; Driscoll–Kraay (bandwidth 10) primary, two-way (country, year) cluster secondary. "
              "Coefficients per unit regressor on g in log points/yr.", "",
              _table(["spec", "term", "β", "SE DK", "p DK", "SE 2-way", "p 2-way", "R² (in-sample)", "n"], rows), "",
              f"ΔR²(S3 − S1) = {_f(pn.get('delta_r2_s3_s1'), 4)}.", ""]
    lines += _exp2_self_match_note(pn)
    ho = pn.get("holdout") or {}
    if ho:
        oos = ho.get("oos_r2") or {}
        sp = ho.get("spearman") or {}
        lines += [f"Fixed holdout: train t ≤ {(ho.get('train') or {}).get('t_max')} (n = {(ho.get('train') or {}).get('n')}), "
                  f"test t ∈ {(ho.get('test') or {}).get('t_range')} (n = {(ho.get('test') or {}).get('n')}, "
                  f"{(ho.get('test') or {}).get('n_dropped_no_region_fe')} rows dropped for a region absent from training). {ho.get('fe_rule')}.", "",
                  _table(["spec", "OOS R² vs training mean", "vs S0", "vs S1", "mean per-t Spearman", "share of t with ρ > 0"],
                         [[spec, _f(v.get("vs_mean"), 4, True), _f(v.get("vs_s0"), 4, True), _f(v.get("vs_s1"), 4, True),
                           _f((sp.get(spec) or {}).get("mean"), 3, True), _f((sp.get(spec) or {}).get("share_positive"), 2)] for spec, v in oos.items()]), ""]
        per_t = (sp.get("S3") or {}).get("per_t") or {}
        if per_t:
            lines += ["Per-t OOS Spearman, S3: " + ", ".join(f"{t}: {_f(r, 2, True)}" for t, r in sorted(per_t.items(), key=lambda kv: int(kv[0]))), ""]
    notes = (pn.get("_meta") or {}).get("implementation_notes") or []
    if notes:
        lines += ["Implementation notes: " + " ".join(f"({i + 1}) {n}." for i, n in enumerate(notes)), ""]
    return "\n".join(lines)


def _sec_exp3(ctx: dict) -> str:
    dc = ctx.get("disconnect") or {}
    lines = ["## 6. Experiment 3 — disconnect table", ""]
    rows = dc.get("rows") or []
    if not rows:
        lines.append("_Not run._")
        return "\n".join(lines)
    out = []
    for r in rows:
        if "pyramid" not in r:
            out.append([r.get("iso3"), r.get("year"), r.get("state"), *["—"] * 9])
            continue
        p, d, lv, m, f = r["pyramid"], r["distance"], r["levels"], r["msci"], r.get("fund") or {}
        mult = lv.get("multiples") or {}
        m30 = mult.get(30, mult.get("30"))
        mult_txt = " / ".join(f"{k}y ×{_f(mult.get(k, mult.get(str(k))), 2)}" for k in (10, 20, 30) if mult.get(k, mult.get(str(k))) is not None)
        if m30 is None and lv.get("mult_last") is not None:
            mult_txt += f" (→ {lv.get('y_last_year')}: ×{_f(lv.get('mult_last'), 2)}, clipped)"
        msci = (f"{m.get('index_name')}: {_f(m.get('ann_pct_gross_since'), 2, True)} %/yr gross since {m.get('since')}"
                f"{' (clipped to index history)' if m.get('clipped_to_index_history') else ''}; max DD {_f(m.get('max_drawdown_pct_gross'), 1)} % "
                f"(net {_f(m.get('ann_pct_net_since'), 2, True)} %/yr since {m.get('net_since')}); accessed {m.get('accessed')}") if m.get("state") == "ok" else m.get("state")
        if f.get("state") == "ok" and f.get("too_short_to_annualise"):
            # pre-specified rule (disconnect.MIN_ANNUALISE_YEARS): a sub-year window is shown as its raw total return, never as pp/yr
            vt = f.get("vt") or {}
            fund = (f"{f.get('ticker')} {f.get('entry_used')}→{f.get('exit_used')} ({f['window_years']} y — window under "
                    f"{f.get('min_annualise_years', 1):g} y, not annualised): total return {_pp(f.get('total_return'))} % over the span (log {_pp(f.get('total_log_return'))} pp), "
                    f"max DD {_pp(f.get('max_dd'), 0)} % · VT over the same span {_pp(vt.get('total_log_return'))} pp total ({vt.get('benchmark')}) · "
                    f"SPY {_pp((f.get('spy') or {}).get('total_log_return'))} · EEM {_pp((f.get('eem') or {}).get('total_log_return'))} (totals, not per year)")
        elif f.get("state") == "ok":
            vt = f.get("vt") or {}
            fund = (f"{f.get('ticker')} {f.get('entry_used')}→{f.get('exit_used')}" + (f" ({f['window_years']} y)" if f.get("window_years") is not None else "") +
                    f": {_pp(f.get('ann_log_return'))} pp/yr log "
                    f"(CAGR {_pp(f.get('cagr'))} %), max DD {_pp(f.get('max_dd'), 0)} % · VT over the same window "
                    f"{_pp(vt.get('ann_log_return'))} pp/yr ({vt.get('benchmark')}) · SPY {_pp((f.get('spy') or {}).get('ann_log_return'))} · "
                    f"EEM {_pp((f.get('eem') or {}).get('ann_log_return'))}")
        else:
            fund = f.get("state", "—") + (f" ({f.get('ticker')}, inception {f.get('inception')})" if f.get("ticker") else "")
        out.append([r.get("iso3"), r.get("year"), r.get("kind"), _f(p.get("median_age"), 1), f"{_f(p.get('u15'), 3)} / {_f(p.get('wa'), 3)} / {_f(p.get('o65'), 3)}",
                    _f(p.get("s0_s20"), 2), _f(p.get("tfr"), 2), f"{_f(d.get('d_blend_chn1990'), 3)} ({d.get('pct_band')}, pct {_f(d.get('pct_same_year'), 2)})",
                    mult_txt or lv.get("state", "—"), msci, fund])
    lines.append(_table(["iso3", "t", "kind", "median age", "u15 / wa / o65", "s0/s20", "TFR", "d_blend to CHN 1990", "y multiples", "MSCI facts (cited)", "fund vs SPY / EEM / VT"], out))
    meta = dc.get("_meta") or {}
    lines += ["", f"MSCI figures are hand-transcribed facts from `msci_citations.yaml` (factsheets as of {meta.get('msci_as_of', 'n/a')}, accessed {meta.get('msci_accessed', 'n/a')}); "
              "no index series was downloaded. Fund statistics come from daily adjusted closes over the window shown, clipped to the fund's history and the last complete calendar year."
              + (f" Fund windows under {meta.get('min_annualise_years'):g} full year are shown as raw total returns over the span (never annualised; the row is kept)."
                 if meta.get("min_annualise_years") else ""), ""]
    return "\n".join(lines)


def _cagr_example(ctx: dict) -> str:
    """' — e.g. NGE 2015–2025 −7.34 pp/yr log is −7.08 %/yr CAGR …' from the first primary-row lookalike with a fund; '' if none."""
    r = ((ctx.get("backtest") or {}).get("rows") or {}).get("B|10|10|returns") or {}
    for p in r.get("picks") or []:
        if p.get("r") is not None and p.get("r_vt") is not None:
            ra, rv = float(p["r"]), float(p["r_vt"])
            return (f" — e.g. {p.get('ticker')} {int(p['T'])}–{int(p['T']) + int(r.get('h', 10))} {_pp(ra)} pp/yr log is {_f(100 * (np.exp(ra) - 1), 2, True)} %/yr CAGR "
                    f"and VT {_pp(rv)} pp/yr log is {_f(100 * (np.exp(rv) - 1), 2, True)} %/yr")
    return ""


def _sec_decision(ctx: dict) -> str:
    dec = ctx.get("decision") or {}
    lines = ["## 8. Decision levels (PREREG §7)", ""]
    for lvl, v in (dec.get("levels") or {}).items():
        lines.append(f"- **{lvl} — {v.get('name')}: {'GRANTED' if v.get('granted') else 'not granted'}.** "
                     + (f"Failed conditions: {', '.join(v.get('failed') or [])}." if v.get("failed") else "All listed conditions hold." if v.get("requires") else "Always allowed.")
                     + (f" Unavailable inputs: {', '.join(v['unavailable'])}." if v.get("unavailable") else "")
                     + (f" _{v.get('note')}_" if v.get("note") else ""))
    lines.append("")
    conds = dec.get("conditions") or {}
    rows = []
    for name, c in conds.items():
        v = c.get("value")
        if isinstance(v, dict):
            v = ", ".join(f"{a} = {_f(b, 3) if isinstance(b, (int, float)) else b}" for a, b in v.items())
        elif isinstance(v, list):
            v = _ci(v)
        else:
            v = _f(v, 3)
        rows.append([name, v, "yes" if c.get("ok") else ("n/a" if not c.get("available") else "no"), c.get("detail")])
    lines += [_table(["condition", "observed", "holds", "read from"], rows), "",
              f"Allowed sentence ids: {', '.join(dec.get('allowed_sentence_ids') or []) or 'none'}. "
              f"Deny-list violations in rendered sentences / templates: {len(dec.get('deny_list_violations') or [])}.", "",
              "Units in the rendered sentences: every `%/yr` market figure (`L0.vs_vt`) is a compound annual growth rate, 100·(e^r − 1), while the "
              "tables in §4 and §6 carry annualised log returns in pp/yr (r = ln(exit/entry)/years)" + _cagr_example(ctx) + ". In `L0.what_happened` N_eff is that T's "
              "own support (the distinct countries at T, = n); the pooled N_eff stands on the §4 row, and the T = 2015 sentence names the span actually observed "
              "(8 years for PWT rows, 7 for the Maddison fallback).", ""]
    rendered = dec.get("rendered") or {}
    if rendered:
        lines += ["Rendered sentences (the only econ text the UI may show):", ""]
        for sid, texts in rendered.items():
            for t in texts[:12]:
                lines.append(f"- `{sid}`: {t}")
            if len(texts) > 12:
                lines.append(f"- `{sid}`: … {len(texts) - 12} more")
        lines.append("")
    return "\n".join(lines)


GROWTH_VINTAGE_PARAGRAPH = (
    "**Growth-data vintage (additional disclosure, same logic as the demographic caveat).** The GDP-per-capita series behind the prototype "
    "sets P(T), the N4 momentum ranking and the N2 income match are PWT 11.0 / Maddison 2023 revised back-series, i.e. today's estimates of "
    "past growth, not the national-accounts data available at T; PPP benchmark revisions (ICP 2011, 2017, 2021) have moved levels and "
    "growth rates of exactly the low-income countries this backtest selects. **Publication lag.** Every quantity conditioned 'as of T' uses "
    "y_T, the GDP of calendar year T, which is not published on the entry date (the last trading day of T): the prototype rule takes windows "
    "ending ≤ T (y + 10 ≤ T), N4 ranks on g_{{c,T−10,10}} and N2 matches on ln y_T, so all three see roughly one year of data a real-time "
    "selector would not have had. N4's growth result{n4} is the row most exposed to this; Query B's prototype "
    "membership and N2's caliper matches are exposed at the margin (a window ending in T could move in or out of the top decile). The "
    "return rows are unaffected in their outcome (prices are known at T) but inherit the selection's look-ahead."
)


VINTAGE_NOT_PERFORMED = ("was not performed in this run: the WPP 2010 / WPP 2000 archive files were not obtained, so this paragraph stands as the caveat.")


def load_vintage_check(path=None) -> dict | None:
    """``evals/econ/vintage/vintage_check.json`` (written by ``scripts/vintage_check.py``) when it exists and parses as a
    document with ``per_T``; None otherwise.  Guarded: a missing, unreadable or malformed file never breaks the render."""
    from pathlib import Path
    from pyramid_explorer.paths import ECON_EVALS

    p = Path(path) if path is not None else ECON_EVALS / "vintage" / "vintage_check.json"
    try:
        if not p.exists():
            return None
        doc = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("per_T"), dict) and doc["per_T"] else None


def _j(c: dict | None) -> str:
    j = (c or {}).get("jaccard")
    return "n/a" if j is None else f"{float(j):.2f}"


def vintage_summary(doc: dict) -> str:
    """One paragraph for RESULTS.md §7 from the vintage-check document: which archives stood in at which T, the k = 10 and
    k = 5 Jaccard overlaps per rule and T, whether the pre-registered ≥ 0.6 expectation held, how large the revisions were
    and which candidates the archive could not supply.  Wording stays inside the sentence-bank rules (no deny-listed words)."""
    per_T = doc.get("per_T") or {}
    Ts = sorted(per_T, key=int, reverse=True)
    m = doc.get("_meta") or {}
    thr = float(m.get("threshold_jaccard_k10", (doc.get("summary") or {}).get("threshold", 0.6)))
    by_rev: dict[str, list[str]] = {}
    for t in Ts:
        by_rev.setdefault(str(per_T[t].get("revision", "?")), []).append(t)
    revs = "; ".join(f"WPP {r} for T = {', '.join(sorted(ts))}" for r, ts in sorted(by_rev.items(), reverse=True))
    labels = {"B": "Query B (primary)", "A_anchor_wpp2024": "Query A, China-1990 anchor from WPP 2024", "A_anchor_archive": "Query A, anchor from the archive too"}
    parts = []
    for k in ("10", "5"):
        cells = []
        for name in ("B", "A_anchor_wpp2024", "A_anchor_archive"):
            vals = [f"{t}: {_j(((per_T[t].get('queries') or {}).get(name) or {}).get('k', {}).get(k))}" for t in Ts if name in (per_T[t].get("queries") or {})]
            if vals:
                cells.append(f"{labels[name]} — " + ", ".join(vals))
        parts.append(f"k = {k}: " + "; ".join(cells))
    summ = doc.get("summary") or {}
    n_cells, n_met = summ.get("cells"), summ.get("cells_met")
    not_met = summ.get("not_met") or []
    b_ok = summ.get("B_k10_met_at_every_T")
    verdict = (f"The pre-registered expectation (k = 10 Jaccard ≥ {thr:.1f} at every T where an archive exists) was "
               + (f"met by Query B at every T" if b_ok else "NOT met by Query B at every T")
               + (f" and held in {n_met} of {n_cells} (rule, T) cells overall" if n_cells else "")
               + (f"; below the threshold: {', '.join(not_met)}" if not_met else "") + ".")
    rc_bits = []
    for name, short in (("B", "Query B"), ("A_anchor_wpp2024", "Query A")):
        vals = []
        for t in Ts:
            rc = ((per_T[t].get("queries") or {}).get(name) or {}).get("rank_continuity") or {}
            if rc.get("spearman") is not None:
                vals.append(f"{t}: ρ {rc['spearman']:.2f}, WPP 2024 members at archive ranks ≤ {rc.get('max_archive_rank')}")
        if vals:
            rc_bits.append(f"{short} — " + "; ".join(vals))
    rev_bits = []
    for t in Ts:
        rs = per_T[t].get("revision_size") or {}
        if rs.get("n"):
            rev_bits.append(f"T = {t}: median L2 {rs['l2_median']:.4f} = {rs['l2_sigma_median']:.2f} σ_l2, max {rs['l2_max']:.4f} ({rs['l2_max_iso3']}), "
                            f"median blend distance between the two vintages {rs['d_blend_median']:.2f}, n = {rs['n']}")
    unm = [f"{t}: {', '.join(per_T[t]['unmapped_candidates'])}" for t in Ts if per_T[t].get("unmapped_candidates")]
    pred = sorted({f"{p['iso3']} ← {p['name']}" for t in Ts for p in (per_T[t].get("predecessors_used_in_candidates") or [])})
    self_ok = m.get("self_check_passed")
    robust = doc.get("robustness") or {}
    rob_txt = ""
    if robust:
        rb = []
        for key, d in sorted(robust.items()):
            c = ((d.get("queries") or {}).get("B") or {}).get("k", {}).get("10")
            rb.append(f"T = {d.get('T')} on WPP {d.get('revision')}: Query B k = 10 Jaccard {_j(c)}")
        rob_txt = " Robustness rows (next revision as the input) — " + "; ".join(rb) + "."
    return ("**Vintage check (PREREG §8) — performed.** `scripts/vintage_check.py`"
            + (f" ({m['generated_at'][:10]})" if m.get("generated_at") else "")
            + f" rebuilt the T cross-sections from the UN's archived revisions ({revs}) and re-ran the selection rules against the main run's "
            "candidate sets, prototype sets (WPP 2024 pyramids, as pre-registered) and σ; only the candidates' 42-share vectors changed, and "
            "Query A is reported with China's 1990 anchor from WPP 2024 and from the archive. "
            + ("The re-implementation reproduced every recorded WPP 2024 lookalike set exactly before the archive was substituted. " if self_ok else
               ("" if self_ok is None else "WARNING: the re-implementation did not reproduce every recorded WPP 2024 set; the overlaps below are not comparable. "))
            + "Jaccard overlap of the WPP 2024 and archive lookalike sets — " + " · ".join(parts) + ". " + verdict
            + (" Rank continuity (additional, not pre-registered; Spearman ρ of the selection statistic between the two vintages over the common candidates): "
               + " · ".join(rc_bits) + "." if rc_bits else "")
            + (" Revision size on the candidate cross-section (‖s42_archive − s42_2024‖₂): " + "; ".join(rev_bits) + "." if rev_bits else "")
            + (" Candidates the archive does not carry (dropped from the archive side): " + "; ".join(unm) + "." if unm else "")
            + (" Predecessor rows used: " + "; ".join(pred) + "." if pred else "")
            + rob_txt + " Sources, hashes, mapping and the per-country revision tables: `evals/econ/vintage/RESULTS_vintage.md`.")


def _sec_vintage(ctx: dict) -> str:
    doc = ctx["vintage_check"] if "vintage_check" in ctx else load_vintage_check()
    status = ctx.get("vintage_status") or (
        "was performed with the WPP 2010 / WPP 2000 CSV archives (`scripts/vintage_check.py`); the result follows below." if doc else VINTAGE_NOT_PERFORMED)
    n4 = ((ctx.get("backtest") or {}).get("rows") or {}).get("N4|10|10|growth") or {}
    n4_txt = ""
    if n4.get("stats"):
        p1 = ((n4.get("nulls") or {}).get("N1") or {}).get("p_mean_excess")
        n4_txt = f" ({_f((n4['stats'] or {}).get('mean_excess'), 2, True)} pp/yr vs the candidate median, p_N1 {_p(p1)}, k = 10, h = 10)"
    out = "## 7. Vintage statement (PREREG §8)\n\n" + VINTAGE_PARAGRAPH.format(vintage_status=status) + "\n\n"
    if doc:
        out += vintage_summary(doc) + "\n\n"
    return out + GROWTH_VINTAGE_PARAGRAPH.format(n4=n4_txt) + "\n"


def _sec_notes(ctx: dict) -> str:
    notes = list(ctx.get("implementation_notes") or [])
    notes += list(((ctx.get("panel") or {}).get("_meta") or {}).get("implementation_notes") or [])
    notes += list(((ctx.get("disconnect") or {}).get("_meta") or {}).get("implementation_notes") or [])
    lines = ["## 9. Implementation notes (pre-specified gaps filled before looking at results; not deviations)", ""]
    lines += [f"- {n}" for n in notes] or ["- none"]
    lines.append("")
    dev = list(ctx.get("deviations") or [])
    lines += ["## 10. Deviations from PREREG", ""]
    lines += [f"- {d}" for d in dev] or ["- none"]
    lines.append("")
    return "\n".join(lines)


def render_results(ctx: dict) -> str:
    """The whole RESULTS.md.  ``ctx`` keys: prereg_commit, run {generated_at, git_rev, seed, B}, sources (list of
    dicts), universe (yaml dict), guard (dict | None), backtest, panel, disconnect, decision, implementation_notes,
    deviations, vintage_status, and optionally ``vintage_check`` (the vintage_check.json document, or None to suppress the
    §7 summary; when the key is absent the file is loaded from evals/econ/vintage/ if it exists)."""
    parts = [_sec_header(ctx), _sec_data(ctx), _sec_universe(ctx), _sec_predictions(ctx), _sec_exp1(ctx), _sec_exp2(ctx),
             _sec_exp3(ctx), _sec_vintage(ctx), _sec_decision(ctx), _sec_notes(ctx)]   # PREREG §10 order
    return "\n".join(parts)


# ----------------------------------------------------------------------------------------------- run metadata
def prereg_commit_hash(repo_root=None) -> str:
    """``git log -1 --format=%H -- evals/econ/PREREG.md`` (PREREG §0.3); empty string when git is unavailable."""
    import subprocess
    from pyramid_explorer.paths import REPO_ROOT

    try:
        out = subprocess.run(["git", "log", "-1", "--format=%H", "--", "evals/econ/PREREG.md"], cwd=str(repo_root or REPO_ROOT),
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def prereg_is_committed(repo_root=None) -> tuple[bool, str]:
    """(True, hash) when PREREG.md is tracked, unmodified and has a commit; else (False, reason)."""
    import subprocess
    from pyramid_explorer.paths import REPO_ROOT

    root = str(repo_root or REPO_ROOT)
    try:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "evals/econ/PREREG.md"], cwd=root, capture_output=True, text=True)
        if tracked.returncode != 0:
            return False, "evals/econ/PREREG.md is not tracked by git"
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "evals/econ/PREREG.md"], cwd=root, capture_output=True, text=True)
        if dirty.stdout.strip():
            return False, "evals/econ/PREREG.md has uncommitted modifications"
    except OSError as exc:
        return False, f"git unavailable: {exc}"
    h = prereg_commit_hash(root)
    return (bool(h), h if h else "no commit found for evals/econ/PREREG.md")


def run_metadata(*, seed: int, B: int) -> dict:
    """Wall-clock and code revision — the only place the clock is read (run metadata)."""
    import subprocess
    from datetime import datetime, timezone
    from pyramid_explorer.paths import REPO_ROOT

    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        rev = None
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_rev": rev, "seed": seed, "B": B,
            "prereg_commit": prereg_commit_hash()}
