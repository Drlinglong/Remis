from pathlib import Path

import pytest

from scripts.core.file_builder import patch_file_content
from scripts.core.services.workshop_writeback_service import apply_translation_fix_to_file
from scripts.core.paradox_localization_parser import (
    parse_file,
    parse_text,
    patch_text,
)
from scripts.utils.quote_extractor import QuoteExtractor


def test_canonical_parser_handles_raw_leading_escaped_quotes_and_comments():
    report = parse_text(
        'l_english:\n'
        ' raw:0 "The ship "Syzygy" has returned." # tail comment\n'
        ' leading:0 ""This will be the end of me," she said."\n'
        ' escaped:0 "The ship \\"Syzygy\\" has returned."\n'
        ' hash:0 "Keep # inside" # outside\n'
    )

    assert report.summary == {
        "raw": 4,
        "syntax_parsed": 4,
        "policy_excluded": 0,
        "eligible": 4,
        "parse_errors": 0,
    }
    assert [entry.key for entry in report.eligible_entries] == [
        "raw:0",
        "leading:0",
        "escaped:0",
        "hash:0",
    ]
    assert report.eligible_entries[0].value == 'The ship "Syzygy" has returned.'
    assert report.eligible_entries[1].value == '"This will be the end of me," she said.'
    assert report.eligible_entries[2].value == 'The ship "Syzygy" has returned.'
    assert report.eligible_entries[3].value == "Keep # inside"


def test_bom_multiline_and_policy_diagnostics_are_explicit(tmp_path: Path):
    path = tmp_path / "sample_l_english.yml"
    path.write_text(
        "l_english:\n"
        ' multiline:0 "first line\n'
        '   second line\\nthird"\n'
        ' pure:0 "$PURE_VARIABLE$"\n'
        ' empty:0 ""\n'
        ' self:0 "self:0"\n',
        encoding="utf-8-sig",
    )

    report = parse_file(path)
    assert report.summary == {
        "raw": 4,
        "syntax_parsed": 4,
        "policy_excluded": 3,
        "eligible": 1,
        "parse_errors": 0,
    }
    entry = report.eligible_entries[0]
    assert entry.line_start == 2
    assert entry.line_end == 3
    assert entry.raw_value == "first line\n   second line\\nthird"
    assert entry.value == entry.raw_value
    reasons = {
        item.key: item.policy_exclusion_reason
        for item in report.policy_excluded_entries
    }
    assert reasons == {
        "pure:0": "pure_variable",
        "empty:0": "empty_value",
        "self:0": "self_referencing_value",
    }


def test_unterminated_value_is_not_silently_dropped():
    report = parse_text(
        'l_english:\n broken:0 "unterminated\n next:0 "valid"\n'
    )
    assert [(entry.key, entry.value) for entry in report.entries] == [("next:0", "valid")]
    assert report.diagnostics[0].code == "unterminated_value"
    assert report.summary["parse_errors"] == 1


def test_key_like_row_with_invalid_value_syntax_is_not_silently_dropped(tmp_path: Path):
    source = "l_english:\n broken:0 noquote\n valid:0 \"value\"\n"
    report = parse_text(source)

    assert [(entry.key, entry.value) for entry in report.entries] == [("valid:0", "value")]
    assert [(item.code, item.line_number) for item in report.diagnostics] == [
        ("invalid_entry_syntax", 2)
    ]
    assert report.summary == {
        "raw": 2,
        "syntax_parsed": 1,
        "policy_excluded": 0,
        "eligible": 1,
        "parse_errors": 1,
    }

    path = tmp_path / "broken_l_english.yml"
    path.write_text(source, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="invalid_entry_syntax"):
        QuoteExtractor.extract_from_file(str(path), strict=True)


def test_span_patch_round_trip_preserves_keys_comments_and_structure():
    source = (
        "l_english:\n"
        ' first:0 "The ship "Syzygy" has returned." # keep\n'
        ' second:0 "line one\n'
        '   line two" # keep too\n'
    )
    report = parse_text(source)
    patched = patch_text(
        source,
        [
            (report.eligible_entries[0], 'Translated "name"'),
            (report.eligible_entries[1], "line A\\nline B"),
        ],
    )
    reparsed = parse_text(patched)
    assert [(entry.key, entry.value) for entry in reparsed.eligible_entries] == [
        ("first:0", 'Translated "name"'),
        ("second:0", "line A\\nline B"),
    ]
    assert "# keep" in patched
    assert "# keep too" in patched
    assert "   line two" not in patched


def test_quote_extractor_and_file_builder_use_canonical_spans(tmp_path: Path):
    path = tmp_path / "sample_l_english.yml"
    path.write_text(
        "l_english:\n"
        ' text:0 "The ship "Syzygy" has returned." # comment\n',
        encoding="utf-8-sig",
    )
    lines, texts, key_map = QuoteExtractor.extract_from_file(str(path))
    assert texts == ['The ship "Syzygy" has returned.']
    assert key_map[0]["entry"].key == "text:0"

    patched = patch_file_content(
        lines,
        texts,
        ['Translated "name"'],
        key_map,
        "l_english",
        "l_simp_chinese",
    )
    reparsed = parse_text("".join(patched))
    assert reparsed.eligible_entries[0].value == 'Translated "name"'
    assert "# comment" in "".join(patched)
    assert "l_simp_chinese:" in "".join(patched)


def test_strict_quote_extractor_rejects_parse_errors(tmp_path: Path):
    path = tmp_path / "broken_l_english.yml"
    path.write_text('l_english:\n broken:0 "unterminated\n', encoding="utf-8-sig")
    with pytest.raises(ValueError, match="unterminated_value"):
        QuoteExtractor.extract_from_file(str(path), strict=True)


def test_workshop_writeback_uses_canonical_span_for_raw_quotes(tmp_path: Path):
    path = tmp_path / "target_l_english.yml"
    path.write_text(
        "l_english:\n"
        ' text:0 "The ship "Syzygy" has returned." # preserve\n',
        encoding="utf-8-sig",
    )
    assert apply_translation_fix_to_file(path, "text:0", 'Translated "name"') is True
    report = parse_file(path)
    assert report.eligible_entries[0].value == 'Translated "name"'
    assert "# preserve" in path.read_text(encoding="utf-8-sig")
