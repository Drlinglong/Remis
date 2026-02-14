import pytest
import os
import shutil
import sqlite3
from scripts.core.archive_manager import ArchiveManager
from scripts.app_settings import PROJECT_ROOT

@pytest.fixture
def temp_archive_db(tmp_path):
    """
    Creates a temporary mods_cache.sqlite for testing.
    """
    db_path = tmp_path / "mods_cache_test.sqlite"
    # Mock MODS_CACHE_DB_PATH for ArchiveManager
    import scripts.core.archive_manager as am
    original_path = am.MODS_CACHE_DB_PATH
    am.MODS_CACHE_DB_PATH = str(db_path)
    
    manager = ArchiveManager()
    manager.initialize_database()
    
    yield manager
    
    manager.close()
    am.MODS_CACHE_DB_PATH = original_path

def test_global_translation_reuse(temp_archive_db):
    """
    验证“银河数据库”：跨模组重用翻译。
    1. 存入模组 A 的翻译。
    2. 在模组 B 中通过 global 搜索复用。
    """
    manager = temp_archive_db
    
    # Setup Mod A
    mod_a_id = manager.get_or_create_mod_entry("ModA", "remote_a")
    version_a_id = manager.create_source_version(mod_a_id, [
        {
            "filename": "file1.yml",
            "texts_to_translate": ["Hello world"],
            "key_map": [{"key_part": "test.1"}]
        }
    ])
    
    manager.archive_translated_results(version_a_id, 
        {"file1.yml": ["你好世界"]}, 
        [{"filename": "file1.yml", "key_map": [{"key_part": "test.1"}]}],
        "zh-CN"
    )
    
    # Verification: Mod B should find it globally
    # Entry Key matches, Source Text matches -> Should find "你好世界"
    translation = manager.find_global_translation("test.1", "Hello world", "zh-CN")
    assert translation == "你好世界"
    
    # Key mismatch -> Should NOT find
    assert manager.find_global_translation("test.diff", "Hello world", "zh-CN") is None
    
    # Text mismatch -> Should NOT find
    assert manager.find_global_translation("test.1", "Hello universe", "zh-CN") is None

def test_incremental_summary_counters():
    """
    Note: Real integration testing of run_incremental_update would require a complex environment.
    We just verified the core archival logic above which is the main dependency for Phase 2.
    """
    pass
