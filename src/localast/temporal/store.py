"""Temporal metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List


@dataclass(slots=True)
class ChangeEvent:
    commit_id: str
    parent_commit_id: str
    path: str
    summary: str
    timestamp: datetime


def record_events(_: Iterable[ChangeEvent]) -> None:
    """Placeholder function to satisfy API expectations during scaffolding."""



def list_events(limit: int = 20) -> List[ChangeEvent]:
    """Return an empty list until commit ingestion is implemented."""

    return []
