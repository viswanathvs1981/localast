#!/bin/bash
# Start LocalAST MCP Server

echo "=================================="
echo "Starting LocalAST MCP Server"
echo "=================================="
echo ""
echo "Database: ~/.localast/localast.db"
echo "Server: stdio mode"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "----------------------------------"

cd /Users/viswanathsekar/localast
source .venv/bin/activate
localast serve



