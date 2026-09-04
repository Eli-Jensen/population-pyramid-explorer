"""Canonical, text-free population-pyramid renders for the image-embedding experiment (CONTRACT §3 `render.py`).

Pure numpy raster (integer pixels, no anti-aliasing, no fonts): identical share vectors give identical bytes on
every machine and library version.  Two styles:

* ``canon2`` — two-sex: 21 rows of ``size/21`` px with 100+ on top, male bars growing LEFT from the centre in
  steelblue, female bars growing RIGHT in pink; half-width = ``AXIS_SHARE`` (17 %) of total population.
* ``canon1`` — total-only: ``s21 / 2`` mirrored on both sides in grey (sex-blind space).

`style_hash` fingerprints the renderer (source + constants) so an embedding index can refuse renders made by a
different style.  `render_style` exposes the nuisance factors (colour, gap, resolution, aspect) used by the
factorial invariance diagnostic in `embed.py`; it is not a canonical style.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np

from pyramid_explorer.paths import DATA_RENDERS, N_BINS, N_DIMS

AXIS_SHARE = 0.17                     # half-width of the canvas = 17 % of total population (corpus max 16.1 %)
MALE = (70, 130, 180)                 # steelblue, grows left
FEMALE = (238, 121, 137)              # #EE7989, grows right
TOTAL = (110, 110, 110)               # canon1 grey
BG = (255, 255, 255)
KINDS: dict[str, int] = {"canon2": 336, "canon1": 294}   # kind -> default canonical size (21 × patch px)
Rgb = tuple[int, int, int]


def _row_edges(height: int) -> np.ndarray:
    """Pixel edges of the 21 rows (top to bottom); exact ``height/21`` pitch when ``height % 21 == 0``."""
    return np.rint(np.arange(N_BINS + 1) * height / N_BINS).astype(int)


def _raster(left: np.ndarray, right: np.ndarray, height: int, width: int, colour_left: Rgb, colour_right: Rgb,
            *, gap: int = 0, axis: float = AXIS_SHARE) -> np.ndarray:
    """Draw ``left``/``right`` (21 shares each, bin 0 first) as mirrored bars; row ``r`` from the top is bin ``20-r``.

    Bar length = ``round(share / axis × width/2)`` px; ``gap`` white pixels are cut from the bottom of each row.
    """
    img = np.full((height, width, 3), BG, dtype=np.uint8)
    half = width // 2
    px_l = np.rint(np.asarray(left, dtype=np.float64) / axis * half).astype(int)
    px_r = np.rint(np.asarray(right, dtype=np.float64) / axis * half).astype(int)
    edges = _row_edges(height)
    for k in range(N_BINS):
        r = N_BINS - 1 - k
        y0, y1 = int(edges[r]), int(edges[r + 1]) - gap
        if y1 <= y0:
            continue
        img[y0:y1, half - px_l[k]:half] = colour_left
        img[y0:y1, half:half + px_r[k]] = colour_right
    return img


def _split(s42: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    v = np.asarray(s42, dtype=np.float64).reshape(-1)
    if v.shape != (N_DIMS,):
        raise ValueError(f"expected a [{N_DIMS}] share vector, got {v.shape}")
    return v[:N_BINS], v[N_BINS:]


def render_canon2(s42: np.ndarray, size: int = 336) -> np.ndarray:
    """Two-sex canonical render → uint8 ``[size, size, 3]`` (white bg, male left steelblue, female right pink)."""
    m, f = _split(s42)
    return _raster(m, f, size, size, MALE, FEMALE)


def render_canon1(s42: np.ndarray, size: int = 294) -> np.ndarray:
    """Total-only canonical render → uint8 ``[size, size, 3]``: ``s21 / 2`` mirrored both sides in grey."""
    m, f = _split(s42)
    t = (m + f) / 2.0
    return _raster(t, t, size, size, TOTAL, TOTAL)


def render_style(s42: np.ndarray, *, kind: str = "canon2", height: int = 336, width: int | None = None,
                 gap: int = 0, palette: tuple[Rgb, Rgb] | None = None) -> np.ndarray:
    """Non-canonical variant of a render (factorial invariance diagnostic): any canvas, gap, or bar colours."""
    m, f = _split(s42)
    width = height if width is None else width
    if kind == "canon2":
        left, right, cl, cr = m, f, MALE, FEMALE
    elif kind == "canon1":
        t = (m + f) / 2.0
        left, right, cl, cr = t, t, TOTAL, TOTAL
    else:
        raise ValueError(f"unknown kind {kind!r}")
    if palette is not None:
        cl, cr = palette
    return _raster(left, right, height, width, cl, cr, gap=gap)


def style_hash() -> str:
    """sha256 over the renderer source (raster + canonical functions) and its constants."""
    src = "".join(inspect.getsource(fn) for fn in (_row_edges, _raster, _split, render_canon2, render_canon1))
    consts = json.dumps({"axis": AXIS_SHARE, "male": MALE, "female": FEMALE, "total": TOTAL, "bg": BG,
                         "kinds": KINDS, "n_bins": N_BINS}, sort_keys=True)
    return hashlib.sha256((src + consts).encode()).hexdigest()


def render_path(kind: str, size: int) -> Path:
    """``data/renders/{kind}_{size}.npy`` (its sidecar ``.meta.json`` carries the style hash)."""
    return DATA_RENDERS / f"{kind}_{size}.npy"


def render_corpus(s42: np.ndarray, kind: str, size: int | None = None, out: Path | None = None) -> np.ndarray:
    """Render every row → uint8 ``[n, size, size, 3]`` written incrementally to ``out`` (memmap) with a meta sidecar.

    ``size`` defaults to the kind's canonical size and must be a multiple of 21 (one exact row per age bin).
    Returns the on-disk array opened read-only (12 GB for canon2 @ 336 — never materialise it twice).
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {list(KINDS)}, got {kind!r}")
    size = KINDS[kind] if size is None else int(size)
    if size % N_BINS:
        raise ValueError(f"canonical size must be a multiple of {N_BINS}, got {size}")
    fn = render_canon2 if kind == "canon2" else render_canon1
    X = np.asarray(s42, dtype=np.float64)
    out = render_path(kind, size) if out is None else Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    arr = np.lib.format.open_memmap(out, mode="w+", dtype=np.uint8, shape=(len(X), size, size, 3))
    for i in range(len(X)):
        arr[i] = fn(X[i], size)
    arr.flush()
    del arr
    meta = {"kind": kind, "size": size, "n": int(len(X)), "style_hash": style_hash(),
            "s42_sha256": hashlib.sha256(np.ascontiguousarray(X).tobytes()).hexdigest()}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1))
    return np.load(out, mmap_mode="r")
