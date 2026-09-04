"""DuckDB store (A1) — the ONLY module importing duckdb (CONTRACT AMENDMENTS §A).

``data/processed/explorer.duckdb`` is rebuilt from scratch by ``scripts/build_data.py`` as a pure
function of manifest-pinned raw files + ``pipeline/*.yaml`` + code; the files under
``data/processed/`` (CONTRACT §1) are EXPORTS of this store (:func:`export_processed`).
Rule: numpy implements metrics; SQL asks questions. The row index is derived by the
``corpus_row`` view (``entity_idx*151 + (year-1950)``) and never stored by hand.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import yaml

from pyramid_explorer.data.wpp import WPP_INDICATORS
from pyramid_explorer.paths import (DATA_PROCESSED, LAST_OBSERVED_YEAR, N_BINS, N_DIMS, N_YEARS, PIPELINE,
                                    REPO_ROOT, REVISION, YEARS)

SCHEMA_VERSION = "1"
SCHEMA_SQL = Path(__file__).with_name("schema.sql")
DB_PATH = DATA_PROCESSED / "explorer.duckdb"
SOURCES_YAML = PIPELINE / "sources.yaml"
SOVEREIGNTY_YAML = PIPELINE / "sovereignty.yaml"
MANIFEST_JSON = PIPELINE / "manifest.json"
ECON_MANIFEST_JSON = PIPELINE / "econ_manifest.json"
WPP_SOURCE, TOGO_SOURCE = "wpp2024", "wpp2024-togo-update"
Con = duckdb.DuckDBPyConnection


# ----------------------------------------------------------------------------- connection

def connect(path: str | Path | None = None, *, read_only: bool = False, rebuild: bool = False) -> Con:
    """Open the store. A fresh file (or ``':memory:'``) gets ``schema.sql`` applied; an existing file
    must carry the current ``schema_version`` (else raise: rebuild it). ``rebuild`` deletes the file first."""
    target = ":memory:" if path == ":memory:" else Path(path or DB_PATH)
    fresh = target == ":memory:"
    if not fresh:
        if rebuild:
            for p in (target, target.with_name(target.name + ".wal")):
                p.unlink(missing_ok=True)
        fresh = not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        if fresh and read_only:
            raise FileNotFoundError(f"{target} does not exist; run `make build`")
    con = duckdb.connect(str(target), read_only=read_only)
    if fresh:
        con.execute(SCHEMA_SQL.read_text())
        write_build_meta(con, schema_version=SCHEMA_VERSION, revision=REVISION)
    else:
        found = con.execute("SELECT value FROM build_meta WHERE key = 'schema_version'").fetchone()
        if not found or found[0] != SCHEMA_VERSION:
            con.close()
            raise RuntimeError(f"{target}: schema_version {found and found[0]!r} != {SCHEMA_VERSION!r}; rebuild with `make build`")
    return con


def _insert(con: Con, table: str, df: pd.DataFrame | pa.Table, columns: list[str] | None = None) -> int:
    """INSERT the frame's columns (by name) into ``table``; returns the row count."""
    cols = columns or (list(df.column_names) if isinstance(df, pa.Table) else list(df.columns))
    n = df.num_rows if isinstance(df, pa.Table) else len(df)
    if n == 0:
        return 0
    con.register("_ins", df)
    try:
        con.execute(f"INSERT INTO {table} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM _ins")
    finally:
        con.unregister("_ins")
    return n


def _fixed(arr: np.ndarray, typ: pa.DataType) -> pa.FixedSizeListArray:
    arr = np.ascontiguousarray(arr)
    return pa.FixedSizeListArray.from_arrays(pa.array(arr.ravel(), typ), arr.shape[1])


def arrays_from_arrow(table: pa.Table, column: str, dim: int) -> np.ndarray:
    """ARRAY column -> numpy [n, dim] (the verified exact round trip)."""
    return table.column(column).combine_chunks().flatten().to_numpy().reshape(-1, dim)


# ----------------------------------------------------------------------------- ingest

def _manifest_files() -> dict[str, dict]:
    files: dict[str, dict] = {}
    if MANIFEST_JSON.exists():
        files.update(json.loads(MANIFEST_JSON.read_text())["files"])
    if ECON_MANIFEST_JSON.exists():
        for key, e in json.loads(ECON_MANIFEST_JSON.read_text()).items():
            files[Path(e.get("file", key)).name] = e
    return files


def ingest_sources(con: Con, sources_yaml: Path = SOURCES_YAML) -> int:
    """Rows of ``pipeline/sources.yaml`` (sha256/bytes/fetched_at from the manifests), plus any
    econ-manifest source id not listed there (so F's loaders' ids satisfy the FK)."""
    spec = yaml.safe_load(sources_yaml.read_text())
    files = _manifest_files()
    econ = json.loads(ECON_MANIFEST_JSON.read_text()) if ECON_MANIFEST_JSON.exists() else {}
    by_file = {f: sid for sid, s in spec["sources"].items() for f in s.get("files", [])}
    rows = []
    for sid, s in spec["sources"].items():
        # files listed in sources.yaml, plus econ-manifest entries that name this source id (e.g. the WDI pages)
        entries = [files[f] for f in s.get("files", []) if f in files]
        entries += [e for e in econ.values() if e.get("source") == sid and Path(e.get("file", "")).name not in by_file]
        hashes = [e["sha256"] for e in entries if e.get("sha256")]
        sha = None if not hashes else (hashes[0] if len(hashes) == 1 else hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest())
        rows.append({"id": sid, "family": s["family"], "name": s.get("name"), "url": s.get("url"),
                     "vintage": s.get("vintage"), "licence": s.get("licence"), "redistributable": bool(s["redistributable"]),
                     "attribution": s.get("attribution"), "sha256": sha,
                     "bytes": sum(int(e.get("bytes") or 0) for e in entries) or None,
                     "fetched_at": max((e.get("fetched_at") for e in entries if e.get("fetched_at")), default=None)})
    known = {r["id"] for r in rows}
    if econ:
        for key, e in econ.items():
            sid = e.get("source", key)
            if sid in known or by_file.get(Path(e.get("file", "")).name) in known:
                continue  # same file already carried by a sources.yaml row (maddison2023 ≙ maddison-2023 …)
            known.add(sid)
            fam = next((f for f in spec["families"] if sid.startswith(f)), "curated")
            rows.append({"id": sid, "family": fam, "name": e.get("notes"), "url": e.get("url"), "vintage": None,
                         "licence": e.get("licence", spec["families"][fam]["licence"]),
                         "redistributable": bool(e.get("redistributable", spec["families"][fam]["redistributable"])),
                         "attribution": None, "sha256": e.get("sha256"), "bytes": e.get("bytes"), "fetched_at": e.get("fetched_at")})
    df = pd.DataFrame(rows)
    df["fetched_at"] = pd.to_datetime(df["fetched_at"]).dt.date
    return _insert(con, "source", df)


def _ensure_source(con: Con, source_id: str, family: str) -> None:
    if con.execute("SELECT 1 FROM source WHERE id = ?", [source_id]).fetchone():
        return
    fam = yaml.safe_load(SOURCES_YAML.read_text())["families"].get(family)
    if fam is None:
        raise ValueError(f"source {source_id!r}: unknown family {family!r}; add it to pipeline/sources.yaml")
    con.execute("INSERT INTO source (id, family, licence, redistributable) VALUES (?, ?, ?, ?)",
                [source_id, family, fam["licence"], bool(fam["redistributable"])])


def ingest_locations(con: Con, locations: pd.DataFrame) -> int:
    """All UN rows of locations.parquet into ``location`` (numeric flags cast to INTEGER)."""
    cols = [r[0] for r in con.execute("DESCRIBE location").fetchall()]
    ints = {r[0] for r in con.execute("DESCRIBE location").fetchall() if r[1] == "INTEGER"}
    sel = ", ".join(f'TRY_CAST("{c}" AS INTEGER) AS "{c}"' if c in ints else f'"{c}"' for c in cols if c in locations)
    con.register("_loc", locations)
    try:
        con.execute(f"INSERT INTO location ({', '.join(chr(34) + c + chr(34) for c in cols if c in locations)}) SELECT {sel} FROM _loc")
    finally:
        con.unregister("_loc")
    return con.execute("SELECT count(*) FROM location").fetchone()[0]


def insert_entities(con: Con, entities: list[dict]) -> int:
    """``entity`` (+ full dict as ``doc``), ``entity_alias`` and ``entity_membership``."""
    cols = ["id", "locid", "type", "iso2", "name", "short_name", "slug", "agg_kind", "parent_locid", "subregion_locid",
            "region_locid", "sdg_region_locid", "income_group", "dev_group", "pop_2026", "is_micro", "axis_pct"]
    rows = [{**{c: e.get(c) for c in cols}, "un_notes": list(e.get("notes", [])), "doc": json.dumps(e, ensure_ascii=False)}
            for e in entities]
    n = _insert(con, "entity", pd.DataFrame(rows))
    alias = [{"alias": a, "entity_id": e["id"], "kind": "slug" if a == e["slug"] else "alias"}
             for e in entities for a in dict.fromkeys([e["slug"], *e["aliases"]])]
    _insert(con, "entity_alias", pd.DataFrame(alias))
    members = [{"agg_id": e["id"], "member_id": m} for e in entities for m in e.get("members", [])]
    if members:
        _insert(con, "entity_membership", pd.DataFrame(members))
    return n


def ingest_sovereignty(con: Con, path: Path = SOVEREIGNTY_YAML) -> int:
    """Curated ``pipeline/sovereignty.yaml`` rows (may be empty); unknown entity ids raise."""
    rows = (yaml.safe_load(path.read_text()) or {}).get("rows") or []
    if not rows:
        return 0
    ids = {r[0] for r in con.execute("SELECT id FROM entity").fetchall()}
    unknown = sorted({r["entity_id"] for r in rows} - ids)
    if unknown:
        raise ValueError(f"sovereignty.yaml: unknown entity ids {unknown}")
    return _insert(con, "sovereignty", pd.DataFrame(rows), ["entity_id", "state_since", "predecessor", "event", "note", "ref"])


def _entity_frame(con: Con, raw: pd.DataFrame) -> pd.DataFrame:
    ent = con.execute("SELECT id AS entity_id, locid FROM entity").df()
    df = raw.merge(ent, on="locid", how="inner")
    return df[["entity_id", "year", "age_start", "pop_male", "pop_female"]]


def ingest_pop_age5(con: Con, vanilla: pd.DataFrame, patched: pd.DataFrame, patch: dict | None) -> dict:
    """Raw (all-location) frames -> ``pop_age5`` (patched, canonical) and ``pop_age5_vanilla``.
    Rows of the patched locids and the recomputed aggregates carry ``patch_id`` and the patch source."""
    v = _entity_frame(con, vanilla)
    v["source_id"] = WPP_SOURCE
    _insert(con, "pop_age5_vanilla", v)
    p = _entity_frame(con, patched)
    touched: set[str] = set()
    if patch:
        _ensure_source(con, patch.get("source_id", TOGO_SOURCE), "wpp")
        con.execute("INSERT INTO patch VALUES (?, ?, ?, ?, ?, ?)",
                    [patch["id"], patch.get("source_id", TOGO_SOURCE), bool(patch.get("applied", True)),
                     list(patch["locids"]), list(patch["recomputed_aggregates"]), patch.get("note")])
        locids = set(patch["locids"]) | set(patch["recomputed_aggregates"])
        touched = {r[0] for r in con.execute("SELECT id FROM entity WHERE locid IN (SELECT unnest(?::INTEGER[]))", [sorted(locids)]).fetchall()}
    is_t = p["entity_id"].isin(touched)
    p["source_id"] = np.where(is_t, patch["source_id"] if patch else WPP_SOURCE, WPP_SOURCE)
    p["patch_id"] = np.where(is_t, patch["id"] if patch else None, None)
    n = _insert(con, "pop_age5", p)
    return {"rows": n, "patched_entities": sorted(touched)}


def ingest_wpp_indicators(con: Con, indicators: pd.DataFrame | None = None, update: pd.DataFrame | None = None,
                          patch: dict | None = None) -> int:
    """WPP demographic indicators (wpp.load_indicators layout) into ``indicator``/``indicator_value``.
    With ``update`` (Togo interim file) the patched locids' rows are replaced and attributed to the
    patch source. Aggregates keep their vanilla indicator values (the UN did not revise them).
    Called with no frames it reads the raw files itself and takes the applied patch from ``patch``
    (the table filled by :func:`ingest_pop_age5`), so ``build_data.py`` can call it bare."""
    if indicators is None:
        from pyramid_explorer.data import wpp

        indicators = wpp.load_indicators()
        applied = load_patches(con)
        if update is None and applied and patch is None:
            patch, update = applied[0], wpp.load_indicators_update()
    rows = [{"id": k, "family": "wpp", "code": col, "name": name, "unit": unit, "derived": False}
            for k, (col, name, unit) in WPP_INDICATORS.items()]
    con.register("_ind", pd.DataFrame(rows))
    con.execute("INSERT OR IGNORE INTO indicator (id, family, code, name, unit, derived) SELECT * FROM _ind")
    con.unregister("_ind")
    ent = con.execute("SELECT id AS entity_id, locid FROM entity").df()

    def long(df: pd.DataFrame, source_id: str) -> pd.DataFrame:
        m = df.merge(ent, on="locid").melt(id_vars=["entity_id", "year", "is_forecast"],
                                            value_vars=[c for _, (c, _, _) in WPP_INDICATORS.items()],
                                            var_name="col", value_name="value").dropna(subset=["value"])
        m["indicator_id"] = m["col"].map({c: k for k, (c, _, _) in WPP_INDICATORS.items()})
        m["source_id"] = source_id
        return m[["entity_id", "year", "indicator_id", "source_id", "value", "is_forecast"]]

    base = indicators
    parts = []
    if update is not None and patch:
        _ensure_source(con, patch.get("source_id", TOGO_SOURCE), "wpp")
        locids = set(patch["locids"])
        base = indicators[~indicators["locid"].isin(locids)]
        parts.append(long(update[update["locid"].isin(locids)], patch.get("source_id", TOGO_SOURCE)))
    parts.append(long(base, WPP_SOURCE))
    return _insert(con, "indicator_value", pd.concat(parts, ignore_index=True))


def ingest_indicators(con: Con, family: str, source_id: str, long_df: pd.DataFrame) -> dict:
    """Econ loader output ``[code, year, indicator_id, value, is_forecast]`` -> ``indicator_value``,
    mapping codes through ``pipeline/econ_iso3.yaml`` (``source_entity_map`` rows recorded) and
    writing every unmapped code to ``source_orphan``. Returns ``{"rows", "orphans"}``."""
    from pyramid_explorer.data.econ_iso3 import apply_remap, load_rules

    _ensure_source(con, source_id, family)
    ids = {r[0] for r in con.execute("SELECT id FROM entity").fetchall()}
    mapped, orphans = apply_remap(long_df, family, ids=ids)
    inds = pd.DataFrame({"id": sorted(mapped["indicator_id"].unique())})
    inds["family"], inds["code"] = family, inds["id"]
    con.register("_ind", inds)
    con.execute("INSERT OR IGNORE INTO indicator (id, family, code) SELECT id, family, code FROM _ind")
    con.unregister("_ind")
    vals = mapped.dropna(subset=["value"]).copy()
    vals["source_id"] = source_id
    vals["year"] = vals["year"].astype(int)
    vals["is_forecast"] = vals["is_forecast"].astype(bool)
    n = _insert(con, "indicator_value", vals, ["entity_id", "year", "indicator_id", "source_id", "value", "is_forecast"])
    remap = load_rules()[family]["remap"]
    used = [{"family": family, "code": c, "entity_id": e, "note": f"{source_id}: {c} -> {e}"}
            for c, e in remap.items() if c in set(long_df["code"])]
    if used:
        con.register("_map", pd.DataFrame(used))
        con.execute("INSERT OR IGNORE INTO source_entity_map SELECT family, code, entity_id, note FROM _map")
        con.unregister("_map")
    if len(orphans):
        o = orphans.copy()
        o["source_id"], o["name"] = source_id, None
        _insert(con, "source_orphan", o, ["source_id", "code", "name", "reason", "n_rows", "first_year", "last_year"])
    return {"rows": n, "orphans": sorted(orphans["code"].tolist())}


# ----------------------------------------------------------------------------- derived + checks

def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _sanity_checks(con: Con) -> dict:
    """SQL cross-checks on the ingested tables (fail the build)."""
    n_ent = con.execute("SELECT count(*) FROM entity").fetchone()[0]
    rep: dict = {"n_entities": n_ent}
    for t in ("pop_age5", "pop_age5_vanilla"):
        bad = con.execute(f"SELECT count(*) FROM (SELECT entity_id, year FROM {t} GROUP BY 1, 2 HAVING count(*) <> {N_BINS} "
                          f"OR min(age_start) <> 0 OR max(age_start) <> 100)").fetchone()[0]
        _check(bad == 0, f"{t}: {bad} (entity, year) groups without exactly {N_BINS} bins 0..100")
        neg = con.execute(f"SELECT count(*) FROM {t} WHERE pop_male < 0 OR pop_female < 0 OR pop_male IS NULL OR pop_female IS NULL").fetchone()[0]
        _check(neg == 0, f"{t}: {neg} negative/NULL populations")
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        _check(n == n_ent * N_YEARS * N_BINS, f"{t}: {n} rows != {n_ent} x {N_YEARS} x {N_BINS}")
    # member sums on vanilla within the 3-decimal rounding bound (0.001k per member per bin)
    ms = con.execute("""
        WITH m AS (SELECT em.agg_id, v.year, v.age_start, sum(v.pop_male) AS pm, sum(v.pop_female) AS pf, count(*) AS n
                   FROM entity_membership em JOIN pop_age5_vanilla v ON v.entity_id = em.member_id GROUP BY 1, 2, 3)
        SELECT m.agg_id, max(greatest(abs(m.pm - a.pop_male), abs(m.pf - a.pop_female)) / (0.001 * m.n)) AS worst_bin,
               max(abs(m.pm + m.pf - a.pop_male - a.pop_female) / greatest(1e-4 * (a.pop_male + a.pop_female), 0.002 * m.n)) AS worst_tot
        FROM m JOIN pop_age5_vanilla a ON a.entity_id = m.agg_id AND a.year = m.year AND a.age_start = m.age_start
        GROUP BY 1 ORDER BY worst_bin DESC""").df()
    if len(ms):
        _check((ms["worst_bin"] <= 1).all() and (ms["worst_tot"] <= 1).all(),
               f"member-sum check failed on vanilla: {ms.head(3).to_dict('records')}")
        rep["member_sum_worst_bin_ratio"] = float(ms["worst_bin"].max())
    # patch identity: (patched − vanilla)_agg == Σ_patched-members (patched − vanilla); others byte-identical
    patches = con.execute("SELECT id, locids, recomputed_aggregates FROM patch WHERE applied").fetchall()
    all_touched: list[str] = []
    all_recomputed: list[str] = []
    for pid, locids, recomputed in patches:
        touched = con.execute("SELECT id FROM entity WHERE locid IN (SELECT unnest(?::INTEGER[]))", [list(locids)]).df()["id"].tolist()
        aggs = con.execute("SELECT id FROM entity WHERE locid IN (SELECT unnest(?::INTEGER[]))", [list(recomputed)]).df()["id"].tolist()
        bad = con.execute("""
            WITH d AS (SELECT p.entity_id, p.year, p.age_start, p.pop_male - v.pop_male AS dm, p.pop_female - v.pop_female AS df
                       FROM pop_age5 p JOIN pop_age5_vanilla v USING (entity_id, year, age_start)),
            dt AS (SELECT year, age_start, sum(dm) AS dm, sum(df) AS df FROM d WHERE entity_id IN (SELECT unnest(?::TEXT[])) GROUP BY 1, 2),
            n AS (SELECT agg_id, count(*) AS n FROM entity_membership GROUP BY 1)
            SELECT d.entity_id, max(greatest(abs(d.dm - dt.dm), abs(d.df - dt.df)) / (0.001 * n.n)) AS worst
            FROM d JOIN dt USING (year, age_start) JOIN n ON n.agg_id = d.entity_id
            WHERE d.entity_id IN (SELECT unnest(?::TEXT[])) GROUP BY 1 HAVING worst > 1""", [touched, aggs]).fetchall()
        _check(not bad, f"patch {pid}: identity failed for {bad}")
        untouched = con.execute("""
            SELECT count(*) FROM pop_age5 p JOIN pop_age5_vanilla v USING (entity_id, year, age_start)
            WHERE (p.pop_male <> v.pop_male OR p.pop_female <> v.pop_female)
              AND entity_id NOT IN (SELECT unnest(?::TEXT[]))""", [touched + aggs]).fetchone()[0]
        _check(untouched == 0, f"patch {pid}: {untouched} rows changed outside the patched entities")
        rep[f"patch_{pid}"] = {"entities": touched, "recomputed": aggs}
        all_touched += touched
        all_recomputed += aggs
    # bin sums vs TPopulation1July (0.02k) for every (entity, year) carrying the indicator, whatever its source.
    # Recomputed aggregates keep the UN's vanilla indicators (ingest_wpp_indicators), so their patched bins differ
    # from TPopulation1July by exactly the patch delta — checked as an identity, never exempted silently.
    base = """
        WITH s AS (SELECT entity_id, year, sum(pop_male + pop_female) AS tot FROM pop_age5 GROUP BY 1, 2),
        iv AS (SELECT entity_id, year, max(value) AS value FROM indicator_value WHERE indicator_id = 'pop_total_wpp' GROUP BY 1, 2),
        d AS (SELECT s.entity_id, s.year, s.tot - iv.value AS diff FROM s JOIN iv USING (entity_id, year))"""
    bs = con.execute(base + """
        SELECT count(*) FILTER (WHERE abs(diff) > 0.02 AND entity_id NOT IN (SELECT unnest(?::TEXT[]))) AS bad,
               count(*) FILTER (WHERE entity_id NOT IN (SELECT unnest(?::TEXT[]))) AS n,
               max(abs(diff)) FILTER (WHERE entity_id NOT IN (SELECT unnest(?::TEXT[]))) AS worst FROM d""",
                     [all_recomputed] * 3).fetchone()
    if bs[1]:
        _check(bs[0] == 0, f"bin sums differ from TPopulation1July by > 0.02k in {bs[0]} entity-years (worst {bs[2]:.4f})")
        rep["bin_sum_vs_tpop_worst"] = float(bs[2])
    if all_recomputed:
        ident = con.execute(base + """,
            dt AS (SELECT p.year, sum(p.pop_male + p.pop_female - v.pop_male - v.pop_female) AS delta
                   FROM pop_age5 p JOIN pop_age5_vanilla v USING (entity_id, year, age_start)
                   WHERE p.entity_id IN (SELECT unnest(?::TEXT[])) GROUP BY 1),
            n AS (SELECT agg_id, count(*) AS n FROM entity_membership GROUP BY 1)
            SELECT d.entity_id, max(abs(d.diff - dt.delta)) AS worst, max(0.02 + 0.001 * ? * n.n) AS tol
            FROM d JOIN dt USING (year) JOIN n ON n.agg_id = d.entity_id
            WHERE d.entity_id IN (SELECT unnest(?::TEXT[])) GROUP BY 1""", [all_touched, N_BINS, all_recomputed]).df()
        bad = ident[ident["worst"] > ident["tol"]]
        _check(bad.empty, f"recomputed aggregates: bins − TPopulation1July ≠ patch delta for {bad.to_dict('records')}")
        rep["bin_sum_recomputed_identity_worst"] = float(ident["worst"].max()) if len(ident) else 0.0
    return rep


def refresh_derived(con: Con, *, checks: bool = True) -> dict:
    """Rebuild ``pyramid`` (shares + per-sex CDFs joined to ``corpus_row``) and ``coverage``; run the
    SQL sanity checks (member sums on vanilla, patch identity, bin sums, shares sum to one)."""
    rep = _sanity_checks(con) if checks else {}
    con.execute("DELETE FROM pyramid; DELETE FROM coverage;")
    con.execute("""
        INSERT INTO pyramid
        WITH t AS (SELECT entity_id, year, sum(pop_male + pop_female) AS total FROM pop_age5 GROUP BY 1, 2),
        b AS (SELECT p.entity_id, p.year, p.age_start, p.pop_male / t.total AS sm, p.pop_female / t.total AS sf,
                     sum(p.pop_male) OVER w / t.total AS cm, sum(p.pop_female) OVER w / t.total AS cf
              FROM pop_age5 p JOIN t USING (entity_id, year)
              WINDOW w AS (PARTITION BY p.entity_id, p.year ORDER BY p.age_start ROWS UNBOUNDED PRECEDING)),
        w AS (SELECT entity_id, year, list(sm ORDER BY age_start) || list(sf ORDER BY age_start) AS s42,
                     list(cm ORDER BY age_start) || list(cf ORDER BY age_start) AS cdf42
              FROM b GROUP BY 1, 2)
        SELECT cr.row, w.entity_id, w.year, t.total, w.s42::DOUBLE[42], w.cdf42::DOUBLE[42]
        FROM w JOIN t USING (entity_id, year) JOIN corpus_row cr USING (entity_id, year)""")
    n_ent = con.execute("SELECT count(*) FROM entity").fetchone()[0]
    n = con.execute("SELECT count(*), max(row) + 1, min(row) FROM pyramid").fetchone()
    _check(n == (n_ent * N_YEARS, n_ent * N_YEARS, 0), f"pyramid rows {n} != {n_ent} x {N_YEARS} dense 0..n-1")
    worst = con.execute("SELECT max(abs(list_sum(s42::DOUBLE[]) - 1)) FROM pyramid").fetchone()[0]
    _check(worst < 1e-12, f"shares do not sum to one (max |Σ−1| = {worst})")
    con.execute(f"""
        INSERT INTO coverage
        SELECT entity_id, 'pyramid' AS series, source_id, min(year), max(year), count(DISTINCT year),
               max(year) - min(year) + 1 - count(DISTINCT year), least(max(year), {LAST_OBSERVED_YEAR})
        FROM pop_age5 GROUP BY 1, 2, 3
        UNION ALL
        SELECT entity_id, indicator_id, source_id, min(year), max(year), count(*), max(year) - min(year) + 1 - count(*),
               max(year) FILTER (WHERE NOT is_forecast)
        FROM indicator_value GROUP BY 1, 2, 3""")
    rep.update({"n_rows": n[0], "n_coverage": con.execute("SELECT count(*) FROM coverage").fetchone()[0]})
    return rep


# ----------------------------------------------------------------------------- arrays, sigma, embeddings, evals

def write_u16(con: Con, u16: np.ndarray) -> int:
    """``corpus_u16`` from a uint16 [n_rows, 42] array in corpus row order (rows must sum to 65535)."""
    u16 = np.asarray(u16, dtype=np.uint16)
    _check(u16.shape[1] == N_DIMS and (u16.sum(1, dtype=np.int64) == 65535).all(), "u16 rows must be [n,42] summing to 65535")
    con.execute("DELETE FROM corpus_u16")
    tbl = pa.table({"row": pa.array(np.arange(len(u16), dtype=np.int32)), "u16": _fixed(u16, pa.uint16())})
    return _insert(con, "corpus_u16", tbl)


def write_sigma(con: Con, sigma: dict) -> int:
    """``{metric: {"2": σ, "1": σ}}`` -> ``sigma``."""
    con.execute("DELETE FROM sigma")
    rows = [{"metric": m, "sex": str(s), "value": float(v)} for m, d in sigma.items() for s, v in d.items()]
    return _insert(con, "sigma", pd.DataFrame(rows))


def ingest_embeddings(con: Con, model: str, full_npy: Path | None, pca_npy: Path, meta_json: Path,
                      keys: pd.DataFrame) -> dict:
    """Load ``evals/embeddings/{model}[.pca64].npy`` (+ meta) into ``embedding_model`` / ``embedding`` /
    ``embedding_pca64``. Refuses when ``meta.data_hash`` differs from ``build_meta.data_hash``."""
    meta = json.loads(Path(meta_json).read_text())
    ours = con.execute("SELECT value FROM build_meta WHERE key = 'data_hash'").fetchone()
    if not ours or meta.get("data_hash") != ours[0]:
        raise ValueError(f"{model}: embedding data_hash {meta.get('data_hash')!r} != build data_hash {ours and ours[0]!r}")
    pca = np.load(pca_npy).astype(np.float32)
    _check(pca.shape == (len(keys), 64), f"{model}: pca64 shape {pca.shape} != ({len(keys)}, 64)")
    for t in ("embedding", "embedding_pca64", "embedding_model"):
        con.execute(f"DELETE FROM {t} WHERE model = ?", [model])
    pca_mean = meta.get("pca_mean")
    con.execute("INSERT INTO embedding_model VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [model, meta.get("hf_id"), meta.get("checkpoint_sha"), int(meta.get("dim", 768)), meta.get("render_kind"),
                 meta.get("render_size"), meta.get("style_hash"), json.dumps(meta.get("processor_config")),
                 json.dumps(meta.get("asserted_shapes")), None if pca_mean is None else [float(x) for x in pca_mean],
                 meta.get("pca_proj_sha"), meta["data_hash"], datetime.now(timezone.utc)])
    ids, years = pa.array(keys["id"].astype(str)), pa.array(keys["year"].astype(np.int16), pa.int16())
    _insert(con, "embedding_pca64", pa.table({"model": pa.array([model] * len(keys)), "entity_id": ids, "year": years,
                                              "vec": _fixed(pca, pa.float32())}))
    n_full = 0
    if full_npy is not None and Path(full_npy).exists():
        full = np.load(full_npy).astype(np.float32)
        _check(full.shape == (len(keys), 768), f"{model}: full embedding shape {full.shape} != ({len(keys)}, 768)")
        n_full = _insert(con, "embedding", pa.table({"model": pa.array([model] * len(keys)), "entity_id": ids, "year": years,
                                                    "vec": _fixed(full, pa.float32())}))
    return {"model": model, "pca64": len(pca), "full": n_full}


def ingest_evals(con: Con, *, label_sets: dict[str, pd.DataFrame] | None = None, triplets: pd.DataFrame | None = None,
                 verdicts: dict | None = None, set_meta: dict[str, dict] | None = None) -> dict:
    """Mirror evals/ files: ``label_sets`` {set_id: df[entity_id, year, label]}, ``triplets``
    df[anchor_id, anchor_year, a_id, a_year, b_id, b_year, choice, rater, stratum], ``verdicts``
    {metric: {gate: {value, verdict}}} (+ optional data_hash/emb_meta_hash keys)."""
    out = {"labels": 0, "triplets": 0, "verdicts": 0}
    for sid, df in (label_sets or {}).items():
        m = (set_meta or {}).get(sid, {})
        con.execute("INSERT OR REPLACE INTO eval_label_set VALUES (?, ?, ?, ?, ?)",
                    [sid, m.get("name", sid), m.get("source"), m.get("vintage"), m.get("note")])
        con.execute("DELETE FROM eval_label WHERE set_id = ?", [sid])
        d = df.copy()
        d["set_id"] = sid
        out["labels"] += _insert(con, "eval_label", d, ["set_id", "entity_id", "year", "label"])
    if triplets is not None:
        con.execute("DELETE FROM eval_triplet")
        t = triplets.reset_index(drop=True).copy()
        t["id"] = np.arange(len(t))
        for c in ("choice", "rater", "stratum"):
            t[c] = t[c] if c in t else None
        out["triplets"] = _insert(con, "eval_triplet", t, ["id", "anchor_id", "anchor_year", "a_id", "a_year", "b_id", "b_year",
                                                         "choice", "rater", "stratum"])
    if verdicts:
        con.execute("DELETE FROM eval_verdict")
        dh, eh = verdicts.get("data_hash"), verdicts.get("emb_meta_hash")
        rows = [{"metric": m, "gate": g, "value": (v.get("value") if isinstance(v, dict) else v),
                 "verdict": (v.get("verdict") if isinstance(v, dict) else None), "data_hash": dh, "emb_meta_hash": eh}
                for m, gates in verdicts.items() if isinstance(gates, dict) for g, v in gates.items()]
        out["verdicts"] = _insert(con, "eval_verdict", pd.DataFrame(rows))
    return out


# ----------------------------------------------------------------------------- loaders

def load_entities(con: Con) -> list[dict]:
    """Entity dicts in corpus order."""
    docs = con.execute("SELECT e.doc FROM entity e JOIN corpus_entity ce ON ce.entity_id = e.id ORDER BY ce.entity_idx").fetchall()
    return [json.loads(d[0]) for d in docs]


def load_patches(con: Con) -> list[dict]:
    df = con.execute("SELECT id, source_id, applied, locids, recomputed_aggregates, note FROM patch ORDER BY id").df()
    return [{**r, "applied": bool(r["applied"]), "locids": [int(x) for x in r["locids"]],
             "recomputed_aggregates": [int(x) for x in r["recomputed_aggregates"]]} for r in df.to_dict("records")]


def _keys_sql() -> str:
    return ("SELECT p.row, p.entity_id AS id, cr.locid, p.year, cr.type, p.total AS pop_total, p.s42, p.cdf42 "
            "FROM pyramid p JOIN corpus_row cr USING (row) ORDER BY p.row")


def load_corpus(con: Con) -> tuple[np.ndarray, pd.DataFrame]:
    """(s42 float64 [n, 42], keys df ``row, id, locid, year, type, pop_total``) in corpus row order."""
    t = con.execute(_keys_sql()).to_arrow_table()
    keys = t.select(["row", "id", "locid", "year", "type", "pop_total"]).to_pandas()
    keys = keys.astype({"row": "int64", "locid": "int64", "year": "int64"})
    _check((keys["row"].to_numpy() == np.arange(len(keys))).all(), "pyramid rows are not dense in corpus order")
    return arrays_from_arrow(t, "s42", N_DIMS), keys


def load_pyramids(con: Con, patched: bool = True) -> pd.DataFrame:
    """Long ``id, locid, year, age_start, pop_male, pop_female`` (thousands) in corpus order from
    ``pop_age5`` (patched, canonical) or ``pop_age5_vanilla``."""
    table = "pop_age5" if patched else "pop_age5_vanilla"
    return con.execute(f"SELECT p.entity_id AS id, e.locid, p.year::BIGINT AS year, p.age_start::BIGINT AS age_start, "
                       f"p.pop_male, p.pop_female FROM {table} p JOIN entity e ON e.id = p.entity_id "
                       "JOIN corpus_entity ce ON ce.entity_id = e.id ORDER BY ce.entity_idx, p.year, p.age_start").df()


def load_cdf(con: Con) -> np.ndarray:
    """cdf42 float64 [n, 42] (per-sex cumulative shares) in corpus row order."""
    return arrays_from_arrow(con.execute("SELECT cdf42 FROM pyramid ORDER BY row").to_arrow_table(), "cdf42", N_DIMS)


def load_u16(con: Con) -> np.ndarray:
    t = con.execute("SELECT u16 FROM corpus_u16 ORDER BY row").to_arrow_table()
    return arrays_from_arrow(t, "u16", N_DIMS).astype(np.uint16)


def load_sigma(con: Con) -> dict:
    out: dict = {}
    for m, s, v in con.execute("SELECT metric, sex, value FROM sigma ORDER BY 1, 2").fetchall():
        out.setdefault(m, {})[s] = v
    return out


def load_embeddings(con: Con, model: str, dim: int = 64) -> np.ndarray:
    """float32 [n_rows, dim] in corpus row order (``dim`` 64 -> pca table, 768 -> full table)."""
    table = "embedding_pca64" if dim == 64 else "embedding"
    t = con.execute(f"SELECT e.vec FROM {table} e JOIN corpus_row cr ON cr.entity_id = e.entity_id AND cr.year = e.year "
                    f"WHERE e.model = ? ORDER BY cr.row", [model]).to_arrow_table()
    return arrays_from_arrow(t, "vec", dim).astype(np.float32)


def load_indicator(con: Con, indicator_id: str, *, source_id: str | None = None, public_only: bool = False) -> pd.DataFrame:
    """Long frame ``entity_id, year, value, source_id, is_forecast`` for one indicator."""
    rel = "indicator_public" if public_only else "indicator_value"
    sql = f"SELECT entity_id, year, value, source_id, is_forecast FROM {rel} WHERE indicator_id = ?"
    params: list = [indicator_id]
    if source_id:
        sql, params = sql + " AND source_id = ?", params + [source_id]
    return con.execute(sql + " ORDER BY entity_id, year, source_id", params).df()


def coverage(con: Con, series: str | None = None) -> pd.DataFrame:
    sql, params = "SELECT * FROM coverage", []
    if series:
        sql, params = sql + " WHERE series = ?", [series]
    return con.execute(sql + " ORDER BY entity_id, series, source_id", params).df()


def entity_years(con: Con) -> pd.DataFrame:
    return con.execute("SELECT * FROM entity_years ORDER BY entity_id").df()


def knn(con: Con, entity_id: str, year: int, *, model: str, k: int = 10, where: str = "TRUE") -> pd.DataFrame:
    """Brute-force cosine top-k over ``embedding_pca64`` (self excluded); ``where`` filters candidates
    (columns of ``corpus_row`` joined as ``cr``, e.g. ``"cr.type = 'country' AND cr.year = 2026"``)."""
    return con.execute(f"""
        WITH q AS (SELECT vec FROM embedding_pca64 WHERE model = ? AND entity_id = ? AND year = ?)
        SELECT e.entity_id, e.year, cr.row, array_cosine_distance(e.vec, q.vec) AS d
        FROM embedding_pca64 e, q JOIN corpus_row cr ON cr.entity_id = e.entity_id AND cr.year = e.year
        WHERE e.model = ? AND NOT (e.entity_id = ? AND e.year = ?) AND ({where})
        ORDER BY d LIMIT ?""", [model, entity_id, year, model, entity_id, year, k]).df()


# ----------------------------------------------------------------------------- exports, meta, diff

def export_processed(con: Con, out_dir: Path | None = None) -> dict[str, Path]:
    """Write the CONTRACT §1 files (+ indicators/coverage/entity_years parquet, patches.json) from the DB.
    Like ``indicators.parquet``, ``coverage.parquet`` carries redistributable sources only (WEO stays in the DB)."""
    out = Path(out_dir or DATA_PROCESSED)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    ents = load_entities(con)
    (out / "entities.json").write_text(json.dumps(ents, ensure_ascii=False, indent=0) + "\n")
    paths["entities"] = out / "entities.json"
    load_pyramids(con).to_parquet(out / "pyramids.parquet", index=False)
    paths["pyramids"] = out / "pyramids.parquet"
    s42, keys = load_corpus(con)
    keys.to_parquet(out / "corpus_keys.parquet", index=False)
    np.save(out / "corpus_s42.npy", s42)
    paths.update(corpus_keys=out / "corpus_keys.parquet", corpus_s42=out / "corpus_s42.npy")
    if con.execute("SELECT count(*) FROM corpus_u16").fetchone()[0]:
        np.save(out / "corpus_u16.npy", load_u16(con))
        paths["corpus_u16"] = out / "corpus_u16.npy"
    sigma = load_sigma(con)
    if sigma:
        (out / "sigma.json").write_text(json.dumps(sigma, indent=1) + "\n")
        paths["sigma"] = out / "sigma.json"
    (out / "patches.json").write_text(json.dumps(load_patches(con), indent=1) + "\n")
    paths["patches"] = out / "patches.json"
    con.execute("SELECT entity_id, year::BIGINT AS year, indicator_id, source_id, value, is_forecast FROM indicator_public "
                "ORDER BY indicator_id, entity_id, year, source_id").df().to_parquet(out / "indicators.parquet", index=False)
    con.execute("SELECT c.* FROM coverage c JOIN source s ON s.id = c.source_id WHERE s.redistributable "
                "ORDER BY entity_id, series, source_id").df().to_parquet(out / "coverage.parquet", index=False)
    entity_years(con).to_parquet(out / "entity_years.parquet", index=False)
    paths.update(indicators=out / "indicators.parquet", coverage=out / "coverage.parquet", entity_years=out / "entity_years.parquet")
    return paths


def write_build_meta(con: Con, values: dict | None = None, **kv) -> None:
    """Upsert ``build_meta`` keys (schema_version, revision, built, data_hash, git_rev, …); accepts a
    mapping and/or keywords."""
    for k, v in {**(values or {}), **kv}.items():
        con.execute("INSERT OR REPLACE INTO build_meta VALUES (?, ?)", [k, None if v is None else str(v)])


def build_meta(con: Con) -> dict[str, str]:
    return dict(con.execute("SELECT key, value FROM build_meta ORDER BY key").fetchall())


def git_rev() -> str | None:
    try:
        import subprocess

        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001 — no git, no problem
        return None


def diff_against(con: Con, old_db: Path) -> dict:
    """Entity / coverage / share diff against an older store (ATTACHed read-only) for the WPP refresh."""
    quoted = str(old_db).replace("'", "''")
    con.execute(f"ATTACH '{quoted}' AS old (READ_ONLY)")
    try:
        added = [r[0] for r in con.execute("SELECT id FROM entity EXCEPT SELECT id FROM old.entity ORDER BY 1").fetchall()]
        removed = [r[0] for r in con.execute("SELECT id FROM old.entity EXCEPT SELECT id FROM entity ORDER BY 1").fetchall()]
        shares = con.execute("""
            SELECT n.entity_id, max(list_max(list_transform(list_zip(n.s42::DOUBLE[], o.s42::DOUBLE[]), x -> abs(x[1] - x[2])))) AS max_abs_diff
            FROM pyramid n JOIN old.pyramid o USING (entity_id, year) GROUP BY 1 HAVING max_abs_diff > 0
            ORDER BY max_abs_diff DESC LIMIT 20""").df()
        cov = con.execute("""
            SELECT count(*) FILTER (WHERE o.entity_id IS NULL) AS added, count(*) FILTER (WHERE n.entity_id IS NULL) AS removed,
                   count(*) FILTER (WHERE n.last_year <> o.last_year) AS changed_last_year
            FROM coverage n FULL JOIN old.coverage o USING (entity_id, series, source_id)""").fetchone()
        meta_old = dict(con.execute("SELECT key, value FROM old.build_meta").fetchall())
    finally:
        con.execute("DETACH old")
    return {"entities_added": added, "entities_removed": removed, "shares_changed": shares.to_dict("records"),
            "coverage": {"added": cov[0], "removed": cov[1], "changed_last_year": cov[2]}, "old_meta": meta_old}


__all__ = [n for n in dir() if not n.startswith("_")]
