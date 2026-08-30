"""Read-only provider checks used before guided workflows create side effects."""

from __future__ import annotations

import os
from typing import Any

import httpx

from scripts.app_settings import API_PROVIDERS, config_manager, get_api_key
from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot


LOCAL_PROVIDER_IDS = {
    "ollama",
    "lm_studio",
    "vllm",
    "koboldcpp",
    "oobabooga",
    "hunyuan",
}


class ProviderReadinessError(Exception):
    """A safe, machine-readable readiness failure with no secret payload."""

    def __init__(self, code: str, message: str, *, checks: dict[str, Any]):
        super().__init__(message)
        self.code = code
        self.message = message
        self.checks = checks

    def as_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": True,
            "checks": self.checks,
        }


def _provider_config(provider_id: str) -> dict[str, Any]:
    provider = API_PROVIDERS.get(provider_id)
    if provider is None:
        try:
            runtime = resolve_provider_runtime_snapshot(provider_id)
        except KeyError as exc:
            raise ProviderReadinessError(
                "invalid_provider",
                "Unknown API provider.",
                checks={"provider": provider_id, "provider_configured": False},
            ) from exc
        return {
            **runtime.config,
            "available_models": [runtime.model_id] if runtime.model_id else [],
            "api_key_env": "profile_secret",
            "_credential_configured": bool(runtime.api_key),
        }
    overrides = config_manager.get_value("provider_config", {}).get(provider_id, {}) or {}
    config = dict(provider)
    config.update({key: value for key, value in overrides.items() if key != "api_key"})
    return config


def _base_url(provider_id: str, config: dict[str, Any]) -> str:
    env_name = config.get("base_url_env")
    return str(
        (os.getenv(env_name) if env_name else None)
        or config.get("api_url")
        or config.get("base_url")
        or ""
    ).strip().rstrip("/")


def _configured_models(config: dict[str, Any]) -> list[str]:
    values = [
        *(config.get("available_models") or []),
        *(config.get("custom_models") or []),
    ]
    selected = config.get("selected_model") or config.get("default_model")
    if selected:
        values.insert(0, selected)
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


async def _probe_local_endpoint(provider_id: str, base_url: str) -> tuple[bool, list[str]]:
    endpoint = f"{base_url}/api/version" if provider_id == "ollama" else f"{base_url}/models"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(endpoint)
        is_success = getattr(response, "is_success", None)
        if is_success is None:
            is_success = getattr(response, "status_code", 500) < 400
        if not is_success:
            return False, []
        if provider_id == "ollama":
            return True, []
        payload = response.json()
        models = payload.get("data", []) if isinstance(payload, dict) else []
        return True, [
            str(item.get("id")).strip()
            for item in models
            if isinstance(item, dict) and item.get("id")
        ]
    except (httpx.HTTPError, ValueError, OSError):
        return False, []


async def check_provider_readiness(provider_id: str, model: str) -> dict[str, Any]:
    """Check credentials, model compatibility, and local reachability read-only."""
    requested_model = str(model or "").strip()
    config = _provider_config(provider_id)
    local = provider_id in LOCAL_PROVIDER_IDS
    env_name = config.get("api_key_env")
    credential_required = bool(env_name)
    credential_configured = (
        bool(config.get("_credential_configured"))
        if env_name == "profile_secret"
        else (bool(get_api_key(provider_id, env_name)) if env_name else True)
    )
    base_url = _base_url(provider_id, config)
    checks: dict[str, Any] = {
        "provider": provider_id,
        "model": requested_model,
        "provider_configured": bool(
            base_url and (not credential_required or credential_configured)
        ),
        "credential_required": credential_required,
        "credential_configured": credential_configured,
        "local": local,
        "endpoint_required": local,
        "endpoint_reachable": None,
        "configured_model": config.get("selected_model") or config.get("default_model"),
        "available_models": [],
    }
    if credential_required and not credential_configured:
        raise ProviderReadinessError(
            "provider_setup_required",
            "Configure the selected provider credential in Remis Settings before continuing.",
            checks=checks,
        )
    if not requested_model:
        raise ProviderReadinessError("model_required", "Model is required.", checks=checks)
    if local and not base_url:
        raise ProviderReadinessError(
            "provider_endpoint_unconfigured",
            "Configure the local provider endpoint in Remis Settings before continuing.",
            checks=checks,
        )

    configured_models = _configured_models(config)
    live_models: list[str] = []
    if local:
        reachable, live_models = await _probe_local_endpoint(provider_id, base_url)
        checks["endpoint_reachable"] = reachable
        if not reachable:
            raise ProviderReadinessError(
                "provider_endpoint_unreachable",
                "The selected local model service is not reachable. Start it or fix its endpoint in Remis Settings.",
                checks=checks,
            )
    # A non-empty live inventory is authoritative. Do not let a stale static
    # catalogue make an unloaded local model appear ready.
    known_models = live_models or configured_models
    checks["available_models"] = known_models[:100]
    if known_models and requested_model not in known_models:
        raise ProviderReadinessError(
            "provider_model_mismatch",
            "The selected model is not available from the configured provider.",
            checks=checks,
        )
    checks["model_compatible"] = True
    return {"ready": True, "checks": checks}


__all__ = ["ProviderReadinessError", "check_provider_readiness"]
