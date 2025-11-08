"""Greptile-style code review stub."""

from __future__ import annotations

from typing import List

from ..mcp.contracts import (
    ReviewFinding,
    ReviewPullRequestRequest,
    ReviewPullRequestResponse,
)


def review_pull_request(request: ReviewPullRequestRequest) -> ReviewPullRequestResponse:
    """Return a placeholder response emphasising local execution."""

    summary = (
        "Local review stubs are active. Indexing and policy evaluation run "
        "entirely on the developer workstation."
    )
    finding = ReviewFinding(
        severity="info",
        path="",
        message="No automated checks have been implemented yet.",
    )
    return ReviewPullRequestResponse(summary=summary, findings=[finding])
