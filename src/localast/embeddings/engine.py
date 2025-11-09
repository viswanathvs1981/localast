"""Embedding generation using sentence-transformers."""

from __future__ import annotations

from array import array
from typing import List, Tuple

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None


# Model configuration
DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingEngine:
    """Generate embeddings for code and documentation."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        if not TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> Tuple[float, ...]:
        """Generate embedding for a single text string.

        Parameters
        ----------
        text:
            Text to embed

        Returns
        -------
        Tuple of embedding values
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return tuple(float(x) for x in embedding)

    def embed_batch(self, texts: List[str]) -> List[Tuple[float, ...]]:
        """Generate embeddings for multiple texts efficiently.

        Parameters
        ----------
        texts:
            List of texts to embed

        Returns
        -------
        List of embedding tuples
        """
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 10,
        )
        return [tuple(float(x) for x in emb) for emb in embeddings]

    def embed_code_symbol(self, symbol_name: str, signature: str, docstring: str = "") -> Tuple[float, ...]:
        """Generate embedding for a code symbol.

        Combines symbol name, signature, and docstring into a semantic representation.

        Parameters
        ----------
        symbol_name:
            Name of the function/class
        signature:
            Function/class signature
        docstring:
            Documentation string

        Returns
        -------
        Embedding tuple
        """
        # Combine into a single text
        text_parts = [f"Name: {symbol_name}"]
        if signature:
            text_parts.append(f"Signature: {signature}")
        if docstring:
            text_parts.append(f"Documentation: {docstring}")
        
        combined_text = "\n".join(text_parts)
        return self.embed_text(combined_text)


def embedding_to_bytes(embedding: Tuple[float, ...]) -> bytes:
    """Convert embedding tuple to bytes for SQLite storage.

    Parameters
    ----------
    embedding:
        Tuple of float values

    Returns
    -------
    Bytes representation
    """
    vec = array("f", embedding)
    return vec.tobytes()


def bytes_to_embedding(data: bytes) -> Tuple[float, ...]:
    """Convert bytes back to embedding tuple.

    Parameters
    ----------
    data:
        Bytes from database

    Returns
    -------
    Embedding tuple
    """
    vec = array("f")
    vec.frombytes(data)
    return tuple(vec)


# Global engine instance (lazy initialization)
_engine: EmbeddingEngine | None = None


def get_engine(model_name: str = DEFAULT_MODEL) -> EmbeddingEngine:
    """Get or create the global embedding engine.

    Parameters
    ----------
    model_name:
        Model to use (default: all-MiniLM-L6-v2)

    Returns
    -------
    EmbeddingEngine instance
    """
    global _engine
    if _engine is None or _engine.model_name != model_name:
        _engine = EmbeddingEngine(model_name)
    return _engine




