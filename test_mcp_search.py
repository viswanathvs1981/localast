#!/usr/bin/env python3
"""Test MCP search functionality directly."""

import sys
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from localast.config import LocalConfig
from localast.storage.database import get_connection


def search_code(connection: sqlite3.Connection, query: str, repo: str = None) -> list:
    """Search for symbols by name (full-text search)."""
    cursor = connection.cursor()
    
    # Build query
    sql = """
        SELECT 
            s.id,
            s.name,
            s.kind,
            s.sig,
            f.path as file_path,
            s.start_line,
            s.end_line,
            r.name as repo_name
        FROM symbols s
        JOIN files f ON s.file_id = f.id
        LEFT JOIN repo r ON f.repo_id = r.id
        WHERE s.name LIKE ?
    """
    params = [f"%{query}%"]
    
    if repo:
        sql += " AND r.name = ?"
        params.append(repo)
    
    sql += " ORDER BY s.name LIMIT 20"
    
    cursor.execute(sql, params)
    results = cursor.fetchall()
    
    return [
        {
            "symbol_id": row[0],
            "name": row[1],
            "kind": row[2],
            "signature": row[3],
            "file_path": row[4],
            "start_line": row[5],
            "end_line": row[6],
            "repo": row[7] or "default",
        }
        for row in results
    ]


def search_semantic(connection: sqlite3.Connection, query: str, repo: str = None, top_k: int = 10):
    """Semantic search using embeddings."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError:
        return {"error": "sentence-transformers not installed"}
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Generate query embedding
    query_emb = model.encode(query, convert_to_numpy=True)
    
    # Get all code embeddings
    cursor = connection.cursor()
    sql = """
        SELECT 
            e.id,
            e.symbol_id,
            e.vector,
            s.name,
            s.kind,
            s.sig,
            f.path,
            s.start_line,
            r.name as repo_name
        FROM emb e
        JOIN symbols s ON e.symbol_id = s.id
        JOIN files f ON s.file_id = f.id
        LEFT JOIN repo r ON f.repo_id = r.id
        WHERE e.index_kind = 'code'
    """
    params = []
    
    if repo:
        sql += " AND r.name = ?"
        params.append(repo)
    
    cursor.execute(sql, params)
    
    # Calculate similarities
    results = []
    for row in cursor.fetchall():
        emb_bytes = row[2]
        if not emb_bytes:
            continue
            
        stored_emb = np.frombuffer(emb_bytes, dtype=np.float32)
        
        # Cosine similarity
        similarity = np.dot(query_emb, stored_emb) / (
            np.linalg.norm(query_emb) * np.linalg.norm(stored_emb)
        )
        
        results.append({
            "symbol_id": row[1],
            "name": row[3],
            "kind": row[4],
            "signature": row[5],
            "file_path": row[6],
            "start_line": row[7],
            "repo": row[8] or "default",
            "similarity": float(similarity),
        })
    
    # Sort by similarity and return top_k
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def main():
    print("=" * 80)
    print("Testing LocalAST Search (Simulating MCP Agent)")
    print("=" * 80)
    print()
    
    # Initialize
    config = LocalConfig()
    conn = get_connection(config)
    
    # Test 1: Full-text search for "parse_file"
    print("🔍 Test 1: Full-Text Search for 'parse_file'")
    print("-" * 80)
    results = search_code(conn, "parse_file", repo="localast")
    
    if results:
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['name']} ({result['kind']})")
            print(f"   File: {result['file_path']}:{result['start_line']}-{result['end_line']}")
            print(f"   Repo: {result['repo']}")
            if result['signature']:
                print(f"   Signature: {result['signature'][:100]}")
    else:
        print("No results found.")
    
    print("\n" + "=" * 80)
    print("🧠 Test 2: Semantic Search for 'function that parses source code files'")
    print("-" * 80)
    
    semantic_results = search_semantic(
        conn, 
        "function that parses source code files and extracts symbols",
        repo="localast",
        top_k=5
    )
    
    if isinstance(semantic_results, dict) and "error" in semantic_results:
        print(f"Error: {semantic_results['error']}")
    elif semantic_results:
        for i, result in enumerate(semantic_results, 1):
            print(f"\n{i}. {result['name']} ({result['kind']}) - Similarity: {result['similarity']:.4f}")
            print(f"   File: {result['file_path']}:{result['start_line']}")
            print(f"   Repo: {result['repo']}")
            if result['signature']:
                print(f"   Signature: {result['signature'][:100]}")
    else:
        print("No results found.")
    
    print("\n" + "=" * 80)
    print("✅ Search tests completed!")
    print("=" * 80)
    
    conn.close()


if __name__ == "__main__":
    main()

