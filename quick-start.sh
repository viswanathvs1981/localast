#!/usr/bin/env bash
# LocalAST Quick Start - Setup and index in one command

set -e

echo "🚀 LocalAST Quick Start"
echo ""

# Run setup
echo "Step 1: Installing LocalAST..."
./setup.sh

# Activate venv
source .venv/bin/activate

# Add this repo
echo ""
echo "Step 2: Registering LocalAST repository..."
localast repo add . --name localast

# Index it
echo ""
echo "Step 3: Indexing (this will take 1-2 minutes)..."
localast index repo localast --embed

# Show stats
echo ""
echo "Step 4: Results..."
localast repo info

echo ""
echo "======================================"
echo "  ✓ Ready to use!"
echo "======================================"
echo ""
echo "What you can do now:"
echo ""
echo "1. Start MCP server:"
echo "   localast serve"
echo ""
echo "2. Or search from command line:"
echo "   # Coming soon: localast search 'your query'"
echo ""
echo "3. Configure Cursor/VSCode:"
echo "   See GETTING_STARTED.md for config instructions"
echo ""
echo "4. View indexed data:"
echo "   localast repo list"
echo ""
echo "Database location: ~/.localast/localast.db"
echo ""




