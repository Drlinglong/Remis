"""Synthetic-only tests for Surviving Mars package generation.

The fixtures below are authored for this test and contain no game corpus.
"""

import csv
import hashlib
import io
from pathlib import Path
import re

import pytest

from scripts.core import surviving_mars_csv
from scripts.core.services import mars_translation_package as package


def _source_metadata(
    *,
    mod_id="source42",
    title='"Synthetic Mod"',
    version_minor=1,
    description='"Synthetic test metadata"',
):
    return (
        "return PlaceObj('ModDef', {\n"
        f"  'title', {title},\n"
        f"  'description', {description},\n"
        f"  'id', \"{mod_id}\",\n"
        f"  'version_minor', {version_minor},\n"
        "})\n"
    )


def _write_csv(path: Path, rows: list[list[str]], *, sep=True, bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    if sep:
        writer.writerow(["sep=", ""])
    writer.writerow(list(surviving_mars_csv.HEADER))
    writer.writerows(rows)
    content = output.getvalue().encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + content)


def _inputs(tmp_path, *, tables=None, metadata=None):
    source = tmp_path / "source"
    translations = tmp_path / "translation"
    source.mkdir()
    translations.mkdir()
    (source / "metadata.lua").write_text(
        metadata or _source_metadata(), encoding="utf-8", newline=""
    )
    entries_by_name = tables or {
        "ModTexts.csv": [
            ["00001", "Text with, comma <count>", "", "Aide", "entry, one"],
            ["00002", "Original \\\"quoted\\\" text", "", "", "plain context"],
        ]
    }
    for name, rows in entries_by_name.items():
        _write_csv(source / name, rows, bom=True)
        translated = [
            row[:2] + ["译文 " + " ".join(re.findall(r"<[^>]+>", row[1]))] + row[3:]
            for row in rows
        ]
        _write_csv(translations / name, translated, bom=True)
    return source, translations


def _read_output_table(root: Path, relative: str):
    return surviving_mars_csv.parse_file(root / Path(*relative.split("/")))


def test_language_mapping_uses_sdk_language_tokens_and_reports_local_availability():
    assert package.LANGUAGE_NAMES == {
        "zh-CN": "Schinese", "en": "English", "fr": "French", "de": "German",
        "es": "Spanish", "pl": "Polish", "pt-BR": "Brazilian",
        "ru": "Russian", "tr": "Turkish",
    }
    assert package.LANGUAGE_LABELS["es"] == "Spanish (Spain)"
    assert package.LANGUAGE_LABELS["pt-BR"] == "Portuguese (Brazil)"
    assert package.INSTALLED_LANGUAGE_CODES == frozenset(package.LANGUAGE_NAMES)


def test_read_source_metadata_ignores_fake_nested_or_quoted_fields(tmp_path):
    source, _ = _inputs(
        tmp_path,
        metadata=_source_metadata(
            title='"Real \\\"quoted\\\" title"',
            description='"description contains \'id\', \\\"evil\\\", \'title\', \\\"Injected\\\""',
        ),
    )

    assert package.read_source_metadata(source) == {
        "id": "source42",
        "title": 'Real "quoted" title',
    }


def test_metadata_parser_rejects_expressions_for_identity_without_execution(tmp_path):
    source, _ = _inputs(
        tmp_path,
        metadata="return PlaceObj('ModDef', {'title', 'x', 'id', os.execute('echo no')})",
    )

    with pytest.raises(package.TranslationPackageError, match="plain quoted string"):
        package.read_source_metadata(source)


def test_inspect_and_build_emit_translation_only_mod_and_preserve_inputs(tmp_path):
    source, translations = _inputs(tmp_path)
    original_source = {
        path.relative_to(source): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    }
    original_translations = {
        path.relative_to(translations): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in translations.rglob("*") if path.is_file()
    }
    facts = package.inspect_package_inputs(source, translations, "zh-CN")
    destination = tmp_path / "packages" / "plan-1" / facts["package"]["mod_id"]

    result = package.build_package(
        source, translations, "zh-CN", destination,
        expected_fingerprint=facts["fingerprint"],
    )

    assert result["runtime_verified"] is False
    assert result["package_path"] == str(destination)
    assert result["size_bytes"] == facts["package"]["total_size_bytes"]
    actual_files = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    assert actual_files == {
        "metadata.lua",
        "items.lua",
        "Localization/Schinese/ModTexts.csv",
    }
    meta = (destination / "metadata.lua").read_text(encoding="utf-8")
    items = (destination / "items.lua").read_text(encoding="utf-8")
    assert "'id', \"RemisTr" in meta
    assert "'lua_revision', 350453" in meta
    assert "'optional_mod', true" in meta
    assert "'id', \"source42\"" in meta
    assert "'required', true" in meta
    assert "'version_major'" not in meta
    assert "'loctables'" in meta
    assert "'language', \"Schinese\"" in items
    mounted_csv = f"Mod/{facts['package']['mod_id']}/Localization/Schinese/ModTexts.csv"
    assert mounted_csv in items
    assert mounted_csv in meta

    output_doc = _read_output_table(destination, "Localization/Schinese/ModTexts.csv")
    input_doc = surviving_mars_csv.parse_file(source / "ModTexts.csv")
    output_rows = output_doc.rows[output_doc.header_row_index + 1:]
    input_rows = input_doc.rows[input_doc.header_row_index + 1:]
    assert output_rows[0][0] == "00001"
    assert output_rows[0][1] == input_rows[0][1]
    assert output_rows[0][2] == "译文 <count>"
    assert output_rows[0][3:] == input_rows[0][3:]
    assert output_rows[1][0] == "00002"
    assert (source / "ModTexts.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert {
        path.relative_to(source): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    } == original_source
    assert {
        path.relative_to(translations): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in translations.rglob("*") if path.is_file()
    } == original_translations


def test_stable_generated_id_does_not_change_when_source_version_changes(tmp_path):
    source, translations = _inputs(tmp_path)
    initial = package.inspect_package_inputs(source, translations, "zh-CN")
    metadata = (source / "metadata.lua").read_text(encoding="utf-8")
    (source / "metadata.lua").write_text(
        metadata.replace("'version_minor', 1", "'version_minor', 77"),
        encoding="utf-8", newline="",
    )

    changed = package.inspect_package_inputs(source, translations, "zh-CN")

    assert changed["package"]["mod_id"] == initial["package"]["mod_id"]
    assert changed["fingerprint"] != initial["fingerprint"]


def test_generator_change_invalidates_preview_even_when_inputs_are_unchanged(tmp_path, monkeypatch):
    source, translations = _inputs(tmp_path)
    initial = package.inspect_package_inputs(source, translations, "zh-CN")
    monkeypatch.setattr(package, "MIN_LUA_REVISION", package.MIN_LUA_REVISION + 1)
    changed = package.inspect_package_inputs(source, translations, "zh-CN")
    assert changed["fingerprint"] != initial["fingerprint"]
    destination = tmp_path / "not-created"
    with pytest.raises(package.TranslationPackageError, match="changed after preview"):
        package.build_package(source, translations, "zh-CN", destination,
                              expected_fingerprint=initial["fingerprint"])
    assert not destination.exists()


@pytest.mark.parametrize("translated", [r"段落一\n\n段落二", "段落一段落二"])
def test_package_preview_rejects_escaped_or_missing_paragraph_breaks(tmp_path, translated):
    source, translations = _inputs(tmp_path, tables={
        "ModTexts.csv": [["123", "First\n\nSecond", "", "", "Description"]],
    })
    _write_csv(translations / "ModTexts.csv", [["123", "First\n\nSecond", translated, "", "Description"]])
    with pytest.raises(package.TranslationPackageError, match="CSV line breaks differ for ID 123"):
        package.inspect_package_inputs(source, translations, "zh-CN")


def test_multiple_recognized_csvs_are_registered_and_other_reports_are_ignored(tmp_path):
    source, translations = _inputs(
        tmp_path,
        tables={
            "Loc/one.csv": [["101", "One", "", "", "ctx"]],
            "Loc/two.csv": [["202", "Two", "", "", "ctx"]],
        },
    )
    (translations / "Proofreading.csv").write_text(
        "ID,Text,Translation,VoiceActor,Context\n999,Report,ignore,,,\n",
        encoding="utf-8",
    )

    facts = package.inspect_package_inputs(source, translations, "zh-CN")
    destination = tmp_path / "package"
    package.build_package(source, translations, "zh-CN", destination)

    csv_outputs = [item["path"] for item in facts["package"]["files"] if item["path"].endswith(".csv")]
    assert csv_outputs == [
        "Localization/Schinese/Loc/one.csv",
        "Localization/Schinese/Loc/two.csv",
    ]
    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    assert metadata.count("filename =") == 2
    assert "Proofreading.csv" not in metadata
    assert (destination / "Localization/Schinese/Loc/one.csv").is_file()
    assert (destination / "Localization/Schinese/Loc/two.csv").is_file()


def test_missing_translation_table_is_omitted_with_warning(tmp_path):
    source, translations = _inputs(
        tmp_path,
        tables={
            "one.csv": [["101", "One", "", "", "ctx"]],
            "two.csv": [["202", "Two", "", "", "ctx"]],
        },
    )
    (translations / "two.csv").unlink()

    facts = package.inspect_package_inputs(source, translations, "zh-CN")

    assert len(facts["package"]["files"]) == 3
    assert facts["warnings"] == ["No matching translation CSV for source table two.csv; table omitted."]


def test_conflicting_translations_for_same_id_across_tables_are_rejected(tmp_path):
    source, translations = _inputs(
        tmp_path,
        tables={
            "one.csv": [["101", "One", "", "", "ctx"]],
            "two.csv": [["101", "One", "", "", "ctx"]],
        },
    )
    _write_csv(translations / "two.csv", [["101", "One", "不同译文", "", "ctx"]])

    with pytest.raises(package.TranslationPackageError, match="Conflicting translations"):
        package.inspect_package_inputs(source, translations, "zh-CN")


def test_source_and_translation_nontranslation_columns_must_match(tmp_path):
    source, translations = _inputs(tmp_path)
    _write_csv(
        translations / "ModTexts.csv",
        [["00001", "Changed source text", "译文", "Aide", "entry, one"],
         ["00002", "Original \\\"quoted\\\" text", "译文", "", "plain context"]],
    )

    with pytest.raises(package.TranslationPackageError, match="Source columns changed"):
        package.inspect_package_inputs(source, translations, "zh-CN")


@pytest.mark.parametrize(
    "translation",
    ["Text without the required tag", "<count(other)>Changed tag argument</count>"],
)
def test_tag_identity_and_parameters_must_be_preserved(tmp_path, translation):
    source, translations = _inputs(
        tmp_path,
        tables={"ModTexts.csv": [["00001", "<count(num)>Original</count>", "", "", "ctx"]]},
    )
    _write_csv(
        translations / "ModTexts.csv",
        [["00001", "<count(num)>Original</count>", translation, "", "ctx"]],
    )

    with pytest.raises(package.TranslationPackageError, match="Tag mismatch"):
        package.inspect_package_inputs(source, translations, "zh-CN")


def test_blank_translation_is_rejected_as_incomplete_package_input(tmp_path):
    source, translations = _inputs(tmp_path)
    original = surviving_mars_csv.parse_file(translations / "ModTexts.csv")
    rows = [list(row) for row in original.rows[original.header_row_index + 1:]]
    rows[0][2] = ""
    _write_csv(translations / "ModTexts.csv", rows)

    with pytest.raises(package.TranslationPackageError, match="Missing translations"):
        package.inspect_package_inputs(source, translations, "zh-CN")


def test_build_rejects_changed_inputs_and_existing_destination(tmp_path):
    source, translations = _inputs(tmp_path)
    facts = package.inspect_package_inputs(source, translations, "zh-CN")
    destination = tmp_path / "package"
    (translations / "ModTexts.csv").write_text(
        (translations / "ModTexts.csv").read_text(encoding="utf-8").replace("译文 <count>", "变更 <count>", 1),
        encoding="utf-8", newline="",
    )
    with pytest.raises(package.TranslationPackageError, match="changed after preview"):
        package.build_package(
            source, translations, "zh-CN", destination,
            expected_fingerprint=facts["fingerprint"],
        )
    assert not destination.exists()

    package.build_package(source, translations, "zh-CN", destination)
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        package.build_package(source, translations, "zh-CN", destination)
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_destination_inside_inputs_is_rejected(tmp_path):
    source, translations = _inputs(tmp_path)

    with pytest.raises(package.TranslationPackageError, match="inside a source"):
        package.build_package(source, translations, "zh-CN", source / "generated")


def test_linked_input_root_is_rejected_and_nested_links_are_not_followed(tmp_path):
    source, translations = _inputs(tmp_path)
    outside = tmp_path / "outside.csv"
    _write_csv(outside, [["001", "Original", "Injected", "", "ctx"]])
    link = translations / "linked.csv"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("This Windows environment does not allow symlink fixtures.")

    assert package.inspect_package_inputs(source, translations, "zh-CN")["translated_entry_count"] == 2
    root_link = tmp_path / "source-link"
    root_link.symlink_to(source, target_is_directory=True)
    with pytest.raises(package.TranslationPackageError, match="non-linked"):
        package.inspect_package_inputs(root_link, translations, "zh-CN")


def test_language_outside_mars_catalog_is_rejected(tmp_path):
    source, translations = _inputs(tmp_path)

    with pytest.raises(package.TranslationPackageError, match="Unsupported Surviving Mars"):
        package.inspect_package_inputs(source, translations, "ja-JP")
