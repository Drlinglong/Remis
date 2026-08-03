import os
import json
import sqlite3

import pytest

import scripts.core.db_initializer as db_initializer
from scripts import app_settings
from scripts.core.db_migrations import (
    MAIN_DB_TARGET_VERSION,
    UnsupportedDatabaseVersionError,
    migrate_main_database,
)
from scripts.core.db_initializer import (
    extract_bundled_demo_translations,
    initialize_database,
    run_projects_db_migrations,
)


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
        INSERT INTO project_glossary_bindings (project_id, glossary_id)
        VALUES ('proj_1', 1);
        INSERT INTO activity_log (log_id, project_id, type, description, timestamp)
        VALUES ('must_not_import', 'proj_1', 'private', 'not release seed data', '2026-01-01');
        COMMIT;
        """,
    )

    os.makedirs(resource_dir / "demos" / "Test_Project_Remis_EU5", exist_ok=True)
    os.makedirs(resource_dir / "my_translation" / "zh-CN-Test_Project_Remis_EU5", exist_ok=True)
    _write_file(resource_dir / "my_translation" / "zh-CN-Test_Project_Remis_EU5" / "demo.yml", "demo")
    _write_file(app_data_dir / "my_translation" / "user-output" / "keep.yml", "keep")

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
    assert migrations == [
        (1, "establish_managed_main_schema"),
        (2, "add_project_watches"),
        (3, "add_project_glossary_bindings"),
        (4, "add_background_task_ledger"),
        (5, "make_glossary_bindings_many_to_many"),
        (6, "index_task_summary_queries"),
        (7, "govern_task_events_and_retention"),
        (8, "pause_archived_project_watches"),
        (9, "add_model_arena_history"),
        (10, "enforce_status_contracts"),
        (11, "add_steam_workshop_assets"),
        (12, "track_bundled_seed_state"),
        (13, "harden_bundled_seed_state"),
        (14, "add_context_release_storage"),
        (15, "add_context_analysis_batch_storage"),
        (16, "add_context_delivery_memberships"),
        (17, "add_context_aggregation_phase"),
        (18, "add_context_release_manifests"),
    ]

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

    cursor.execute("SELECT project_id, glossary_id FROM project_glossary_bindings")
    assert cursor.fetchone() == ("proj_1", 1)

    cursor.execute("SELECT COUNT(*) FROM activity_log")
    assert cursor.fetchone()[0] == 0
    conn.close()

    assert (app_data_dir / "my_translation" / "zh-CN-Test_Project_Remis_EU5" / "demo.yml").exists()
    assert (app_data_dir / "my_translation" / "user-output" / "keep.yml").exists()


def test_extract_bundled_demo_translations_only_replaces_bundled_children(tmp_path):
    source_root = tmp_path / "resources" / "my_translation"
    dest_root = tmp_path / "appdata" / "my_translation"

    _write_file(source_root / "zh-CN-Test_Project_Remis_Vic3" / "fresh.yml", "fresh")
    _write_file(dest_root / "zh-CN-Test_Project_Remis_Vic3" / "stale.yml", "stale")
    _write_file(dest_root / "user-project" / "keep.yml", "keep")

    changed = extract_bundled_demo_translations(str(source_root), str(dest_root), force=True)

    assert changed is True
    assert (dest_root / "zh-CN-Test_Project_Remis_Vic3" / "fresh.yml").exists()
    assert not (dest_root / "zh-CN-Test_Project_Remis_Vic3" / "stale.yml").exists()
    assert (dest_root / "user-project" / "keep.yml").exists()


def test_seed_failure_is_recorded_and_retried_without_overwriting_user_data(
    tmp_path,
    monkeypatch,
):
    app_data_dir = tmp_path / "appdata"
    resource_dir = tmp_path / "resources"
    db_path = app_data_dir / "remis.sqlite"
    config_path = app_data_dir / "config.json"
    seed_main = resource_dir / "data" / "seed_data_main.sql"

    _write_file(
        seed_main,
        "INSERT INTO glossaries (does_not_exist) VALUES (1);",
    )
    _write_file(resource_dir / "data" / "seed_data_projects.sql", "-- empty")

    monkeypatch.setattr(app_settings, "APP_DATA_DIR", str(app_data_dir))
    monkeypatch.setattr(app_settings, "RESOURCE_DIR", str(resource_dir))
    monkeypatch.setattr(app_settings, "REMIS_DB_PATH", str(db_path))
    monkeypatch.setattr(app_settings, "PROJECTS_DB_PATH", str(db_path))
    monkeypatch.setattr(app_settings, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(app_settings, "CONFIG_DIR", str(app_data_dir / "config"))
    monkeypatch.setattr(app_settings, "get_appdata_config_path", lambda: str(config_path))

    initialize_database()

    with sqlite3.connect(db_path) as conn:
        failure = conn.execute(
            """
            SELECT status, seed_version, attempt_count, last_error
            FROM bundled_seed_state
            WHERE seed_key = 'main'
            """
        ).fetchone()
        assert failure[0] == "failed"
        assert failure[1] == 0
        assert failure[2] == 1
        assert "OperationalError" in failure[3]
        conn.execute(
            """
            INSERT INTO glossaries (
                glossary_id, game_id, name, description, version, is_main,
                sources, raw_metadata
            ) VALUES (1, 'eu5', 'User edit', 'kept', '1', 0, '[]', '{}')
            """
        )

    _write_file(
        seed_main,
        """
        INSERT INTO glossaries (
            glossary_id, game_id, name, description, version, is_main,
            sources, raw_metadata
        ) VALUES (1, 'eu5', 'Bundled value', 'seed', '1', 1, '[]', '{}');
        """,
    )
    initialize_database()

    with sqlite3.connect(db_path) as conn:
        state = conn.execute(
            """
            SELECT status, seed_version, attempt_count, last_error
            FROM bundled_seed_state
            WHERE seed_key = 'main'
            """
        ).fetchone()
        assert state == ("applied", 1, 2, None)
        assert conn.execute(
            "SELECT name FROM glossaries WHERE glossary_id = 1"
        ).fetchone()[0] == "User edit"


def test_migration_retries_after_version_recording_crash_window(tmp_path):
    db_path = tmp_path / "migration-crash-window.sqlite"

    def fail_after_migration(version, _name):
        if version == 5:
            raise RuntimeError("injected crash after migration 5 DDL")

    with pytest.raises(RuntimeError, match="injected crash"):
        migrate_main_database(str(db_path), after_migration=fail_after_migration)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0] == 4
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'project_glossary_bindings_v2'"
        ).fetchone() is None
        assert conn.execute(
            "PRAGMA table_info(project_glossary_bindings)"
        ).fetchall()[0][1] == "project_id"

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT name FROM schema_migrations WHERE version = 5"
        ).fetchone()[0] == "make_glossary_bindings_many_to_many"
        primary_key = {
            row[1]: row[5]
            for row in conn.execute("PRAGMA table_info(project_glossary_bindings)")
            if row[5]
        }
        assert primary_key == {"project_id": 1, "glossary_id": 2}


def test_migration_five_recovers_existing_staging_table(tmp_path):
    db_path = tmp_path / "migration-five-staging.sqlite"

    def fail_before_migration_five(version, _name):
        if version == 4:
            raise RuntimeError("stop before migration 5")

    with pytest.raises(RuntimeError, match="stop before migration 5"):
        migrate_main_database(
            str(db_path),
            after_migration=fail_before_migration_five,
        )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE project_glossary_bindings_v2 (
                project_id TEXT NOT NULL,
                glossary_id INTEGER NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY(project_id, glossary_id),
                FOREIGN KEY(project_id) REFERENCES projects(project_id),
                FOREIGN KEY(glossary_id) REFERENCES glossaries(glossary_id)
            )
            """
        )

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "project_glossary_bindings" in tables
        assert "project_glossary_bindings_v2" not in tables
        assert conn.execute(
            "SELECT name FROM schema_migrations WHERE version = 5"
        ).fetchone()[0] == "make_glossary_bindings_many_to_many"


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
            is_main INTEGER NOT NULL DEFAULT 0,
            raw_metadata TEXT
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
        "INSERT INTO glossaries (glossary_id, game_id, name, description, is_main, raw_metadata) VALUES (1, 'eu5', 'Legacy', 'old', 1, '{\"project_id\": \"p1\"}')"
    )
    cursor.execute(
        "INSERT INTO glossaries (glossary_id, game_id, name, description, is_main, raw_metadata) VALUES (2, 'eu5', 'Stale Binding', 'old', 0, '{\"project_id\": \"missing-project\"}')"
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
    assert cursor.fetchall() == [
        (1,),
        (2,),
        (3,),
        (4,),
        (5,),
        (6,),
        (7,),
        (8,),
        (9,),
        (10,),
        (11,),
        (12,),
        (13,),
        (14,),
        (15,),
        (16,),
        (17,),
        (18,),
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_watches'")
    assert cursor.fetchone() == ("project_watches",)
    cursor.execute("PRAGMA table_info(project_watches)")
    watch_columns = {row[1] for row in cursor.fetchall()}
    assert "paused_by_project_archive" in watch_columns

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_glossary_bindings'")
    assert cursor.fetchone() == ("project_glossary_bindings",)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='background_tasks'")
    assert cursor.fetchone() == ("background_tasks",)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_events'")
    assert cursor.fetchone() == ("task_events",)
    cursor.execute("PRAGMA table_info(task_events)")
    task_event_columns = {row[1] for row in cursor.fetchall()}
    assert "audience" in task_event_columns
    cursor.execute("PRAGMA index_list(background_tasks)")
    task_indexes = {row[1] for row in cursor.fetchall()}
    assert {
        "ix_background_tasks_archived_updated",
        "ix_background_tasks_status_updated",
        "ix_background_tasks_created_at",
        "ix_background_tasks_status_finished",
        "ix_background_tasks_idempotency_key",
    }.issubset(task_indexes)
    cursor.execute("PRAGMA index_list(task_events)")
    task_event_indexes = {row[1] for row in cursor.fetchall()}
    assert "ix_task_events_task_audience_sequence" in task_event_indexes

    cursor.execute("SELECT glossary_id FROM project_glossary_bindings WHERE project_id = 'p1'")
    assert cursor.fetchone() == (1,)
    cursor.execute("SELECT COUNT(*) FROM project_glossary_bindings WHERE project_id = 'missing-project'")
    assert cursor.fetchone()[0] == 0

    cursor.execute("PRAGMA index_list(project_glossary_bindings)")
    binding_indexes = {row[1] for row in cursor.fetchall()}
    assert "ix_project_glossary_bindings_glossary_id" in binding_indexes
    assert "ix_project_glossary_bindings_project_id" in binding_indexes

    cursor.execute("PRAGMA table_info(project_glossary_bindings)")
    binding_primary_key = {
        row[1]: row[5]
        for row in cursor.fetchall()
        if row[5]
    }
    assert binding_primary_key == {"project_id": 1, "glossary_id": 2}

    cursor.execute("SELECT name FROM glossaries WHERE glossary_id = 1")
    assert cursor.fetchone()[0] == "Legacy"
    conn.close()

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    conn = sqlite3.connect(db_path)
    assert (
        conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        == MAIN_DB_TARGET_VERSION
    )
    assert conn.execute("SELECT COUNT(*) FROM project_glossary_bindings").fetchone()[0] == 1
    conn.close()


def test_managed_connection_enforces_foreign_keys(tmp_path):
    from scripts.core.db_manager import DatabaseConnectionManager

    db_path = tmp_path / "foreign-keys.sqlite"
    migrate_main_database(str(db_path))

    manager = object.__new__(DatabaseConnectionManager)
    manager.db_path = str(db_path)
    conn = manager.get_connection()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO project_glossary_bindings (project_id, glossary_id) VALUES (?, ?)",
            ("missing-project", 999999),
        )
    conn.close()


def test_glossary_binding_schema_allows_many_to_many_relationships(tmp_path):
    db_path = tmp_path / "many-to-many.sqlite"
    migrate_main_database(str(db_path))

    conn = sqlite3.connect(db_path)
    conn.executemany(
        """
        INSERT INTO projects
            (project_id, name, game_id, source_path, source_language, status)
        VALUES (?, ?, 'vic3', ?, 'english', 'active')
        """,
        [
            ("project-1", "First Mod", "/tmp/project-1"),
            ("project-2", "Second Mod", "/tmp/project-2"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO glossaries
            (glossary_id, game_id, name, is_main, sources, raw_metadata)
        VALUES (?, 'vic3', ?, 0, '[]', '{}')
        """,
        [
            (1, "First Terms"),
            (2, "Second Terms"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO project_glossary_bindings (project_id, glossary_id)
        VALUES (?, ?)
        """,
        [
            ("project-1", 1),
            ("project-1", 2),
            ("project-2", 1),
            ("project-2", 2),
        ],
    )
    conn.commit()

    assert conn.execute(
        "SELECT COUNT(*) FROM project_glossary_bindings WHERE project_id = 'project-1'"
    ).fetchone()[0] == 2
    assert conn.execute(
        "SELECT COUNT(*) FROM project_glossary_bindings WHERE glossary_id = 1"
    ).fetchone()[0] == 2
    conn.close()


def test_migration_rejects_future_schema_version(tmp_path):
    db_path = tmp_path / "future.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (999, 'future', '2026-01-01')"
        )

    with pytest.raises(UnsupportedDatabaseVersionError, match="newer than this Remis build"):
        migrate_main_database(str(db_path))


def test_existing_v14_database_adds_context_delivery_memberships(tmp_path):
    db_path = tmp_path / "context-delivery-upgrade.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TRIGGER trg_context_release_delivery_no_update")
        conn.execute("DROP TRIGGER trg_context_release_delivery_no_delete")
        conn.execute("DROP TABLE context_release_delivery_memberships")
        conn.execute("DELETE FROM schema_migrations WHERE version IN (15, 16)")

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' "
            "AND name = 'context_release_delivery_memberships'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' "
            "AND name LIKE 'trg_context_release_delivery_%'"
        ).fetchone()[0] == 2


def test_existing_v16_database_hydrates_persisted_release_manifest(tmp_path):
    db_path = tmp_path / "context-manifest-upgrade.sqlite"
    migrate_main_database(str(db_path))
    relative_path = "localisation/main.yml"
    content_hash = "hash-legacy"
    source_metadata = {
        "relative_path": relative_path,
        "item_key": "legacy_key:0",
        "source_order": 0,
        "source_snapshot_hash": "legacy-snapshot",
    }
    analysis_config = {
        "source_items": [
            {
                "relative_path": relative_path,
                "item_key": "legacy_key:0",
                "source_order": 0,
                "source_sha256": content_hash,
            }
        ]
    }
    with sqlite3.connect(db_path) as connection:
        for table in (
            "context_release_local_unit_members",
            "context_release_local_units",
            "context_release_source_items",
            "context_release_files",
        ):
            connection.execute(f"DROP TABLE {table}")
        connection.execute(
            "DELETE FROM schema_migrations WHERE version = 18"
        )
        connection.execute(
            """
            INSERT INTO projects
                (project_id, name, game_id, source_path, source_language, status)
            VALUES ('legacy-project', 'Legacy Context', 'vic3', '/legacy', 'english', 'active')
            """
        )
        connection.execute(
            """
            INSERT INTO context_source_items
                (source_item_id, project_id, source_type, source_ref, content,
                 content_hash, metadata_json, created_at)
            VALUES (?, 'legacy-project', 'localization', ?, ?, ?, ?, '2026-01-01T00:00:00+00:00')
            """,
            (
                "legacy-source",
                f"{relative_path}::0:legacy_key:0",
                "Legacy text",
                content_hash,
                json.dumps(source_metadata),
            ),
        )
        connection.execute(
            """
            INSERT INTO context_releases
                (release_id, project_id, source_snapshot_hash, analysis_scope_json,
                 schema_version, prompt_version, provider_id, model_id,
                 analysis_config_json, created_at, parent_release_id, upstream_version)
            VALUES (?, 'legacy-project', 'legacy-snapshot', ?, 'context-v1', 'prompt-v1',
                    'local', 'local-model', ?, '2026-01-01T00:00:00+00:00', NULL, NULL)
            """,
            (
                "legacy-release",
                json.dumps({"files": [relative_path]}),
                json.dumps(analysis_config),
            ),
        )

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "context_release_files",
            "context_release_source_items",
            "context_release_local_units",
            "context_release_local_unit_members",
        } <= tables
        assert connection.execute(
            "SELECT COUNT(*) FROM context_release_source_items "
            "WHERE release_id = 'legacy-release'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM context_release_local_unit_members "
            "WHERE release_id = 'legacy-release'"
        ).fetchone()[0] == 1

    from scripts.core.repositories.context_repository import ContextRepository

    manifest = ContextRepository(str(db_path)).get_release_manifest("legacy-release")
    assert manifest is not None
    assert manifest.source_items[0].source_item_id == "legacy-source"
    assert manifest.source_items[0].content == "Legacy text"
    assert manifest.local_units[0].source_item_ids == ["legacy-source"]


def test_status_contract_triggers_reject_unknown_values(tmp_path):
    db_path = tmp_path / "status-contract.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="invalid projects.status"):
            conn.execute(
                """
                INSERT INTO projects
                    (project_id, name, game_id, source_path, status, created_at)
                VALUES ('bad-project', 'Bad', 'hoi4', '/tmp/bad', 'mystery', '2026-01-01')
                """
            )


def test_run_projects_db_migrations_raises_on_failure(monkeypatch, tmp_path):
    db_path = tmp_path / "broken.sqlite"

    def fail_migration(_db_path):
        raise RuntimeError("schema drift")

    monkeypatch.setattr(db_initializer, "migrate_main_database", fail_migration)

    with pytest.raises(RuntimeError, match="schema drift"):
        run_projects_db_migrations(str(db_path))
