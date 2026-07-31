import base64
import hashlib
import sqlite3
import struct
import zlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.steam_workshop_repository import (
    SteamWorkshopRepository,
)
from scripts.core.services.steam_workshop_service import SteamWorkshopService
from scripts.core.services.workshop_description_generation_service import (
    GeneratedWorkshopDescription,
)
from scripts.routers import steam_workshop as steam_workshop_router


def _png_chunk(name: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + name
        + data
        + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
    )


def _png(width: int = 2, height: int = 3) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    rows = b"".join(b"\x00" + (b"\x00\x00\x00\xff" * width) for _ in range(height))
    return (
        signature
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(rows))
        + _png_chunk(b"IEND", b"")
    )


@pytest.fixture
def workshop_client(tmp_path, monkeypatch):
    db_path = tmp_path / "remis.sqlite"
    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES ('project-1', 'Project', 'vic3', 'source', 'en', 'active')
            """
        )
    service = SteamWorkshopService(
        SteamWorkshopRepository(str(db_path)),
        tmp_path / "assets",
    )
    monkeypatch.setattr(
        steam_workshop_router,
        "steam_workshop_service",
        service,
    )
    app = FastAPI()
    app.include_router(steam_workshop_router.router)
    with TestClient(app) as client:
        yield client, service, db_path


def _workspace(client, **overrides):
    payload = {"name": "发布素材", **overrides}
    response = client.post("/api/steam-workshop/workspaces", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _description(client, workspace_id, text="你好 [b]世界[/b]", **overrides):
    payload = {
        "bbcode": text,
        "language": "zh-CN",
        "source": "manual",
        **overrides,
    }
    response = client.post(
        f"/api/steam-workshop/workspaces/{workspace_id}/versions/description",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _cover(client, workspace_id, **overrides):
    payload = {
        "png_base64": base64.b64encode(_png()).decode("ascii"),
        "canvas": {
            "schema_version": 1,
            "width": 512,
            "height": 512,
            "backgroundColor": "#fff",
            "elements": [{"type": "text", "text": "中文"}],
        },
        "source": "manual",
        **overrides,
    }
    response = client.post(
        f"/api/steam-workshop/workspaces/{workspace_id}/versions/cover",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_migration_upgrades_managed_database_with_asset_tables(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (project_id TEXT PRIMARY KEY);
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO schema_migrations VALUES (?, ?, 'now')",
            [(version, f"migration-{version}") for version in range(1, 11)],
        )

    assert migrate_main_database(str(db_path)) == 11
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        applied = connection.execute(
            "SELECT name FROM schema_migrations WHERE version = 11"
        ).fetchone()
    assert "steam_workshop_workspaces" in tables
    assert "steam_workshop_asset_versions" in tables
    assert applied == ("add_steam_workshop_assets",)


def test_workspace_crud_supports_optional_bindings(workshop_client):
    client, _service, _db_path = workshop_client
    unbound = _workspace(client)
    bound = _workspace(
        client,
        name="Project assets",
        project_id="project-1",
        workshop_item_id=None,
    )
    assert unbound["project_id"] is None
    assert unbound["workshop_item_id"] is None
    assert bound["project_id"] == "project-1"

    listing = client.get(
        "/api/steam-workshop/workspaces",
        params={"project_id": "project-1"},
    )
    assert [item["workspace_id"] for item in listing.json()] == [
        bound["workspace_id"]
    ]
    updated = client.patch(
        f"/api/steam-workshop/workspaces/{bound['workspace_id']}",
        json={"workshop_item_id": "12345", "project_id": None},
    )
    assert updated.status_code == 200
    assert updated.json()["project_id"] is None
    assert updated.json()["workshop_item_id"] == "12345"

    deleted = client.delete(
        f"/api/steam-workshop/workspaces/{unbound['workspace_id']}"
    )
    assert deleted.status_code == 204
    assert client.get(
        f"/api/steam-workshop/workspaces/{unbound['workspace_id']}"
    ).status_code == 404


def test_description_versions_are_utf8_immutable_snapshots(workshop_client):
    client, _service, db_path = workshop_client
    workspace = _workspace(client)
    first = _description(client, workspace["workspace_id"])
    second = _description(
        client,
        workspace["workspace_id"],
        text="第二版",
        parent_version_id=first["version_id"],
    )
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert first["sha256"] == hashlib.sha256(
        "你好 [b]世界[/b]".encode("utf-8")
    ).hexdigest()

    with sqlite3.connect(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO steam_workshop_asset_versions (
                    version_id, workspace_id, sequence, asset_type, status,
                    sha256, metadata_json, source, created_at
                ) VALUES ('duplicate', ?, 1, 'description', 'candidate',
                          'hash', '{}', 'manual', 'now')
                """,
                (workspace["workspace_id"],),
            )
    reloaded = client.get(
        f"/api/steam-workshop/versions/{first['version_id']}"
    ).json()
    assert reloaded["bbcode"] == "你好 [b]世界[/b]"
    assert reloaded["status"] == "candidate"


def test_selecting_version_keeps_history_and_validates_ownership(workshop_client):
    client, _service, _db_path = workshop_client
    workspace = _workspace(client)
    other_workspace = _workspace(client, name="Other")
    first = _description(client, workspace["workspace_id"], text="一")
    second = _description(client, workspace["workspace_id"], text="二")
    other = _description(client, other_workspace["workspace_id"], text="三")

    selected = client.post(
        f"/api/steam-workshop/workspaces/{workspace['workspace_id']}"
        "/selections/description",
        json={"version_id": second["version_id"]},
    )
    assert selected.status_code == 200
    assert selected.json()["status"] == "selected"
    listing = client.get(
        f"/api/steam-workshop/workspaces/{workspace['workspace_id']}"
        "/versions?asset_type=description"
    ).json()
    assert {item["version_id"] for item in listing} == {
        first["version_id"],
        second["version_id"],
    }
    assert next(
        item for item in listing if item["version_id"] == first["version_id"]
    )["status"] == "candidate"
    denied = client.post(
        f"/api/steam-workshop/workspaces/{workspace['workspace_id']}"
        "/selections/description",
        json={"version_id": other["version_id"]},
    )
    assert denied.status_code == 400


def test_cover_storage_is_controlled_and_round_trips(workshop_client):
    client, service, _db_path = workshop_client
    workspace = _workspace(client)
    cover = _cover(client, workspace["workspace_id"])
    assert cover["width"] == 2
    assert cover["height"] == 3
    assert cover["mime_type"] == "image/png"
    assert "cover_file_ref" not in cover
    assert str(service.asset_root) not in str(cover)
    content = client.get(cover["content_url"])
    assert content.status_code == 200
    assert content.content == _png()

    service.repository.get_cover_file_ref = lambda _version_id: "../outside.png"
    with pytest.raises(ValueError, match="Unsafe cover"):
        service.get_cover_path(cover["version_id"])


def test_cover_rejects_arbitrary_canvas_fields_and_secret_metadata(
    workshop_client,
):
    client, _service, _db_path = workshop_client
    workspace = _workspace(client)
    endpoint = (
        f"/api/steam-workshop/workspaces/{workspace['workspace_id']}"
        "/versions/cover"
    )
    payload = {
        "png_base64": base64.b64encode(_png()).decode("ascii"),
        "canvas": {"elements": [], "output_path": "../../escape.png"},
        "source": "manual",
    }
    bad_canvas = client.post(endpoint, json=payload)
    assert bad_canvas.status_code == 400
    assert "Unsupported canvas fields" in bad_canvas.text

    payload["canvas"] = {"elements": []}
    payload["metadata"] = {"api_key": "must-not-persist"}
    bad_metadata = client.post(endpoint, json=payload)
    assert bad_metadata.status_code == 400
    assert "Sensitive field" in bad_metadata.text


def test_cover_canvas_accepts_editable_embedded_image_payload(workshop_client):
    client, _service, _db_path = workshop_client
    workspace = _workspace(client)
    embedded_image = "data:image/png;base64," + ("a" * (600 * 1024))
    cover = _cover(
        client,
        workspace["workspace_id"],
        canvas={
            "width": 512,
            "height": 512,
            "background_image": embedded_image,
            "elements": [],
        },
    )
    loaded = client.get(
        f"/api/steam-workshop/versions/{cover['version_id']}"
    ).json()
    assert loaded["canvas"]["background_image"] == embedded_image


def test_model_generation_requires_approval_and_saves_candidate(
    workshop_client,
    monkeypatch,
):
    client, _service, _db_path = workshop_client
    workspace = _workspace(
        client,
        workshop_item_id="3538617386",
    )
    endpoint = (
        f"/api/steam-workshop/workspaces/{workspace['workspace_id']}"
        "/generate-description"
    )
    payload = {
        "user_template": "[b]Remis[/b]",
        "target_language_name": "简体中文",
        "language": "zh-CN",
        "provider": "lm_studio",
        "model": "google/gemma-4-31b-qat",
        "approved": False,
    }
    denied = client.post(endpoint, json=payload)
    assert denied.status_code == 409

    monkeypatch.setattr(
        steam_workshop_router.description_generation_service,
        "generate",
        lambda **_kwargs: GeneratedWorkshopDescription(
            bbcode="[h1]Remis 汉化[/h1]",
            source_description="Original",
            source_description_sha256=hashlib.sha256(
                b"Original"
            ).hexdigest(),
            workshop_item_id="3538617386",
            provider="lm_studio",
            model="google/gemma-4-31b-qat",
        ),
    )
    payload["approved"] = True
    created = client.post(endpoint, json=payload)

    assert created.status_code == 201, created.text
    assert created.json()["source"] == "model"
    assert created.json()["status"] == "candidate"
    assert created.json()["metadata"]["model"] == "google/gemma-4-31b-qat"
    current = client.get(
        f"/api/steam-workshop/workspaces/{workspace['workspace_id']}"
    ).json()
    assert current["current_description_version_id"] is None
