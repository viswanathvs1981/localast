"""MCP tools for hierarchical code queries (symbol trees, call graphs, dependencies)."""

import json
import sqlite3
from typing import Any, Dict, List, Optional


async def get_symbol_tree(
    conn: sqlite3.Connection,
    file_path: str,
    repo_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get hierarchical symbol tree for a file.
    
    Returns symbols organized by parent-child relationships.
    Methods are nested under their classes, nested functions under their parents.
    
    Args:
        conn: Database connection
        file_path: Path to the file
        repo_name: Optional repository name to filter by
    
    Returns:
        List of symbol trees with nested children
    """
    cursor = conn.cursor()
    
    # Build query
    if repo_name:
        query = """
            SELECT s.id, s.kind, s.name, s.fqn, s.parent_id, 
                   s.start_line, s.end_line, s.sig, s.doc
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            JOIN repo r ON f.repo_id = r.id
            WHERE f.path LIKE ? AND r.name = ?
            ORDER BY s.start_line
        """
        rows = cursor.execute(query, (f"%{file_path}%", repo_name)).fetchall()
    else:
        query = """
            SELECT s.id, s.kind, s.name, s.fqn, s.parent_id,
                   s.start_line, s.end_line, s.sig, s.doc
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE f.path LIKE ?
            ORDER BY s.start_line
        """
        rows = cursor.execute(query, (f"%{file_path}%",)).fetchall()
    
    # Build symbol map
    symbols = {}
    for row in rows:
        symbol_id, kind, name, fqn, parent_id, start_line, end_line, sig, doc = row
        symbols[symbol_id] = {
            "id": symbol_id,
            "kind": kind,
            "name": name,
            "fqn": fqn,
            "parent_id": parent_id,
            "start_line": start_line,
            "end_line": end_line,
            "signature": sig,
            "docstring": doc,
            "children": [],
        }
    
    # Build tree structure
    tree = []
    for symbol_id, symbol in symbols.items():
        if symbol["parent_id"] is None:
            tree.append(symbol)
        else:
            parent = symbols.get(symbol["parent_id"])
            if parent:
                parent["children"].append(symbol)
    
    return tree


async def get_call_graph(
    conn: sqlite3.Connection,
    symbol_name: str,
    repo_name: Optional[str] = None,
    direction: str = "forward",
) -> Dict[str, Any]:
    """Get call graph for a symbol.
    
    Args:
        conn: Database connection
        symbol_name: Name of the function/method
        repo_name: Optional repository name to filter by
        direction: "forward" (what this calls) or "backward" (what calls this)
    
    Returns:
        Call graph with nodes and edges
    """
    cursor = conn.cursor()
    
    # Find the symbol
    if repo_name:
        symbol_query = """
            SELECT s.id, s.kind, s.name, s.fqn, f.path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            JOIN repo r ON f.repo_id = r.id
            WHERE s.name = ? AND r.name = ?
            LIMIT 1
        """
        symbol_row = cursor.execute(symbol_query, (symbol_name, repo_name)).fetchone()
    else:
        symbol_query = """
            SELECT s.id, s.kind, s.name, s.fqn, f.path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.name = ?
            LIMIT 1
        """
        symbol_row = cursor.execute(symbol_query, (symbol_name,)).fetchone()
    
    if not symbol_row:
        return {"error": f"Symbol '{symbol_name}' not found"}
    
    symbol_id, kind, name, fqn, file_path = symbol_row
    
    # Get call relationships
    nodes = {symbol_id: {"id": symbol_id, "name": name, "fqn": fqn, "kind": kind, "path": file_path}}
    edges = []
    
    def traverse_calls(current_id: int, visited: set, depth: int = 0, max_depth: int = 3):
        """Recursively traverse call graph."""
        if depth >= max_depth or current_id in visited:
            return
        
        visited.add(current_id)
        
        if direction == "forward":
            # Get functions this symbol calls
            call_query = """
                SELECT s2.id, s2.name, s2.fqn, s2.kind, f.path
                FROM edges e
                JOIN symbols s2 ON e.dst = s2.id
                JOIN files f ON s2.file_id = f.id
                WHERE e.src = ? AND e.etype = 'CALLS'
            """
            call_rows = cursor.execute(call_query, (current_id,)).fetchall()
            
            for called_id, called_name, called_fqn, called_kind, called_path in call_rows:
                if called_id not in nodes:
                    nodes[called_id] = {
                        "id": called_id,
                        "name": called_name,
                        "fqn": called_fqn,
                        "kind": called_kind,
                        "path": called_path,
                    }
                edges.append({"from": current_id, "to": called_id, "type": "CALLS"})
                traverse_calls(called_id, visited, depth + 1, max_depth)
        
        else:  # backward
            # Get functions that call this symbol
            caller_query = """
                SELECT s1.id, s1.name, s1.fqn, s1.kind, f.path
                FROM edges e
                JOIN symbols s1 ON e.src = s1.id
                JOIN files f ON s1.file_id = f.id
                WHERE e.dst = ? AND e.etype = 'CALLS'
            """
            caller_rows = cursor.execute(caller_query, (current_id,)).fetchall()
            
            for caller_id, caller_name, caller_fqn, caller_kind, caller_path in caller_rows:
                if caller_id not in nodes:
                    nodes[caller_id] = {
                        "id": caller_id,
                        "name": caller_name,
                        "fqn": caller_fqn,
                        "kind": caller_kind,
                        "path": caller_path,
                    }
                edges.append({"from": caller_id, "to": current_id, "type": "CALLS"})
                traverse_calls(caller_id, visited, depth + 1, max_depth)
    
    traverse_calls(symbol_id, set())
    
    return {
        "root": {"name": name, "fqn": fqn, "kind": kind},
        "direction": direction,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


async def get_dependencies(
    conn: sqlite3.Connection,
    file_path: str,
    repo_name: Optional[str] = None,
    depth: int = 1,
) -> Dict[str, Any]:
    """Get file dependencies (imports).
    
    Args:
        conn: Database connection
        file_path: Path to the file
        repo_name: Optional repository name to filter by
        depth: How many levels deep to traverse (default 1)
    
    Returns:
        Dependency graph with files and import relationships
    """
    cursor = conn.cursor()
    
    # Find the file
    if repo_name:
        file_query = """
            SELECT f.id, f.path, f.lang
            FROM files f
            JOIN repo r ON f.repo_id = r.id
            WHERE f.path LIKE ? AND r.name = ?
            LIMIT 1
        """
        file_row = cursor.execute(file_query, (f"%{file_path}%", repo_name)).fetchone()
    else:
        file_query = """
            SELECT f.id, f.path, f.lang
            FROM files f
            WHERE f.path LIKE ?
            LIMIT 1
        """
        file_row = cursor.execute(file_query, (f"%{file_path}%",)).fetchone()
    
    if not file_row:
        return {"error": f"File '{file_path}' not found"}
    
    file_id, path, lang = file_row
    
    # Build dependency graph
    nodes = {file_id: {"id": file_id, "path": path, "lang": lang}}
    edges = []
    
    def traverse_imports(current_file_id: int, visited: set, current_depth: int = 0):
        """Recursively traverse import relationships."""
        if current_depth >= depth or current_file_id in visited:
            return
        
        visited.add(current_file_id)
        
        # Get files this file imports
        import_query = """
            SELECT f2.id, f2.path, f2.lang
            FROM edges e
            JOIN files f2 ON e.dst = f2.id
            WHERE e.src = ? AND e.etype = 'IMPORTS'
        """
        import_rows = cursor.execute(import_query, (current_file_id,)).fetchall()
        
        for imported_id, imported_path, imported_lang in import_rows:
            if imported_id not in nodes:
                nodes[imported_id] = {
                    "id": imported_id,
                    "path": imported_path,
                    "lang": imported_lang,
                }
            edges.append({"from": current_file_id, "to": imported_id, "type": "IMPORTS"})
            traverse_imports(imported_id, visited, current_depth + 1)
    
    traverse_imports(file_id, set())
    
    return {
        "root_file": path,
        "depth": depth,
        "nodes": list(nodes.values()),
        "edges": edges,
        "total_dependencies": len(nodes) - 1,
    }


async def get_symbol_dependencies(
    conn: sqlite3.Connection,
    symbol_name: str,
    repo_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get all dependencies for a symbol (imports of its file + calls).
    
    Args:
        conn: Database connection
        symbol_name: Name of the symbol
        repo_name: Optional repository name to filter by
    
    Returns:
        Combined dependencies (file imports + function calls)
    """
    cursor = conn.cursor()
    
    # Find the symbol
    if repo_name:
        symbol_query = """
            SELECT s.id, s.name, s.fqn, s.kind, f.id, f.path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            JOIN repo r ON f.repo_id = r.id
            WHERE s.name = ? AND r.name = ?
            LIMIT 1
        """
        symbol_row = cursor.execute(symbol_query, (symbol_name, repo_name)).fetchone()
    else:
        symbol_query = """
            SELECT s.id, s.name, s.fqn, s.kind, f.id, f.path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.name = ?
            LIMIT 1
        """
        symbol_row = cursor.execute(symbol_query, (symbol_name,)).fetchone()
    
    if not symbol_row:
        return {"error": f"Symbol '{symbol_name}' not found"}
    
    symbol_id, name, fqn, kind, file_id, file_path = symbol_row
    
    # Get file imports
    file_imports = []
    import_query = """
        SELECT f2.path, f2.lang
        FROM edges e
        JOIN files f2 ON e.dst = f2.id
        WHERE e.src = ? AND e.etype = 'IMPORTS'
    """
    for imported_path, imported_lang in cursor.execute(import_query, (file_id,)).fetchall():
        file_imports.append({"path": imported_path, "lang": imported_lang})
    
    # Get direct function calls
    direct_calls = []
    call_query = """
        SELECT s2.name, s2.fqn, s2.kind, f.path
        FROM edges e
        JOIN symbols s2 ON e.dst = s2.id
        JOIN files f ON s2.file_id = f.id
        WHERE e.src = ? AND e.etype = 'CALLS'
    """
    for called_name, called_fqn, called_kind, called_path in cursor.execute(call_query, (symbol_id,)).fetchall():
        direct_calls.append({
            "name": called_name,
            "fqn": called_fqn,
            "kind": called_kind,
            "file": called_path,
        })
    
    return {
        "symbol": {"name": name, "fqn": fqn, "kind": kind, "file": file_path},
        "file_imports": file_imports,
        "direct_calls": direct_calls,
        "total_file_dependencies": len(file_imports),
        "total_function_calls": len(direct_calls),
    }


def register_tools(server) -> None:
    """Register hierarchy tools with the MCP server."""
    import json
    
    for tool_def in HIERARCHY_TOOLS:
        async def make_handler(tool_name):
            """Create handler for specific tool."""
            async def handler(conn, args):
                if tool_name == "get_symbol_tree":
                    result = await get_symbol_tree(conn, **args)
                elif tool_name == "get_call_graph":
                    result = await get_call_graph(conn, **args)
                elif tool_name == "get_dependencies":
                    result = await get_dependencies(conn, **args)
                elif tool_name == "get_symbol_dependencies":
                    result = await get_symbol_dependencies(conn, **args)
                else:
                    return {"error": f"Unknown tool: {tool_name}"}
                return json.dumps(result, indent=2)
            return handler
        
        server.register_tool(
            tool_def["name"],
            tool_def["description"],
            tool_def["inputSchema"],
            make_handler(tool_def["name"]),
        )


# Tool registration metadata
HIERARCHY_TOOLS = [
    {
        "name": "get_symbol_tree",
        "description": "Get hierarchical symbol tree for a file showing nested classes, methods, and functions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file (can be partial path)",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_call_graph",
        "description": "Get call graph for a function/method showing what it calls or what calls it",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the function/method",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
                "direction": {
                    "type": "string",
                    "enum": ["forward", "backward"],
                    "description": "forward: what this calls, backward: what calls this (default: forward)",
                },
            },
            "required": ["symbol_name"],
        },
    },
    {
        "name": "get_dependencies",
        "description": "Get file dependencies (import relationships) with configurable depth",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file (can be partial path)",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many levels deep to traverse (default: 1)",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_symbol_dependencies",
        "description": "Get all dependencies for a symbol (file imports + function calls)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the symbol",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
            },
            "required": ["symbol_name"],
        },
    },
]

