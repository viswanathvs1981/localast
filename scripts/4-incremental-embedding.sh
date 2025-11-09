#!/bin/bash
# Script 4: Incremental Embedding Generation
# Use this for: Generate embeddings for symbols that don't have them yet
# What it does: Only creates embeddings for new symbols (smart detection)
# Time: Seconds to minutes (depends on # of new symbols)
# Use case: After incremental indexing without --embed flag

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
echo "LocalAST - Incremental Embedding Generation"
echo "=============================================="
echo -e "${NC}"

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <repo_name>${NC}"
    echo ""
    echo "Example:"
    echo "  $0 my-project"
    echo ""
    exit 1
fi

REPO_NAME="$1"
DB_PATH="$HOME/.localast/localast.db"

# Activate virtual environment
echo -e "${YELLOW}[1/3] Activating virtual environment...${NC}"
cd "$PROJECT_ROOT"
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Verify repository
echo -e "${YELLOW}[2/3] Verifying repository...${NC}"
REPO_ID=$(sqlite3 "$DB_PATH" "SELECT id FROM repo WHERE name='$REPO_NAME'" 2>/dev/null || echo "")
if [ -z "$REPO_ID" ]; then
    echo -e "${RED}Error: Repository '$REPO_NAME' not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Repository found (ID: $REPO_ID)${NC}"
echo ""

# Check what needs embeddings
echo -e "${YELLOW}[3/3] Checking embedding coverage...${NC}"
total_symbols=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
existing_embeddings=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID AND index_kind='code'")
missing=$((total_symbols - existing_embeddings))

echo "Current status:"
echo "  Total symbols: $total_symbols"
echo "  Have embeddings: $existing_embeddings"
echo "  Missing embeddings: $missing"
echo ""

if [ $missing -eq 0 ]; then
    echo -e "${GREEN}✓ All symbols already have embeddings!${NC}"
    echo "Nothing to do."
    exit 0
fi

echo "Generating embeddings for $missing symbols..."
echo "Estimated time: $((missing / 1500 + 1)) minutes"
echo ""

# Create and run Python script
cat > /tmp/incremental_embedding_$$.py << 'SCRIPT_EOF'
import sys
import sqlite3
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from localast.storage.database import get_connection
from localast.config import LocalConfig
from localast.embeddings.engine import get_engine, embedding_to_bytes

def generate_incremental_embeddings(repo_id):
    config = LocalConfig()
    conn = get_connection(config)
    cursor = conn.cursor()
    
    print("Initializing embedding engine...")
    engine = get_engine()
    print(f"✓ Engine ready\n")
    
    # Get symbols without embeddings
    cursor.execute("""
        SELECT s.id, s.name, s.fqn, s.doc, s.file_id
        FROM symbols s
        WHERE s.file_id IN (SELECT id FROM files WHERE repo_id = ?)
          AND s.id NOT IN (SELECT symbol_id FROM emb WHERE symbol_id IS NOT NULL AND repo_id = ?)
        ORDER BY s.id
    """, (repo_id, repo_id))
    
    symbols = cursor.fetchall()
    total = len(symbols)
    
    if total == 0:
        return True
    
    processed = 0
    batch_size = 500
    
    for symbol_id, name, fqn, doc, file_id in symbols:
        docstring = doc or ""
        embedding = engine.embed_code_symbol(name, fqn or name, docstring)
        vec_bytes = embedding_to_bytes(embedding)
        
        cursor.execute("""
            INSERT INTO emb (blob_id, dim, vec, index_kind, repo_id, file_id, symbol_id, fqn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (None, engine.dim, sqlite3.Binary(vec_bytes), "code", repo_id, file_id, symbol_id, fqn))
        
        processed += 1
        
        if processed % batch_size == 0:
            conn.commit()
            progress = (processed / total) * 100
            print(f"  Progress: {processed}/{total} ({progress:.1f}%)")
    
    conn.commit()
    print(f"\n✓ Generated {processed} new embeddings")
    conn.close()
    return True

if __name__ == "__main__":
    repo_id = int(sys.argv[1])
    success = generate_incremental_embeddings(repo_id)
    sys.exit(0 if success else 1)
SCRIPT_EOF

python /tmp/incremental_embedding_$$.py "$REPO_ID"
exit_code=$?
rm -f /tmp/incremental_embedding_$$.py

if [ $exit_code -eq 0 ]; then
    # Verify
    new_total=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID AND index_kind='code'")
    
    echo ""
    echo -e "${GREEN}=============================================="
    echo "✓ INCREMENTAL EMBEDDING COMPLETE!"
    echo "=============================================="
    echo -e "${NC}"
    echo "Embedding coverage: $existing_embeddings → $new_total"
    echo ""
    echo -e "${GREEN}Done!${NC}"
else
    echo -e "${RED}✗ Embedding generation failed${NC}"
    exit 1
fi




