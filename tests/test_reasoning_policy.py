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


def test_custom_parameters_override_builtin_fields_without_losing_siblings():
    config = {
        **API_PROVIDERS["openrouter"],
        "reasoning_builtin_enabled": True,
        "reasoning_preset": "high",
        "custom_parameters": {"reasoning": {"effort": "low", "exclude": True}},
    }

    resolution = resolve_reasoning_parameters(config)

    assert resolution.parameters == {
        "reasoning": {"effort": "low", "exclude": True}
    }
    assert resolution.overridden_paths == ("reasoning.effort",)


@pytest.mark.parametrize("key", ["model", "messages", "stream", "authorization"])
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
    handler.model_id = "gpt-5.6-terra"
    handler.logger = logging.getLogger("reasoning-openai-test")
    handler._reasoning_request_parameters = lambda: {"reasoning_effort": "medium"}

    result = handler._call_api(
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
        "Translate",
    )

    assert result == "done"
    assert captured["extra_body"] == {"reasoning_effort": "medium"}


def test_anthropic_handler_uses_current_output_config_effort_contract():
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
