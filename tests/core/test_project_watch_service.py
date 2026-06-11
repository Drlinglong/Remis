import os
import time

import pytest
import pytest_asyncio

from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.repositories.project_watch_repository import ProjectWatchRepository
from scripts.core.services.project_watch_service import ProjectWatchService


def write_loc(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest_asyncio.fixture
async def watch_service(tmp_path):
    db_path = str(tmp_path / "watch.sqlite")
    from scripts.core.db_migrations import migrate_main_database
    from scripts.core.db_manager import db_manager

    original_path = db_manager.db_path
    db_manager.db_path = db_path
    if hasattr(db_manager, "_async_engine"):
        await db_manager._async_engine.dispose()
        del db_manager._async_engine
    migrate_main_database(db_path)
    service = ProjectWatchService(
        watch_repository=ProjectWatchRepository(db_path),
        project_repository=ProjectRepository(db_path),
    )
    yield service
    if hasattr(db_manager, "_async_engine"):
        await db_manager._async_engine.dispose()
        del db_manager._async_engine
    db_manager.db_path = original_path


@pytest.mark.asyncio
async def test_project_watch_baseline_then_detects_added_modified_deleted(watch_service, tmp_path):
    mod_root = tmp_path / "mod"
    write_loc(mod_root / "localization" / "english" / "demo_l_english.yml", "l_english:\n key:0 \"Old\"\n")

    watch = await watch_service.create_watch({
        "name": "Demo Mod",
        "path": str(mod_root),
        "enabled": True,
        "scan_interval_minutes": 30,
    })

    baseline = await watch_service.scan_watch(watch["watch_id"])
    assert baseline["baseline_created"] is True
    assert baseline["changed_count"] == 0

    original_file = mod_root / "localization" / "english" / "demo_l_english.yml"
    write_loc(original_file, "l_english:\n key:0 \"New\"\n")
    write_loc(mod_root / "localization" / "english" / "added_l_english.yml", "l_english:\n added:0 \"Added\"\n")
    original_file.unlink()

    result = await watch_service.scan_watch(watch["watch_id"])

    assert result["baseline_created"] is False
    assert result["added_count"] == 1
    assert result["deleted_count"] == 1


@pytest.mark.asyncio
async def test_project_watch_empty_localization_scan_does_not_create_baseline(watch_service, tmp_path):
    mod_root = tmp_path / "mod"
    mod_root.mkdir()

    watch = await watch_service.create_watch({"name": "Empty Mod", "path": str(mod_root)})
    result = await watch_service.scan_watch(watch["watch_id"])

    assert result["status"] == "no_localization"
    assert result["baseline_created"] is False
    assert result["scanned_file_count"] == 0


@pytest.mark.asyncio
async def test_project_watch_preserves_app_data_demo_path_when_project_root_has_same_folder(watch_service, tmp_path, monkeypatch):
    import scripts.app_settings as app_settings

    app_data_root = tmp_path / "AppData" / "RemisModFactoryDev"
    project_root = tmp_path / "repo"
    app_data_mod = app_data_root / "demos" / "Test_Project_Remis_Vic3"
    project_mod = project_root / "source_mod" / "Test_Project_Remis_Vic3"
    write_loc(app_data_mod / "localization" / "simp_chinese" / "demo.yml", "l_simp_chinese:\n key:0 \"AppData\"\n")
    write_loc(project_mod / "localization" / "simp_chinese" / "demo.yml", "l_simp_chinese:\n key:0 \"ProjectRoot\"\n")

    monkeypatch.setattr(app_settings, "APP_DATA_DIR", str(app_data_root).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "PROJECT_ROOT", str(project_root).replace("\\", "/"))

    watch = await watch_service.create_watch({"name": "Demo Mod", "path": str(app_data_mod)})
    baseline = await watch_service.scan_watch(watch["watch_id"])

    assert watch["path"] == str(app_data_mod.resolve())
    assert baseline["root_path"] == str(app_data_mod.resolve())
    assert baseline["scanned_file_count"] == 1

    write_loc(app_data_mod / "localization" / "simp_chinese" / "demo.yml", "l_simp_chinese:\n key:0 \"Changed!\"\n")
    result = await watch_service.scan_watch(watch["watch_id"])

    assert result["modified_count"] == 1


@pytest.mark.asyncio
async def test_project_watch_sha256_avoids_false_positive_when_only_mtime_changes(watch_service, tmp_path):
    mod_root = tmp_path / "mod"
    loc_file = mod_root / "localisation" / "english" / "demo_l_english.yml"
    write_loc(loc_file, "l_english:\n key:0 \"Same\"\n")

    watch = await watch_service.create_watch({"name": "Demo Mod", "path": str(mod_root)})
    await watch_service.scan_watch(watch["watch_id"])

    now = time.time() + 5
    os.utime(loc_file, (now, now))
    result = await watch_service.scan_watch(watch["watch_id"])

    assert result["changed_count"] == 0


@pytest.mark.asyncio
async def test_project_watch_sha256_detects_same_size_content_change(watch_service, tmp_path):
    mod_root = tmp_path / "mod"
    loc_file = mod_root / "localization" / "english" / "demo_l_english.yml"
    write_loc(loc_file, "l_english:\n key:0 \"AAAA\"\n")

    watch = await watch_service.create_watch({"name": "Demo Mod", "path": str(mod_root)})
    await watch_service.scan_watch(watch["watch_id"])

    write_loc(loc_file, "l_english:\n key:0 \"BBBB\"\n")
    result = await watch_service.scan_watch(watch["watch_id"])

    assert result["modified_count"] == 1


@pytest.mark.asyncio
async def test_project_watch_keeps_change_pending_after_followup_scan(watch_service, tmp_path):
    mod_root = tmp_path / "mod"
    loc_file = mod_root / "localization" / "english" / "demo_l_english.yml"
    write_loc(loc_file, "l_english:\n key:0 \"Old\"\n")

    watch = await watch_service.create_watch({"name": "Demo Mod", "path": str(mod_root), "enabled": True, "scan_interval_minutes": 1})
    await watch_service.scan_watch(watch["watch_id"])

    write_loc(loc_file, "l_english:\n key:0 \"New\"\n")
    changed_result = await watch_service.scan_watch(watch["watch_id"])
    followup_result = await watch_service.scan_watch(watch["watch_id"])

    assert changed_result["changed_count"] == 1
    assert followup_result["status"] == "changed"
    assert followup_result["changed_count"] == 1
    assert followup_result["pending_acknowledgement"] is True


@pytest.mark.asyncio
async def test_project_watch_ignores_non_localization_files(watch_service, tmp_path):
    mod_root = tmp_path / "mod"
    write_loc(mod_root / "localization" / "english" / "demo_l_english.yml", "l_english:\n key:0 \"Same\"\n")
    write_loc(mod_root / "README.txt", "first")

    watch = await watch_service.create_watch({"name": "Demo Mod", "path": str(mod_root)})
    await watch_service.scan_watch(watch["watch_id"])

    write_loc(mod_root / "README.txt", "second")
    result = await watch_service.scan_watch(watch["watch_id"])

    assert result["changed_count"] == 0
