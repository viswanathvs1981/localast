"""SQLite helpers for LocalAST's fully offline storage engine."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from ..config import LocalConfig, DEFAULT_CONFIG


def _configure_connection(connection: sqlite3.Connection) -> None:
    """Apply pragmas that improve local developer experience.

    WAL mode keeps concurrent readers responsive while incremental indexing is
    running. The ``foreign_keys`` pragma ensures data integrity even though we
    primarily rely on application-level orchestration.
    """

    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA foreign_keys=ON;")


def get_connection(config: LocalConfig | None = None) -> sqlite3.Connection:
    """Create a SQLite connection scoped to the configured database path."""

    active_config = config or DEFAULT_CONFIG
    db_path = active_config.resolved_database_path()
    connection = sqlite3.connect(db_path)
    _configure_connection(connection)
    return connection


@contextmanager
def temp_connection(schema_sql: str) -> Iterator[sqlite3.Connection]:
    """Yield an in-memory SQLite connection loaded with ``schema_sql``.

    Tests use this helper to validate migrations without touching files on disk.
    """

    connection = sqlite3.connect(":memory:")
    try:
        _configure_connection(connection)
        connection.executescript(schema_sql)
        yield connection
    finally:
        connection.close()
