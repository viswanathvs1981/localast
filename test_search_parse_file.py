#!/usr/bin/env python3
"""Quick test: Search for parse_file function."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from localast.config import LocalConfig
from localast.storage.database import get_connection

def search_parse_file():
    """Search for parse_file in localast repo."""
    config = LocalConfig()
    conn = get_connection(config)
    cursor = conn.cursor()
    
    # Search in our own code (not venv)
    cursor.execute("""
        SELECT 
            s.name,
            s.kind,
            s.sig,
            f.path,
            s.start_line,
            s.end_line,
            s.doc
        FROM symbols s
        JOIN files f ON s.file_id = f.id
        WHERE s.name = 'parse_file'
          AND f.path LIKE '%/localast/%'
          AND f.path NOT LIKE '%/.venv/%'
        ORDER BY f.path
    """)
    
    results = cursor.fetchall()
    
    print("=" * 80)
    print(f"Found {len(results)} result(s) for 'parse_file' in LocalAST code:")
    print("=" * 80)
    
    for i, row in enumerate(results, 1):
        name, kind, sig, path, start, end, doc = row
        print(f"\n{i}. {name} ({kind})")
        print(f"   📁 File: {path}")
        print(f"   📍 Lines: {start}-{end}")
        if sig:
            print(f"   ✍️  Signature: {sig[:100]}")
        if doc:
            print(f"   📖 Docstring: {doc[:150]}...")
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    search_parse_file()


