"""Git history tools for MCP server."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..server import LocalASTServer


def get_changes_between_commits(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get file changes between two commits.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'repo', 'from_commit', 'to_commit'

    Returns
    -------
    JSON string with changes
    """
    repo_name = args.get("repo")
    from_commit = args.get("from_commit")
    to_commit = args.get("to_commit")
    
    if not all([repo_name, from_commit, to_commit]):
        return json.dumps({"error": "repo, from_commit, and to_commit required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Get repo_id
    row = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (repo_name,)
    ).fetchone()
    
    if not row:
        return json.dumps({"error": f"Repository '{repo_name}' not found"}, indent=2)
    
    repo_id = row[0]
    
    # Get changes
    rows = cursor.execute(
        """SELECT commit_id, path, kind, hunk, summary, ts
           FROM change_event
           WHERE repo_id = ? AND commit_id IN (
               SELECT commit_id FROM version
               WHERE repo_id = ? AND ts BETWEEN (
                   SELECT ts FROM version WHERE repo_id = ? AND commit_id = ?
               ) AND (
                   SELECT ts FROM version WHERE repo_id = ? AND commit_id = ?
               )
           )
           ORDER BY ts DESC""",
        (repo_id, repo_id, repo_id, from_commit, repo_id, to_commit),
    ).fetchall()
    
    changes = []
    for row in rows:
        changes.append({
            "commit": row[0][:8],
            "path": row[1],
            "kind": row[2],
            "diff_preview": row[3][:500] if row[3] else "",
            "message": row[4],
            "timestamp": row[5],
        })
    
    return json.dumps({"changes": changes, "count": len(changes)}, indent=2)


def find_when_introduced(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Find when a symbol or file was introduced.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'repo' and ('symbol_fqn' or 'file_path')

    Returns
    -------
    JSON string with introduction details
    """
    repo_name = args.get("repo")
    symbol_fqn = args.get("symbol_fqn")
    file_path = args.get("file_path")
    
    if not repo_name:
        return json.dumps({"error": "repo required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Get repo_id
    row = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (repo_name,)
    ).fetchone()
    
    if not row:
        return json.dumps({"error": f"Repository '{repo_name}' not found"}, indent=2)
    
    repo_id = row[0]
    
    if symbol_fqn:
        # Find when symbol was introduced
        row = cursor.execute(
            """SELECT s.name, f.path, ce.commit_id, ce.ts, ce.summary
               FROM symbols s
               JOIN files f ON s.file_id = f.id
               LEFT JOIN change_event ce ON ce.path = f.path AND ce.kind = 'added' AND ce.repo_id = ?
               WHERE s.fqn = ? AND f.repo_id = ?
               ORDER BY ce.ts ASC
               LIMIT 1""",
            (repo_id, symbol_fqn, repo_id),
        ).fetchone()
        
        if row:
            return json.dumps({
                "symbol": row[0],
                "file": row[1],
                "introduced_in_commit": row[2][:8] if row[2] else "unknown",
                "timestamp": row[3],
                "commit_message": row[4],
            }, indent=2)
    
    elif file_path:
        # Find when file was introduced
        row = cursor.execute(
            """SELECT path, commit_id, ts, summary
               FROM change_event
               WHERE repo_id = ? AND path LIKE ? AND kind = 'added'
               ORDER BY ts ASC
               LIMIT 1""",
            (repo_id, f"%{file_path}%"),
        ).fetchone()
        
        if row:
            return json.dumps({
                "file": row[0],
                "introduced_in_commit": row[1][:8],
                "timestamp": row[2],
                "commit_message": row[3],
            }, indent=2)
    
    return json.dumps({"error": "Not found"}, indent=2)


def get_recent_changes(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get recent commits affecting a path or symbol.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'repo' and optional 'path', 'fqn', 'limit'

    Returns
    -------
    JSON string with recent changes
    """
    repo_name = args.get("repo")
    path = args.get("path")
    fqn = args.get("fqn")
    limit = args.get("limit", 10)
    
    if not repo_name:
        return json.dumps({"error": "repo required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Get repo_id
    row = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (repo_name,)
    ).fetchone()
    
    if not row:
        return json.dumps({"error": f"Repository '{repo_name}' not found"}, indent=2)
    
    repo_id = row[0]
    
    # Build query based on what's provided
    if fqn:
        # Find file containing the symbol
        file_row = cursor.execute(
            """SELECT f.path FROM symbols s
               JOIN files f ON s.file_id = f.id
               WHERE s.fqn = ? AND f.repo_id = ?""",
            (fqn, repo_id),
        ).fetchone()
        
        if file_row:
            path = file_row[0]
    
    if path:
        rows = cursor.execute(
            """SELECT commit_id, kind, hunk, summary, ts
               FROM change_event
               WHERE repo_id = ? AND path LIKE ?
               ORDER BY ts DESC
               LIMIT ?""",
            (repo_id, f"%{path}%", limit),
        ).fetchall()
    else:
        # All recent changes in repo
        rows = cursor.execute(
            """SELECT commit_id, path, kind, summary, ts
               FROM change_event
               WHERE repo_id = ?
               ORDER BY ts DESC
               LIMIT ?""",
            (repo_id, limit),
        ).fetchall()
    
    changes = []
    for row in rows:
        change = {
            "commit": row[0][:8],
            "kind": row[1] if path else row[2],
            "message": row[2] if path else row[3],
            "timestamp": row[3] if path else row[4],
        }
        if not path:
            change["path"] = row[1]
        changes.append(change)
    
    return json.dumps({"changes": changes, "count": len(changes)}, indent=2)


def get_commit_details(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get full details of a commit.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'repo' and 'commit_id'

    Returns
    -------
    JSON string with commit details
    """
    repo_name = args.get("repo")
    commit_id = args.get("commit_id")
    
    if not all([repo_name, commit_id]):
        return json.dumps({"error": "repo and commit_id required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Get repo_id
    row = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (repo_name,)
    ).fetchone()
    
    if not row:
        return json.dumps({"error": f"Repository '{repo_name}' not found"}, indent=2)
    
    repo_id = row[0]
    
    # Get commit metadata
    commit_row = cursor.execute(
        """SELECT commit_id, ts, author, message
           FROM version
           WHERE repo_id = ? AND commit_id LIKE ?
           LIMIT 1""",
        (repo_id, f"{commit_id}%"),
    ).fetchone()
    
    if not commit_row:
        return json.dumps({"error": "Commit not found"}, indent=2)
    
    full_commit_id = commit_row[0]
    
    # Get changes in this commit
    change_rows = cursor.execute(
        """SELECT path, kind, hunk
           FROM change_event
           WHERE repo_id = ? AND commit_id = ?""",
        (repo_id, full_commit_id),
    ).fetchall()
    
    changes = []
    for row in change_rows:
        changes.append({
            "path": row[0],
            "kind": row[1],
            "diff": row[2][:1000] if row[2] else "",
        })
    
    return json.dumps({
        "commit_id": full_commit_id[:8],
        "full_commit_id": full_commit_id,
        "timestamp": commit_row[1],
        "author": commit_row[2],
        "message": commit_row[3],
        "changes": changes,
        "files_changed": len(changes),
    }, indent=2)


def blame_line(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Find who last changed specific lines (simplified blame).

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'repo', 'file_path', and 'line_number'

    Returns
    -------
    JSON string with blame information
    """
    repo_name = args.get("repo")
    file_path = args.get("file_path")
    line_number = args.get("line_number")
    
    if not all([repo_name, file_path]):
        return json.dumps({"error": "repo and file_path required"}, indent=2)
    
    cursor = connection.cursor()
    
    # Get repo_id
    row = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (repo_name,)
    ).fetchone()
    
    if not row:
        return json.dumps({"error": f"Repository '{repo_name}' not found"}, indent=2)
    
    repo_id = row[0]
    
    # Find most recent change to this file
    row = cursor.execute(
        """SELECT ce.commit_id, ce.ts, ce.summary, v.author
           FROM change_event ce
           JOIN version v ON ce.commit_id = v.commit_id AND ce.repo_id = v.repo_id
           WHERE ce.repo_id = ? AND ce.path LIKE ?
           ORDER BY ce.ts DESC
           LIMIT 1""",
        (repo_id, f"%{file_path}%"),
    ).fetchone()
    
    if row:
        return json.dumps({
            "file": file_path,
            "line": line_number,
            "last_modified_commit": row[0][:8],
            "timestamp": row[1],
            "author": row[3],
            "message": row[2],
            "note": "This is a simplified blame - shows most recent change to file",
        }, indent=2)
    
    return json.dumps({"error": "No change history found"}, indent=2)


def register_tools(server: LocalASTServer) -> None:
    """Register history tools with the MCP server.

    Parameters
    ----------
    server:
        MCP server instance
    """
    server.register_tool(
        name="get_changes_between_commits",
        description="Get file changes between two commits",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "from_commit": {"type": "string", "description": "Starting commit SHA"},
                "to_commit": {"type": "string", "description": "Ending commit SHA"},
            },
            "required": ["repo", "from_commit", "to_commit"],
        },
        handler=get_changes_between_commits,
    )
    
    server.register_tool(
        name="find_when_introduced",
        description="Find when a symbol or file was introduced",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "symbol_fqn": {"type": "string", "description": "Symbol fully qualified name"},
                "file_path": {"type": "string", "description": "File path"},
            },
            "required": ["repo"],
        },
        handler=find_when_introduced,
    )
    
    server.register_tool(
        name="get_recent_changes",
        description="Get recent commits affecting a path or symbol",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "path": {"type": "string", "description": "File path (optional)"},
                "fqn": {"type": "string", "description": "Symbol FQN (optional)"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"},
            },
            "required": ["repo"],
        },
        handler=get_recent_changes,
    )
    
    server.register_tool(
        name="get_commit_details",
        description="Get full details of a commit including all changes",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "commit_id": {"type": "string", "description": "Commit SHA (can be short)"},
            },
            "required": ["repo", "commit_id"],
        },
        handler=get_commit_details,
    )
    
    server.register_tool(
        name="blame_line",
        description="Find who last changed specific lines (simplified blame)",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "file_path": {"type": "string", "description": "File path"},
                "line_number": {"type": "integer", "description": "Line number (optional)"},
            },
            "required": ["repo", "file_path"],
        },
        handler=blame_line,
    )




