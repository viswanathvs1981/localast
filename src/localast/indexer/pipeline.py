"""Incremental indexing helpers for local development."""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path
from typing import Iterable, List

from ..ast.parser import parse_symbols


def _iter_source_files(paths: Iterable[Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            yield from path.rglob("*.py")
        elif path.is_file():
            yield path


def _detect_language(path: Path) -> str | None:
    if path.suffix == ".py":
        return "python"
    return None


def _upsert_file(
    cursor: sqlite3.Cursor,
    path: Path,
    lang: str | None,
    file_hash: str,
    module_name: str | None,
) -> tuple[int, bool, str | None]:
    existing = cursor.execute(
        "SELECT id, hash FROM files WHERE path = ?", (str(path),)
    ).fetchone()
    if existing:
        file_id = int(existing[0])
        previous_hash = existing[1]
        cursor.execute(
            "UPDATE files SET lang = ?, hash = ?, modname = ? WHERE id = ?",
            (lang, file_hash, module_name, file_id),
        )
        return file_id, True, previous_hash

    cursor.execute(
        "INSERT INTO files (path, lang, hash, modname) VALUES (?, ?, ?, ?)",
        (str(path), lang, file_hash, module_name),
    )
    return int(cursor.lastrowid), False, None


def index_code_paths(
    connection: sqlite3.Connection,
    paths: Iterable[Path],
    *,
    reindex: bool = False,
) -> dict[str, int]:
    """Index Python source files into the local SQLite database."""

    cursor = connection.cursor()
    indexed_files = 0
    indexed_symbols = 0
    for file_path in _iter_source_files(paths):
        if file_path.suffix != ".py":
            continue

        try:
            file_bytes = file_path.read_bytes()
        except OSError:
            continue

        lang = _detect_language(file_path)
        module_name = file_path.stem
        file_hash = hashlib.sha1(file_bytes).hexdigest()
        file_id, existed, previous_hash = _upsert_file(
            cursor, file_path.resolve(), lang, file_hash, module_name
        )

        if existed and not reindex and previous_hash == file_hash:
            continue

        cursor.execute(
            "DELETE FROM ident_fts WHERE symbol_id IN (SELECT id FROM symbols WHERE file_id = ?)",
            (file_id,),
        )
        cursor.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))

        symbols = parse_symbols([file_path])
        symbol_rows: List[tuple] = []
        for symbol in symbols:
            fqn = f"{module_name}.{symbol.name}"
            cursor.execute(
                "INSERT INTO symbols (kind, name, fqn, file_id, start_line, end_line)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    symbol.kind,
                    symbol.name,
                    fqn,
                    file_id,
                    symbol.start_line,
                    symbol.end_line,
                ),
            )
            symbol_id = int(cursor.lastrowid)
            symbol_rows.append((symbol_id, symbol.name))

        for symbol_id, token in symbol_rows:
            cursor.execute(
                "INSERT INTO ident_fts (token, symbol_id) VALUES (?, ?)",
                (token, symbol_id),
            )

        indexed_files += 1
        indexed_symbols += len(symbol_rows)

    connection.commit()
    return {"files": indexed_files, "symbols": indexed_symbols}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to hand to the local parser stubs.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    raise SystemExit(
        "The CLI entry point has moved to 'localast.cli'. "
        "Run 'localast index code ...' instead."
    )


if __name__ == "__main__":
    main()
