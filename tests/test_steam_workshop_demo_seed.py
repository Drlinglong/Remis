import hashlib
import json
import sqlite3
from pathlib import Path

from scripts.core.db_migrations import migrate_main_database
from scripts.core.services.steam_workshop_demo_seed import (
    COVER_VERSION_ID,
    DESCRIPTION_VERSION_IDS,
    PROJECT_ID,
    WORKSPACE_ID,
    ensure_steam_workshop_demo,
)


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (512).to_bytes(4, "big") * 2 + b"demo"


def test_installs_canonical_demo_once_and_preserves_later_edits(tmp_path: Path):
    db_path = tmp_path / "remis.sqlite"
    app_data = tmp_path / "app-data"
    resource_root = tmp_path / "resources"
    project_root = app_data / "demos" / "vic3"
    project_root.mkdir(parents=True)
    thumbnail = project_root / "thumbnail.png"
    thumbnail.write_bytes(_png())
    descriptions = resource_root / "data" / "steam_workshop_demo"
    descriptions.mkdir(parents=True)
    (descriptions / "description-1.bbcode").write_text("中文 [b]描述[/b]", encoding="utf-8")
    (descriptions / "description-2.bbcode").write_text("日本語 [url=https://example.com]説明[/url]", encoding="utf-8")
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO projects (project_id, name, game_id, source_path, "
            "source_language, status) VALUES (?, 'Demo', 'victoria3', ?, 'zh-CN', 'active')",
            (PROJECT_ID, str(project_root)),
        )

    assert ensure_steam_workshop_demo(db_path, resource_root, app_data) is True
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        workspace = connection.execute(
            "SELECT * FROM steam_workshop_workspaces WHERE workspace_id = ?",
            (WORKSPACE_ID,),
        ).fetchone()
        versions = connection.execute(
            "SELECT * FROM steam_workshop_asset_versions WHERE workspace_id = ? "
            "ORDER BY asset_type, sequence",
            (WORKSPACE_ID,),
        ).fetchall()
        connection.execute(
            "UPDATE steam_workshop_workspaces SET name = 'User renamed demo' "
            "WHERE workspace_id = ?",
            (WORKSPACE_ID,),
        )
        connection.commit()

    assert workspace["game_id"] == "victoria3"
    assert workspace["current_cover_version_id"] == COVER_VERSION_ID
    assert workspace["current_description_version_id"] == DESCRIPTION_VERSION_IDS[0]
    assert [(row["asset_type"], row["sequence"]) for row in versions] == [
        ("cover", 2),
        ("description", 1),
        ("description", 2),
    ]
    canvas = json.loads(versions[0]["cover_canvas_json"])
    assert canvas["backgroundImage"]["src"].startswith("data:image/png;base64,")
    cover_path = app_data / "steam_workshop_assets" / versions[0]["cover_file_ref"]
    assert cover_path.is_file()
    assert hashlib.sha256(cover_path.read_bytes()).hexdigest() == versions[0]["sha256"]

    assert ensure_steam_workshop_demo(db_path, resource_root, app_data) is False
    with sqlite3.connect(db_path) as connection:
        name = connection.execute(
            "SELECT name FROM steam_workshop_workspaces WHERE workspace_id = ?",
            (WORKSPACE_ID,),
        ).fetchone()[0]
    assert name == "User renamed demo"
