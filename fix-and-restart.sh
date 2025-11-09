#!/usr/bin/env bash
set -e

echo "================================================"
echo "  Fixing NumPy Compatibility Issue"
echo "================================================"
echo ""

# Activate venv
source .venv/bin/activate

echo "Uninstalling NumPy 2.x..."
pip uninstall -y numpy

echo "Installing NumPy 1.x..."
pip install "numpy>=1.24.0,<2.0.0"

echo "Reinstalling dependencies to ensure compatibility..."
pip install -r requirements.txt --force-reinstall --no-cache-dir

echo ""
echo "✓ Fixed!"
echo ""
echo "================================================"
echo "  Now indexing LocalAST..."
echo "================================================"
echo ""

# Register and index
if localast repo list 2>/dev/null | grep -q "localast"; then
    echo "Repository already registered, reindexing..."
    localast reindex localast
else
    echo "Registering repository..."
    localast repo add . --name localast
    echo "Indexing..."
    localast index repo localast --embed
fi

echo ""
echo "✓ Complete!"
echo ""

# Show stats
localast repo info

echo ""
echo "================================================"
echo "  Starting MCP Server..."
echo "================================================"
echo ""
echo "Server will start in 3 seconds. Press Ctrl+C to stop."
echo ""
sleep 3

localast serve




