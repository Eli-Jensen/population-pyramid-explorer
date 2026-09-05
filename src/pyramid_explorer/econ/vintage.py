"""Vintage sensitivity check for Experiment 1 (evals/econ/PREREG.md §8).

The lookalike sets of the main run are selected on WPP 2024 back-series — today's estimate of what every pyramid *was*
at T, not what was known at T.  This module rebuilds the T cross-section from the UN's **archived** revision that was
current shortly after T (WPP 2010 for 2000 < T ≤ 2010, WPP 2000 for T ≤ 2000; WPP 2002 / 2012 as robustness inputs),
re-runs the two pre-registered selection rules with everything else held fixed — the same candidate set ``C(T)``, the
same prototype set ``P(T)`` (whose pyramids stay WPP 2024, as pre-registered), the same σ and the same ``blend``
metric; only the *candidates'* 42-share vectors change — and reports the k = 10 / k = 5 Jaccard overlap with the
WPP 2024 lookalike sets (pre-registered expectation: ≥ 0.6 at k = 10 at every T where an archive exists).

Query A is reported twice: with China's 1990 anchor vector taken from WPP 2024 (only the candidates change) and with
the anchor taken from the archive as well (everything the selector sees is of the archive's vintage).

Sources: the UN re-published every revision since 1992 as ``WPP<rev>-CSV-data.zip`` / ``WPP<rev>-Excel-files.zip``
under ``assets/Excel Files/5_Archive/`` (discovered through ``assets/downloads.json`` → folder "Archive" → group
"CSV files").  The CSV member ``WPP<rev>_PopulationByAgeSex_5x5_Medium.csv`` (5-year age groups × 5-year time points,
1 July, thousands, medium variant) is what this module reads.  Raw files live under ``data/raw/wpp_archive/`` (gitignored).

Everything below is a pure function of what is handed in; :mod:`scripts.vintage_check` wires the real corpus.
Language rule (PREREG §7): the outputs describe what happened; nothing here is a forecast.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pyramid_explorer.econ import lookalike as lk
from pyramid_explorer.metrics import distances
from pyramid_explorer.paths import AGE_STARTS, DATA_RAW, ECON_EVALS, N_BINS, N_DIMS

ARCHIVE_DIR = DATA_RAW / "wpp_archive"
VINTAGE_DIR = ECON_EVALS / "vintage"
VINTAGE_JSON = VINTAGE_DIR / "vintage_check.json"
VINTAGE_MD = VINTAGE_DIR / "RESULTS_vintage.md"
DOWNLOADS_JSON_URL = "https://population.un.org/wpp/assets/downloads.json"
ARCHIVE_BASE_URL = "https://population.un.org/wpp/assets/Excel%20Files/5_Archive/"
ARCHIVE_PAGE_URL = "https://population.un.org/wpp/Download/Archive/"
# downloads.json: Folders[name="Archive"] → MajorGroup[name="CSV files"] → SubGroup[name="<rev> Revision"] → Item[0].File[0].Path
REVISION_ZIPS: dict[int, str] = {1998: "WPP1998-CSV-data.zip", 2000: "WPP2000-CSV-data.zip", 2002: "WPP2002-CSV-data.zip",
                                 2004: "WPP2004-CSV-data.zip", 2006: "WPP2006-CSV-data.zip", 2008: "WPP2008-CSV-data.zip",
                                 2010: "WPP2010-CSV-data.zip", 2012: "WPP2012-CSV-data.zip", 2015: "WPP2015-CSV-data.zip"}
POP_MEMBER = "WPP{rev}_PopulationByAgeSex_5x5_Medium.csv"
THRESHOLD_JACCARD = 0.6          # PREREG §8, k = 10
KS = (10, 5)
PRIMARY_T = (2010, 2000)         # the two T's the check was written for; the other archive T's are additional rows
# Archive entities that no longer exist as one WPP 2024 country.  A predecessor is mapped to the successor that kept the
# ISO3 code ONLY when that successor has no row of its own in the archive; the mapping is reported in the output.
PREDECESSORS: dict[int, tuple[str, str]] = {
    736: ("SDN", "Sudan (Former): the pre-2011 state, i.e. today's Sudan plus South Sudan"),
    891: ("SRB", "Serbia and Montenegro: today's Serbia plus Montenegro (and Kosovo)"),
}
# Archive-only entities with no ≥ 1 M successor in the corpus: reported as unmapped, never merged into anything.
ARCHIVE_ONLY_NOTES: dict[int, str] = {
    530: "Netherlands Antilles (dissolved 2010; CUW, SXM and BES are separate WPP 2024 entities)",
    830: "Channel Islands (GGY and JEY are separate WPP 2024 entities)",
}
ARCHIVE_LABELS: dict[int, str] = {158: "labelled 'Other non-specified areas' in WPP 2010/2012 (Taiwan Province of China)"}
CSV_KW = dict(keep_default_na=False, na_values=[""], low_memory=False)


# ----------------------------------------------------------------------------------------------- revisions
def revision_for_T(T: int) -> int | None:
    """PREREG §8: WPP 2000 for T ≤ 2000, WPP 2010 for 2000 < T ≤ 2010, nothing for later T (no archive predates the outcome)."""
    if T <= 2000:
        return 2000
    if T <= 2010:
        return 2010
    return None


def archive_url(rev: int) -> str:
    return ARCHIVE_BASE_URL + REVISION_ZIPS[rev]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_archive(rev: int, archive_dir: Path = ARCHIVE_DIR, *, download: bool = True) -> dict[str, Any]:
    """The ``WPP<rev>-CSV-data.zip`` for ``rev`` under ``archive_dir`` (downloaded when absent and ``download``), with the
    population member extracted to ``archive_dir/wpp<rev>/``.  Returns the source record (url, paths, sha256, bytes)."""
    if rev not in REVISION_ZIPS:
        raise KeyError(f"no archived CSV revision {rev}; known: {sorted(REVISION_ZIPS)}")
    archive_dir = Path(archive_dir)
    zip_path = archive_dir / REVISION_ZIPS[rev]
    if not zip_path.exists():
        if not download:
            raise FileNotFoundError(f"{zip_path} missing and download disabled")
        from pyramid_explorer.data.base import download as _download

        _download(archive_url(rev), zip_path)
    member = POP_MEMBER.format(rev=rev)
    out_dir = archive_dir / f"wpp{rev}"
    csv_path = out_dir / member
    with zipfile.ZipFile(zip_path) as zf:
        info = zf.getinfo(member)
        if not csv_path.exists() or csv_path.stat().st_size != info.file_size:
            zf.extract(member, out_dir)
        member_date = "%04d-%02d-%02d" % info.date_time[:3]
    return {"revision": rev, "zip": REVISION_ZIPS[rev], "url": archive_url(rev), "discovered_via": DOWNLOADS_JSON_URL,
            "archive_page": ARCHIVE_PAGE_URL, "zip_path": str(zip_path), "zip_sha256": sha256_of(zip_path),
            "zip_bytes": zip_path.stat().st_size, "member": member, "member_path": str(csv_path),
            "member_sha256": sha256_of(csv_path), "member_bytes": csv_path.stat().st_size, "member_zip_date": member_date}


def load_archive_population(rev: int, archive_dir: Path = ARCHIVE_DIR) -> pd.DataFrame:
    """Long frame ``locid, name, year, age_start, age_span, pop_male, pop_female`` (thousands, 1 July, medium variant) from
    the extracted ``WPP<rev>_PopulationByAgeSex_5x5_Medium.csv``."""
    path = Path(archive_dir) / f"wpp{rev}" / POP_MEMBER.format(rev=rev)
    df = pd.read_csv(path, usecols=["LocID", "Location", "Variant", "Time", "AgeGrpStart", "AgeGrpSpan", "PopMale", "PopFemale"], **CSV_KW)
    df = df[df["Variant"].astype(str) == "Medium"]
    out = df.rename(columns={"LocID": "locid", "Location": "name", "Time": "year", "AgeGrpStart": "age_start", "AgeGrpSpan": "age_span",
                             "PopMale": "pop_male", "PopFemale": "pop_female"}).drop(columns="Variant")
    for c in ("locid", "year", "age_start", "age_span"):
        out[c] = out[c].astype(int)
    for c in ("pop_male", "pop_female"):
        out[c] = out[c].astype(np.float64)
    return out.reset_index(drop=True)


# ----------------------------------------------------------------------------------------------- bins
def align_bins(age_starts: np.ndarray, pop_male: np.ndarray, pop_female: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    """Map an archive's 5-year age groups onto the corpus's 21 bins (0–4 … 95–99, 100+; CONTRACT §1).

    * identical 21 bins → identity;
    * a shorter ladder whose last bin is open-ended below 100 (e.g. 80+) → the open bin's people are placed in the
      corpus bin that starts at the same age and every bin above it is zero (the archive did not resolve those ages);
    * a longer ladder (100–104, 105+ …) → everything from 100 up is summed into the 100+ bin.
    Returns ``(m21, f21, note)``; irregular ladders raise."""
    a = np.asarray(age_starts, dtype=int)
    m = np.asarray(pop_male, dtype=np.float64)
    f = np.asarray(pop_female, dtype=np.float64)
    order = np.argsort(a)
    a, m, f = a[order], m[order], f[order]
    if len(a) != len(np.unique(a)) or (a % 5).any() or a[0] != 0 or (np.diff(a) != 5).any():
        raise ValueError(f"irregular age ladder {a.tolist()}")
    if a.tolist() == AGE_STARTS:
        return m, f, "identity: the archive carries the same 21 five-year bins with an open 100+ bin"
    m21, f21 = np.zeros(N_BINS), np.zeros(N_BINS)
    if a[-1] < 100:
        m21[: len(a)], f21[: len(a)] = m, f
        return m21, f21, (f"open bin {a[-1]}+ placed in the corpus bin {a[-1]}–{a[-1] + 4}; bins above {a[-1] + 4} set to zero "
                          f"(the archive resolves no ages beyond {a[-1]}+)")
    m21[:N_BINS - 1], f21[:N_BINS - 1] = m[:N_BINS - 1], f[:N_BINS - 1]
    m21[N_BINS - 1], f21[N_BINS - 1] = m[N_BINS - 1:].sum(), f[N_BINS - 1:].sum()
    return m21, f21, f"{len(a)} bins: everything from age 100 up summed into the 100+ bin"


# ----------------------------------------------------------------------------------------------- cross-section
@dataclass
class ArchiveSlice:
    """One archived revision's T cross-section on the corpus's country ids."""
    revision: int
    year: int
    X: np.ndarray                                  # [n, 42] shares, rows aligned with ``keys``
    keys: pd.DataFrame                             # iso3, locid, name, pop_total (thousands), via (None | predecessor note)
    predecessors_used: list[dict] = field(default_factory=list)
    archive_unmapped: list[dict] = field(default_factory=list)      # archive countries/areas (LocID < 900) with no corpus id
    corpus_absent: list[str] = field(default_factory=list)          # corpus countries with no archive row
    bin_note: str = ""

    def vector(self, iso3: str) -> np.ndarray | None:
        hit = np.flatnonzero(self.keys["iso3"].to_numpy() == iso3)
        return self.X[int(hit[0])] if len(hit) else None

    def vectors(self, iso3s) -> dict[str, np.ndarray]:
        pos = {i: n for n, i in enumerate(self.keys["iso3"])}
        return {i: self.X[pos[i]] for i in iso3s if i in pos}


def archive_cross_section(pop: pd.DataFrame, year: int, entities: list[dict], *, revision: int = 0,
                          predecessors: dict[int, tuple[str, str]] | None = None) -> ArchiveSlice:
    """Build the s42 vectors of every corpus country the archive knows at ``year`` (CONTRACT §1: 21 male then 21 female
    shares of the two-sex total).  Countries are matched on the UN ``LocID`` (stable across revisions); a
    :data:`PREDECESSORS` entity stands in for its successor only when the successor has no row of its own.  Reports the
    archive entities left unmapped and the corpus countries absent from the archive."""
    predecessors = PREDECESSORS if predecessors is None else predecessors
    sub = pop[pop["year"] == year]
    if sub.empty:
        raise ValueError(f"the archive has no rows for year {year}")
    by_loc = {int(e["locid"]): e["id"] for e in entities if e.get("type") == "country"}
    present = set(int(v) for v in sub["locid"].unique())
    loc_to_iso: dict[int, tuple[str, str | None]] = {lid: (iso, None) for lid, iso in by_loc.items() if lid in present}
    used = []
    iso_present = {iso for iso, _ in loc_to_iso.values()}
    for lid, (iso, note) in predecessors.items():
        if lid in present and iso not in iso_present and iso in by_loc.values():
            loc_to_iso[lid] = (iso, note)
            iso_present.add(iso)
            used.append({"locid": lid, "iso3": iso, "name": str(sub.loc[sub["locid"] == lid, "name"].iloc[0]), "note": note})
    names = sub.drop_duplicates("locid").set_index("locid")["name"].astype(str)
    unmapped = [{"locid": int(lid), "name": names[lid], "note": ARCHIVE_ONLY_NOTES.get(int(lid))}
                for lid in sorted(present) if lid < 900 and lid not in loc_to_iso]
    absent = sorted(iso for lid, iso in by_loc.items() if iso not in iso_present)
    rows, X, note = [], [], ""
    for lid, (iso, via) in sorted(loc_to_iso.items(), key=lambda kv: kv[1][0]):
        g = sub[sub["locid"] == lid].sort_values("age_start")
        m21, f21, note = align_bins(g["age_start"].to_numpy(), g["pop_male"].to_numpy(), g["pop_female"].to_numpy())
        total = float(m21.sum() + f21.sum())
        if not total > 0:
            raise ValueError(f"zero population for {iso} ({lid}) in {year}")
        X.append(np.concatenate([m21, f21]) / total)
        rows.append({"iso3": iso, "locid": int(lid), "name": names[lid], "pop_total": total, "via": via})
    keys = pd.DataFrame(rows, columns=["iso3", "locid", "name", "pop_total", "via"])
    Xa = np.asarray(X, dtype=np.float64).reshape(-1, N_DIMS)
    return ArchiveSlice(revision, year, Xa, keys, used, unmapped, absent, note)


def archive_vector(pop: pd.DataFrame, entities: list[dict], iso3: str = lk.ANCHOR_ID, year: int = lk.ANCHOR_YEAR) -> np.ndarray | None:
    """One country's s42 vector from the archive at ``year`` (the Query A anchor, China 1990, by default); None when the
    archive has no such row.  Matches on LocID like :func:`archive_cross_section` (predecessor rows are not used here)."""
    lid = next((int(e["locid"]) for e in entities if e.get("id") == iso3 and e.get("type") == "country"), None)
    if lid is None:
        return None
    g = pop[(pop["year"] == year) & (pop["locid"] == lid)].sort_values("age_start")
    if g.empty:
        return None
    m21, f21, _ = align_bins(g["age_start"].to_numpy(), g["pop_male"].to_numpy(), g["pop_female"].to_numpy())
    total = float(m21.sum() + f21.sum())
    return np.concatenate([m21, f21]) / total


# ----------------------------------------------------------------------------------------------- selection
def jaccard(a, b) -> float:
    """|A ∩ B| / |A ∪ B| over two iterables of ids (1.0 for two empty sets)."""
    A, B = set(a), set(b)
    return 1.0 if not (A | B) else len(A & B) / len(A | B)


def rank_candidates(corpus: lk.Corpus, cand: pd.DataFrame, P: pd.DataFrame, vectors: dict[str, np.ndarray], *,
                    anchor: np.ndarray | None) -> pd.DataFrame:
    """The two selection statistics of PREREG §3.3 for every candidate that has a vector in ``vectors`` (iso3 → s42):
    ``D_P`` (min blend distance to the prototype pyramids, which stay the corpus's), ``D2`` (second-smallest, the tie-break)
    and ``d_A`` (blend distance to ``anchor``; NaN for the anchor country itself, which Query A excludes, and everywhere
    when ``anchor`` is None).  Sorted by iso3; the candidate columns are kept."""
    keep = cand[cand["iso3"].isin(vectors)].sort_values("iso3").reset_index(drop=True)
    if keep.empty:
        return keep.assign(D_P=np.nan, D2=np.nan, d_A=np.nan)
    Xc = np.stack([vectors[i] for i in keep["iso3"]])
    Dm = (np.stack([distances("blend", corpus.X[int(p)], Xc, sigma=corpus.sigma).astype(np.float64) for p in P["row"]])
          if len(P) else np.zeros((0, len(keep))))
    md = lk.min_distances(Dm)
    d_a = np.full(len(keep), np.nan)
    if anchor is not None:
        d_a = distances("blend", anchor, Xc, sigma=corpus.sigma).astype(np.float64)
        d_a[keep["iso3"].to_numpy() == lk.ANCHOR_ID] = np.nan
    return keep.assign(D_P=md["D"], D2=md["D2"], d_A=d_a)


def select_lookalikes(ranked: pd.DataFrame, ks: tuple[int, ...] = KS) -> dict[str, dict[int, pd.DataFrame]]:
    """Query A and Query B lookalike sets from a :func:`rank_candidates` frame — the main run's rules: Query B = the k
    smallest ``D_P`` (ties by ``D2``, then iso3); Query A = the k smallest ``d_A`` (the anchor country is excluded).
    Returns ``{"A": {k: picks}, "B": {k: picks}}`` with ``iso3, d`` plus the candidate columns."""
    out: dict[str, dict[int, pd.DataFrame]] = {"A": {}, "B": {}}
    b = ranked.drop(columns=[c for c in ("d",) if c in ranked])
    a = b[np.isfinite(b["d_A"].to_numpy(dtype=np.float64))].reset_index(drop=True)
    for k in ks:
        out["B"][k] = lk._rank_pick(b, b["D_P"].to_numpy(dtype=np.float64), b["D2"].to_numpy(dtype=np.float64), k)
        out["A"][k] = lk._rank_pick(a, a["d_A"].to_numpy(dtype=np.float64), a["d_A"].to_numpy(dtype=np.float64), k)
    return out


def rank_continuity(base: pd.DataFrame, alt: pd.DataFrame, col: str, k: int = 10) -> dict[str, Any]:
    """How the archive re-orders the candidates (additional diagnostics, not pre-registered): Spearman ρ between the WPP 2024
    and archive statistics over the common candidates, the archive rank of every member of the WPP 2024 k-set, and how
    many of them stay within the archive's first k / 2k."""
    from scipy.stats import spearmanr

    m = base[["iso3", col]].merge(alt[["iso3", col]], on="iso3", suffixes=("_wpp2024", "_archive"))
    m = m[np.isfinite(m[f"{col}_wpp2024"]) & np.isfinite(m[f"{col}_archive"])]
    if len(m) < 3:
        return {"n": int(len(m)), "spearman": None}
    rho = float(spearmanr(m[f"{col}_wpp2024"], m[f"{col}_archive"]).statistic)
    r24 = m[f"{col}_wpp2024"].rank(method="first")
    ra = m[f"{col}_archive"].rank(method="first")
    top = m.loc[r24 <= k, "iso3"]
    ranks = {str(i): int(ra[m["iso3"] == i].iloc[0]) for i in top}
    vals = np.array(list(ranks.values()), dtype=float)
    return {"n": int(len(m)), "spearman": rho, "k": k, "archive_ranks_of_wpp2024_set": ranks,
            "median_archive_rank": float(np.median(vals)) if len(vals) else None, "max_archive_rank": int(vals.max()) if len(vals) else None,
            "n_within_k": int((vals <= k).sum()), "n_within_2k": int((vals <= 2 * k).sum()),
            "median_abs_change": float(np.median(np.abs(m[f"{col}_archive"] - m[f"{col}_wpp2024"]))),
            "wpp2024_kth_gap": float(np.sort(m[f"{col}_wpp2024"].to_numpy())[min(2 * k, len(m)) - 1] - np.sort(m[f"{col}_wpp2024"].to_numpy())[0])}


def recorded_lookalikes(backtest: dict, query: str, k: int, T: int, *, h: int = 10) -> list[str]:
    """The main run's lookalike set (ordered by distance) for ``query`` at ``T`` from ``backtest_lookalikes.json``."""
    row = (backtest.get("rows") or {}).get(f"{query}|{k}|{h}|growth") or {}
    picks = [p for p in row.get("picks", []) if int(p["T"]) == T]
    return [p["iso3"] for p in sorted(picks, key=lambda p: (float(p["d"]), p["iso3"]))]


# ----------------------------------------------------------------------------------------------- revision size
def revision_table(corpus: lk.Corpus, T: int, sl: ArchiveSlice, iso3s, entities: list[dict] | None = None) -> pd.DataFrame:
    """Per country in ``iso3s`` with an archive vector: ``l2`` = ‖s42_archive − s42_2024‖₂, ``l2_sigma`` = l2 / σ_l2,
    ``d_blend`` (the metric's own units), and the total-population revision ``pop_rel`` = pop_archive / pop_2024 − 1."""
    names = {e["id"]: e.get("name", e["id"]) for e in (entities or corpus.entities)}
    sig = float(corpus.sigma["l2"]["2"])
    rows = []
    vec = sl.vectors(iso3s)
    for iso in sorted(vec):
        a, b = vec[iso], corpus.X[corpus.row(iso, T)]
        l2 = float(np.linalg.norm(a - b))
        pop24 = float(corpus.pop_wide.at[iso, T])
        popa = float(sl.keys.loc[sl.keys["iso3"] == iso, "pop_total"].iloc[0])
        rows.append({"iso3": iso, "name": names.get(iso, iso), "l2": l2, "l2_sigma": l2 / sig,
                     "d_blend": float(distances("blend", a, b[None, :], sigma=corpus.sigma)[0]),
                     "pop_2024": pop24, "pop_archive": popa, "pop_rel": popa / pop24 - 1.0 if pop24 > 0 else float("nan"),
                     "via": sl.keys.loc[sl.keys["iso3"] == iso, "via"].iloc[0]})
    return pd.DataFrame(rows, columns=["iso3", "name", "l2", "l2_sigma", "d_blend", "pop_2024", "pop_archive", "pop_rel", "via"])


def _summ(rev: pd.DataFrame, n_largest: int = 10) -> dict[str, Any]:
    if rev.empty:
        return {"n": 0}
    big = rev.sort_values("l2", ascending=False).head(n_largest)
    return {"n": int(len(rev)), "l2_median": float(rev["l2"].median()), "l2_max": float(rev["l2"].max()),
            "l2_max_iso3": str(rev.loc[rev["l2"].idxmax(), "iso3"]), "l2_sigma_median": float(rev["l2_sigma"].median()),
            "l2_sigma_max": float(rev["l2_sigma"].max()), "d_blend_median": float(rev["d_blend"].median()),
            "d_blend_max": float(rev["d_blend"].max()), "pop_rel_abs_median": float(rev["pop_rel"].abs().median()),
            "pop_rel_abs_max": float(rev["pop_rel"].abs().max()), "pop_rel_abs_max_iso3": str(rev.loc[rev["pop_rel"].abs().idxmax(), "iso3"]),
            "largest": [{k: (None if (isinstance(v, float) and not np.isfinite(v)) else v) for k, v in r.items()}
                        for r in big[["iso3", "name", "l2", "l2_sigma", "d_blend", "pop_rel", "via"]].to_dict("records")]}


# ----------------------------------------------------------------------------------------------- one T
def check_T(corpus: lk.Corpus, gd: lk.GrowthData, T: int, sl: ArchiveSlice, backtest: dict | None, *, anchor_archive: np.ndarray | None = None,
            ks: tuple[int, ...] = KS, threshold: float = THRESHOLD_JACCARD, role: str = "primary") -> dict[str, Any]:
    """The whole check for one (T, archive): candidate/prototype sets as in the main run, WPP 2024 self-check (the
    re-implementation must reproduce the recorded lookalike sets exactly), archive selections for Query B and Query A
    (anchor from WPP 2024, and from the archive when ``anchor_archive`` — China 1990 of the archive — is given), Jaccard
    per k against the WPP 2024 sets, rank-continuity diagnostics and the revision-size table over ``C(T)``."""
    cand = lk.candidates(corpus, gd, T, 10)
    P = lk.prototype_set(corpus, gd, T)
    anchor24 = corpus.X[corpus.row(lk.ANCHOR_ID, lk.ANCHOR_YEAR)]
    vec24 = {i: corpus.X[int(r)] for i, r in zip(cand["iso3"], cand["row"])}
    ranked24 = rank_candidates(corpus, cand, P, vec24, anchor=anchor24)
    base = select_lookalikes(ranked24, ks)
    vec_arch = sl.vectors(cand["iso3"])
    unmapped = sorted(set(cand["iso3"]) - set(vec_arch))
    ranked_a24 = rank_candidates(corpus, cand, P, vec_arch, anchor=anchor24)
    ranked_aa = rank_candidates(corpus, cand, P, vec_arch, anchor=anchor_archive) if anchor_archive is not None else None
    arch_a24 = select_lookalikes(ranked_a24, ks)
    arch_aa = select_lookalikes(ranked_aa, ks) if ranked_aa is not None else None
    variants = {
        "B": ("B", arch_a24["B"], ranked_a24, "D_P", "Query B — PRIMARY: min blend distance to P(T); archive candidate vectors, WPP 2024 prototypes"),
        "A_anchor_wpp2024": ("A", arch_a24["A"], ranked_a24, "d_A", "Query A — China-1990 anchor from WPP 2024, archive candidate vectors"),
        "A_anchor_archive": ("A", None if arch_aa is None else arch_aa["A"], ranked_aa, "d_A", "Query A — China-1990 anchor AND candidate vectors from the archive"),
    }
    self_check, queries = {}, {}
    for name, (q, picks_by_k, ranked_alt, col, label) in variants.items():
        queries[name] = {"query": q, "label": label, "k": {}}
        for k in ks:
            recomputed = list(base[q][k]["iso3"])
            recorded = recorded_lookalikes(backtest, q, k, T) if backtest else None
            self_check.setdefault(q, {})[str(k)] = {"recorded": recorded, "recomputed": recomputed,
                                                    "identical": None if recorded is None else recorded == recomputed}
            wpp = recorded if recorded is not None else recomputed
            if picks_by_k is None:
                queries[name]["k"][str(k)] = {"wpp2024": wpp, "archive": None, "jaccard": None, "met": None,
                                              "note": "China 1990 is not in this archive"}
                continue
            arch = list(picks_by_k[k]["iso3"])
            j = jaccard(wpp, arch)
            queries[name]["k"][str(k)] = {"wpp2024": wpp, "archive": arch, "archive_d": [float(x) for x in picks_by_k[k]["d"]],
                                          "n_common": len(set(wpp) & set(arch)), "jaccard": j,
                                          "only_wpp2024": sorted(set(wpp) - set(arch)), "only_archive": sorted(set(arch) - set(wpp)),
                                          "met": (j >= threshold) if k == 10 else None}
        if ranked_alt is not None:
            queries[name]["rank_continuity"] = rank_continuity(ranked24, ranked_alt, col, k=10)
    rev = revision_table(corpus, T, sl, cand["iso3"])
    anchor_rev = None
    if anchor_archive is not None:
        anchor_rev = {"l2": float(np.linalg.norm(anchor_archive - anchor24)), "l2_sigma": float(np.linalg.norm(anchor_archive - anchor24) / corpus.sigma["l2"]["2"]),
                      "d_blend": float(distances("blend", anchor_archive, anchor24[None, :], sigma=corpus.sigma)[0])}
    return {"T": T, "revision": sl.revision, "role": role, "n_candidates": int(len(cand)), "n_candidates_with_archive": int(len(vec_arch)),
            "unmapped_candidates": unmapped, "n_prototypes": int(len(P)),
            "predecessors_used_in_candidates": [p for p in sl.predecessors_used if p["iso3"] in set(cand["iso3"])],
            "self_check_wpp2024_reproduced": self_check, "queries": queries, "revision_size": _summ(rev), "anchor_revision": anchor_rev,
            "revision_rows": rev.to_dict("records")}


def summarise(per_T: dict[str, dict], *, threshold: float = THRESHOLD_JACCARD) -> dict[str, Any]:
    """Which (query, T) cells met the k = 10 ≥ threshold expectation; Query B is the pre-registered primary."""
    cells, not_met, b_met = 0, [], []
    for tkey, doc in sorted(per_T.items()):
        for name, q in doc["queries"].items():
            c = q["k"].get("10") or {}
            if c.get("jaccard") is None:
                continue
            cells += 1
            if not c["met"]:
                not_met.append(f"{name}@{tkey}")
            if name == "B":
                b_met.append(bool(c["met"]))
    return {"expectation": f"k = 10 Jaccard(WPP 2024 set, archive set) ≥ {threshold} at every T where an archive exists (PREREG §8); Query B is the primary rule",
            "threshold": threshold, "cells": cells, "cells_met": cells - len(not_met), "not_met": not_met,
            "B_k10_met_at_every_T": bool(b_met) and all(b_met), "n_T": len(per_T)}


# ----------------------------------------------------------------------------------------------- report
def _f(x, nd=3):
    return "—" if x is None else f"{float(x):.{nd}f}"


def render_vintage_md(doc: dict) -> str:
    """``evals/econ/vintage/RESULTS_vintage.md`` from the check document."""
    m = doc.get("_meta") or {}
    L = ["# Vintage sensitivity check — Experiment 1 lookalike sets (PREREG §8)", "",
         f"**Generated:** {m.get('generated_at', 'n/a')} · code revision `{m.get('git_rev', 'n/a')}` · `scripts/vintage_check.py` · "
         f"main-run input `evals/econ/backtest_lookalikes.json` (generated {(m.get('backtest_run') or {}).get('generated_at', 'n/a')}, "
         f"code `{(m.get('backtest_run') or {}).get('git_rev', 'n/a')}`).", "",
         "## 1. Question and method", "",
         "The main run selects lookalikes as of T on WPP 2024 back-series — today's estimate of what each pyramid *was* at T, not what "
         "was known at T (PREREG §8). This check rebuilds the T cross-section from the UN revision current shortly after T and re-runs the "
         "two pre-registered selection rules with **everything else held fixed**: the same candidate set C(T) (countries with WPP 2024 "
         "population ≥ 1 M at T and a single-source growth window), the same prototype set P(T) (its pyramids stay WPP 2024 — the "
         "prototypes are chosen on GDP windows, as pre-registered), the same σ (`data/processed/sigma.json`) and the same `blend` metric "
         "(½·L2/σ + ½·per-sex W1/σ on the 42 age×sex shares). Only the **candidates'** 42-share vectors are swapped for the archive's. "
         "Query B (PRIMARY) = the k candidates with the smallest min-distance to P(T), ties by the second-smallest prototype distance. "
         "Query A = the k candidates nearest China 1990, reported twice: anchor vector from WPP 2024 (only the candidates change) and "
         "anchor from the archive as well (everything the selector sees is of the archive's vintage). Candidates the archive does not "
         "carry are dropped from the archive-side set and listed. Overlap = Jaccard |A∩B|/|A∪B| between the WPP 2024 set and the archive "
         "set at k = 10 (pre-registered expectation ≥ 0.6) and k = 5 (secondary). Revision size per country = ‖s42_archive − s42_2024‖₂ "
         "(also in σ_l2 units and as the blend distance between the two vectors).", "",
         f"Revision rule: WPP 2000 for T ≤ 2000, WPP 2010 for 2000 < T ≤ 2010 (PREREG §8). Primary T's: {', '.join(str(t) for t in m.get('primary_T', PRIMARY_T))}; "
         "the other T's the archives cover are additional rows under the same rule. Robustness rows use the next revision (WPP 2002 for T = 2000).", "",
         "**Self-check.** Before touching the archive, the re-implementation was run on the WPP 2024 vectors and had to reproduce the "
         "recorded lookalike sets exactly (same ids, same order) — see §5.", "",
         "## 2. Sources", "",
         f"Discovered through `{DOWNLOADS_JSON_URL}` (folder *Archive* → group *CSV files* → *<rev> Revision*), also listed on `{ARCHIVE_PAGE_URL}`. "
         "Raw files under `data/raw/wpp_archive/` (gitignored). Member read: `WPP<rev>_PopulationByAgeSex_5x5_Medium.csv` "
         "(medium variant, 5-year age groups × 5-year time points, 1 July, thousands).", "",
         "| revision | zip | url | zip sha256 | bytes | member | member sha256 | member date in zip |", "|---|---|---|---|---|---|---|---|"]
    for rev, s in sorted((doc.get("sources") or {}).items()):
        L.append(f"| WPP {s.get('revision', rev)} | `{s.get('zip')}` | {s.get('url')} | `{s.get('zip_sha256')}` | {s.get('zip_bytes')} | `{s.get('member')}` | "
                 f"`{s.get('member_sha256')}` | {s.get('member_zip_date')} |")
    L += ["", "Not used: `WPP<rev>-Excel-files.zip` (the 2010 Excel release, 402 MB, carries the same medium-variant figures as the CSV re-export); "
          "WPP 2012 (`WPP2012-CSV-data.zip`, 125 MB) exists at the same location and was not needed.", "",
          "## 3. Bin alignment", "", doc.get("bin_alignment") or "—", "",
          "## 4. Entity mapping", "",
          "Countries are matched on the UN `LocID` (stable across revisions; the corpus's `pipeline/locations.parquet` carries LocID ↔ ISO3). "
          "A predecessor state stands in for the successor that kept its ISO3 code only when the successor has no row of its own; "
          "the substitution is flagged on every row that uses it.", ""]
    for rev, mp in sorted((doc.get("mapping") or {}).items()):
        L.append(f"**WPP {rev} at {mp.get('year')}:** {mp.get('n_mapped')} of {mp.get('n_corpus_countries')} corpus countries mapped.")
        if mp.get("predecessors_used"):
            L.append("- predecessor rows used: " + "; ".join(f"LocID {p['locid']} “{p['name']}” → {p['iso3']} ({p['note']})" for p in mp["predecessors_used"]))
        if mp.get("archive_unmapped"):
            L.append("- archive countries/areas (LocID < 900) with no corpus id: " + "; ".join(f"LocID {u['locid']} “{u['name']}”" + (f" — {u['note']}" if u.get("note") else "") for u in mp["archive_unmapped"]))
        if mp.get("labels"):
            L.append("- labels: " + "; ".join(f"LocID {k} {v}" for k, v in mp["labels"].items()))
        L.append(f"- corpus countries absent from the archive ({len(mp.get('corpus_absent') or [])}, none ≥ 1 M except where listed under the T rows): "
                 + ", ".join(mp.get("corpus_absent") or []) )
        L.append("")
    L += ["## 5. Results per T", ""]
    summ = doc.get("summary") or {}
    L += [f"**Expectation:** {summ.get('expectation')} — met in {summ.get('cells_met')} of {summ.get('cells')} (query, T) cells"
          + (f"; not met: {', '.join(summ['not_met'])}" if summ.get("not_met") else "") + ". "
          + ("Query B met the expectation at every T." if summ.get("B_k10_met_at_every_T") else "Query B did NOT meet the expectation at every T."), ""]

    def block(key: str, d: dict) -> list[str]:
        out = [f"### T = {d['T']} · WPP {d['revision']} ({d.get('role')})", "",
               f"C(T): {d['n_candidates']} candidates, {d['n_candidates_with_archive']} with an archive vector"
               + (f"; without one (dropped from the archive side): {', '.join(d['unmapped_candidates'])}" if d.get("unmapped_candidates") else "")
               + f". P(T): {d['n_prototypes']} prototypes (WPP 2024 pyramids)."]
        if d.get("predecessors_used_in_candidates"):
            out.append("Predecessor rows inside C(T): " + "; ".join(f"{p['iso3']} ← LocID {p['locid']} “{p['name']}”" for p in d["predecessors_used_in_candidates"]) + ".")
        sc = d.get("self_check_wpp2024_reproduced") or {}
        flags = [f"{q} k={k}: {'reproduced' if v.get('identical') else ('n/a' if v.get('identical') is None else 'MISMATCH')}" for q, ks_ in sc.items() for k, v in ks_.items()]
        out += ["", "Self-check (WPP 2024 vectors → recorded sets): " + "; ".join(flags) + ".", "",
                "| rule | k | WPP 2024 set | archive set | common | Jaccard | ≥ 0.6 |", "|---|---|---|---|---|---|---|"]
        for name, q in d["queries"].items():
            for k, c in q["k"].items():
                if c.get("jaccard") is None:
                    out.append(f"| {name} | {k} | {', '.join(c.get('wpp2024') or [])} | — | — | — | {c.get('note', '—')} |")
                    continue
                met = "—" if c.get("met") is None else ("met" if c["met"] else "**not met**")
                out.append(f"| {name} | {k} | {', '.join(c['wpp2024'])} | {', '.join(c['archive'])} | {c['n_common']} | {_f(c['jaccard'], 2)} | {met} |")
        rc_lines = []
        for name, q in d["queries"].items():
            rc = q.get("rank_continuity") or {}
            if rc.get("spearman") is not None:
                rc_lines.append(f"{name}: Spearman ρ {rc['spearman']:.3f} over {rc['n']} common candidates; the WPP 2024 k = 10 set sits at archive ranks "
                                f"median {rc['median_archive_rank']:.0f} / max {rc['max_archive_rank']} ({rc['n_within_k']} within 10, {rc['n_within_2k']} within 20); "
                                f"median |Δ statistic| {rc['median_abs_change']:.4f} vs a WPP 2024 rank-1→rank-20 spread of {rc['wpp2024_kth_gap']:.4f}")
        if rc_lines:
            out += ["", "Rank continuity (additional diagnostics, not pre-registered): " + " · ".join(rc_lines) + "."]
        rs = d.get("revision_size") or {}
        if rs.get("n"):
            out += ["", f"Revision size over the {rs['n']} candidates with both vectors: median L2 {_f(rs['l2_median'], 4)} (max {_f(rs['l2_max'], 4)}, {rs['l2_max_iso3']}); "
                    f"in σ_l2 units median {_f(rs['l2_sigma_median'], 3)} (max {_f(rs['l2_sigma_max'], 3)}); blend distance between the two vintages median "
                    f"{_f(rs['d_blend_median'], 3)} (max {_f(rs['d_blend_max'], 3)}); |total-population revision| median {100 * rs['pop_rel_abs_median']:.1f} % "
                    f"(max {100 * rs['pop_rel_abs_max']:.1f} %, {rs['pop_rel_abs_max_iso3']}).",
                    "", "Ten largest shape revisions (L2):", "", "| iso3 | name | L2 | L2/σ | blend d | Δpop | via |", "|---|---|---|---|---|---|---|"]
            for r in rs.get("largest") or []:
                out.append(f"| {r['iso3']} | {r['name']} | {_f(r['l2'], 4)} | {_f(r['l2_sigma'], 3)} | {_f(r['d_blend'], 3)} | "
                           f"{'—' if r.get('pop_rel') is None else f'{100 * r['pop_rel']:+.1f} %'} | {r.get('via') or '—'} |")
        ar = d.get("anchor_revision")
        if ar:
            out += ["", f"China 1990 anchor: archive vs WPP 2024 L2 {_f(ar['l2'], 4)} ({_f(ar['l2_sigma'], 3)} σ_l2), blend distance {_f(ar['d_blend'], 3)}."]
        out.append("")
        return out

    for key, d in sorted((doc.get("per_T") or {}).items(), key=lambda kv: -int(kv[0])):
        L += block(key, d)
    if doc.get("robustness"):
        L += ["## 6. Robustness rows (next revision)", ""]
        for key, d in sorted(doc["robustness"].items()):
            L += block(key, d)
    L += ["## 7. Caveats", ""]
    L += [f"- {c}" for c in (doc.get("caveats") or [])] or ["- none"]
    L.append("")
    return "\n".join(L)


__all__ = ["revision_for_T", "archive_url", "ensure_archive", "load_archive_population", "align_bins", "ArchiveSlice",
           "archive_cross_section", "archive_vector", "jaccard", "rank_candidates", "select_lookalikes", "rank_continuity",
           "recorded_lookalikes", "revision_table", "check_T", "summarise",
           "render_vintage_md", "ARCHIVE_DIR", "VINTAGE_DIR", "VINTAGE_JSON", "VINTAGE_MD", "THRESHOLD_JACCARD", "PREDECESSORS", "KS", "PRIMARY_T"]
