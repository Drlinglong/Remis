from fastapi.testclient import TestClient

from scripts.web_server import app
from scripts.routers import system as system_router
from scripts.shared import services
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


def test_reset_db_endpoint_rebuilds_main_database(monkeypatch):
    removed_paths = []
    initialize_called = {"value": False}
    fake_engine = _FakeEngine()
    fake_archive_manager = _FakeArchiveManager()

    monkeypatch.setattr(system_router, "_remove_sqlite_family", removed_paths.append)
    monkeypatch.setattr(db_initializer, "initialize_database", lambda: initialize_called.__setitem__("value", True))
    monkeypatch.setattr(services, "archive_manager", fake_archive_manager)
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
