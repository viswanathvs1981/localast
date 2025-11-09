"""MCP tools for repository tree structure and file organization."""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


async def get_repo_tree(
    conn: sqlite3.Connection,
    repo_name: str,
    path_filter: Optional[str] = None,
    max_depth: int = 5,
) -> Dict[str, Any]:
    """Get file tree structure for a repository.
    
    Args:
        conn: Database connection
        repo_name: Repository name
        path_filter: Optional path prefix to filter by (e.g., "src/")
        max_depth: Maximum directory depth to traverse (default: 5)
    
    Returns:
        Tree structure with files and directories
    """
    cursor = conn.cursor()
    
    # Get repository
    repo_query = "SELECT id, path FROM repo WHERE name = ?"
    repo_row = cursor.execute(repo_query, (repo_name,)).fetchone()
    
    if not repo_row:
        return {"error": f"Repository '{repo_name}' not found"}
    
    repo_id, repo_path = repo_row
    
    # Get all files
    if path_filter:
        files_query = """
            SELECT path, lang, hash
            FROM files
            WHERE repo_id = ? AND path LIKE ?
            ORDER BY path
        """
        files = cursor.execute(files_query, (repo_id, f"%{path_filter}%")).fetchall()
    else:
        files_query = """
            SELECT path, lang, hash
            FROM files
            WHERE repo_id = ?
            ORDER BY path
        """
        files = cursor.execute(files_query, (repo_id,)).fetchall()
    
    # Build tree structure
    def build_tree(file_paths: List[tuple]) -> Dict[str, Any]:
        """Build nested tree structure from file paths."""
        tree = {
            "name": repo_name,
            "type": "directory",
            "children": {},
        }
        
        for file_path, lang, hash_val in file_paths:
            # Convert to relative path
            rel_path = Path(file_path)
            if repo_path in str(rel_path):
                try:
                    rel_path = rel_path.relative_to(repo_path)
                except ValueError:
                    pass
            
            parts = str(rel_path).split("/")
            
            # Skip if too deep
            if len(parts) > max_depth:
                continue
            
            current = tree["children"]
            
            # Traverse/create directory structure
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {
                        "name": part,
                        "type": "directory",
                        "children": {},
                    }
                current = current[part]["children"]
            
            # Add file
            filename = parts[-1]
            current[filename] = {
                "name": filename,
                "type": "file",
                "path": file_path,
                "language": lang,
                "hash": hash_val,
            }
        
        # Convert dict to list for better JSON representation
        def dict_to_list(node: Dict[str, Any]) -> Dict[str, Any]:
            """Convert children dict to list."""
            if "children" in node and isinstance(node["children"], dict):
                node["children"] = [dict_to_list(child) for child in node["children"].values()]
            return node
        
        return dict_to_list(tree)
    
    tree = build_tree(files)
    
    return {
        "repository": repo_name,
        "path_filter": path_filter,
        "total_files": len(files),
        "tree": tree,
    }


async def get_file_tree_with_symbols(
    conn: sqlite3.Connection,
    repo_name: str,
    directory: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get file tree with symbol counts for a directory.
    
    Useful for understanding code organization and finding hot spots.
    
    Args:
        conn: Database connection
        repo_name: Repository name
        directory: Optional directory to filter by
    
    Returns:
        List of files with symbol counts and types
    """
    cursor = conn.cursor()
    
    # Build query
    if directory:
        query = """
            SELECT f.path, f.lang,
                   COUNT(DISTINCT s.id) as symbol_count,
                   COUNT(DISTINCT CASE WHEN s.kind = 'class' THEN s.id END) as class_count,
                   COUNT(DISTINCT CASE WHEN s.kind IN ('function', 'async_function') THEN s.id END) as function_count
            FROM files f
            JOIN repo r ON f.repo_id = r.id
            LEFT JOIN symbols s ON f.id = s.file_id
            WHERE r.name = ? AND f.path LIKE ?
            GROUP BY f.id
            ORDER BY f.path
        """
        rows = cursor.execute(query, (repo_name, f"%{directory}%")).fetchall()
    else:
        query = """
            SELECT f.path, f.lang,
                   COUNT(DISTINCT s.id) as symbol_count,
                   COUNT(DISTINCT CASE WHEN s.kind = 'class' THEN s.id END) as class_count,
                   COUNT(DISTINCT CASE WHEN s.kind IN ('function', 'async_function') THEN s.id END) as function_count
            FROM files f
            JOIN repo r ON f.repo_id = r.id
            LEFT JOIN symbols s ON f.id = s.file_id
            WHERE r.name = ?
            GROUP BY f.id
            ORDER BY f.path
        """
        rows = cursor.execute(query, (repo_name,)).fetchall()
    
    results = []
    for path, lang, symbol_count, class_count, function_count in rows:
        results.append({
            "path": path,
            "language": lang,
            "total_symbols": symbol_count,
            "classes": class_count,
            "functions": function_count,
        })
    
    return results


async def get_directory_stats(
    conn: sqlite3.Connection,
    repo_name: str,
    directory: str,
) -> Dict[str, Any]:
    """Get statistics for a specific directory.
    
    Args:
        conn: Database connection
        repo_name: Repository name
        directory: Directory path
    
    Returns:
        Statistics including file counts, symbol counts, languages used
    """
    cursor = conn.cursor()
    
    # Get file and symbol counts
    stats_query = """
        SELECT 
            COUNT(DISTINCT f.id) as file_count,
            COUNT(DISTINCT s.id) as symbol_count,
            COUNT(DISTINCT CASE WHEN s.kind = 'class' THEN s.id END) as class_count,
            COUNT(DISTINCT CASE WHEN s.kind IN ('function', 'async_function') THEN s.id END) as function_count,
            COUNT(DISTINCT cf.id) as config_file_count
        FROM files f
        JOIN repo r ON f.repo_id = r.id
        LEFT JOIN symbols s ON f.id = s.file_id
        LEFT JOIN config_files cf ON f.id = cf.file_id
        WHERE r.name = ? AND f.path LIKE ?
    """
    stats_row = cursor.execute(stats_query, (repo_name, f"%{directory}%")).fetchone()
    
    if not stats_row:
        return {"error": f"Directory '{directory}' not found in repository '{repo_name}'"}
    
    file_count, symbol_count, class_count, function_count, config_count = stats_row
    
    # Get language breakdown
    lang_query = """
        SELECT f.lang, COUNT(*) as count
        FROM files f
        JOIN repo r ON f.repo_id = r.id
        WHERE r.name = ? AND f.path LIKE ? AND f.lang IS NOT NULL
        GROUP BY f.lang
        ORDER BY count DESC
    """
    lang_rows = cursor.execute(lang_query, (repo_name, f"%{directory}%")).fetchall()
    
    languages = {}
    for lang, count in lang_rows:
        languages[lang] = count
    
    return {
        "repository": repo_name,
        "directory": directory,
        "files": file_count,
        "symbols": symbol_count,
        "classes": class_count,
        "functions": function_count,
        "config_files": config_count,
        "languages": languages,
    }


async def find_largest_files(
    conn: sqlite3.Connection,
    repo_name: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Find largest files by symbol count (code complexity indicator).
    
    Args:
        conn: Database connection
        repo_name: Repository name
        limit: Maximum number of files to return (default: 10)
    
    Returns:
        List of largest files with symbol counts
    """
    cursor = conn.cursor()
    
    query = """
        SELECT f.path, f.lang,
               COUNT(s.id) as symbol_count,
               MAX(s.end_line) as total_lines
        FROM files f
        JOIN repo r ON f.repo_id = r.id
        JOIN symbols s ON f.id = s.file_id
        WHERE r.name = ?
        GROUP BY f.id
        ORDER BY symbol_count DESC
        LIMIT ?
    """
    rows = cursor.execute(query, (repo_name, limit)).fetchall()
    
    results = []
    for path, lang, symbol_count, total_lines in rows:
        results.append({
            "path": path,
            "language": lang,
            "symbol_count": symbol_count,
            "lines": total_lines,
        })
    
    return results


async def search_files_by_name(
    conn: sqlite3.Connection,
    filename: str,
    repo_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search for files by name across repositories.
    
    Args:
        conn: Database connection
        filename: Filename or pattern to search for
        repo_name: Optional repository name to filter by
    
    Returns:
        List of matching files with metadata
    """
    cursor = conn.cursor()
    
    if repo_name:
        query = """
            SELECT f.path, f.lang, r.name as repo,
                   COUNT(s.id) as symbol_count
            FROM files f
            JOIN repo r ON f.repo_id = r.id
            LEFT JOIN symbols s ON f.id = s.file_id
            WHERE f.path LIKE ? AND r.name = ?
            GROUP BY f.id
            ORDER BY f.path
        """
        rows = cursor.execute(query, (f"%{filename}%", repo_name)).fetchall()
    else:
        query = """
            SELECT f.path, f.lang, r.name as repo,
                   COUNT(s.id) as symbol_count
            FROM files f
            LEFT JOIN repo r ON f.repo_id = r.id
            LEFT JOIN symbols s ON f.id = s.file_id
            WHERE f.path LIKE ?
            GROUP BY f.id
            ORDER BY f.path
        """
        rows = cursor.execute(query, (f"%{filename}%",)).fetchall()
    
    results = []
    for path, lang, repo, symbol_count in rows:
        results.append({
            "path": path,
            "language": lang,
            "repository": repo,
            "symbol_count": symbol_count,
        })
    
    return results


def register_tools(server) -> None:
    """Register repository tree tools with the MCP server."""
    import json
    
    for tool_def in TREE_TOOLS:
        async def make_handler(tool_name):
            """Create handler for specific tool."""
            async def handler(conn, args):
                if tool_name == "get_repo_tree":
                    result = await get_repo_tree(conn, **args)
                elif tool_name == "get_file_tree_with_symbols":
                    result = await get_file_tree_with_symbols(conn, **args)
                elif tool_name == "get_directory_stats":
                    result = await get_directory_stats(conn, **args)
                elif tool_name == "find_largest_files":
                    result = await find_largest_files(conn, **args)
                elif tool_name == "search_files_by_name":
                    result = await search_files_by_name(conn, **args)
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
TREE_TOOLS = [
    {
        "name": "get_repo_tree",
        "description": "Get file tree structure for a repository showing directories and files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Repository name",
                },
                "path_filter": {
                    "type": "string",
                    "description": "Optional path prefix to filter by (e.g., 'src/')",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth to traverse (default: 5)",
                },
            },
            "required": ["repo_name"],
        },
    },
    {
        "name": "get_file_tree_with_symbols",
        "description": "Get file tree with symbol counts showing code organization and complexity",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Repository name",
                },
                "directory": {
                    "type": "string",
                    "description": "Optional directory to filter by",
                },
            },
            "required": ["repo_name"],
        },
    },
    {
        "name": "get_directory_stats",
        "description": "Get statistics for a specific directory (file counts, languages, symbols)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Repository name",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory path",
                },
            },
            "required": ["repo_name", "directory"],
        },
    },
    {
        "name": "find_largest_files",
        "description": "Find largest files by symbol count (complexity indicator)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Repository name",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of files to return (default: 10)",
                },
            },
            "required": ["repo_name"],
        },
    },
    {
        "name": "search_files_by_name",
        "description": "Search for files by name across repositories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename or pattern to search for",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
            },
            "required": ["filename"],
        },
    },
]

