"""Offline integration checks for Project Zomboid's normal Remis file path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core import file_builder
from scripts.core.game_adapters import workflow_bridge
from scripts.core.game_adapters.output_records import output_record, source_values
from scripts.core.game_adapters import proofreading
from scripts.core.game_adapters.translation_reuse import existing_translations
from scripts.core.services import initial_translation_file_service as output_service
from scripts.core.services.initial_translation_snapshot_service import read_files_for_backup
from scripts.core.services.initial_translation_task_service import _split_reference_hits


PROFILE = {"id": "project_zomboid", "game_version": "42.15.0"}
SOURCE_LANGUAGE = {"code": "en", "key": "l_english"}
TARGET_LANGUAGE = {"code": "zh-CN", "key": "l_simp_chinese"}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _mod(root: Path, mod_id: str, source: str, target: str | None = None) -> tuple[Path, Path]:
    _write(root / "common" / "mod.info", f"id={mod_id}\nname={mod_id} Example\n")
    source_path = root / "common/media/lua/shared/Translate/EN/UI.json"
    _write(source_path, source)
    if target is not None:
        _write(root / "common/media/lua/shared/Translate/CH/UI.json", target)
    return root, source_path


def test_discover_backup_reuse_and_build_use_captured_pz_snapshot(tmp_path, monkeypatch):
    root, source_path = _mod(
        tmp_path / "source" / "One",
        "one.example",
        '{\n  "Existing": "Hello %1",\n  "New": "Translate this %1"\n}\n',
        '{\n  "Existing": "已有翻译 %1"\n}\n',
    )
    before_snapshot = hashlib.sha256(source_path.read_bytes()).hexdigest()
    discovered = workflow_bridge.discover_files(root, PROFILE, SOURCE_LANGUAGE)
    assert len(discovered) == 1
    backup = read_files_for_backup(discovered, len(discovered))
    assert not backup.issues
    file_data = backup.files[0]
    assert file_data["adapter_id"] == "project_zomboid"
    assert file_data["texts_to_translate"] == ["Hello %1", "Translate this %1"]

    # Existing CH text should be protected from the model position list.
    reused = existing_translations(file_data, TARGET_LANGUAGE)
    model_texts, model_positions, preserved = _split_reference_hits(
        file_data["texts_to_translate"], file_data["key_map"], None,
        file_data["file_path"], reused,
    )
    assert reused == {0: "已有翻译 %1"}
    assert model_texts == ["Translate this %1"]
    assert model_positions == [1]
    assert preserved == {0: "已有翻译 %1"}
    assembled = [preserved.get(index, "") for index in range(2)]
    for index, translated in zip(model_positions, ["新译文本 %1"]):
        assembled[index] = translated

    # Simulate a source edit after backup; rendering must consume the captured
    # document, while the later source bytes remain untouched by the output build.
    source_path.write_text('{"Existing":"EDITED AFTER SNAPSHOT","New":"EDITED"}', encoding="utf-8")
    live_source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    monkeypatch.setattr(output_service, "DEST_DIR", str(tmp_path / "built"))
    task = SimpleNamespace(
        file_path=file_data["file_path"], is_custom_loc=False,
        root=file_data["root"], loc_root=file_data["loc_root"],
    )
    dest_dir = output_service.build_dest_dir(task, TARGET_LANGUAGE, "Overlay-One", PROFILE)
    output_path = file_builder.rebuild_and_write_file(
        file_data["original_lines"], file_data["texts_to_translate"], assembled,
        file_data["key_map"], dest_dir, file_data["filename"], SOURCE_LANGUAGE,
        TARGET_LANGUAGE, PROFILE,
    )

    target = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert target == {"Existing": "已有翻译 %1", "New": "新译文本 %1"}
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == live_source_hash
    manifest_root, record = output_record(output_path)
    assert manifest_root is not None
    captured_document = next(iter(file_data["key_map"].values()))["adapter_document"]
    assert record["source_hash"] == hashlib.sha256(captured_document.source_text.encode("utf-8")).hexdigest()
    assert record["source_hash"] == before_snapshot
    assert source_values(output_path) == {entry.key: entry.value for entry in captured_document.entries}
    metadata = Path(manifest_root, "common", "mod.info").read_text(encoding="utf-8")
    assert "id=remis_translation_one.example_ch" in metadata
    assert "require=one.example" in metadata


def test_output_package_rejects_a_different_source_mod(tmp_path):
    first_root, first_path = _mod(tmp_path / "one", "one.example", '{"Shared":"One"}')
    second_root, second_path = _mod(tmp_path / "two", "two.example", '{"Shared":"Two"}')
    adapter = workflow_bridge.resource_adapter("project_zomboid")
    first_meta = {"source_root": str(first_root), "project_root": str(tmp_path),
                  "source_mod_id": "one.example", "category": "UI",
                  "stable_relative_path": "common/media/lua/shared/Translate/EN/UI.json"}
    second_meta = {"source_root": str(second_root), "project_root": str(tmp_path),
                   "source_mod_id": "two.example", "category": "UI",
                   "stable_relative_path": "common/media/lua/shared/Translate/EN/UI.json"}
    first_doc = adapter.parse(first_path, first_meta)
    second_doc = adapter.parse(second_path, second_meta)
    destination = tmp_path / "shared-output"
    workflow_bridge.write_document(first_doc, adapter.id, ["一"], destination, TARGET_LANGUAGE)
    with pytest.raises(ValueError, match="Output package belongs to another source Mod"):
        workflow_bridge.write_document(second_doc, adapter.id, ["二"], destination, TARGET_LANGUAGE)


def test_permissioned_real_mod_mini_fixture_is_readable_when_installed():
    repo_root = Path(__file__).resolve().parents[3]
    root = repo_root / ".runtime/pz-fixture/Contents/mods/TraduccionES_B42"
    source = root / "42/media/lua/shared/Translate/ES/Attributes.json"
    info = root / "42/mod.info"
    if not source.is_file() or not info.is_file():
        pytest.skip("Optional MIT-licensed PZ sample is stored outside Git under .runtime")
    adapter = workflow_bridge.resource_adapter("project_zomboid")
    discovery = adapter.discover(root, {"code": "es"}, "42.19.0")
    resources = [item for item in discovery.resources if item.path.name == "Attributes.json"]
    assert len(resources) == 1
    document = adapter.parse(resources[0].path, resources[0].metadata)
    assert len(document.entries) >= 3
    rendered = adapter.render(document, {document.entries[0].key: document.entries[0].value}, {"code": "en"})
    assert "common/media/lua/shared/Translate/EN/Attributes.json" in rendered
    metadata = adapter.package_metadata(root, {"code": "en"}, "42.19.0")
    assert "require=TraduccionES_B42" in metadata["common/mod.info"]


def test_workshop_container_import_manifest_and_proofread_source_binding(tmp_path, monkeypatch):
    workshop = tmp_path / "steamapps/workshop/content/108600/123456"
    mods = workshop / "Contents/mods"
    mod_root = mods / "WorkshopExample"
    _write(mod_root / "42/mod.info", "id=workshop.example\nname=Workshop Example\n")
    source_path = mod_root / "42/media/lua/shared/Translate/EN/UI.json"
    _write(source_path, '{\n  "Greeting": "Hello %1"\n}\n')

    discovered = workflow_bridge.discover_files(workshop, PROFILE, SOURCE_LANGUAGE)
    assert len(discovered) == 1
    backup = read_files_for_backup(discovered, len(discovered))
    assert not backup.issues
    item = backup.files[0]
    resource = discovered[0]["adapter_metadata"]
    assert Path(resource["project_root"]) == workshop
    assert Path(resource["source_root"]) == mod_root
    assert resource["source_mod_id"] == "workshop.example"

    monkeypatch.setattr(output_service, "DEST_DIR", str(tmp_path / "build"))
    task = SimpleNamespace(file_path=item["file_path"], is_custom_loc=False,
                           root=item["root"], loc_root=item["loc_root"])
    destination = output_service.build_dest_dir(task, TARGET_LANGUAGE,
                                                "Workshop Overlay", PROFILE)
    output_path = file_builder.rebuild_and_write_file(
        item["original_lines"], item["texts_to_translate"], ["你好 %1"],
        item["key_map"], destination, item["filename"], SOURCE_LANGUAGE,
        TARGET_LANGUAGE, PROFILE,
    )
    package_root, record = output_record(output_path)
    assert package_root is not None
    manifest = json.loads((package_root / workflow_bridge.MANIFEST).read_text(encoding="utf-8"))
    manifest_entry = manifest["files"][Path(output_path).relative_to(package_root).as_posix()]
    assert manifest.get("source_mod_id") == "workshop.example"
    assert manifest_entry["source_path"] == "Contents/mods/WorkshopExample/42/media/lua/shared/Translate/EN/UI.json"
    assert source_values(output_path) == {"UI::Greeting": "Hello %1"}
    source_file, language, source_map = proofreading._binding(
        {"source_path": str(workshop)}, Path(output_path),
        workflow_bridge.resource_adapter("project_zomboid"),
    )
    assert source_file.resolve() == source_path.resolve()
    assert language == "zh-CN"
    assert source_map == {"UI::Greeting": "Hello %1"}
    metadata = (package_root / "common/mod.info").read_text(encoding="utf-8")
    assert "require=workshop.example" in metadata
