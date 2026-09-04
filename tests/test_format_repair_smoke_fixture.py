"""Regression contract for the multilingual Victoria 3 Format Repair fixture."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.core.paradox_localization_parser import parse_file
from scripts.utils.post_process_validator import PostProcessValidator


FIXTURE_ROOT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "demo_smoke"
    / "format_repair_regression_v1"
)
FORMAT_TAGS = ["BOLD", "blue", "bold", "italic", "warning", "tooltippable", "tooltip"]


def _load_manifest() -> dict:
    return json.loads(
        (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )


def _entries(relative_path: str) -> dict[str, str]:
    report = parse_file(FIXTURE_ROOT / relative_path)
    return {entry.key: entry.value for entry in report.eligible_entries}


def test_manifest_is_a_complete_repair_contract():
    manifest = _load_manifest()
    assert manifest["schema_version"] == 1
    assert manifest["game_id"] == "victoria3"
    assert manifest["target_languages"] == ["zh-CN", "fr", "pl", "tr", "ru"]

    cases = manifest["cases"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["kind"] for case in cases} == {
        "repair",
        "review",
        "control",
        "report_only",
    }
    required_categories = {
        "semantic_token_loss",
        "tag_identity_drift",
        "tag_missing_closer",
        "tag_extra_closer",
        "variable_missing",
        "variable_mutated",
        "variable_boundary_damaged",
        "newline_missing",
        "newline_extra",
        "foreign_language_residue",
        "reasonable_token_reduction",
        "reasonable_token_substitution",
        "source_format_anomaly",
        "invalid_key_report_only",
    }
    assert required_categories <= {case["category"] for case in cases}


def test_broken_entries_and_expected_repairs_match_the_fixture_files():
    manifest = _load_manifest()
    source = _entries("localization/english/format_repair_demo_l_english.yml")
    parsed_targets: dict[str, dict[str, str]] = {}

    for case in manifest["cases"]:
        target = parsed_targets.setdefault(case["file"], _entries(case["file"]))
        if case["kind"] == "report_only":
            raw = (FIXTURE_ROOT / case["file"]).read_text(encoding="utf-8-sig")
            assert f'{case["key"]} "' in raw
            continue

        assert case["key"] in source
        assert case["key"] in target
        current = target[case["key"]]
        expected = case["expected"]
        assert expected is not None
        if case["kind"] == "repair":
            assert current != expected, case["id"]
        else:
            assert current == expected, case["id"]


def test_deterministic_validator_catches_the_structural_subset_only():
    manifest = _load_manifest()
    source = _entries("localization/english/format_repair_demo_l_english.yml")
    validator = PostProcessValidator()

    for case in manifest["cases"]:
        if not case["deterministic_issue_expected"]:
            continue
        if case["kind"] == "report_only":
            continue
        target = _entries(case["file"])[case["key"]]
        results = validator.validate_entry(
            "victoria3",
            case["key"],
            target,
            source_value=source[case["key"]],
            source_lang={"code": "en", "name": "English"},
            target_lang=case["target_language"],
            dynamic_valid_tags=FORMAT_TAGS,
        )
        assert results, case["id"]
