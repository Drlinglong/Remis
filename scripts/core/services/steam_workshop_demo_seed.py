from __future__ import annotations

import base64
import hashlib
import json
import shutil
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

from scripts.core.services.project_thumbnail_service import find_project_thumbnail

SEED_KEY = "steam_workshop_demo"
SEED_VERSION = 1
WORKSPACE_ID = "7e492e06-823d-4343-998e-f121db6e0ee1"
PROJECT_ID = "a525f596-6c71-43fe-ade2-52c9205a2720"
COVER_VERSION_ID = "d907ac84-1af0-497e-8f13-48a3e914e03b"
DESCRIPTION_VERSION_IDS = (
    "917fb128-8aff-45b2-becc-ca6c2f6ff870",
    "09bfaa79-25ac-4766-98b1-d18704c5c235",
)
CANONICAL_VERSION_IDS = (COVER_VERSION_ID, *DESCRIPTION_VERSION_IDS)


def _read_png_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 24 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Bundled Steam Workshop demo thumbnail is not a PNG")
    return struct.unpack(">II", content[16:24])


def _canvas_for_thumbnail(content: bytes, width: int, height: int) -> dict:
    encoded = base64.b64encode(content).decode("ascii")
    ratio = min(512 / width, 512 / height, 1)
    display_width = width * ratio
    display_height = height * ratio
    return {
        "schema_version": 1,
        "width": 512,
        "height": 512,
        "backgroundColor": "#ffffff",
        "backgroundImage": {
            "src": f"data:image/png;base64,{encoded}",
            "x": (512 - display_width) / 2,
            "y": (512 - display_height) / 2,
            "width": display_width,
            "height": display_height,
        },
        "elements": [],
    }


def _pending_project_source(db_path: Path) -> str | None:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        applied = connection.execute(
            "SELECT seed_version FROM bundled_seed_state WHERE seed_key = ?",
            (SEED_KEY,),
        ).fetchone()
        if applied and applied["seed_version"] >= SEED_VERSION:
            return None
        project = connection.execute(
            "SELECT source_path FROM projects WHERE project_id = ?",
            (PROJECT_ID,),
        ).fetchone()
        return project["source_path"] if project else None


def _prepare_cover(source_path: str, app_data_root: Path) -> tuple[bytes, int, int, str, Path]:
    thumbnail = find_project_thumbnail(source_path)
    png = thumbnail.read_bytes()
    width, height = _read_png_dimensions(png)
    asset_root = (app_data_root / "steam_workshop_assets").resolve()
    cover_ref = f"covers/{WORKSPACE_ID}/{COVER_VERSION_ID}.png"
    cover_path = (asset_root / Path(*cover_ref.split("/"))).resolve()
    if asset_root not in cover_path.parents:
        raise ValueError("Unsafe bundled Steam Workshop cover path")
    cover_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(thumbnail, cover_path)
    return png, width, height, cover_ref, asset_root


def _write_seed_records(
    db_path: Path,
    descriptions: list[str],
    cover: tuple[bytes, int, int, str],
) -> list[str]:
    png, width, height, cover_ref = cover
    now = datetime.now(timezone.utc).isoformat()
    metadata = json.dumps(
        {"builtin_demo": True, "seed_version": SEED_VERSION},
        ensure_ascii=False,
    )
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        stale_cover_refs = [
            row["cover_file_ref"]
            for row in connection.execute(
                "SELECT cover_file_ref FROM steam_workshop_asset_versions "
                "WHERE workspace_id = ? AND version_id NOT IN (?, ?, ?) "
                "AND cover_file_ref IS NOT NULL",
                (WORKSPACE_ID, *CANONICAL_VERSION_IDS),
            )
        ]
        connection.execute(
            "INSERT INTO steam_workshop_workspaces (workspace_id, name, game_id, "
            "project_id, workshop_item_id, current_cover_version_id, "
            "current_description_version_id, created_at, updated_at) "
            "VALUES (?, ?, 'victoria3', ?, '3538617386', ?, ?, ?, ?) "
            "ON CONFLICT(workspace_id) DO UPDATE SET name=excluded.name, "
            "game_id=excluded.game_id, project_id=excluded.project_id, "
            "workshop_item_id=excluded.workshop_item_id, "
            "current_cover_version_id=excluded.current_cover_version_id, "
            "current_description_version_id=excluded.current_description_version_id, "
            "updated_at=excluded.updated_at",
            (WORKSPACE_ID, "Demo - 测试工作区", PROJECT_ID, COVER_VERSION_ID,
             DESCRIPTION_VERSION_IDS[0], now, now),
        )
        connection.execute(
            "UPDATE steam_workshop_asset_versions SET parent_version_id = NULL "
            "WHERE workspace_id = ?",
            (WORKSPACE_ID,),
        )
        connection.execute(
            "DELETE FROM steam_workshop_asset_versions WHERE workspace_id = ? "
            "AND version_id NOT IN (?, ?, ?)",
            (WORKSPACE_ID, *CANONICAL_VERSION_IDS),
        )
        connection.execute(
            "INSERT OR REPLACE INTO steam_workshop_asset_versions (version_id, "
            "workspace_id, sequence, asset_type, status, sha256, metadata_json, "
            "source, created_at, cover_file_ref, cover_mime_type, cover_width, "
            "cover_height, cover_canvas_json) VALUES (?, ?, 2, 'cover', "
            "'selected', ?, ?, 'imported', ?, ?, 'image/png', ?, ?, ?)",
            (COVER_VERSION_ID, WORKSPACE_ID, hashlib.sha256(png).hexdigest(),
             metadata, now, cover_ref, width, height,
             json.dumps(_canvas_for_thumbnail(png, width, height), ensure_ascii=False)),
        )
        for sequence, (version_id, bbcode, language, status) in enumerate(
            zip(DESCRIPTION_VERSION_IDS, descriptions, ("zh-CN", "ja"),
                ("selected", "candidate")),
            start=1,
        ):
            connection.execute(
                "INSERT OR REPLACE INTO steam_workshop_asset_versions (version_id, "
                "workspace_id, sequence, asset_type, status, sha256, metadata_json, "
                "source, created_at, description_bbcode, description_language) "
                "VALUES (?, ?, ?, 'description', ?, ?, ?, 'imported', ?, ?, ?)",
                (version_id, WORKSPACE_ID, sequence, status,
                 hashlib.sha256(bbcode.encode("utf-8")).hexdigest(), metadata, now,
                 bbcode, language),
            )
        connection.execute(
            "INSERT OR REPLACE INTO bundled_seed_state "
            "(seed_key, seed_version, applied_at) VALUES (?, ?, ?)",
            (SEED_KEY, SEED_VERSION, now),
        )
        connection.commit()
        return stale_cover_refs


def _remove_stale_covers(asset_root: Path, file_refs: list[str]) -> None:
    for file_ref in file_refs:
        stale_path = (asset_root / Path(*file_ref.split("/"))).resolve()
        if asset_root in stale_path.parents:
            stale_path.unlink(missing_ok=True)


def ensure_steam_workshop_demo(
    db_path: str | Path,
    resource_root: str | Path,
    app_data_root: str | Path,
) -> bool:
    """Install the canonical demo once, then leave later user edits untouched."""
    db_path = Path(db_path)
    resource_root = Path(resource_root)
    app_data_root = Path(app_data_root)
    source_path = _pending_project_source(db_path)
    if source_path is None:
        return False
    descriptions = [
        (resource_root / "data" / "steam_workshop_demo" / f"description-{index}.bbcode")
        .read_text(encoding="utf-8")
        for index in (1, 2)
    ]
    png, width, height, cover_ref, asset_root = _prepare_cover(source_path, app_data_root)
    stale_refs = _write_seed_records(
        db_path, descriptions, (png, width, height, cover_ref)
    )
    _remove_stale_covers(asset_root, stale_refs)
    return True
