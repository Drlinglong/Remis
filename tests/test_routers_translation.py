import os
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from scripts.routers import translation, translation_recovery
from scripts.core.provider_errors import ProviderFatalError
from scripts.schemas.translation import InitialTranslationRequest, TranslationRequestV2
from scripts.shared.state import tasks
from scripts.shared import task_state
from scripts.web_server import app


@pytest.fixture(autouse=True)
def clear_translation_tasks():
    tasks.clear()
    yield
    tasks.clear()


def test_status_payload_is_trimmed_without_mutating_task_log():
    client = TestClient(app)
    task_state.create_task("task-1", status="processing")
    for idx in range(120):
        task_state.update_task("task-1", append_log=f"line-{idx}", push=False)

    response = client.get("/api/status/task-1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["log"]) == 100
    assert payload["log"][0] == "line-20"
    assert len(tasks["task-1"]["log"]) == 120


def _legacy_translation_request(project_path: str) -> TranslationRequestV2:
    return TranslationRequestV2(
        project_path=project_path,
        game_profile_id="stellaris",
        source_lang_code="en",
        target_lang_codes=["zh-CN"],
        api_provider="mock",
    )


@pytest.mark.parametrize(
    "custom_config",
    [
        {"name": "Alienese", "code": "custom", "key": "l_english", "folder_prefix": "../escape-"},
        {"name": "Alienese", "code": "../../outside", "key": "l_english", "folder_prefix": "AL-"},
        {"name": "Alienese", "code": "custom", "key": "../../outside", "folder_prefix": "AL-"},
    ],
)
def test_translate_v2_rejects_unsafe_custom_language_configuration(tmp_path, custom_config):
    response = TestClient(app).post("/api/translate_v2", json={
        "project_path": str(tmp_path),
        "game_profile_id": "stellaris",
        "source_lang_code": "en",
        "target_lang_codes": ["custom"],
        "api_provider": "mock",
        "custom_lang_config": custom_config,
    })

    assert response.status_code == 422
    assert tasks == {}


@pytest.mark.parametrize(
    "custom_config",
    [
        {"name": "Alienese", "code": "custom", "key": "l_english", "folder_prefix": "AL-"},
        {"name": "繁體中文", "code": "custom", "key": "l_simp_chinese", "folder_prefix": "zh-TW-"},
    ],
)
def test_custom_language_schema_keeps_supported_shell_languages(custom_config):
    request = TranslationRequestV2(
        project_path="C:/source/mod",
        game_profile_id="stellaris",
        source_lang_code="en",
        target_lang_codes=["custom"],
        api_provider="mock",
        custom_lang_config=custom_config,
    )

    assert request.custom_lang_config.name == custom_config["name"]


@pytest.mark.asyncio
async def test_translate_v2_invalid_path_does_not_admit_task(monkeypatch, tmp_path):
    monkeypatch.setattr(translation, "resolve_runtime_or_400", lambda *_args: object())
    monkeypatch.setattr(translation, "provider_task_fields", lambda _runtime: {})

    with pytest.raises(translation.HTTPException) as error:
        await translation.start_translation_v2(
            BackgroundTasks(),
            _legacy_translation_request(str(tmp_path / "missing")),
        )

    assert error.value.status_code == 400
    assert tasks == {}


@pytest.mark.asyncio
async def test_translate_v2_rejects_filesystem_root_without_touching_managed_sources(
    monkeypatch, tmp_path,
):
    managed = tmp_path / "managed"
    protected = managed / "ExistingMod"
    protected.mkdir(parents=True)
    sentinel = protected / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(translation, "SOURCE_DIR", str(managed))
    monkeypatch.setattr(translation, "resolve_runtime_or_400", lambda *_args: object())
    monkeypatch.setattr(translation, "provider_task_fields", lambda _runtime: {})

    with pytest.raises(translation.HTTPException) as error:
        await translation.start_translation_v2(
            BackgroundTasks(),
            _legacy_translation_request(str(tmp_path.anchor)),
        )

    assert error.value.status_code == 400
    assert "filesystem root" in error.value.detail
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert tasks == {}


@pytest.mark.asyncio
async def test_translate_v2_refuses_to_overwrite_same_named_managed_source(
    monkeypatch, tmp_path,
):
    incoming = tmp_path / "incoming" / "ExistingMod"
    incoming.mkdir(parents=True)
    (incoming / "incoming.txt").write_text("new", encoding="utf-8")
    managed = tmp_path / "managed"
    protected = managed / "ExistingMod"
    protected.mkdir(parents=True)
    sentinel = protected / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(translation, "SOURCE_DIR", str(managed))
    monkeypatch.setattr(translation, "resolve_runtime_or_400", lambda *_args: object())
    monkeypatch.setattr(translation, "provider_task_fields", lambda _runtime: {})

    with pytest.raises(translation.HTTPException) as error:
        await translation.start_translation_v2(
            BackgroundTasks(),
            _legacy_translation_request(str(incoming)),
        )

    assert error.value.status_code == 400
    assert "already exists" in error.value.detail
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert not (protected / "incoming.txt").exists()
    assert tasks == {}


@pytest.mark.asyncio
async def test_translate_v2_copy_failure_does_not_admit_task(monkeypatch, tmp_path):
    source = tmp_path / "incoming" / "mod"
    source.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir()
    monkeypatch.setattr(translation, "SOURCE_DIR", str(managed))
    monkeypatch.setattr(translation, "resolve_runtime_or_400", lambda *_args: object())
    monkeypatch.setattr(translation, "provider_task_fields", lambda _runtime: {})
    monkeypatch.setattr(
        translation.legacy_translation_start_service.shutil,
        "copytree",
        MagicMock(side_effect=OSError("copy failed")),
    )

    with pytest.raises(translation.HTTPException) as error:
        await translation.start_translation_v2(
            BackgroundTasks(),
            _legacy_translation_request(str(source)),
        )

    assert error.value.status_code == 500
    assert tasks == {}


def test_run_translation_workflow_v2_success_uses_shared_task_state(monkeypatch):
    task_state.create_task("task-success", status="pending")
    load_language = MagicMock()
    run_workflow = MagicMock()
    monkeypatch.setattr(translation.i18n, "load_language", load_language)
    monkeypatch.setattr(translation.initial_translate, "run", run_workflow)

    translation.run_translation_workflow_v2(
        "task-success",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [],
        None,
        False,
    )

    task = tasks["task-success"]
    assert task["status"] == "completed"
    assert task["progress"]["percent"] == 100
    assert task["progress"]["stage"] == "Completed"
    assert task["output_dirs"]
    assert any("completed successfully" in line for line in task["log"])
    run_workflow.assert_called_once()


def test_run_translation_workflow_v2_uses_project_runtime_version(monkeypatch):
    task_state.create_task("task-pz-version", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    run_workflow = MagicMock()
    monkeypatch.setattr(translation.initial_translate, "run", run_workflow)

    translation.run_translation_workflow_v2(
        "task-pz-version", "PZ fixture", "project_zomboid", "en", ["zh-CN"],
        "gemini", "", [], None, False, game_version="41.78.0",
    )

    assert run_workflow.call_args.kwargs["game_profile"]["game_version"] == "41.78.0"


def test_project_translation_enqueue_passes_persisted_game_version():
    background = MagicMock()
    request = InitialTranslationRequest(
        project_id="project-pz", source_lang_code="en", target_lang_codes=["zh-CN"],
    )

    translation._enqueue_project_translation(
        background, "task-pz", "PZ fixture",
        {"game_id": "project_zomboid", "game_version": "41.78.0"},
        request, provider_runtime=None, recovery={},
    )

    assert background.add_task.call_args.kwargs["game_version"] == "41.78.0"


def test_run_translation_workflow_v2_preserves_partial_failed_outcome(monkeypatch):
    task_state.create_task("task-partial", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    monkeypatch.setattr(
        translation.initial_translate,
        "run",
        MagicMock(return_value=SimpleNamespace(
            status="partial_failed",
            message=(
                "Translation completed with source-file warnings: "
                "1 invalid entries replaced with empty values; 0 files dropped."
            ),
            issue_count=1,
        )),
    )

    translation.run_translation_workflow_v2(
        "task-partial",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [],
        None,
        False,
    )

    task = tasks["task-partial"]
    assert task["status"] == "partial_failed"
    assert task["progress"]["percent"] == 100
    assert task["progress"]["error_count"] == 1
    assert any("source-file warnings" in line for line in task["log"])


def test_run_translation_workflow_v2_failure_sets_failed_terminal_state(monkeypatch):
    task_state.create_task("task-failed", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    monkeypatch.setattr(
        translation.initial_translate,
        "run",
        MagicMock(side_effect=RuntimeError("boom")),
    )

    translation.run_translation_workflow_v2(
        "task-failed",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [],
        None,
        False,
    )

    task = tasks["task-failed"]
    assert task["status"] == "failed"
    assert task["progress"]["stage"] == "Failed"
    assert any("boom" in line for line in task["log"])
    assert all("Traceback (most recent call last)" not in line for line in task["log"])


def test_run_translation_workflow_v2_projects_fatal_provider_reason(monkeypatch):
    task_state.create_task("task-invalid-model", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    monkeypatch.setattr(
        translation.initial_translate,
        "run",
        MagicMock(side_effect=ProviderFatalError(
            "model not found",
            provider="lm_studio",
            status_code=404,
            reason_code="provider_invalid_model",
        )),
    )

    translation.run_translation_workflow_v2(
        "task-invalid-model",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "lm_studio",
        "",
        [],
        "missing-model",
        False,
    )

    task = tasks["task-invalid-model"]
    assert task["status"] == "failed"
    assert task["attention_reason_code"] == "provider_invalid_model"
    assert task["attention_reason"].startswith("The selected model is invalid")


def test_run_translation_workflow_v2_tracks_checkpoint_when_old_reads_are_disabled(monkeypatch):
    task_state.create_task("task-checkpoint", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())

    def run_with_progress(**kwargs):
        kwargs["progress_callback"](
            2,
            5,
            "localisation/events.yml",
            stage="Translating",
            current_batch=1,
            total_batches=3,
        )
        raise RuntimeError("interrupted after checkpoint")

    monkeypatch.setattr(translation.initial_translate, "run", run_with_progress)

    translation.run_translation_workflow_v2(
        "task-checkpoint",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [],
        None,
        False,
        use_resume=False,
    )

    checkpoint = tasks["task-checkpoint"]["checkpoint"]
    assert checkpoint["available"] is True
    assert checkpoint["resume_supported"] is True
    assert checkpoint["metadata"]["resume_requested"] is False
    assert checkpoint["cursor"] == "localisation/events.yml"
    assert checkpoint["metadata"]["completed"] == 2
    assert checkpoint["metadata"]["total"] == 5


def test_legacy_checkpoint_status_is_retired():
    response = TestClient(app).post(
        "/api/translation/checkpoint-status",
        json={"project_id": "project-1", "target_lang_codes": ["zh-CN"]},
    )

    assert response.status_code == 410
    assert "translation-recovery" in response.json()["detail"]


def test_initial_translation_request_does_not_read_checkpoint_by_default():
    request = InitialTranslationRequest(
        project_id="project-1",
        source_lang_code="en",
    )

    assert request.use_resume is False


def test_clear_translation_checkpoint_uses_project_slot_endpoint(monkeypatch):
    repository = object()
    clear = MagicMock(return_value={
        "task_id": "task-interrupted",
        "status": "interrupted",
        "checkpoint": {"available": False},
        "allowed_actions": ["return_to_workflow"],
    })
    monkeypatch.setattr(task_state, "get_repository", lambda: repository)
    monkeypatch.setattr(
        translation_recovery.TranslationRecoveryService,
        "clear_project_checkpoint",
        clear,
    )

    response = TestClient(app).delete(
        "/api/projects/project-1/translation-checkpoint"
    )

    assert response.status_code == 200
    clear.assert_called_once_with("project-1")


def test_run_translation_workflow_v2_logs_project_history_through_async_bridge(monkeypatch, tmp_path):
    task_state.create_task("task-project", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    monkeypatch.setattr(translation.initial_translate, "run", MagicMock())

    project_manager = MagicMock()
    project_manager.log_history_event = AsyncMock()
    project_manager.get_project = AsyncMock(return_value={"source_path": str(tmp_path)})
    monkeypatch.setattr(translation, "project_manager", project_manager)
    glossary_manager = MagicMock()
    glossary_manager.get_project_glossary = AsyncMock(return_value=None)
    monkeypatch.setattr(translation, "glossary_manager", glossary_manager)

    translation.run_translation_workflow_v2(
        "task-project",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [],
        None,
        False,
        project_id="project-1",
    )

    assert tasks["task-project"]["status"] == "completed"
    assert project_manager.log_history_event.await_count == 2
    project_manager.get_project.assert_awaited_once_with("project-1")
    glossary_manager.get_project_glossary.assert_awaited_once()


def test_run_translation_workflow_v2_gives_explicit_glossary_highest_priority(monkeypatch, tmp_path):
    task_state.create_task("task-glossary-priority", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    run_workflow = MagicMock()
    monkeypatch.setattr(translation.initial_translate, "run", run_workflow)

    project_manager = MagicMock()
    project_manager.log_history_event = AsyncMock()
    project_manager.get_project = AsyncMock(
        return_value={"source_path": str(tmp_path), "name": "Example Mod"}
    )
    monkeypatch.setattr(translation, "project_manager", project_manager)

    glossary_manager = MagicMock()
    glossary_manager.get_available_glossaries = AsyncMock(
        return_value=[{"glossary_id": 10, "is_main": True}]
    )
    glossary_manager.get_project_glossary = AsyncMock(
        return_value={"glossary_id": 20, "name": "Project Terms"}
    )
    monkeypatch.setattr(translation, "glossary_manager", glossary_manager)

    translation.run_translation_workflow_v2(
        "task-glossary-priority",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [30],
        None,
        True,
        project_id="project-1",
    )

    assert run_workflow.call_args.kwargs["selected_glossary_ids"] == [10, 20, 30]


def test_reference_reuse_preview_resolves_project_and_languages(monkeypatch, tmp_path):
    source_path = tmp_path / "source"
    source_path.mkdir()
    monkeypatch.setattr(
        translation.project_manager,
        "get_project",
        AsyncMock(return_value={
            "project_id": "demo",
            "game_id": "victoria3",
            "source_path": str(source_path),
        }),
    )
    preview_service = MagicMock()
    preview_service.preview.return_value = {
        "status": "success",
        "matched_count": 1,
        "matches": [{"key": "TRK:0"}],
    }
    monkeypatch.setattr(
        translation,
        "ReferenceReusePreviewService",
        MagicMock(return_value=preview_service),
    )

    response = TestClient(app).post("/api/reference-reuse/preview", json={
        "project_id": "demo",
        "source_lang_code": "en",
        "target_lang_codes": ["zh-CN"],
        "localization_path": "C:/Victoria 3/game/localization",
    })

    assert response.status_code == 200
    assert response.json()["matches"] == [{"key": "TRK:0"}]
    preview_service.preview.assert_called_once()


def test_reference_reuse_preview_uses_custom_incremental_source(monkeypatch, tmp_path):
    custom_source = tmp_path / "new-version"
    custom_source.mkdir()
    monkeypatch.setattr(
        translation.project_manager,
        "get_project",
        AsyncMock(return_value={
            "project_id": "demo",
            "game_id": "victoria3",
            "source_path": str(tmp_path / "old-version"),
        }),
    )
    preview_service = MagicMock()
    preview_service.preview.return_value = {"status": "success", "matches": []}
    monkeypatch.setattr(
        translation,
        "ReferenceReusePreviewService",
        MagicMock(return_value=preview_service),
    )

    response = TestClient(app).post("/api/reference-reuse/preview", json={
        "project_id": "demo",
        "source_lang_code": "en",
        "target_lang_codes": ["zh-CN"],
        "custom_source_path": str(custom_source),
    })

    assert response.status_code == 200
    assert preview_service.preview.call_args.kwargs["source_path"] == str(custom_source)


def test_run_translation_workflow_v2_none_mode_mounts_no_context_resources(
    monkeypatch,
    tmp_path,
):
    task_state.create_task("task-no-context", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    run_workflow = MagicMock()
    monkeypatch.setattr(translation.initial_translate, "run", run_workflow)

    project_manager = MagicMock()
    project_manager.log_history_event = AsyncMock()
    project_manager.get_project = AsyncMock(
        return_value={"source_path": str(tmp_path), "name": "Example Mod"}
    )
    monkeypatch.setattr(translation, "project_manager", project_manager)
    glossary_manager = MagicMock()
    glossary_manager.get_available_glossaries = AsyncMock()
    glossary_manager.get_project_glossary = AsyncMock()
    monkeypatch.setattr(translation, "glossary_manager", glossary_manager)

    translation.run_translation_workflow_v2(
        "task-no-context",
        "Example Mod",
        "stellaris",
        "en",
        ["zh-CN"],
        "gemini",
        "",
        [30],
        None,
        True,
        project_id="project-1",
        translation_context_mode="none",
    )

    call = run_workflow.call_args.kwargs
    assert call["selected_glossary_ids"] == []
    assert call["use_glossary"] is False
    assert call["use_project_context"] is False
    assert call["use_resume"] is False
    assert call["override_path"] == str(tmp_path)
    glossary_manager.get_available_glossaries.assert_not_awaited()
    glossary_manager.get_project_glossary.assert_not_awaited()


def test_cancelled_task_never_enters_translation_workflow():
    task_state.create_task(
        "task-cancel-before-start",
        status="starting",
        fields={"kind": "initial_translation"},
    )
    task_state.request_task_cancellation("task-cancel-before-start")

    result = translation.run_translation_workflow_v2("task-cancel-before-start")

    assert result is None
    assert task_state.get_task("task-cancel-before-start")["status"] == "cancelled"
