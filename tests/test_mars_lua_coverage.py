from pathlib import Path

from scripts.core.services import mars_game_support, mars_lua_coverage
from scripts.core.copilot.game_support import _safe_project_summary


def source(tmp_path: Path) -> Path:
    (tmp_path / "ModTexts.csv").write_text(
        "ID,Text,Translation,VoiceActor,Context\n123,CSV text,,,\n", encoding="utf-8"
    )
    return tmp_path


def test_untranslated_warnings_do_not_expand_csv_translation_coverage(tmp_path):
    root = source(tmp_path)
    code = root / "Code.lua"
    code.write_text('local name = Untranslated("Upgrade")\n'
                    'local desc = Untranslated("Gain " .. count)\n', encoding="utf-8")
    original = code.read_bytes()
    result = mars_game_support.inspect_csv_support(str(root))
    lua = result["hardcoded_lua"]
    assert lua["candidate_count"] == 2
    assert lua["literal_count"] == lua["dynamic_count"] == 1
    assert lua["scan_complete"] and lua["requires_review"]
    assert not lua["included_in_translation"]
    assert len(result["resources"]) == 1 and result["resources"][0]["entry_count"] == 1
    assert any(d["code"] == "hardcoded_lua_outside_csv" for d in result["diagnostics"])
    assert code.read_bytes() == original


def test_decode_and_lexical_errors_make_lua_coverage_partial_without_blocking_csv(tmp_path):
    root = source(tmp_path)
    (root / "Bad.lua").write_bytes(b"\xff")
    (root / "Broken.lua").write_text('Untranslated("unterminated', encoding="utf-8")
    result = mars_game_support.inspect_csv_support(str(root))
    assert not result["hardcoded_lua"]["scan_complete"]
    assert len(result["hardcoded_lua"]["diagnostics"]) == 2
    assert all(d["severity"] == "warning" for d in result["diagnostics"])
    assert result["resources"]


def test_candidate_budget_reports_truncation(tmp_path, monkeypatch):
    root = source(tmp_path)
    (root / "Names.lua").write_text('Untranslated("a")\nUntranslated("b")', encoding="utf-8")
    monkeypatch.setattr(mars_lua_coverage, "MAX_CANDIDATES", 1)
    result = mars_game_support.inspect_csv_support(str(root))["hardcoded_lua"]
    assert result["candidate_count"] == 1
    assert not result["scan_complete"]
    assert result["requires_review"]


def test_byte_budget_and_bom_file_fingerprint(tmp_path, monkeypatch):
    import hashlib
    root = source(tmp_path)
    data = b'\xef\xbb\xbfUntranslated("a")'
    (root / "Names.lua").write_bytes(data)
    result = mars_game_support.inspect_csv_support(str(root))["hardcoded_lua"]
    assert result["candidates"][0]["source_sha256"] == hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(mars_lua_coverage, "MAX_TOTAL_BYTES", 1)
    result = mars_game_support.inspect_csv_support(str(root))["hardcoded_lua"]
    assert not result["scan_complete"] and result["requires_review"]


def test_copilot_sees_coverage_counts_without_raw_code_or_paths(tmp_path):
    root = source(tmp_path)
    (root / "Names.lua").write_text('local name = Untranslated("PRIVATE_TEXT")', encoding="utf-8")
    result = mars_game_support.inspect_csv_support(str(root))
    summary = _safe_project_summary(result)
    assert summary["hardcoded_lua"]["candidate_count"] == 1
    assert summary["hardcoded_lua"]["requires_review"]
    assert "candidates" not in summary["hardcoded_lua"]
    assert "PRIVATE_TEXT" not in str(summary)
    assert str(root) not in str(summary)


def test_csv_beside_unscanned_fpk_never_reports_complete_lua_coverage(tmp_path):
    root = source(tmp_path)
    (root / "ModContent.fpk").write_bytes(b"FLPK fixture is not parsed by support scan")
    result = mars_game_support.inspect_csv_support(str(root))
    assert result["resources"]
    assert not result["hardcoded_lua"]["scan_complete"]
    assert result["hardcoded_lua"]["requires_review"]
    assert any(d["code"] == "compiled_package_unsupported" for d in result["diagnostics"])
