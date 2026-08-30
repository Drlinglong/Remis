"""Application service for normal-user human override publication."""

from __future__ import annotations

from typing import Any

from scripts.core.repositories.context_override_repository import ContextOverrideRepository
from scripts.schemas.context import ContextDraft, ContextRelease


class ContextOverrideService:
    """Keep draft ownership and override-only publication in one boundary."""

    def __init__(self, repository: ContextOverrideRepository):
        self.repository = repository

    def start_draft(self, project_id: str, base_release_id: str) -> ContextDraft:
        return self.repository.create_draft(project_id, base_release_id)

    def get_draft(self, project_id: str, draft_id: str) -> ContextDraft:
        return self.repository.get_draft(project_id, draft_id)

    def save_override(
        self,
        project_id: str,
        draft_id: str,
        context_key: str,
        value: dict[str, Any],
        note: str | None,
    ) -> ContextDraft:
        return self.repository.save_override(
            project_id, draft_id, context_key, value, note
        )

    def publish_draft(self, project_id: str, draft_id: str) -> ContextRelease:
        return self.repository.publish_override_draft(project_id, draft_id)
