from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from scripts.developer_tools.reset_demo_smoke_state import (
    DemoSmokeReset,
    EU5_PROJECT_ID,
    REPO_ROOT,
    ResetPaths,
    STELLARIS_PROJECT_ID,
    VIC3_PROJECT_ID,
)


def _create_main_db(path: Path, app_data: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT,
                game_id TEXT,
                source_path TEXT,
                target_path TEXT,
                source_language TEXT,
                status TEXT
            );
            CREATE TABLE project_files (
                file_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT,
                original_key_count INTEGER,
                line_count INTEGER,
                file_type TEXT,
                UNIQUE(project_id, file_path)
            );
            CREATE TABLE project_history (
                history_id TEXT PRIMARY KEY,
                project_id TEXT,
                timestamp TEXT,
                action_type TEXT,
                description TEXT,
                snapshot_id INTEGER,
                extra_metadata JSON
            );
            CREATE TABLE glossaries (
                glossary_id INTEGER PRIMARY KEY,
                game_id TEXT,
                name TEXT,
                description TEXT,
                version TEXT,
                is_main INTEGER,
                sources JSON,
                raw_metadata JSON
            );
            CREATE TABLE entries (
                entry_id TEXT PRIMARY KEY,
                glossary_id INTEGER,
                translations JSON,
                abbreviations JSON,
                variants JSON,
                raw_metadata JSON
            );
            CREATE TABLE project_glossary_bindings (
                project_id TEXT,
                glossary_id INTEGER,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY(project_id, glossary_id)
            );
            CREATE TABLE background_tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT,
                project_id TEXT,
                status TEXT,
                updated_at TEXT,
                archived_at TEXT,
                result JSON
            );
            """
        )
        projects = [
            (
                VIC3_PROJECT_ID,
                "Vic3 demo",
                "victoria3",
                app_data / "demos" / "Test_Project_Remis_Vic3",
                app_data / "my_translation" / "en-Test_Project_Remis_Vic3",
                "zh-CN",
            ),
            (
                STELLARIS_PROJECT_ID,
                "Stellaris demo",
                "stellaris",
                app_data / "demos" / "Test_Project_Remis_stellaris",
                app_data / "my_translation" / "zh-CN-Test_Project_Remis_stellaris",
                "en",
            ),
            (
                EU5_PROJECT_ID,
                "EU5 demo",
                "eu5",
                app_data / "demos" / "Test_Project_Remis_EU5",
                app_data / "my_translation" / "zh-CN-Test_Project_Remis_EU5",
                "en",
            ),
        ]
        connection.executemany(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path,
                target_path, source_language, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            [
                (
                    project_id,
                    name,
                    game_id,
                    str(source),
                    str(target),
                    source_language,
                )
                for (
                    project_id,
                    name,
                    game_id,
                    source,
                    target,
                    source_language,
                ) in projects
            ],
        )
        incremental_output = (
            app_data.parent
            / "worktree"
            / "my_translation"
            / "en-demo-incremental-update-20260726"
        )
        connection.execute(
            """
            INSERT INTO project_history
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "history-incremental",
                VIC3_PROJECT_ID,
                "2026-07-26T00:00:00Z",
                "translate",
                "demo",
                999,
                json.dumps({"output_dir": str(incremental_output)}),
            ),
        )
        connection.execute(
            """
            INSERT INTO background_tasks
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                "task-incremental",
                "incremental_translation",
                VIC3_PROJECT_ID,
                "completed",
                "2026-07-26T00:00:00Z",
                json.dumps({"output_paths": [str(incremental_output)]}),
            ),
        )
        connection.execute(
            """
            INSERT INTO glossaries
            VALUES (101, 'stellaris', 'Owned demo glossary', NULL, NULL, 0, '[]', ?)
            """,
            (json.dumps({"owner_project_id": STELLARIS_PROJECT_ID}),),
        )
        connection.execute(
            """
            INSERT INTO glossaries
            VALUES (102, 'stellaris', 'Shared glossary', NULL, NULL, 0, '[]', '{}')
            """
        )
        connection.executemany(
            """
            INSERT INTO project_glossary_bindings
            VALUES (?, ?, NULL, NULL)
            """,
            [
                (STELLARIS_PROJECT_ID, 101),
                (STELLARIS_PROJECT_ID, 102),
            ],
        )
        connection.execute(
            """
            INSERT INTO entries
            VALUES ('owned-entry', 101, '{}', '{}', '{}', '{}')
            """
        )
        connection.commit()


def _write_sidecar(path: Path, translation_dirs: list[str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".remis_project.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "config": {"translation_dirs": translation_dirs},
                "kanban": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_all_demo_smoke_scopes_restore_isolated_ready_states(tmp_path):
    app_data = tmp_path / "appdata"
    fake_worktree = tmp_path / "worktree"
    main_db = app_data / "remis.sqlite"
    archive_db = app_data / "mods_cache.sqlite"
    app_data.mkdir()
    fake_worktree.mkdir()
    _create_main_db(main_db, app_data)
    shutil.copy2(REPO_ROOT / "assets" / "mods_cache_skeleton.sqlite", archive_db)

    with sqlite3.connect(archive_db) as connection:
        mod_id = connection.execute(
            """
            SELECT mod_id FROM mod_identities WHERE remote_file_id = ?
            """,
            (VIC3_PROJECT_ID,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO source_versions (mod_id, snapshot_hash, created_at)
            VALUES (?, 'smoke-test-snapshot', '2026-07-26 00:00:00')
            """,
            (mod_id,),
        )
        connection.commit()

    incremental_output = (
        fake_worktree
        / "my_translation"
        / "en-demo-incremental-update-20260726"
    )
    incremental_output.mkdir(parents=True)
    (incremental_output / "result.yml").write_text("result", encoding="utf-8")
    eu5_target = app_data / "my_translation" / "zh-CN-Test_Project_Remis_EU5"
    eu5_target.mkdir(parents=True)
    (eu5_target / "old.yml").write_text("old", encoding="utf-8")
    vic3_target = app_data / "my_translation" / "en-Test_Project_Remis_Vic3"
    vic3_target.mkdir(parents=True)
    (vic3_target / "old.yml").write_text("old", encoding="utf-8")

    vic3_source = app_data / "demos" / "Test_Project_Remis_Vic3"
    stellaris_source = app_data / "demos" / "Test_Project_Remis_stellaris"
    eu5_source = app_data / "demos" / "Test_Project_Remis_EU5"
    _write_sidecar(vic3_source, [str(incremental_output)])
    _write_sidecar(stellaris_source, [])
    _write_sidecar(eu5_source, [])

    candidate_dir = (
        fake_worktree / "data" / "cache" / "neologism_candidates"
    )
    candidate_dir.mkdir(parents=True)
    candidate_file = candidate_dir / (
        hashlib.sha256(STELLARIS_PROJECT_ID.encode("utf-8")).hexdigest()
        + ".json"
    )
    candidate_file.write_text("[]", encoding="utf-8")

    paths = ResetPaths(
        repo_root=REPO_ROOT,
        fixture_repo_root=REPO_ROOT,
        app_data_dir=app_data,
        main_db=main_db,
        archive_db=archive_db,
        archive_seed_db=REPO_ROOT / "assets" / "mods_cache_skeleton.sqlite",
        backup_root=tmp_path / "backup",
    )
    reset = DemoSmokeReset(
        paths,
        ("initial", "incremental", "workshop", "neologism"),
        worktree_roots=[fake_worktree],
        backend_port=65534,
    )

    report = reset.apply(allow_running_backend=True)

    assert Path(report["backup_root"]).is_dir()
    assert not incremental_output.exists()
    assert not candidate_file.exists()
    assert not (eu5_target / "old.yml").exists()
    assert (
        vic3_target
        / "localization"
        / "english"
        / "remis_demo_l_english.yml"
    ).is_file()
    assert (
        app_data
        / "demos"
        / "Test_Project_Remis_Vic3_Incremental_Frozen"
        / "localization"
        / "simp_chinese"
        / "remis_newspaper_l_simp_chinese.yml"
    ).is_file()
    assert (
        app_data
        / "demo_smoke"
        / "agent_workshop_broken"
        / "localization"
        / "simp_chinese"
        / "workshop_demo_l_simp_chinese.yml"
    ).is_file()

    with sqlite3.connect(archive_db) as connection:
        connection.row_factory = sqlite3.Row
        versions = connection.execute(
            """
            SELECT snapshot_hash FROM source_versions
            WHERE mod_id = (
                SELECT mod_id FROM mod_identities WHERE remote_file_id = ?
            )
            ORDER BY snapshot_hash
            """,
            (VIC3_PROJECT_ID,),
        ).fetchall()
        seed_connection = sqlite3.connect(
            REPO_ROOT / "assets" / "mods_cache_skeleton.sqlite"
        )
        seed_versions = seed_connection.execute(
            """
            SELECT snapshot_hash FROM source_versions
            WHERE mod_id = (
                SELECT mod_id FROM mod_identities WHERE remote_file_id = ?
            )
            ORDER BY snapshot_hash
            """,
            (VIC3_PROJECT_ID,),
        ).fetchall()
        seed_connection.close()
        assert [row["snapshot_hash"] for row in versions] == [
            row[0] for row in seed_versions
        ]
        eu5_translation_count = connection.execute(
            """
            SELECT COUNT(*) FROM translated_entries
            WHERE source_entry_id IN (
                SELECT source_entry_id FROM source_entries
                WHERE version_id IN (
                    SELECT version_id FROM source_versions
                    WHERE mod_id = (
                        SELECT mod_id FROM mod_identities
                        WHERE remote_file_id = ?
                    )
                )
            )
            """,
            (EU5_PROJECT_ID,),
        ).fetchone()[0]
        assert eu5_translation_count == 0

    with sqlite3.connect(main_db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM glossaries WHERE glossary_id = 101"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM glossaries WHERE glossary_id = 102"
        ).fetchone()[0] == 1
        assert connection.execute(
            """
            SELECT archived_at FROM background_tasks
            WHERE task_id = 'task-incremental'
            """
        ).fetchone()[0]
        workshop_files = connection.execute(
            """
            SELECT COUNT(*) FROM project_files
            WHERE project_id = ?
              AND file_path LIKE '%agent_workshop_broken%'
            """,
            (STELLARIS_PROJECT_ID,),
        ).fetchone()[0]
        assert workshop_files == 2


def test_preview_lists_scopes_without_creating_backup(tmp_path):
    paths = ResetPaths(
        repo_root=REPO_ROOT,
        fixture_repo_root=REPO_ROOT,
        app_data_dir=tmp_path / "appdata",
        main_db=tmp_path / "appdata" / "remis.sqlite",
        archive_db=tmp_path / "appdata" / "mods_cache.sqlite",
        archive_seed_db=REPO_ROOT / "assets" / "mods_cache_skeleton.sqlite",
        backup_root=tmp_path / "backup",
    )
    reset = DemoSmokeReset(
        paths,
        ("incremental", "neologism"),
        worktree_roots=[REPO_ROOT],
        backend_port=65534,
    )

    preview = reset.preview()

    assert any("Vic3 archive" in action for action in preview)
    assert any("candidate caches" in action for action in preview)
    assert not paths.backup_root.exists()


def test_non_incremental_scope_does_not_require_incremental_fixtures(tmp_path):
    app_data = tmp_path / "appdata"
    main_db = app_data / "remis.sqlite"
    archive_db = app_data / "mods_cache.sqlite"
    app_data.mkdir()
    main_db.touch()
    archive_db.touch()
    paths = ResetPaths(
        repo_root=REPO_ROOT,
        fixture_repo_root=tmp_path / "missing-fixtures",
        app_data_dir=app_data,
        main_db=main_db,
        archive_db=archive_db,
        archive_seed_db=tmp_path / "missing-archive-seed.sqlite",
        backup_root=tmp_path / "backup",
    )
    reset = DemoSmokeReset(
        paths,
        ("neologism",),
        worktree_roots=[REPO_ROOT],
        backend_port=65534,
    )

    reset.validate()
