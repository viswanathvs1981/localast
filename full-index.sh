#!/bin/bash
# Full setup and indexing script for LocalAST
# This script initializes the database, adds the current repo, and performs full indexing with all features

set -e  # Exit on error

REPO_PATH="/Users/viswanathsekar/localast"
REPO_NAME="localast"

echo "=========================================="
echo "LocalAST - Full Setup & Indexing Script"
echo "=========================================="
echo ""

# Activate virtual environment
echo "[1/5] Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Check if database exists
DB_PATH="$HOME/.localast/localast.db"
if [ ! -f "$DB_PATH" ]; then
    echo "[2/5] Initializing database (first time)..."
    python scripts/init_db.py
    echo "✓ Database initialized at $DB_PATH"
else
    echo "[2/5] Database already exists at $DB_PATH"
    echo "✓ Using existing database"
fi
echo ""

# Check if repo is already added
echo "[3/5] Checking repository registration..."
if localast repo list 2>/dev/null | grep -q "$REPO_NAME"; then
    echo "✓ Repository '$REPO_NAME' already registered"
else
    echo "Adding repository '$REPO_NAME'..."
    localast repo add "$REPO_PATH" --name "$REPO_NAME"
    echo "✓ Repository added"
fi
echo ""

# Show what will be indexed
echo "[4/5] Pre-indexing scan..."
echo ""
echo "Scanning repository contents:"
echo "  Python files: $(find "$REPO_PATH/src" -name "*.py" 2>/dev/null | wc -l | xargs)"
echo "  Config files (JSON): $(find "$REPO_PATH" -name "*.json" -not -path "*/.*" 2>/dev/null | wc -l | xargs)"
echo "  Config files (YAML): $(find "$REPO_PATH" -name "*.yaml" -o -name "*.yml" 2>/dev/null | wc -l | xargs)"
echo "  Documentation: $(find "$REPO_PATH" -name "*.md" 2>/dev/null | wc -l | xargs)"
echo ""

# Perform full indexing
echo "[5/5] Starting FULL INDEXING (this may take a few minutes)..."
echo ""
echo "This will:"
echo "  ✓ Extract all symbols (functions, classes, methods)"
echo "  ✓ Build hierarchical symbol trees (nested classes/methods)"
echo "  ✓ Extract call graphs (function dependencies)"
echo "  ✓ Track import dependencies"
echo "  ✓ Index configuration files (JSON, YAML, XML)"
echo "  ✓ Extract git history (commits, changes)"
echo "  ✓ Generate semantic embeddings (384-dim vectors)"
echo ""
echo "Starting in 3 seconds... (Press Ctrl+C to cancel)"
sleep 1
echo "Starting in 2 seconds..."
sleep 1
echo "Starting in 1 second..."
sleep 1
echo ""
echo "=========================================="
echo "INDEXING IN PROGRESS..."
echo "=========================================="
echo ""

# Run the actual indexing with progress output
localast index repo "$REPO_NAME" --embed

echo ""
echo "=========================================="
echo "✓ INDEXING COMPLETE!"
echo "=========================================="
echo ""

# Show summary
echo "Summary:"
localast repo info "$REPO_NAME"
echo ""

echo "=========================================="
echo "What's Available Now:"
echo "=========================================="
echo ""
echo "✓ All code symbols indexed (with nested structures)"
echo "✓ Call graphs built (function dependencies)"
echo "✓ Import dependencies tracked"
echo "✓ Configuration files indexed"
echo "✓ Git history extracted"
echo "✓ Semantic embeddings generated"
echo ""
echo "You can now:"
echo "  1. Start MCP server: localast serve"
echo "  2. Query via CLI: localast search semantic 'your query'"
echo "  3. Use AI agents with 30+ MCP tools"
echo ""
echo "Documentation:"
echo "  - ENHANCED_FEATURES.md - Feature documentation"
echo "  - QUICK_START_ENHANCED.md - Usage guide"
echo "  - README.md - MCP tools reference"
echo ""
echo "Happy coding! 🚀"




