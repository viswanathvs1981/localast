#!/bin/bash
# Script 3: Incremental Indexing
# Use this for: Updating index after code changes
# What it does: Only reindexes changed files (hash-based detection)
# Time: Seconds to minutes (depends on # of changed files)
# Use case: Regular updates, git pull, after editing files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================="
echo "LocalAST - Incremental Indexing"
echo "=============================================="
echo -e "${NC}"

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <repo_name> [--with-embeddings]${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 my-project                    # Fast: index only, no embeddings"
    echo "  $0 my-project --with-embeddings  # Slower: index + embeddings for new symbols"
    echo ""
    exit 1
fi

REPO_NAME="$1"
WITH_EMBEDDINGS=false

if [ "$2" = "--with-embeddings" ]; then
    WITH_EMBEDDINGS=true
fi

DB_PATH="$HOME/.localast/localast.db"

# Activate virtual environment
echo -e "${YELLOW}[1/4] Activating virtual environment...${NC}"
cd "$PROJECT_ROOT"
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Verify repository exists
echo -e "${YELLOW}[2/4] Verifying repository...${NC}"
if ! localast repo list 2>/dev/null | grep -q "$REPO_NAME"; then
    echo -e "${RED}Error: Repository '$REPO_NAME' not found${NC}"
    echo "Run: ./scripts/1-initial-index.sh <path> $REPO_NAME"
    exit 1
fi

REPO_ID=$(sqlite3 "$DB_PATH" "SELECT id FROM repo WHERE name='$REPO_NAME'")
echo -e "${GREEN}✓ Repository found (ID: $REPO_ID)${NC}"
echo ""

# Get before stats
echo -e "${YELLOW}[3/4] Checking current state...${NC}"
before_files=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE repo_id=$REPO_ID")
before_symbols=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
before_embeddings=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID AND index_kind='code'")

echo "Before incremental index:"
echo "  Files: $before_files"
echo "  Symbols: $before_symbols"
echo "  Embeddings: $before_embeddings"
echo ""

# Run incremental indexing
echo -e "${YELLOW}[4/4] Running incremental indexing...${NC}"
echo ""
echo "Strategy:"
echo "  ✓ Hash-based change detection"
echo "  ✓ Only reindex modified files"
echo "  ✓ Update call graphs and dependencies"
echo "  ✓ Reindex new/modified configurations"

if [ "$WITH_EMBEDDINGS" = true ]; then
    echo "  ✓ Generate embeddings for new symbols"
    echo ""
    localast index repo "$REPO_NAME" --embed
else
    echo "  ✗ Skip embedding generation (use --with-embeddings flag)"
    echo ""
    localast index repo "$REPO_NAME"
fi

echo ""

# Get after stats
after_files=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE repo_id=$REPO_ID")
after_symbols=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
after_embeddings=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID AND index_kind='code'")

# Calculate changes
files_diff=$((after_files - before_files))
symbols_diff=$((after_symbols - before_symbols))
embeddings_diff=$((after_embeddings - before_embeddings))

echo -e "${GREEN}=============================================="
echo "✓ INCREMENTAL INDEXING COMPLETE!"
echo "=============================================="
echo -e "${NC}"

echo "Changes:"
echo "  Files: $before_files → $after_files (${files_diff:+$files_diff})"
echo "  Symbols: $before_symbols → $after_symbols (${symbols_diff:+$symbols_diff})"
echo "  Embeddings: $before_embeddings → $after_embeddings (${embeddings_diff:+$embeddings_diff})"
echo ""

if [ "$WITH_EMBEDDINGS" = false ] && [ $symbols_diff -gt 0 ]; then
    echo -e "${YELLOW}Note: New symbols were added but embeddings were not generated${NC}"
    echo "Run: ./scripts/4-incremental-embedding.sh $REPO_NAME"
    echo ""
fi

echo -e "${GREEN}Done!${NC}"




