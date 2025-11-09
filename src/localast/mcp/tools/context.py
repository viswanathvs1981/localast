"""Context retrieval tools for MCP server."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..server import LocalASTServer


def get_symbol_info(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get detailed information about a code symbol.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'symbol_id' or 'fqn'

    Returns
    -------
    JSON string with symbol details
    """
    symbol_id = args.get("symbol_id")
    fqn = args.get("fqn")
    
    cursor = connection.cursor()
    
    if fqn and not symbol_id:
        row = cursor.execute(
            "SELECT id FROM symbols WHERE fqn = ?", (fqn,)
        ).fetchone()
        if row:
            symbol_id = row[0]
    
    if not symbol_id:
        return json.dumps({"error": "symbol_id or fqn required"}, indent=2)
    
    # Get symbol details
    row = cursor.execute(
        """SELECT s.id, s.kind, s.name, s.fqn, s.start_line, s.end_line, 
                  s.sig, s.doc, f.path, f.lang, r.name
           FROM symbols s
           JOIN files f ON s.file_id = f.id
           LEFT JOIN repo r ON f.repo_id = r.id
           WHERE s.id = ?""",
        (symbol_id,),
    ).fetchone()
    
    if not row:
        return json.dumps({"error": "Symbol not found"}, indent=2)
    
    result = {
        "id": row[0],
        "kind": row[1],
        "name": row[2],
        "fqn": row[3],
        "start_line": row[4],
        "end_line": row[5],
        "signature": row[6],
        "docstring": row[7],
        "file_path": row[8],
        "language": row[9],
        "repository": row[10],
    }
    
    return json.dumps(result, indent=2)


def get_file_context(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get file contents with line numbers.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'file_path' and optional 'start_line', 'end_line'

    Returns
    -------
    JSON string with file contents
    """
    file_path = args.get("file_path", "")
    start_line = args.get("start_line", 1)
    end_line = args.get("end_line")
    repo_name = args.get("repo")
    
    cursor = connection.cursor()
    
    # Find file in database
    if repo_name:
        row = cursor.execute(
            """SELECT f.path FROM files f
               JOIN repo r ON f.repo_id = r.id
               WHERE f.path LIKE ? AND r.name = ?""",
            (f"%{file_path}%", repo_name),
        ).fetchone()
    else:
        row = cursor.execute(
            "SELECT path FROM files WHERE path LIKE ?",
            (f"%{file_path}%",),
        ).fetchone()
    
    if not row:
        return json.dumps({"error": "File not found"}, indent=2)
    
    full_path = Path(row[0])
    
    try:
        lines = full_path.read_text(encoding="utf-8").splitlines()
        
        # Apply line range
        if end_line is None:
            end_line = len(lines)
        
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        selected_lines = lines[start_idx:end_idx]
        
        # Format with line numbers
        numbered_lines = [
            f"{i + start_line:4d} | {line}"
            for i, line in enumerate(selected_lines)
        ]
        
        return json.dumps({
            "file_path": str(full_path),
            "start_line": start_line,
            "end_line": end_idx,
            "total_lines": len(lines),
            "content": "\n".join(numbered_lines),
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {str(e)}"}, indent=2)


def get_documentation(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get documentation linked to a code entity.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'symbol_id', 'fqn', or 'file_path'

    Returns
    -------
    JSON string with linked documentation
    """
    symbol_id = args.get("symbol_id")
    fqn = args.get("fqn")
    file_path = args.get("file_path")
    
    cursor = connection.cursor()
    
    # Get symbol_id or file_id
    target_id = None
    target_type = None
    
    if fqn and not symbol_id:
        row = cursor.execute(
            "SELECT id, file_id FROM symbols WHERE fqn = ?", (fqn,)
        ).fetchone()
        if row:
            symbol_id = row[0]
            target_id = row[1]
            target_type = "file"
    elif symbol_id:
        row = cursor.execute(
            "SELECT file_id FROM symbols WHERE id = ?", (symbol_id,)
        ).fetchone()
        if row:
            target_id = row[0]
            target_type = "file"
    elif file_path:
        row = cursor.execute(
            "SELECT id FROM files WHERE path LIKE ?", (f"%{file_path}%",)
        ).fetchone()
        if row:
            target_id = row[0]
            target_type = "file"
    
    if not target_id:
        return json.dumps({"error": "Could not find target entity"}, indent=2)
    
    # Find linked documentation
    rows = cursor.execute(
        """SELECT b.blob_id, b.path, b.text, b.kind
           FROM edges e
           JOIN blob b ON e.src = b.blob_id
           WHERE e.etype = 'DOCS' AND e.dst = ?""",
        (target_id,),
    ).fetchall()
    
    docs = []
    for row in rows:
        docs.append({
            "doc_id": row[0],
            "path": row[1],
            "text": row[2],
            "kind": row[3],
        })
    
    return json.dumps({"documentation": docs, "count": len(docs)}, indent=2)


def list_symbols_in_file(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """List all symbols defined in a file.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'file_path'

    Returns
    -------
    JSON string with symbol list
    """
    file_path = args.get("file_path", "")
    repo_name = args.get("repo")
    
    cursor = connection.cursor()
    
    # Find file and its symbols
    if repo_name:
        rows = cursor.execute(
            """SELECT s.id, s.kind, s.name, s.fqn, s.start_line, s.end_line
               FROM symbols s
               JOIN files f ON s.file_id = f.id
               JOIN repo r ON f.repo_id = r.id
               WHERE f.path LIKE ? AND r.name = ?
               ORDER BY s.start_line""",
            (f"%{file_path}%", repo_name),
        ).fetchall()
    else:
        rows = cursor.execute(
            """SELECT s.id, s.kind, s.name, s.fqn, s.start_line, s.end_line
               FROM symbols s
               JOIN files f ON s.file_id = f.id
               WHERE f.path LIKE ?
               ORDER BY s.start_line""",
            (f"%{file_path}%",),
        ).fetchall()
    
    symbols = []
    for row in rows:
        symbols.append({
            "id": row[0],
            "kind": row[1],
            "name": row[2],
            "fqn": row[3],
            "start_line": row[4],
            "end_line": row[5],
        })
    
    return json.dumps({"symbols": symbols, "count": len(symbols)}, indent=2)


def get_symbol_definition(connection: sqlite3.Connection, args: Dict[str, Any]) -> str:
    """Get the exact code definition of a symbol.

    Parameters
    ----------
    connection:
        Database connection
    args:
        Tool arguments containing 'symbol_id' or 'fqn'

    Returns
    -------
    JSON string with symbol definition code
    """
    symbol_id = args.get("symbol_id")
    fqn = args.get("fqn")
    
    cursor = connection.cursor()
    
    if fqn and not symbol_id:
        row = cursor.execute(
            "SELECT id FROM symbols WHERE fqn = ?", (fqn,)
        ).fetchone()
        if row:
            symbol_id = row[0]
    
    if not symbol_id:
        return json.dumps({"error": "symbol_id or fqn required"}, indent=2)
    
    # Get symbol location
    row = cursor.execute(
        """SELECT s.name, s.fqn, s.start_line, s.end_line, f.path
           FROM symbols s
           JOIN files f ON s.file_id = f.id
           WHERE s.id = ?""",
        (symbol_id,),
    ).fetchone()
    
    if not row:
        return json.dumps({"error": "Symbol not found"}, indent=2)
    
    name, fqn, start_line, end_line, file_path = row
    
    try:
        file_path_obj = Path(file_path)
        lines = file_path_obj.read_text(encoding="utf-8").splitlines()
        
        # Extract definition
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        definition_lines = lines[start_idx:end_idx]
        
        # Format with line numbers
        numbered_lines = [
            f"{i + start_line:4d} | {line}"
            for i, line in enumerate(definition_lines)
        ]
        
        return json.dumps({
            "name": name,
            "fqn": fqn,
            "file": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "definition": "\n".join(numbered_lines),
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {str(e)}"}, indent=2)


def register_tools(server: LocalASTServer) -> None:
    """Register context tools with the MCP server.

    Parameters
    ----------
    server:
        MCP server instance
    """
    server.register_tool(
        name="get_symbol_info",
        description="Get detailed information about a code symbol",
        input_schema={
            "type": "object",
            "properties": {
                "symbol_id": {"type": "integer", "description": "Symbol ID"},
                "fqn": {"type": "string", "description": "Fully qualified name"},
            },
        },
        handler=get_symbol_info,
    )
    
    server.register_tool(
        name="get_file_context",
        description="Get file contents with optional line range",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path (can be partial)"},
                "repo": {"type": "string", "description": "Repository name (optional)"},
                "start_line": {"type": "integer", "description": "Start line (default: 1)"},
                "end_line": {"type": "integer", "description": "End line (default: end of file)"},
            },
            "required": ["file_path"],
        },
        handler=get_file_context,
    )
    
    server.register_tool(
        name="get_documentation",
        description="Get documentation linked to a code entity",
        input_schema={
            "type": "object",
            "properties": {
                "symbol_id": {"type": "integer", "description": "Symbol ID"},
                "fqn": {"type": "string", "description": "Fully qualified name"},
                "file_path": {"type": "string", "description": "File path"},
            },
        },
        handler=get_documentation,
    )
    
    server.register_tool(
        name="list_symbols_in_file",
        description="List all symbols defined in a file",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path (can be partial)"},
                "repo": {"type": "string", "description": "Repository name (optional)"},
            },
            "required": ["file_path"],
        },
        handler=list_symbols_in_file,
    )
    
    server.register_tool(
        name="get_symbol_definition",
        description="Get the exact code definition of a symbol",
        input_schema={
            "type": "object",
            "properties": {
                "symbol_id": {"type": "integer", "description": "Symbol ID"},
                "fqn": {"type": "string", "description": "Fully qualified name"},
            },
        },
        handler=get_symbol_definition,
    )




