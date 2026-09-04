"""Shared plumbing for data loaders: cache dirs, download, parquet IO."""
from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import httpx
import pandas as pd

from pyramid_explorer.paths import DATA_PROCESSED as PROCESSED, DATA_RAW as RAW, REPO_ROOT  # noqa: F401


def download(url: str, dest: Path, *, skip_existing: bool = True) -> Path:
    """Stream url to dest, skipping if already cached."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if skip_existing and dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


def read_csv_gz(path: Path, **kwargs) -> pd.DataFrame:
    with gzip.open(path, "rt") as f:
        return pd.read_csv(f, **kwargs)


def write_parquet(df: pd.DataFrame, name: str) -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / f"{name}.parquet"
    df.to_parquet(out, index=False)
    return out


def read_parquet(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / f"{name}.parquet")
