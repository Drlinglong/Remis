from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.services.translation_context_readiness_service import (
    TranslationContextReadinessService,
)
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.translation_context_service import build_translation_source_snapshot


class FakeCandidateStore:
    def __init__(self, pending=()):
        self.pending = list(pending)

    def get_pending_candidates(self, project_id):
        return self.pending


class FakeRepository:
    def list_releases(self, project_id):
        return []


@pytest.mark.asyncio
async def test_none_mode_is_ready_without_touching_project_resources():
    glossary_manager = SimpleNamespace(
        get_available_glossaries=AsyncMock(),
        get_project_glossary=AsyncMock(),
    )
    service = TranslationContextReadinessService(
        glossary_manager,
        FakeCandidateStore(),
    )

    readiness = await service.inspect("project-1", "none", None)

    assert readiness["status"] == "ready"
    assert readiness["can_start"] is True
    assert readiness["included_resources"]["project_archive"] is False
    glossary_manager.get_available_glossaries.assert_not_awaited()


@pytest.mark.asyncio
async def test_context_mode_blocks_when_project_game_is_unavailable():
    service = TranslationContextReadinessService(
        SimpleNamespace(),
        FakeCandidateStore(),
    )

    readiness = await service.inspect("project-1", "archive", {})

    assert readiness["status"] == "blocked"
    assert readiness["can_start"] is False
    assert readiness["warnings"] == ["project_context_readiness_unavailable"]


@pytest.mark.asyncio
async def test_archive_mode_reports_exact_glossary_counts_and_blocks_without_release():
    glossary_manager = SimpleNamespace(
        get_available_glossaries=AsyncMock(
            return_value=[{"glossary_id": 10, "is_main": True}]
        ),
        get_project_glossary=AsyncMock(return_value={"glossary_id": 20}),
        get_entries_for_glossary_ids=AsyncMock(return_value=[]),
    )
    service = TranslationContextReadinessService(
        glossary_manager,
        FakeCandidateStore([{"id": "candidate-1"}]),
    )
    service.repository = FakeRepository()

    readiness = await service.inspect(
        "project-1",
        "archive",
        {
            "game_id": "stellaris",
            "project_name": "Example",
            "source_path": "J:/mods/example",
        },
    )

    assert readiness["status"] == "blocked"
    assert readiness["can_start"] is False
    assert readiness["glossaries"] == {
        "main_glossary_id": 10,
        "project_glossary_id": 20,
        "project_entry_count": 0,
        "pending_candidate_count": 1,
    }
    assert readiness["warnings"] == [
        "project_glossary_empty",
        "pending_term_review",
        "context_release_missing",
    ]


@pytest.mark.asyncio
async def test_new_localization_file_marks_archive_stale(tmp_path):
    root = tmp_path / "example-mod"
    localization = root / "localisation" / "english"
    localization.mkdir(parents=True)
    first = localization / "01_first_l_english.yml"
    first.write_text(
        'l_english:\n first_key:0 "The first entry"\n',
        encoding="utf-8",
    )
    inventory = IncrementalSnapshotService().build_snapshot(
        str(root), {"name_en": "English", "code": "en"},
    )
    release_hash = build_translation_source_snapshot(inventory).source_snapshot_hash
    release = SimpleNamespace(
        release_id="release-1",
        project_id="project-1",
        metadata=SimpleNamespace(
            source_snapshot_hash=release_hash,
            analysis_config={"files": ["localisation/english/01_first_l_english.yml"]},
            prompt_version="context-v1",
        ),
    )

    class Repository(FakeRepository):
        def list_releases(self, project_id):
            return [release] if project_id == "project-1" else []

    class Context:
        def effective_context(self, release_id):
            assert release_id == "release-1"
            return SimpleNamespace(effective_context={"project:summary": {"summary": "ready"}})

    glossary_manager = SimpleNamespace(
        get_available_glossaries=AsyncMock(return_value=[{"glossary_id": 10, "is_main": True}]),
        get_project_glossary=AsyncMock(return_value={"glossary_id": 20}),
        get_entries_for_glossary_ids=AsyncMock(return_value=[{"key": "term"}]),
    )
    service = TranslationContextReadinessService(glossary_manager, FakeCandidateStore())
    service.repository = Repository()
    service.context_service = Context()
    project = {
        "game_id": "stellaris",
        "project_name": "Example",
        "source_path": str(root),
        "source_language": "en",
    }

    ready = await service.inspect("project-1", "archive", project)
    assert ready["can_start"] is True
    assert ready["archive"]["source_inventory_file_count"] == 1

    second = localization / "02_new_l_english.yml"
    second.write_text(
        'l_english:\n second_key:0 "The new entry"\n',
        encoding="utf-8",
    )
    stale = await service.inspect("project-1", "archive", project)

    assert stale["status"] == "blocked"
    assert stale["can_start"] is False
    assert "context_release_stale" in stale["warnings"]
    assert stale["archive"]["source_inventory_file_count"] == 2
