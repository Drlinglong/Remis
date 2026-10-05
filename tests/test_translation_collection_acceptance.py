"""Filesystem acceptance through real Mars analysis, CSV validation and export."""
import csv
from pathlib import Path

import pytest

from scripts.core.mars_pipeline import workflow_delivery
from scripts.core.mars_pipeline.prepare_source import analyze_source
from scripts.core.mars_pipeline.publication_identity import read_source_workshop_id
from scripts.core.surviving_mars_csv import HEADER
from scripts.core.translation_collections import packaging


def fixture_member(tmp_path, name, own_id):
    source = tmp_path / name / "source"
    source.mkdir(parents=True)
    (source / "metadata.lua").write_text(
        f"return PlaceObj('ModDef', {{'title', '{name}', 'id', '{name}', 'steam_id', '12345', 'lua_revision', 350453,}})\n",
        encoding="utf-8")
    (source / "items.lua").write_text("return {}\n", encoding="utf-8")
    texts = {"42": "Shared <em>name</em>", str(own_id): "First\n\nSecond <count>"}
    (source / "Code").mkdir()
    (source / "Code" / "Text.lua").write_text("\n".join(
        f"local text{key} = T({key}, [=[{value}]=])" for key, value in texts.items()), encoding="utf-8")
    source_table = source / "ModTexts.csv"
    with source_table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows((key, value, "", "", "") for key, value in texts.items())
    manifest = analyze_source(source)
    manifest["approved_ids"] = list(manifest["entries"])
    folders = {}
    for language in ("zh-CN", "fr", "de"):
        folder = tmp_path / name / (language + "-output")
        folder.mkdir()
        with (folder / "ModTexts.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows((key, value, language + " " + value, "", "") for key, value in texts.items())
        folders[folder.name] = folder
    receipt = {"run_id": name + "-prepared", "source_path": str(source), "manifest": manifest}
    project = {"project_id": name, "game_id": "surviving_mars", "source_path": str(source)}
    return project, receipt, folders


@pytest.mark.asyncio
async def test_real_csv_to_one_multilingual_optional_collection(tmp_path, monkeypatch):
    fixture = {name: fixture_member(tmp_path, name, key) for name, key in (("mod-a", 51), ("mod-b", 52))}
    async def context(project_id):
        return fixture[project_id][:2]
    monkeypatch.setattr(workflow_delivery, "_context", context)
    monkeypatch.setattr(workflow_delivery, "_outputs", lambda p: [
        {"output_folder_name": name, "language_code": name.removesuffix("-output")}
        for name in fixture[p["project_id"]][2]])
    monkeypatch.setattr(workflow_delivery, "_select_output", lambda p, name: fixture[p["project_id"]][2][name])
    collection = {"collection_id": "a" * 32, "mod_id": "RemisCollection" + "a" * 16,
                  "game_id": "surviving_mars", "title": "三语言合集", "description": "测试说明\n第二段",
                  "target_languages": ["zh-CN", "fr", "de"], "steam_id": "3807689989", "revision": 1,
                  "members": [{"project_id": name, "outputs": [
                      {"language_code": code, "output_folder_name": code + "-output"}
                      for code in ("zh-CN", "fr", "de")]} for name in fixture]}
    before = {name: (Path(data[0]["source_path"]) / "metadata.lua").read_bytes() for name, data in fixture.items()}
    inspection = await packaging.inspect_collection(collection)
    assert inspection["can_export"], inspection["diagnostics"]
    assert inspection["entry_count"] == 9  # Shared ID once plus two unique IDs, in three languages.
    destination = tmp_path / "package"
    exported = await packaging.build_collection(collection, destination, inspection["fingerprint"])
    assert exported["file_count"] == inspection["file_count"] == len(list(p for p in destination.rglob("*") if p.is_file()))
    assert read_source_workshop_id(destination) == "3807689989"
    assert {p.name for p in (destination / "Localization").iterdir()} == {"Schinese", "French", "German"}
    assert "ModDependency" not in (destination / "metadata.lua").read_text(encoding="utf-8")
    assert "ModItemLocTable" not in (destination / "items.lua").read_text(encoding="utf-8")
    assert all((Path(data[0]["source_path"]) / "metadata.lua").read_bytes() == before[name] for name, data in fixture.items())
    for path in destination.rglob("*.csv"):
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert all("\\n" not in field for row in rows for field in row)
    # A changed selected CSV cannot be exported with the previous preview.
    changed = fixture["mod-a"][2]["fr-output"] / "ModTexts.csv"
    changed.write_bytes(changed.read_bytes().replace(b"fr First", b"Nouveau First"))
    with pytest.raises(ValueError, match="changed after preview"):
        await packaging.build_collection(collection, tmp_path / "stale", inspection["fingerprint"])
    assert not (tmp_path / "stale").exists()
