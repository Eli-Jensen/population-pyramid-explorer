"""Fetch the WPP 2024 raw inputs listed in pipeline/manifest.json into data/raw/wpp2024/.

    uv run scripts/fetch_data.py --from ~/Projects/pyramid-econ/data/raw/wpp2024

Files present in ``--from DIR`` are copied (no symlinks); the rest are downloaded. Every file is
sha256-verified against the manifest (a ``null`` sha256 is recorded on first fetch, a mismatch
fails). The Togo update CSVs are extracted from the zip and WPP2024_F01_LOCATIONS.xlsx sheet DB
is converted to the committed ``pipeline/locations.parquet``. Idempotent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer.data.base import download  # noqa: E402
from pyramid_explorer.data.wpp import RAW_DIR, locations_from_xlsx  # noqa: E402
from pyramid_explorer.paths import PIPELINE, REPO_ROOT  # noqa: E402

MANIFEST = PIPELINE / "manifest.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, entry: dict, name: str) -> None:
    digest, size = sha256_of(path), path.stat().st_size
    if entry.get("sha256") and entry["sha256"] != digest:
        raise SystemExit(f"{name}: sha256 mismatch\n  manifest {entry['sha256']}\n  on disk  {digest}")
    if entry.get("bytes") and entry["bytes"] != size:
        raise SystemExit(f"{name}: size mismatch (manifest {entry['bytes']}, on disk {size})")
    entry["sha256"], entry["bytes"] = digest, size


def fetch(name: str, entry: dict, src_dir: Path | None, *, force: bool = False) -> Path:
    dest = RAW_DIR / name
    if dest.exists() and not force:
        print(f"  exists   {name}")
    elif src_dir and (src_dir / name).exists():
        print(f"  copy     {name}  <- {src_dir}")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_dir / name, dest)
    else:
        print(f"  download {name}  <- {entry['url']}")
        download(entry["url"], dest, skip_existing=not force)
    verify(dest, entry, name)
    entry["fetched_at"] = entry.get("fetched_at") or date.today().isoformat()
    return dest


def postprocess(name: str, entry: dict, path: Path) -> None:
    for member in entry.get("extract", []):
        with zipfile.ZipFile(path) as z:
            z.extract(member, RAW_DIR)
        print(f"  extract  {member}")
    if entry.get("convert_to"):
        out = REPO_ROOT / entry["convert_to"]
        df = locations_from_xlsx(path)
        df.to_parquet(out, index=False)
        print(f"  convert  {name} sheet DB -> {out.relative_to(REPO_ROOT)} ({len(df)} rows, {out.stat().st_size} B)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="src", type=Path, default=None, help="directory holding already-downloaded files")
    ap.add_argument("--force", action="store_true", help="re-fetch even if present")
    args = ap.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text())
    print(f"fetch_data: {len(manifest['files'])} files -> {RAW_DIR}")
    for name, entry in manifest["files"].items():
        path = fetch(name, entry, args.src, force=args.force)
        postprocess(name, entry, path)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print("manifest updated:", MANIFEST.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
