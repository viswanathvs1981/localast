"""Utilities for applying the bundled SQLite schema."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sqlite3


SCHEMA_PATH = Path(__file__).resolve().parents[3] / "db" / "schema.sql"


@lru_cache(maxsize=1)
def _load_schema() -> str:
    """Return the contents of ``db/schema.sql``.

    The schema is cached because multiple commands may request it within a
    single CLI invocation. Caching avoids repeated disk IO without introducing
    any global mutable state.
    """

    return SCHEMA_PATH.read_text(encoding="utf-8")


def apply_schema(connection: sqlite3.Connection) -> None:
    """Ensure that the database ``connection`` matches the project schema."""

    connection.executescript(_load_schema())
    connection.commit()

