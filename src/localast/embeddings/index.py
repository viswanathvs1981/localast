"""Embedding index operations and vector search."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

from .engine import bytes_to_embedding, get_engine


@dataclass(slots=True)
class SearchResult:
    """Result from semantic search."""
    
    identifier: str  # FQN or blob_id
    score: float
    text: Optional[str] = None
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None


def cosine_similarity(vec1: Tuple[float, ...], vec2: Tuple[float, ...]) -> float:
    """Compute cosine similarity between two vectors.

    Parameters
    ----------
    vec1, vec2:
        Embedding vectors

    Returns
    -------
    Similarity score between 0 and 1
    """
    if not NUMPY_AVAILABLE:
        # Fallback to pure Python (slower)
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot / (norm1 * norm2) if norm1 and norm2 else 0.0
    
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def search_code_semantic(
    connection: sqlite3.Connection,
    query: str,
    repo_id: Optional[int] = None,
    top_k: int = 10,
) -> List[SearchResult]:
    """Semantic search for code symbols.

    Parameters
    ----------
    connection:
        Database connection
    query:
        Search query text
    repo_id:
        Filter by repository (None for all repos)
    top_k:
        Number of results to return

    Returns
    -------
    List of search results sorted by relevance
    """
    # Generate query embedding
    engine = get_engine()
    query_embedding = engine.embed_text(query)
    
    # Fetch all symbol embeddings
    cursor = connection.cursor()
    
    if repo_id is not None:
        rows = cursor.execute(
            """SELECT e.id, e.vec, e.fqn, e.symbol_id, f.path, s.start_line, s.end_line
               FROM emb e
               LEFT JOIN files f ON e.file_id = f.id
               LEFT JOIN symbols s ON e.symbol_id = s.id
               WHERE e.repo_id = ? AND e.symbol_id IS NOT NULL""",
            (repo_id,),
        ).fetchall()
    else:
        rows = cursor.execute(
            """SELECT e.id, e.vec, e.fqn, e.symbol_id, f.path, s.start_line, s.end_line
               FROM emb e
               LEFT JOIN files f ON e.file_id = f.id
               LEFT JOIN symbols s ON e.symbol_id = s.id
               WHERE e.symbol_id IS NOT NULL"""
        ).fetchall()
    
    # Compute similarities
    results = []
    for row in rows:
        emb_id, vec_bytes, fqn, symbol_id, path, start_line, end_line = row
        if vec_bytes:
            embedding = bytes_to_embedding(vec_bytes)
            score = cosine_similarity(query_embedding, embedding)
            results.append(
                SearchResult(
                    identifier=fqn or f"symbol_{symbol_id}",
                    score=score,
                    file_path=path,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
    
    # Sort by score and return top_k
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


def search_docs_semantic(
    connection: sqlite3.Connection,
    query: str,
    repo_id: Optional[int] = None,
    top_k: int = 10,
) -> List[SearchResult]:
    """Semantic search for documentation.

    Parameters
    ----------
    connection:
        Database connection
    query:
        Search query text
    repo_id:
        Filter by repository (None for all repos)
    top_k:
        Number of results to return

    Returns
    -------
    List of search results sorted by relevance
    """
    # Generate query embedding
    engine = get_engine()
    query_embedding = engine.embed_text(query)
    
    # Fetch all doc embeddings
    cursor = connection.cursor()
    
    if repo_id is not None:
        rows = cursor.execute(
            """SELECT e.id, e.vec, e.blob_id, b.path, b.text
               FROM emb e
               JOIN blob b ON e.blob_id = b.blob_id
               WHERE e.repo_id = ? AND b.kind = 'doc'""",
            (repo_id,),
        ).fetchall()
    else:
        rows = cursor.execute(
            """SELECT e.id, e.vec, e.blob_id, b.path, b.text
               FROM emb e
               JOIN blob b ON e.blob_id = b.blob_id
               WHERE b.kind = 'doc'"""
        ).fetchall()
    
    # Compute similarities
    results = []
    for row in rows:
        emb_id, vec_bytes, blob_id, path, text = row
        if vec_bytes:
            embedding = bytes_to_embedding(vec_bytes)
            score = cosine_similarity(query_embedding, embedding)
            results.append(
                SearchResult(
                    identifier=f"doc_{blob_id}",
                    score=score,
                    text=text[:200] if text else None,  # Preview
                    file_path=path,
                )
            )
    
    # Sort by score and return top_k
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


def find_similar_symbols(
    connection: sqlite3.Connection,
    symbol_id: int,
    top_k: int = 5,
) -> List[SearchResult]:
    """Find symbols similar to a given symbol.

    Parameters
    ----------
    connection:
        Database connection
    symbol_id:
        ID of the reference symbol
    top_k:
        Number of similar symbols to return

    Returns
    -------
    List of similar symbols
    """
    cursor = connection.cursor()
    
    # Get the embedding for the reference symbol
    ref_row = cursor.execute(
        "SELECT vec, repo_id FROM emb WHERE symbol_id = ?", (symbol_id,)
    ).fetchone()
    
    if not ref_row or not ref_row[0]:
        return []
    
    ref_embedding = bytes_to_embedding(ref_row[0])
    repo_id = ref_row[1]
    
    # Get all other symbols in the same repo
    rows = cursor.execute(
        """SELECT e.symbol_id, e.vec, e.fqn, f.path, s.start_line, s.end_line
           FROM emb e
           LEFT JOIN files f ON e.file_id = f.id
           LEFT JOIN symbols s ON e.symbol_id = s.id
           WHERE e.repo_id = ? AND e.symbol_id != ? AND e.symbol_id IS NOT NULL""",
        (repo_id, symbol_id),
    ).fetchall()
    
    # Compute similarities
    results = []
    for row in rows:
        sym_id, vec_bytes, fqn, path, start_line, end_line = row
        if vec_bytes:
            embedding = bytes_to_embedding(vec_bytes)
            score = cosine_similarity(ref_embedding, embedding)
            results.append(
                SearchResult(
                    identifier=fqn or f"symbol_{sym_id}",
                    score=score,
                    file_path=path,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
    
    # Sort and return top_k
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
