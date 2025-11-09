"""Incremental indexing helpers for local development."""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path
from typing import Iterable, List

from ..ast.parser import parse_symbols, detect_language, extract_python_imports
from ..embeddings.engine import embedding_to_bytes, get_engine
from ..config_parser import parse_config_file, detect_config_format


def _iter_source_files(paths: Iterable[Path]) -> Iterable[Path]:
    """Iterate over all supported source files."""
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            # Walk directory and find all supported files
            for file_path in path.rglob("*"):
                if file_path.is_file() and detect_language(file_path):
                    yield file_path
        elif path.is_file():
            yield path


def _detect_language(path: Path) -> str | None:
    """Detect language - delegates to parser module."""
    return detect_language(path)


def _upsert_file(
    cursor: sqlite3.Cursor,
    repo_id: int | None,
    path: Path,
    lang: str | None,
    file_hash: str,
    module_name: str | None,
) -> tuple[int, bool, str | None]:
    if repo_id is not None:
        existing = cursor.execute(
            "SELECT id, hash FROM files WHERE repo_id = ? AND path = ?",
            (repo_id, str(path)),
        ).fetchone()
    else:
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
        "INSERT INTO files (repo_id, path, lang, hash, modname) VALUES (?, ?, ?, ?, ?)",
        (repo_id, str(path), lang, file_hash, module_name),
    )
    return int(cursor.lastrowid), False, None


def index_code_paths(
    connection: sqlite3.Connection,
    paths: Iterable[Path],
    *,
    repo_id: int | None = None,
    reindex: bool = False,
    embed: bool = False,
) -> dict[str, int]:
    """Index Python source files into the local SQLite database.
    
    Parameters
    ----------
    connection:
        Database connection
    paths:
        Files or directories to index
    repo_id:
        Repository ID (for multi-repo support)
    reindex:
        Force reindexing even if files haven't changed
    embed:
        Generate embeddings for symbols
    
    Returns
    -------
    Dictionary with 'files' and 'symbols' counts
    """

    cursor = connection.cursor()
    indexed_files = 0
    indexed_symbols = 0
    
    # Initialize embedding engine if needed
    engine = None
    if embed:
        try:
            engine = get_engine()
        except RuntimeError:
            print("  Warning: sentence-transformers not available, skipping embeddings")
            embed = False
    
    for file_path in _iter_source_files(paths):
        # File iteration already filters for supported languages
        try:
            file_bytes = file_path.read_bytes()
        except OSError:
            continue

        lang = _detect_language(file_path)
        module_name = file_path.stem
        file_hash = hashlib.sha1(file_bytes).hexdigest()
        file_id, existed, previous_hash = _upsert_file(
            cursor, repo_id, file_path.resolve(), lang, file_hash, module_name
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
        symbol_map = {}  # Map (name, parent_name) -> symbol_id for resolving parent_id
        
        # First pass: insert all symbols
        for symbol in symbols:
            fqn = symbol.fqn if symbol.fqn else f"{module_name}.{symbol.name}"
            
            # Find parent_id if this is a nested symbol
            parent_id = None
            if symbol.parent_name:
                parent_key = (symbol.parent_name, None)  # Look for top-level parent first
                if parent_key in symbol_map:
                    parent_id = symbol_map[parent_key]
            
            cursor.execute(
                """INSERT INTO symbols (kind, name, fqn, file_id, parent_id, 
                                       start_line, end_line, sig, doc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol.kind,
                    symbol.name,
                    fqn,
                    file_id,
                    parent_id,
                    symbol.start_line,
                    symbol.end_line,
                    symbol.signature,
                    symbol.docstring,
                ),
            )
            symbol_id = int(cursor.lastrowid)
            symbol_rows.append((symbol_id, symbol.name, fqn, symbol.docstring or ""))
            
            # Store in map for parent resolution
            symbol_map[(symbol.name, symbol.parent_name)] = symbol_id
            
            # Store call relationships as edges
            for called_func in symbol.calls:
                # Try to find the called function in our symbol table
                called_symbol = cursor.execute(
                    "SELECT id FROM symbols WHERE name = ? AND file_id = ?",
                    (called_func, file_id),
                ).fetchone()
                
                if called_symbol:
                    called_id = called_symbol[0]
                    # Insert CALLS edge
                    cursor.execute(
                        "INSERT INTO edges (src, etype, dst) VALUES (?, ?, ?)",
                        (symbol_id, "CALLS", called_id),
                    )

        # Add to full-text search
        for symbol_id, token, _, _ in symbol_rows:
            cursor.execute(
                "INSERT INTO ident_fts (token, symbol_id) VALUES (?, ?)",
                (token, symbol_id),
            )
        
        # Store imports as edges
        if lang == "python":
            try:
                file_imports = extract_python_imports(file_path)
                for imported_module in file_imports.imports:
                    # Find the imported file if it's in our database
                    imported_file = cursor.execute(
                        """SELECT id FROM files WHERE modname = ? OR path LIKE ?""",
                        (imported_module, f"%{imported_module.replace('.', '/')}%"),
                    ).fetchone()
                    
                    if imported_file:
                        imported_file_id = imported_file[0]
                        # Insert IMPORTS edge (file -> file)
                        cursor.execute(
                            "INSERT INTO edges (src, etype, dst) VALUES (?, ?, ?)",
                            (file_id, "IMPORTS", imported_file_id),
                        )
            except Exception as e:
                print(f"  Warning: Failed to extract imports from {file_path}: {e}")
        
        # Generate embeddings if requested
        if embed and engine and symbol_rows:
            try:
                for symbol_id, symbol_name, fqn, docstring in symbol_rows:
                    # Use docstring if available for better embeddings
                    embedding = engine.embed_code_symbol(symbol_name, fqn, docstring)
                    vec_bytes = embedding_to_bytes(embedding)
                    
                    cursor.execute(
                        """INSERT INTO emb (blob_id, dim, vec, index_kind, repo_id, 
                                           file_id, symbol_id, fqn, start_line, end_line)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            None,
                            engine.dim,
                            sqlite3.Binary(vec_bytes),
                            "code",
                            repo_id,
                            file_id,
                            symbol_id,
                            fqn,
                            None,
                            None,
                        ),
                    )
            except Exception as e:
                print(f"  Warning: Failed to generate embeddings for {file_path}: {e}")

        indexed_files += 1
        indexed_symbols += len(symbol_rows)

    connection.commit()
    return {"files": indexed_files, "symbols": indexed_symbols}


def index_config_files(
    connection: sqlite3.Connection,
    paths: Iterable[Path],
    *,
    repo_id: int | None = None,
) -> dict[str, int]:
    """Index configuration files (JSON, YAML, XML) into the database.
    
    Parameters
    ----------
    connection:
        Database connection
    paths:
        Files or directories to scan for config files
    repo_id:
        Repository ID (for multi-repo support)
    
    Returns
    -------
    Dictionary with 'config_files' and 'config_nodes' counts
    """
    cursor = connection.cursor()
    indexed_configs = 0
    indexed_nodes = 0
    
    def _iter_config_files(paths: Iterable[Path]) -> Iterable[Path]:
        """Iterate over all config files."""
        for raw_path in paths:
            path = raw_path.resolve()
            if path.is_dir():
                for file_path in path.rglob("*"):
                    if file_path.is_file() and detect_config_format(file_path):
                        yield file_path
            elif path.is_file() and detect_config_format(path):
                yield path
    
    for config_path in _iter_config_files(paths):
        try:
            config_file = parse_config_file(config_path)
            if not config_file:
                continue
            
            # Get or create file_id
            if repo_id is not None:
                file_row = cursor.execute(
                    "SELECT id FROM files WHERE repo_id = ? AND path = ?",
                    (repo_id, str(config_path)),
                ).fetchone()
            else:
                file_row = cursor.execute(
                    "SELECT id FROM files WHERE path = ?",
                    (str(config_path),)
                ).fetchone()
            
            if not file_row:
                # Insert as a file entry
                cursor.execute(
                    "INSERT INTO files (repo_id, path, lang, hash, modname) VALUES (?, ?, ?, ?, ?)",
                    (repo_id, str(config_path), config_file.format, config_file.hash, None),
                )
                file_id = int(cursor.lastrowid)
            else:
                file_id = file_row[0]
            
            # Check if config already exists
            existing_config = cursor.execute(
                "SELECT id, hash FROM config_files WHERE repo_id = ? AND path = ?" if repo_id 
                else "SELECT id, hash FROM config_files WHERE path = ?",
                (repo_id, str(config_path)) if repo_id else (str(config_path),),
            ).fetchone()
            
            if existing_config:
                config_id = existing_config[0]
                old_hash = existing_config[1]
                
                # Skip if unchanged
                if old_hash == config_file.hash:
                    continue
                
                # Delete old nodes
                cursor.execute("DELETE FROM config_nodes WHERE config_id = ?", (config_id,))
                
                # Update config file
                cursor.execute(
                    """UPDATE config_files SET format = ?, content_json = ?, hash = ?,
                       indexed_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (config_file.format, config_file.raw_content, config_file.hash, config_id),
                )
            else:
                # Insert new config file
                cursor.execute(
                    """INSERT INTO config_files (repo_id, file_id, path, format, content_json, hash)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (repo_id, file_id, str(config_path), config_file.format, 
                     config_file.raw_content, config_file.hash),
                )
                config_id = int(cursor.lastrowid)
            
            # Insert config nodes
            def insert_nodes(nodes: list, parent_id: int | None = None):
                """Recursively insert config nodes."""
                node_count = 0
                for node in nodes:
                    cursor.execute(
                        """INSERT INTO config_nodes (config_id, parent_id, key_path, key, 
                                                     value, value_type, line_number)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (config_id, parent_id, node.key_path, node.key, 
                         str(node.value) if node.value is not None else None,
                         node.value_type, node.line_number),
                    )
                    node_id = int(cursor.lastrowid)
                    node_count += 1
                    
                    # Insert children
                    if node.children:
                        node_count += insert_nodes(node.children, node_id)
                
                return node_count
            
            nodes_count = insert_nodes(config_file.root_nodes)
            indexed_configs += 1
            indexed_nodes += nodes_count
            
        except Exception as e:
            print(f"  Warning: Failed to index config file {config_path}: {e}")
            continue
    
    connection.commit()
    return {"config_files": indexed_configs, "config_nodes": indexed_nodes}


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
