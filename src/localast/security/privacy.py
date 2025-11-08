"""Security & privacy helpers for local-only execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class AccessPolicy:
    allow_paths: Iterable[Path]
    deny_paths: Iterable[Path]

    def is_allowed(self, path: Path) -> bool:
        absolute = path.resolve()
        deny_paths = [Path(p).resolve() for p in self.deny_paths]
        allow_paths = [Path(p).resolve() for p in self.allow_paths]

        if any(absolute.is_relative_to(deny) for deny in deny_paths):
            return False
        if not allow_paths:
            return True
        return any(absolute.is_relative_to(allow) for allow in allow_paths)
