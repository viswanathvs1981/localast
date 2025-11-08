"""Command line utilities for working with LocalAST data locally."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable

from .config import LocalConfig
from .docs import ingest_documents
from .indexer.pipeline import index_code_paths
from .storage.database import get_connection
from .storage.schema import apply_schema


def _resolve_config(database: Path | None) -> LocalConfig:
    config = LocalConfig()
    if database is not None:
        config.database_path = database
    return config


def _ensure_connection(config: LocalConfig) -> sqlite3.Connection:
    connection = get_connection(config)
    apply_schema(connection)
    return connection


def _index_code(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    try:
        summary = index_code_paths(connection, args.paths, reindex=args.reindex)
    finally:
        connection.close()
    print(
        f"Indexed {summary['files']} files and {summary['symbols']} symbols into"
        f" {config.resolved_database_path()}"
    )


def _index_docs(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    try:
        summary = ingest_documents(
            connection,
            args.paths,
            repo_root=args.repo_root.resolve(),
            index_kind=args.index_kind,
        )
    finally:
        connection.close()
    print(
        f"Indexed {summary['documents']} documents into"
        f" {config.resolved_database_path()}"
    )


def _repo_info(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    try:
        cursor = connection.cursor()
        files = cursor.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols = cursor.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        documents = cursor.execute("SELECT COUNT(*) FROM blob WHERE kind = 'doc'").fetchone()[0]
        edges = cursor.execute("SELECT COUNT(*) FROM edges WHERE etype = 'DOCS'").fetchone()[0]
    finally:
        connection.close()

    print("Repository summary:")
    print(f"  Files indexed      : {files}")
    print(f"  Symbols extracted  : {symbols}")
    print(f"  Documents ingested : {documents}")
    print(f"  Doc ↔ Code links   : {edges}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        help="Path to the SQLite database (defaults to ~/.localast/localast.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index code or documentation")
    index_sub = index_parser.add_subparsers(dest="index_command", required=True)

    code_parser = index_sub.add_parser("code", help="Index Python source files")
    code_parser.add_argument("paths", nargs="+", type=Path, help="Files or directories")
    code_parser.add_argument(
        "--reindex",
        action="store_true",
        help="Drop existing symbols for the provided files before indexing",
    )
    code_parser.set_defaults(func=_index_code)

    docs_parser = index_sub.add_parser("docs", help="Index documentation folders")
    docs_parser.add_argument("paths", nargs="+", type=Path, help="Documentation paths")
    docs_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root used when resolving code references",
    )
    docs_parser.add_argument(
        "--index-kind",
        default="documentation",
        help="Identifier stored alongside generated embeddings",
    )
    docs_parser.set_defaults(func=_index_docs)

    repo_parser = subparsers.add_parser("repo", help="Inspect indexed repository data")
    repo_sub = repo_parser.add_subparsers(dest="repo_command", required=True)

    info_parser = repo_sub.add_parser("info", help="Display aggregate statistics")
    info_parser.set_defaults(func=_repo_info)

    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

