"""Read-only readiness manifest for Agent-started translation context."""

from __future__ import annotations

from typing import Any

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.context_service import ContextService
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.source_snapshot_service import SourceSnapshotService
from scripts.core.services.translation_context_gate import (
    TranslationContextGate,
    archive_readiness_payload,
)
from scripts.core.services.translation_context_service import (
    build_translation_source_snapshot,
)


class TranslationContextReadinessService:
    """Describe exactly which context resources an Agent plan can consume."""

    def __init__(
        self,
        glossary_manager: Any,
        candidate_store: Any,
        source_inventory_service: Any | None = None,
    ):
        self.glossary_manager = glossary_manager
        self.candidate_store = candidate_store
        self.repository = ContextRepository(PROJECTS_DB_PATH)
        self.context_service = ContextService(self.repository)
        self.snapshot_service = SourceSnapshotService()
        self.source_inventory_service = source_inventory_service or IncrementalSnapshotService()

    async def inspect(
        self,
        project_id: str,
        mode: str,
        inspection: dict[str, Any] | None,
        requested_release_id: str | None = None,
    ) -> dict[str, Any]:
        if mode == "none":
            return self._base(mode, status="ready", can_start=True)
        project = inspection or {}
        game_id = str(project.get("game_id") or "")
        if not game_id:
            result = self._base(mode, status="blocked", can_start=False)
            result["warnings"] = ["project_context_readiness_unavailable"]
            result["allowed_actions"] = ["analyze_context", "update_context_archive"]
            return result

        main, project_glossary = await self._glossaries(project_id, game_id, project)
        pending_count = len(self.candidate_store.get_pending_candidates(project_id))
        project_entries = await self._project_entry_count(project_glossary)
        release_details = self._release_details(
            project_id,
            project,
            requested_release_id=requested_release_id,
        )
        warnings = []
        if project_entries == 0:
            warnings.append("project_glossary_empty")
        if pending_count:
            warnings.append("pending_term_review")
        archive_decision = TranslationContextGate.decide(
            mode,
            release_id=release_details.get("release_id"),
            source_snapshot_match=release_details.get("source_snapshot_match"),
            effective_context_items=release_details.get("effective_context_items"),
        )
        if archive_decision.reason_code:
            warnings.append(archive_decision.reason_code)
        blocking = {archive_decision.reason_code} if archive_decision.blocked else set()
        release_details["readiness"] = archive_readiness_payload(
            mode,
            release_id=release_details.get("release_id"),
            source_snapshot_match=release_details.get("source_snapshot_match"),
            effective_context_items=release_details.get("effective_context_items"),
        )
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
            "allowed_actions": archive_decision.allowed_actions,
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
            "allowed_actions": [],
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
        *,
        requested_release_id: str | None = None,
    ) -> dict[str, Any]:
        releases = self.repository.list_releases(project_id)
        if not releases:
            return {}
        release = next(
            (
                item for item in releases
                if not requested_release_id or item.release_id == requested_release_id
            ),
            None,
        )
        if release is None:
            return {}
        effective = self.context_service.effective_context(release.release_id)
        config = release.metadata.analysis_config
        current_snapshot_hash, current_file_count = self._current_snapshot(project)
        release_hash = release.metadata.source_snapshot_hash
        return {
            "release_id": release.release_id,
            "source_snapshot_hash": release_hash,
            "current_source_snapshot_hash": current_snapshot_hash,
            "source_snapshot_match": (
                None
                if current_snapshot_hash is None
                else current_snapshot_hash == release_hash
            ),
            "source_inventory_file_count": current_file_count,
            "effective_context_items": (
                None
                if effective is None
                else len((effective.effective_context or {}))
            ),
            "description_language": config.get("description_language"),
            "prompt_version": release.metadata.prompt_version,
        }

    def _current_snapshot(self, project: dict[str, Any]) -> tuple[str | None, int]:
        source_root = project.get("source_path")
        if not source_root:
            return None, 0
        try:
            files = self.source_inventory_service.build_snapshot(
                str(source_root), self._source_language_info(project),
            )
            if not files:
                return None, 0
            snapshot = build_translation_source_snapshot(files, self.snapshot_service)
        except (OSError, UnicodeError, ValueError, TypeError):
            return None, 0
        return snapshot.source_snapshot_hash, len(files)

    @staticmethod
    def _source_language_info(project: dict[str, Any]) -> dict[str, str]:
        language = str(
            project.get("source_language")
            or project.get("source_lang")
            or "english"
        ).strip()
        normalized = language.casefold()
        names = {
            "en": "English",
            "en-us": "English",
            "english": "English",
            "zh": "Chinese",
            "zh-cn": "Simplified Chinese",
            "zh-hans": "Simplified Chinese",
        }
        return {"name_en": names.get(normalized, language), "code": language}
