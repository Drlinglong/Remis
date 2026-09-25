"""Game-observed regression: CSV paragraph breaks must remain real characters."""
import pytest

from scripts.core.surviving_mars_csv import compare_newlines
from scripts.utils.surviving_mars_validator import build_validator


@pytest.mark.parametrize("source,target", [
    ("Requirement\n\nUpgrade\n\nDescription", r"需求\n\n升级\n\n说明"),
    ("Story\nContinuation\n\nEffect", "故事续文效果"),
    ("First\n\nSecond", "第一段\n第二段"),
    ("Plain text", r"普通\n文字"),
])
def test_missing_or_escaped_csv_paragraph_breaks_are_blocking(source, target):
    assert compare_newlines(source, target).is_mismatch
    issues = build_validator().validate_text(target, source_text=source)
    assert [issue.code for issue in issues] == ["validation_surviving_mars_newline_mismatch"]
    assert issues[0].level.value == "error"


@pytest.mark.parametrize("source,target", [
    ("First\n\nSecond", "第一段\n\n第二段"),
    ("First\r\nSecond", "第一行\n第二行"),
    (r"Literal C:\new folder", r"字面路径 C:\new 目录"),
    ("Literal \\n and\nreal newline", "字面量 \\n 和\n真实换行"),
])
def test_valid_newlines_and_intentional_literal_sequences_remain_valid(source, target):
    assert not compare_newlines(source, target).is_mismatch
    assert build_validator().validate_text(target, source_text=source) == []


def test_tags_and_newlines_are_checked_independently():
    issues = build_validator().validate_text("内容", source_text="<em>First</em>\nSecond")
    assert {issue.code for issue in issues} == {
        "validation_surviving_mars_newline_mismatch", "validation_surviving_mars_tag_mismatch",
    }
