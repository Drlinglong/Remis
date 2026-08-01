"""Read-only readiness manifest for Agent-started translation context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.context_service import ContextService
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.services.context_source_parser import ContextSourceParser
from scripts.core.services.source_snapshot_service import SourceSnapshotService


class TranslationContextReadinessService:
    """Describe exactly which context resources an Agent plan can consume."""

    def __init__(self, glossary_manager: Any, candidate_store: Any):
        self.glossary_manager = glossary_manager
        self.candidate_store = candidate_store
        self.repository = ContextRepository(PROJECTS_DB_PATH)
        self.context_service = ContextService(self.repository)
        self.source_parser = ContextSourceParser()
        self.snapshot_service = SourceSnapshotService()

    async def inspect(
        self,
        project_id: str,
        mode: str,
        inspection: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if mode == "none":
            return self._base(mode, status="ready", can_start=True)
        project = inspection or {}
        game_id = str(project.get("game_id") or "")
        if not game_id:
            result = self._base(mode, status="blocked", can_start=False)
            result["warnings"] = ["project_context_readiness_unavailable"]
            return result

        main, project_glossary = await self._glossaries(project_id, game_id, project)
        pending_count = len(self.candidate_store.get_pending_candidates(project_id))
        project_entries = await self._project_entry_count(project_glossary)
        release_details = self._release_details(project_id, project)
        warnings = []
        if project_entries == 0:
            warnings.append("project_glossary_empty")
        if pending_count:
            warnings.append("pending_term_review")
        if mode == "archive" and not release_details.get("release_id"):
            warnings.append("context_release_missing")
        if mode == "archive" and release_details.get("source_snapshot_match") is False:
            warnings.append("context_release_stale")
        if (
            mode == "archive"
            and release_details.get("release_id")
            and release_details.get("source_snapshot_match") is None
        ):
            warnings.append("context_release_unverified")
        if mode == "archive" and release_details.get("effective_context_items") == 0:
            warnings.append("context_release_empty")
        blocking = {
            "context_release_missing",
            "context_release_stale",
            "context_release_unverified",
            "context_release_empty",
        }.intersection(warnings)
        return {
            **self._base(
                mode,
                status="blocked" if blocking else ("attention_required" if warnings else "ready"),
                can_start=not blocking,
            ),
            "glossaries": {
                "main_glossary_id": (main or {}).get("glossary_id"),
                "project_glossary_id": (project_glossary or {}).get("glossary_id"),
                "project_entry_count": project_entries,
                "pending_candidate_count": pending_count,
            },
            "archive": release_details,
            "warnings": warnings,
        }

    @staticmethod
    def _base(mode: str, *, status: str, can_start: bool) -> dict[str, Any]:
        return {
            "requested_mode": mode,
            "status": status,
            "can_start": can_start,
            "included_resources": {
                "main_glossary": mode != "none",
                "project_glossary": mode != "none",
                "project_archive": mode == "archive",
            },
            "glossaries": {},
            "archive": {},
            "warnings": [],
        }

    async def _glossaries(
        self,
        project_id: str,
        game_id: str,
        project: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        available = await self.glossary_manager.get_available_glossaries(game_id)
        main = next((item for item in available if item.get("is_main")), None)
        project_glossary = await self.glossary_manager.get_project_glossary(
            game_id,
            project_id,
            project.get("project_name"),
        )
        return main, project_glossary

    async def _project_entry_count(self, glossary: dict[str, Any] | None) -> int:
        glossary_id = (glossary or {}).get("glossary_id")
        if not glossary_id:
            return 0
        entries = await self.glossary_manager.get_entries_for_glossary_ids([glossary_id])
        return len(entries)

    def _release_details(
        self,
        project_id: str,
        project: dict[str, Any],
    ) -> dict[str, Any]:
        releases = self.repository.list_releases(project_id)
        if not releases:
            return {}
        release = releases[0]
        effective = self.context_service.effective_context(release.release_id)
        config = release.metadata.analysis_config
        return {
            "release_id": release.release_id,
            "source_snapshot_hash": release.metadata.source_snapshot_hash,
            "source_snapshot_match": self._snapshot_matches(release, project),
            "effective_context_items": len((effective.effective_context if effective else {}) or {}),
            "description_language": config.get("description_language"),
            "prompt_version": release.metadata.prompt_version,
        }

    def _snapshot_matches(self, release: Any, project: dict[str, Any]) -> bool | None:
        source_root = project.get("source_path")
        files = (release.metadata.analysis_scope or {}).get("files") or []
        if not source_root or not files:
            return None
        root = Path(source_root).resolve()
        paths = [(root / relative_path).resolve() for relative_path in files]
        if any(not path.is_relative_to(root) or not path.is_file() for path in paths):
            return False
        try:
            parsed = self.source_parser.parse_files([str(path) for path in paths], str(root))
            snapshot = self.source_parser.build_snapshot(parsed, self.snapshot_service)
        except (OSError, UnicodeError, ValueError):
            return None
        return snapshot.source_snapshot_hash == release.metadata.source_snapshot_hash
