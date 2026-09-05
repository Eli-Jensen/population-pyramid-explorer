"""``econ.{sha8}.ecz`` + the small web JSONs of the economic lens (plan §7 "Data & format"; consumer: ``web/src/lib/econ.ts``).

File = u32-LE header length · UTF-8 JSON header · typed-array body (little-endian, country-major, one value per
(country, year) for ``year_min..year_max``), gzip-9 with mtime 0, NO ``.gz`` extension (the web sniffs ``1f 8b``).
The header is self-describing (``arrays`` carries dtype / offset / scale / encoding / na per series) and carries the
instrument records, the VT benchmark ladder, mobility, events and attribution. Budget: ≤ 160 KB on the wire.

Licence guard (tests/test_econ_export.py): nothing written under ``web/public/data`` may name a non-redistributable
source or carry an index-provider series — the header therefore holds fund tickers/issuers and DERIVED statistics
only (annual year-end levels ≤ 40 numbers per fund, a CAGR, a drawdown, a date), fund names and provider URLs that
would name the index provider are dropped, and event notes are paraphrased; the full records stay in
``evals/instruments.yaml`` / ``web/src/data/evidence.json``.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pyramid_explorer.econ import etf, instruments as I, splice as S, typology as T
from pyramid_explorer.paths import REVISION, WEB_DATA, WEB_SRC_DATA

SIZE_BUDGET = 160_000
LAST_FULL_YEAR = 2025                 # last complete calendar year at build time (year-end levels stop here)
VT_FIRST_BAR = "2008-06-24"
PROXY_UNTIL_YEAR = 2008               # a window starting at year-end 2008 or later is pure VT
LEVELS_FIRST_YEAR = 1995              # VT ladder base (SPY history begins 1993)
PROVIDER_RE = re.compile(r"msci", re.I)
LICENCE_RE = re.compile(r"weo|imf|ngdp", re.I)

ARRAYS = {   # name → (numpy dtype, header spec)  — body order = this order
    "gdppc": ("<u2", {"dtype": "u16", "encoding": "log", "scale": 4096, "na": 0}),
    "g_rgdp": ("<i2", {"dtype": "i16", "scale": 0.01, "na": -32768}),
    "g_rgdp_1y": ("<i2", {"dtype": "i16", "scale": 0.01, "na": -32768}),
    "tfr": ("<u2", {"dtype": "u16", "scale": 0.001, "na": 0}),
    "income": ("<u1", {"dtype": "u8", "na": 0}),
    "stage": ("<u1", {"dtype": "u8", "na": 0}),
}
ARRAY_NOTES = {
    "gdppc": "GDP per capita, Maddison Project Database 2023 level (2011 int. $) through 2022, extended year by year with World Development Indicators PPP-per-capita growth (else Penn World Table growth); countries absent from Maddison carry the WDI level rescaled by the 2017 cross-country median ratio. value = exp(u / 4096).",
    "g_rgdp": "trailing 10-year real GDP per capita growth ending in the year, %/yr, 100·ln(pc_t / pc_t-10) / 10; pc = Penn World Table 11.0 rgdpna / pop, extended to 2024 by WDI per-capita PPP growth.",
    "g_rgdp_1y": "annual real GDP growth, 100·ln(rgdpna_t / rgdpna_t-1), Penn World Table 11.0 through 2023, WDI NY.GDP.MKTP.KD.ZG (log form) for 2024.",
    "tfr": "total fertility rate, WPP 2024 (medium variant for 2024).",
    "income": "World Bank income group by fiscal year (OGHIST): 1 = low, 2 = lower-middle, 3 = upper-middle, 4 = high; 0 = not classified (before FY1989 or unclassified).",
    "stage": "demographic-dividend stage, World Bank GMR 2015/16 typology adapted to every year (pipeline/typology.yaml): 1 = pre, 2 = early, 3 = late, 4 = post; 0 = n/a.",
}
INCOME_LABELS = {"1": "low income", "2": "lower-middle income", "3": "upper-middle income", "4": "high income"}
STAGE_LABELS = {"1": "pre-dividend", "2": "early-dividend", "3": "late-dividend", "4": "post-dividend"}


def sha8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


# ------------------------------------------------------------------------------------------------ encoding
def encode_arrays(splice: pd.DataFrame, stages: pd.DataFrame, ids: list[str], years: range) -> dict[str, np.ndarray]:
    """Country-major typed arrays (``len(ids) × len(years)``) from the long tables."""
    n_y = len(years)
    idx = {c: i for i, c in enumerate(ids)}
    sp = splice[splice["iso3"].isin(idx)].copy()
    sp["_i"] = sp["iso3"].map(idx) * n_y + (sp["year"] - years.start)
    st = stages[stages["iso3"].isin(idx) & stages["year"].between(years.start, years.stop - 1)].copy()
    st["_i"] = st["iso3"].map(idx) * n_y + (st["year"] - years.start)
    n = len(ids) * n_y

    def put(vals: pd.Series, pos: pd.Series, fill, dtype, fn):
        out = np.full(n, fill, dtype=dtype)
        v = vals.to_numpy(dtype=float)
        ok = np.isfinite(v)
        out[pos.to_numpy()[ok]] = fn(v[ok]).astype(dtype)
        return out

    gd = put(sp["gdppc"], sp["_i"], 0, "<u2", lambda v: np.clip(np.rint(np.log(v) * 4096), 1, 65535))
    g10 = put(sp["g10"], sp["_i"], -32768, "<i2", lambda v: np.clip(np.rint(v * 100), -32767, 32767))
    g1 = put(sp["g_rgdp"], sp["_i"], -32768, "<i2", lambda v: np.clip(np.rint(v * 100), -32767, 32767))
    tf = put(sp["tfr"], sp["_i"], 0, "<u2", lambda v: np.clip(np.rint(v * 1000), 1, 65535))
    inc = np.zeros(n, dtype="<u1")
    inc[sp["_i"].to_numpy()] = sp["income_class"].fillna(0).to_numpy().astype("<u1")
    stg = np.zeros(n, dtype="<u1")
    stg[st["_i"].to_numpy()] = st["stage"].to_numpy().astype("<u1")
    return {"gdppc": gd, "g_rgdp": g10, "g_rgdp_1y": g1, "tfr": tf, "income": inc, "stage": stg}


def decode_arrays(header: dict, body: bytes) -> dict[str, np.ndarray]:
    """Reference decoder (mirrors ``econ.ts#parseEcon``): name → float array (NaN = n/a) or uint8 codes."""
    n = len(header["ids"]) * (header["year_max"] - header["year_min"] + 1)
    out = {}
    for name, spec in header["arrays"].items():
        dt = {"u16": "<u2", "i16": "<i2", "u8": "<u1"}[spec["dtype"]]
        raw = np.frombuffer(body, dtype=dt, count=n, offset=spec["offset"])
        if spec["dtype"] == "u8":
            out[name] = raw.astype(np.uint8)
            continue
        v = raw.astype(np.float64)
        na = spec.get("na", 0)
        v = np.where(raw == na, np.nan, np.exp(v / spec["scale"]) if spec.get("encoding") == "log" else v * spec.get("scale", 1))
        out[name] = v
    return out


# ------------------------------------------------------------------------------------------------ annual levels
def year_end_levels(bars: pd.DataFrame, *, last_full_year: int = LAST_FULL_YEAR) -> dict | None:
    """Adjusted close at the last bar of every calendar year the series covers (≤ ``last_full_year``)."""
    if bars is None or bars.empty:
        return None
    b = bars[bars["date"].dt.year <= last_full_year]
    if b.empty:
        return None
    ye = b.groupby(b["date"].dt.year)["adjclose"].last()
    years = list(range(int(ye.index.min()), int(ye.index.max()) + 1))
    levels = [round(float(ye.get(y, np.nan)), 4) if np.isfinite(ye.get(y, np.nan)) else None for y in years]
    return {"from_year": years[0], "levels": levels, "basis": "adjusted close at the last bar of each calendar year"}


def manual_levels(fund: dict) -> dict | None:
    """Issuer calendar-year NAV total returns compounded from a base of 1.0 at the year-end before the first full year;
    stops at the first missing year or reinvestment artefact (post-halt distributions are not compounded)."""
    years = {int(y["year"]): y for y in fund.get("years", []) if y.get("tr_nav") is not None and not y.get("reinvestment_artifact")}
    if not years:
        return None
    y0 = min(years)
    levels, lvl, y = [1.0], 1.0, y0
    while y in years:
        lvl *= 1.0 + float(years[y]["tr_nav"])
        levels.append(round(lvl, 6))
        y += 1
    return {"from_year": y0 - 1, "levels": levels,
            "basis": "issuer calendar-year NAV total returns compounded from 1.0 at the prior year-end; the final stub to liquidation is not covered"}


def vt_levels(bench: dict[str, pd.DataFrame], *, first_year: int = LEVELS_FIRST_YEAR, last_full_year: int = LAST_FULL_YEAR) -> dict | None:
    """VT-or-proxy ladder: 1.0 at the last SPY bar of ``first_year``, chained year by year with ``etf.vt_benchmark``
    (SPY / EFA / EEM proxy at the PREREG §3.5 weights before VT's first bar, VT itself afterwards)."""
    if "SPY" not in bench:
        return None
    spy = bench["SPY"]
    ye = spy.groupby(spy["date"].dt.year)["date"].last()
    years = [y for y in range(first_year, last_full_year + 1) if y in ye.index]
    levels, lvl = [1.0], 1.0
    for a, b in zip(years[:-1], years[1:]):
        try:
            v = etf.vt_benchmark(ye[a], ye[b], prices=bench)
            lvl *= float(v["gross"])
        except Exception:  # noqa: BLE001 — a gap ends the ladder rather than inventing a level
            break
        levels.append(round(lvl, 6))
    return {"from_year": years[0], "levels": levels}


# ------------------------------------------------------------------------------------------------ header
def _clean_url(u) -> str | None:
    if u is None or (isinstance(u, float) and math.isnan(u)):
        return None
    return None if PROVIDER_RE.search(str(u)) else str(u)


def _paraphrase(text: str) -> str:
    return PROVIDER_RE.sub("the index provider", text or "")


def header_instruments(inst_doc: dict, universe: pd.DataFrame, manual: dict[str, dict], bench: dict[str, pd.DataFrame]) -> tuple[dict, dict, dict]:
    """``instruments`` / ``mobility`` / ``events`` header blocks from the instruments document."""
    entries = {r["ticker"]: r.to_dict() for _, r in universe.iterrows()}
    instruments, mobility, events = {}, {}, {}
    for iso3, c in inst_doc["countries"].items():
        mobility[iso3] = c["mobility"]
        if c.get("events"):
            events[iso3] = [{"date": e["date"], "kind": e["kind"], "note": e.get("note") or _paraphrase(e.get("detail") or ""),
                             "url": _clean_url(e.get("url")), "verified": bool(e.get("verified", False))} for e in c["events"]]
        recs = []
        for t in c.get("tickers", []):
            entry = entries.get(t["ticker"], {})
            annual = manual_levels(manual[t["ticker"]]) if t["ticker"] in manual else year_end_levels(I.cached_prices(t["ticker"], entry) if entry else None)
            recs.append({
                "ticker": t["ticker"], "issuer": t.get("issuer"), "inception": t["inception"], "status": t["status"],
                "delisted": t.get("delisted"), "liquidation_date": t.get("liquidation_date"),
                "status_url": _clean_url(t.get("status_url")), "source_url": _clean_url(t.get("source_url")),
                "msci_class": t.get("msci_class"), "annual": annual,
                "stats": {k: t.get(k) for k in ("since_inception_cagr_pct", "vt_same_window_pct", "benchmark", "window", "cagr_10y_pct",
                                                 "cagr_10y_vt_pct", "cagr_10y_window", "cagr_10y_benchmark", "cagr_10y_status", "max_dd_pct", "as_of")},
            })
        if recs:
            instruments[iso3] = recs
    return instruments, mobility, events


def build_header(*, ids: list[str], years: range, arrays: dict[str, np.ndarray], splice_cov: dict, stages: pd.DataFrame,
                 inst_doc: dict, universe: pd.DataFrame, manual: dict[str, dict], bench: dict[str, pd.DataFrame],
                 typology_doc: dict, built: str | None = None) -> dict:
    offset, specs = 0, {}
    for name, (dt, spec) in ARRAYS.items():
        specs[name] = {**spec, "offset": offset, "note": ARRAY_NOTES[name]}
        offset += arrays[name].nbytes
    instruments, mobility, events = header_instruments(inst_doc, universe, manual, bench)
    thr = typology_doc["thresholds"]
    hints = {
        "1": f"fertility at or above {thr['tfr_high']:g} births per woman and a working-age share still rising over the next {thr['horizon_years']} years",
        "2": f"fertility below {thr['tfr_high']:g} and a working-age share rising over the next {thr['horizon_years']} years",
        "3": f"working-age share not rising over the next {thr['horizon_years']} years; fertility a generation earlier at or above {thr['tfr_replacement']:g}",
        "4": f"working-age share not rising over the next {thr['horizon_years']} years; fertility a generation earlier already below {thr['tfr_replacement']:g}",
    }
    last_year = int(splice_cov.get("last_econ_year", years.stop - 1))
    return {
        "version": 1, "built": built or datetime.now(timezone.utc).isoformat(timespec="seconds"), "as_of": inst_doc.get("as_of"),
        "year_min": years.start, "year_max": years.stop - 1, "ids": ids, "arrays": specs, "body_bytes": offset,
        "last_econ_year": last_year,
        "income_labels": INCOME_LABELS, "stage_labels": STAGE_LABELS, "stage_hints": hints,
        "typology": {"citation": typology_doc["source"]["citation"], "url": typology_doc["source"]["url"], "adapted": True,
                     "thresholds": {k: v for k, v in thr.items()}, "reproduction_2015": splice_cov.get("typology_reproduction")},
        "coverage": {k: splice_cov[k] for k in ("n_countries", "gdppc_ge_min", "min_years", "below_min", "flags", "g10_flags", "rescale") if k in splice_cov},
        "instruments": instruments,
        "benchmark": {"vt": vt_levels(bench), "vt_first_bar": VT_FIRST_BAR, "proxy_until_year": PROXY_UNTIL_YEAR,
                      "proxy_note": "before VT's first bar the ladder is the pre-registered SPY / EFA / EEM proxy (PREREG §3.5), rebalanced at calendar year-ends; a window that starts before the proxy_until_year year-end is flagged vt_proxy"},
        "mobility": mobility, "events": events,
        "sources": {
            "gdppc": "Bolt & van Zanden (2024), Maddison Project Database 2023, CC BY 4.0 — spliced past 2022 with World Bank WDI (CC BY 4.0) / Penn World Table 11.0 (CC BY 4.0) growth",
            "growth": "Feenstra, Inklaar & Timmer, Penn World Table 11.0, CC BY 4.0; World Bank WDI NY.GDP.MKTP.KD.ZG / NY.GDP.PCAP.PP.KD for 2024, CC BY 4.0",
            "income": "World Bank, historical classification by income (OGHIST), CC BY 4.0",
            "tfr": "United Nations, World Population Prospects 2024, CC BY 3.0 IGO",
            "stage": typology_doc["source"]["citation"] + " — adapted to every year (pipeline/typology.yaml)",
            "instruments": "issuer product pages, press releases and SEC filings as listed in evals/econ/etf_universe.yaml and etf_manual.yaml; statistics derived from daily adjusted closes (personal-use price data; only derived figures are shipped)",
        },
        "language": "past-tense statements of published data only; no forecast, no ranking by return, no score combining shape and economics",
    }


# ------------------------------------------------------------------------------------------------ file
def pack(header: dict, arrays: dict[str, np.ndarray]) -> bytes:
    hjson = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body = b"".join(np.ascontiguousarray(arrays[name]).tobytes() for name in ARRAYS)
    raw = len(hjson).to_bytes(4, "little") + hjson + body
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw)
    return buf.getvalue()


def unpack(blob: bytes) -> tuple[dict, dict[str, np.ndarray]]:
    raw = gzip.decompress(blob) if blob[:2] == b"\x1f\x8b" else blob
    n = int.from_bytes(raw[:4], "little")
    header = json.loads(raw[4:4 + n].decode("utf-8"))
    return header, decode_arrays(header, raw[4 + n:])


def guard_text(header_json: str) -> list[str]:
    """Licence-guard violations in a header: any non-redistributable-source token, or the index provider's name anywhere
    but the ``msci_class`` key (the classification label is a fact, not a series)."""
    bad = []
    if LICENCE_RE.search(header_json):
        bad.append("header names a non-redistributable source (weo|imf|ngdp)")
    stripped = header_json.replace('"msci_class"', '"class"')
    if PROVIDER_RE.search(stripped):
        bad.append("header names the index provider outside the msci_class key")
    return bad


# ------------------------------------------------------------------------------------------------ web/src/data
def _json_dump(path: Path, doc) -> int:
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def econ_entities(ids: list[str], splice: pd.DataFrame, stages: pd.DataFrame, inst_doc: dict, *, min_years: int = 30) -> dict:
    n = splice.groupby("iso3")["gdppc"].apply(lambda s: int(s.notna().sum()))
    st24 = stages[stages["year"] == stages["year"].max()].set_index("iso3")["stage"]
    out = {}
    for iso3 in ids:
        c = inst_doc["countries"].get(iso3, {})
        out[iso3] = {"has_econ": bool(n.get(iso3, 0) > 0), "gdppc_years": int(n.get(iso3, 0)), "gdppc_ge_30y": bool(n.get(iso3, 0) >= min_years),
                     "investability_status": c.get("status", "none"), "msci_class": c.get("msci_class"), "mobility": c.get("mobility", "not_assessed"),
                     "stage_latest": T.NAMES[int(st24.get(iso3, 0))]}
    return out


def register_in_meta(meta_path: Path, rel: str, *, size: int | None = None) -> None:
    """Add ``files.econ`` to meta.json without touching anything else (round-trip-checked read-modify-write)."""
    text = meta_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    ascii_ = "\\u" in text
    trailing_nl = text.endswith("\n")

    def dump(d):
        s = json.dumps(d, ensure_ascii=ascii_, separators=(",", ":"))
        return s + ("\n" if trailing_nl else "")

    if dump(doc) != text:
        raise RuntimeError("meta.json serialisation does not round-trip; refusing to rewrite it")
    doc["files"]["econ"] = rel
    meta_path.write_text(dump(doc), encoding="utf-8")


NOTICE_LINE = ("Economic-context series (econ.*.ecz), derived by this site: GDP per capita is the Maddison Project Database 2023 level "
               "(2011 int. $) spliced past 2022 with World Bank World Development Indicators / Penn World Table 11.0 growth; 10-year real "
               "growth from Penn World Table 11.0 (World Development Indicators for 2024); income group from the World Bank historical "
               "classification (OGHIST) by fiscal year; fertility from WPP 2024; dividend stage adapted from the World Bank GMR 2015/16 "
               "typology (Ahmed, Cruz, Quillin & Schellekens 2016, PRWP 7893). Fund figures are derived statistics (year-end levels, "
               "growth rates, drawdowns), never price series; no non-redistributable source is included.")


def append_notice(notice_path: Path, line: str = NOTICE_LINE) -> bool:
    text = notice_path.read_text(encoding="utf-8") if notice_path.exists() else ""
    if line in text:
        return False
    notice_path.write_text(text.rstrip("\n") + "\n\n" + line + "\n", encoding="utf-8")
    return True


# ------------------------------------------------------------------------------------------------ orchestration
def export(*, splice: pd.DataFrame, stages: pd.DataFrame, ids: list[str], inst_doc: dict, universe: pd.DataFrame | None = None,
           manual: dict[str, dict] | None = None, bench: dict[str, pd.DataFrame] | None = None, typology_doc: dict | None = None,
           typology_reproduction: dict | None = None, web_data: Path = WEB_DATA, src_data: Path = WEB_SRC_DATA,
           revision: str = REVISION, built: str | None = None) -> dict:
    """Write the ecz + econ_entities.json, register in meta.json, append the NOTICE line. Returns a report."""
    universe = universe if universe is not None else etf.load_universe()
    manual = manual if manual is not None else etf.manual_funds()
    bench = bench if bench is not None else I.load_benchmarks(universe)
    typology_doc = typology_doc or T.load_thresholds()["_doc"]
    years = range(S.YEAR_MIN, S.YEAR_MAX + 1)
    cov = S.coverage(splice)
    cov["last_econ_year"] = int(splice.loc[splice["gdppc"].notna(), "year"].max())
    cov["typology_reproduction"] = None if typology_reproduction is None else {k: typology_reproduction[k] for k in ("year", "n", "agree", "rate", "named_all_agree", "named_disagree")}
    arrays = encode_arrays(splice, stages, ids, years)
    header = build_header(ids=ids, years=years, arrays=arrays, splice_cov=cov, stages=stages, inst_doc=inst_doc, universe=universe,
                          manual=manual, bench=bench, typology_doc=typology_doc, built=built)
    hjson = json.dumps(header, ensure_ascii=False)
    bad = guard_text(hjson)
    if bad:
        raise RuntimeError("licence guard: " + "; ".join(bad))
    blob = pack(header, arrays)
    if len(blob) > SIZE_BUDGET:
        raise RuntimeError(f"econ.ecz is {len(blob)} B > budget {SIZE_BUDGET} B")
    out_dir = Path(web_data) / revision
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("econ.*.ecz"):
        old.unlink()
    name = f"econ.{sha8(blob)}.ecz"
    (out_dir / name).write_bytes(blob)
    rel = f"data/{revision}/{name}"
    # round-trip check against the reference decoder
    h2, arr2 = unpack(blob)
    assert h2["ids"] == ids and len(arr2["gdppc"]) == len(ids) * len(years)
    src_data = Path(src_data)
    src_data.mkdir(parents=True, exist_ok=True)
    n_ent = _json_dump(src_data / "econ_entities.json", econ_entities(ids, splice, stages, inst_doc))
    meta_path = src_data / "meta.json"
    if meta_path.exists():
        register_in_meta(meta_path, rel)
    notice_added = append_notice(out_dir / "NOTICE")
    return {"file": rel, "bytes_gz": len(blob), "bytes_raw": 4 + len(hjson.encode("utf-8")) + sum(a.nbytes for a in arrays.values()),
            "header_bytes": len(json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
            "n_countries": len(ids), "n_years": len(years), "coverage": cov, "econ_entities_bytes": n_ent,
            "meta_registered": meta_path.exists(), "notice_line_added": notice_added,
            "instruments": {"countries_with_records": len(header["instruments"]), "vt_levels": len((header["benchmark"]["vt"] or {}).get("levels", []))}}
