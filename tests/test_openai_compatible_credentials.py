from unittest.mock import patch

import pytest

from scripts.core.openai_handler import OpenAIHandler


@pytest.mark.parametrize(
    ("provider_id", "api_key_env", "base_url"),
    [
        ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1"),
        ("kimi", "KIMI_API_KEY", "https://api.moonshot.ai/v1"),
        ("minimax", "MINIMAX_API_KEY", "https://api.minimaxi.com/v1"),
        ("zhipu", "ZHIPU_API_KEY", "https://open.bigmodel.cn/api/paas/v4/"),
    ],
)
def test_openai_compatible_provider_uses_its_declared_credential(
    provider_id,
    api_key_env,
    base_url,
):
    with (
        patch(
            "scripts.core.openai_handler.get_api_key",
            return_value="provider-specific-key",
        ) as get_api_key,
        patch("scripts.core.openai_handler.OpenAI") as client,
    ):
        handler = OpenAIHandler(provider_id)

    get_api_key.assert_called_once_with(provider_id, api_key_env)
    client.assert_called_once_with(
        api_key="provider-specific-key",
        base_url=base_url,
        timeout=300.0,
    )
    assert handler.client is client.return_value


def test_openai_compatible_provider_reports_the_missing_declared_credential():
    with (
        patch("scripts.core.openai_handler.get_api_key", return_value=None),
        patch("scripts.core.openai_handler.OpenAI") as client,
        pytest.raises(ValueError, match="MINIMAX_API_KEY not set"),
    ):
        OpenAIHandler("minimax")

    client.assert_not_called()
