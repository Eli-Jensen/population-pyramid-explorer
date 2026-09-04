"""Bookkeeping for economic raw files: data/raw/econ/ + pipeline/econ_manifest.json.

Every econ loader's ``fetch()`` lands a file under ``data/raw/econ/`` and calls
:func:`record` so the manifest carries ``sha256``, ``bytes``, ``fetched_at`` and
licence notes per file.  ``fetched_at`` is the only wall-clock value and is kept
unchanged while the file's sha256 is unchanged (idempotent re-runs).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from pyramid_explorer.paths import DATA_RAW, PIPELINE

RAW_ECON = DATA_RAW / "econ"
MANIFEST = PIPELINE / "econ_manifest.json"


def sha256_of(path: Path) -> str:
    """Hex sha256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path = MANIFEST) -> dict:
    """The manifest as a dict keyed by entry id (empty when absent)."""
    return json.loads(path.read_text()) if path.exists() else {}


def record(entry_id: str, file: Path, *, url: str, source: str, licence: str,
           redistributable: bool, notes: str = "", path: Path = MANIFEST) -> dict:
    """Upsert one manifest entry for ``file``; refresh ``fetched_at`` only on a new sha256."""
    manifest = load_manifest(path)
    digest = sha256_of(file)
    old = manifest.get(entry_id, {})
    fetched_at = old.get("fetched_at") if old.get("sha256") == digest else None
    manifest[entry_id] = {
        "source": source,
        "file": str(file.relative_to(DATA_RAW)),
        "url": url,
        "sha256": digest,
        "bytes": file.stat().st_size,
        "fetched_at": fetched_at or dt.date.today().isoformat(),
        "licence": licence,
        "redistributable": redistributable,
        "notes": notes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")
    return manifest[entry_id]


def verify(entry_id: str, path: Path = MANIFEST) -> bool:
    """True when the manifest entry exists and its file's sha256 still matches."""
    entry = load_manifest(path).get(entry_id)
    if not entry:
        return False
    file = DATA_RAW / entry["file"]
    return file.exists() and sha256_of(file) == entry["sha256"]
