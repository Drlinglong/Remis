from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.core.agents.fix_agent import ReflexionFixAgent


def _issue(target_lang=None, reflection=""):
    return {
        "source": "A #P good#! result.",
        "target": "一个#P 好的#!结果。",
        "error_messages": ["format issue"],
        "error_details": ["Needs repair"],
        "reflection": reflection,
        "target_lang": target_lang,
    }


def test_batch_prompt_only_applies_english_punctuation_rule_to_english_targets():
    agent = ReflexionFixAgent(MagicMock())

    zh_prompt = agent._build_batch_prompt([_issue(target_lang="zh-CN")], "vic3")
    en_prompt = agent._build_batch_prompt([_issue(target_lang="en")], "vic3")

    assert "### TARGET LANGUAGE\nzh-CN" in zh_prompt
    assert "When localizing to English" not in zh_prompt
    assert "### TARGET LANGUAGE\nen" in en_prompt
    assert "When localizing to English" in en_prompt


def test_batch_prompt_includes_retry_diagnostic_reflection():
    agent = ReflexionFixAgent(MagicMock())

    prompt = agent._build_batch_prompt(
        [_issue(reflection="The previous fix dropped a color close tag.")],
        "vic3",
        target_lang_code="zh-CN",
    )

    assert "Diagnostic Reflection: The previous fix dropped a color close tag." in prompt


@pytest.mark.asyncio
async def test_fix_batch_loop_reports_retry_reflection_attempts():
    handler = MagicMock()
    handler.client = MagicMock()
    handler._call_api = MagicMock(side_effect=[
        '["bad translation without tag"]',
        '["A #P good#! result."]',
    ])
    handler.generate_response = AsyncMock(return_value="Restore the missing color tag from the source.")
    agent = ReflexionFixAgent(handler)

    fake_error = SimpleNamespace(
        level=SimpleNamespace(value="error"),
        message="Missing color tag",
        details="The previous repair dropped #P...#!",
    )
    mock_validator = MagicMock()
    mock_validator.validate_entry.side_effect = [[fake_error], []]

    with patch("scripts.utils.post_process_validator.PostProcessValidator", return_value=mock_validator):
        result = await agent.fix_batch_loop(
            issues=[{
                "source_str": "A #P good#! result.",
                "target_str": "bad translation",
                "error_type": "format issue",
                "details": "Missing color tag",
                "key": "demo.key",
                "file_name": "demo_l_english.yml",
                "target_lang": "en",
            }],
            game_id="vic3",
            max_retries=3,
            target_lang_code="en",
        )

    assert result["results"][0]["status"] == "SUCCESS"
    assert result["attempts"][0]["attempt"] == 1
    assert result["attempts"][0]["used_reflection"] is False
    assert result["attempts"][0]["fixed_count"] == 0
    assert result["attempts"][0]["remaining_count"] == 1
    assert result["attempts"][1]["attempt"] == 2
    assert result["attempts"][1]["used_reflection"] is True
    assert result["attempts"][1]["reflections_generated"] == 1
    assert result["attempts"][1]["fixed_count"] == 1
    assert result["attempts"][1]["remaining_count"] == 0
    assert result["max_retries"] == 3
    handler.generate_response.assert_awaited_once()
