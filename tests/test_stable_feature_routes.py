from fastapi.testclient import TestClient

from scripts.web_server import app


def test_stable_app_does_not_register_project_archive_routes():
    client = TestClient(app)

    assert client.get("/api/context/releases/project-1/latest").status_code == 404
    assert client.get("/api/context/tree-v2/projects/project-1/latest").status_code == 404
    assert client.get("/api/agent/context/releases/project-1/latest").status_code == 404
