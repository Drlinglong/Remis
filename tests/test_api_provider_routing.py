import json
import os
import logging
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.app_settings import API_PROVIDERS
from scripts.core import api_handler
from scripts.core.deepseek_handler import DeepSeekHandler
from scripts.core.openrouter_handler import OpenRouterHandler
from scripts.core.provider_structured_output import structured_output_mode


TURNKEY_CLOUD_PROVIDER_IDS = [
    "gemini",
    "anthropic",
    "openai",
    "qwen",
    "grok",
    "deepseek",
    "openrouter",
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
    "scripts.core.openrouter_handler.OpenAI",
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


def test_deepseek_request_uses_explicit_v4_flash_model():
    captured = {}

    class Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))]
            )

    handler = DeepSeekHandler.__new__(DeepSeekHandler)
    handler.provider_name = "deepseek"
    handler.model_id = "deepseek-v4-flash"
    handler.logger = logging.getLogger("DeepSeekHandlerTest")
    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    assert handler._call_api(client, "Analyze this text") == "{}"
    assert captured["model"] == "deepseek-v4-flash"


def test_openrouter_adapter_uses_isolated_key_and_official_endpoint():
    with (
        patch(
            "scripts.core.openrouter_handler.get_api_key",
            return_value="openrouter-test-key",
        ) as get_api_key,
        patch("scripts.core.openrouter_handler.OpenAI") as client_class,
    ):
        handler = OpenRouterHandler(
            "openrouter",
            model_id="deepseek/deepseek-v4-flash",
        )

    get_api_key.assert_called_once_with("openrouter", "OPENROUTER_API_KEY")
    assert handler.model_id == "deepseek/deepseek-v4-flash"
    client_class.assert_called_once_with(
        api_key="openrouter-test-key",
        base_url="https://openrouter.ai/api/v1",
        timeout=300.0,
        default_headers={
            "HTTP-Referer": "https://github.com/Drlinglong/Remis",
            "X-OpenRouter-Title": "Remis",
        },
    )


def test_openrouter_chat_preserves_provider_failure():
    class FailingCompletions:
        @staticmethod
        def create(**_kwargs):
            raise RuntimeError("openrouter unavailable")

    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler.provider_name = "openrouter"
    handler.model_id = "deepseek/deepseek-v4-flash"
    handler.logger = logging.getLogger("OpenRouterHandlerTest")
    handler.client = SimpleNamespace(
        chat=SimpleNamespace(completions=FailingCompletions())
    )

    with pytest.raises(RuntimeError, match="openrouter unavailable"):
        handler.generate_with_messages(
            [{"role": "user", "content": "Analyze this text"}],
            temperature=0.0,
        )


def test_openrouter_unverified_model_uses_bounded_output_without_builtin_reasoning():
    captured = {}

    class Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))]
            )

    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler.provider_name = "openrouter"
    handler.model_id = "openai/gpt-5.6-luna"
    handler.logger = logging.getLogger("OpenRouterHandlerTest")
    handler.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    assert handler.generate_with_messages(
        [{"role": "user", "content": "Analyze this text"}],
        temperature=0.0,
    ) == "[]"
    assert captured["model"] == "openai/gpt-5.6-luna"
    assert captured["max_tokens"] == 32768
    assert "extra_body" not in captured
    assert "temperature" not in captured


def test_openrouter_luna_structured_chat_sends_json_schema():
    captured = {}

    class Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":[]}'))]
            )

    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler.provider_name = "openrouter"
    handler.model_id = "openai/gpt-5.6-luna"
    handler.logger = logging.getLogger("OpenRouterHandlerTest")
    handler.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "string"}, "default": []},
        },
    }

    result = handler.generate_structured_with_messages(
        [{"role": "user", "content": "Return items"}],
        schema=schema,
        schema_name="items_response",
    )

    assert result == '{"items":[]}'
    assert captured["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "items_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    }
    assert captured["extra_body"] == {
        "provider": {"require_parameters": True},
        "plugins": [{"id": "response-healing"}],
    }


def test_openrouter_structured_chat_retries_invalid_response_envelope_once():
    calls = 0

    class Completions:
        @staticmethod
        def create(**_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise json.JSONDecodeError("Expecting value", "", 0)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":[]}'))]
            )

    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler.provider_name = "openrouter"
    handler.model_id = "openai/gpt-5.6-luna"
    handler.logger = logging.getLogger("OpenRouterHandlerTest")
    handler.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    result = handler.generate_structured_with_messages(
        [{"role": "user", "content": "Return items"}],
        schema={"type": "object", "properties": {}},
        schema_name="items_response",
    )

    assert result == '{"items":[]}'
    assert calls == 2


def test_openrouter_structured_chat_does_not_retry_other_failures():
    calls = 0

    class Completions:
        @staticmethod
        def create(**_kwargs):
            nonlocal calls
            calls += 1
            raise RuntimeError("openrouter unavailable")

    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler.provider_name = "openrouter"
    handler.model_id = "openai/gpt-5.6-luna"
    handler.logger = logging.getLogger("OpenRouterHandlerTest")
    handler.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    with pytest.raises(RuntimeError, match="openrouter unavailable"):
        handler.generate_structured_with_messages(
            [{"role": "user", "content": "Return items"}],
            schema={"type": "object", "properties": {}},
            schema_name="items_response",
        )

    assert calls == 1


def test_openrouter_structured_chat_stops_after_second_invalid_envelope():
    calls = 0

    class Completions:
        @staticmethod
        def create(**_kwargs):
            nonlocal calls
            calls += 1
            raise json.JSONDecodeError("Expecting value", "", 0)

    handler = OpenRouterHandler.__new__(OpenRouterHandler)
    handler.provider_name = "openrouter"
    handler.model_id = "openai/gpt-5.6-luna"
    handler.logger = logging.getLogger("OpenRouterHandlerTest")
    handler.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    with pytest.raises(json.JSONDecodeError):
        handler.generate_structured_with_messages(
            [{"role": "user", "content": "Return items"}],
            schema={"type": "object", "properties": {}},
            schema_name="items_response",
        )

    assert calls == 2


def test_provider_structured_output_capability_is_not_inferred_from_json_prompts():
    assert structured_output_mode("openrouter") == "strict_json_schema"
    for provider_id in (
        "openai", "gemini", "anthropic", "deepseek", "grok", "qwen",
        "siliconflow", "nvidia", "lm_studio", "ollama", "vllm",
    ):
        assert structured_output_mode(provider_id) == "prompt_json_with_local_validation"


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
