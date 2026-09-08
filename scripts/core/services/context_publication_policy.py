"""Shared publication decision for Context Research and Tree v2 storage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextPublicationDecision:
    publishable: bool
    status: str
    coverage_complete: bool


def evaluate_context_publication(
    *,
    unresolved_count: int,
    uncovered_source_item_count: int = 0,
    validation_issue_count: int = 0,
) -> ContextPublicationDecision:
    """Return one fail-closed decision for every Context publication surface."""

    coverage_complete = uncovered_source_item_count == 0
    publishable = (
        unresolved_count == 0
        and coverage_complete
        and validation_issue_count == 0
    )
    return ContextPublicationDecision(
        publishable=publishable,
        status="complete" if publishable else "incomplete",
        coverage_complete=coverage_complete,
    )
