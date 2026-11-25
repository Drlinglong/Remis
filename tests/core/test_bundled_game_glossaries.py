import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts import app_settings, build_pipeline
from scripts.build_glossary_resources import BUNDLED_GLOSSARY_ASSETS, PROBABLY_STOLEN_RESOURCE, RESOURCE_PATH
from scripts.core.bundled_glossary_service import SEED_KEYS, install_bundled_glossaries
from scripts.core.db_initializer import initialize_database
from scripts.core.db_migrations import migrate_main_database

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def installed_resources(tmp_path, monkeypatch):
    # Stage precisely the files added by the production freezer command.
    resources = tmp_path / "resources"
    args = build_pipeline.backend_seed_add_data_args(ROOT, "main.sql", "projects.sql")
    for resource in BUNDLED_GLOSSARY_ASSETS:
        assert f'--add-data "{ROOT / resource};{resource.parent.as_posix()}"' in args
        target = resources / resource
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / resource, target)
    data = resources / "data"
    data.mkdir()
    for name in ("seed_data_main.sql", "seed_data_projects.sql"):
        (data / name).write_text("-- empty test seed\n", encoding="utf-8")
    app_data = tmp_path / "user"
    database = app_data / "remis.sqlite"
    monkeypatch.setattr(app_settings, "RESOURCE_DIR", str(resources))
    monkeypatch.setattr(app_settings, "APP_DATA_DIR", str(app_data))
    monkeypatch.setattr(app_settings, "REMIS_DB_PATH", str(database))
    monkeypatch.setattr(app_settings, "CONFIG_DIR", str(app_data / "config"))
    monkeypatch.setattr(app_settings, "get_appdata_config_path", lambda: str(app_data / "config.json"))
    return resources, database


def _bundled_sizes(conn):
    return conn.execute("""
        SELECT game_id, is_main, COUNT(e.entry_id)
        FROM glossaries g JOIN entries e USING (glossary_id)
        WHERE json_extract(g.raw_metadata, '$.bundled_resource') IS NOT NULL
        GROUP BY g.glossary_id
        ORDER BY game_id, COUNT(e.entry_id)
    """).fetchall()


def test_first_start_installs_editable_optional_resources(installed_resources, monkeypatch):
    _, database = installed_resources
    initialize_database()
    with sqlite3.connect(database) as conn:
        assert _bundled_sizes(conn) == [
            ("probably_stolen", 0, 851), ("surviving_mars", 0, 278), ("surviving_mars", 0, 1711),
        ]
        assert set(conn.execute(
            "SELECT seed_key FROM bundled_seed_state WHERE seed_key LIKE 'glossary:%'"
        ).fetchall()) == {(key,) for key in SEED_KEYS}
        state, context = conn.execute("""
            SELECT json_extract(e.raw_metadata, '$.terminology.review_state'),
                   json_extract(e.raw_metadata, '$.terminology.context_keys')
            FROM entries e JOIN glossaries g USING (glossary_id)
            WHERE json_extract(g.raw_metadata, '$.terminology_locale') = 'zh-TW'
            AND json_extract(e.raw_metadata, '$.terminology.review_state') = 'approved' LIMIT 1
        """).fetchone()
        assert state == "approved" and isinstance(json.loads(context), list)
        languages = conn.execute("""
            SELECT e.translations FROM entries e JOIN glossaries g USING (glossary_id)
            WHERE g.game_id = 'probably_stolen' LIMIT 1
        """).fetchone()[0]
        assert set(json.loads(languages)) == {"en", "zh-CN", "fr", "de", "ja", "pl", "ru", "es"}


    from scripts.routers import glossary as glossary_router
    monkeypatch.setattr(glossary_router.glossary_manager.db_manager, "db_path", str(database))
    app = FastAPI()
    app.include_router(glossary_router.router)
    with TestClient(app) as client:
        tree = client.get("/api/glossary/tree")
        assert tree.status_code == 200
        assert {node["key"]: len(node["children"]) for node in tree.json()} == {
            "probably_stolen": 1, "surviving_mars": 2,
        }
        for game, count in (("probably_stolen", 1), ("surviving_mars", 2)):
            response = client.get(f"/api/glossaries/{game}")
            assert response.status_code == 200 and len(response.json()) == count
            assert all(not item["is_main"] for item in response.json())


def test_upgrade_preserves_prior_import_and_user_edits(installed_resources):
    root, database = installed_resources
    database.parent.mkdir()
    migrate_main_database(str(database))
    mars = json.loads((root / RESOURCE_PATH / "surviving-mars.en-zh-CN.json").read_text(encoding="utf-8"))
    with sqlite3.connect(database) as conn:
        conn.execute("""
            INSERT INTO glossaries (glossary_id, game_id, name, is_main, raw_metadata)
            VALUES (12, 'surviving_mars', 'User renamed', 0, ?)
        """, (json.dumps({"terminology_import_key": mars["import_payload"]["import_key"]}),))
        conn.execute("""
            INSERT INTO entries (entry_id, glossary_id, translations, raw_metadata)
            VALUES ('mine', 12, '{"en":"Edited by user"}', '{}')
        """)
        conn.execute("""
            INSERT INTO projects (project_id, name, game_id, source_path, source_language, status)
            VALUES ('p', 'Project', 'surviving_mars', 'fixture', 'en', 'active')
        """)
        conn.execute("INSERT INTO project_glossary_bindings (project_id, glossary_id) VALUES ('p', 12)")
    initialize_database()
    initialize_database()
    with sqlite3.connect(database) as conn:
        assert _bundled_sizes(conn) == [("probably_stolen", 0, 851), ("surviving_mars", 0, 278)]
        assert conn.execute("SELECT name FROM glossaries WHERE glossary_id = 12").fetchone() == ("User renamed",)
        assert conn.execute("SELECT translations FROM entries WHERE entry_id = 'mine'").fetchone() == ('{"en":"Edited by user"}',)
        assert conn.execute("SELECT project_id, glossary_id FROM project_glossary_bindings").fetchall() == [("p", 12)]


def test_failed_bundle_rolls_back_rows_and_markers_before_retry(installed_resources):
    root, database = installed_resources
    database.parent.mkdir()
    migrate_main_database(str(database))
    resource = root / PROBABLY_STOLEN_RESOURCE
    resource.write_text("{}", encoding="utf-8")
    with pytest.raises(KeyError):
        install_bundled_glossaries(database, root)
    with sqlite3.connect(database) as conn:
        assert _bundled_sizes(conn) == []
        assert conn.execute("SELECT COUNT(*) FROM bundled_seed_state WHERE seed_key LIKE 'glossary:%'").fetchone() == (0,)
    shutil.copy2(ROOT / PROBABLY_STOLEN_RESOURCE, resource)
    install_bundled_glossaries(database, root)
    with sqlite3.connect(database) as conn:
        assert len(_bundled_sizes(conn)) == 3
