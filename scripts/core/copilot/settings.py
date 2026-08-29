"""Persist and resolve the shared Remis Copilot model configuration."""

from __future__ import annotations

from typing import Any

from scripts.app_settings import API_PROVIDERS, config_manager
from scripts.core.reasoning_policy import describe_reasoning_settings
from scripts.core.reasoning_policy import resolve_reasoning_parameters


CONFIG_KEY = "copilot_settings"
DEFAULT_PROVIDER = "lm_studio"


def _provider_models(provider_id: str) -> list[str]:
    provider = API_PROVIDERS[provider_id]
    overrides = config_manager.get_value("provider_config", {}).get(provider_id, {}) or {}
    models = [
        *provider.get("available_models", []),
        *overrides.get("models", []),
    ]
    default_model = overrides.get("selected_model") or provider.get("default_model")
    if default_model:
        models.append(default_model)
    return list(dict.fromkeys(str(model) for model in models if model))


def _default_model(provider_id: str) -> str:
    provider = API_PROVIDERS[provider_id]
    overrides = config_manager.get_value("provider_config", {}).get(provider_id, {}) or {}
    return str(overrides.get("selected_model") or provider.get("default_model") or "")


def _reasoning(provider_id: str, model: str, enabled: bool, preset: str) -> dict[str, Any]:
    provider_config = dict(API_PROVIDERS[provider_id])
    provider_config.update({
        "default_model": model,
        "reasoning_builtin_enabled": enabled,
        "reasoning_preset": preset,
        "custom_parameters": {},
    })
    return describe_reasoning_settings(provider_config)


def get_copilot_settings() -> dict[str, Any]:
    stored = config_manager.get_value(CONFIG_KEY, {}) or {}
    provider = str(stored.get("provider") or DEFAULT_PROVIDER)
    if provider not in API_PROVIDERS:
        provider = DEFAULT_PROVIDER
    models = _provider_models(provider)
    model = str(stored.get("model") or _default_model(provider))
    if models and model not in models:
        model = _default_model(provider)
    preset = str(stored.get("reasoning_preset") or "medium")
    enabled = bool(stored.get("reasoning_enabled", False))
    reasoning = _reasoning(provider, model, enabled, preset)
    if enabled and (
        not reasoning["supported"]
        or preset not in reasoning["available_presets"]
    ):
        enabled = False
        reasoning = _reasoning(provider, model, False, preset)
    return {
        "provider": provider,
        "model": model,
        "reasoning_enabled": enabled,
        "reasoning_preset": preset,
        "reasoning": reasoning,
    }


def update_copilot_settings(
    *, provider: str, model: str, reasoning_enabled: bool, reasoning_preset: str
) -> dict[str, Any]:
    if provider not in API_PROVIDERS:
        raise ValueError("Unknown API provider")
    models = _provider_models(provider)
    if not model or (models and model not in models):
        raise ValueError("The selected model is not configured for this provider")
    reasoning = _reasoning(provider, model, reasoning_enabled, reasoning_preset)
    if reasoning_enabled and not reasoning["supported"]:
        raise ValueError("The selected model has no verified reasoning mapping")
    if reasoning_enabled and reasoning_preset not in reasoning["available_presets"]:
        raise ValueError("The selected reasoning strength is not supported by this model")
    value = {
        "provider": provider,
        "model": model,
        "reasoning_enabled": reasoning_enabled,
        "reasoning_preset": reasoning_preset,
    }
    config_manager.set_value(CONFIG_KEY, value)
    return get_copilot_settings()


def list_copilot_providers() -> list[dict[str, Any]]:
    result = []
    for provider_id, provider in API_PROVIDERS.items():
        models = _provider_models(provider_id)
        result.append({
            "id": provider_id,
            "name": provider.get("name", provider_id),
            "models": models,
            "default_model": _default_model(provider_id),
            "reasoning_models": (provider.get("reasoning") or {}).get("models", {}),
        })
    return result


def reasoning_override(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "reasoning_builtin_enabled": settings["reasoning_enabled"],
        "reasoning_preset": settings["reasoning_preset"],
        "custom_parameters": {},
    }


def pydantic_reasoning_settings(
    *, provider: str, model: str, enabled: bool, preset: str
) -> dict[str, Any]:
    """Translate the verified Remis mapping to PydanticAI OpenAI settings."""
    provider_config = dict(API_PROVIDERS[provider])
    provider_config.update({
        "default_model": model,
        "reasoning_builtin_enabled": enabled,
        "reasoning_preset": preset,
        "custom_parameters": {},
    })
    parameters = dict(resolve_reasoning_parameters(provider_config).parameters)
    result: dict[str, Any] = {}
    effort = parameters.pop("reasoning_effort", None)
    if effort:
        result["openai_reasoning_effort"] = effort
    if parameters:
        result["extra_body"] = parameters
    return result
