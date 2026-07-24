import pytest
import json
import os
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from scripts.routers import projects as projects_router
from scripts.schemas.project import IncrementalUpdateRequest
from scripts.shared.state import tasks
from scripts.web_server import app

# We Mock the project_manager in the router module
@pytest.fixture
def mock_project_manager():
    with patch("scripts.routers.projects.project_manager", new_callable=MagicMock) as mock:
        # Configure methods to be async
        mock.get_projects = AsyncMock()
        mock.get_project = AsyncMock()
        mock.get_project_files = AsyncMock(return_value=[])
        mock.create_project = AsyncMock()
        mock.refresh_project_files = AsyncMock()
        mock.repair_project_metadata = AsyncMock()
        mock.update_project_files_to_db = AsyncMock()
        mock.update_file_status_with_kanban_sync = AsyncMock()
        mock.update_project_metadata = AsyncMock()
        mock.update_project_status = AsyncMock()
        mock.update_project_notes = AsyncMock()
        mock.update_source_path = AsyncMock()
        yield mock

def test_read_projects(mock_project_manager):
    # Setup mock return value
    mock_project_manager.get_projects.return_value = [
        {"project_id": "1", "name": "Test Project", "status": "active"}
    ]
    
    client = TestClient(app)
    response = client.get("/api/projects")
    
    assert response.status_code == 200
    assert response.json() == [{"project_id": "1", "name": "Test Project", "status": "active"}]
    mock_project_manager.get_projects.assert_called_once()

def test_create_project_invalid_path(mock_project_manager):
    # The router checks os.path.exists before calling manager.create_project (synchronously)
    # So this tests the Router's validation logic which relies on real filesystem (which says path doesn't exist)
    client = TestClient(app)
    response = client.post("/api/project/create", json={
        "name": "Test Project",
        "folder_path": "C:/NonExistentPath/Mod",
        "game_id": "stellaris",
        "source_language": "english"
    })
    
    assert response.status_code == 404

def test_create_project_defaults_to_copy_mode(mock_project_manager):
    mock_project_manager.create_project.return_value = {
        "project_id": "proj-1",
        "name": "Test Project",
        "source_path": "C:/Mods/TestProject",
    }

    client = TestClient(app)
    with patch("scripts.routers.projects.os.path.exists", return_value=True):
        response = client.post("/api/project/create", json={
            "name": "Test Project",
            "folder_path": "C:/Mods/TestProject",
            "game_id": "stellaris",
        })

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_project_manager.create_project.assert_awaited_once_with(
        "Test Project",
        "C:/Mods/TestProject",
        "stellaris",
        "en",
        import_mode="copy",
    )


def test_run_incremental_update_background_marks_task_completed(monkeypatch, tmp_path):
    task_id = "task-1"
    project_id = "project-1"
    request = IncrementalUpdateRequest(project_id=project_id, target_lang_codes=["zh-CN"])
    tasks.clear()
    tasks[task_id] = {"status": "pending", "log": []}

    async def fake_run_incremental_update_workflow(passed_request, progress_callback):
        assert passed_request.project_id == project_id
        progress_callback(
            {
                "percent": 55,
                "stage": "Translating",
                "stage_code": "translating",
                "message": "Working...",
            }
        )
        return {
            "status": "success",
            "summary": {"total": 3, "changed": 1},
            "file_summaries": [{"file": "demo.yml", "status": "changed"}],
            "telemetry": {"languages": [{"target_lang": "zh-CN", "written": 1}]},
            "output_dir": str(tmp_path / "zh-CN-demo"),
            "output_dirs": [str(tmp_path / "zh-CN-demo")],
            "warnings": ["warning-1"],
            "warning_count": 1,
            "workshop_issue_exports": [
                {
                    "issue_count": 2,
                    "issues_path": str(tmp_path / "zh-CN-demo" / "workshop_issues.json"),
                }
            ],
        }

    workflow_log_path = str(tmp_path / "zh-CN-demo" / "incremental_update.log")
    write_logs = MagicMock(return_value=[workflow_log_path])
    ws_push = MagicMock()
    monkeypatch.setattr(
        projects_router.project_manager,
        "run_incremental_update_workflow",
        fake_run_incremental_update_workflow,
    )
    monkeypatch.setattr(projects_router, "_write_incremental_logs", write_logs)
    monkeypatch.setattr("scripts.shared.ws_manager.ws_manager.sync_send_task_update", ws_push)

    projects_router.run_incremental_update_background(task_id, project_id, request)

    assert tasks[task_id]["status"] == "completed"
    assert tasks[task_id]["progress"]["percent"] == 100
    assert tasks[task_id]["progress"]["stage_code"] == "completed"
    assert tasks[task_id]["summary"] == {"total": 3, "changed": 1}
    assert tasks[task_id]["warning_count"] == 1
    assert tasks[task_id]["output_dirs"] == [str(tmp_path / "zh-CN-demo")]
    assert "Working..." in tasks[task_id]["log"]
    assert "Incremental update completed successfully." in tasks[task_id]["log"]
    assert "Runtime translation warnings: 1." in tasks[task_id]["log"]
    assert any("Post-build validation issues: 2." in line for line in tasks[task_id]["log"])
    assert any("Workshop issue sidecar generated:" in line for line in tasks[task_id]["log"])
    assert tasks[task_id]["result"]["types"] == ["files", "change_summary", "workflow_log"]
    assert workflow_log_path in tasks[task_id]["result"]["output_paths"]
    assert tasks[task_id]["result"]["metadata"]["workflow_log_paths"] == [workflow_log_path]
    write_logs.assert_called_once_with(
        [str(tmp_path / "zh-CN-demo")],
        tasks[task_id]["log"],
        {"languages": [{"target_lang": "zh-CN", "written": 1}]},
    )
    assert ws_push.call_count >= 2


def test_write_incremental_logs_returns_explicit_artifact_paths(tmp_path):
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    written = projects_router._write_incremental_logs(
        [str(first_output), str(second_output)],
        ["Queued", "Completed"],
        {"warning_count": 0},
    )

    assert written == [
        str(first_output / "incremental_update.log"),
        str(second_output / "incremental_update.log"),
    ]
    assert "# Incremental Update Log" in (first_output / "incremental_update.log").read_text(encoding="utf-8")
    assert "Completed" in (second_output / "incremental_update.log").read_text(encoding="utf-8")


def test_update_project_status_rejects_unknown_status(mock_project_manager):
    client = TestClient(app)

    response = client.post("/api/project/proj-1/status", json={"status": "half_deleted"})

    assert response.status_code == 422
    mock_project_manager.update_project_status.assert_not_awaited()


def test_update_file_status_rejects_unknown_status(mock_project_manager):
    client = TestClient(app)

    response = client.put(
        "/api/project/proj-1/file/file-1/status",
        json={"status": "half_done"},
    )

    assert response.status_code == 422
    mock_project_manager.update_file_status_with_kanban_sync.assert_not_awaited()


def test_update_file_status_accepts_legacy_translated_status(mock_project_manager):
    client = TestClient(app)

    response = client.put(
        "/api/project/proj-1/file/file-1/status",
        json={"status": "translated"},
    )

    assert response.status_code == 200
    mock_project_manager.update_file_status_with_kanban_sync.assert_awaited_once_with(
        "proj-1",
        "file-1",
        "done",
    )


def test_update_project_config_delegates_source_path_to_manager(mock_project_manager):
    mock_project_manager.get_project.side_effect = [
        {
            "project_id": "proj-1",
            "source_path": "C:/Mods/Old",
            "game_id": "hoi4",
        },
        {
            "project_id": "proj-1",
            "source_path": "C:/Mods/New",
            "game_id": "hoi4",
        },
    ]

    client = TestClient(app)
    with patch("scripts.routers.projects.ProjectJsonManager") as mock_json_manager:
        mock_json_manager.return_value.get_config.return_value = {"translation_dirs": []}
        response = client.post(
            "/api/project/proj-1/config",
            json={"source_path": "C:/Mods/New", "translation_dirs": ["C:/Mods/New/out"]},
        )

    assert response.status_code == 200
    mock_project_manager.update_source_path.assert_awaited_once_with("proj-1", "C:/Mods/New")
    mock_json_manager.assert_called_with("C:/Mods/New")
    mock_json_manager.return_value.update_config.assert_called_once_with(
        {"translation_dirs": ["C:/Mods/New/out"]}
    )
    mock_project_manager.refresh_project_files.assert_awaited_once_with("proj-1")


def test_repair_project_metadata_delegates_to_manager(mock_project_manager):
    mock_project_manager.repair_project_metadata.return_value = {
        "status": "success",
        "actions": ["created_project_sidecar"],
        "warnings": [],
        "file_count": 2,
    }

    client = TestClient(app)
    response = client.post("/api/project/proj-1/repair-metadata")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["file_count"] == 2
    mock_project_manager.repair_project_metadata.assert_awaited_once_with("proj-1")


def test_project_validation_status_prefers_translation_sidecar(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    translation_root = tmp_path / "translation" / "en-DemoMod"
    source_root.mkdir(parents=True)
    translation_root.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(translation_root)]}}),
        encoding="utf-8",
    )
    (source_root / ".remis_errors.json").write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "file_name": "old.yml",
                        "key": "old.key",
                        "error_code": "old_source_issue",
                        "status": "detected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    translation_sidecar = translation_root / ".remis_errors.json"
    translation_sidecar.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "file_name": "localization/english/demo_l_english.yml",
                        "key": "demo.one",
                        "target_lang": "en",
                        "error_code": "validation_residual_punctuation_found",
                        "status": "detected",
                    },
                    {
                        "file_name": "localization/english/demo_l_english.yml",
                        "key": "demo.two",
                        "target_lang": "en",
                        "error_code": "validation_vic3_color_tags_mismatch",
                        "status": "fixed",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    os.utime(source_root / ".remis_errors.json", (3000, 3000))
    os.utime(translation_sidecar, (2000, 2000))

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get("/api/project/proj-1/validation-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["issues_count"] == 1
    assert payload["sidecar_path"] == str(translation_sidecar)
    assert payload["issue_type_counts"] == {"validation_residual_punctuation_found": 1}
    assert payload["last_updated_at"].endswith("+00:00")
    assert {candidate["path"] for candidate in payload["sidecar_candidates"]} == {
        str(source_root / ".remis_errors.json"),
        str(translation_sidecar),
    }


def test_project_validation_status_can_select_source_sidecar(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    translation_root = tmp_path / "translation" / "en-DemoMod"
    source_root.mkdir(parents=True)
    translation_root.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(translation_root)]}}),
        encoding="utf-8",
    )
    source_sidecar = source_root / ".remis_errors.json"
    source_sidecar.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "file_name": "source.yml",
                        "key": "source.key",
                        "error_code": "source_issue",
                        "status": "detected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    translation_sidecar = translation_root / ".remis_errors.json"
    translation_sidecar.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "file_name": "translated.yml",
                        "key": "translated.key",
                        "error_code": "translation_issue",
                        "status": "detected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get(
        "/api/project/proj-1/validation-status",
        params={"sidecar_path": str(source_sidecar)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["issues_count"] == 1
    assert payload["sidecar_path"] == str(source_sidecar)
    assert payload["issue_type_counts"] == {"source_issue": 1}


def test_project_validation_status_groups_selected_current_translation_version(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    current_en = tmp_path / "translation" / "en-Demo-incremental-update-20260708"
    current_fr = tmp_path / "translation" / "fr-Demo-incremental-update-20260708"
    old_de = tmp_path / "translation" / "de-Demo-incremental-update-20260701"
    source_root.mkdir(parents=True)
    current_en.mkdir(parents=True)
    current_fr.mkdir(parents=True)
    old_de.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(current_en), str(current_fr), str(old_de)]}}),
        encoding="utf-8",
    )
    selected_sidecar = current_en / "workshop_issues.json"
    selected_sidecar.write_text(
        json.dumps({
            "issues": [{
                "file_name": "en.yml",
                "key": "en.key",
                "error_code": "current_en_issue",
                "target_lang": "en",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )
    (current_fr / "workshop_issues.json").write_text(
        json.dumps({
            "issues": [{
                "file_name": "fr.yml",
                "key": "fr.key",
                "error_code": "current_fr_issue",
                "target_lang": "fr",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )
    (old_de / "workshop_issues.json").write_text(
        json.dumps({
            "issues": [{
                "file_name": "de.yml",
                "key": "de.key",
                "error_code": "old_de_issue",
                "target_lang": "de",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get(
        "/api/project/proj-1/validation-status",
        params={"sidecar_path": str(selected_sidecar)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["issues_count"] == 2
    assert payload["sidecar_scope"] == "current_translation_version"
    assert payload["issue_type_counts"] == {
        "current_en_issue": 1,
        "current_fr_issue": 1,
    }


def test_project_validation_status_keeps_folder_versions_separate_when_run_id_matches(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    current_translation = tmp_path / "translation" / "Multilanguage-Demo-incremental-update-20260708"
    old_translation = tmp_path / "translation" / "Multilanguage-Demo-incremental-update-20260701"
    source_root.mkdir(parents=True)
    current_translation.mkdir(parents=True)
    old_translation.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(old_translation), str(current_translation)]}}),
        encoding="utf-8",
    )
    selected_sidecar = current_translation / "workshop_issues.json"
    selected_sidecar.write_text(
        json.dumps({
            "project_id": "proj-1",
            "run_id": "same-run-from-bad-refresh",
            "issues": [{
                "file_name": "current.yml",
                "key": "current.key",
                "error_code": "current_issue",
                "target_lang": "de",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )
    (old_translation / "workshop_issues.json").write_text(
        json.dumps({
            "project_id": "proj-1",
            "run_id": "same-run-from-bad-refresh",
            "issues": [{
                "file_name": "old.yml",
                "key": "old.key",
                "error_code": "old_issue",
                "target_lang": "de",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get(
        "/api/project/proj-1/validation-status",
        params={"sidecar_path": str(selected_sidecar)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["issues_count"] == 1
    assert payload["issue_type_counts"] == {"current_issue": 1}


def test_project_validation_status_defaults_to_latest_folder_version(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    current_translation = tmp_path / "translation" / "Multilanguage-Demo-incremental-update-20260708"
    old_translation = tmp_path / "translation" / "Multilanguage-Demo-incremental-update-20260701"
    source_root.mkdir(parents=True)
    current_translation.mkdir(parents=True)
    old_translation.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(old_translation), str(current_translation)]}}),
        encoding="utf-8",
    )
    (old_translation / "workshop_issues.json").write_text(
        json.dumps({
            "issues": [{
                "file_name": "old.yml",
                "key": "old.key",
                "error_code": "old_issue",
                "target_lang": "de",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )
    current_sidecar = current_translation / "workshop_issues.json"
    current_sidecar.write_text(
        json.dumps({
            "issues": [{
                "file_name": "current.yml",
                "key": "current.key",
                "error_code": "current_issue",
                "target_lang": "de",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get("/api/project/proj-1/validation-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sidecar_path"] == str(current_sidecar)
    assert payload["issue_type_counts"] == {"current_issue": 1}


def test_project_validation_status_keeps_distinct_details_for_same_key(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    translation_root = tmp_path / "translation" / "Multilanguage-Demo-incremental-update-20260708"
    source_root.mkdir(parents=True)
    translation_root.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(translation_root)]}}),
        encoding="utf-8",
    )
    (translation_root / "workshop_issues.json").write_text(
        json.dumps({
            "issues": [
                {
                    "file_name": "current.yml",
                    "key": "same.key",
                    "error_code": "variable_mismatch",
                    "details": "variable A missing",
                    "target_lang": "de",
                    "status": "detected",
                },
                {
                    "file_name": "current.yml",
                    "key": "same.key",
                    "error_code": "variable_mismatch",
                    "details": "variable B missing",
                    "target_lang": "de",
                    "status": "detected",
                },
            ]
        }),
        encoding="utf-8",
    )

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get("/api/project/proj-1/validation-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["issues_count"] == 2
    assert payload["issue_type_counts"] == {"variable_mismatch": 2}


def test_project_validation_status_groups_explicit_run_metadata(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    current_en = tmp_path / "translation" / "english-output"
    current_fr = tmp_path / "translation" / "french-output"
    old_de = tmp_path / "translation" / "german-output"
    source_root.mkdir(parents=True)
    current_en.mkdir(parents=True)
    current_fr.mkdir(parents=True)
    old_de.mkdir(parents=True)

    (source_root / ".remis_project.json").write_text(
        json.dumps({"config": {"translation_dirs": [str(current_en), str(current_fr), str(old_de)]}}),
        encoding="utf-8",
    )
    selected_sidecar = current_en / "workshop_issues.json"
    selected_sidecar.write_text(
        json.dumps({
            "project_id": "proj-1",
            "run_id": "run-current",
            "source_version_id": 7,
            "issues": [{
                "file_name": "en.yml",
                "key": "en.key",
                "error_code": "current_en_issue",
                "target_lang": "en",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )
    (current_fr / "workshop_issues.json").write_text(
        json.dumps({
            "project_id": "proj-1",
            "run_id": "run-current",
            "source_version_id": 7,
            "issues": [{
                "file_name": "fr.yml",
                "key": "fr.key",
                "error_code": "current_fr_issue",
                "target_lang": "fr",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )
    (old_de / "workshop_issues.json").write_text(
        json.dumps({
            "project_id": "proj-1",
            "run_id": "run-old",
            "source_version_id": 3,
            "issues": [{
                "file_name": "de.yml",
                "key": "de.key",
                "error_code": "old_de_issue",
                "target_lang": "de",
                "status": "detected",
            }]
        }),
        encoding="utf-8",
    )

    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get(
        "/api/project/proj-1/validation-status",
        params={"sidecar_path": str(selected_sidecar)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["issues_count"] == 2
    assert payload["issue_type_counts"] == {
        "current_en_issue": 1,
        "current_fr_issue": 1,
    }


def test_project_validation_status_rejects_unknown_sidecar(mock_project_manager, tmp_path):
    source_root = tmp_path / "source" / "DemoMod"
    source_root.mkdir(parents=True)
    (source_root / ".remis_errors.json").write_text(
        json.dumps({"issues": []}),
        encoding="utf-8",
    )
    mock_project_manager.get_project.return_value = {
        "project_id": "proj-1",
        "source_path": str(source_root),
    }

    client = TestClient(app)
    response = client.get(
        "/api/project/proj-1/validation-status",
        params={"sidecar_path": str(tmp_path / "outside.json")},
    )

    assert response.status_code == 400
