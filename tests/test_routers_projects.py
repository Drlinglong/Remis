import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from scripts.web_server import app

# We Mock the project_manager in the router module
@pytest.fixture
def mock_project_manager():
    with patch("scripts.routers.projects.project_manager") as mock:
        yield mock

def test_read_projects(mock_project_manager):
    # Setup mock return value
    mock_project_manager.get_projects.return_value = [
        {"project_id": "1", "name": "Test Project", "status": "active"}
    ]
    
    client = TestClient(app)
    response = client.get("/api/projects")
    
    assert response.status_code == 200
    assert response.json() == [{"project_id": "1", "name": "Test Project", "status": "active"}]
    mock_project_manager.get_projects.assert_called_once()

def test_create_project_invalid_path(mock_project_manager):
    # The router checks os.path.exists before calling manager.create_project
    # So this tests the Router's validation logic which relies on real filesystem (which says path doesn't exist)
    client = TestClient(app)
    response = client.post("/api/project/create", json={
        "name": "Test Project",
        "folder_path": "C:/NonExistentPath/Mod",
        "game_id": "stellaris",
        "source_language": "english"
    })
    
    assert response.status_code == 404
