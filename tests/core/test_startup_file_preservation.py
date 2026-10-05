import json
import sqlite3

import pytest

from scripts import app_settings
from scripts.core import db_initializer


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("corrupt", [False, True])
def test_startup_preserves_existing_files_and_archive_when_main_db_is_fresh(tmp_path, monkeypatch, corrupt):
    app = tmp_path / "app"
    resources = tmp_path / "resources"
    for relative in ("demos/Demo/user.yml", "my_translation/demo-output/user.yml"):
        _write(app / relative, "user content")
        _write(resources / relative, "bundled content")
    _write(app / "demos/custom/extra.yml", "custom content")
    _write(app / "mods_cache.sqlite", "existing user archive")
    _write(resources / "assets/mods_cache_skeleton.sqlite", "bundled archive")
    if corrupt:
        _write(app / "remis.sqlite", "corrupt database")
    for key, value in {
        "APP_DATA_DIR": app, "RESOURCE_DIR": resources,
        "REMIS_DB_PATH": app / "remis.sqlite", "CONFIG_DIR": app / "config",
    }.items():
        monkeypatch.setattr(app_settings, key, str(value))
    monkeypatch.setattr(app_settings, "get_appdata_config_path", lambda: str(app / "config.json"))
    monkeypatch.setattr(db_initializer, "_install_steam_workshop_demo", lambda *_args: None)
    if corrupt:
        with pytest.raises(sqlite3.DatabaseError):
            db_initializer.initialize_database()
    else:
        db_initializer.initialize_database()
        db_initializer.initialize_database()
    for relative in ("demos/Demo/user.yml", "my_translation/demo-output/user.yml"):
        assert (app / relative).read_text(encoding="utf-8") == "user content"
    assert (app / "demos/custom/extra.yml").read_text(encoding="utf-8") == "custom content"
    assert (app / "mods_cache.sqlite").read_text(encoding="utf-8") == "existing user archive"


def test_development_demo_sync_preserves_edited_files_and_fills_missing_files(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "demos"
    relative = "Test_Project_Remis_Vic3/localization.yml"
    _write(source / relative, "bundled content")
    _write(source / "Test_Project_Remis_Vic3/missing.yml", "missing content")
    _write(dest / relative, "user content")
    assert db_initializer.sync_development_demo_sources(str(source), str(dest))
    assert (dest / relative).read_text(encoding="utf-8") == "user content"
    assert (dest / "Test_Project_Remis_Vic3/missing.yml").read_text(encoding="utf-8") == "missing content"


def test_hydration_preserves_user_text_and_external_paths(tmp_path):
    path = tmp_path / "my_translation/user-output/.remis_project.json"
    payload = {
        "source_path": "{{BUNDLED_DEMO_ROOT}}/Demo",
        "config": {"translation_dirs": [
            "J:\\V3_Mod_Localization_Factory\\my_translation\\Multilanguage-Test_Project_Remis_Vic3",
            "C:\\source_mod\\custom",
        ]},
        "notes": [{"content": "keep \\n /source_mod/ {{DEMO_ROOT}}"}],
        "name": "Custom /source_mod/ title",
        "unknown": {"source_path": "{{DEMO_ROOT}}", "backslash": "\\"},
    }
    _write(path, json.dumps(payload))
    db_initializer.hydrate_json_configs(str(tmp_path))
    hydrated = json.loads(path.read_text(encoding="utf-8"))
    assert hydrated["source_path"] == f"{tmp_path.as_posix()}/demos/Demo"
    assert hydrated["config"]["translation_dirs"] == [
        f"{tmp_path.as_posix()}/my_translation/en-Test_Project_Remis_Vic3",
        "C:\\source_mod\\custom",
    ]
    for key in ("notes", "name", "unknown"):
        assert hydrated[key] == payload[key]
    before = path.read_bytes()
    db_initializer.hydrate_json_configs(str(tmp_path))
    assert path.read_bytes() == before


def test_hydration_failed_atomic_replace_preserves_original(tmp_path, monkeypatch):
    from scripts.core import demo_config_hydration
    path = tmp_path / "demos/Demo/.remis_project.json"
    _write(path, '{"source_path": "{{BUNDLED_DEMO_ROOT}}/Demo"}')
    before = path.read_bytes()
    def reject_replace(*_args):
        raise OSError("injected replace failure")
    monkeypatch.setattr(demo_config_hydration.os, "replace", reject_replace)
    db_initializer.hydrate_json_configs(str(tmp_path))
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]
