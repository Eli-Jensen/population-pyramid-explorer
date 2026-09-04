"""Web data export (CONTRACT §3 export / §5 formats, PLAN §3.4) — owner A2.

``write_web_data`` wipes ``web/public/data/<revision>/`` and writes every shard with a content hash in
its name (directories are hashed over their files' bytes in sorted name order), plus the imported
``web/src/data/{entities,meta}.json`` and ``data/out/build-report.json``. ``meta.files`` is the only
reference the web may use for shard paths (values are relative to ``web/public``).

Payload budgets are asserted per request class (``BUDGETS``, decimal KB/MB) and a ``BudgetError``
lists every violation. ``dir_total`` covers everything except ``emb/`` (each embedding space has its
own ≤ 6 MB budget; with the two image spaces the plan wants shipped the directory necessarily exceeds
16 MB, so the whole-directory number is reported both with and without them).
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer import bands as B
from pyramid_explorer.delta import decode_blob, encode_blob, layout_sizes
from pyramid_explorer.paths import (
    DATA_OUT,
    LAST_OBSERVED_YEAR,
    N_DIMS,
    N_YEARS,
    PIPELINE,
    REVISION,
    WEB,
    YEARS,
)
from pyramid_explorer.quantise import U16_TOTAL

KERNEL = [0.054, 0.242, 0.399, 0.242, 0.054]
EMB_DIM = 64
BUDGETS: dict[str, int] = {
    "first_paint": 175_000,   # gz(entities.json) + gz(meta.json) + largest entity shard + largest year shard + bands_default
    "entity_shard": 16_000,
    "year_shard": 32_000,
    "shares_d16z": 2_200_000,
    "shares_u16": 4_000_000,
    # CONTRACT/PLAN say 200 KB, derived for u16-scaled values and 14 metric×sex combos; the contract's
    # float32 layout with the full menu (8 snapshot + 3 trend + visual, ×2 sexes) measures ≈ 55 KB per
    # metric ⇒ ≈ 600–700 KB. Lazy-loaded once per session, so the budget is set to the measured class.
    "bands": 800_000,
    "emb": 6_000_000,
    "dir_total": 16_000_000,  # everything under the revision directory except emb/
}
WPP_ATTRIBUTION = (
    "Population data: United Nations, Department of Economic and Social Affairs, Population Division (2024). "
    "World Population Prospects 2024, Online Edition (medium variant). https://population.un.org/wpp/ — "
    "© 2024 United Nations, licensed under CC BY 3.0 IGO (https://creativecommons.org/licenses/by/3.0/igo/). "
    "Files under data/ are reshaped, share-normalised and 16-bit-quantised derivatives, not the original UN "
    "files; the UN does not endorse this site.")


class BudgetError(ValueError):
    """One or more payload classes exceed ``BUDGETS``."""


def sha8(data: bytes) -> str:
    """First 8 hex chars of sha256 over ``data``."""
    return hashlib.sha256(data).hexdigest()[:8]


def sha8_dir(files: dict[str, bytes]) -> str:
    """Directory hash: sha256 over the concatenation of the files' bytes in sorted name order."""
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(files[name])
    return h.hexdigest()[:8]


def _gz_len(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=6, mtime=0))  # ≈ what a CDN would send


def attribution_lines(patches: list[dict], sources_yaml: Path | None = None,
                      families: set[str] | None = None) -> list[str]:
    """Attribution strings of every redistributable row in ``pipeline/sources.yaml`` (A1) — restricted to
    ``families`` (e.g. ``{"wpp"}``) when given — with the WPP text as the fallback when the file is absent,
    plus a Togo-patch line when a patch was applied."""
    path = sources_yaml or PIPELINE / "sources.yaml"
    lines: list[str] = []
    if path.exists():
        import yaml

        doc = yaml.safe_load(path.read_text()) or {}
        rows = doc.get("sources", doc) if isinstance(doc, dict) else doc
        rows = list(rows.values()) if isinstance(rows, dict) else rows
        for r in rows:
            if not isinstance(r, dict) or not (r.get("redistributable") and r.get("attribution")):
                continue
            if families is not None and r.get("family") not in families:
                continue
            lines.append(str(r["attribution"]).strip())
    if not lines:
        lines.append(WPP_ATTRIBUTION)
    for p in patches or []:
        lines.append(f"Patch {p.get('id')}: UN interim update applied to LocID(s) {p.get('locids')}; "
                     f"aggregates {p.get('recomputed_aggregates', [])} recomputed from members by this site "
                     f"(the UN did not revise aggregates).")
    return lines


def _check_inputs(entities, keys, s42, u16) -> None:
    n_ent, n_rows = len(entities), len(keys)
    if n_rows != n_ent * N_YEARS:
        raise ValueError(f"keys has {n_rows} rows, expected {n_ent} entities × {N_YEARS}")
    if s42.shape != (n_rows, N_DIMS) or u16.shape != (n_rows, N_DIMS):
        raise ValueError(f"s42 {s42.shape} / u16 {u16.shape} must be [{n_rows}, {N_DIMS}]")
    ids = keys["id"].to_numpy()[::N_YEARS]
    if list(ids) != [e["id"] for e in entities]:
        raise ValueError("keys entity order differs from entities order")
    if not np.array_equal(keys["year"].to_numpy(), np.tile(YEARS, n_ent)):
        raise ValueError("keys years are not 1950..2100 entity-major")
    if not np.all(u16.sum(1, dtype=np.int64) == U16_TOTAL):
        raise ValueError("u16 rows must sum to exactly 65535")


def write_web_data(*, entities: list[dict], keys: pd.DataFrame, s42: np.ndarray, u16: np.ndarray,
                   bands: dict | None, sigma: dict, patches: list[dict], emb: dict[str, np.ndarray] | None = None,
                   out_root: Path | None = None, report_path: Path | None = None,
                   budgets: dict[str, int] | None = None, revision: str = REVISION,
                   families: set[str] | None = frozenset({"wpp"}), verdicts: dict | None = None) -> dict:
    """Write every web shard + entities/meta JSON + the build report; raise ``BudgetError`` on violation.

    ``out_root`` is the web directory (default ``web/``): shards go to ``<out_root>/public/data/<revision>/``
    and the JSON imports to ``<out_root>/src/data/``. The report is also written to ``report_path``
    (default ``data/out/build-report.json``) and returned. ``families`` selects which ``sources.yaml``
    families are cited in NOTICE (only WPP-derived files ship in M0; None = every redistributable row).
    ``verdicts`` (from ``evals/verdicts.json``, already hash-checked by the caller) is copied into ``meta.json``.
    """
    budgets = {**BUDGETS, **(budgets or {})}
    u16 = np.ascontiguousarray(u16, dtype=np.uint16)
    s42 = np.asarray(s42, dtype=np.float64)
    _check_inputs(entities, keys, s42, u16)
    n_ent, n_rows = len(entities), len(keys)
    n_countries = sum(e["type"] == "country" for e in entities)
    totals = keys["pop_total"].to_numpy(dtype="<f4")
    web = Path(out_root) if out_root else WEB
    data_dir = web / "public" / "data" / revision
    src_dir = web / "src" / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    src_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, object] = {}
    sizes: dict[str, object] = {}
    rel = f"data/{revision}"

    def write(name: str, data: bytes) -> Path:
        p = data_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    # year shards: n_entities × 42 u16 (entity order) + n_entities f32 totals
    year_files = {}
    for yi, year in enumerate(YEARS):
        rows = yi + N_YEARS * np.arange(n_ent)
        year_files[f"{year}.u16"] = u16[rows].astype("<u2").tobytes() + totals[rows].tobytes()
    ydir = f"years.{sha8_dir(year_files)}"
    for name, data in year_files.items():
        write(f"{ydir}/{name}", data)
    files["years"] = f"{rel}/{ydir}"
    sizes["year_shard_max"] = max(map(len, year_files.values()))

    # entity shards: 151 × 42 u16 + 151 f32 totals
    ent_files = {}
    for ei, e in enumerate(entities):
        sl = slice(ei * N_YEARS, (ei + 1) * N_YEARS)
        ent_files[f"{e['id']}.u16"] = u16[sl].astype("<u2").tobytes() + totals[sl].tobytes()
    pdir = f"pyramids.{sha8_dir(ent_files)}"
    for name, data in ent_files.items():
        write(f"{pdir}/{name}", data)
    files["pyramids"] = f"{rel}/{pdir}"
    sizes["entity_shard_max"] = max(map(len, ent_files.values()))

    # corpus blobs
    blob = encode_blob(u16)
    if not np.array_equal(decode_blob(blob, n_rows), u16):
        raise AssertionError("d16z round trip failed")
    singles = {
        "shares_d16z": (f"shares.{sha8(blob)}.d16z", blob),
        "shares_u16": (f"shares.{sha8(u16.astype('<u2').tobytes())}.u16", u16.astype("<u2").tobytes()),
        "totals": (f"totals.{sha8(totals.tobytes())}.f32", totals.tobytes()),
    }
    bands_bytes = B.serialize_bands(bands or {})
    default_bytes = B.serialize_bands(B.default_subset(bands or {}))
    singles["bands"] = (f"bands.{sha8(bands_bytes)}.bin", bands_bytes)
    singles["bands_default"] = (f"bands_default.{sha8(default_bytes)}.bin", default_bytes)
    for key, (name, data) in singles.items():
        write(name, data)
        files[key] = f"{rel}/{name}"
        sizes[key] = len(data)

    # embeddings (PCA-64, float16)
    files["emb"], sizes["emb"] = {}, {}
    for model, Z in (emb or {}).items():
        Z = np.asarray(Z)
        if Z.shape != (n_rows, EMB_DIM):
            raise ValueError(f"emb[{model}] must be [{n_rows}, {EMB_DIM}], got {Z.shape}")
        data = Z.astype("<f2").tobytes()
        name = f"emb/{model}.{sha8(data)}.f16"
        write(name, data)
        files["emb"][model] = f"{rel}/{name}"
        sizes["emb"][model] = len(data)

    attribution = attribution_lines(patches, families=families)
    write("NOTICE", ("\n\n".join(attribution) + "\n").encode("utf-8"))
    files["notice"] = f"{rel}/NOTICE"

    # imported JSON
    entities_json = json.dumps(entities, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    (src_dir / "entities.json").write_bytes(entities_json)
    sizes["entities_json"] = len(entities_json)
    sizes["entities_gz"] = _gz_len(entities_json)
    sizes["layouts"] = layout_sizes(u16)
    sizes["bands_tables"] = _bands_table_counts(bands or {})
    meta = {
        "revision": revision, "patches": patches or [], "built": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "last_observed_year": LAST_OBSERVED_YEAR, "n_entities": n_ent, "n_countries": n_countries, "n_rows": n_rows,
        "n_years": N_YEARS, "files": files, "sigma": sigma, "kernel": KERNEL, "budgets": budgets, "sizes": sizes,
        "attribution": attribution, "bands_grid": B.GRID,
        "bands_format": "u32 LE json length + JSON {name:[offset,count]} (float32 elements) + float32 LE values",
    }
    if verdicts is not None:
        meta["verdicts"] = verdicts
    meta_json = _write_meta(src_dir / "meta.json", meta, sizes, data_dir)
    report = {k: meta[k] for k in ("revision", "patches", "built", "n_entities", "n_countries", "n_rows", "files",
                                   "sigma", "budgets", "sizes")}
    report["axis_distribution"] = _axis_distribution(entities)
    if verdicts is not None:
        report["verdicts"] = verdicts
    report["checks"] = {"u16_row_sums_65535": True, "d16z_round_trip": True, "budgets": _violations(sizes, budgets)}
    report["meta_json_bytes"] = len(meta_json)
    rp = Path(report_path) if report_path else DATA_OUT / "build-report.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=1))
    if report["checks"]["budgets"]:
        raise BudgetError("payload budget violated: " + "; ".join(report["checks"]["budgets"]))
    return report


def _write_meta(path: Path, meta: dict, sizes: dict, data_dir: Path) -> bytes:
    """Serialise meta.json; ``sizes.meta_gz`` / ``first_paint`` / ``dir_total`` depend on the JSON itself,
    so iterate to a fixed point (the digit count stabilises after one or two rounds)."""
    dir_files = [p for p in data_dir.rglob("*") if p.is_file()]
    with_emb = sum(p.stat().st_size for p in dir_files)
    no_emb = sum(p.stat().st_size for p in dir_files if "emb" not in p.relative_to(data_dir).parts)
    sizes.update({"dir_total": no_emb, "dir_total_with_emb": with_emb, "meta_gz": 0, "first_paint": 0})
    for _ in range(5):
        data = json.dumps(meta, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        gz = _gz_len(data)
        fp = sizes["entities_gz"] + gz + sizes["entity_shard_max"] + sizes["year_shard_max"] + sizes["bands_default"]
        if (gz, fp) == (sizes["meta_gz"], sizes["first_paint"]):
            break
        sizes["meta_gz"], sizes["first_paint"] = gz, fp
    path.write_bytes(data)
    return data


def _violations(sizes: dict, budgets: dict) -> list[str]:
    checks = {
        "first_paint": sizes["first_paint"], "entity_shard": sizes["entity_shard_max"],
        "year_shard": sizes["year_shard_max"], "shares_d16z": sizes["shares_d16z"], "shares_u16": sizes["shares_u16"],
        "bands": sizes["bands"], "dir_total": sizes["dir_total"],
    }
    for model, n in sizes["emb"].items():
        checks[f"emb:{model}"] = n
    out = []
    for name, value in checks.items():
        limit = budgets["emb"] if name.startswith("emb:") else budgets[name]
        if value > limit:
            out.append(f"{name} {value:,} B > {limit:,} B")
    return out


def _axis_distribution(entities: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entities:
        k = str(e.get("axis_pct", "?"))
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items()))


def _bands_table_counts(bands: dict) -> dict[str, dict[str, int]]:
    """Number of tables and LOGICAL float32 bytes per family/metric (for the build report). Sex-blind metrics
    alias their sex='1' tables onto '2' in the file, so their stored bytes are half the logical figure."""
    out: dict[str, dict[str, int]] = {}
    for name, vals in B.flatten_bands(bands).items():
        fam, metric = name.split("/")[:2]
        key = f"{fam}/{metric}"
        out.setdefault(key, {"tables": 0, "bytes": 0})
        out[key]["tables"] += 1
        out[key]["bytes"] += 4 * len(vals)
    return out
