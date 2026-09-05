#!/usr/bin/env python
"""Decision rules → decision.json + RESULTS.md (evals/econ/PREREG.md §7, §10).

    uv run --group econ scripts/decide_econ.py

Reads backtest_lookalikes.json, panel_shape_growth.json, disconnect.json and ui_sentences.yaml; grants L0/L1/L2 by
the pre-registered rules; renders the allowed sentences; writes decision.json and RESULTS.md; runs the deny-list over
the rendered sentences AND over RESULTS.md and exits non-zero on any hit or when PREREG.md is not committed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from pyramid_explorer.econ import decide, lookalike as lk, results
from pyramid_explorer.paths import DATA_OUT, ECON_EVALS, PIPELINE

GUARD_CANDIDATES = (DATA_OUT / "etf_guard_report.json", ECON_EVALS / "etf_guard_report.json", ECON_EVALS / "etf_guard.json")


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _sources() -> list[dict]:
    try:
        from pyramid_explorer import db
        with db.connect(read_only=True) as con:
            df = con.execute("SELECT id, family, name, vintage, licence, redistributable, sha256, fetched_at FROM source ORDER BY id").df()
        def clean(k, v):
            if v is None or (isinstance(v, float) and v != v) or str(v) in ("NaT", "None"):
                return None
            return str(v)[:10] if k == "fetched_at" else v
        return [{k: clean(k, v) for k, v in r.items()} for r in df.to_dict("records")]
    except Exception:  # noqa: BLE001 — the store is optional for rendering
        man = PIPELINE / "econ_manifest.json"
        if man.exists():
            return [{"id": k, "family": v.get("source", k), "fetched_at": v.get("fetched_at"), "sha256": v.get("sha256"), "licence": v.get("licence")}
                    for k, v in json.loads(man.read_text()).items()]
        return []


def ladder_gap_sensitivity(mdoc: dict, backtest: dict, returns_table) -> dict[str, str]:
    """Quantify, for every liquidating fund whose cash ladder lacks a sourced reference NAV but names an implied one
    (``cash_ladder.implied_nav_YYYY_MM_DD_unsourced`` in etf_manual.yaml), how far the halt-year mark understates the cash
    actually recovered and what that does to the equal-weight basket of the affected T — one §10 sentence per (fund, T).
    Pure arithmetic on transcribed figures; the implied NAV is unsourced and is never used in any statistic."""
    import math
    import re as _re

    out: dict[str, str] = {}
    bench = backtest.get("benchmarks") or {}
    for f in mdoc.get("funds", []) or []:
        cl = f.get("cash_ladder") or {}
        key = next((k for k in cl if k.startswith("implied_nav_") and k.endswith("_unsourced") and cl[k]), None)
        if key is None or f.get("last_trading_day") is None:
            continue
        implied = float(cl[key])
        ref_date = _re.sub(r"^implied_nav_(\d{4})_(\d{2})_(\d{2})_unsourced$", r"\1-\2-\3", key)
        halt_year = int(str(f["last_trading_day"])[:4])
        years = {int(y["year"]): float(y["tr_nav"]) for y in f.get("years", []) or [] if y.get("tr_nav") is not None}
        if halt_year not in years:
            continue
        dist = float(cl.get("distributions_total_to_date") or 0.0)
        resid = next((float(cl[k]) for k in cl if k.startswith("residual_nav_") and cl[k] is not None), 0.0)
        recovered_frac = (dist + resid) / implied                      # cash per share ÷ implied reference NAV
        tk = f["ticker"]
        rows = returns_table[(returns_table["ticker"] == tk) & (returns_table["status"] == "manual_incomplete")] if "ticker" in returns_table else returns_table.iloc[0:0]
        for r in rows.itertuples(index=False):
            T = int(r.T)
            v_ref = math.prod(1.0 + years[y] for y in range(T + 1, halt_year) if y in years)
            mark = v_ref * (1.0 + years[halt_year])                    # the applied halt-year mark, then 0 % cash
            alt = v_ref * recovered_frac                               # cash actually paid + residual, per unit of start value
            ew = (bench.get(str(T)) or bench.get(T) or {}).get("ew") or {}
            basket = ""
            if ew.get("r_log") is not None and ew.get("n") and ew.get("years"):
                mean_gross = math.exp(float(ew["r_log"]))
                r_alt = math.log(mean_gross + (alt - mark) / float(ew["n"])) / float(ew["years"])
                basket = (f"; the T = {T} equal-weight basket (n = {ew['n']}) would move from {100 * float(ew['r_ann']):+.3f} to {100 * r_alt:+.3f} pp/yr "
                          f"({100 * (r_alt - float(ew['r_ann'])):+.3f} pp/yr, < 0.05 pp/yr)" if abs(r_alt - float(ew["r_ann"])) < 0.0005 else
                          f"; the T = {T} equal-weight basket (n = {ew['n']}) would move from {100 * float(ew['r_ann']):+.3f} to {100 * r_alt:+.3f} pp/yr")
            yrs = float(r.exit_used[:4]) - T if isinstance(r.exit_used, str) else 10.0
            out[f"{tk}|{T}"] = (f"{tk} T = {T} ladder gap, quantified: the row carries the {halt_year} N-PORT mark ({100 * years[halt_year]:+.3f} %) with the post-halt "
                                f"span at 0 %, i.e. {100 * mark:.2f} % of the start value ({100 * r.r_ann:+.2f} pp/yr log); against the transcriber's implied but "
                                f"UNSOURCED {ref_date} NAV of ${implied:.2f} the cash actually paid (${dist:.6f}) plus the residual NAV (${resid:.4f}) is "
                                f"{100 * recovered_frac:.1f} % of that NAV, i.e. {100 * alt:.2f} % of the start value ({100 * math.log(alt) / yrs:+.2f} pp/yr log) — "
                                f"the mark understates recovery by {100 * (alt - mark):.1f} pp of start value{basket}. The implied NAV enters no statistic; "
                                f"sourcing a `nav_{ref_date.replace('-', '_')}` would put {tk} on the same cash-ladder arithmetic as RSX.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(ECON_EVALS))
    ap.add_argument("--allow-uncommitted-prereg", action="store_true")
    args = ap.parse_args(argv)
    d = Path(args.dir)
    ok, why = results.prereg_is_committed()
    if not ok and not args.allow_uncommitted_prereg:
        print(f"[decide_econ] refusing to run: {why} (PREREG §0.1)", file=sys.stderr)
        return 2
    prereg_commit = results.prereg_commit_hash()
    backtest, panel, disconnect = _load(d / "backtest_lookalikes.json"), _load(d / "panel_shape_growth.json"), _load(d / "disconnect.json")
    missing = [n for n, v in (("backtest_lookalikes.json", backtest), ("panel_shape_growth.json", panel)) if v is None]
    if missing:
        print(f"[decide_econ] missing inputs: {missing} — run the backtest scripts first", file=sys.stderr)
        return 2
    sentences = yaml.safe_load((ECON_EVALS / "ui_sentences.yaml").read_text())
    decision = decide.decide(backtest, panel, sentences, prereg_commit=prereg_commit, disconnect=disconnect)
    decision["run"] = results.run_metadata(seed=lk.SEED, B=(backtest.get("_meta") or {}).get("B", lk.B_DEFAULT))
    decision["inputs"] = {"backtest_run": (backtest.get("_meta") or {}).get("run"), "panel_run": (panel.get("_meta") or {}).get("run"),
                          "disconnect_run": ((disconnect or {}).get("_meta") or {}).get("run")}
    universe = yaml.safe_load((ECON_EVALS / "etf_universe.yaml").read_text())
    guard = next((_load(c) for c in GUARD_CANDIDATES if c.exists()), None)
    deviations = list((backtest.get("_meta") or {}).get("deviations") or []) + list((panel.get("_meta") or {}).get("deviations") or []) \
        + list(((disconnect or {}).get("_meta") or {}).get("deviations") or [])
    if guard is not None and (guard.get("run") or {}).get("dead_series_policy") == "ok":
        dev_tickers = sorted(tk for tk, rec in (guard.get("tickers") or {}).items() if isinstance(rec, dict) and rec.get("deviation"))
        deviations.append("Survivorship guard (PREREG §6, assertion 4): Yahoo's daily range=max endpoint served a full multi-year history for "
                          f"{len(dev_tickers)} delisted ticker(s) ({', '.join(dev_tickers)}) instead of refusing (the one-bar / no-data signature seen with the "
                          "monthly interval during curation). PREREG says any assertion failure stops the build; the recorded run was "
                          "`make backtest DEAD_SERIES=ok` (i.e. `scripts/fetch_etf.py --dead-series ok`), which records the failure per ticker below, "
                          "DISCARDS every dead series and takes those funds' returns only from etf_manual.yaml — no number in this file uses a served dead series. "
                          "The Makefile default is `DEAD_SERIES ?= fail`, the strict pre-registered stop (exit 1 after 4 A4 failures), so plain `make backtest` "
                          "refuses and the deviation has to be chosen explicitly on every run.")
    if guard is None:
        deviations.append("No per-ticker guard report file was found (looked for " + ", ".join(str(c) for c in GUARD_CANDIDATES) +
                          "); the guard's per-ticker results are in the fetch_etf console output only.")
    else:
        for tk, rec in sorted((guard.get("tickers") or {}).items()):
            if isinstance(rec, dict) and rec.get("deviation"):
                deviations.append(f"{tk}: {rec['deviation']} (guard report)")
        cc = d / "tables" / "etf_crosscheck.csv"
        if cc.exists():
            guard["crosscheck"] = __import__("pandas").read_csv(cc).to_dict("records")
    manual = ECON_EVALS / "etf_manual.yaml"
    if manual.exists():
        mdoc = yaml.safe_load(manual.read_text()) or {}
        structured = mdoc.get("prereg_deviations")
        if structured:
            deviations += [f"etf_manual.yaml: {str(d).strip()}" for d in structured]
        else:                                             # fall back to the comment header
            head = [ln[1:].strip() for ln in manual.read_text().splitlines()[:60] if ln.startswith("#")]
            try:
                i = next(k for k, ln in enumerate(head) if ln.lower().startswith("deviations from etf_universe.yaml"))
                block = [ln for ln in head[i + 1:]]
                block = block[next((j for j, ln in enumerate(block) if re.match(r"^[A-Z]{2,5}:", ln)), 0):]
                block = block[:next((j for j, ln in enumerate(block) if not ln), len(block))]
                deviations.append("etf_manual.yaml (E3) records these date/distribution deviations from etf_universe.yaml: " + " ".join(block))
            except StopIteration:
                pass
    ret_csv = d / "tables" / "etf_returns.csv"
    if ret_csv.exists():
        rt = __import__("pandas").read_csv(ret_csv)
        gaps = rt[rt["status"].isin(["manual_incomplete"]) | rt["incomplete"].notna()] if "incomplete" in rt else rt.iloc[0:0]
        if len(gaps):
            deviations.append("Manual NAV ladder (PREREG §6): the ladder does not cover every day of some windows — "
                              + "; ".join(f"{r.ticker} T = {int(r.T)}: {r.incomplete}" for r in gaps.itertuples(index=False) if isinstance(r.incomplete, str))
                              + ". Each uncovered span is held at 0 % nominal and the row is carried with status liquidated_in_window (Experiment 1) / "
                              "manual_incomplete (etf_returns.csv) — never dropped, never silently completed.")
        if manual.exists():
            for tk, sens in ladder_gap_sensitivity(mdoc, backtest, rt).items():
                deviations.append(sens)
    if not (backtest.get("_meta") or {}).get("returns_computed", True):
        deviations.append("Return outcomes were not computed in this run (--no-returns); every returns row and P3/P3b are absent.")
    ctx = {"prereg_commit": prereg_commit, "run": decision["run"], "sources": _sources(), "universe": universe, "guard": guard,
           "backtest": backtest, "panel": panel, "disconnect": disconnect, "decision": decision,
           "implementation_notes": (backtest.get("_meta") or {}).get("implementation_notes") or [], "deviations": deviations,
           "vintage_status": (backtest.get("_meta") or {}).get("vintage_status")}
    md = results.render_results(ctx)
    patterns = decide.compile_deny_list(sentences)
    md_hits = decide.scan_deny_list(md, patterns)
    decision["results_md_deny_list_violations"] = md_hits
    lk.dump_json(decision, d / "decision.json")
    (d / "RESULTS.md").write_text(md)
    print("levels: " + ", ".join(f"{l}={'granted' if v['granted'] else 'no'}" for l, v in decision["levels"].items()))
    print("predictions: " + ", ".join(f"{k}: {'met' if v.get('met') else 'not met'}" for k, v in decision["predictions"].items()))
    print(f"wrote {d / 'decision.json'} and {d / 'RESULTS.md'}")
    bad = decision["deny_list_violations"] + md_hits
    if bad:
        for h in bad:
            print(f"[deny-list] {h.get('where', 'RESULTS.md')}: {h['pattern']!r} matched {h['match']!r} … {h['context']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
