from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.routers import context_archive as context_archive_router


app = FastAPI()
app.include_router(context_archive_router.router)
client = TestClient(app)


def test_archive_removal_requires_matching_project_confirmation(monkeypatch):
    monkeypatch.setattr(
        context_archive_router.project_manager,
        "get_project",
        AsyncMock(return_value={"project_id": "project-1", "name": "Horizon"}),
    )

    response = client.request(
        "DELETE",
        "/api/context/projects/project-1/archive",
        json={"project_name": "Wrong project", "approved": True},
    )

    assert response.status_code == 409
    assert "does not match" in response.json()["detail"]


def test_archive_removal_preserves_project_assets(monkeypatch):
    monkeypatch.setattr(
        context_archive_router.project_manager,
        "get_project",
        AsyncMock(return_value={"project_id": "project-1", "name": "Horizon"}),
    )
    monkeypatch.setattr(
        context_archive_router.context_archive_removal_service,
        "remove",
        lambda project_id: {
            "removed": project_id == "project-1",
            "counts": {"releases": 1, "analysis_runs": 1},
        },
    )
    monkeypatch.setattr(
        context_archive_router.task_state,
        "find_active_task_by_dedupe_key",
        lambda _key: None,
    )

    response = client.request(
        "DELETE",
        "/api/context/projects/project-1/archive",
        json={"project_name": "Horizon", "approved": True},
    )

    assert response.status_code == 200
    assert response.json()["removed_counts"] == {"releases": 1, "analysis_runs": 1}
    assert response.json()["preserved"] == [
        "project",
        "source_files",
        "project_glossary",
        "neologism_candidates",
    ]
