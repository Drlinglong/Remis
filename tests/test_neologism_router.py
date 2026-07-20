from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from scripts.routers import neologism as neologism_router
from scripts.web_server import app


client = TestClient(app)


@pytest.mark.parametrize(
    ("source_language", "target_language"),
    [
        ("zh-CN", "zh-CN"),
        ("simp_chinese", "zh-CN"),
        ("english", "en"),
    ],
)
def test_mining_rejects_project_source_language_as_target(
    monkeypatch,
    source_language,
    target_language,
):
    monkeypatch.setattr(
        neologism_router.project_manager,
        "get_project",
        AsyncMock(return_value={
            "project_id": "project-1",
            "name": "Demo",
            "game_id": "victoria3",
            "source_language": source_language,
        }),
    )

    response = client.post("/api/neologisms/mine", json={
        "project_id": "project-1",
        "api_provider": "unused-because-validation-runs-first",
        "target_lang": target_language,
    })

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Target language must be different from the project source language."
    )
