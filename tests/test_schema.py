"""Smoke tests for the local SQLite schema."""

from __future__ import annotations

from pathlib import Path

from localast.storage.database import temp_connection

SCHEMA_SQL = (Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text(encoding="utf-8")


EXPECTED_TABLES = {
    "files",
    "symbols",
    "edges",
    "blob",
    "version",
    "change_event",
    "emb",
    "prompt_template",
    "prompt_experiment",
    "golden_task",
    "review_policy",
    "review_run",
    "review_finding",
}


EXPECTED_VIRTUAL_TABLES = {
    "ident_fts",
    "doc_fts",
}


def test_schema_tables_exist() -> None:
    with temp_connection(SCHEMA_SQL) as connection:
        rows = connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    tables = {name for name, kind in rows if kind == "table"}
    assert EXPECTED_TABLES.issubset(tables)


def test_schema_virtual_tables_exist() -> None:
    with temp_connection(SCHEMA_SQL) as connection:
        rows = connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    tables = {name for name, _ in rows}
    assert EXPECTED_VIRTUAL_TABLES.issubset(tables)
