import base64
import sqlite3
import struct

import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.steam_workshop_repository import SteamWorkshopRepository
from scripts.core.services.steam_workshop_service import SteamWorkshopService


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 2, 2) + b"content"


@pytest.fixture
def workshop_service(tmp_path):
    db_path = tmp_path / "remis.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO projects (project_id, name, game_id, source_path, "
            "source_language, status) VALUES ('project-1', 'Demo', 'victoria3', "
            "'demo', 'en', 'active')"
        )
    return SteamWorkshopService(
        SteamWorkshopRepository(str(db_path)),
        tmp_path / "assets",
    )


def test_deletes_only_unselected_version_and_detaches_children(workshop_service):
    workspace = workshop_service.create_workspace({"name": "Demo"})
    first = workshop_service.create_description_version(workspace["workspace_id"], {
        "bbcode": "first", "language": "en", "source": "manual",
    })
    second = workshop_service.create_description_version(workspace["workspace_id"], {
        "bbcode": "second", "language": "en", "source": "manual",
        "parent_version_id": first["version_id"],
    })
    workshop_service.select_version(
        workspace["workspace_id"], "description", second["version_id"],
    )

    with pytest.raises(ValueError, match="Selected version cannot be deleted"):
        workshop_service.delete_version(workspace["workspace_id"], second["version_id"])

    workshop_service.delete_version(workspace["workspace_id"], first["version_id"])
    remaining = workshop_service.get_version(second["version_id"])
    assert remaining["parent_version_id"] is None


def test_deleting_cover_version_removes_png(workshop_service):
    workspace = workshop_service.create_workspace({"name": "Demo"})
    cover = workshop_service.create_cover_version(workspace["workspace_id"], {
        "png_base64": base64.b64encode(_png()).decode("ascii"),
        "canvas": {"schema_version": 1, "width": 512, "height": 512, "elements": []},
        "source": "manual",
    })
    path = workshop_service.get_cover_path(cover["version_id"])
    assert path.is_file()

    workshop_service.delete_version(workspace["workspace_id"], cover["version_id"])

    assert not path.exists()
    with pytest.raises(LookupError, match="Version not found"):
        workshop_service.get_version(cover["version_id"])
