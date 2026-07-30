import sqlite3
from pathlib import Path

import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.utils.export_seed_data import (
    DEMO_PROJECTS,
    export_release_seeds,
    validate_release_assets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _create_release_source(path: Path) -> None:
    migrate_main_database(str(path))
    with sqlite3.connect(path) as connection:
        for index, (project_id, name) in enumerate(DEMO_PROJECTS, start=1):
            game_id = {
                "6049331a-433d-4d09-9205-165c3aad6010": "stellaris",
                "a525f596-6c71-43fe-ade2-52c9205a2720": "victoria3",
                "ae507ae2-2a08-44e3-9c3d-caa4445911f2": "eu5",
            }[project_id]
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, name, game_id, source_path, target_path,
                    source_language, status
                ) VALUES (?, ?, ?, ?, ?, 'english', 'active')
                """,
                (
                    project_id,
                    name,
                    game_id,
                    f"J:/repo/source_mod/Demo{index}",
                    f"J:/repo/my_translation/Demo{index}",
                ),
            )
            connection.execute(
                """
                INSERT INTO glossaries (
                    glossary_id, game_id, name, is_main
                ) VALUES (?, ?, ?, 0)
                """,
                (index, game_id, f"Demo glossary {index}"),
            )
            connection.execute(
                """
                INSERT INTO entries (
                    entry_id, glossary_id, translations, raw_metadata
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    f"entry-{index}",
                    index,
                    '{"en":"Hello"}',
                    (
                        '{"source_file":"C:\\\\Users\\\\developer\\\\AppData\\\\'
                        f'Roaming\\\\RemisModFactoryDev\\\\demos\\\\Demo{index}\\\\source.yml"}}'
                    ),
                ),
            )
            connection.execute(
                """
                INSERT INTO project_files (
                    file_id, project_id, file_path, status,
                    original_key_count, line_count, file_type
                ) VALUES (?, ?, ?, 'todo', 1, 1, 'source')
                """,
                (
                    f"file-{index}",
                    project_id,
                    (
                        "{{PROJECT_ROOT}}/my_translation/Demo2/output.yml"
                        if index == 2
                        else f"J:/repo/source_mod/Demo{index}/source.yml"
                    ),
                ),
            )
            connection.execute(
                """
                INSERT INTO project_glossary_bindings (
                    project_id, glossary_id
                ) VALUES (?, ?)
                """,
                (project_id, index),
            )
        connection.execute(
            """
            INSERT INTO activity_log (
                log_id, project_id, type, description, timestamp
            ) VALUES ('private-log', ?, 'scan', 'must not ship', '2026-07-29')
            """,
            (DEMO_PROJECTS[0][0],),
        )
        connection.execute(
            """
            INSERT INTO background_tasks (
                task_id, kind, status, title, created_at, updated_at
            ) VALUES (
                'private-task', 'model_arena', 'completed', 'must not ship',
                '2026-07-29', '2026-07-29'
            )
            """
        )


def _create_release_cache(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE mods (
                mod_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.executemany(
            "INSERT INTO mods (mod_id, name) VALUES (?, ?)",
            [
                (index, name)
                for index, (_project_id, name) in enumerate(DEMO_PROJECTS, start=1)
            ],
        )


def test_release_seed_export_is_three_demo_allowlist(tmp_path):
    source_db = tmp_path / "skeleton.sqlite"
    cache_db = tmp_path / "mods_cache_skeleton.sqlite"
    main_seed = tmp_path / "seed_data_main.sql"
    projects_seed = tmp_path / "seed_data_projects.sql"
    _create_release_source(source_db)
    _create_release_cache(cache_db)

    main_count, project_count = export_release_seeds(
        source_db=source_db,
        cache_db=cache_db,
        main_output=main_seed,
        projects_output=projects_seed,
    )

    assert main_count == 6
    assert project_count == 9
    project_sql = projects_seed.read_text(encoding="utf-8")
    assert "private-log" not in project_sql
    assert "private-task" not in project_sql
    assert "{{PROJECT_ROOT}}" not in project_sql
    assert "{{BUNDLED_DEMO_ROOT}}/Demo1/source.yml" in project_sql
    assert "{{BUNDLED_TRANSLATION_ROOT}}/Demo2/output.yml" in project_sql
    main_sql = main_seed.read_text(encoding="utf-8")
    assert "C:\\\\Users\\\\developer" not in main_sql
    assert "{{BUNDLED_DEMO_ROOT}}/Demo1/source.yml" in main_sql

    installed_db = tmp_path / "installed.sqlite"
    migrate_main_database(str(installed_db))
    with sqlite3.connect(installed_db) as connection:
        connection.executescript(main_seed.read_text(encoding="utf-8"))
        connection.executescript(project_sql)
        projects = connection.execute(
            "SELECT project_id, name FROM projects ORDER BY project_id"
        ).fetchall()
        assert dict(projects) == dict(DEMO_PROJECTS)
        assert connection.execute(
            "SELECT COUNT(*) FROM project_glossary_bindings"
        ).fetchone()[0] == 3
        assert connection.execute(
            "SELECT COUNT(*) FROM activity_log"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM background_tasks"
        ).fetchone()[0] == 0


def test_release_seed_validation_rejects_an_extra_project(tmp_path):
    source_db = tmp_path / "skeleton.sqlite"
    cache_db = tmp_path / "mods_cache_skeleton.sqlite"
    _create_release_source(source_db)
    _create_release_cache(cache_db)
    with sqlite3.connect(source_db) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES (
                'private-project', 'Private Project', 'eu5', 'C:/private',
                'english', 'active'
            )
            """
        )

    with pytest.raises(ValueError, match="exactly the three approved"):
        validate_release_assets(source_db, cache_db)


def test_checked_in_release_assets_match_three_demo_policy():
    validate_release_assets(
        REPO_ROOT / "assets" / "skeleton.sqlite",
        REPO_ROOT / "assets" / "mods_cache_skeleton.sqlite",
    )


def test_packaging_does_not_bundle_main_skeleton_or_read_live_appdata():
    build_pipeline = (REPO_ROOT / "scripts" / "build_pipeline.py").read_text(
        encoding="utf-8"
    )
    debug_build = (
        REPO_ROOT / "scripts" / "developer_tools" / "windows" / "debug_build.bat"
    ).read_text(encoding="utf-8")
    exporter = (
        REPO_ROOT / "scripts" / "utils" / "export_seed_data.py"
    ).read_text(encoding="utf-8")

    assert '"{release_seed_db};assets"' not in build_pipeline
    assert "%PROJECT_ROOT%\\assets\\skeleton.sqlite;assets" not in debug_build
    assert "app_settings" not in exporter
    assert "--source-db" in build_pipeline
    assert "--source-db" in debug_build
