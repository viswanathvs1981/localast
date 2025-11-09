#!/bin/bash
# Script 1: Initial Full Indexing (WITHOUT embeddings)
# Use this for: First-time indexing of a repository
# What it does: Indexes code, configs, git history - FAST (no embeddings)
# Time: 1-3 minutes for medium repos
# Next step: Run script 2 (initial-embedding.sh) to add embeddings

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=============================================="
echo "LocalAST - Initial Full Indexing"
echo "=============================================="
echo -e "${NC}"

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Usage: $0 <repo_path> <repo_name>${NC}"
    echo ""
    echo "Example:"
    echo "  $0 /path/to/my-project my-project"
    echo "  $0 ~/projects/backend backend-api"
    echo ""
    exit 1
fi

REPO_PATH="$1"
REPO_NAME="$2"

# Validate repo path
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${RED}Error: Repository path does not exist: $REPO_PATH${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}[1/5] Activating virtual environment...${NC}"
cd "$PROJECT_ROOT"
if [ ! -d ".venv" ]; then
    echo -e "${RED}Error: Virtual environment not found. Run ./install.sh first${NC}"
    exit 1
fi
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Check if database exists
DB_PATH="$HOME/.localast/localast.db"
if [ ! -f "$DB_PATH" ]; then
    echo -e "${YELLOW}[2/5] Database not found, initializing...${NC}"
    python scripts/init_db.py
    echo -e "${GREEN}✓ Database initialized${NC}"
else
    echo -e "${YELLOW}[2/5] Database exists at $DB_PATH${NC}"
    echo -e "${GREEN}✓ Using existing database${NC}"
fi
echo ""

# Check if repo is already registered
echo -e "${YELLOW}[3/5] Checking repository registration...${NC}"
if localast repo list 2>/dev/null | grep -q "$REPO_NAME"; then
    echo -e "${GREEN}✓ Repository '$REPO_NAME' already registered${NC}"
    read -p "Do you want to continue indexing? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
else
    echo "Registering repository '$REPO_NAME'..."
    localast repo add "$REPO_PATH" --name "$REPO_NAME"
    echo -e "${GREEN}✓ Repository registered${NC}"
fi
echo ""

# Pre-indexing scan
echo -e "${YELLOW}[4/5] Pre-indexing scan...${NC}"
echo ""
echo "Repository: $REPO_NAME"
echo "Path: $REPO_PATH"
echo ""
if [ -d "$REPO_PATH" ]; then
    py_count=$(find "$REPO_PATH" -name "*.py" -type f 2>/dev/null | wc -l | xargs)
    json_count=$(find "$REPO_PATH" -name "*.json" -not -path "*/.*" -type f 2>/dev/null | wc -l | xargs)
    yaml_count=$(find "$REPO_PATH" \( -name "*.yaml" -o -name "*.yml" \) -type f 2>/dev/null | wc -l | xargs)
    md_count=$(find "$REPO_PATH" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
    
    echo "Estimated content:"
    echo "  Python files: $py_count"
    echo "  JSON configs: $json_count"
    echo "  YAML configs: $yaml_count"
    echo "  Markdown docs: $md_count"
fi
echo ""

# Perform indexing (WITHOUT embeddings)
echo -e "${YELLOW}[5/5] Starting FULL INDEXING (without embeddings)...${NC}"
echo ""
echo "This will index:"
echo "  ✓ All source code (functions, classes, methods)"
echo "  ✓ Nested symbols (methods in classes, inner functions)"
echo "  ✓ Call graphs (function dependencies)"
echo "  ✓ Import dependencies"
echo "  ✓ Configuration files (JSON, YAML, XML)"
echo "  ✓ Git history (commits, changes)"
echo "  ✗ Embeddings (skipped for speed)"
echo ""
echo "Estimated time: 1-5 minutes"
echo ""

# Run the actual indexing
localast index repo "$REPO_NAME"

echo ""
echo -e "${GREEN}=============================================="
echo "✓ INITIAL INDEXING COMPLETE!"
echo "=============================================="
echo -e "${NC}"

# Show summary
echo "Summary:"
localast repo list | grep -A 3 "$REPO_NAME" || echo "Repository: $REPO_NAME"
echo ""

echo -e "${BLUE}What was indexed:${NC}"
sqlite3 "$DB_PATH" "
SELECT 
  '  Files: ' || COUNT(DISTINCT f.id),
  '  Symbols: ' || COUNT(DISTINCT s.id),
  '  Nested: ' || COUNT(DISTINCT CASE WHEN s.parent_id IS NOT NULL THEN s.id END),
  '  Calls: ' || COUNT(DISTINCT e.src) 
FROM files f
LEFT JOIN symbols s ON f.id = s.file_id
LEFT JOIN edges e ON s.id = e.src AND e.etype = 'CALLS'
JOIN repo r ON f.repo_id = r.id
WHERE r.name = '$REPO_NAME';
" | tr '|' '\n'

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Generate embeddings: ./scripts/2-initial-embedding.sh $REPO_NAME"
echo "  2. Or start using: localast search code 'query' --repo $REPO_NAME"
echo "  3. Or start MCP server: localast serve"
echo ""
echo -e "${GREEN}Done!${NC}"




