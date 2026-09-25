from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_preview_is_bound_to_project_and_discovered_source(tmp_path, monkeypatch):
    from scripts.routers import game_support
    source = tmp_path / "outside-remis" / "media/lua/shared/Translate/EN/UI.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b'{"Greeting":"Hello"}')
    root = tmp_path / "outside-remis"
    (root / "mod.info").write_text("id=preview.fixture\n", encoding="utf-8")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("private unrelated content", encoding="utf-8")
    project = {"project_id": "p", "game_id": "project_zomboid", "source_path": str(root)}
    manager = SimpleNamespace(get_project=AsyncMock(return_value=project),
        get_project_files=AsyncMock(return_value=[
            {"file_id": "source", "file_path": str(source), "file_type": "source"},
            {"file_id": "stale", "file_path": str(unrelated), "file_type": "source"},
            {"file_id": "translation", "file_path": str(source), "file_type": "translation"},
        ]))
    monkeypatch.setattr(game_support, "project_manager", manager)
    app = FastAPI()
    app.include_router(game_support.router)
    client = TestClient(app)
    response = client.get("/api/projects/p/game-resources/source/preview")
    assert response.status_code == 200
    assert response.json()["content"] == '{"Greeting":"Hello"}'
    assert response.json()["read_only"] is True
    for file_id in ("stale", "translation", "missing"):
        assert client.get(f"/api/projects/p/game-resources/{file_id}/preview").status_code == 404
    manager.get_project.return_value = None
    assert client.get("/api/projects/other/game-resources/source/preview").status_code == 404
