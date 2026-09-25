import json

import pytest

from scripts.core.mars_pipeline import publication_identity as identity
from scripts.core.mars_pipeline.delivery_metadata import _source_copy_mod_id


@pytest.fixture
def publication_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "APP_DATA_DIR", str(tmp_path / "app-data"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "metadata.lua").write_text(
        "return PlaceObj('ModDef', { 'id', 'mars-source', 'steam_id', 3807689989, 'nested', { 'steam_id', 77 } })\n",
        encoding="utf-8",
    )
    receipt = {"project_id": "project-a", "status": "prepared", "source_path": str(source),
               "manifest": {"mod_id": "mars-source"}}
    return source, receipt


def test_binding_persists_across_new_receipt_and_rejects_source_id(publication_scope):
    _, receipt = publication_scope
    assert identity.get_publication_binding("project-a", receipt) == {
        "status": "unbound", "revision": 0, "steam_id": None, "url": None,
        "source_mod_id": "mars-source", "output_mod_id": _source_copy_mod_id("mars-source"),
    }
    with pytest.raises(identity.PublicationIdentityError, match="cannot equal"):
        identity.bind_publication_id("project-a", receipt, "3807689989", 0, True)
    bound = identity.bind_publication_id("project-a", receipt, "76561198000000000", 0, True)
    assert bound["status"] == "bound"
    assert bound["revision"] == 1
    assert bound["url"].endswith("id=76561198000000000")
    fresh_receipt = {**receipt, "run_id": "plan_new_run"}
    assert identity.get_publication_binding("project-a", fresh_receipt) == bound


@pytest.mark.parametrize("value", ["0", "-1", "+3", "01", "18446744073709551616", "not-an-id"])
def test_invalid_workshop_ids_are_rejected(value):
    with pytest.raises(identity.PublicationIdentityError):
        identity.validate_steam_id(value)


def test_binding_uses_optimistic_revision_and_cannot_be_silently_replaced(publication_scope):
    _, receipt = publication_scope
    identity.bind_publication_id("project-a", receipt, "4000000000", 0, True)
    with pytest.raises(identity.PublicationIdentityError, match="changed"):
        identity.bind_publication_id("project-a", receipt, "5000000000", 0, True)
    with pytest.raises(identity.PublicationIdentityError, match="already bound"):
        identity.bind_publication_id("project-a", receipt, "5000000000", 1, True)


def test_binding_rejects_stale_scope_and_corrupt_storage(publication_scope, tmp_path):
    _, receipt = publication_scope
    identity.bind_publication_id("project-a", receipt, "4000000000", 0, True)
    with pytest.raises(identity.PublicationIdentityError, match="different prepared"):
        identity.get_publication_binding("project-a", {**receipt, "manifest": {"mod_id": "changed"}})
    path = identity._storage_path("project-a")
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(identity.PublicationIdentityError, match="corrupt"):
        identity.get_publication_binding("project-a", receipt)


def test_binding_rejects_boolean_revision_and_nonregular_record(publication_scope):
    _, receipt = publication_scope
    path = identity._storage_path("project-a")
    path.write_text(json_record(revision=True), encoding="utf-8")
    with pytest.raises(identity.PublicationIdentityError, match="corrupt"):
        identity.get_publication_binding("project-a", receipt)
    path.unlink()
    path.mkdir()
    with pytest.raises(identity.PublicationIdentityError, match="regular"):
        identity.get_publication_binding("project-a", receipt)


def test_binding_is_project_scoped(publication_scope):
    _, receipt = publication_scope
    identity.bind_publication_id("project-a", receipt, "4000000000", 0, True)
    other_receipt = {**receipt, "project_id": "project-b"}
    assert identity.get_publication_binding("project-b", other_receipt)["status"] == "unbound"


def test_source_workshop_parser_uses_only_top_level_literal(publication_scope):
    source, _ = publication_scope
    assert identity.read_source_workshop_id(source) == "3807689989"
    (source / "metadata.lua").write_text(
        "return PlaceObj('ModDef', { 'id', 'x', 'nested', { 'steam_id', 88 } })\n", encoding="utf-8"
    )
    assert identity.read_source_workshop_id(source) is None


@pytest.mark.parametrize("value", ["0", "'0'"])
def test_zero_source_workshop_id_means_unpublished(publication_scope, value):
    source, _ = publication_scope
    (source / "metadata.lua").write_text(
        f"return PlaceObj('ModDef', {{ 'id', 'x', 'steam_id', {value} }})\n", encoding="utf-8"
    )
    assert identity.read_source_workshop_id(source) is None


def test_duplicate_top_level_source_workshop_ids_fail_closed(publication_scope):
    source, _ = publication_scope
    (source / "metadata.lua").write_text(
        "return PlaceObj('ModDef', { 'id', 'x', 'steam_id', 44, 'steam_id', 55 })\n", encoding="utf-8"
    )
    with pytest.raises(identity.PublicationIdentityError, match="duplicate"):
        identity.read_source_workshop_id(source)


def json_record(revision):
    return json.dumps({"schema_version": 1, "revision": revision, "steam_id": "4000000000",
                       "source_mod_id": "mars-source", "output_mod_id": _source_copy_mod_id("mars-source")})
