import os

import pytest
from fastapi.testclient import TestClient

from scripts.web_server import app
from scripts.routers import system as system_router
from scripts.shared import services, task_state
from scripts.core import db_initializer
from scripts.core.db_manager import db_manager


client = TestClient(app)


class _FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


class _FakeArchiveManager:
    def __init__(self):
        self._conn = object()
        self.closed = False

    def close(self):
        self.closed = True


def test_reference_library_status_and_manual_build_endpoints(monkeypatch):
    status_payload = {
        "status": "success",
        "libraries": [{"game_id": "victoria3", "available": True}],
    }
    build_calls = []
    monkeypatch.setattr(system_router.reference_library_service, "status", lambda: status_payload)
    monkeypatch.setattr(
        system_router.reference_library_service,
        "build",
        lambda game_id, path: build_calls.append((game_id, path)) or {
            "status": "success",
            "library": {"game_id": game_id, "available": True},
        },
    )

    status_response = client.get("/api/system/reference-library")
    build_response = client.post(
        "/api/system/reference-library/build",
        json={"game_id": "victoria3", "localization_path": "I:/game/localization"},
    )

    assert status_response.json() == status_payload
    assert build_response.status_code == 200
    assert build_calls == [("victoria3", "I:/game/localization")]


def test_reference_library_manual_build_rejects_invalid_path(monkeypatch):
    monkeypatch.setattr(
        system_router.reference_library_service,
        "build",
        lambda *_args: (_ for _ in ()).throw(ValueError("wrong localization spelling")),
    )

    response = client.post(
        "/api/system/reference-library/build",
        json={"game_id": "stellaris", "localization_path": "I:/game/localization"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "wrong localization spelling"


def test_reference_library_job_routes_expose_persisted_task(monkeypatch):
    accepted = {"status": "accepted", "task_id": "reference-library-1"}
    task = {"task_id": "reference-library-1", "kind": "reference_library_maintenance", "status": "running"}
    calls = []
    monkeypatch.setattr(
        system_router.reference_library_service,
        "start_operations",
        lambda operations: calls.extend(operations) or accepted,
    )
    monkeypatch.setattr(system_router.reference_library_service, "get_task", lambda task_id: task if task_id == task["task_id"] else None)
    monkeypatch.setattr(task_state, "find_active_task_by_dedupe_key", lambda _key: task)

    start_response = client.post(
        "/api/system/reference-library/jobs",
        json={"operations": [{
            "game_id": "victoria3",
            "localization_path": "I:/game/localization",
            "action": "update",
        }]},
    )
    active_response = client.get("/api/system/reference-library/jobs/active")
    task_response = client.get("/api/system/reference-library/jobs/reference-library-1")

    assert start_response.json() == accepted
    assert calls == [{
        "game_id": "victoria3",
        "localization_path": "I:/game/localization",
        "action": "update",
    }]
    assert active_response.json() == task
    assert task_response.json() == task


def test_reference_library_delete_route_queues_scoped_removal(monkeypatch):
    calls = []
    monkeypatch.setattr(
        system_router.reference_library_service,
        "delete",
        lambda game_id: calls.append(game_id) or {"status": "accepted", "task_id": "delete-1"},
    )

    response = client.delete("/api/system/reference-library/libraries/ck3")

    assert response.status_code == 200
    assert response.json()["task_id"] == "delete-1"
    assert calls == ["ck3"]


def test_reset_db_endpoint_rebuilds_main_database(monkeypatch):
    removed_paths = []
    initialize_called = {"value": False}
    configured_repositories = []
    fake_engine = _FakeEngine()
    fake_archive_manager = _FakeArchiveManager()

    monkeypatch.setattr(system_router, "_remove_sqlite_family", removed_paths.append)
    monkeypatch.setattr(db_initializer, "initialize_database", lambda: initialize_called.__setitem__("value", True))
    monkeypatch.setattr(services, "archive_manager", fake_archive_manager)
    monkeypatch.setattr(
        task_state,
        "configure_repository",
        lambda repository, **kwargs: configured_repositories.append((repository, kwargs)),
    )
    if not hasattr(db_manager, "_async_engine"):
        db_manager._async_engine = None
    monkeypatch.setattr(db_manager, "_async_engine", fake_engine, raising=False)

    response = client.post("/api/system/reset-db")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert removed_paths == [system_router.REMIS_DB_PATH]
    assert initialize_called["value"] is True
    assert fake_archive_manager.closed is True
    assert fake_archive_manager._conn is None
    assert fake_engine.disposed is True
    assert not hasattr(db_manager, "_async_engine")
    assert len(configured_repositories) == 1
    configured_repository, configure_options = configured_repositories[0]
    assert os.path.normcase(os.path.normpath(configured_repository.db_path)) == os.path.normcase(
        os.path.normpath(system_router.REMIS_DB_PATH)
    )
    assert configure_options == {"hydrate": True, "replace": True}


def test_open_database_folder_opens_main_database_parent(monkeypatch, tmp_path):
    database_folder = tmp_path / "appdata"
    database_folder.mkdir()
    opened_paths = []
    monkeypatch.setattr(system_router, "REMIS_DB_PATH", str(database_folder / "remis.sqlite"))
    monkeypatch.setattr(system_router, "_open_directory_in_explorer", opened_paths.append)

    response = client.post("/api/system/open-database-folder")

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "database_file": "remis.sqlite",
    }
    assert opened_paths == [str(database_folder)]


def test_open_database_folder_reports_missing_parent(monkeypatch, tmp_path):
    missing_folder = tmp_path / "missing"
    monkeypatch.setattr(system_router, "REMIS_DB_PATH", str(missing_folder / "remis.sqlite"))

    response = client.post("/api/system/open-database-folder")

    assert response.status_code == 404
    assert response.json()["detail"] == "Database folder not found"


def test_save_and_read_file_are_limited_to_remis_roots(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    app_data_root = tmp_path / "appdata"
    outside_root = tmp_path / "outside"
    project_root.mkdir()
    app_data_root.mkdir()
    outside_root.mkdir()

    monkeypatch.setattr(system_router, "PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(system_router, "APP_DATA_DIR", str(app_data_root))

    allowed_file = project_root / "notes" / "safe.txt"
    save_response = client.post(
        "/api/system/save_file",
        json={"file_path": str(allowed_file), "content": "hello"},
    )

    assert save_response.status_code == 200
    assert allowed_file.read_text(encoding="utf-8-sig") == "hello"

    read_response = client.post(
        "/api/system/read_file",
        json={"file_path": str(allowed_file)},
    )

    assert read_response.status_code == 200
    assert read_response.json()["content"] == "hello"

    blocked_response = client.post(
        "/api/system/save_file",
        json={"file_path": str(outside_root / "blocked.txt"), "content": "nope"},
    )

    assert blocked_response.status_code == 403
    assert not (outside_root / "blocked.txt").exists()


def test_relative_system_file_paths_resolve_under_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    app_data_root = tmp_path / "appdata"
    project_root.mkdir()
    app_data_root.mkdir()

    monkeypatch.setattr(system_router, "PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(system_router, "APP_DATA_DIR", str(app_data_root))

    response = client.post(
        "/api/system/save_file",
        json={"file_path": "relative/safe.txt", "content": "relative ok"},
    )

    assert response.status_code == 200
    assert (project_root / "relative" / "safe.txt").read_text(encoding="utf-8-sig") == "relative ok"


def test_patch_file_is_limited_to_remis_roots(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    app_data_root = tmp_path / "appdata"
    outside_root = tmp_path / "outside"
    project_root.mkdir()
    app_data_root.mkdir()
    outside_root.mkdir()

    monkeypatch.setattr(system_router, "PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(system_router, "APP_DATA_DIR", str(app_data_root))

    loc_file = project_root / "localization" / "english" / "demo_l_english.yml"
    loc_file.parent.mkdir(parents=True)
    loc_file.write_text(' key:0 "Old"\n', encoding="utf-8-sig")

    response = client.post(
        "/api/system/patch_file",
        json={
            "file_path": str(loc_file),
            "entries": [{"key": "key", "value": "New", "line_number": 1}],
        },
    )

    assert response.status_code == 200
    assert 'key:0 "New"' in loc_file.read_text(encoding="utf-8-sig")

    outside_file = outside_root / "demo_l_english.yml"
    outside_file.write_text(' key:0 "Old"\n', encoding="utf-8-sig")
    blocked_response = client.post(
        "/api/system/patch_file",
        json={
            "file_path": str(outside_file),
            "entries": [{"key": "key", "value": "Blocked", "line_number": 1}],
        },
    )

    assert blocked_response.status_code == 403
    assert "Blocked" not in outside_file.read_text(encoding="utf-8-sig")


def test_system_file_paths_reject_symlink_escape(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    app_data_root = tmp_path / "appdata"
    outside_root = tmp_path / "outside"
    project_root.mkdir()
    app_data_root.mkdir()
    outside_root.mkdir()

    outside_file = outside_root / "secret.txt"
    outside_file.write_text("outside", encoding="utf-8-sig")
    linked_file = project_root / "linked.txt"
    try:
        linked_file.symlink_to(outside_file)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    monkeypatch.setattr(system_router, "PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(system_router, "APP_DATA_DIR", str(app_data_root))

    read_response = client.post(
        "/api/system/read_file",
        json={"file_path": str(linked_file)},
    )

    assert read_response.status_code == 403
