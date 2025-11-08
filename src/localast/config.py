"""Configuration utilities for running LocalAST entirely on a developer laptop."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class LocalConfig:
    """Runtime configuration for a fully local deployment.

    Attributes
    ----------
    base_dir:
        Root directory where runtime artefacts such as the SQLite database,
        logs, and caches are stored. Defaults to ``~/.localast``.
    database_path:
        Location of the SQLite database file. Derived from ``base_dir`` when
        not provided explicitly.
    enable_auth_token:
        Whether API endpoints should require an authentication token. Disabled
        by default for local prototyping but can be toggled on once secrets
        management is configured.
    allow_paths:
        Optional whitelist of repository paths that the engine is allowed to
        inspect. Empty list implies full access to the working tree.
    deny_paths:
        Optional blacklist of repository paths that must be ignored even when
        present under ``allow_paths``.
    """

    base_dir: Path = field(default_factory=lambda: Path.home() / ".localast")
    database_path: Path | None = None
    enable_auth_token: bool = False
    allow_paths: list[Path] = field(default_factory=list)
    deny_paths: list[Path] = field(default_factory=list)

    def resolved_database_path(self) -> Path:
        """Return an absolute path to the SQLite database file.

        The directory is created when it does not yet exist so that the rest of
        the application can assume the path is ready for use.
        """

        target = self.database_path or self.base_dir / "localast.db"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target.resolve()


DEFAULT_CONFIG = LocalConfig()
