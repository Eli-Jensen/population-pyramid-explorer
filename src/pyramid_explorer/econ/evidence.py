"""``web/src/data/{evidence,econ_decision,ui_sentences}.json`` — the Evidence page's numbers, every one read from a file.

The base schema is the one ``pages/Evidence.svelte`` consumes and ``scripts/export_econ_ui.py`` established (decision
trimmed, sentence templates + deny list, the four links, the China row, the primary backtest rows, the disconnect
table, the vintage Jaccard table, the investability table, deviations, licences). That script's functions are reused
here (loaded from ``scripts/``) so the two cannot drift; this module adds the blocks only the M5 export knows:

* ``instruments``   — per-country status / class / mobility / derived fund statistics (``evals/instruments.yaml``);
* ``guard``         — the survivorship-guard summary (``data/out/etf_guard_report.json`` when present);
* ``typology``      — thresholds, citation and the 2015 reproduction against WPS7893 Table A1;
* ``econ_coverage`` — the spliced series' coverage and the 2024 stage distribution;
* ``msci_facts``    — the hand-transcribed factsheet facts (``evals/econ/msci_citations.yaml``), dates as strings.

``notice`` is the NOTICE that actually ships (``web/public/data/<revision>/NOTICE``). The finished JSON is scanned with
the shipped-data licence regex (weo|imf|ngdp) before it is written — the page must never name a non-redistributable
source as if it were shipped data.
"""
from __future__ import annotations

import importlib.util
import json
import re
from datetime import date
from pathlib import Path

import yaml

from pyramid_explorer.paths import DATA_OUT, ECON_EVALS, EVALS, REPO_ROOT, REVISION, WEB_DATA, WEB_SRC_DATA

UI_SCRIPT = REPO_ROOT / "scripts" / "export_econ_ui.py"
EVIDENCE_YAML = EVALS / "evidence.yaml"
LICENCE_RE = re.compile(r"weo|imf|ngdp", re.I)


def load_ui_module():
    """``scripts/export_econ_ui.py`` as a module (the schema owner for the Evidence page)."""
    if not UI_SCRIPT.exists():
        raise FileNotFoundError(f"{UI_SCRIPT} is missing — the Evidence page schema lives there")
    spec = importlib.util.spec_from_file_location("export_econ_ui", UI_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _plain(o):
    """JSON-safe: dates → ISO strings, tuples → lists."""
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, float) and o != o:
        return None
    return o


def guard_summary(path: Path = DATA_OUT / "etf_guard_report.json") -> dict:
    if not path.exists():
        return {"available": False, "note": "data/out/etf_guard_report.json is not present in this checkout (written by `make backtest`); RESULTS.md §2 carries the recorded run"}
    g = json.loads(path.read_text(encoding="utf-8"))
    t = g.get("tickers", {})
    return {"available": True, "generated_at": g.get("generated_at"), "thresholds": g.get("thresholds"), "n_tickers": len(t),
            "passed": sum(1 for r in t.values() if r.get("passed")), "route_manual": sorted(k for k, r in t.items() if r.get("route") == "manual"),
            "deviations": {k: r["deviation"] for k, r in t.items() if r.get("deviation")},
            "violations": {k: r["violations"] for k, r in t.items() if r.get("violations")}}


def instruments_block(inst_doc: dict) -> dict:
    keep = ("ticker", "name", "issuer", "inception", "status", "delisted", "delisted_universe", "liquidation_date", "msci_class", "status_url", "source_url",
            "since_inception_cagr_pct", "vt_same_window_pct", "benchmark", "window", "basis", "n_full_years", "contiguous",
            "cagr_10y_pct", "cagr_10y_vt_pct", "cagr_10y_window", "cagr_10y_benchmark", "cagr_10y_status", "cagr_10y_incomplete", "max_dd_pct", "max_dd_basis", "as_of")
    countries = {iso3: {"status": c["status"], "msci_class": c.get("msci_class"), "msci_class_source": c.get("msci_class_source"), "mobility": c["mobility"],
                        "tickers": [{k: t.get(k) for k in keep if k in t} for t in c.get("tickers", [])], "events": c.get("events", [])}
                 for iso3, c in inst_doc["countries"].items()}
    return {"as_of": inst_doc.get("as_of"), "universe_as_of": inst_doc.get("universe_as_of"), "counts": inst_doc.get("counts"),
            "countries": countries, "baskets": [{k: t.get(k) for k in keep if k in t} for t in inst_doc.get("baskets", [])],
            "mobility_rule": "standalone or an index_deletion event → closed; FM with a repatriation event → restricted; EM / DM → open; otherwise not_assessed"}


def build_all(*, inst_doc: dict, typology_doc: dict, typology_reproduction: dict | None, splice_coverage: dict,
              stage_distribution: dict | None, revision: str = REVISION) -> dict[str, dict]:
    """``{'econ_decision': …, 'ui_sentences': …, 'evidence': …}`` — the three documents, not yet written."""
    ui = load_ui_module()
    decision = ui.load_json(ECON_EVALS / "decision.json")
    sentences = ui.load_yaml(ECON_EVALS / "ui_sentences.yaml")
    bt = ui.load_json(ECON_EVALS / "backtest_lookalikes.json")
    dc = ui.load_json(ECON_EVALS / "disconnect.json")
    vint = ui.load_json(ECON_EVALS / "vintage" / "vintage_check.json")
    universe = ui.load_yaml(ECON_EVALS / "etf_universe.yaml")
    manual = ui.load_yaml(ECON_EVALS / "etf_manual.yaml")
    ev = ui.load_yaml(EVIDENCE_YAML)
    results_md = (ECON_EVALS / "RESULTS.md").read_text(encoding="utf-8")
    notice_path = WEB_DATA / revision / "NOTICE"
    notice = notice_path.read_text(encoding="utf-8") if notice_path.exists() else ""

    level_sources = ui.load_level_sources(ECON_EVALS / "tables" / "gdp_pc.parquet")
    evidence = ui.export_evidence(ev, decision, bt, dc, vint, universe, manual, results_md, notice, level_sources)
    # evals/evidence.yaml wording wins over the script's built-in copies (its wording keeps the licence guard clean)
    for k in ("question", "never_does"):
        if ev.get(k):
            evidence[k] = ev[k]
    # build-time-only sources stay in evals/econ/RESULTS.md §1; the shipped page lists shipped sources only
    vint_rows = evidence.get("data_vintages") or []
    kept = [r for r in vint_rows if not LICENCE_RE.search(json.dumps(r, ensure_ascii=False))]
    evidence["data_vintages"] = kept
    evidence["data_vintages_note"] = (f"{len(vint_rows) - len(kept)} build-time-only source(s) (never exported) are listed in evals/econ/RESULTS.md §1, not here"
                                      if len(kept) != len(vint_rows) else None)
    citations = yaml.safe_load((ECON_EVALS / "msci_citations.yaml").read_text(encoding="utf-8"))
    evidence["instruments"] = instruments_block(inst_doc)
    evidence["guard"] = guard_summary()
    evidence["typology"] = {"citation": typology_doc["source"]["citation"], "url": typology_doc["source"]["url"],
                            "verified": typology_doc["source"].get("verified"), "adapted": True, "thresholds": typology_doc["thresholds"],
                            "codes": {str(k): v for k, v in typology_doc["codes"].items()},
                            "reproduction_2015": None if typology_reproduction is None else
                            {k: typology_reproduction[k] for k in ("year", "n", "agree", "rate", "named_all_agree", "named_disagree", "disagreements")}}
    evidence["econ_coverage"] = {**splice_coverage, "stage_distribution_latest": stage_distribution}
    evidence["msci_facts"] = _plain({"accessed": citations.get("accessed"), "as_of": citations.get("as_of"), "currency": citations.get("currency"),
                                     "note_on_use": citations.get("note_on_use"), "indexes": citations.get("indexes")})
    evidence["notice_source"] = str(notice_path.relative_to(REPO_ROOT)) if notice_path.exists() else None
    return {"econ_decision": ui.export_decision(decision), "ui_sentences": ui.export_sentences(sentences), "evidence": _rename_keys(_plain(evidence), {"picks": "members"})}


def _rename_keys(o, mapping: dict[str, str]):
    """Rename dict keys throughout ``o``. The backtest JSON calls a cohort's lookalikes ``picks``; that word is on the
    language deny-list (PLAN §7), and a grep over web/src must stay clean even for keys nothing renders."""
    if isinstance(o, dict):
        return {mapping.get(k, k): _rename_keys(v, mapping) for k, v in o.items()}
    if isinstance(o, list):
        return [_rename_keys(v, mapping) for v in o]
    return o


def write_all(docs: dict[str, dict], out_dir: Path = WEB_SRC_DATA) -> dict[str, int]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name, doc in docs.items():
        text = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
        m = LICENCE_RE.search(text)
        if m:
            ctx = text[max(0, m.start() - 60):m.end() + 60].replace("\n", " ")
            raise RuntimeError(f"{name}.json would name a non-redistributable source ({m.group()!r}): …{ctx}…")
        (out_dir / f"{name}.json").write_text(text, encoding="utf-8")
        sizes[name] = len(text.encode("utf-8"))
    return sizes
