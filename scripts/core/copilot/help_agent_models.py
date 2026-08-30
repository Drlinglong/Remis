"""Provider factory for the Remis PydanticAI Help Copilot."""

from __future__ import annotations

from typing import Any

from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import (
    OpenAIChatModel,
    OpenAIChatModelSettings,
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from scripts.app_settings import API_PROVIDERS, config_manager, get_api_key
from scripts.core.copilot.settings import pydantic_reasoning_settings
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


def supports_pydantic_help_agent(provider: str) -> bool:
    """Every configured Remis provider enters the tool-agent path."""
    return provider in API_PROVIDERS


def _provider_config(
    provider: str,
    model_name: str | None,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> tuple[dict[str, Any], str, str, str]:
    config = dict(API_PROVIDERS.get(provider, {}))
    if provider_runtime is not None:
        runtime_config = dict(provider_runtime.config)
        base_url = str(runtime_config.get("base_url") or runtime_config.get("api_url") or "")
        selected_model = str(
            provider_runtime.model_id
            or model_name
            or runtime_config.get("default_model")
            or "local-model"
        )
        env_name = str(config.get("api_key_env") or "")
        api_key = provider_runtime.api_key or (
            "local-no-key-required" if not env_name else ""
        )
        if env_name and not api_key:
            raise RuntimeError(f"provider_not_configured: {provider} API key is not configured")
        return runtime_config, base_url, selected_model, api_key
    overrides = config_manager.get_value("provider_config", {}).get(provider, {}) or {}
    base_url = str(overrides.get("api_url") or config.get("base_url") or "")
    selected_model = str(
        model_name or overrides.get("selected_model") or config.get("default_model") or "local-model"
    )
    env_name = str(config.get("api_key_env") or "")
    api_key = get_api_key(provider, env_name) if env_name else "local-no-key-required"
    if env_name and not api_key:
        raise RuntimeError(f"provider_not_configured: {provider} API key is not configured")
    return config, base_url, selected_model, api_key


def _model(provider: str, base_url: str, model_name: str, api_key: str):
    if provider == "openrouter":
        return OpenRouterModel(
            model_name,
            provider=OpenRouterProvider(
                api_key=api_key,
                app_url="https://github.com/Drlinglong/Remis",
                app_title="Remis",
            ),
        ), OpenRouterModelSettings
    if provider == "anthropic":
        return AnthropicModel(
            model_name, provider=AnthropicProvider(api_key=api_key, base_url=base_url or None)
        ), AnthropicModelSettings
    if provider == "gemini":
        return GoogleModel(
            model_name, provider=GoogleProvider(api_key=api_key)
        ), GoogleModelSettings
    if provider == "ollama":
        return OpenAIChatModel(
            model_name, provider=OllamaProvider(base_url=base_url or None)
        ), OpenAIChatModelSettings
    if provider in {"lm_studio", "openai"}:
        return OpenAIResponsesModel(
            model_name, provider=OpenAIProvider(base_url=base_url or None, api_key=api_key)
        ), OpenAIResponsesModelSettings
    return OpenAIChatModel(
        model_name, provider=OpenAIProvider(base_url=base_url or None, api_key=api_key)
    ), OpenAIChatModelSettings


def build_help_model(
    provider: str,
    model_name: str | None,
    reasoning_override: dict[str, Any] | None,
    *,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
):
    """Create a provider-native or OpenAI-compatible tool model and common settings."""
    provider_config, base_url, selected_model, api_key = _provider_config(
        provider,
        model_name,
        provider_runtime,
    )
    model, settings_type = _model(provider, base_url, selected_model, api_key)
    reasoning: dict[str, Any] = {}
    if provider not in {"anthropic", "gemini"}:
        reasoning = pydantic_reasoning_settings(
            provider=provider,
            model=selected_model,
            enabled=bool((reasoning_override or {}).get("reasoning_builtin_enabled")),
            preset=str((reasoning_override or {}).get("reasoning_preset") or "medium"),
            provider_config=provider_config,
        )
    common_settings: dict[str, Any] = {
        "max_tokens": 1200,
        "timeout": 90,
        "parallel_tool_calls": True,
    }
    if provider not in {"openai", "openrouter"}:
        common_settings["temperature"] = 0.1
    settings = settings_type(
        **common_settings,
        **reasoning,
    )
    return model, settings, selected_model
