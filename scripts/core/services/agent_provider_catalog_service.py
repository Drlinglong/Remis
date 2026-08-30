"""Expose built-in providers and saved custom profiles to the Agent API."""

from __future__ import annotations

from typing import Any

from scripts.app_settings import API_PROVIDERS, config_manager, get_api_key
from scripts.core.services.custom_provider_profile_service import CustomProviderProfileService


def _profile_service(api_providers=API_PROVIDERS) -> CustomProviderProfileService:
    return CustomProviderProfileService(config_manager, api_providers)


def agent_provider_catalog(api_providers=API_PROVIDERS) -> dict[str, dict[str, Any]]:
    providers = dict(api_providers)
    if "your_favourite_api" not in providers:
        return providers
    providers.pop("your_favourite_api", None)
    for profile in _profile_service(api_providers).list_profiles():
        providers[profile["profile_id"]] = {
            "name": profile["display_name"],
            "api_key_env": "profile_secret",
        }
    return providers


def agent_key_resolver(
    provider_id: str, env_name: str, api_providers=API_PROVIDERS, builtin_key_resolver=get_api_key,
) -> str | None:
    if provider_id in api_providers:
        return builtin_key_resolver(provider_id, env_name)
    try:
        return _profile_service(api_providers).resolve_runtime(provider_id).api_key
    except KeyError:
        return None


def agent_provider_setup(
    provider_id: str | None, local_provider_ids: set[str], provider_catalog, key_resolver,
) -> dict[str, Any]:
    configured_cloud = [
        item_id
        for item_id, config in provider_catalog.items()
        if config.get("api_key_env")
        and key_resolver(item_id, config["api_key_env"])
    ]
    selected = provider_catalog.get(provider_id) if provider_id else None
    selected_requires_key = bool(selected and selected.get("api_key_env"))
    selected_ready = None
    if selected is not None:
        selected_ready = not selected_requires_key or provider_id in configured_cloud
    return {
        "api_key_configured": bool(configured_cloud),
        "configured_cloud_providers": configured_cloud,
        "selected_provider": provider_id,
        "selected_provider_ready": selected_ready,
        "keyless_local_providers_available": sorted(local_provider_ids),
        "setup_required": selected_ready is False or (selected is None and not configured_cloud),
        "settings_location": "Remis Settings > API Settings",
        "explanation_available": True,
        "explanation": (
            "An API key is a secret credential issued by a model provider. "
            "It lets Remis authenticate model requests and may be tied to billing. "
            "Store it in Remis Settings; never paste it into an Agent chat. "
            "A deliberately selected local provider can be keyless."
        ),
    }
