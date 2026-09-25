import json

import pytest

from scripts.core.mars_pipeline.prepare_source import analyze_source, prepare_source, rewrite_sources


def _add_metadata(source, mod_id="mod-1"):
    (source / "metadata.lua").write_text(f"return PlaceObj('ModDef', {{'id', '{mod_id}'}})", encoding="utf-8")


def test_analyze_builds_stable_entries_and_reports_untranslated_option_values(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source)
    (source / "Code.lua").write_text(
        'local title = Untranslated("A title")\nlocal desc = Untranslated("Range " .. tostring(BONUS) .. "%")\n',
        encoding="utf-8",
    )
    (source / "items.lua").write_text(
        "return { PlaceObj('ModItemOptionChoice', {'DisplayName', \"Cost\", 'Help', \"Pick a cost\", 'ChoiceList', {\"Low\", \"High\"}}) }",
        encoding="utf-8",
    )
    manifest = analyze_source(source)
    assert manifest["mod_id"] == "mod-1"
    assert len(manifest["entries"]) == 4
    assert all(str(entry["id"]).isdigit() and int(entry["id"]) <= 2**53 - 1 for entry in manifest["entries"].values())
    assert sorted(entry["kind"] for entry in manifest["entries"].values()).count("manual") == 2
    assert any(entry["text"] == "Range <bonus>%" and not entry["review_required"] for entry in manifest["entries"].values())
    assert "ChoiceList" in manifest["diagnostics"][0]["message"]
    again = analyze_source(source, manifest)
    assert [entry["id"] for entry in manifest["entries"].values()] == [entry["id"] for entry in again["entries"].values()]


def test_rewrite_sources_is_review_gated_and_fails_closed_on_stale_bytes(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source)
    lua = source / "Code.lua"
    lua.write_text('local title = Untranslated("Hello")\n', encoding="utf-8")
    manifest = analyze_source(source)
    entry_id = next(iter(manifest["entries"]))
    assert rewrite_sources(source, manifest) == {}
    rewritten = rewrite_sources(source, manifest, {entry_id})
    assert rewritten["Code.lua"].decode() == f'local title = T({entry_id}, "Hello")\r\n'
    lua.write_text('local title = Untranslated("Changed")\n', encoding="utf-8")
    with pytest.raises(ValueError, match="stale Lua source"):
        rewrite_sources(source, manifest, {entry_id})


def test_prepare_source_writes_deterministic_csv_and_refuses_overwrite(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source)
    (source / "Code.lua").write_text('Untranslated("Hello, world")', encoding="utf-8")
    output = tmp_path / "prepared"
    manifest = prepare_source(source, output)
    content = (output / "ModTexts.csv").read_text(encoding="utf-8")
    assert content.startswith("ID,Text,Translation,VoiceActor,Context\n")
    assert "Hello, world" in content
    persisted = json.loads((output / "mars_lua_manifest.json").read_text(encoding="utf-8"))
    assert persisted["source_fingerprint"] == manifest["source_fingerprint"]
    with pytest.raises(FileExistsError):
        prepare_source(source, output)


def test_existing_numeric_t_ids_and_table_arguments_are_preserved(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source)
    lua = source / "Code.lua"
    lua.write_text(
        'T(100000001, "Telepath <amount>")\n'
        'T(9702, "SDK shared")\n'
        'local text = Untranslated{"<resource(stored,max_stored,res_type)>", res_type = res_type, stored = stored}\n',
        encoding="utf-8",
    )
    manifest = analyze_source(source)
    assert manifest["entries"]["100000001"]["kind"] == "existing_t"
    assert "9702" not in manifest["entries"]
    assert [item["id"] for item in manifest["shared_references"]] == ["9702"]
    table_id = next(key for key, item in manifest["entries"].items() if item["kind"] == "table_template")
    rewritten = rewrite_sources(source, manifest, {table_id})["Code.lua"].decode()
    assert f'T{{ {table_id},"<resource(stored,max_stored,res_type)>", res_type = res_type, stored = stored }}' in rewritten


def test_semantic_identity_survives_source_text_edit_and_file_move(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source)
    lua = source / "Code.lua"
    lua.write_text('local UPGRADE_NAME = Untranslated("Before")\n', encoding="utf-8")
    first = analyze_source(source)
    first_id = next(iter(first["entries"]))
    lua.write_text('local UPGRADE_NAME = Untranslated("After")\n', encoding="utf-8")
    moved = source / "nested"
    moved.mkdir()
    lua.rename(moved / "Code.lua")
    second = analyze_source(source, first)
    assert list(second["entries"]) == [first_id]
    assert second["entries"][first_id]["text"] == "After"


def test_string_format_flags_and_escaped_percent_keep_runtime_formatting(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source)
    (source / "Code.lua").write_text(
        'local desc = Untranslated(string.format("Telepathy %02d%%", amount))\n', encoding="utf-8"
    )
    manifest = analyze_source(source)
    entry = next(iter(manifest["entries"].values()))
    assert entry["text"] == "Telepathy <value1>%"
    assert entry["params"] == {"value1": 'string.format("%02d", amount)'}


def test_shuttle_dedup_uses_localized_label_and_recompiles_stale_profile_templates(tmp_path):
    source = tmp_path / "mod"
    source.mkdir()
    _add_metadata(source, "kz4dEz")
    lua = source / "Code" / "Exotics_ShuttleHubUpgrade.lua"
    lua.parent.mkdir()
    lua.write_text(
        'local function InsertLineBeforeThresholds(base_text, line_text)\n'
        '  if string.find(base_text, "From Shuttles", 1, true) then return base_text end\n'
        'end\n'
        'local function caller(base, line)\n'
        '  InsertLineBeforeThresholds(base, line)\n'
        'end\n'
        'local label = Untranslated("Shuttles")\n',
        encoding="utf-8",
    )
    manifest = analyze_source(source)
    shuttle_id = next(key for key, entry in manifest["entries"].items() if entry["text"] == "Shuttles")
    profile = next(item for item in manifest["source_profiles"] if item["name"] == "localized_shuttle_dedup")
    # A persisted legacy renderer template must not override the current reviewed compiler.
    profile["rewrites"][1]["replacement_template"] = '"From " .. shuttle_label'
    rewritten = rewrite_sources(source, manifest, {shuttle_id})[lua.relative_to(source).as_posix()].decode()
    assert 'string.find(base_text, shuttle_label, 1, true)' in rewritten
    assert 'string.find(base_text, "From Shuttles", 1, true)' not in rewritten
    assert '"From " .. shuttle_label' not in rewritten
