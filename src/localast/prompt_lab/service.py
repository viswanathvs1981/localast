"""Prompt Lab service interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class PromptTemplate:
    name: str
    task: str
    template: str
    metadata: Dict[str, str]


@dataclass(slots=True)
class PromptExperiment:
    template_name: str
    variant: str
    metrics: Dict[str, float]


def list_best_prompts(task: str) -> List[PromptTemplate]:
    """Return an empty list until experiments are tracked."""

    return []
