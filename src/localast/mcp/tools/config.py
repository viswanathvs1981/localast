"""MCP tools for configuration file analysis and comparison."""

import json
import sqlite3
from typing import Any, Dict, List, Optional


async def get_config_tree(
    conn: sqlite3.Connection,
    config_path: str,
    repo_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get hierarchical tree view of a configuration file.
    
    Args:
        conn: Database connection
        config_path: Path to the configuration file
        repo_name: Optional repository name to filter by
    
    Returns:
        Configuration tree with nested structure
    """
    cursor = conn.cursor()
    
    # Find the config file
    if repo_name:
        config_query = """
            SELECT cf.id, cf.path, cf.format, cf.indexed_at
            FROM config_files cf
            JOIN repo r ON cf.repo_id = r.id
            WHERE cf.path LIKE ? AND r.name = ?
            LIMIT 1
        """
        config_row = cursor.execute(config_query, (f"%{config_path}%", repo_name)).fetchone()
    else:
        config_query = """
            SELECT cf.id, cf.path, cf.format, cf.indexed_at
            FROM config_files cf
            WHERE cf.path LIKE ?
            LIMIT 1
        """
        config_row = cursor.execute(config_query, (f"%{config_path}%",)).fetchone()
    
    if not config_row:
        return {"error": f"Configuration file '{config_path}' not found"}
    
    config_id, path, format_type, indexed_at = config_row
    
    # Get all nodes
    nodes_query = """
        SELECT id, parent_id, key_path, key, value, value_type, line_number
        FROM config_nodes
        WHERE config_id = ?
        ORDER BY id
    """
    nodes_rows = cursor.execute(nodes_query, (config_id,)).fetchall()
    
    # Build node map
    nodes_map = {}
    for node_id, parent_id, key_path, key, value, value_type, line_number in nodes_rows:
        nodes_map[node_id] = {
            "id": node_id,
            "parent_id": parent_id,
            "key_path": key_path,
            "key": key,
            "value": value,
            "value_type": value_type,
            "line_number": line_number,
            "children": [],
        }
    
    # Build tree structure
    tree = []
    for node_id, node in nodes_map.items():
        if node["parent_id"] is None:
            tree.append(node)
        else:
            parent = nodes_map.get(node["parent_id"])
            if parent:
                parent["children"].append(node)
    
    return {
        "path": path,
        "format": format_type,
        "indexed_at": indexed_at,
        "tree": tree,
        "total_nodes": len(nodes_map),
    }


async def compare_configs(
    conn: sqlite3.Connection,
    config_path1: str,
    config_path2: str,
    repo_name1: Optional[str] = None,
    repo_name2: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare two configuration files and show differences.
    
    Args:
        conn: Database connection
        config_path1: Path to first config file
        config_path2: Path to second config file
        repo_name1: Optional repository name for first config
        repo_name2: Optional repository name for second config
    
    Returns:
        Comparison results with added, removed, and modified keys
    """
    cursor = conn.cursor()
    
    # Helper to get config nodes
    def get_config_nodes(config_path: str, repo_name: Optional[str]) -> Optional[Dict[str, Any]]:
        if repo_name:
            query = """
                SELECT cf.id
                FROM config_files cf
                JOIN repo r ON cf.repo_id = r.id
                WHERE cf.path LIKE ? AND r.name = ?
                LIMIT 1
            """
            config_row = cursor.execute(query, (f"%{config_path}%", repo_name)).fetchone()
        else:
            query = """
                SELECT cf.id
                FROM config_files cf
                WHERE cf.path LIKE ?
                LIMIT 1
            """
            config_row = cursor.execute(query, (f"%{config_path}%",)).fetchone()
        
        if not config_row:
            return None
        
        config_id = config_row[0]
        
        # Get all leaf nodes (nodes with actual values)
        nodes_query = """
            SELECT key_path, value, value_type
            FROM config_nodes
            WHERE config_id = ? AND value IS NOT NULL
        """
        nodes = {}
        for key_path, value, value_type in cursor.execute(nodes_query, (config_id,)).fetchall():
            nodes[key_path] = {"value": value, "type": value_type}
        
        return nodes
    
    config1_nodes = get_config_nodes(config_path1, repo_name1)
    config2_nodes = get_config_nodes(config_path2, repo_name2)
    
    if config1_nodes is None:
        return {"error": f"Configuration file '{config_path1}' not found"}
    if config2_nodes is None:
        return {"error": f"Configuration file '{config_path2}' not found"}
    
    # Find differences
    all_keys = set(config1_nodes.keys()) | set(config2_nodes.keys())
    
    added = []
    removed = []
    modified = []
    unchanged = []
    
    for key in sorted(all_keys):
        if key not in config1_nodes:
            added.append({
                "key_path": key,
                "new_value": config2_nodes[key]["value"],
                "type": config2_nodes[key]["type"],
            })
        elif key not in config2_nodes:
            removed.append({
                "key_path": key,
                "old_value": config1_nodes[key]["value"],
                "type": config1_nodes[key]["type"],
            })
        elif config1_nodes[key]["value"] != config2_nodes[key]["value"]:
            modified.append({
                "key_path": key,
                "old_value": config1_nodes[key]["value"],
                "new_value": config2_nodes[key]["value"],
                "type": config1_nodes[key]["type"],
            })
        else:
            unchanged.append(key)
    
    return {
        "config1": config_path1,
        "config2": config_path2,
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged_count": len(unchanged),
        "total_differences": len(added) + len(removed) + len(modified),
    }


async def search_config_value(
    conn: sqlite3.Connection,
    search_term: str,
    repo_name: Optional[str] = None,
    value_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search for configuration values across all config files.
    
    Args:
        conn: Database connection
        search_term: Value to search for (supports wildcards)
        repo_name: Optional repository name to filter by
        value_type: Optional type filter (string, number, boolean, etc.)
    
    Returns:
        List of matching configuration entries
    """
    cursor = conn.cursor()
    
    # Build query
    if repo_name:
        if value_type:
            query = """
                SELECT cf.path, cf.format, cn.key_path, cn.key, cn.value, cn.value_type, cn.line_number
                FROM config_nodes cn
                JOIN config_files cf ON cn.config_id = cf.id
                JOIN repo r ON cf.repo_id = r.id
                WHERE cn.value LIKE ? AND cn.value_type = ? AND r.name = ?
                ORDER BY cf.path, cn.key_path
            """
            rows = cursor.execute(query, (f"%{search_term}%", value_type, repo_name)).fetchall()
        else:
            query = """
                SELECT cf.path, cf.format, cn.key_path, cn.key, cn.value, cn.value_type, cn.line_number
                FROM config_nodes cn
                JOIN config_files cf ON cn.config_id = cf.id
                JOIN repo r ON cf.repo_id = r.id
                WHERE cn.value LIKE ? AND r.name = ?
                ORDER BY cf.path, cn.key_path
            """
            rows = cursor.execute(query, (f"%{search_term}%", repo_name)).fetchall()
    else:
        if value_type:
            query = """
                SELECT cf.path, cf.format, cn.key_path, cn.key, cn.value, cn.value_type, cn.line_number
                FROM config_nodes cn
                JOIN config_files cf ON cn.config_id = cf.id
                WHERE cn.value LIKE ? AND cn.value_type = ?
                ORDER BY cf.path, cn.key_path
            """
            rows = cursor.execute(query, (f"%{search_term}%", value_type)).fetchall()
        else:
            query = """
                SELECT cf.path, cf.format, cn.key_path, cn.key, cn.value, cn.value_type, cn.line_number
                FROM config_nodes cn
                JOIN config_files cf ON cn.config_id = cf.id
                WHERE cn.value LIKE ?
                ORDER BY cf.path, cn.key_path
            """
            rows = cursor.execute(query, (f"%{search_term}%",)).fetchall()
    
    results = []
    for path, format_type, key_path, key, value, val_type, line_number in rows:
        results.append({
            "file": path,
            "format": format_type,
            "key_path": key_path,
            "key": key,
            "value": value,
            "type": val_type,
            "line_number": line_number,
        })
    
    return results


async def get_config_by_key_path(
    conn: sqlite3.Connection,
    key_path: str,
    repo_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Find all configuration entries matching a specific key path.
    
    Useful for finding the same configuration key across different files.
    
    Args:
        conn: Database connection
        key_path: Configuration key path (e.g., "database.connection.host")
        repo_name: Optional repository name to filter by
    
    Returns:
        List of matching entries across all config files
    """
    cursor = conn.cursor()
    
    if repo_name:
        query = """
            SELECT cf.path, cf.format, cn.value, cn.value_type, cn.line_number
            FROM config_nodes cn
            JOIN config_files cf ON cn.config_id = cf.id
            JOIN repo r ON cf.repo_id = r.id
            WHERE cn.key_path = ? AND r.name = ?
            ORDER BY cf.path
        """
        rows = cursor.execute(query, (key_path, repo_name)).fetchall()
    else:
        query = """
            SELECT cf.path, cf.format, cn.value, cn.value_type, cn.line_number
            FROM config_nodes cn
            JOIN config_files cf ON cn.config_id = cf.id
            WHERE cn.key_path = ?
            ORDER BY cf.path
        """
        rows = cursor.execute(query, (key_path,)).fetchall()
    
    results = []
    for path, format_type, value, val_type, line_number in rows:
        results.append({
            "file": path,
            "format": format_type,
            "key_path": key_path,
            "value": value,
            "type": val_type,
            "line_number": line_number,
        })
    
    return results


async def list_config_files(
    conn: sqlite3.Connection,
    repo_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all indexed configuration files.
    
    Args:
        conn: Database connection
        repo_name: Optional repository name to filter by
    
    Returns:
        List of configuration files with metadata
    """
    cursor = conn.cursor()
    
    if repo_name:
        query = """
            SELECT cf.path, cf.format, cf.indexed_at,
                   COUNT(cn.id) as node_count,
                   r.name as repo_name
            FROM config_files cf
            JOIN repo r ON cf.repo_id = r.id
            LEFT JOIN config_nodes cn ON cf.id = cn.config_id
            WHERE r.name = ?
            GROUP BY cf.id
            ORDER BY cf.path
        """
        rows = cursor.execute(query, (repo_name,)).fetchall()
    else:
        query = """
            SELECT cf.path, cf.format, cf.indexed_at,
                   COUNT(cn.id) as node_count,
                   r.name as repo_name
            FROM config_files cf
            LEFT JOIN repo r ON cf.repo_id = r.id
            LEFT JOIN config_nodes cn ON cf.id = cn.config_id
            GROUP BY cf.id
            ORDER BY cf.path
        """
        rows = cursor.execute(query).fetchall()
    
    results = []
    for path, format_type, indexed_at, node_count, repo in rows:
        results.append({
            "path": path,
            "format": format_type,
            "indexed_at": indexed_at,
            "node_count": node_count,
            "repository": repo,
        })
    
    return results


def register_tools(server) -> None:
    """Register configuration tools with the MCP server."""
    import json
    
    for tool_def in CONFIG_TOOLS:
        async def make_handler(tool_name):
            """Create handler for specific tool."""
            async def handler(conn, args):
                if tool_name == "get_config_tree":
                    result = await get_config_tree(conn, **args)
                elif tool_name == "compare_configs":
                    result = await compare_configs(conn, **args)
                elif tool_name == "search_config_value":
                    result = await search_config_value(conn, **args)
                elif tool_name == "get_config_by_key_path":
                    result = await get_config_by_key_path(conn, **args)
                elif tool_name == "list_config_files":
                    result = await list_config_files(conn, **args)
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
CONFIG_TOOLS = [
    {
        "name": "get_config_tree",
        "description": "Get hierarchical tree view of a configuration file (JSON, YAML, XML) showing all keys and values",
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the configuration file (can be partial path)",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "compare_configs",
        "description": "Compare two configuration files and show differences (added, removed, modified keys)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path1": {
                    "type": "string",
                    "description": "Path to first configuration file",
                },
                "config_path2": {
                    "type": "string",
                    "description": "Path to second configuration file",
                },
                "repo_name1": {
                    "type": "string",
                    "description": "Optional repository name for first config",
                },
                "repo_name2": {
                    "type": "string",
                    "description": "Optional repository name for second config",
                },
            },
            "required": ["config_path1", "config_path2"],
        },
    },
    {
        "name": "search_config_value",
        "description": "Search for configuration values across all config files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Value to search for (supports wildcards)",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
                "value_type": {
                    "type": "string",
                    "enum": ["string", "number", "boolean", "array", "object"],
                    "description": "Optional type filter",
                },
            },
            "required": ["search_term"],
        },
    },
    {
        "name": "get_config_by_key_path",
        "description": "Find all configuration entries matching a specific key path (e.g., 'database.connection.host') across all files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key_path": {
                    "type": "string",
                    "description": "Configuration key path using dot notation",
                },
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
            },
            "required": ["key_path"],
        },
    },
    {
        "name": "list_config_files",
        "description": "List all indexed configuration files with metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Optional repository name to filter by",
                },
            },
        },
    },
]

