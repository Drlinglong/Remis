import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts.app_settings import API_PROVIDERS
from scripts.core.anthropic_handler import AnthropicHandler
from scripts.core.openai_handler import OpenAIHandler
from scripts.core.reasoning_policy import (
    resolve_reasoning_parameters,
    validate_custom_parameters,
)


LOCAL_PROVIDER_IDS = {
    "ollama",
    "lm_studio",
    "vllm",
    "koboldcpp",
    "oobabooga",
    "hunyuan",
    "your_favourite_api",
}


def test_every_cloud_catalog_model_has_an_explicit_reasoning_disposition():
    for provider_id, config in API_PROVIDERS.items():
        models = config.get("available_models")
        if not models or provider_id in LOCAL_PROVIDER_IDS:
            continue
        dispositions = (config.get("reasoning") or {}).get("models") or {}
        assert set(dispositions) == set(models), provider_id


def test_gemini_25_family_is_removed_from_the_presets():
    assert not any(
        model.startswith("gemini-2.5")
        for model in API_PROVIDERS["gemini"]["available_models"]
    )


def test_approved_provider_catalogs_and_defaults_are_locked():
    expected = {
        "gemini": (
            "gemini-3.7-flash",
            ["gemini-3.7-flash", "gemini-3.6-flash"],
        ),
        "anthropic": (
            "claude-sonnet-5",
            ["claude-opus-5", "claude-opus-4-6", "claude-sonnet-5"],
        ),
        "openai": (
            "gpt-5.6-luna",
            ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
        ),
        "qwen": ("qwen3.8-max", ["qwen3.8-max", "qwen3.8-flash-next"]),
        "grok": ("grok-4.6", ["grok-4.6"]),
        "deepseek": (
            "deepseek-v4-flash",
            ["deepseek-v4-pro", "deepseek-v4-flash"],
        ),
        "kimi": ("kimi-k3", ["kimi-k3", "kimi-k2.7-code"]),
        "minimax": (
            "MiniMax-M3",
            ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"],
        ),
        "zhipu": ("glm-5.3-flash", ["glm-5.3-flash"]),
    }

    for provider_id, (default_model, models) in expected.items():
        assert API_PROVIDERS[provider_id]["default_model"] == default_model
        assert API_PROVIDERS[provider_id]["available_models"] == models


def test_curated_aggregator_catalogs_never_infer_reasoning():
    expected = {
        "modelscope": (
            "deepseek-ai/DeepSeek-V4-Flash",
            [
                "deepseek-ai/DeepSeek-V4-Pro",
                "deepseek-ai/DeepSeek-V4-Flash",
            ],
        ),
        "siliconflow": (
            "deepseek-ai/DeepSeek-V4-Flash",
            [
                "deepseek-ai/DeepSeek-V4-Flash",
                "deepseek-ai/DeepSeek-V4-Pro",
            ],
        ),
        "openrouter": (
            "openai/gpt-5.6-luna",
            [
                "openai/gpt-5.6-luna",
                "google/gemini-3.7-flash",
                "qwen/qwen3.8-max",
                "meta/muse-spark-1.2",
            ],
        ),
        "nvidia": (
            "deepseek-ai/deepseek-v4-flash",
            [
                "deepseek-ai/deepseek-v4-flash",
                "deepseek-ai/deepseek-v4-pro",
                "minimaxai/minimax-m3",
            ],
        ),
    }

    for provider_id, (default_model, models) in expected.items():
        config = API_PROVIDERS[provider_id]
        assert config["default_model"] == default_model
        assert config["available_models"] == models
        assert config["reasoning"]["models"] == dict.fromkeys(models)


def test_unknown_custom_model_never_receives_builtin_reasoning_parameters():
    config = {
        **API_PROVIDERS["openai"],
        "default_model": "user/custom-model",
        "reasoning_builtin_enabled": True,
        "reasoning_preset": "high",
        "custom_parameters": {"thinking": {"type": "enabled"}},
    }

    resolution = resolve_reasoning_parameters(config)

    assert resolution.supported is False
    assert resolution.builtin_parameters == {}
    assert resolution.parameters == {"thinking": {"type": "enabled"}}


@pytest.mark.parametrize("model", ["qwen3.8-max"])
def test_qwen_verified_builtin_is_a_single_thinking_toggle(model):
    config = {
        **API_PROVIDERS["qwen"],
        "default_model": model,
        "reasoning_builtin_enabled": True,
        "reasoning_preset": "high",
    }

    resolution = resolve_reasoning_parameters(config)

    assert resolution.available_presets == ("high",)
    assert resolution.parameters == {"enable_thinking": True}


@pytest.mark.parametrize(
    ("preset", "effort"),
    [
        ("low", "high"),
        ("medium", "high"),
        ("high", "high"),
        ("xhigh", "max"),
        ("max", "max"),
    ],
)
def test_deepseek_v4_reasoning_presets_match_current_official_mapping(
    preset,
    effort,
):
    config = {
        **API_PROVIDERS["deepseek"],
        "reasoning_builtin_enabled": True,
        "reasoning_preset": preset,
    }

    resolution = resolve_reasoning_parameters(config)

    assert resolution.parameters == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": effort,
    }


def test_custom_parameters_override_builtin_fields_without_losing_siblings():
    config = {
        **API_PROVIDERS["gemini"],
        "reasoning_builtin_enabled": True,
        "reasoning_preset": "high",
        "custom_parameters": {
            "thinking_config": {
                "thinking_level": "low",
                "include_thoughts": False,
            }
        },
    }

    resolution = resolve_reasoning_parameters(config)

    assert resolution.parameters == {
        "thinking_config": {
            "thinking_level": "low",
            "include_thoughts": False,
        }
    }
    assert resolution.overridden_paths == ("thinking_config.thinking_level",)


def test_current_openai_model_supports_xhigh_reasoning_preset():
    config = {
        **API_PROVIDERS["openai"],
        "default_model": "gpt-5.6-luna",
        "reasoning_builtin_enabled": True,
        "reasoning_preset": "xhigh",
    }

    resolution = resolve_reasoning_parameters(config)

    assert resolution.selected_preset == "xhigh"
    assert resolution.effective_preset == "xhigh"
    assert resolution.builtin_parameters == {"reasoning_effort": "xhigh"}


def test_handler_uses_current_openai_max_preset_without_fallback(caplog):
    handler = OpenAIHandler.__new__(OpenAIHandler)
    handler.provider_name = "openai"
    handler.model_id = "gpt-5.6-luna"
    handler.logger = logging.getLogger("reasoning-preset-fallback-test")

    with (
        patch(
            "scripts.app_settings.config_manager.get_value",
            return_value={
                "openai": {
                    "reasoning_builtin_enabled": True,
                    "reasoning_preset": "max",
                }
            },
        ),
        caplog.at_level(logging.WARNING),
    ):
        parameters = handler._reasoning_request_parameters()

    assert parameters == {"reasoning_effort": "max"}
    assert "using '" not in caplog.text


def test_retired_catalog_ids_do_not_reappear():
    retired = {
        "gemini-3.5-flash",
        "claude-opus-4-1",
        "claude-sonnet-4",
        "gpt-5-mini",
        "qwen-plus",
        "grok-4.3",
        "kimi-k2.6",
        "MiniMax-M2.5",
        "glm-4.7",
        "z-ai/glm-5.2",
        "qwen/qwen3.5-397b-a17b",
    }

    configured = {
        model
        for config in API_PROVIDERS.values()
        for model in config.get("available_models", [])
    }
    assert retired.isdisjoint(configured)


@pytest.mark.parametrize(
    "key",
    ["model", "messages", "prompt", "system", "stream", "authorization"],
)
def test_custom_parameters_cannot_replace_transport_contract(key):
    with pytest.raises(ValueError, match="protected fields"):
        validate_custom_parameters({key: "unsafe"})


def test_openai_handler_sends_verified_reasoning_mapping_through_extra_body():
    captured = {}

    class Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="done"))]
            )

    handler = OpenAIHandler.__new__(OpenAIHandler)
    handler.provider_name = "openai"
    handler.model_id = "gpt-5.6-luna"
    handler.logger = logging.getLogger("reasoning-openai-test")
    handler._reasoning_request_parameters = lambda: {"reasoning_effort": "medium"}

    result = handler._call_api(
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
        "Translate",
    )

    assert result == "done"
    assert captured["extra_body"] == {"reasoning_effort": "medium"}


def test_anthropic_handler_preserves_user_supplied_output_config():
    response = MagicMock()
    response.json.return_value = {"content": [{"type": "text", "text": "done"}]}
    session = MagicMock()
    session.post.return_value = response
    handler = AnthropicHandler.__new__(AnthropicHandler)
    handler.provider_name = "anthropic"
    handler.model_id = "claude-sonnet-5"
    handler.base_url = "https://api.anthropic.com/v1"
    handler.logger = logging.getLogger("reasoning-anthropic-test")

    with patch.object(
        handler,
        "_reasoning_request_parameters",
        return_value={"output_config": {"effort": "medium"}},
    ):
        assert handler._create_message(
            session,
            messages=[{"role": "user", "content": "Translate"}],
            system="System",
        ) == "done"

    payload = session.post.call_args.kwargs["json"]
    assert payload["output_config"] == {"effort": "medium"}
