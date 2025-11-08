"""Initialise the LocalAST SQLite database locally."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from localast.storage.schema import apply_schema


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path.home() / ".localast" / "localast.db",
        help="Path to the SQLite database that should be created/updated.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(args.database)
    try:
        apply_schema(connection)
    finally:
        connection.close()
    print(f"Initialised local database at {args.database}")


if __name__ == "__main__":
    main()
