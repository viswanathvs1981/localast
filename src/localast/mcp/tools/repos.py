"""Repository management tools for MCP server."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..server import LocalASTServer


def list_repositories(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """List all indexed repositories.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments (none required)

    Returns
    -------
    JSON string with repository list
    """
    cursor = connection.cursor()
    
    rows = cursor.execute(
        """SELECT id, name, path, default_branch, indexed_at, last_commit
           FROM repo
           ORDER BY name"""
    ).fetchall()
    
    repos = []
    for row in rows:
        repos.append({
            "id": row[0],
            "name": row[1],
            "path": row[2],
            "default_branch": row[3],
            "indexed_at": row[4],
            "last_commit": row[5][:8] if row[5] else None,
        })
    
    return json.dumps({"repositories": repos, "count": len(repos)}, indent=2)


def get_repo_stats(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get statistics about a repository.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'repo'

    Returns
    -------
    JSON string with repository statistics
    """
    repo_name = args.get("repo")
    
    if not repo_name:
        return json.dumps({"error": "repo required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Get repo_id and info
    row = cursor.execute(
        """SELECT id, name, path, default_branch, indexed_at, last_commit
           FROM repo WHERE name = ?""",
        (repo_name,),
    ).fetchone()
    
    if not row:
        return json.dumps({"error": f"Repository '{repo_name}' not found"}, indent=2)
    
    repo_id = row[0]
    
    # Get statistics
    files = cursor.execute(
        "SELECT COUNT(*) FROM files WHERE repo_id = ?", (repo_id,)
    ).fetchone()[0]
    
    symbols = cursor.execute(
        """SELECT COUNT(*) FROM symbols 
           WHERE file_id IN (SELECT id FROM files WHERE repo_id = ?)""",
        (repo_id,),
    ).fetchone()[0]
    
    commits = cursor.execute(
        "SELECT COUNT(DISTINCT commit_id) FROM version WHERE repo_id = ?",
        (repo_id,),
    ).fetchone()[0]
    
    changes = cursor.execute(
        "SELECT COUNT(*) FROM change_event WHERE repo_id = ?", (repo_id,)
    ).fetchone()[0]
    
    docs = cursor.execute(
        """SELECT COUNT(*) FROM blob b
           JOIN emb e ON b.blob_id = e.blob_id
           WHERE e.repo_id = ? AND b.kind = 'doc'""",
        (repo_id,),
    ).fetchone()[0]
    
    embeddings = cursor.execute(
        "SELECT COUNT(*) FROM emb WHERE repo_id = ?", (repo_id,)
    ).fetchone()[0]
    
    # Get language breakdown
    lang_rows = cursor.execute(
        """SELECT lang, COUNT(*) as count
           FROM files
           WHERE repo_id = ? AND lang IS NOT NULL
           GROUP BY lang
           ORDER BY count DESC""",
        (repo_id,),
    ).fetchall()
    
    languages = {row[0]: row[1] for row in lang_rows}
    
    # Get top-level symbols breakdown
    symbol_rows = cursor.execute(
        """SELECT kind, COUNT(*) as count
           FROM symbols s
           JOIN files f ON s.file_id = f.id
           WHERE f.repo_id = ?
           GROUP BY kind
           ORDER BY count DESC""",
        (repo_id,),
    ).fetchall()
    
    symbol_kinds = {row[0]: row[1] for row in symbol_rows}
    
    return json.dumps({
        "repository": {
            "name": row[1],
            "path": row[2],
            "default_branch": row[3],
            "indexed_at": row[4],
            "last_commit": row[5][:8] if row[5] else None,
        },
        "statistics": {
            "files": files,
            "symbols": symbols,
            "commits": commits,
            "changes": changes,
            "documents": docs,
            "embeddings": embeddings,
        },
        "languages": languages,
        "symbol_kinds": symbol_kinds,
    }, indent=2)


def search_across_repos(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Search for code across all repositories.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'query' and optional 'limit'

    Returns
    -------
    JSON string with search results grouped by repository
    """
    query = args.get("query", "")
    limit = args.get("limit", 20)
    
    if not query:
        return json.dumps({"error": "query required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Search across all repositories
    rows = cursor.execute(
        """SELECT r.name, s.id, s.name, s.fqn, s.kind, f.path, s.start_line
           FROM ident_fts i
           JOIN symbols s ON i.symbol_id = s.id
           JOIN files f ON s.file_id = f.id
           JOIN repo r ON f.repo_id = r.id
           WHERE i.token MATCH ?
           LIMIT ?""",
        (query, limit),
    ).fetchall()
    
    # Group by repository
    by_repo: Dict[str, list] = {}
    for row in rows:
        repo_name = row[0]
        if repo_name not in by_repo:
            by_repo[repo_name] = []
        
        by_repo[repo_name].append({
            "id": row[1],
            "name": row[2],
            "fqn": row[3],
            "kind": row[4],
            "file": row[5],
            "line": row[6],
        })
    
    results = []
    for repo_name, symbols in by_repo.items():
        results.append({
            "repository": repo_name,
            "symbols": symbols,
            "count": len(symbols),
        })
    
    return json.dumps({
        "results": results,
        "total_results": sum(r["count"] for r in results),
        "repositories_matched": len(results),
    }, indent=2)


def register_tools(server: LocalASTServer) -> None:
    """Register repository tools with the MCP server.

    Parameters
    ----------
    server:
        MCP server instance
    """
    server.register_tool(
        name="list_repositories",
        description="List all indexed repositories",
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=list_repositories,
    )
    
    server.register_tool(
        name="get_repo_stats",
        description="Get detailed statistics about a repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
            },
            "required": ["repo"],
        },
        handler=get_repo_stats,
    )
    
    server.register_tool(
        name="search_across_repos",
        description="Search for code across all indexed repositories",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (default: 20)"},
            },
            "required": ["query"],
        },
        handler=search_across_repos,
    )




