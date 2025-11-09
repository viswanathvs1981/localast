"""Git integration for tracking repository history and changes."""

from .history import GitRepo, extract_commits, extract_changes

__all__ = [
    "GitRepo",
    "extract_commits",
    "extract_changes",
]




