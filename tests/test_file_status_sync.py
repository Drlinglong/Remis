import pytest
import os
import json
import shutil
import tempfile
import asyncio
from sqlmodel import create_engine, SQLModel
from scripts.core.project_manager import ProjectManager
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.db_models import Project, ProjectFile
from scripts.core.db_manager import db_manager

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
async def project_manager(test_db_path):
    # 1. Setup DB Schema (Sync is fine here for setup)
    setup_engine = create_engine(f"sqlite:///{test_db_path}")
    SQLModel.metadata.create_all(setup_engine)
    
    from sqlalchemy import text
    with setup_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS activity_log (
                log_id TEXT PRIMARY KEY,
                project_id TEXT,
                type TEXT,
                description TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    setup_engine.dispose()
    
    # 2. Configure DB Manager to use test DB
    # Ensure db_manager singleton points to our test DB
    original_path = db_manager.db_path
    db_manager.db_path = test_db_path
    # Force re-creation of async engine
    if hasattr(db_manager, '_async_engine'):
        del db_manager._async_engine

    # 3. Initialize Repo and Manager
    repo = ProjectRepository(test_db_path)
    pm = ProjectManager(project_repository=repo, db_path=test_db_path)
    
    yield pm
    
    # Cleanup
    if hasattr(db_manager, '_async_engine'):
        await db_manager._async_engine.dispose()
        del db_manager._async_engine
    db_manager.db_path = original_path

@pytest.mark.asyncio
async def test_update_file_status_with_kanban_sync(project_manager, temp_project_dir):
    project_id = "test-prod-id"
    file_id = "test-file-id"
    source_path = temp_project_dir.replace("\\", "/") # Normalize for DB
    
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
    await project_manager.repository.create_project(proj)
    
    # Create DB entry for file
    file_record = ProjectFile(
        file_id=file_id,
        project_id=project_id,
        file_path="localization/test.yml",
        status="todo",
        original_key_count=10,
        line_count=20,
        file_type="source"
    )
    await project_manager.repository.batch_upsert_files([file_record.model_dump()])

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
    files = await project_manager.get_project_files(project_id)
    assert len(files) == 1
    assert files[0]['status'] == new_status

    # 4. Verification - Kanban JSON
    with open(kanban_path, 'r', encoding='utf-8') as f:
        updated_data = json.load(f)
        # The manager aligns task key with file_id logic if needed, 
        # but here we used task-1, so it might have re-keyed it to file_id (as per manager logic)
        # or just updated it if key matches.
        # Original logic: if key != file_id, pops and re-inserts.
        assert updated_data["kanban"]["tasks"][file_id]["status"] == new_status

    # 5. Verification - Activity Log
    logs = await project_manager.repository.get_recent_logs(limit=5)
    assert any(log['project_id'] == project_id and log['type'] == 'file_update' for log in logs)
    assert any(new_status in log['description'] for log in logs)

