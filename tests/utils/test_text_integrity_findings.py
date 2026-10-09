import pytest

from scripts.core.services.workshop_writeback_service import is_repairable_workshop_issue
from scripts.utils.post_process_validator import validate_entry
from scripts.utils.text_integrity_findings import (
    line_break_count,
    quotes_paired,
    text_integrity_findings,
)


@pytest.mark.parametrize("text, paired", [
    ('He said "hi"', True),
    ("他说“你好”", True),
    ("Er sagte „Hallo“", True),
    ("Il a dit « Bonjour »", True),
    ("「こんにちは」", True),
    ('Escaped \\"pair\\"', True),
    ('odd " quote', False),
    ("他说“你好", False),
    ("« Bonjour", False),
])
def test_quote_pairing(text, paired):
    assert quotes_paired(text) is paired


def test_line_break_count_counts_literal_and_real_newlines():
    assert line_break_count("a\\nb\\n\\nc\nd") == 4


def test_findings_are_review_only_and_never_repairable():
    findings = text_integrity_findings('Say "hi"\\n\\nNext', 'Say "hi\\nNext')
    assert [finding["code"] for finding in findings] == [
        "validation_unpaired_quotes",
        "validation_line_break_count_mismatch",
    ]
    for finding in findings:
        assert finding["blocking"] is False
        assert finding["repair_queue"] is False
        assert finding["review_queue"] is True


def test_source_with_unpaired_quotes_is_not_blamed_on_target():
    assert text_integrity_findings('odd " source', 'odd " target') == []


def test_matching_text_has_no_findings():
    assert text_integrity_findings('A "b"\\nC', "A “b”\\nC") == []


def test_validator_emits_warnings_that_stay_out_of_the_repair_queue():
    results = validate_entry(
        "victoria3", "key", '他说"你好', source_value='He said "Hi"\\nNext', target_lang="zh-CN",
    )
    by_code = {result.code: result for result in results}
    for code in ("validation_unpaired_quotes", "validation_line_break_count_mismatch"):
        result = by_code[code]
        assert result.level.value == "warning"
        assert result.details_params["reviewQueue"] is True
        assert result.details_params["repairQueue"] is False
        assert not is_repairable_workshop_issue({"error_code": code, "severity": "warning"})
