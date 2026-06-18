# tests/utils/test_post_process_validator.py
import pytest
from scripts.utils.post_process_validator import PostProcessValidator, ValidationLevel

# Mock source_lang objects for testing
SOURCE_LANG_ZH = {"code": "zh-CN", "name": "简体中文"}
SOURCE_LANG_JA = {"code": "ja", "name": "日本語"}
SOURCE_LANG_EN = {"code": "en", "name": "English"}

@pytest.fixture
def validator():
    """Provides a PostProcessValidator instance for testing."""
    return PostProcessValidator()

def test_residual_punctuation_check_finds_chinese_issue(validator, mocker):
    """
    Tests that the check correctly identifies Chinese punctuation when source is Chinese.
    We mock the i18n function to assert against the message key directly.
    """
    # Mock i18n.t to return the key and its arguments, making the test language-agnostic yet verifiable.
    mocker.patch("scripts.utils.post_process_validator.i18n.t", side_effect=lambda key, **kwargs: f"{key} {kwargs}")

    game_id = "1"  # Victoria 3
    test_text = "This is a translated sentence，but it still contains a Chinese comma。"

    results = validator.validate_game_text(game_id, test_text, 1, SOURCE_LANG_ZH)

    assert len(results) > 0, "Validator should have found at least one issue."

    punc_result = next((r for r in results if "validation_residual_punctuation_found" in r.message), None)

    assert punc_result is not None, "A specific punctuation validation result should be found."
    assert punc_result.is_valid is False
    assert punc_result.level == ValidationLevel.WARNING
    assert punc_result.details_code == "validation_residual_punctuation_details_localized"
    assert punc_result.details_params == {"punctuations": "，, 。"}
    # The details will now be something like: "validation_residual_punctuation_details {'punctuations': '，, 。'}"
    assert "，" in punc_result.details
    assert "。" in punc_result.details


def test_invalid_key_format_exposes_structured_details(validator):
    result = validator.validate_entry("victoria3", "bad key", "Value", 3)[0]

    assert result.code == "validation_invalid_key_format"
    assert result.details_code == "validation_invalid_key_format_details_localized"
    assert result.details_params == {"foundText": "bad key"}

def test_paradox_localization_version_suffix_is_valid(validator):
    results = validator.validate_entry("victoria3", "remis_event.1.t:0", "The Storm's Gift", 3)

    assert not [result for result in results if result.code == "validation_invalid_key_format"]


def test_vic3_format_marker_parity_flags_missing_source_wrapper(validator):
    results = validator.validate_entry(
        "victoria3",
        "remis_event.1.f:0",
        "reminiscent of the legendary Tyrian Purple.",
        12,
        SOURCE_LANG_ZH,
        source_value="像极了传说中早已失传的#r 泰尔紫 (Tyrian Purple)#!。",
        target_lang="en",
    )

    parity_result = next((r for r in results if r.code == "validation_format_marker_parity_mismatch"), None)

    assert parity_result is not None
    assert parity_result.level == ValidationLevel.WARNING
    assert parity_result.details_params == {
        "sourceStartCount": 1,
        "targetStartCount": 0,
        "sourceEndCount": 1,
        "targetEndCount": 0,
    }


def test_vic3_format_marker_parity_allows_translated_text_inside_wrapper(validator):
    """The v1 parity rule only compares wrapper marker counts, not inner text."""
    results = validator.validate_entry(
        "victoria3",
        "remis_event.1.f:0",
        "reminiscent of the legendary #r Tyrian Purple#!.",
        12,
        SOURCE_LANG_ZH,
        source_value="像极了传说中早已失传的#r 泰尔紫 (Tyrian Purple)#!。",
        target_lang="en",
    )

    assert not [r for r in results if r.code == "validation_format_marker_parity_mismatch"]


def test_vic3_mismatched_color_tags_allows_source_preserved_imbalance(validator):
    source = "#tooltippable #tooltip:$BREAKDOWN_TAG$ Pops outside their home land face low Acceptance.#!"
    target = "#tooltippable #tooltip:$BREAKDOWN_TAG$ 处于家园之外的人口接纳较低。#!"

    results = validator.validate_entry(
        "victoria3",
        "EFFECTS_ON_ACCEPTANCE_ut_law_subjecthood_fascist:0",
        target,
        926,
        SOURCE_LANG_EN,
        source_value=source,
        target_lang="zh-CN",
    )

    assert not [r for r in results if r.code == "validation_vic3_color_tags_mismatch"]
    assert not [r for r in results if r.code == "validation_format_marker_parity_mismatch"]


def test_vic3_mismatched_color_tags_still_flags_target_only_imbalance(validator):
    results = validator.validate_entry(
        "victoria3",
        "remis_event.1.f:0",
        "#bold text",
        12,
        SOURCE_LANG_EN,
        source_value="plain text",
        target_lang="zh-CN",
    )

    assert [r for r in results if r.code == "validation_vic3_color_tags_mismatch"]
    assert [r for r in results if r.code == "validation_format_marker_parity_mismatch"]


def test_residual_punctuation_check_finds_japanese_issue(validator, mocker):
    """
    Tests that the check correctly identifies Japanese punctuation when source is Japanese.
    """
    mocker.patch("scripts.utils.post_process_validator.i18n.t", side_effect=lambda key, **kwargs: f"{key} {kwargs}")

    game_id = "1" # Any game, the check is universal
    test_text = "A sentence with Japanese punctuation、like this one。"

    results = validator.validate_game_text(game_id, test_text, 1, SOURCE_LANG_JA)

    assert len(results) > 0, "Validator should have found at least one issue."

    punc_result = next((r for r in results if "validation_residual_punctuation_found" in r.message), None)

    assert punc_result is not None, "A specific punctuation validation result should be found."
    assert "、" in punc_result.details
    assert "。" in punc_result.details

def test_residual_punctuation_check_passes_clean_text(validator, mocker):
    """
    Tests that the check does not raise issues for a clean text, regardless of source language.
    """
    mocker.patch("scripts.utils.post_process_validator.i18n.t", side_effect=lambda key, **kwargs: f"{key} {kwargs}")

    game_id = "1"
    test_text = "This is a perfectly clean sentence."

    results = validator.validate_game_text(game_id, test_text, 1, SOURCE_LANG_ZH)

    punc_result = next((r for r in results if "validation_residual_punctuation_found" in r.message), None)

    assert punc_result is None, "No punctuation issues should be found in clean text."

def test_check_ignores_other_language_punctuation(validator, mocker):
    """
    Tests that the check is specific and doesn't flag punctuation from a different source language.
    """
    mocker.patch("scripts.utils.post_process_validator.i18n.t", side_effect=lambda key, **kwargs: f"{key} {kwargs}")

    game_id = "1"
    # Text contains Chinese punctuation, but we are pretending the source language is English.
    test_text = "This is a translated sentence，but it still contains a Chinese comma。"

    # Since source is English, and English is not in LANGUAGE_PUNCTUATION_CONFIG, it should find nothing.
    results = validator.validate_game_text(game_id, test_text, 1, SOURCE_LANG_EN)

    punc_result = next((r for r in results if "validation_residual_punctuation_found" in r.message), None)

    assert punc_result is None, "Should not find Chinese punctuation when source language is set to English."
