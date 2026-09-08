from scripts.web_server import app


def test_stable_app_registers_governed_project_archive_routes():
    paths = app.openapi()["paths"]

    assert "/api/context/releases/{project_id}/latest" in paths
    assert "/api/context/tree-v2/projects/{project_id}/latest" in paths
    assert "/api/agent/context/releases/{project_id}/latest" in paths
