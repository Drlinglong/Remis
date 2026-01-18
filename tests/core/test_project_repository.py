
import pytest
import pytest_asyncio
import os
import shutil
from datetime import datetime
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.db_models import Project, ProjectFile
from scripts.core.db_manager import DatabaseConnectionManager

# Setup a temporary DB for testing
TEST_DB_PATH = "test_projects_repo.db"

@pytest_asyncio.fixture
async def repo():
    # Force Reset Singleton
    if DatabaseConnectionManager._instance:
        if hasattr(DatabaseConnectionManager._instance, '_async_engine'):
             await DatabaseConnectionManager._instance._async_engine.dispose()
        DatabaseConnectionManager._instance = None
        
    # Setup
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass
    
    # Init Schema
    from sqlmodel import SQLModel
    db_manager = DatabaseConnectionManager(TEST_DB_PATH)
    engine = db_manager.get_async_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    repository = ProjectRepository(TEST_DB_PATH)
    yield repository
    
    # Teardown
    await engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass

@pytest.mark.asyncio
async def test_create_and_get_project(repo):
    # Arrange
    project_id = "test_proj_1"
    new_project = Project(
        project_id=project_id,
        name="Test Project 1",
        game_id="stellaris",
        source_path="/tmp/source",
        source_language="english",
        status="active",
        created_at=datetime.now().isoformat(),
        last_modified=datetime.now().isoformat()
    )
    
    # Act
    created = await repo.create_project(new_project)
    fetched = await repo.get_project(project_id)
    
    # Assert
    assert created.project_id == project_id
    assert fetched is not None
    assert fetched.project_id == project_id
    assert fetched.name == "Test Project 1"
    assert fetched.source_language == "english"

@pytest.mark.asyncio
async def test_update_project_metadata(repo):
    # Arrange
    project_id = "test_proj_meta"
    new_project = Project(
        project_id=project_id,
        name="Meta Test",
        game_id="stellaris",
        source_path="/tmp/source_meta",
        source_language="english",
        status="active"
    )
    await repo.create_project(new_project)
    
    # Act
    await repo.update_project_metadata(project_id, "hoi4", "german")
    fetched = await repo.get_project(project_id)
    
    # Assert
    assert fetched.game_id == "hoi4"
    assert fetched.source_language == "german"

@pytest.mark.asyncio
async def test_batch_upsert_files(repo):
    # Arrange
    project_id = "test_proj_files"
    await repo.create_project(Project(
        project_id=project_id,
        name="Files Test",
        game_id="stellaris",
        source_path="/tmp/source_files",
        source_language="english"
    ))
    
    files_data = [
        {
            "file_id": "f1",
            "project_id": project_id,
            "file_path": "/tmp/source_files/f1.yml",
            "status": "todo",
            "original_key_count": 10,
            "line_count": 100,
            "file_type": "source"
        },
        {
            "file_id": "f2",
            "project_id": project_id,
            "file_path": "/tmp/source_files/f2.yml",
            "status": "done",
            "original_key_count": 20,
            "line_count": 200,
            "file_type": "translation"
        }
    ]
    
    # Act
    await repo.batch_upsert_files(files_data)
    files = await repo.get_project_files(project_id)
    
    # Assert
    assert len(files) == 2
    f1 = next(f for f in files if f.file_id == "f1")
    assert f1.status == "todo"
    assert f1.original_key_count == 10

@pytest.mark.asyncio
async def test_get_dashboard_stats(repo):
    # Arrange
    # Project 1: Active, 10 keys todo
    p1 = Project(project_id="p1", name="P1", game_id="stellaris", source_path="/p1", source_language="en", status="active")
    await repo.create_project(p1)
    
    # Project 2: Archived, 0 keys
    p2 = Project(project_id="p2", name="P2", game_id="hoi4", source_path="/p2", source_language="en", status="archived")
    await repo.create_project(p2)
    
    files = [
        {"file_id": "f1", "project_id": "p1", "file_path": "/p1/f1", "status": "todo", "original_key_count": 10, "line_count": 10, "file_type": "source"},
        {"file_id": "f2", "project_id": "p1", "file_path": "/p1/f2", "status": "done", "original_key_count": 5, "line_count": 5, "file_type": "source"}
    ]
    await repo.batch_upsert_files(files)
    
    # Act
    stats = await repo.get_dashboard_stats()
    
    # Assert
    # total_projects = 2
    assert stats["total_projects"] == 2
    # active_projects = 1
    assert stats["active_projects"] == 1
    # total_files = 2
    assert stats["total_files"] == 2
    # total_keys = 15 (10 + 5)
    assert stats["total_keys"] == 15
    # translated_keys = 5 (from status='done')
    assert stats["translated_keys"] == 5
    # completion_rate = 5/15 = 33.3%
    assert 33.0 < stats["completion_rate"] < 34.0
    
    # Game distribution
    dist = stats["game_distribution"]
    msg = f"Distribution: {dist}"
    # Expect: [{'name': 'stellaris', 'value': 1}, {'name': 'hoi4', 'value': 1}] (order may vary)
    assert len(dist) == 2, msg
    assert any(d['name'] == 'stellaris' and d['value'] == 1 for d in dist), msg

