import re
import sqlite3

import pytest

from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.steam_workshop_repository import SteamWorkshopRepository
from scripts.core.services.steam_workshop_service import SteamWorkshopService
from scripts.core.steam_workshop_sequence_migration import InvalidSteamWorkshopForeignKeyError


def _legacy_v26(db_path):
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as conn:
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='steam_workshop_asset_versions'"
        ).fetchone()[0]
        sql, count = re.subn(
            r",\s*FOREIGN KEY\(parent_version_id\) REFERENCES steam_workshop_asset_versions \(version_id\)",
            "", sql,
        )
        assert count == 1
        conn.execute("DROP TABLE steam_workshop_asset_versions")
        conn.execute(sql)
        conn.execute("DELETE FROM schema_migrations WHERE version=27")
    repo = SteamWorkshopRepository(str(db_path))
    workspace = repo.create_workspace({"name": "Probe", "game_id": "vic3"})
    data = {
        "workspace_id": workspace["workspace_id"], "asset_type": "description",
        "sha256": "sha", "source": "manual", "description_bbcode": "Hello",
        "description_language": "en",
    }
    parent = repo.create_version(data)
    child = repo.create_version({**data, "parent_version_id": parent["version_id"]})
    return repo, workspace, data, parent, child


def test_fresh_schema_rejects_missing_parent_inside_repository(tmp_path):
    db = tmp_path / "fresh.sqlite"
    migrate_main_database(str(db))
    repo = SteamWorkshopRepository(str(db))
    workspace = repo.create_workspace({"name": "Probe"})
    with sqlite3.connect(db) as conn:
        assert any(row[3] == "parent_version_id" for row in conn.execute(
            "PRAGMA foreign_key_list(steam_workshop_asset_versions)"
        ))
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        repo.create_version({
            "workspace_id": workspace["workspace_id"], "asset_type": "description",
            "parent_version_id": "missing", "sha256": "sha", "source": "manual",
        })


def test_v26_upgrade_preserves_lineage_and_is_idempotent(tmp_path):
    db = tmp_path / "legacy.sqlite"
    repo, workspace, data, parent, child = _legacy_v26(db)
    before = repo.list_versions(workspace["workspace_id"])
    assert migrate_main_database(str(db)) == MAIN_DB_TARGET_VERSION
    assert migrate_main_database(str(db)) == MAIN_DB_TARGET_VERSION
    assert repo.list_versions(workspace["workspace_id"]) == before
    assert repo.get_version(child["version_id"])["parent_version_id"] == parent["version_id"]
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_version({**data, "parent_version_id": "missing"})


def test_v27_refuses_legacy_orphans_without_discarding_rows(tmp_path):
    db = tmp_path / "orphan.sqlite"
    repo, _workspace, _data, _parent, child = _legacy_v26(db)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE steam_workshop_asset_versions SET parent_version_id='missing' WHERE version_id=?",
                     (child["version_id"],))
    with pytest.raises(InvalidSteamWorkshopForeignKeyError, match="missing parent"):
        migrate_main_database(str(db))
    assert repo.get_version(child["version_id"])["parent_version_id"] == "missing"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=27").fetchone()[0] == 0


def test_v27_recovers_after_ddl_commit_before_ledger_write(tmp_path):
    db = tmp_path / "crash.sqlite"
    _legacy_v26(db)
    def stop(version, _name):
        if version == 27:
            raise RuntimeError("injected ledger crash")
    with pytest.raises(RuntimeError, match="injected ledger crash"):
        migrate_main_database(str(db), after_migration=stop)
    assert migrate_main_database(str(db)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_parent_deleted_after_service_validation_cannot_leave_orphan(tmp_path):
    db = tmp_path / "race.sqlite"
    repo, workspace, data, parent, _child = _legacy_v26(db)
    migrate_main_database(str(db))
    service = SteamWorkshopService(repo, tmp_path / "assets")
    new_child = {**data, "parent_version_id": parent["version_id"]}
    service._validate_common_version(workspace["workspace_id"], new_child, "description")
    repo.delete_version(workspace["workspace_id"], parent["version_id"])
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_version(new_child)
