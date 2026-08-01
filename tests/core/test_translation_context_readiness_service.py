from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.services.translation_context_readiness_service import (
    TranslationContextReadinessService,
)


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
