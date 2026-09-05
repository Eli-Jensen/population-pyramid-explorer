#!/usr/bin/env python
"""M5 econ export — the last step of `make build`:

    uv run --group econ scripts/build_econ.py            # everything
    uv run --group econ scripts/build_econ.py --check    # exit 1 when a shipped econ file is stale (no writes)

Chain (all read-only against data/processed/explorer.duckdb; redistributable sources only; no network):
  1. econ.splice      → spliced gdppc / growth / income / TFR 1950–2024 per country
  2. econ.typology    → dividend stage per (country, year) (pipeline/typology.yaml; WPS7893 reproduction report)
  3. econ.instruments → evals/instruments.yaml (hand-editable header + generated body)
  4. econ.export_econ → web/public/data/wpp2024/econ.{sha8}.ecz, web/src/data/econ_entities.json, meta.json files.econ, NOTICE line
  5. econ.evidence    → web/src/data/{evidence,econ_decision,ui_sentences}.json
Prints sizes, coverage, the 2024 stage distribution and the instrument status counts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyramid_explorer import db
from pyramid_explorer.econ import evidence as EV, export_econ as X, instruments as I, splice as S, typology as T
from pyramid_explorer.paths import REPO_ROOT, REVISION, WEB_DATA, WEB_SRC_DATA


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="verify the shipped econ file is registered and fresh; write nothing")
    p.add_argument("--built", default=None, help="override the header's `built` timestamp (tests)")
    a = p.parse_args(argv)

    with db.connect(read_only=True) as con:
        inputs = S.load_inputs(con)
        splice = S.build_splice(inputs)
        thr = T.load_thresholds()
        stages = T.build_stages(con, thresholds=thr, tfr=inputs["tfr"])
        built_store = dict(con.execute("SELECT key, value FROM build_meta").fetchall()).get("built")
    ids = list(inputs["_countries"])
    cov = S.coverage(splice)
    repro = T.reproduction_report(stages, thr["_doc"])
    dist_latest = T.distribution(stages, S.YEAR_MAX)

    inst_doc = I.build_instruments(country_ids=ids)

    if a.check:
        meta = json.loads((WEB_SRC_DATA / "meta.json").read_text(encoding="utf-8"))
        rel = meta.get("files", {}).get("econ")
        ok = bool(rel) and (REPO_ROOT / "web" / "public" / rel).exists()
        print(f"meta.files.econ = {rel!r}: {'present' if ok else 'MISSING'}")
        return 0 if ok else 1

    I.write_instruments(inst_doc)
    rep = X.export(splice=splice, stages=stages, ids=ids, inst_doc=inst_doc, typology_doc=thr["_doc"], typology_reproduction=repro, built=a.built or built_store)
    docs = EV.build_all(inst_doc=inst_doc, typology_doc=thr["_doc"], typology_reproduction=repro, splice_coverage=cov, stage_distribution=dist_latest)
    sizes = EV.write_all(docs)

    print(f"wrote web/public/{rep['file']}: {rep['bytes_gz']} B gz ({rep['bytes_raw']} B raw, header {rep['header_bytes']} B) "
          f"— {rep['n_countries']} countries × {rep['n_years']} years; budget {X.SIZE_BUDGET} B")
    print(f"coverage: gdppc ≥ {cov['min_years']} y for {cov['gdppc_ge_min']}/{cov['n_countries']} countries; "
          f"below: {len(cov['below_min'])} ({', '.join(cov['below_min'])}); flags {cov['flags']}; g10 {cov['g10_flags']}; "
          f"rescale {cov['rescale']}")
    print(f"stage {S.YEAR_MAX}: {dist_latest}; typology 2015 reproduction: {repro['agree']}/{repro['n']} ({repro['rate']:.0%}), "
          f"named all agree: {repro['named_all_agree']} {repro['named_disagree'] or ''}")
    print(f"instruments: {inst_doc['counts']['status']} over {inst_doc['counts']['countries']} countries; mobility {inst_doc['counts']['mobility']}; "
          f"{rep['instruments']}")
    print(f"web/src/data: econ_entities {rep['econ_entities_bytes']} B; " + ", ".join(f"{k} {v} B" for k, v in sizes.items())
          + f"; meta registered: {rep['meta_registered']}; NOTICE line added: {rep['notice_line_added']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
