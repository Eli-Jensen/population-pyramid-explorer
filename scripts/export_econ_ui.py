#!/usr/bin/env python
"""Export the economic-lens UI data files (PLAN §7, M5) — a mechanical copy of the frozen evals.

Writes, from evals/econ/* (generated, frozen) and evals/evidence.yaml (hand-transcribed, cited):

  web/src/data/econ_decision.json   allowed_sentence_ids + levels + conditions + the rendered L0 sentences
                                    (decision.json trimmed; `rendered.L0.investability` de-duplicated)
  web/src/data/ui_sentences.json    the sentence templates, variants and deny list of ui_sentences.yaml
  web/src/data/evidence.json        everything pages/Evidence.svelte renders: the four links, the China row,
                                    this site's backtest numbers (primary rows, nulls, benchmarks, EW basket,
                                    decision levels, vintage Jaccard table, deviations), the investability table
                                    (etf_universe.yaml + the etf_manual.yaml date corrections), sources & licences.

Growth / market CLAIMS reach the UI only through lib/econ/lang.ts, which renders ids present in `allowed_sentence_ids`
through the templates copied here; table cells and chips print numbers with their window and VT beside them, and every
string under web/src passes the deny list (lang.test.ts). Every fund figure is exported in BOTH units — annualised log
return (pp/yr, as RESULTS.md §4/§6 print it) and CAGR (%/yr, as the L0.vs_vt sentence prints it) — so the page never
converts by hand. Re-run after `make backtest` (`make build` calls this through pyramid_explorer.econ.evidence).
Pure file → file; no network.

Usage: uv run --group econ python scripts/export_econ_ui.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ECON = ROOT / "evals" / "econ"
OUT = ROOT / "web" / "src" / "data"

PRIMARY_GROWTH = "B|10|10|growth"
PRIMARY_RETURNS = "B|10|10|returns"
PRIMARY_GROWTH_20 = "B|10|20|growth"

# The neutral question the page opens with, and the list of what the lens never does (PLAN §7). Fixed copy, kept here
# (not in evidence.yaml, whose header Z3 owns) so lang.test.ts scans it in the generated JSON.
QUESTION = (
    "Does a country's population pyramid say anything about its later economic growth, and did that growth reach an "
    "index investor? This page lists what the published literature found, what happened after a well-known case "
    "(China 1990), and what this site's own pre-registered backtest found on its own data. Nothing here is a forecast."
)
NEVER_DOES = [
    "Never combines shape distance with any economic number into a score.",
    "Never sorts or ranks result lists by return or by growth; the cohort strip reports where a country's own growth fell among its lookalikes (median, IQR, rank), in shape order.",
    "Never shows a price, a valuation forecast or an IMF WEO projection.",
    "Never links to a broker; instrument links go only to the issuer's own notice, filing or factsheet.",
    "Never states a growth or market claim outside the pre-registered templates granted by evals/econ/decision.json (levels L1 and L2 were not granted); table cells and chips print numbers with their window, VT beside them, and every string passes the deny list.",
    "Never shows a market number without VT (Vanguard Total World Stock ETF) over the identical window, flagged VT-proxy before 2008-06-24.",
    "Never redistributes IMF WEO or MSCI series; MSCI facts are hand-transcribed and cited with the access date.",
]

# Units, stated once: the page shows CAGR wherever it says %/yr; RESULTS.md §4/§6 tables carry annualised log returns.
UNITS_NOTE = (
    "Every %/yr market figure on this page is a compound annual growth rate, 100·(e^r − 1), the unit of the L0.vs_vt "
    "sentence; the pp/yr figures (mean excess, CIs, EW minus VT) are differences of annualised log returns, the unit of "
    "the RESULTS.md §4 and §6 tables (r = ln(exit/entry)/years)."
)
# GDP-per-capita level series behind the disconnect multiples (RESULTS §1: "level: PWT rgdpe/pop else Maddison"), per
# (iso3, year) from evals/econ/tables/gdp_pc.parquet's y_level_source. The country page's EconStrip shows Maddison 2011 $.
LEVEL_SOURCE_LABEL = {"pwt": "PWT 11.0 rgdpe/pop, 2017 PPP $", "maddison": "Maddison 2023, 2011 $"}
VINTAGE_FAMILIES = {"curated", "maddison", "oghist", "pwt", "wdi", "weo", "wpp"}


def log_to_cagr(r):
    """Annualised log return (fraction) → CAGR in %/yr, 100·(e^r − 1); None stays None."""
    return None if r is None else 100.0 * (math.exp(r) - 1.0)


def pp100(r):
    return None if r is None else 100.0 * r


def total_log_to_pct(r):
    """Total log return over a span → total simple return in %, 100·(e^r − 1)."""
    return None if r is None else 100.0 * (math.exp(r) - 1.0)


def load_level_sources(p: Path) -> dict[tuple[str, int], str]:
    """{(iso3, year): 'pwt' | 'maddison'} from tables/gdp_pc.parquet, or {} when the table is absent."""
    if not p.exists():
        return {}
    import pandas as pd  # econ group dependency; the script runs under `uv run --group econ`

    df = pd.read_parquet(p, columns=["iso3", "year", "y_level_source"]).dropna(subset=["y_level_source"])
    return {(str(r.iso3), int(r.year)): str(r.y_level_source) for r in df.itertuples(index=False)}


def load_json(p: Path):
    with p.open() as f:
        return json.load(f)


def load_yaml(p: Path):
    with p.open() as f:
        return yaml.safe_load(f)


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size} B)")


def uniq(seq):
    seen = set()
    out = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ------------------------------------------------------------------------------------------------ decision


def export_decision(decision: dict) -> dict:
    rendered = {k: uniq(v) for k, v in decision["rendered"].items()}
    return {
        "prereg_commit": decision["prereg_commit"],
        "primary": decision["primary"],
        "levels_granted": decision["levels_granted"],
        "allowed_sentence_ids": sorted(decision["allowed_sentence_ids"]),
        "levels": {
            k: {"name": v["name"], "granted": v["granted"], "requires": v["requires"], "failed": v["failed"], "unavailable": v["unavailable"], "note": v.get("note")}
            for k, v in decision["levels"].items()
        },
        "conditions": {k: {"value": v["value"], "ok": v["ok"], "available": v["available"], "detail": v["detail"]} for k, v in decision["conditions"].items()},
        "rendered": rendered,
        "deny_list": decision["deny_list"],
        "run": decision["run"],
    }


def export_sentences(ui: dict) -> dict:
    return {
        "version": ui["version"],
        "deny_list": ui["deny_list"],
        "levels": {k: {"name": v["name"], "requires": v.get("requires", [])} for k, v in ui["levels"].items()},
        "sentences": ui["sentences"],
    }


# ------------------------------------------------------------------------------------------------ evidence


def results_deviations(results_md: str) -> list[str]:
    """The bullet list under '## 10. Deviations from PREREG' (RESULTS.md is generated; we copy, never retype)."""
    m = re.search(r"^## 10\. Deviations from PREREG\s*$(.*?)(?=^## |\Z)", results_md, re.S | re.M)
    if not m:
        return []
    return [re.sub(r"\s+", " ", b.strip()) for b in re.findall(r"^- (.*?)(?=^- |\Z)", m.group(1), re.S | re.M)]


VINTAGE_COLUMNS = ["source", "family", "vintage", "licence", "shipped", "fetched", "sha256"]


def results_vintages(results_md: str) -> list[dict]:
    """The §1 data-vintage table: source | family | vintage | licence | shipped | fetched | sha256.

    Anchored on that table's own header row and read only to the first blank line after it — §1 also holds the
    candidate-set table `| candidate set C(T) | 1990 | … |`, whose 7-cell rows are not vintages. Rows whose family is
    not a known source family are refused rather than shipped."""
    m = re.search(r"^## 1\. Data vintages and fetch dates\s*$(.*?)(?=^## |\Z)", results_md, re.S | re.M)
    rows: list[dict] = []
    if not m:
        return rows
    lines = m.group(1).splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"^\|\s*source\s*\|\s*family\s*\|", l))
    except StopIteration:
        return rows
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        if line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(VINTAGE_COLUMNS):
            raise ValueError(f"RESULTS §1 vintage row has {len(cells)} cells, expected {len(VINTAGE_COLUMNS)}: {line!r}")
        row = dict(zip(VINTAGE_COLUMNS, cells))
        if row["family"] not in VINTAGE_FAMILIES:
            raise ValueError(f"RESULTS §1 vintage row with an unknown family {row['family']!r}: {line!r}")
        rows.append(row)
    return rows


def results_partial_note(results_md: str) -> str | None:
    """The parenthetical of §1's 'T = 2015 growth windows are partial (PWT h = 8 → 2023, Maddison h = 7 → 2022)'."""
    m = re.search(r"growth windows are partial \(([^)]*)\)", results_md)
    return m.group(1) if m else None


def growth_row(bt: dict, key: str) -> dict:
    r = bt["rows"][key]
    s = r["stats"]
    per_T = []
    for T in r["T_values"]:
        t = str(T)
        picks = [p for p in r["picks"] if p["T"] == T]
        per_T.append(
            {
                "T": T,
                "n": len(picks),
                "mean_excess": s["per_T"][t]["mean_excess"],
                "hit_rate": s["per_T"][t]["hit_rate"],
                "median_g": r["median_g_per_T"][t],
                "n_candidates": r["candidates_per_T"][t],
                "partial": any(p["partial"] for p in picks),
                "picks": [{"iso3": p["iso3"], "eg": p["eg"], "g": p["g"], "src": p["src"]} for p in picks],
            }
        )
    nulls = r["nulls"]
    return {
        "key": key,
        "query_name": r["query_name"],
        "k": r["k"],
        "h": r["h"],
        "n": s["n"],
        "n_partial": r["n_partial"],
        "n_eff": s["n_eff"],
        "hit_rate": s["hit_rate"],
        "top_quartile_rate": s["top_quartile_rate"],
        "mean_excess": s["mean_excess"],
        "ci_headline": s["ci_headline"],
        "ci_country_cluster": s["ci_country_cluster"],
        "ci_block_T": s["ci_block_T"],
        "ci_block_T_degenerate": s.get("ci_block_T_degenerate", False),
        "hh_p": s.get("hh_p"),
        "nw2_p": s.get("nw2_p"),
        "nw4_p": s.get("nw4_p"),
        "cluster_p": s.get("cluster_p"),
        "bootstrap_B": (s.get("bootstrap") or {}).get("B"),
        "nulls": {
            "N1": {"p": nulls["N1"]["p_mean_excess"], "share": nulls["N1"]["share_at_least_as_good"], "null_mean": nulls["N1"]["null_mean"], "B": nulls["N1"]["B"]},
            "N2": {"p": nulls["N2"]["p_mean_excess"], "share": nulls["N2"]["share_at_least_as_good"], "null_mean": nulls["N2"]["null_mean"], "B": nulls["N2"]["B"], "caliper": nulls["N2"].get("caliper")},
            "N4": {"p": nulls["N4"]["p_one_sided"], "mean_excess_N4": nulls["N4"]["mean_excess_N4"], "delta": nulls["N4"]["paired_vs_picks"]["delta"], "ci": nulls["N4"]["paired_vs_picks"]["ci_headline"]},
        },
        "per_T": per_T,
    }


def last_trading_days(manual: dict) -> dict[str, str]:
    """ticker → etf_manual.yaml last_trading_day (the SEC-filing correction of the frozen universe's date)."""
    return {f["ticker"]: f["last_trading_day"] for f in manual.get("funds", []) if f.get("last_trading_day")}


def returns_row(bt: dict, key: str, manual: dict | None = None) -> dict:
    """The picks' r / r_vt / er are log fractions per year in backtest_lookalikes.json (`_meta.units`); the per-T
    r_vt / r_ew are already pp/yr (×100). Both are exported as pp/yr log AND CAGR %/yr so the page prints one unit
    per label. A liquidated pick's `delisted` is the universe file's date; `last_trading_day` is the etf_manual.yaml
    correction the window arithmetic used (RESULTS §10)."""
    r = bt["rows"][key]
    s = r["stats"]
    ltd = last_trading_days(manual or {})
    per_T = []
    for T in r["T_values"]:
        t = str(T)
        picks = [p for p in r["picks"] if p["T"] == T]
        per_T.append(
            {
                "T": T,
                "benchmark": r["benchmark_per_T"][t],
                "r_vt": r["r_vt_per_T"][t],
                "r_vt_cagr": log_to_cagr(r["r_vt_per_T"][t] / 100.0),
                "r_ew": r["r_ew_per_T"][t],
                "r_ew_cagr": log_to_cagr(r["r_ew_per_T"][t] / 100.0),
                "ew_n": r["ew_n_per_T"][t],
                "investable_share": r["investable_share_per_T"][t],
                "investable_candidates": r["investable_candidates_per_T"][t],
                "n_candidates": r["candidates_per_T"][t],
                "status_counts": r["status_counts_per_T"][t],
                "picks": [
                    {
                        "iso3": p["iso3"],
                        "status": p["status"],
                        "ticker": p.get("ticker"),
                        "r_pp": pp100(p.get("r")),
                        "r_vt_pp": pp100(p.get("r_vt")),
                        "er_pp": pp100(p.get("er")),
                        "r_cagr": log_to_cagr(p.get("r")),
                        "r_vt_cagr": log_to_cagr(p.get("r_vt")),
                        "inception": p.get("inception"),
                        "delisted_universe": p.get("delisted"),
                        "last_trading_day": ltd.get(p.get("ticker") or "", p.get("delisted")),
                    }
                    for p in picks
                ],
            }
        )
    return {
        "key": key,
        "query_name": r["query_name"],
        "k": r["k"],
        "h": r["h"],
        "n": s["n"],
        "n_eff": s["n_eff"],
        "hit_rate": s["hit_rate"],
        "mean_excess_vs_vt": s["mean_excess"],
        "mean_r": r.get("mean_r"),
        "ci_headline": s["ci_headline"],
        "ci_degenerate": s.get("ci_degenerate", False),
        "status_counts": r["status_counts"],
        "ladder_incomplete": r.get("ladder_incomplete", []),
        "vs": {k: {"n": v["n"], "mean_excess": v["mean_excess"], "ci_headline": v["ci_headline"]} for k, v in r["vs"].items()},
        "oos_block_T_ge_2010": r["oos_block_T_ge_2010"],
        "nulls": {
            "N1_investable": {"p": r["nulls"]["N1_investable"]["p_mean_excess"], "null_mean": r["nulls"]["N1_investable"]["null_mean"], "B": r["nulls"]["N1_investable"]["B"]},
            "N4_investable": {"p": r["nulls"]["N4_investable"].get("p_one_sided"), "mean_excess_N4": (r["nulls"]["N4_investable"].get("stats") or {}).get("mean_excess")},
        },
        "per_T": per_T,
    }


def benchmarks(bt: dict) -> list[dict]:
    out = []
    for T, b in sorted(bt["benchmarks"].items()):
        vt = b["vt"]
        out.append(
            {
                "T": int(T),
                "r_vt_ann": vt["r_ann"],
                "r_vt_cagr": log_to_cagr(vt["r_ann"]),
                "r_vt_log": vt["r_log"],
                "benchmark": vt["benchmark"],
                "entry": vt["entry_used"][:10],
                "exit": vt["exit_used"][:10],
                "legs": [{"from": l["from"][:10], "to": l["to"][:10], "weights": l["weights"]} for l in b.get("vt_legs", [])],
                "ew": {"r_ann": b["ew"]["r_ann"], "r_cagr": log_to_cagr(b["ew"]["r_ann"]), "n": b["ew"]["n"], "n_liquidated": b["ew"].get("n_liquidated"), "incomplete": b["ew"].get("incomplete", [])},
                "spy": (b.get("refs") or {}).get("SPY"),
                "efa": (b.get("refs") or {}).get("EFA"),
                "eem": (b.get("refs") or {}).get("EEM"),
                "spy_cagr": log_to_cagr((b.get("refs") or {}).get("SPY")),
                "efa_cagr": log_to_cagr((b.get("refs") or {}).get("EFA")),
                "eem_cagr": log_to_cagr((b.get("refs") or {}).get("EEM")),
            }
        )
    return out


def vintage(v: dict) -> dict:
    rows = []
    rhos = []
    for T, pt in sorted(v["per_T"].items(), key=lambda kv: int(kv[0])):
        for q, qq in pt["queries"].items():
            rc = qq.get("rank_continuity") or {}
            if rc.get("spearman") is not None:
                rhos.append(float(rc["spearman"]))
            for k, kk in qq["k"].items():
                rows.append(
                    {
                        "T": int(T),
                        "revision": pt["revision"],
                        "query": q,
                        "k": int(k),
                        "wpp2024": kk["wpp2024"],
                        "archive": kk["archive"],
                        "common": kk.get("common", len(set(kk["wpp2024"]) & set(kk["archive"]))),
                        "jaccard": kk["jaccard"],
                        "met": kk.get("met"),
                        "rho": rc.get("spearman"),
                    }
                )
    return {
        "expectation": v["summary"]["expectation"],
        "threshold": v["summary"]["threshold"],
        "cells": v["summary"]["cells"],
        "cells_met": v["summary"]["cells_met"],
        "not_met": v["summary"]["not_met"],
        "B_k10_met_at_every_T": v["summary"]["B_k10_met_at_every_T"],
        "revision_rule": v["_meta"]["revision_rule"],
        "self_check_passed": v["_meta"]["self_check_passed"],
        "spearman": {"min": min(rhos), "max": max(rhos), "n": len(rhos)} if rhos else None,
        "sources": {T: {"revision": s["revision"], "zip": s["zip"], "url": s["url"], "zip_sha256": s["zip_sha256"]} for T, s in v["sources"].items()},
        "rows": rows,
        "caveats": v.get("caveats", []),
    }


def disconnect_rows(dc: dict, level_sources: dict[tuple[str, int], str] | None = None) -> list[dict]:
    """Disconnect table rows. `levels.source` names the series behind y_t (gdp_pc.parquet's y_level_source); the fund
    block carries the annualised log returns AND the total log returns of the fund, VT, SPY and EEM, so a window too
    short to annualise is shown as totals over the identical span on both sides."""
    rows = []
    ls = level_sources or {}
    for r in dc["rows"]:
        fund = r.get("fund") or {}
        msci = r.get("msci") or {}
        levels = r.get("levels") or {}
        src = ls.get((r["iso3"], int(r["year"])))
        rows.append(
            {
                "iso3": r["iso3"],
                "year": r["year"],
                "kind": r["kind"],
                "name": r["name"],
                "pyramid": r["pyramid"],
                "distance": r["distance"],
                "levels": {
                    "y_t": levels.get("y_t"),
                    "multiples": levels.get("multiples"),
                    "y_last_year": levels.get("y_last_year"),
                    "mult_last": levels.get("mult_last"),
                    "state": levels.get("state"),
                    "source": LEVEL_SOURCE_LABEL.get(src, src) if levels.get("y_t") is not None else None,
                },
                "msci": {
                    k: msci.get(k)
                    for k in ("state", "index_name", "since", "clipped_to_index_history", "ann_pct_gross_since", "ann_pct_net_since", "net_since", "max_drawdown_pct_gross", "max_drawdown_period_gross", "url_gross", "url_net", "accessed", "as_of")
                },
                "fund": {
                    k: fund.get(k)
                    for k in ("state", "ticker", "name", "issuer", "inception", "delisted", "entry_used", "exit_used", "window_years", "ann_log_return", "cagr", "total_return", "too_short_to_annualise", "max_dd", "status")
                }
                | {
                    "total_log_return": fund.get("total_log_return"),
                    "cagr_pct": None if fund.get("ann_log_return") is None else log_to_cagr(fund["ann_log_return"]),
                    "vt": (fund.get("vt") or {}).get("ann_log_return"),
                    "vt_cagr_pct": log_to_cagr((fund.get("vt") or {}).get("ann_log_return")),
                    "vt_total_log": (fund.get("vt") or {}).get("total_log_return"),
                    "vt_total_pct": total_log_to_pct((fund.get("vt") or {}).get("total_log_return")),
                    "vt_benchmark": (fund.get("vt") or {}).get("benchmark"),
                    "spy": (fund.get("spy") or {}).get("ann_log_return"),
                    "spy_cagr_pct": log_to_cagr((fund.get("spy") or {}).get("ann_log_return")),
                    "spy_total_log": (fund.get("spy") or {}).get("total_log_return"),
                    "eem": (fund.get("eem") or {}).get("ann_log_return"),
                    "eem_cagr_pct": log_to_cagr((fund.get("eem") or {}).get("ann_log_return")),
                    "eem_total_log": (fund.get("eem") or {}).get("total_log_return"),
                },
            }
        )
    return rows


def investability(universe: dict, manual: dict) -> dict:
    corrections = {f["ticker"]: f for f in manual.get("funds", [])}
    rows = []
    for e in universe["entries"]:
        m = corrections.get(e["ticker"])
        rows.append(
            {
                "ticker": e["ticker"],
                "iso3": e.get("iso3"),
                "role": e["role"],
                "name": e.get("name"),
                "issuer": e.get("issuer"),
                "inception": e.get("inception"),
                "inception_verified": e.get("inception_verified"),
                "status": e.get("status"),
                "delisted_universe": e.get("delisted"),
                "last_trading_day": (m or {}).get("last_trading_day"),
                "liquidation_date": (m or {}).get("liquidation_date"),
                "status_url": e.get("status_url"),
                "liquidation_source_url": (m or {}).get("liquidation_source_url"),
                "source_url": e.get("source_url"),
                "msci_class": e.get("msci_class"),
            }
        )
    return {"as_of": universe.get("as_of"), "n": len(rows), "rows": rows, "manual_deviations": manual.get("prereg_deviations", [])}


def rendered_notes(rendered: dict[str, list[str]], universe: dict, manual: dict) -> list[dict]:
    """decision.json is frozen, so its rendered L0.investability sentences carry the universe file's liquidation dates;
    where etf_manual.yaml corrected a date from SEC filings (RESULTS §10) the page shows the correction beside the
    sentence instead of editing it."""
    ltd = last_trading_days(manual)
    by_date = {}
    for e in universe["entries"]:
        if e.get("delisted") and e["ticker"] in ltd and ltd[e["ticker"]] != e["delisted"]:
            by_date[(e["ticker"], e["delisted"])] = ltd[e["ticker"]]
    out = []
    for sentence in rendered.get("L0.investability", []):
        m = re.search(r"^(\w+) was liquidated on (\d{4}-\d{2}-\d{2})", sentence)
        if m and (m.group(1), m.group(2)) in by_date:
            out.append({"sentence": sentence, "ticker": m.group(1), "universe_date": m.group(2), "last_trading_day": by_date[(m.group(1), m.group(2))]})
    return out


def export_evidence(ev: dict, decision: dict, bt: dict, dc: dict, vint: dict, universe: dict, manual: dict, results_md: str, notice: str, level_sources: dict | None = None) -> dict:
    rendered = {k: uniq(v) for k, v in decision["rendered"].items()}
    p3b = decision["predictions"].get("P3b", {})
    dc_rows = disconnect_rows(dc, level_sources)
    return {
        "version": 1,
        "built": decision["run"]["generated_at"],
        "backtest_git_rev": decision["run"]["git_rev"],
        "prereg_commit": decision["prereg_commit"],
        "transcribed": ev.get("transcribed_on") or ev.get("transcribed"),
        "source_doc": ev.get("source_doc"),
        "question": QUESTION,
        "links": [
            {
                "id": l["id"],
                "title": l["title"],
                "direction": l.get("direction"),
                "strength": l.get("strength"),
                "summary": " ".join(str(l.get("summary", "")).split()),
                "findings": [
                    {k: f.get(k) for k in ("claim", "effect", "sample", "citation", "url", "verified", "companion_url", "companion_verified")}
                    for f in l.get("findings", [])
                ],
            }
            for l in ev["links"]
        ],
        "china": {
            "source": ev["china_1990_vs_today"].get("source"),
            "columns": ev["china_1990_vs_today"]["columns"],
            "rows": ev["china_1990_vs_today"]["rows"],
            "reading": " ".join(str(ev["china_1990_vs_today"].get("reading", "")).split()),
            "row": next((r for r in dc_rows if r["iso3"] == "CHN" and r["year"] == 1990), None),
        },
        "disconnect": {"meta": {k: dc["_meta"].get(k) for k in ("anchor", "span_years", "last_full_year", "msci_accessed", "msci_as_of", "vt_rule")}, "rows": dc_rows},
        "backtest": {
            "T_grid": bt["_meta"]["T_grid"],
            "returns_T": bt["_meta"]["returns_T"],
            "minpop_thousands": bt["_meta"]["minpop_thousands"],
            "B": bt["_meta"]["B"],
            "seed": bt["_meta"]["seed"],
            "prototype_rule": bt["_meta"]["prototype_rule"],
            "no_etf_rows": bt["_meta"].get("no_etf_rows", {}),
            "partial_note": results_partial_note(results_md),
            "growth": growth_row(bt, PRIMARY_GROWTH),
            "growth_20": growth_row(bt, PRIMARY_GROWTH_20),
            "returns": returns_row(bt, PRIMARY_RETURNS, manual),
            "n3": bt["n3"]["10|10"],
            "benchmarks": benchmarks(bt),
            "ew_minus_vt": p3b.get("ew_minus_vt_pp_per_yr"),
            "predictions": {k: {"statement": v["statement"], "met": v["met"]} for k, v in decision["predictions"].items()},
        },
        "decision": {
            "levels_granted": decision["levels_granted"],
            "levels": {k: {"name": v["name"], "granted": v["granted"], "requires": v["requires"], "failed": v["failed"], "unavailable": v["unavailable"], "note": v.get("note")} for k, v in decision["levels"].items()},
            "conditions": {k: {"value": v["value"], "ok": v["ok"], "available": v["available"], "detail": v["detail"]} for k, v in decision["conditions"].items()},
            "allowed_sentence_ids": sorted(decision["allowed_sentence_ids"]),
            "rendered": rendered,
            "rendered_notes": rendered_notes(rendered, universe, manual),
        },
        "units_note": UNITS_NOTE,
        "vintage": vintage(vint),
        "investability": investability(universe, manual),
        "deviations": results_deviations(results_md),
        "data_vintages": results_vintages(results_md),
        "licences": ev["licences"],
        "never_does": NEVER_DOES,
        "notice": notice,
    }


def main() -> int:
    decision = load_json(ECON / "decision.json")
    ui = load_yaml(ECON / "ui_sentences.yaml")
    bt = load_json(ECON / "backtest_lookalikes.json")
    dc = load_json(ECON / "disconnect.json")
    vint = load_json(ECON / "vintage" / "vintage_check.json")
    universe = load_yaml(ECON / "etf_universe.yaml")
    manual = load_yaml(ECON / "etf_manual.yaml")
    ev = load_yaml(ROOT / "evals" / "evidence.yaml")
    results_md = (ECON / "RESULTS.md").read_text()
    notice = (ECON / "NOTICE").read_text()
    level_sources = load_level_sources(ECON / "tables" / "gdp_pc.parquet")

    dump(OUT / "econ_decision.json", export_decision(decision))
    dump(OUT / "ui_sentences.json", export_sentences(ui))
    dump(OUT / "evidence.json", export_evidence(ev, decision, bt, dc, vint, universe, manual, results_md, notice, level_sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
