#!/bin/bash
# Script 5: Delete and Rebuild Everything
# Use this for: Nuclear option - complete reset and reindex
# What it does: Deletes all data for a repo and rebuilds from scratch
# Time: 5-20 minutes (full reindex + embeddings)
# Use case: Data corruption, schema changes, testing, clean slate

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}=============================================="
echo "LocalAST - DELETE AND REBUILD"
echo "⚠️  WARNING: This will delete all indexed data!"
echo "=============================================="
echo -e "${NC}"

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <repo_name> [--with-embeddings]${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 my-project                    # Rebuild index only (fast)"
    echo "  $0 my-project --with-embeddings  # Rebuild index + embeddings (slow)"
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
cd "$PROJECT_ROOT"
source .venv/bin/activate

# Verify repository exists
if ! localast repo list 2>/dev/null | grep -q "$REPO_NAME"; then
    echo -e "${RED}Error: Repository '$REPO_NAME' not found${NC}"
    exit 1
fi

REPO_ID=$(sqlite3 "$DB_PATH" "SELECT id FROM repo WHERE name='$REPO_NAME'")
REPO_PATH=$(sqlite3 "$DB_PATH" "SELECT path FROM repo WHERE name='$REPO_NAME'")

echo ""
echo "Repository: $REPO_NAME (ID: $REPO_ID)"
echo "Path: $REPO_PATH"
echo ""

# Get current stats
files_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE repo_id=$REPO_ID")
symbols_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
emb_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID")

echo "Current data that will be DELETED:"
echo "  Files: $files_count"
echo "  Symbols: $symbols_count"
echo "  Embeddings: $emb_count"
echo "  Call graphs, configs, git history: All associated data"
echo ""

# Confirmation
echo -e "${YELLOW}⚠️  This action CANNOT be undone!${NC}"
echo ""
read -p "Type 'DELETE' to confirm: " confirmation

if [ "$confirmation" != "DELETE" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}[1/3] Deleting all data for repository '$REPO_NAME'...${NC}"

# Delete all data for this repository
sqlite3 "$DB_PATH" << SQL
-- Delete embeddings
DELETE FROM emb WHERE repo_id=$REPO_ID;

-- Delete edges (call graphs, imports)
DELETE FROM edges WHERE src IN (SELECT id FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID));

-- Delete FTS entries
DELETE FROM ident_fts WHERE symbol_id IN (SELECT id FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID));
DELETE FROM doc_fts WHERE symbol_id IN (SELECT id FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID));

-- Delete symbols
DELETE FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID);

-- Delete config nodes and files
DELETE FROM config_nodes WHERE config_id IN (SELECT id FROM config_files WHERE repo_id=$REPO_ID);
DELETE FROM config_files WHERE repo_id=$REPO_ID;

-- Delete git history
DELETE FROM change_event WHERE repo_id=$REPO_ID;
DELETE FROM version WHERE repo_id=$REPO_ID;

-- Delete files
DELETE FROM files WHERE repo_id=$REPO_ID;

-- Reset repository indexed_at
UPDATE repo SET indexed_at = NULL, last_commit = NULL WHERE id=$REPO_ID;
SQL

echo -e "${GREEN}✓ All data deleted${NC}"
echo ""

# Verify deletion
remaining=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
if [ $remaining -ne 0 ]; then
    echo -e "${RED}Error: Failed to delete all data (remaining symbols: $remaining)${NC}"
    exit 1
fi

# Rebuild
echo -e "${YELLOW}[2/3] Rebuilding index...${NC}"
echo ""

if [ "$WITH_EMBEDDINGS" = true ]; then
    echo "Rebuilding with embeddings (this will take 10-20 minutes)..."
    localast index repo "$REPO_NAME" --embed
else
    echo "Rebuilding without embeddings (faster - 2-5 minutes)..."
    localast index repo "$REPO_NAME"
fi

echo ""

# Get new stats
new_files=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE repo_id=$REPO_ID")
new_symbols=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
new_emb=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID")

echo -e "${YELLOW}[3/3] Verification...${NC}"
echo ""
echo "Rebuilt data:"
echo "  Files: $new_files"
echo "  Symbols: $new_symbols"
echo "  Embeddings: $new_emb"
echo ""

if [ "$WITH_EMBEDDINGS" = false ] && [ $new_symbols -gt 0 ]; then
    echo -e "${YELLOW}Note: Index rebuilt but no embeddings generated${NC}"
    echo "To add embeddings: ./scripts/2-initial-embedding.sh $REPO_NAME"
    echo ""
fi

echo -e "${GREEN}=============================================="
echo "✓ REBUILD COMPLETE!"
echo "=============================================="
echo -e "${NC}"
echo -e "${GREEN}Repository '$REPO_NAME' has been completely rebuilt!${NC}"
echo ""




