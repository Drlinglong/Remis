import pytest
import os
from unittest.mock import MagicMock, AsyncMock
from scripts.core.project_manager import ProjectManager

@pytest.fixture
async def mock_project_manager(tmp_path):
    # Mock Repository
    repo = MagicMock()
    test_project = {
        "project_id": "test-p1",
        "name": "TestMod",
        "game_id": "victoria3",
        "source_language": "en"
    }
    mock_p = MagicMock()
    mock_p.model_dump.return_value = test_project
    repo.get_project = AsyncMock(return_value=mock_p)
    
    # Mock Archive Manager and Service
    from scripts.core.archive_manager import ArchiveManager
    from scripts.core.services.translation_archive_service import TranslationArchiveService
    
    db_path = tmp_path / "cache.sqlite"
    am = ArchiveManager()
    # Force test DB path
    import scripts.core.archive_manager as am_module
    original_db_path = am_module.MODS_CACHE_DB_PATH
    am_module.MODS_CACHE_DB_PATH = str(db_path)
    
    am.initialize_database()
    
    # Pre-seed some data so check-archive passes
    mod_id = am.get_or_create_mod_entry("TestMod", "test-p1")
    version_id = am.create_source_version(mod_id, [{
        "filename": "test.yml",
        "key_map": ["key.1"],
        "texts_to_translate": ["Hello"]
    }])
    am.archive_translated_results(version_id, {"test.yml": ["你好"]}, [{"filename": "test.yml", "key_map": ["key.1"]}], "zh-CN")
    
    service = TranslationArchiveService(am=am)
    
    pm = ProjectManager(project_repository=repo, archive_service=service)
    
    yield pm, am
    
    am.close()
    am_module.MODS_CACHE_DB_PATH = original_db_path

@pytest.mark.asyncio
async def test_orchestration_check_archive(mock_project_manager):
    pm, am = mock_project_manager
    
    # Test check_project_archive orchestration
    # This should find the pre-seeded data
    result = await pm.check_project_archive("test-p1")
    
    assert result["exists"] is True
    assert "version_id" in result
    assert result["target_language"] == "zh-CN"

@pytest.mark.asyncio
async def test_orchestration_not_found(mock_project_manager):
    pm, am = mock_project_manager
    pm.repository.get_project = AsyncMock(return_value=None)
    
    result = await pm.check_project_archive("non-existent")
    assert result["exists"] is False
    assert result["reason"] == "Project not found"
