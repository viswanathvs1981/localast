"""Placeholders for embedding index operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


@dataclass(slots=True)
class Embedding:
    identifier: str
    vector: Tuple[float, ...]


def add_embeddings(_: Iterable[Embedding]) -> None:
    """Stubbed out to keep the local build dependency-free."""



def search(_: Tuple[float, ...], top_k: int = 10) -> List[Embedding]:
    """Return an empty result set to satisfy call sites during early prototyping."""

    return []
