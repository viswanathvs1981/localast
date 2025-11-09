"""MCP server implementation for LocalAST."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Dict

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None
    stdio_server = None
    types = None

from ..config import LocalConfig
from ..storage.database import get_connection
from ..storage.schema import apply_schema


class LocalASTServer:
    """MCP server for LocalAST code intelligence."""

    def __init__(self, config: LocalConfig | None = None):
        if not MCP_AVAILABLE:
            raise RuntimeError(
                "MCP SDK is not installed. Install with: pip install mcp"
            )
        
        self.config = config or LocalConfig()
        self.server = Server("localast")
        self.connection: sqlite3.Connection | None = None
        self.tools: Dict[str, Callable] = {}
        self.tool_metadata: Dict[str, tuple[str, Dict]] = {}
        
        # Register handlers once at initialization
        self._setup_handlers()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.connection is None:
            self.connection = get_connection(self.config)
            apply_schema(self.connection)
        return self.connection

    def _setup_handlers(self) -> None:
        """Set up MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """List available tools."""
            return [
                types.Tool(
                    name=tool_name,
                    description=desc,
                    inputSchema=schema,
                )
                for tool_name, (desc, schema) in self.tool_metadata.items()
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool invocation."""
            if name not in self.tools:
                raise ValueError(f"Unknown tool: {name}")
            
            connection = self._get_connection()
            handler = self.tools[name]
            
            try:
                result = handler(connection, arguments)
                return [types.TextContent(type="text", text=str(result))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable,
    ) -> None:
        """Register an MCP tool.

        Parameters
        ----------
        name:
            Tool name
        description:
            Tool description
        input_schema:
            JSON schema for tool inputs
        handler:
            Function to call when tool is invoked
        """
        self.tools[name] = handler
        self.tool_metadata[name] = (description, input_schema)

    async def run(self) -> None:
        """Run the MCP server with stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.connection:
            self.connection.close()
            self.connection = None


def create_server(config: LocalConfig | None = None) -> LocalASTServer:
    """Create and configure an MCP server instance.

    Parameters
    ----------
    config:
        LocalAST configuration

    Returns
    -------
    Configured LocalASTServer instance
    """
    server = LocalASTServer(config)
    
    # Import and register all tools
    from .tools import search, context, history, repos, hierarchy, config, tree
    
    # Register search tools
    search.register_tools(server)
    
    # Register context tools
    context.register_tools(server)
    
    # Register history tools
    history.register_tools(server)
    
    # Register repository tools
    repos.register_tools(server)
    
    # Register hierarchy tools (symbol tree, call graph, dependencies)
    hierarchy.register_tools(server)
    
    # Register configuration tools (config analysis, comparison)
    config.register_tools(server)
    
    # Register tree tools (repository structure, file tree)
    tree.register_tools(server)
    
    return server

