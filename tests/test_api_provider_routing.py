import os
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from scripts.app_settings import API_PROVIDERS
from scripts.core import api_handler


TURNKEY_CLOUD_PROVIDER_IDS = [
    "gemini",
    "anthropic",
    "openai",
    "qwen",
    "grok",
    "deepseek",
    "modelscope",
    "siliconflow",
    "kimi",
    "minimax",
    "zhipu",
    "nvidia",
]

CLIENT_CONSTRUCTORS = [
    "scripts.core.gemini_handler.genai.Client",
    "scripts.core.anthropic_handler.requests.Session",
    "scripts.core.openai_handler.OpenAI",
    "scripts.core.qwen_handler.OpenAI",
    "scripts.core.grok_handler.OpenAI",
    "scripts.core.deepseek_handler.OpenAI",
    "scripts.core.modelscope_handler.OpenAI",
    "scripts.core.siliconflow_handler.OpenAI",
    "scripts.core.nvidia_handler.OpenAI",
]


def test_every_configured_provider_has_an_explicit_backend_route():
    assert set(API_PROVIDERS) <= api_handler.SUPPORTED_PROVIDER_IDS


def test_every_configured_default_model_is_in_its_available_catalog():
    for provider_id, config in API_PROVIDERS.items():
        available_models = config.get("available_models")
        if available_models:
            assert config["default_model"] in available_models, provider_id


def test_deepseek_v4_flash_is_selectable_for_context_smoke_tests():
    assert "deepseek-v4-flash" in API_PROVIDERS["deepseek"]["available_models"]


@pytest.mark.parametrize("provider_id", TURNKEY_CLOUD_PROVIDER_IDS)
def test_each_cloud_provider_initializes_with_only_its_declared_key(provider_id):
    declared_env = API_PROVIDERS[provider_id]["api_key_env"]
    all_provider_envs = {
        config["api_key_env"]
        for config in API_PROVIDERS.values()
        if config.get("api_key_env")
    }
    isolated_environment = {
        key: "provider-specific-test-key" if key == declared_env else ""
        for key in all_provider_envs
    }

    def configured_key(requested_provider, requested_env):
        assert requested_provider == provider_id
        assert requested_env == declared_env
        return os.environ.get(requested_env) or None

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, isolated_environment, clear=True))
        stack.enter_context(
            patch(
                "scripts.core.openai_handler.get_api_key",
                side_effect=configured_key,
            )
        )
        stack.enter_context(
            patch(
                "scripts.core.anthropic_handler.get_api_key",
                side_effect=configured_key,
            )
        )
        for constructor in CLIENT_CONSTRUCTORS:
            stack.enter_context(patch(constructor))

        handler = api_handler.get_handler(provider_id, model_name="test-model")

    assert handler.provider_name == provider_id
    assert handler.model_id == "test-model"


@pytest.mark.parametrize(
    ("provider_id", "expected_handler"),
    [
        ("openai", "OpenAIHandler"),
        ("kimi", "OpenAIHandler"),
        ("minimax", "OpenAIHandler"),
        ("zhipu", "OpenAIHandler"),
        ("anthropic", "AnthropicHandler"),
    ],
)
def test_recently_uncovered_cloud_providers_route_explicitly(
    provider_id,
    expected_handler,
):
    handler_class = (
        api_handler.OpenAIHandler
        if expected_handler == "OpenAIHandler"
        else api_handler.AnthropicHandler
    )
    with patch.object(handler_class, "__init__", return_value=None) as initializer:
        handler = api_handler.get_handler(provider_id, model_name="test-model")

    assert isinstance(handler, handler_class)
    initializer.assert_called_once_with(provider_id, model_id="test-model")


def test_unknown_provider_fails_instead_of_falling_back_to_gemini():
    with patch.object(api_handler.GeminiHandler, "__init__", return_value=None) as gemini:
        with pytest.raises(ValueError, match="Unknown API provider: typo-provider"):
            api_handler.get_handler("typo-provider")

    gemini.assert_not_called()
