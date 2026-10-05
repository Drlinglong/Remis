from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from scripts.core.translation_collections import packaging


def _pz_paths(base: Path):
    source = base / "source"
    output = base / "output"
    (source / "common").mkdir(parents=True, exist_ok=True)
    (source / "common" / "mod.info").write_text("id=ModOne\nname=Mod One\n", encoding="utf-8")
    resource = output / "common" / "media" / "lua" / "shared" / "Translate" / "FR" / "UI.json"
    resource.parent.mkdir(parents=True, exist_ok=True)
    resource.write_text('{"Greeting":"Bonjour"}\n', encoding="utf-8")
    return source, output


def test_merge_deduplicates_identical_rows_and_unions_owners():
    merged = {}
    first = {"1": {"source": "Hello", "translations": {"fr": "Salut"}, "owners": {"mod-a"}}}
    second = {"1": {"source": "Hello", "translations": {"fr": "Salut"}, "owners": {"mod-b"}}}

    packaging._merge_rows(merged, first)
    packaging._merge_rows(merged, second)

    assert merged["1"]["owners"] == {"mod-a", "mod-b"}
    assert merged["1"]["translations"] == {"fr": "Salut"}


@pytest.mark.parametrize("row", [
    {"source": "Different", "translations": {"fr": "Salut"}, "owners": {"mod-b"}},
    {"source": "Hello", "translations": {"fr": "Bonjour"}, "owners": {"mod-b"}},
])
def test_merge_rejects_source_and_target_conflicts(row):
    merged = {"1": {"source": "Hello", "translations": {"fr": "Salut"}, "owners": {"mod-a"}}}
    with pytest.raises(ValueError, match="conflict"):
        packaging._merge_rows(merged, {"1": row})


def test_collection_identity_is_stable_and_steam_id_is_numeric():
    collection = {"collection_id": "RemisCollectionabc123", "mod_id": "RemisCollectionabc123",
                  "game_id": "surviving_mars", "title": "Collection", "steam_id": "123456"}
    packaging._collection_identity(collection)
    collection["steam_id"] = "source-mod-id"
    with pytest.raises(ValueError, match="steam_id"):
        packaging._collection_identity(collection)


def test_portable_tree_inventory_parses_game_adapter_json_and_generated_metadata(tmp_path: Path):
    source, root = _pz_paths(tmp_path)
    project = {"source_path": str(source)}

    inventory = packaging._tree_inventory(root, "project_zomboid", project, "fr")

    assert [item["path"] for item in inventory] == ["common/media/lua/shared/Translate/FR/UI.json"]
    assert inventory[0]["sha256"] == hashlib.sha256((root / inventory[0]["path"]).read_bytes()).hexdigest()


def test_portable_inventory_rejects_symlink_and_traversal(tmp_path: Path):
    source, root = _pz_paths(tmp_path)
    target = tmp_path / "outside.csv"
    target.write_text("private", encoding="utf-8")
    link = root / "escape.csv"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this host")
    with pytest.raises(ValueError, match="Linked"):
        packaging._tree_inventory(root, "project_zomboid", {"source_path": str(source)}, "fr")
    with pytest.raises(ValueError, match="Unsafe"):
        packaging._safe_relative("../outside.csv")


def test_portable_member_destinations_keep_colliding_filenames_isolated(tmp_path: Path):
    roots = []
    projects = []
    for index in (1, 2):
        source, root = _pz_paths(tmp_path / str(index))
        resource = root / "common" / "media" / "lua" / "shared" / "Translate" / "FR" / "UI.json"
        resource.write_text(f'{{"Greeting":"member-{index}"}}\n', encoding="utf-8")
        roots.append(root)
        projects.append({"project_id": f"project-{index}", "name": f"Mod {index}", "source_path": str(source)})
    staging = tmp_path / "stage"
    staging.mkdir()
    collection = {"collection_id": "RemisCollectionabc123", "game_id": "project_zomboid",
                  "title": "Two mods", "description": "", "target_languages": ["fr"]}
    portable = [{"project": project, "folders": [root]} for project, root in zip(projects, roots)]
    snapshots = [{"project_id": project["project_id"], "outputs": [{"files": packaging._tree_inventory(root, "project_zomboid", project, "fr")}]} for project, root in zip(projects, roots)]

    count = packaging._copy_portable(staging, collection, portable, snapshots, [])

    members = json.loads((staging / "collection.json").read_text(encoding="utf-8"))["members"]
    paths = [staging / row["outputs"][0]["directory"] / "common/media/lua/shared/Translate/FR/UI.json" for row in members]
    assert len(set(path.parent for path in paths)) == 2
    assert ["member-1" in path.read_text(encoding="utf-8") for path in paths] == [True, False]
    assert ["member-2" in path.read_text(encoding="utf-8") for path in paths] == [False, True]
    assert count == 4


def test_portable_inventory_rejects_malformed_adapter_json(tmp_path: Path):
    source, root = _pz_paths(tmp_path)
    resource = root / "common" / "media" / "lua" / "shared" / "Translate" / "FR" / "UI.json"
    resource.write_text("{bad json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid project_zomboid translation resource"):
        packaging._tree_inventory(root, "project_zomboid", {"source_path": str(source)}, "fr")


def test_paradox_conflict_report_only_flags_different_global_values():
    first = {"project_id": "mod-a", "outputs": [{"language_code": "fr", "files": [
        {"path": "a.yml", "runtime_keys": {"global_key": {"source": "source-a", "target": "target-a", "path": "a.yml"}}}]}]}
    same = {"project_id": "mod-b", "outputs": [{"language_code": "fr", "files": [
        {"path": "b.yml", "runtime_keys": {"global_key": {"source": "source-a", "target": "target-a", "path": "b.yml"}}}]}]}
    conflict = {"project_id": "mod-c", "outputs": [{"language_code": "fr", "files": [
        {"path": "c.yml", "runtime_keys": {"global_key": {"source": "source-b", "target": "target-b", "path": "c.yml"}}}]}]}

    rows = packaging._paradox_conflicts([first, same, conflict])

    assert rows == [{"language_code": "fr", "key": "global_key", "projects": ["mod-a", "mod-c"],
                     "paths": ["a.yml", "c.yml"],
                     "source_conflict": True, "translation_conflict": True,
                     "resolution": "mutually_exclusive"},
                    {"language_code": "fr", "key": "global_key", "projects": ["mod-b", "mod-c"],
                     "paths": ["b.yml", "c.yml"],
                     "source_conflict": True, "translation_conflict": True,
                     "resolution": "mutually_exclusive"}]


def test_generated_mars_loader_with_lua_runtime():
    lupa = pytest.importorskip("lupa")
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    members = []
    merged = {}
    for index in range(1, 7):
        member_id = f"mod-{index}"
        members.append({"mod_id": member_id})
        merged[str(index)] = {"source": f"Source {index}", "translations": {
            "fr": f"fr-{index}", "zh-CN": f"zh-{index}"}, "owners": {member_id}}
    generated = packaging._render_mars({"mod_id": "RemisCollectionabc123", "collection_id": "collection",
        "game_id": "surviving_mars", "title": "Collection", "target_languages": ["fr", "zh-CN"]}, members, merged)
    import csv
    import io
    locale_files = {}
    for relative, content in generated.items():
        if relative.startswith("Localization/"):
            values = {row[0]: row[2] for row in list(csv.reader(io.StringIO(content.decode("utf-8"))))[1:]}
            locale_files[f"Mod/RemisCollectionabc123/{relative}"] = values
    loader = generated["Code/RemisCollection.lua"]
    lua.execute("TranslationTable = {}; OnMsg = {}; ModsLoaded = {}; lang = 'French'; "
                "function GetLanguage() return lang end; "
                "function LoadTranslationTableFile(path) "
                "  local rows = locale_files[path]; if rows then for k,v in pairs(rows) do TranslationTable[tonumber(k) or k]=v end end; end")
    lua.globals().locale_files = lua.table_from({path: lua.table_from(values) for path, values in locale_files.items()})
    lua.execute(loader.decode("utf-8"))
    assert lua.eval("next(TranslationTable) == nil")
    lua.execute("ModsLoaded = {{id='mod-1'}}; OnMsg.ModsReloaded()")
    assert lua.eval("TranslationTable[1]") == "fr-1"
    assert lua.eval("TranslationTable[2] == nil")
    lua.execute("TranslationTable[1]='external'; ModsLoaded={}; OnMsg.ModsReloaded()")
    assert lua.eval("TranslationTable[1]") == "external"
    lua.execute("ModsLoaded={{id='mod-1'}}; OnMsg.ModsReloaded()")
    assert lua.eval("TranslationTable[1]") == "fr-1"
    lua.execute("ModsLoaded={}; OnMsg.ModsReloaded()")
    assert lua.eval("TranslationTable[1]") == "external"
    lua.execute("TranslationTable[1]=nil")
    lua.execute("lang = 'Schinese'; OnMsg.TranslationChanged()")
    assert lua.eval("TranslationTable[1] == nil")
    lua.execute("ModsLoaded = {{id='mod-2'}}; OnMsg.ModsReloaded()")
    assert lua.eval("TranslationTable[2]") == "zh-2"
    lua.execute("ModsLoaded = {{id='mod-1'},{id='mod-2'},{id='mod-3'},{id='mod-4'},{id='mod-5'},{id='mod-6'}}; lang='French'; OnMsg.ModsReloaded()")
    assert lua.eval("TranslationTable[1]") == "fr-1"
    assert lua.eval("TranslationTable[3]") == "fr-3"
    assert lua.eval("TranslationTable[2]") == "fr-2"
    lua.execute("ModsLoaded = {}; OnMsg.ModsReloaded()")
    assert lua.eval("next(TranslationTable) == nil")


@pytest.mark.asyncio
async def test_two_optional_mars_members_render_conditional_tables_and_deduplicate(monkeypatch):
    async def member(_collection, item, _selections):
        owner = item["project_id"]
        row = {"7": {"source": "Shared", "translations": {"zh-CN": "共享"}, "owners": {owner}}}
        return {"project_id": owner, "mod_id": owner}, row, {}

    monkeypatch.setattr(packaging, "_mars_member", member)
    collection = {"collection_id": "collection-1", "mod_id": "RemisCollectionabc123",
                  "game_id": "surviving_mars", "title": "Optional mods", "description": "",
                  "target_languages": ["zh-CN"], "steam_id": "", "revision": 1,
                  "members": [{"project_id": "optional-a", "outputs": [{"language_code": "zh-CN", "output_folder_name": "zh-CN-a"}]},
                              {"project_id": "optional-b", "outputs": [{"language_code": "zh-CN", "output_folder_name": "zh-CN-b"}]}]}

    preview = await packaging.inspect_collection(collection)
    files = packaging._render_mars(collection, preview["members"], {
        "7": {"source": "Shared", "translations": {"zh-CN": "共享"}, "owners": {"optional-a", "optional-b"}}
    })
    loader = files["Code/RemisCollection.lua"].decode("utf-8")
    metadata = files["metadata.lua"].decode("utf-8")

    assert preview["can_export"] is True, preview["diagnostics"]
    assert preview["entry_count"] == 1
    assert "enabled[owner]" in loader and "optional-a" in loader and "optional-b" in loader
    assert "'id', \"RemisCollectionabc123\"" in metadata
    assert "dependencies" not in metadata


@pytest.mark.asyncio
async def test_mars_duplicate_id_target_conflict_blocks_inspection(monkeypatch):
    async def member(_collection, item, _selections):
        text = "Un" if item["project_id"] == "optional-a" else "Deux"
        row = {"7": {"source": "Shared", "translations": {"zh-CN": text}, "owners": {item["project_id"]}}}
        return {"project_id": item["project_id"]}, row, {}

    monkeypatch.setattr(packaging, "_mars_member", member)
    collection = {"collection_id": "collection-1", "mod_id": "RemisCollectionabc123",
                  "game_id": "surviving_mars", "title": "Optional mods", "target_languages": ["zh-CN"],
                  "members": [{"project_id": pid, "outputs": [{"language_code": "zh-CN", "output_folder_name": f"zh-CN-{pid}"}]}
                              for pid in ("optional-a", "optional-b")]}

    result = await packaging.inspect_collection(collection)

    assert result["can_export"] is False
    assert "target conflict" in result["diagnostics"][0]["message"]


@pytest.mark.asyncio
async def test_build_rejects_changed_preview_fingerprint_before_creating_destination(monkeypatch, tmp_path: Path):
    async def changed(_collection):
        return ({"can_export": True, "fingerprint": "current", "mode": "portable_translations",
                 "members": []}, [])

    monkeypatch.setattr(packaging, "_inspect", changed)
    destination = tmp_path / "new-package"
    with pytest.raises(ValueError, match="changed after preview"):
        await packaging.build_collection({}, destination, "old-preview")
    assert not destination.exists()


@pytest.mark.asyncio
async def test_cancelled_build_removes_written_staging(monkeypatch, tmp_path: Path):
    staged = asyncio.Event()
    inspection = {"can_export": True, "fingerprint": "preview", "mode": "portable_translations",
                  "members": []}
    calls = 0

    async def inspect(_collection):
        nonlocal calls
        calls += 1
        if calls == 2:
            staged.set()
            await asyncio.Event().wait()
        return inspection, []

    def copy(staging, *_args):
        (staging / "translated.txt").write_text("translated", encoding="utf-8")
        return 1

    monkeypatch.setattr(packaging, "_inspect", inspect)
    monkeypatch.setattr(packaging, "_copy_portable", copy)
    destination = tmp_path / "package"
    task = asyncio.create_task(packaging.build_collection({}, destination, "preview"))
    await asyncio.wait_for(staged.wait(), timeout=5)
    assert list(tmp_path.glob(".remis-collection-*/translated.txt"))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not destination.exists()
    assert not list(tmp_path.glob(".remis-collection-*"))
