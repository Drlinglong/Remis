"""The project screen must use the same CSV discovery as Agent clients."""
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.routers import game_support


def test_gui_game_support_reports_real_mars_csv_counts_and_package_capability(tmp_path, monkeypatch):
    (tmp_path / "ModTexts.csv").write_text(
        "sep=,\nID,Text,Translation,VoiceActor,Context\n100,Ore,,,resource\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(game_support.project_manager, "get_project", AsyncMock(return_value={
        "game_id": "surviving_mars", "source_path": str(tmp_path), "source_language": "en",
    }))
    app = FastAPI()
    app.include_router(game_support.router)
    response = TestClient(app).get("/api/projects/mars-project/game-support")
    assert response.status_code == 200
    result = response.json()
    assert result["recognized_resource_count"] == 1
    assert result["recognized_entry_count"] == 1
    assert result["resources"][0]["entry_count"] == 1
    assert result["capabilities"]["independent_translation_mod"] is True
    assert result["support"]["translation_package"]["supported"] is True
    assert result["runtime_verified"] is False
