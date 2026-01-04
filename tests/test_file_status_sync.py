import pytest
import os
import json
import shutil
import tempfile
from scripts.core.project_manager import ProjectManager
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.schemas.project import Project, ProjectFile

@pytest.fixture
def temp_project_dir():
    # Use a temporary directory for the project source
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def test_db_path():
    # Use a temporary database
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def project_manager(test_db_path):
    # Initialize repository and manager with test DB
    repo = ProjectRepository(test_db_path)
    # Repo creates tables on first connection if they don't exist
    # (Actually repository._get_connection ensures tables exist via schema injection usually)
    # ProjectRepository does NOT have auto-migration in __init__. 
    # Let's ensure tables exist.
    import sqlite3
    conn = sqlite3.connect(test_db_path)
    # Very basic schema for tests
    conn.execute("""
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT,
            game_id TEXT,
            source_path TEXT,
            source_language TEXT,
            status TEXT,
            created_at TEXT,
            last_modified TEXT,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE project_files (
            file_id TEXT PRIMARY KEY,
            project_id TEXT,
            file_path TEXT,
            status TEXT,
            original_key_count INTEGER,
            line_count INTEGER,
            file_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE activity_log (
            log_id TEXT PRIMARY KEY,
            project_id TEXT,
            type TEXT,
            description TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    return ProjectManager(project_repository=repo, db_path=test_db_path)

import asyncio

def test_update_file_status_with_kanban_sync(project_manager, temp_project_dir):
    async def run_test():
        # ... existing test logic ...
        project_id = "test-prod-id"
        file_id = "test-file-id"
        source_path = temp_project_dir
        
        # Create DB entry for project
        proj = Project(
            project_id=project_id,
            name="Test Project",
            game_id="stellaris",
            source_path=source_path,
            source_language="english",
            status="active",
            created_at="2024-01-01",
            last_modified="2024-01-01"
        )
        project_manager.repository.create_project(proj)
        
        # Create DB entry for file
        file_path = "localization/test.yml"
        # We need a manual insert because repo might not have add_file
        import sqlite3
        conn = sqlite3.connect(project_manager.db_path)
        conn.execute(
            "INSERT INTO project_files (file_id, project_id, file_path, status, original_key_count, line_count, file_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_id, project_id, file_path, "todo", 10, 20, "source")
        )
        conn.commit()
        conn.close()

        # Create Kanban JSON
        kanban_path = os.path.join(source_path, ".remis_project.json")
        kanban_data = {
            "tasks": {
                "task-1": {
                    "id": file_id,
                    "type": "file",
                    "title": "test.yml",
                    "status": "todo"
                }
            },
            "columns": ["todo", "in_progress", "proofreading", "paused", "done"]
        }
        with open(kanban_path, 'w', encoding='utf-8') as f:
            json.dump({"kanban": kanban_data}, f)

        # 2. Execution
        new_status = "in_progress"
        await project_manager.update_file_status_with_kanban_sync(project_id, file_id, new_status)

        # 3. Verification - DB
        files = project_manager.get_project_files(project_id)
        assert len(files) == 1
        assert files[0]['status'] == new_status

        # 4. Verification - Kanban JSON
        with open(kanban_path, 'r', encoding='utf-8') as f:
            updated_data = json.load(f)
            # The code now aligns the task key with file_id
            assert updated_data["kanban"]["tasks"][file_id]["status"] == new_status

        # 5. Verification - Activity Log
        logs = project_manager.repository.get_recent_logs(limit=5)
        assert any(log['project_id'] == project_id and log['type'] == 'file_update' for log in logs)
        assert any(new_status in log['description'] for log in logs)

    asyncio.run(run_test())
