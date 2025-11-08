"""Stubs for AST parsing routines.

The implementation intentionally stays lightweight so that developers can run
unit tests locally without additional tooling. Real parsers can be wired in
once language-specific dependencies are available.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(slots=True)
class ParsedSymbol:
    """Minimal representation of a parsed symbol."""

    name: str
    path: Path
    start_line: int
    end_line: int
    kind: str


def _parse_python_file(path: Path) -> List[ParsedSymbol]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        module = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    symbols: List[ParsedSymbol] = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "function"
        elif isinstance(node, ast.ClassDef):
            kind = "class"
        else:
            continue

        end_line = getattr(node, "end_lineno", node.lineno)
        symbols.append(
            ParsedSymbol(
                name=node.name,
                path=path,
                start_line=node.lineno,
                end_line=end_line,
                kind=kind,
            )
        )

    return symbols


def parse_symbols(paths: Iterable[Path]) -> List[ParsedSymbol]:
    """Parse supported files into :class:`ParsedSymbol` instances."""

    symbols: List[ParsedSymbol] = []
    for raw_path in paths:
        path = raw_path.resolve()
        if path.suffix == ".py" and path.is_file():
            symbols.extend(_parse_python_file(path))
    return symbols
