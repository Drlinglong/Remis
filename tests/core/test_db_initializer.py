import os
import sqlite3

from scripts import app_settings
from scripts.core.db_initializer import initialize_database, run_projects_db_migrations


def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def test_initialize_database_builds_schema_and_imports_seed(tmp_path, monkeypatch):
    app_data_dir = tmp_path / "appdata"
    resource_dir = tmp_path / "resources"
    db_path = app_data_dir / "remis.sqlite"
    config_dir = app_data_dir / "config"
    config_path = app_data_dir / "config.json"

    _write_file(
        resource_dir / "data" / "seed_data_main.sql",
        """
        BEGIN TRANSACTION;
        INSERT INTO glossaries (glossary_id, game_id, name, description, version, is_main, sources, raw_metadata)
        VALUES (1, 'eu5', 'Demo Glossary', 'demo', '1', 1, '["demo"]', '{"kind": "demo"}');
        INSERT INTO entries (entry_id, glossary_id, translations, abbreviations, variants, raw_metadata)
        VALUES ('entry_1', 1, '{"en":"Hello","zh-CN":"你好"}', '{}', '{}', '{}');
        COMMIT;
        """,
    )
    _write_file(
        resource_dir / "data" / "seed_data_projects.sql",
        """
        BEGIN TRANSACTION;
        INSERT INTO projects (project_id, name, game_id, source_path, target_path, source_language, status, created_at, last_modified, last_activity_type, last_activity_desc, notes)
        VALUES ('proj_1', 'Demo Project', 'eu5', '{{DEMO_ROOT}}/demos/Test_Project_Remis_EU5', '{{BUNDLED_TRANSLATION_ROOT}}/zh-CN-Test_Project_Remis_EU5', 'en', 'active', '2026-01-01T00:00:00', '2026-01-01T00:00:00', NULL, NULL, NULL);
        INSERT INTO project_files (file_id, project_id, file_path, status, original_key_count, line_count, file_type)
        VALUES ('file_1', 'proj_1', '{{DEMO_ROOT}}/demos/Test_Project_Remis_EU5/main_menu/localization/english/demo.yml', 'todo', 10, 20, 'source');
        COMMIT;
        """,
    )

    os.makedirs(resource_dir / "demos" / "Test_Project_Remis_EU5", exist_ok=True)
    os.makedirs(resource_dir / "my_translation" / "zh-CN-Test_Project_Remis_EU5", exist_ok=True)

    monkeypatch.setattr(app_settings, "APP_DATA_DIR", str(app_data_dir).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "RESOURCE_DIR", str(resource_dir).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "REMIS_DB_PATH", str(db_path).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "PROJECTS_DB_PATH", str(db_path).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "DATABASE_PATH", str(db_path).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "CONFIG_DIR", str(config_dir).replace("\\", "/"))
    monkeypatch.setattr(app_settings, "get_appdata_config_path", lambda: str(config_path))

    initialize_database()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT version, name FROM schema_migrations")
    migrations = cursor.fetchall()
    assert migrations == [(1, "establish_managed_main_schema")]

    cursor.execute("SELECT source_path, target_path FROM projects WHERE project_id = 'proj_1'")
    source_path, target_path = cursor.fetchone()
    assert source_path.replace("\\", "/").endswith("/demos/Test_Project_Remis_EU5")
    assert target_path.replace("\\", "/").endswith("/my_translation/zh-CN-Test_Project_Remis_EU5")

    cursor.execute("SELECT file_path FROM project_files WHERE file_id = 'file_1'")
    file_path = cursor.fetchone()[0]
    assert file_path.replace("\\", "/").endswith("/demos/Test_Project_Remis_EU5/main_menu/localization/english/demo.yml")

    cursor.execute("SELECT COUNT(*) FROM glossaries")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT COUNT(*) FROM entries")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_run_projects_db_migrations_upgrades_legacy_schema(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE glossaries (
            glossary_id INTEGER PRIMARY KEY,
            game_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_main INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            game_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
        """
    )
    cursor.execute(
        "INSERT INTO glossaries (glossary_id, game_id, name, description, is_main) VALUES (1, 'eu5', 'Legacy', 'old', 1)"
    )
    cursor.execute(
        "INSERT INTO projects (project_id, name, game_id, source_path, status) VALUES ('p1', 'Legacy Project', 'eu5', '/tmp/demo', 'active')"
    )
    conn.commit()
    conn.close()

    run_projects_db_migrations(str(db_path))

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(glossaries)")
    glossary_columns = {row[1] for row in cursor.fetchall()}
    assert {"version", "sources", "raw_metadata"}.issubset(glossary_columns)

    cursor.execute("PRAGMA table_info(projects)")
    project_columns = {row[1] for row in cursor.fetchall()}
    assert {"source_language", "last_modified", "last_activity_type", "last_activity_desc", "notes", "target_path"}.issubset(project_columns)

    cursor.execute("SELECT version FROM schema_migrations")
    assert cursor.fetchall() == [(1,)]

    cursor.execute("SELECT name FROM glossaries WHERE glossary_id = 1")
    assert cursor.fetchone()[0] == "Legacy"
    conn.close()
