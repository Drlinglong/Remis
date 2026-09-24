from __future__ import annotations

from pathlib import Path

from scripts.core.game_adapters.rimworld import RimWorldAdapter
from scripts.core.game_adapters.rimworld_text import parse_rules_strings, parse_strings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rimworld_adapter" / "Mod"


def _codes(items):
    return {item.code for item in items}


def test_language_folder_maps_remis_codes_and_current_language_records():
    from scripts.app_settings import LANGUAGES

    adapter = RimWorldAdapter()
    expected = {
        "en": "English", "zh-CN": "ChineseSimplified", "fr": "French",
        "de": "German", "es": "Spanish", "ja": "Japanese", "ko": "Korean",
        "pl": "Polish", "pt-BR": "PortugueseBrazilian", "ru": "Russian",
        "tr": "Turkish",
    }
    assert {info["code"]: adapter.language_folder(info) for info in LANGUAGES.values()} == expected
    assert adapter.language_folder({"code": "en"}) == "English"
    assert adapter.language_folder({"code": "zh-CN"}) == "ChineseSimplified"


def test_discover_and_extract_known_v16_defs_fields():
    adapter = RimWorldAdapter()
    found = adapter.discover(FIXTURE, {"folder": "English"}, "1.6.4")
    assert {resource.metadata["kind"] for resource in found.resources} == {"keyed", "strings", "defs"}
    resource = next(item for item in found.resources if item.metadata["kind"] == "defs")
    document = adapter.parse(resource.path, resource.metadata)
    assert [entry.metadata["field_path"] for entry in document.entries] == [
        "label", "description", "ingestible.ingestCommandString"
    ]
    assert any(diagnostic.code == "game_version_unknown" for diagnostic in found.diagnostics) is False


def test_keyed_snapshot_render_preserves_untranslated_source_and_markup():
    adapter = RimWorldAdapter()
    path = FIXTURE / "Languages" / "English" / "Keyed" / "Keys.xml"
    text = path.read_text(encoding="utf-8-sig")
    doc = adapter.parse_text(text, path, {"kind": "keyed", "relative_output_path": "Languages/English/Keyed/Keys.xml"})
    entry = next(item for item in doc.entries if item.key == "Synthetic_Title")
    rendered = adapter.render(doc, {entry.key: "按 {0} 显示 {PAWN_nameDef}"}, {"folder": "ChineseSimplified"})
    output_path, output = next(iter(rendered.items()))
    assert output_path == "Languages/ChineseSimplified/Keyed/Keys.xml"
    assert "<!--" not in output
    assert "按 {0} 显示 {PAWN_nameDef}" in output
    assert "Nested sample" in output


def test_defs_render_to_definjected_without_nontext_fields():
    adapter = RimWorldAdapter()
    path = FIXTURE / "Defs" / "ThingDefs" / "Items.xml"
    doc = adapter.parse_text(path.read_text(encoding="utf-8-sig"), path, {"kind": "defs", "game_version": "1.6.4"})
    values = {entry.key: f"译文 {entry.metadata['field_path']}" for entry in doc.entries}
    outputs = adapter.render(doc, values, {"folder": "ChineseSimplified"})
    assert len(outputs) == 1
    rendered = next(iter(outputs.values()))
    assert "Synthetic_Crystal.ingestible.ingestCommandString" in rendered
    assert "preferability" not in rendered and "statBases" not in rendered


def test_definjected_keys_match_defs_and_output_path_is_version_independent():
    adapter = RimWorldAdapter()
    defs_path = FIXTURE / "Defs" / "ThingDefs" / "Items.xml"
    source = adapter.parse_text(defs_path.read_text(encoding="utf-8-sig"), defs_path, {"kind": "defs", "game_version": "1.6"})
    generated = adapter.render(source, {entry.key: "translated" for entry in source.entries}, {"folder": "ChineseSimplified"})
    target_path = Path("Languages/ChineseSimplified/DefInjected/ThingDef/generated.xml")
    target = adapter.parse_text(next(iter(generated.values())), target_path, {"kind": "definjected"})
    assert {entry.key for entry in source.entries} == {entry.key for entry in target.entries}
    assert all(str(FIXTURE) not in entry.key for entry in source.entries)


def test_rules_strings_translate_only_the_grammar_rhs():
    adapter = RimWorldAdapter()
    path = Path("Defs/RulePacks.xml")
    source_text = "<Defs><RulePackDef><defName>Synthetic_Rules</defName><rulePack><rulesStrings><li>r_event(tag=raid)->[PAWN_nameDef] said {0}</li></rulesStrings></rulePack></RulePackDef></Defs>"
    source = adapter.parse_text(source_text, path, {"kind": "defs", "game_version": "1.6"})
    assert len(source.entries) == 1
    entry = source.entries[0]
    assert entry.value == "[PAWN_nameDef] said {0}"
    generated = adapter.render(source, {entry.key: "[PAWN_nameDef] 说了 {0}"}, {"folder": "ChineseSimplified"})
    xml = next(iter(generated.values()))
    assert "r_event(tag=raid)-&gt;[PAWN_nameDef] 说了 {0}" in xml
    target_path = Path("Languages/ChineseSimplified/DefInjected/RulePackDef/Rules.xml")
    target = adapter.parse_text(xml, target_path, {"kind": "definjected"})
    assert target.entries[0].key == entry.key
    assert target.entries[0].value == "[PAWN_nameDef] 说了 {0}"


def test_package_metadata_uses_stable_package_id_dependency():
    result = RimWorldAdapter().package_metadata(FIXTURE, {"folder": "ChineseSimplified"}, "1.6")
    about = result["About/About.xml"]
    assert "Example.SyntheticMod.ChineseSimplified" in about
    assert "<packageId>Example.SyntheticMod</packageId>" in about
    assert "<li>1.6</li>" in about


def test_nonenglish_source_keeps_explicit_definjected_and_reports_default_fallback(tmp_path):
    defs = tmp_path / "Defs" / "Items.xml"
    defs.parent.mkdir(parents=True)
    defs.write_text("<Defs><ThingDef><defName>Example_Item</defName><label>default</label><description>default description</description></ThingDef></Defs>", encoding="utf-8")
    translated = tmp_path / "Languages" / "Japanese" / "DefInjected" / "ThingDef" / "Items.xml"
    translated.parent.mkdir(parents=True)
    translated.write_text("<LanguageData><Example_Item.label>既存訳</Example_Item.label></LanguageData>", encoding="utf-8")
    found = RimWorldAdapter().discover(tmp_path, {"folder": "Japanese"}, "1.6")
    defs_resource = next(resource for resource in found.resources if resource.metadata["kind"] == "defs")
    doc = RimWorldAdapter().parse(defs_resource.path, defs_resource.metadata)
    assert [entry.metadata["field_path"] for entry in doc.entries] == ["description"]
    assert "source_language_def_fallback" in _codes(found.diagnostics)


def test_render_rejects_documents_with_parse_errors():
    adapter = RimWorldAdapter()
    doc = adapter.parse_text("<LanguageData><K>", Path("Languages/English/Keyed/Bad.xml"), {"kind": "keyed"})
    try:
        adapter.render(doc, {}, {"folder": "ChineseSimplified"})
    except ValueError as exc:
        assert "invalid RimWorld document" in str(exc)
    else:
        raise AssertionError("invalid XML must not silently render")


def test_strings_keep_blank_lines_comments_and_line_endings():
    path = Path("Languages/English/Strings/Names/Words.txt")
    source = "# names\r\nAlpha\r\n\r\nBeta\r\n"
    doc = parse_strings(source, path)
    assert [entry.value for entry in doc.entries] == ["Alpha", "Beta"]
    rendered = RimWorldAdapter().render(doc, {doc.entries[0].key: "阿尔法"}, {"folder": "ChineseSimplified"})
    output = next(iter(rendered.values()))
    assert output == "# names\r\n阿尔法\r\n\r\nBeta\r\n"


def test_rules_strings_only_extracts_rhs_and_keeps_grammar_tokens():
    path = Path("Rules.xml")
    source = "r_event(tag=raid)->[PAWN_nameDef] carries {0}.\naction->fought back\n"
    doc = parse_rules_strings(source, path, {"key": "RulePackDef::Raid.rulesStrings"})
    assert len(doc.entries) == 2
    assert doc.entries[0].value == "[PAWN_nameDef] carries {0}."
    rendered = RimWorldAdapter().render(doc, {doc.entries[0].key: "[PAWN_nameDef] 攜帶 {0}."}, {})
    assert next(iter(rendered.values())) == "r_event(tag=raid)->[PAWN_nameDef] 攜帶 {0}.\naction->fought back\n"
    assert not RimWorldAdapter().validate(doc.entries[0].value, "[PAWN_nameDef] {0} 携带。")


def test_loadfolders_reports_unknown_conditions_without_hiding_candidates(tmp_path):
    (tmp_path / "About").mkdir()
    (tmp_path / "About" / "About.xml").write_text("<ModMetaData><packageId>Example.Mod</packageId></ModMetaData>", encoding="utf-8")
    (tmp_path / "LoadFolders.xml").write_text(
        "<loadFolders><v1.6><li>/</li><li IfModActive=\"Example.DLC\">DLC</li></v1.6></loadFolders>",
        encoding="utf-8",
    )
    candidate = tmp_path / "DLC" / "Languages" / "English" / "Keyed"
    candidate.mkdir(parents=True)
    (candidate / "Keys.xml").write_text("<LanguageData><Visible>yes</Visible></LanguageData>", encoding="utf-8")
    found = RimWorldAdapter().discover(tmp_path, {"folder": "English"}, "1.6")
    assert "loadfolders_condition_unknown" in _codes(found.diagnostics)
    assert any(resource.metadata["condition"].startswith("unresolved:") for resource in found.resources)


def test_external_entities_are_rejected():
    adapter = RimWorldAdapter()
    doc = adapter.parse_text('<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///secret">]><LanguageData><K>&ext;</K></LanguageData>', Path("x.xml"), {"kind": "keyed"})
    assert not doc.entries
    assert doc.metadata["diagnostics"][0]["code"] == "invalid_xml"
