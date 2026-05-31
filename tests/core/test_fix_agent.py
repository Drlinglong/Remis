from unittest.mock import MagicMock

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
