"""Read-only SQL against data/processed/explorer.duckdb; prints a frame.

    uv run scripts/sql.py "SELECT count(*) FROM pyramid"
    make sql Q="SELECT * FROM entity_years LIMIT 5"
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer import db  # noqa: E402


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    query = " ".join(argv)
    with db.connect(read_only=True) as con:
        frame = con.execute(query).df()
    with pd.option_context("display.max_rows", 200, "display.max_columns", 50, "display.width", 200):
        print(frame.to_string(index=False) if len(frame) else "(no rows)")


if __name__ == "__main__":
    main(sys.argv[1:])
