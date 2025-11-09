"""Embedding index operations and vector search."""

from .index import SearchResult, cosine_similarity, search_code_semantic, search_docs_semantic, find_similar_symbols

__all__ = [
    "SearchResult",
    "cosine_similarity",
    "search_code_semantic",
    "search_docs_semantic",
    "find_similar_symbols",
]
