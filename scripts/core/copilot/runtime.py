"""Resolve one provider selection into an immutable runtime snapshot.

This module is deliberately a thin bridge for model-backed features that have
not yet adopted the main translation resolver.  It does not add an adapter or
an inference path; it only combines the existing provider catalog, overrides,
and custom-profile secret reference into the snapshot consumed by handlers.
"""

from __future__ import annotations

from typing import Any

from scripts.app_settings import API_PROVIDERS, DEFAULT_API_PROVIDER, config_manager, get_api_key
from scripts.core.services.custom_provider_profile_service import (
    CUSTOM_ADAPTER_ID,
    LEGACY_PROFILE_ID,
    CustomProviderProfileService,
)
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


def _config_overrides(provider_id: str) -> dict[str, Any]:
    overrides = config_manager.get_value("provider_config", {}) or {}
    if not isinstance(overrides, dict):
        return {}
    value = overrides.get(provider_id, {})
    return dict(value) if isinstance(value, dict) else {}


def _built_in_runtime(selection_id: str, model_id: str | None) -> ProviderRuntimeSnapshot:
    provider = dict(API_PROVIDERS[selection_id])
    overrides = _config_overrides(selection_id)
    selected_model = model_id or overrides.get("selected_model") or provider.get("default_model")
    if selected_model:
        provider["default_model"] = str(selected_model)
    if overrides.get("api_url"):
        provider["base_url"] = overrides["api_url"]
    for key in (
        "prompt_prefix",
        "system_prompt_suffix",
        "reasoning_builtin_enabled",
        "reasoning_preset",
        "custom_parameters",
    ):
        if key in overrides:
            provider[key] = overrides[key]
    env_name = provider.get("api_key_env")
    api_key = get_api_key(selection_id, env_name) if env_name else None
    return ProviderRuntimeSnapshot(
        selection_id=selection_id,
        adapter_id=selection_id,
        display_name=str(provider.get("name") or selection_id),
        model_id=str(selected_model) if selected_model else None,
        config=provider,
        api_key=api_key,
        secret_ref=f"api_keys.{selection_id}" if env_name else None,
    )


def _custom_runtime(selection_id: str, model_id: str | None) -> ProviderRuntimeSnapshot:
    service = CustomProviderProfileService(config_manager, API_PROVIDERS)
    profile_id = LEGACY_PROFILE_ID if selection_id == CUSTOM_ADAPTER_ID else selection_id
    try:
        profile = service.resolve_profile_selection(profile_id)
    except KeyError:
        if selection_id != CUSTOM_ADAPTER_ID:
            raise
        # Preserve the old single custom-provider contract when no profile has
        # been persisted yet.  The profile service will migrate it on its next
        # normal settings access, while model-backed work remains compatible.
        override = _config_overrides(CUSTOM_ADAPTER_ID)
        adapter = dict(API_PROVIDERS.get(CUSTOM_ADAPTER_ID, {}))
        profile = {
            "profile_id": CUSTOM_ADAPTER_ID,
            "adapter_id": CUSTOM_ADAPTER_ID,
            "secret_ref": None,
            "display_name": adapter.get("name", CUSTOM_ADAPTER_ID),
            "api_url": override.get("api_url") or adapter.get("base_url", ""),
            "selected_model": override.get("selected_model") or adapter.get("default_model"),
            "prompt_prefix": override.get("prompt_prefix", ""),
            "system_prompt_suffix": override.get("system_prompt_suffix", ""),
            "reasoning_builtin_enabled": override.get("reasoning_builtin_enabled", False),
            "reasoning_preset": override.get("reasoning_preset"),
            "custom_parameters": override.get("custom_parameters", {}),
        }
    selected_model = model_id or profile.get("selected_model")
    config = {
        "base_url": profile.get("base_url") or profile.get("api_url"),
        "default_model": selected_model,
        "prompt_prefix": profile.get("prompt_prefix", ""),
        "system_prompt_suffix": profile.get("system_prompt_suffix", ""),
        "reasoning_builtin_enabled": profile.get("reasoning_builtin_enabled", False),
        "reasoning_preset": profile.get("reasoning_preset"),
        "custom_parameters": profile.get("custom_parameters", {}),
    }
    secret_ref = profile.get("secret_ref")
    api_key = service.resolve_profile_secret(secret_ref) if secret_ref else None
    return ProviderRuntimeSnapshot(
        selection_id=str(profile.get("profile_id") or selection_id),
        adapter_id=str(profile.get("adapter_id") or CUSTOM_ADAPTER_ID),
        display_name=str(profile.get("display_name") or "Custom Provider"),
        model_id=str(selected_model) if selected_model else None,
        config=config,
        api_key=api_key,
        secret_ref=secret_ref,
    )


def resolve_provider_runtime_snapshot(
    selection_id: str | None,
    model_id: str | None = None,
    *,
    reasoning_override: dict[str, Any] | None = None,
) -> ProviderRuntimeSnapshot:
    """Resolve a provider/profile selection exactly once for one operation."""

    selected = (selection_id or DEFAULT_API_PROVIDER).strip()
    if selected in API_PROVIDERS and selected != CUSTOM_ADAPTER_ID:
        runtime = _built_in_runtime(selected, model_id)
    else:
        runtime = _custom_runtime(selected, model_id)
    if reasoning_override:
        config = dict(runtime.config)
        config.update(reasoning_override)
        runtime = ProviderRuntimeSnapshot(
            selection_id=runtime.selection_id,
            adapter_id=runtime.adapter_id,
            display_name=runtime.display_name,
            model_id=runtime.model_id,
            config=config,
            api_key=runtime.api_key,
            secret_ref=runtime.secret_ref,
        )
    return runtime
