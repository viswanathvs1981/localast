#!/bin/bash
# Script 2: Initial Embedding Generation
# Use this for: Generating embeddings for already-indexed symbols
# What it does: Creates 384-dim vectors for all symbols (enables semantic search)
# Time: 5-15 minutes depending on symbol count
# Prerequisite: Run script 1 (initial-index.sh) first

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
echo "LocalAST - Initial Embedding Generation"
echo "=============================================="
echo -e "${NC}"

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <repo_name>${NC}"
    echo ""
    echo "Example:"
    echo "  $0 my-project"
    echo "  $0 backend-api"
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

# Verify repository exists
echo -e "${YELLOW}[2/3] Verifying repository...${NC}"
if ! localast repo list 2>/dev/null | grep -q "$REPO_NAME"; then
    echo -e "${RED}Error: Repository '$REPO_NAME' not found${NC}"
    echo "Available repositories:"
    localast repo list
    exit 1
fi

# Get repo ID
REPO_ID=$(sqlite3 "$DB_PATH" "SELECT id FROM repo WHERE name='$REPO_NAME'")
if [ -z "$REPO_ID" ]; then
    echo -e "${RED}Error: Could not find repository ID${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Repository '$REPO_NAME' found (ID: $REPO_ID)${NC}"

# Check current status
symbol_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=$REPO_ID)")
emb_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emb WHERE repo_id=$REPO_ID AND index_kind='code'")

echo ""
echo "Current status:"
echo "  Total symbols: $symbol_count"
echo "  Existing embeddings: $emb_count"
echo "  Need to generate: $((symbol_count - emb_count))"
echo ""

if [ $((symbol_count - emb_count)) -eq 0 ]; then
    echo -e "${GREEN}✓ All symbols already have embeddings!${NC}"
    exit 0
fi

# Generate embeddings
echo -e "${YELLOW}[3/3] Generating embeddings...${NC}"
echo ""
echo "This will:"
echo "  ✓ Generate 384-dimensional vectors for all symbols"
echo "  ✓ Enable semantic search capabilities"
echo "  ✓ Process ~1000-2000 symbols per minute"
echo ""
echo "Estimated time: $((symbol_count / 1500)) minutes"
echo ""

# Create Python script to generate embeddings
cat > /tmp/generate_embeddings_$$.py << 'SCRIPT_EOF'
import sys
import sqlite3
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from localast.storage.database import get_connection
from localast.config import LocalConfig
from localast.embeddings.engine import get_engine, embedding_to_bytes

def generate_embeddings(repo_id, repo_name):
    config = LocalConfig()
    conn = get_connection(config)
    cursor = conn.cursor()
    
    print("Initializing embedding engine...")
    try:
        engine = get_engine()
    except Exception as e:
        print(f"Error: Could not initialize embedding engine: {e}")
        return False
    
    print(f"✓ Engine ready: {engine.dim}-dimensional embeddings\n")
    
    # Get symbols without embeddings
    cursor.execute("""
        SELECT s.id, s.name, s.fqn, s.doc, s.file_id
        FROM symbols s
        WHERE s.file_id IN (SELECT id FROM files WHERE repo_id = ?)
          AND s.id NOT IN (SELECT symbol_id FROM emb WHERE symbol_id IS NOT NULL AND repo_id = ?)
    """, (repo_id, repo_id))
    
    symbols = cursor.fetchall()
    total = len(symbols)
    
    if total == 0:
        print("✓ All symbols already have embeddings!")
        return True
    
    print(f"Generating embeddings for {total:,} symbols...")
    print("Progress updates every 1000 symbols\n")
    
    batch_size = 1000
    processed = 0
    
    for symbol_id, name, fqn, doc, file_id in symbols:
        # Generate embedding
        docstring = doc or ""
        embedding = engine.embed_code_symbol(name, fqn or name, docstring)
        vec_bytes = embedding_to_bytes(embedding)
        
        # Store in database
        cursor.execute("""
            INSERT INTO emb (blob_id, dim, vec, index_kind, repo_id, file_id, symbol_id, fqn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (None, engine.dim, sqlite3.Binary(vec_bytes), "code", repo_id, file_id, symbol_id, fqn))
        
        processed += 1
        
        # Progress update and commit every batch
        if processed % batch_size == 0:
            conn.commit()
            progress = (processed / total) * 100
            print(f"  [{processed:,}/{total:,}] {progress:.1f}% complete - Latest: {name}")
    
    # Final commit
    conn.commit()
    
    print(f"\n✓ Successfully generated {processed:,} embeddings!")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM emb WHERE repo_id=? AND index_kind='code'", (repo_id,))
    emb_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM symbols WHERE file_id IN (SELECT id FROM files WHERE repo_id=?)", (repo_id,))
    symbol_count = cursor.fetchone()[0]
    
    coverage = (emb_count / symbol_count) * 100 if symbol_count > 0 else 0
    print(f"\nEmbedding Coverage: {emb_count:,}/{symbol_count:,} ({coverage:.1f}%)")
    
    conn.close()
    return True

if __name__ == "__main__":
    repo_id = int(sys.argv[1])
    repo_name = sys.argv[2]
    success = generate_embeddings(repo_id, repo_name)
    sys.exit(0 if success else 1)
SCRIPT_EOF

# Run the Python script
python /tmp/generate_embeddings_$$.py "$REPO_ID" "$REPO_NAME"
exit_code=$?

# Cleanup
rm -f /tmp/generate_embeddings_$$.py

if [ $exit_code -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=============================================="
    echo "✓ EMBEDDING GENERATION COMPLETE!"
    echo "=============================================="
    echo -e "${NC}"
    
    echo -e "${BLUE}What's available now:${NC}"
    echo "  ✓ Full-text code search"
    echo "  ✓ Semantic similarity search"
    echo "  ✓ Symbol hierarchy and call graphs"
    echo "  ✓ Configuration analysis"
    echo "  ✓ Git history tracking"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Test semantic search: localast search semantic 'your query' --repo $REPO_NAME"
    echo "  2. Start MCP server: localast serve"
    echo "  3. Configure in Cursor/VSCode and use AI agents!"
    echo ""
    echo -e "${GREEN}Done!${NC}"
else
    echo ""
    echo -e "${RED}✗ Embedding generation failed${NC}"
    exit 1
fi




