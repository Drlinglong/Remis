from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from scripts.routers import project_watches as project_watches_router
from scripts.web_server import app


@pytest.fixture
def mock_project_watch_service(monkeypatch):
    service = MagicMock()
    service.list_watches = AsyncMock(return_value=[])
    service.create_watch = AsyncMock()
    service.update_watch = AsyncMock()
    service.delete_watch = AsyncMock()
    service.scan_watch = AsyncMock()
    service.scan_watches = AsyncMock()
    service.scan_due_watches = AsyncMock(return_value=[])
    monkeypatch.setattr(project_watches_router, "project_watch_service", service)
    return service


def test_update_project_watch_excludes_unset_fields(mock_project_watch_service):
    mock_project_watch_service.update_watch.return_value = {
        "watch_id": "watch-1",
        "name": "Renamed",
        "enabled": False,
    }

    client = TestClient(app)
    response = client.put("/api/project-watches/watch-1", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    mock_project_watch_service.update_watch.assert_awaited_once_with(
        "watch-1",
        {"enabled": False},
    )


def test_update_project_watch_maps_missing_watch_to_404(mock_project_watch_service):
    mock_project_watch_service.update_watch.side_effect = ValueError(
        "Watch not found: watch-1"
    )

    client = TestClient(app)
    response = client.put(
        "/api/project-watches/watch-1",
        json={"name": "Missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Watch not found: watch-1"


def test_create_project_watch_maps_validation_error_to_400(
    mock_project_watch_service,
):
    mock_project_watch_service.create_watch.side_effect = ValueError("Path is required")

    client = TestClient(app)
    response = client.post(
        "/api/project-watches",
        json={"name": "Broken", "path": ""},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Path is required"


def test_scan_project_watches_forwards_requested_ids(mock_project_watch_service):
    mock_project_watch_service.scan_watches.return_value = [
        {"watch_id": "watch-a", "status": "clean"},
        {"watch_id": "watch-b", "status": "changed"},
    ]

    client = TestClient(app)
    response = client.post(
        "/api/project-watches/scan",
        json={"watch_ids": ["watch-a", "watch-b"]},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"watch_id": "watch-a", "status": "clean"},
        {"watch_id": "watch-b", "status": "changed"},
    ]
    mock_project_watch_service.scan_watches.assert_awaited_once_with(
        ["watch-a", "watch-b"]
    )


def test_scan_project_watch_maps_missing_watch_to_404(mock_project_watch_service):
    mock_project_watch_service.scan_watch.side_effect = ValueError(
        "Watch not found: watch-1"
    )

    client = TestClient(app)
    response = client.post("/api/project-watches/watch-1/scan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Watch not found: watch-1"
