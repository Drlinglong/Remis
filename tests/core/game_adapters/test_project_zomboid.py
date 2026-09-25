from pathlib import Path

import pytest

from scripts.core.game_adapters.project_zomboid import ProjectZomboidAdapter


@pytest.fixture
def adapter() -> ProjectZomboidAdapter:
    return ProjectZomboidAdapter()


def test_json_parse_render_preserves_syntax_and_language_path(adapter, tmp_path):
    # Valid JSON with spacing, escaped quotes, unicode, and a terminal newline.
    source = '{\n  "UI_Test" : "Keep %1 and \\\"quote\\\"",\n  "Other": "\u2603"\n}\n'
    path = tmp_path / "common" / "media/lua/shared/Translate/EN/UI.json"
    doc = adapter.parse_text(source, path, {"stable_relative_path": "common/media/lua/shared/Translate/EN/UI.json"})
    assert len(doc.entries) == 2
    key = doc.entries[0].key
    rendered = adapter.render(doc, {key: "Garder %1 et \"citation\""}, {"code": "fr"})
    output_path, content = next(iter(rendered.items()))
    assert output_path == "common/media/lua/shared/Translate/FR/UI.json"
    assert '"UI_Test" : "Garder %1 et \\\"citation\\\""' in content
    assert '"Other": "☃"' in content
    assert content.endswith("\n")


def test_duplicate_json_keys_remain_visible_and_are_not_collapsed(adapter, tmp_path):
    with pytest.raises(ValueError, match="Duplicate JSON localization keys"):
        adapter.parse_text('{"same":"one", "same":"two"}', tmp_path / "UI.json")


def test_legacy_lua_table_parses_literal_data_only_and_rewrites_values(adapter, tmp_path):
    source = '-- data only\nUI_EN = {\n  UI_First = "First\\nline",\n  ["UI_Second"] = "Second", -- note\n}\n'
    doc = adapter.parse_text(source, tmp_path / "UI_EN.txt", {"stable_relative_path": "media/lua/shared/Translate/EN/UI_EN.txt"})
    output = adapter.render(doc, {doc.entries[1].key: 'Deux "ici"'}, {"key": "l_french"})
    assert output["media/lua/shared/Translate/FR/UI_FR.txt"].endswith('["UI_Second"] = "Deux \\"ici\\"", -- note\n}\n')
    assert "First\\nline" in output["media/lua/shared/Translate/FR/UI_FR.txt"]
    assert "UI_FR = {" in output["media/lua/shared/Translate/FR/UI_FR.txt"]
    with pytest.raises(ValueError, match="literal string"):
        adapter.parse_text('UI_EN = { X = os.execute("bad") }', tmp_path / "UI_EN.txt")


def test_discovery_uses_common_and_closest_compatible_version(adapter, tmp_path):
    common = tmp_path / "common/media/lua/shared/Translate/EN/UI.json"
    selected = tmp_path / "42.10/media/lua/shared/Translate/EN/UI.json"
    newer = tmp_path / "42.16/media/lua/shared/Translate/EN/UI.json"
    for path, body in ((common, '{"common":"c"}'), (selected, '{"version":"v"}'), (newer, '{"newer":"n"}')):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    discovery = adapter.discover(tmp_path, {"key": "l_english"}, "42.15.0")
    assert len(discovery.resources) == 1
    assert discovery.resources[0].path == selected
    assert discovery.resources[0].metadata["stable_relative_path"] == "common/media/lua/shared/Translate/EN/UI.json"


def test_unknown_version_surfaces_inference_and_selects_highest_local_version(adapter, tmp_path):
    common = tmp_path / "common/media/lua/shared/Translate/EN/UI.json"
    older = tmp_path / "42.1.5/media/lua/shared/Translate/EN/UI.json"
    newer = tmp_path / "42.2/media/lua/shared/Translate/EN/UI.json"
    for path in (common, older, newer):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"Key":"Value"}', encoding="utf-8")
    discovery = adapter.discover(tmp_path, {"code": "en"})
    assert [resource.path for resource in discovery.resources] == [newer]
    assert discovery.diagnostics[0].code == "version_selection_inferred"


def test_translation_overlay_identity_and_placeholder_validation(adapter, tmp_path):
    root = tmp_path / "Original"
    (root / "common").mkdir(parents=True)
    (root / "common" / "mod.info").write_text("id=OriginalID\nname=Original Name\n", encoding="utf-8")
    generated = adapter.package_metadata(root, {"code": "zh-CN"}, "42.15.0")
    assert list(generated) == ["common/mod.info"]
    assert "id=remis_translation_OriginalID_" in generated["common/mod.info"]
    assert "require=OriginalID" in generated["common/mod.info"]
    assert "name=Original Name - Remis Translation [CH]" in generated["common/mod.info"]
    assert not adapter.validate("Hello %1 <RGB:1,0,0>", "Bonjour %1 <RGB:1,0,0>")
    assert adapter.validate("Hello %1", "Bonjour %2")[0].code == "placeholder_mismatch"
    assert adapter.validate("Hello %1", "Bonjour %2")[0].severity == "error"


def test_cross_language_and_version_translation_keys_are_stable(adapter, tmp_path):
    source = '{"UI_Key":"Hello"}'
    left = adapter.parse_text(source, tmp_path / "42.1/media/lua/shared/Translate/EN/UI.json",
                              {"category": "UI"})
    right = adapter.parse_text(source, tmp_path / "42.2/media/lua/shared/Translate/FR/UI.json",
                               {"category": "UI"})
    assert left.entries[0].key == right.entries[0].key == "UI::UI_Key"


def test_noop_render_preserves_bom_crlf_and_other_json_lexemes(adapter, tmp_path):
    source = '\ufeff{\r\n  "Key" : "Same",\r\n  "Escaped" : "\\u2603"\r\n}\r\n'
    doc = adapter.parse_text(source, tmp_path / "UI.json", {"category": "UI", "stable_relative_path": "common/media/lua/shared/Translate/EN/UI.json"})
    rendered = adapter.render(doc, {entry.key: entry.value for entry in doc.entries}, {"code": "fr"})
    assert next(iter(rendered.values())) == source


def test_nested_json_shape_is_rejected_with_specific_error(adapter, tmp_path):
    with pytest.raises(ValueError, match="Unsupported nested object"):
        adapter.parse_text('{"Outer":{"Inner":"Value"}}', tmp_path / "UI.json")


def test_workshop_container_requires_single_mod_root(adapter, tmp_path):
    first = tmp_path / "Contents/mods/One/common/media/lua/shared/Translate/EN"
    first.mkdir(parents=True)
    (first.parent.parent.parent.parent.parent.parent / "mod.info").write_text("id=One\n", encoding="utf-8")
    discovery = adapter.discover(tmp_path, {"code": "en"})
    assert not discovery.diagnostics
    assert discovery.metadata["source_root"].endswith("One")


def test_workshop_container_with_multiple_mods_is_blocked(adapter, tmp_path):
    for name in ("One", "Two"):
        mod = tmp_path / "Contents/mods" / name
        (mod / "common").mkdir(parents=True)
        (mod / "common" / "mod.info").write_text(f"id={name}\n", encoding="utf-8")
    discovery = adapter.discover(tmp_path, {"code": "en"})
    assert not discovery.resources
    assert discovery.diagnostics[0].code == "multiple_mod_roots"
    assert discovery.diagnostics[0].severity == "error"


def test_metadata_identity_is_source_id_based_and_infers_common_layout(adapter, tmp_path):
    source = tmp_path / "first-copy"
    version = source / "42.1.5"
    version.mkdir(parents=True)
    (version / "mod.info").write_text("id=Original.Stable\nname=Original\n", encoding="utf-8")
    first = adapter.package_metadata(source, {"code": "fr"})
    moved = tmp_path / "moved-copy"
    (moved / "42.1.5").mkdir(parents=True)
    (moved / "42.1.5" / "mod.info").write_text("id=Original.Stable\nname=Original\n", encoding="utf-8")
    second = adapter.package_metadata(moved, {"code": "fr"})
    assert list(first) == list(second) == ["common/mod.info"]
    assert first["common/mod.info"] == second["common/mod.info"]
    assert "require=Original.Stable" in first["common/mod.info"]


def test_legacy_noop_keeps_crlf_and_bom_while_output_identifiers_match_target(adapter, tmp_path):
    source = '\ufeffUI_EN = {\r\n  First = "First",\r\n}\r\n'
    path = tmp_path / "UI_EN.txt"
    doc = adapter.parse_text(source, path, {"category": "UI", "language_folder": "EN",
                                            "stable_relative_path": "common/media/lua/shared/Translate/EN/UI_EN.txt"})
    assert doc.entries[0].key == "UI::First"
    output = adapter.render(doc, {doc.entries[0].key: "First"}, {"code": "fr"})
    assert output["common/media/lua/shared/Translate/FR/UI_FR.txt"] == source.replace("UI_EN =", "UI_FR =")


def test_discovery_skips_linked_translation_directory(adapter, tmp_path):
    source = tmp_path / "common/media/lua/shared/Translate/EN"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    (outside / "UI.json").write_text('{"ShouldNotScan":"Value"}', encoding="utf-8")
    source.parent.mkdir(parents=True)
    try:
        source.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are unavailable on this Windows setup")
    discovery = adapter.discover(tmp_path, {"code": "en"}, "42.15")
    assert not discovery.resources


def test_discovery_prunes_linked_subdirectory_but_scans_nested_regular_files(adapter, tmp_path):
    language = tmp_path / "common/media/lua/shared/Translate/EN"
    ordinary = language / "nested/UI.json"
    ordinary.parent.mkdir(parents=True)
    ordinary.write_text('{"Allowed":"Value"}', encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Injected.json").write_text('{"MustNotRead":"Value"}', encoding="utf-8")
    link = language / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are unavailable on this Windows setup")
    discovery = adapter.discover(tmp_path, {"code": "en"}, "42.15")
    assert [resource.path for resource in discovery.resources] == [ordinary]
