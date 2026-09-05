#!/usr/bin/env python
"""Export the similarity-evaluation record for the About page → ``web/src/data/evals.json``.

    uv run scripts/export_evals.py                  # the last step of `make build`
    uv run scripts/export_evals.py --check          # exit 1 if the committed file is stale

Sources, in order of authority:
  1. ``evals/verdicts.json``   — verdict + gates + a `numbers` block per metric, `exposed_visual`, `_meta`
                                 (data_hash, stage, label fallback, β-sweep, blend W1 share).
  2. ``evals/RESULTS.md``      — fallback table parse for the columns the numbers block does not carry
                                 (G1 C5 on projected years, Korenjak-Černe 1996/2001) and a cross-check of C1/C5.
  3. ``evals/image_embeddings.md`` — the pre-registered predictions table (§2, frozen before the run) and the
                                 results block (per-model C1 full / PCA-64, ρ vs blend, top-10 overlap), if parseable.

The About page renders every number from this file (and from meta.json); nothing there is hardcoded.  The
verdicts are INFORMATIONAL per DECISION 4 — both `blend` and the exposed image space ship — and the file says so
in `stage` / `informational`.  Deterministic: no wall-clock is written (``built`` is copied from verdicts.json), so
a rebuild without new evals leaves the file byte-identical.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
OUT = REPO / "web" / "src" / "data" / "evals.json"
META = REPO / "web" / "src" / "data" / "meta.json"   # written earlier in the same `make build`; read for the SHIPPED verdicts

# Gates as pre-registered in evals/protocol.md and applied by scripts/eval_similarity.py (kept in step by the
# `gates` cross-check below: a metric's G1 gate in verdicts.json must equal (C1 ≥ c1) ∧ (C5 ≥ c5)).
GATES = {"c1": 0.95, "c5": 0.99, "kc_agree": 0.7, "hk_agree": 0.85, "stage_agree": 0.9, "lab_c1": 0.8, "reject_hk": 0.6}
EXPECTED_VISUAL_VERDICT = "lab"   # evals/image_embeddings.md §2


# ------------------------------------------------------------------------------------------ markdown helpers
def md_tables(text: str) -> list[list[list[str]]]:
    """Every pipe table in a markdown document as rows of stripped cells (header row first, separator dropped)."""
    tables, cur = [], []
    for line in text.splitlines():
        if line.startswith("|"):
            # `\|` inside a cell is a literal pipe, not a column break
            cells = [c.strip().replace("\x00", "|") for c in line.strip().replace("\\|", "\x00").strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue
            cur.append(cells)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def table_with_header(tables: list[list[list[str]]], first_col: str, must_have: str) -> list[list[str]] | None:
    for t in tables:
        if t and t[0] and t[0][0] == first_col and any(must_have in c for c in t[0]):
            return t
    return None


def num(cell: str) -> float | None:
    """'0.9500 ✓' → 0.95; '1994 ✓' → 1994; '–' → None."""
    m = re.search(r"-?\d+(?:\.\d+)?", cell.replace("−", "-"))
    return float(m.group()) if m else None


def tick(cell: str) -> bool | None:
    return True if "✓" in cell else False if "✗" in cell else None


def strip_code(s: str) -> str:
    return s.strip().strip("`")


# ------------------------------------------------------------------------------------------ RESULTS.md parse
def parse_results(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    tables = md_tables(text)
    out: dict = {"g1": {}, "g2": {}, "verdicts": {}}
    g1 = table_with_header(tables, "metric", "C1 obs")
    if g1:
        for row in g1[1:]:
            if len(row) >= 6:
                out["g1"][strip_code(row[0])] = {
                    "c1_obs": num(row[1]), "c5_obs": num(row[2]), "c1_proj": num(row[3]), "c5_proj": num(row[4]),
                    "gate": tick(row[5]),
                }
    g2 = table_with_header(tables, "metric", "KC2006")
    if g2:
        for row in g2[1:]:
            if len(row) >= 10:
                out["g2"][strip_code(row[0])] = {
                    "kc2006": num(row[1]), "kc1996": num(row[2]), "kc2001": num(row[3]), "hk_family": num(row[4]),
                    "hk_fine": num(row[5]), "stage": num(row[6]), "rieti_best_year": num(row[7]),
                    "yoshida_hits": row[8].split(" ")[0], "gate": tick(row[9]),
                }
    v = table_with_header(tables, "metric", "verdict")
    if v:
        for row in v[1:]:
            if len(row) >= 2:
                out["verdicts"][strip_code(row[0])] = row[1].strip("* ")
    m = re.search(r"Built (\S+) · git `([0-9a-f]+)`", text)
    if m:
        out["built"], out["git_head"] = m.group(1), m.group(2)
    return out


# ------------------------------------------------------------------------------------- image_embeddings.md
def parse_image_embeddings(path: Path) -> dict:
    if not path.exists():
        return {"predictions": [], "spaces": []}
    text = path.read_text(encoding="utf-8")
    # The preamble quotes the marker in backticks, so anchor it to a line of its own.
    pre = re.split(r"^<!-- results:start -->\s*$", text, maxsplit=1, flags=re.M)[0]
    tables = md_tables(pre)
    preds = []
    pt = table_with_header(tables, "id", "prediction")
    if pt:
        for row in pt[1:]:
            if len(row) >= 4 and re.fullmatch(r"P\d+", row[0]):
                preds.append({"id": row[0], "prediction": row[1].replace("\\|", "|"), "gate": row[2].replace("\\|", "|"),
                              "measured_by": row[3]})
    spaces = []
    res_m = re.search(r"^<!-- results:start -->\s*$(.*?)^<!-- results:end -->", text, re.S | re.M)
    if res_m:
        rt = table_with_header(md_tables(res_m.group(1)), "model", "C1 obs")
        if rt:
            for row in rt[1:]:
                if len(row) < 10:
                    continue
                c1 = [num(x) for x in row[3].split("/")]
                spaces.append({
                    "model": strip_code(row[0]), "img_per_s": num(row[1]), "wall": row[2],
                    "c1_full": c1[0] if c1 else None, "c1_pca64": c1[1] if len(c1) > 1 else None,
                    "c5_obs": num(row[4]), "c1_proj": num(row[5]), "spearman_vs_blend": num(row[6]),
                    "spearman_vs_l2": num(row[7]),
                    "top10_overlap": (num(row[8]) or 0) / 100 if "%" in row[8] else num(row[8]),
                    "top10_overlap_anyyear": (num(row[10]) or 0) / 100 if len(row) > 10 and "%" in row[10] else None,
                })
        # auto-scored predictions per model: "- `model`: P1/P2 … → 0.605 **met**; …"
        scored = {}
        for m in re.finditer(r"^- `([^`]+)`: (P\d.*)$", res_m.group(1), re.M):
            items = []
            for part in m.group(2).split(";"):
                pm = re.match(r"\s*(P\d(?:/P\d)?)\s+(.*?)→\s*([-\d.]+)\s+\*\*(met|NOT met)\*\*", part)
                if pm:
                    items.append({"id": pm.group(1), "test": pm.group(2).strip(), "observed": float(pm.group(3)),
                                  "met": pm.group(4) == "met"})
            scored[m.group(1)] = items
        for s in spaces:
            s["predictions_scored"] = scored.get(s["model"], [])
    return {"predictions": preds, "spaces": spaces}


# ------------------------------------------------------------------------------------------------- assemble
def build(verdicts_path: Path, results_path: Path, image_path: Path, meta_path: Path | None = None) -> dict:
    v = json.loads(verdicts_path.read_text(encoding="utf-8"))
    meta = v.get("_meta", {})
    # What the UI actually ships: build_data.load_verdicts caps a metric without percentile tables in this build
    # (evaluation-only `clr`) at `lab`, and marks the whole block stale when the data hash moved.
    shipped: dict = {}
    if meta_path and meta_path.exists():
        shipped = json.loads(meta_path.read_text(encoding="utf-8")).get("verdicts", {}) or {}
    shipped_metrics = shipped.get("metrics", {})
    results = parse_results(results_path)
    image = parse_image_embeddings(image_path)
    metrics = [k for k in v if not k.startswith("_") and isinstance(v[k], dict) and "verdict" in v[k]]

    g1_rows, g2_rows, verdict_map = [], [], {}
    for m in metrics:
        n = v[m].get("numbers", {})
        r1, r2 = results.get("g1", {}).get(m, {}), results.get("g2", {}).get(m, {})
        c1, c5 = n.get("C1_obs", r1.get("c1_obs")), n.get("C5_obs", r1.get("c5_obs"))
        for k, a, b in (("C1", c1, r1.get("c1_obs")), ("C5", c5, r1.get("c5_obs"))):
            if a is not None and b is not None and abs(a - b) > 6e-4:
                raise SystemExit(f"{m}: {k} disagrees between verdicts.json ({a}) and RESULTS.md ({b})")
        gate_g1 = v[m]["gates"]["G1"]
        if c1 is not None and c5 is not None and gate_g1 != (c1 >= GATES["c1"] and c5 >= GATES["c5"]):
            raise SystemExit(f"{m}: G1 gate {gate_g1} inconsistent with C1 {c1} / C5 {c5} and gates {GATES}")
        g1_rows.append({"metric": m, "c1_obs": c1, "c5_obs": c5, "c1_proj": n.get("C1_proj", r1.get("c1_proj")),
                        "c5_proj": r1.get("c5_proj"), "gate": gate_g1})
        g2_rows.append({
            "metric": m, "kc2006": n.get("kc2006_agree", r2.get("kc2006")), "kc1996": r2.get("kc1996"),
            "kc2001": r2.get("kc2001"), "hk_family": n.get("hk_agree", r2.get("hk_family")),
            "hk_fine": n.get("hk_agree_fine", r2.get("hk_fine")), "stage": n.get("stage_agree", r2.get("stage")),
            "rieti_best_year": n.get("rieti_best_year", r2.get("rieti_best_year")),
            "yoshida_hits": r2.get("yoshida_hits"), "yoshida_pass": n.get("yoshida_pass"),
            "g4_pass": n.get("g4_pass"), "gate": v[m]["gates"].get("G2"), "gates": v[m]["gates"],
        })
        sv = shipped_metrics.get(m, {}).get("verdict")
        verdict_map[m] = {"verdict": v[m]["verdict"], "provisional": bool(v[m].get("provisional", False)),
                          "shipped": sv,   # None = not in the web metric set / meta.json absent
                          **({"scope": v[m]["scope"]} if v[m].get("scope") else {})}
        if sv and sv != v[m]["verdict"]:
            verdict_map[m]["shipped_note"] = ("capped at lab — no percentile tables are shipped for this evaluation-only "
                                              "metric" if sv == "lab" else "differs from the evaluation verdict")
        rv = results.get("verdicts", {}).get(m)
        if rv and rv != v[m]["verdict"]:
            raise SystemExit(f"{m}: verdict differs between verdicts.json ({v[m]['verdict']}) and RESULTS.md ({rv})")

    # image spaces: verdict-side numbers first, embed-script diagnostics (ρ, overlap, full vs PCA-64 C1) merged in
    by_model = {s["model"]: s for s in image["spaces"]}
    image_spaces = []
    for m in metrics:
        if not m.startswith("visual:"):
            continue
        model = m[len("visual:"):]
        s = by_model.get(model, {})
        n = v[m].get("numbers", {})
        image_spaces.append({
            "model": model, "metric": m, "verdict": v[m]["verdict"],
            "c1": n.get("C1_obs"), "c5": n.get("C5_obs"), "c1_proj": n.get("C1_proj"),
            "c1_full_dim": s.get("c1_full"), "c1_pca64_embed_script": s.get("c1_pca64"),
            "hk_family": n.get("hk_agree"), "kc2006": n.get("kc2006_agree"), "stage": n.get("stage_agree"),
            "spearman_vs_blend": s.get("spearman_vs_blend"), "spearman_vs_l2": s.get("spearman_vs_l2"),
            "top10_overlap": s.get("top10_overlap"), "top10_overlap_anyyear": s.get("top10_overlap_anyyear"),
            "predictions_scored": s.get("predictions_scored", []),
            "expected_verdict": EXPECTED_VISUAL_VERDICT,
            "prediction_met": v[m]["verdict"] == EXPECTED_VISUAL_VERDICT,
        })

    exposed = v.get("exposed_visual")
    if shipped and shipped.get("data_hash") and shipped.get("data_hash") != v.get("data_hash"):
        raise SystemExit(f"data_hash differs: evals {v.get('data_hash')} vs meta.json {shipped.get('data_hash')} — rebuild")
    notes = [
        "Verdicts are informational (DECISION 4): both the numeric default and the exposed image space ship; "
        "'Visual' is labelled experimental in the metric menu.",
        f"Stage: {meta.get('stage', 'unknown')} — the human-triplet test (M4) has not run; 'menu' verdicts marked "
        "provisional await it.",
        "G2(e) Yoshida epitomes is reported, not gated (protocol.md §4 amendment: the paper's own metric fails its "
        "targets on WPP 2024 rows because Bolivia and Puerto Rico were revised between WPP 2015 and WPP 2024).",
    ]
    lf = meta.get("label_fallback", {})
    if lf:
        notes.append(f"Korenjak-Černe labels: fallback rung '{lf.get('korenjak_cerne')}' (2015 memberships paywalled; "
                     f"2008 lists, IDB-2008 vintage); vintage-sensitivity row {lf.get('vintage_sensitivity_row')}.")
    notes.append("The opposites coverage target (≥ 3 shape classes and ≥ 3 UN regions among 5 opposites) fails for every "
                 "metric and is structural: the diversity term works over shape distance, and the farthest quartile "
                 "from an old anchor is entirely young pyramids, so no β buys regional variety.")

    findings = meta.get("findings", {})
    return {
        "built": meta.get("built") or results.get("built"),
        "git_head": meta.get("git_head") or results.get("git_head"),
        "stage": meta.get("stage"),
        "informational": bool(meta.get("informational", True)),
        "data_hash": v.get("data_hash"),
        "data_hash_definition": meta.get("data_hash_definition"),
        "emb_meta_hash": v.get("emb_meta_hash", {}),
        "n_rows": meta.get("n_rows"), "n_entities": meta.get("n_entities"), "n_countries": meta.get("n_countries"),
        "n_queries": meta.get("n_queries"), "n_anchors": meta.get("n_anchors"), "seed": meta.get("seed"),
        "gates": GATES,
        "prereg": {
            "continuity_gate": {"c1": GATES["c1"], "c5": GATES["c5"], "span": "observed 1950–2023 query years",
                                "definition": "C1 = P(nearest neighbour is the same country within ±1 year), self excluded; "
                                              "C5 = the same within the 5 nearest"},
            "image_predictions": image["predictions"],
            "expected_visual_verdict": EXPECTED_VISUAL_VERDICT,
            "niche": "Visual may claim a win only on triplets whose anchor carries a detected cohort notch/bulge "
                     "(paired sign test, α = 0.05); no other post-hoc claim is admissible.",
        },
        "g1": g1_rows,
        "g2": g2_rows,
        "verdicts": verdict_map,
        "verdicts_stale_in_build": bool(shipped.get("stale", False)) if shipped else None,
        "exposed_visual": exposed,
        "image_spaces": image_spaces,
        "blend_w1_share": findings.get("blend_w1_share"),
        "beta_sweep": findings.get("beta_sweep"),
        "div_presets": findings.get("div_presets"),
        "hk_family_counts_2024": meta.get("hk_family_counts_2024"),
        "labels_sha256": {k: h[:16] for k, h in meta.get("labels_sha256", {}).items()},
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--verdicts", type=Path, default=EVALS / "verdicts.json")
    p.add_argument("--results", type=Path, default=EVALS / "RESULTS.md")
    p.add_argument("--image", type=Path, default=EVALS / "image_embeddings.md")
    p.add_argument("--meta", type=Path, default=META, help="web/src/data/meta.json (shipped verdicts); skipped if absent")
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--check", action="store_true", help="do not write; exit 1 if the file on disk differs")
    a = p.parse_args(argv)
    doc = build(a.verdicts, a.results, a.image, a.meta)
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if a.check:
        if not a.out.exists() or a.out.read_text(encoding="utf-8") != text:
            print(f"{a.out} is stale — run scripts/export_evals.py", file=sys.stderr)
            sys.exit(1)
        print(f"{a.out} up to date")
        return
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8")
    n_img = len(doc["image_spaces"])
    print(f"wrote {a.out.relative_to(REPO)}: {len(doc['g1'])} metrics, {n_img} image spaces, "
          f"{len(doc['prereg']['image_predictions'])} pre-registered predictions, {len(text.encode())} bytes")


if __name__ == "__main__":
    main()
