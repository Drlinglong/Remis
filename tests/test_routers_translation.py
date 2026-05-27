from unittest.mock import AsyncMock, MagicMock

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


def test_run_translation_workflow_v2_logs_project_history_through_async_bridge(monkeypatch, tmp_path):
    task_state.create_task("task-project", status="pending")
    monkeypatch.setattr(translation.i18n, "load_language", MagicMock())
    monkeypatch.setattr(translation.initial_translate, "run", MagicMock())

    project_manager = MagicMock()
    project_manager.log_history_event = AsyncMock()
    project_manager.get_project = AsyncMock(return_value={"source_path": str(tmp_path)})
    monkeypatch.setattr(translation, "project_manager", project_manager)

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
