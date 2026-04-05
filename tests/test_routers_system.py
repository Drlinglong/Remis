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
