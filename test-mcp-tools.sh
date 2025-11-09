#!/bin/bash
# Test MCP Tools Directly (without Cursor)

cd /Users/viswanathsekar/localast
source .venv/bin/activate

echo "================================================================"
echo "Testing LocalAST MCP Tools"
echo "================================================================"
echo ""

python3 << 'PYTHON_EOF'
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

from localast.config import LocalConfig
from localast.storage.database import get_connection

config = LocalConfig()
conn = get_connection(config)

print("🔍 Test 1: Search for 'parse_file' function")
print("-" * 70)

cursor = conn.cursor()
cursor.execute("""
    SELECT 
        s.name,
        s.kind,
        f.path,
        s.start_line,
        s.end_line
    FROM symbols s
    JOIN files f ON s.file_id = f.id
    WHERE s.name = 'parse_file'
      AND f.path LIKE '%/localast/%'
      AND f.path NOT LIKE '%/.venv/%'
    LIMIT 3
""")

results = cursor.fetchall()
for i, (name, kind, path, start, end) in enumerate(results, 1):
    print(f"{i}. {name} ({kind})")
    print(f"   📁 {path}:{start}-{end}")
    print()

print("=" * 70)
print("🌳 Test 2: Get Symbol Hierarchy")
print("-" * 70)

cursor.execute("""
    SELECT 
        s.name,
        s.kind,
        COUNT(c.id) as child_count
    FROM symbols s
    LEFT JOIN symbols c ON c.parent_id = s.id
    WHERE s.name = 'LocalASTServer'
    GROUP BY s.id
    LIMIT 1
""")

result = cursor.fetchone()
if result:
    name, kind, children = result
    print(f"{name} ({kind})")
    print(f"   Has {children} child symbols (methods/attributes)")
    
    # Get children
    cursor.execute("""
        SELECT name, kind
        FROM symbols
        WHERE parent_id = (
            SELECT id FROM symbols WHERE name = 'LocalASTServer' LIMIT 1
        )
        ORDER BY start_line
        LIMIT 10
    """)
    
    children = cursor.fetchall()
    if children:
        print(f"   Methods:")
        for child_name, child_kind in children:
            print(f"     - {child_name} ({child_kind})")
else:
    print("LocalASTServer not found")

print()
print("=" * 70)
print("📊 Test 3: Repository Statistics")
print("-" * 70)

cursor.execute("""
    SELECT 
        (SELECT COUNT(*) FROM repo) as repos,
        (SELECT COUNT(*) FROM files) as files,
        (SELECT COUNT(*) FROM symbols) as symbols,
        (SELECT COUNT(*) FROM emb WHERE index_kind='code') as embeddings,
        (SELECT COUNT(*) FROM version) as commits
""")

repos, files, symbols, embeddings, commits = cursor.fetchone()
print(f"Repositories:     {repos}")
print(f"Files:            {files:,}")
print(f"Symbols:          {symbols:,}")
print(f"Code Embeddings:  {embeddings:,}")
print(f"Commits:          {commits}")

print()
print("=" * 70)
print("✅ All tests completed successfully!")
print("=" * 70)

conn.close()
PYTHON_EOF


