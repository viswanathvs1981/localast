"""Search tools for MCP server."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..server import LocalASTServer

from ...embeddings.index import search_code_semantic, search_docs_semantic


def search_code(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Search for code symbols by name using full-text search.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'query' and optional 'repo' and 'limit'

    Returns
    -------
    JSON string with search results
    """
    query = args.get("query", "")
    repo_name = args.get("repo")
    limit = args.get("limit", 10)
    
    cursor = connection.cursor()
    
    # Get repo_id if repo name provided
    repo_id = None
    if repo_name:
        row = cursor.execute(
            "SELECT id FROM repo WHERE name = ?", (repo_name,)
        ).fetchone()
        if row:
            repo_id = row[0]
    
    # Search using FTS
    if repo_id:
        rows = cursor.execute(
            """SELECT s.id, s.name, s.fqn, s.kind, f.path, s.start_line, s.end_line
               FROM ident_fts i
               JOIN symbols s ON i.symbol_id = s.id
               JOIN files f ON s.file_id = f.id
               WHERE i.token MATCH ? AND f.repo_id = ?
               LIMIT ?""",
            (query, repo_id, limit),
        ).fetchall()
    else:
        rows = cursor.execute(
            """SELECT s.id, s.name, s.fqn, s.kind, f.path, s.start_line, s.end_line
               FROM ident_fts i
               JOIN symbols s ON i.symbol_id = s.id
               JOIN files f ON s.file_id = f.id
               WHERE i.token MATCH ?
               LIMIT ?""",
            (query, limit),
        ).fetchall()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "name": row[1],
            "fqn": row[2],
            "kind": row[3],
            "file": row[4],
            "start_line": row[5],
            "end_line": row[6],
        })
    
    return json.dumps({"results": results, "count": len(results)}, indent=2)


def search_semantic(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Semantic search across code and documentation.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'query', optional 'repo', 'type', and 'limit'

    Returns
    -------
    JSON string with search results
    """
    query = args.get("query", "")
    repo_name = args.get("repo")
    search_type = args.get("type", "code")  # 'code' or 'docs'
    limit = args.get("limit", 10)
    
    cursor = connection.cursor()
    
    # Get repo_id if repo name provided
    repo_id = None
    if repo_name:
        row = cursor.execute(
            "SELECT id FROM repo WHERE name = ?", (repo_name,)
        ).fetchone()
        if row:
            repo_id = row[0]
    
    try:
        if search_type == "code":
            results = search_code_semantic(connection, query, repo_id, limit)
        else:
            results = search_docs_semantic(connection, query, repo_id, limit)
        
        output = []
        for result in results:
            output.append({
                "identifier": result.identifier,
                "score": round(result.score, 4),
                "file": result.file_path,
                "start_line": result.start_line,
                "end_line": result.end_line,
                "text_preview": result.text,
            })
        
        return json.dumps({"results": output, "count": len(output)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def search_documentation(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Search documentation using full-text search.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'query' and optional 'repo' and 'limit'

    Returns
    -------
    JSON string with search results
    """
    query = args.get("query", "")
    repo_name = args.get("repo")
    limit = args.get("limit", 10)
    
    cursor = connection.cursor()
    
    # Get repo_id if repo name provided
    repo_id = None
    if repo_name:
        row = cursor.execute(
            "SELECT id FROM repo WHERE name = ?", (repo_name,)
        ).fetchone()
        if row:
            repo_id = row[0]
    
    # Search using FTS
    if repo_id:
        rows = cursor.execute(
            """SELECT b.blob_id, b.path, b.text, b.kind
               FROM doc_fts d
               JOIN blob b ON d.rowid = b.blob_id
               JOIN emb e ON e.blob_id = b.blob_id
               WHERE d.text MATCH ? AND e.repo_id = ?
               LIMIT ?""",
            (query, repo_id, limit),
        ).fetchall()
    else:
        rows = cursor.execute(
            """SELECT b.blob_id, b.path, b.text, b.kind
               FROM doc_fts d
               JOIN blob b ON d.rowid = b.blob_id
               WHERE d.text MATCH ?
               LIMIT ?""",
            (query, limit),
        ).fetchall()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "path": row[1],
            "preview": row[2][:200] if row[2] else "",
            "kind": row[3],
        })
    
    return json.dumps({"results": results, "count": len(results)}, indent=2)


def find_references(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Find references to a symbol (documentation links).

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'symbol_id' or 'fqn'

    Returns
    -------
    JSON string with references
    """
    symbol_id = args.get("symbol_id")
    fqn = args.get("fqn")
    
    cursor = connection.cursor()
    
    # Get symbol_id from fqn if provided
    if fqn and not symbol_id:
        row = cursor.execute(
            "SELECT id FROM symbols WHERE fqn = ?", (fqn,)
        ).fetchone()
        if row:
            symbol_id = row[0]
    
    if not symbol_id:
        return json.dumps({"error": "symbol_id or fqn required"}, indent=2)
    
    # Find documentation references
    rows = cursor.execute(
        """SELECT b.blob_id, b.path, b.text, b.kind
           FROM edges e
           JOIN blob b ON e.src = b.blob_id
           JOIN files f ON e.dst = f.id
           WHERE e.etype = 'DOCS' AND f.id IN (
               SELECT file_id FROM symbols WHERE id = ?
           )""",
        (symbol_id,),
    ).fetchall()
    
    results = []
    for row in rows:
        results.append({
            "doc_id": row[0],
            "path": row[1],
            "preview": row[2][:200] if row[2] else "",
            "kind": row[3],
        })
    
    return json.dumps({"results": results, "count": len(results)}, indent=2)


def register_tools(server: LocalASTServer) -> None:
    """Register search tools with the MCP server.

    Parameters
    ----------
    server:
        MCP server instance
    """
    server.register_tool(
        name="search_code",
        description="Search for code symbols by name using full-text search",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "repo": {"type": "string", "description": "Repository name (optional)"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"},
            },
            "required": ["query"],
        },
        handler=search_code,
    )
    
    server.register_tool(
        name="search_semantic",
        description="Semantic search across code or documentation using embeddings",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "repo": {"type": "string", "description": "Repository name (optional)"},
                "type": {"type": "string", "enum": ["code", "docs"], "description": "Search type"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"},
            },
            "required": ["query"],
        },
        handler=search_semantic,
    )
    
    server.register_tool(
        name="search_documentation",
        description="Search documentation using full-text search",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "repo": {"type": "string", "description": "Repository name (optional)"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"},
            },
            "required": ["query"],
        },
        handler=search_documentation,
    )
    
    server.register_tool(
        name="find_references",
        description="Find documentation references to a code symbol",
        input_schema={
            "type": "object",
            "properties": {
                "symbol_id": {"type": "integer", "description": "Symbol ID"},
                "fqn": {"type": "string", "description": "Fully qualified name"},
            },
        },
        handler=find_references,
    )




