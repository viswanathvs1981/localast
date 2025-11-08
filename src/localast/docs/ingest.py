"""Lightweight documentation ingestion for local experiments."""

from __future__ import annotations

import re
import sqlite3
from array import array
from pathlib import Path
from typing import Iterable


DOCUMENT_EXTENSIONS = {".md", ".rst", ".txt"}
_CODE_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9_/.-]+\.[A-Za-z0-9_]+")


def _iter_documents(paths: Iterable[Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in DOCUMENT_EXTENSIONS:
                    yield candidate
        elif path.is_file() and path.suffix.lower() in DOCUMENT_EXTENSIONS:
            yield path


def _compute_vector(text: str) -> bytes:
    words = re.findall(r"\w+", text.lower())
    total_words = float(len(words))
    unique_words = float(len(set(words)))
    line_count = float(text.count("\n") + 1)
    char_count = float(len(text))
    vector = array("f", [total_words, unique_words, line_count, char_count])
    return vector.tobytes()


def _load_file_index(cursor: sqlite3.Cursor) -> dict[str, int]:
    rows = cursor.execute("SELECT id, path FROM files").fetchall()
    return {str(Path(path).resolve()): int(file_id) for file_id, path in rows}


def _resolve_repo_paths(repo_root: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for candidate in repo_root.rglob("*"):
        if candidate.is_file():
            mapping[candidate.name] = candidate.resolve()
    return mapping


def ingest_documents(
    connection: sqlite3.Connection,
    doc_paths: Iterable[Path],
    *,
    repo_root: Path,
    index_kind: str = "documentation",
) -> dict[str, int]:
    """Load documentation files into ``blob``, ``doc_fts``, and ``emb`` tables."""

    cursor = connection.cursor()
    existing_files = _load_file_index(cursor)
    indexed_docs = 0

    name_lookup = _resolve_repo_paths(repo_root)

    for doc_path in _iter_documents(doc_paths):
        try:
            text = doc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        cursor.execute(
            "INSERT INTO blob (kind, text, lang, path) VALUES (?, ?, ?, ?)",
            ("doc", text, doc_path.suffix.lstrip("."), str(doc_path.resolve())),
        )
        blob_id = int(cursor.lastrowid)

        cursor.execute(
            "INSERT INTO doc_fts (rowid, text, symbol_id) VALUES (?, ?, ?)",
            (blob_id, text, None),
        )

        vector = _compute_vector(text)
        cursor.execute(
            "INSERT INTO emb (blob_id, dim, vec, index_kind, file_id, fqn, start_line, end_line)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (blob_id, 4, sqlite3.Binary(vector), index_kind, None, None, None, None),
        )

        matches = set(_CODE_REFERENCE_PATTERN.findall(text))
        for match in matches:
            candidate_path = Path(match)
            if not candidate_path.is_absolute():
                resolved = (repo_root / candidate_path).resolve()
            else:
                resolved = candidate_path.resolve()

            file_id = existing_files.get(str(resolved))
            if file_id is None:
                fallback = name_lookup.get(candidate_path.name)
                if fallback is None:
                    continue
                file_id = existing_files.get(str(fallback))
                if file_id is None:
                    continue
            if file_id is not None:
                cursor.execute(
                    "INSERT INTO edges (src, etype, dst) VALUES (?, ?, ?)",
                    (blob_id, "DOCS", file_id),
                )

        indexed_docs += 1

    connection.commit()
    return {"documents": indexed_docs}

