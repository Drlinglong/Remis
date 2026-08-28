from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from scripts.routers import translation
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


def test_run_translation_workflow_v2_tracks_recovery_checkpoint(monkeypatch):
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
        use_resume=True,
    )

    checkpoint = tasks["task-checkpoint"]["checkpoint"]
    assert checkpoint["available"] is True
    assert checkpoint["resume_supported"] is True
    assert checkpoint["cursor"] == "localisation/events.yml"
    assert checkpoint["metadata"]["completed"] == 2
    assert checkpoint["metadata"]["total"] == 5


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
