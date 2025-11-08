"""Graph representations used by LocalAST."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import DefaultDict, Dict, Iterable, List


@dataclass(slots=True)
class GraphNode:
    """Represents a file or symbol in the dependency graph."""

    id: str
    kind: str
    data: dict


@dataclass(slots=True)
class Graph:
    """Minimal adjacency list implementation."""

    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: DefaultDict[str, List[str]] = field(default_factory=lambda: DefaultDict(list))

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source].append(target)

    def neighbors(self, source: str) -> List[str]:
        return self.edges.get(source, [])
