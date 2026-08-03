"""Application service for explicit, project-scoped Mod Archive removal."""

from __future__ import annotations

from typing import Any

from scripts.core.repositories.context_archive_repository import ContextArchiveRepository


class ContextArchiveRemovalService:
    def __init__(self, repository: ContextArchiveRepository):
        self.repository = repository

    def preview(self, project_id: str) -> dict[str, int]:
        return self.repository.archive_counts(project_id)

    def remove(self, project_id: str) -> dict[str, Any]:
        return self.repository.remove_project_archive(project_id)
