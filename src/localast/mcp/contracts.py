"""Dataclasses describing the MCP request/response payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(slots=True)
class ReviewPullRequestRequest:
    repo: str
    from_commit: str
    to_commit: str
    rules: List[str]
    depth: str = "shallow"


@dataclass(slots=True)
class ReviewFinding:
    severity: str
    path: str
    message: str
    suggestion: Optional[str] = None


@dataclass(slots=True)
class ReviewPullRequestResponse:
    summary: str
    findings: List[ReviewFinding]
