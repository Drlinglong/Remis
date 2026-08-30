from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.services.agent_translation_plan_service import (
    AgentTranslationPlanError,
    build_agent_translation_plan,
)
from scripts.core.services.translation_context_gate import (
    TranslationContextGate,
    TranslationContextGateError,
)
from scripts.core.services.translation_context_service import (
    TranslationContextService,
    build_translation_source_snapshot,
)
from scripts.schemas.agent import AgentJobPlanRequest
from scripts.workflows import initial_translate


SOURCE_FILES = [{
    "file_path": "localisation/english/main_l_english.yml",
    "original_lines": ["l_english:\n", ' main:0 "Main entry"\n'],
    "source_entries": [{"key": "main", "source": "Main entry"}],
}]


class FakeContextService:
    def __init__(self):
        self.release = SimpleNamespace(
            release_id="release-1",
            project_id="project-1",
            metadata=SimpleNamespace(source_snapshot_hash="different"),
        )

    def list_releases(self, project_id):
        return [self.release] if project_id == "project-1" else []

    def effective_context(self, release_id):
        return SimpleNamespace(
            release=self.release,
            effective_context={"project:summary": {"summary": "Summary"}},
        )

    def traceability(self, release_id):
        return []


def test_translation_context_gate_and_ui_selection_share_archive_blocking_semantics():
    context = FakeContextService()
    current_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    decision = TranslationContextGate.decide(
        "archive",
        release_id="release-1",
        source_snapshot_match=False,
        effective_context_items=1,
    )
    selection = TranslationContextService(context_service=context).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        mode="archive",
    )

    assert decision.can_start is False
    assert decision.reason_code == "context_release_stale"
    assert selection.status == "blocked"
    assert selection.warning["code"] == decision.reason_code
    assert selection.warning["allowed_actions"] == decision.allowed_actions
    assert selection.source_snapshot_hash == current_hash
    with pytest.raises(TranslationContextGateError) as exc_info:
        TranslationContextGate.require_ready("archive", selection)
    assert exc_info.value.reason_code == decision.reason_code
    assert exc_info.value.code == "project_context_not_ready"


def test_non_archive_modes_keep_their_existing_fallback_semantics():
    context = FakeContextService()
    glossaries = TranslationContextService(context_service=context).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        enabled=False,
        mode="glossaries",
    )
    none = TranslationContextService(context_service=context).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        enabled=False,
        mode="none",
    )

    assert glossaries.status == "disabled"
    assert none.status == "disabled"
    assert TranslationContextGate.require_ready("glossaries", glossaries) is glossaries
    assert TranslationContextGate.require_ready("none", none) is none


def test_archive_mode_cannot_be_disabled_without_a_blocking_decision():
    selection = TranslationContextService(
        context_service=FakeContextService(),
    ).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        enabled=False,
        mode="archive",
    )

    assert selection.status == "blocked"
    assert selection.warning["code"] == "context_release_stale"
    with pytest.raises(TranslationContextGateError) as exc_info:
        TranslationContextGate.require_ready("archive", selection)
    assert exc_info.value.reason_code == "context_release_stale"


@pytest.mark.asyncio
async def test_agent_and_ui_share_archive_blocking_semantics():
    decision = TranslationContextGate.decide(
        "archive",
        release_id="release-1",
        source_snapshot_match=False,
        effective_context_items=1,
    )
    readiness = SimpleNamespace(
        inspect=AsyncMock(return_value={
            "requested_mode": "archive",
            "status": decision.status,
            "can_start": decision.can_start,
            "warnings": [decision.reason_code],
            "allowed_actions": decision.allowed_actions,
        })
    )
    plan_factory = AsyncMock(return_value={
        "execution_args": {
            "project_id": "project-1",
            "translation_context_mode": "archive",
        },
        "inspection": {"game_id": "stellaris"},
    })

    with pytest.raises(AgentTranslationPlanError) as exc_info:
        await build_agent_translation_plan(
            AgentJobPlanRequest(
                project_id="project-1",
                api_provider="lm_studio",
                model="local-model",
                translation_context_mode="archive",
            ),
            api_providers={"lm_studio": {"name": "LM Studio"}},
            key_resolver=lambda *_: None,
            plan_factory=plan_factory,
            readiness_service=readiness,
            registry=SimpleNamespace(),
            local_provider_ids={"lm_studio"},
        )

    assert exc_info.value.code == "project_context_not_ready"
    assert exc_info.value.details["context_readiness"]["warnings"] == [
        decision.reason_code
    ]


@pytest.mark.asyncio
async def test_update_translation_path_fails_closed_for_archive_block(monkeypatch):
    from scripts.workflows import update_translate

    selection = SimpleNamespace(
        enabled=True,
        status="blocked",
        warning={"code": "context_release_stale", "allowed_actions": ["update_context_archive"]},
        metadata={"warning": {"code": "context_release_stale"}},
    )
    project_manager = SimpleNamespace(
        get_project=AsyncMock(return_value={
            "name": "Example",
            "source_path": "J:/mods/example",
        })
    )
    monkeypatch.setattr(update_translate, "project_manager", project_manager)
    monkeypatch.setattr(
        update_translate,
        "IncrementalSnapshotService",
        lambda: SimpleNamespace(build_snapshot=lambda *_args, **_kwargs: [{
            "filename": "main_l_english.yml",
            "file_path": "localisation/english/main_l_english.yml",
            "root": "J:/mods/example",
            "original_lines": [],
            "parsed_entries": [],
        }]),
    )
    monkeypatch.setattr(
        update_translate,
        "prepare_context_with_warnings",
        lambda *_args, **_kwargs: (selection, [selection.warning]),
    )

    with pytest.raises(TranslationContextGateError) as exc_info:
        await update_translate.run_incremental_update(
            project_id="project-1",
            target_lang_infos=[{"code": "zh-CN"}],
            source_lang_info={"code": "en"},
            game_profile={"id": "stellaris"},
            translation_context_mode="archive",
        )

    assert exc_info.value.reason_code == "context_release_stale"
    project_manager.get_project.assert_awaited_once_with("project-1")


def test_initial_translation_path_fails_closed_before_translation(monkeypatch):
    called = []
    monkeypatch.setattr(
        initial_translate,
        "build_run_plan",
        lambda *args, **kwargs: SimpleNamespace(
            output_folder_name="out",
            primary_target_lang={"code": "zh-CN"},
            is_batch_mode=False,
        ),
    )
    monkeypatch.setattr(initial_translate, "resolve_provider_model", lambda *args: "local-model")
    monkeypatch.setattr(initial_translate, "create_translation_handler", lambda *args: object())
    monkeypatch.setattr(initial_translate, "load_glossaries_for_run", lambda *args: None)
    monkeypatch.setattr(initial_translate, "prepare_output_workspace", lambda *args: "out")
    monkeypatch.setattr(initial_translate, "discover_files", lambda *args, **kwargs: ["main.yml"])
    monkeypatch.setattr(
        initial_translate,
        "read_files_for_backup",
        lambda *args, **kwargs: SOURCE_FILES,
    )
    monkeypatch.setattr(
        initial_translate,
        "run_language_translation",
        lambda *args, **kwargs: called.append("translated"),
    )

    with pytest.raises(TranslationContextGateError) as exc_info:
        initial_translate.run(
            "Example",
            {"code": "en", "name": "English"},
            [{"code": "zh-CN", "name": "Chinese"}],
            {"id": "stellaris"},
            "",
            selected_provider="local",
            project_id="project-1",
            use_project_context=True,
            context_service=FakeContextService(),
        )

    assert exc_info.value.reason_code == "context_release_stale"
    assert called == []
