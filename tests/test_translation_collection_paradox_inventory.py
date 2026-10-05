"""Real Paradox parsing and portable collection export regression coverage."""
from pathlib import Path
import json

import pytest

from scripts.core.translation_collections import packaging, sources


@pytest.fixture
def member(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "fr-output"
    output.mkdir()
    project = {"project_id": "member", "game_id": "victoria3",
               "name": "Member", "source_path": str(source)}

    async def project_by_id(project_id):
        assert project_id == "member"
        return project

    def select_output(selected_project, selection):
        assert selected_project == project
        assert selection == {"language_code": "fr", "output_folder_name": "fr-output"}
        return output

    # Only managed project/output resolution is stubbed; parsing, inventory,
    # preview fingerprints and staged package construction remain production code.
    monkeypatch.setattr(sources, "project_by_id", project_by_id)
    monkeypatch.setattr(sources, "select_output", select_output)
    collection = {"collection_id": "a" * 32, "mod_id": "RemisCollection" + "a" * 16,
                  "game_id": "victoria3", "title": "Collection", "revision": 1,
                  "target_languages": ["fr"], "members": [{"project_id": "member", "outputs": [
                      {"language_code": "fr", "output_folder_name": "fr-output"}]}]}
    return project, output, collection


def write_resource(output: Path, name: str, rows: str) -> Path:
    path = output / name
    path.write_text("l_french:\n" + rows, encoding="utf-8")
    return path


@pytest.mark.parametrize("rows", [
    ' KEY:0 "One"\n KEY:0 "Two"\n',
    ' KEY:0 "Same"\n KEY:0 "Same"\n',
    ' KEY:0 "One"\n KEY:1 "Two"\n',
    ' KEY:0 "$OTHER$"\n KEY:0 "Two"\n',
])
def test_same_file_runtime_duplicate_is_rejected_by_real_inventory(member, rows):
    project, output, _ = member
    write_resource(output, "duplicates_l_french.yml", rows)

    with pytest.raises(ValueError, match="Duplicate runtime localization keys"):
        packaging._tree_inventory(output, "victoria3", project, "fr")


@pytest.mark.asyncio
async def test_duplicate_resource_blocks_real_collection_preview_and_build(member, tmp_path):
    _, output, collection = member
    write_resource(output, "ordinary_l_french.yml", ' HELLO:0 "Bonjour"\n')
    write_resource(output, "duplicates_l_french.yml", ' KEY:0 "One"\n KEY:0 "Two"\n')

    inspection = await packaging.inspect_collection(collection)

    assert not inspection["can_export"]
    assert "Duplicate runtime localization keys" in inspection["diagnostics"][0]["message"]
    destination = tmp_path / "package"
    with pytest.raises(ValueError, match="Duplicate runtime localization keys"):
        await packaging.build_collection(collection, destination, inspection["fingerprint"])
    assert not destination.exists()


@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.asyncio
async def test_reference_only_resource_survives_real_inventory_and_package(member, tmp_path, mixed):
    project, output, collection = member
    reference = write_resource(output, "references_l_french.yml",
                               ' NAME:0 "$OTHER_NAME$"\n SELF:0 "$SELF$"\n EMPTY:0 ""\n')
    if mixed:
        write_resource(output, "ordinary_l_french.yml", ' HELLO:0 "Bonjour"\n')
    inventory = packaging._tree_inventory(output, "victoria3", project, "fr")
    reference_fact = next(row for row in inventory if row["path"] == reference.name)
    assert reference_fact["entry_count"] == 3
    assert set(reference_fact["runtime_keys"]) == {"NAME", "SELF", "EMPTY"}

    inspection = await packaging.inspect_collection(collection)
    assert inspection["can_export"], inspection["diagnostics"]
    assert inspection["entry_count"] == 3 + mixed
    destination = tmp_path / "package"
    result = await packaging.build_collection(collection, destination, inspection["fingerprint"])
    manifest = json.loads((destination / "collection.json").read_text(encoding="utf-8"))
    member_directory = destination / manifest["members"][0]["outputs"][0]["directory"]
    assert (member_directory / reference.name).read_bytes() == reference.read_bytes()
    assert result["file_count"] == 3 + mixed


def test_same_runtime_key_in_different_files_remains_a_blocking_conflict(member):
    project, output, _ = member
    write_resource(output, "first_l_french.yml", ' KEY:0 "$FIRST$"\n')
    write_resource(output, "second_l_french.yml", ' KEY:1 "$SECOND$"\n')
    inventory = packaging._tree_inventory(output, "victoria3", project, "fr")
    conflicts = packaging._paradox_conflicts([{"project_id": "member", "outputs": [
        {"language_code": "fr", "files": inventory}]}])
    assert len(conflicts) == 1
    assert conflicts[0]["key"] == "KEY"
    assert conflicts[0]["resolution"] == "same_member_duplicate"
    assert conflicts[0]["translation_conflict"] is True
