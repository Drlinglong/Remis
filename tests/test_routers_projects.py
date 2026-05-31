import pytest
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
        mock.create_project = AsyncMock()
        mock.refresh_project_files = AsyncMock()
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

    write_logs = MagicMock()
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
    write_logs.assert_called_once_with(
        [str(tmp_path / "zh-CN-demo")],
        tasks[task_id]["log"],
        {"languages": [{"target_lang": "zh-CN", "written": 1}]},
    )
    assert ws_push.call_count >= 2


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
