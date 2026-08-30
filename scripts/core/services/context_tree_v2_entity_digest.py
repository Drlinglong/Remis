"""Public entity-digest service boundary for context-archive tree v2."""

from __future__ import annotations

from typing import Any

from scripts.core.services.context_tree_v2_entity_digest_execution import (
    EntityDigestExecutionEngine,
)
from scripts.schemas.context_tree_v2_entity_digest import (
    CandidateGrade,
    CandidateKind,
    DigestCandidate,
    DigestLocalUnit,
    EntityCandidate,
    EntityDigest,
    EntityDigestCallRecord,
    EntityDigestDiagnostic,
    EntityDigestResponse,
    EntityDigestRunResult,
    EntityEvidenceBundle,
    EntityEvidenceRecord,
    LocalUnit,
    MAX_ENTITY_SOURCE_CHARS,
    MAX_ENTITY_UNITS,
    MAX_PROJECT_OVERVIEW_CHARS,
    PartialEntityDigest,
    ProjectOverview,
    SampledLocalUnit,
    SamplingMetadata,
    SamplingResult,
    SemanticMergeProposal,
    SemanticMergeRecompute,
    SemanticMergeResult,
    TreeCandidate,
)


def _as_items(value: Any, attribute: str) -> Any:
    if value is not None and not isinstance(value, (list, tuple)) and hasattr(value, attribute):
        return getattr(value, attribute)
    return value or ()


class ContextTreeV2EntityDigestService:
    """Run A/B digest calls while preserving complete #2 evidence."""

    def __init__(
        self,
        handler: Any,
        *,
        max_units: int = MAX_ENTITY_UNITS,
        max_source_chars: int = MAX_ENTITY_SOURCE_CHARS,
        max_project_overview_chars: int = MAX_PROJECT_OVERVIEW_CHARS,
    ) -> None:
        self._engine = EntityDigestExecutionEngine(
            handler,
            max_units=max_units,
            max_source_chars=max_source_chars,
            max_project_overview_chars=max_project_overview_chars,
        )

    def run(
        self,
        candidates: Any = None,
        local_units: Any = None,
        *,
        entity_candidates: Any = None,
        units: Any = None,
        project_title: str = "",
        human_project_summary: str | None = None,
        manual_project_summary: str | None = None,
        project_summary: str | None = None,
        event_group_summaries: Any = None,
        event_groups: Any = None,
    ) -> EntityDigestRunResult:
        selected_candidates = _as_items(entity_candidates if candidates is None else candidates, "candidates")
        selected_units = _as_items(units if local_units is None else local_units, "local_units")
        return self._engine.run(
            selected_candidates,
            selected_units,
            project_title=project_title,
            human_project_summary=human_project_summary or manual_project_summary or project_summary,
            event_groups=event_group_summaries if event_group_summaries is not None else event_groups,
        )

    def execute(self, *args: Any, **kwargs: Any) -> EntityDigestRunResult:
        return self.run(*args, **kwargs)

    def sample_units(self, candidate: Any, local_units: Any) -> SamplingResult:
        return self._engine.sample_preview(candidate, local_units)


EntityDigestService = ContextTreeV2EntityDigestService


__all__ = [
    "CandidateGrade",
    "CandidateKind",
    "ContextTreeV2EntityDigestService",
    "DigestCandidate",
    "DigestLocalUnit",
    "EntityCandidate",
    "EntityDigest",
    "EntityDigestCallRecord",
    "EntityDigestDiagnostic",
    "EntityDigestResponse",
    "EntityDigestRunResult",
    "EntityDigestService",
    "EntityEvidenceBundle",
    "EntityEvidenceRecord",
    "LocalUnit",
    "MAX_ENTITY_SOURCE_CHARS",
    "MAX_ENTITY_UNITS",
    "MAX_PROJECT_OVERVIEW_CHARS",
    "PartialEntityDigest",
    "ProjectOverview",
    "SampledLocalUnit",
    "SamplingMetadata",
    "SamplingResult",
    "SemanticMergeProposal",
    "SemanticMergeRecompute",
    "SemanticMergeResult",
    "TreeCandidate",
]
