import os
import json
import logging
import copy
import requests
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from scripts.app_settings import API_PROVIDERS, get_api_key, get_appdata_config_path, GAME_PROFILES, LANGUAGES
from scripts.schemas.config import (
    CustomProviderProfileCreateRequest,
    CustomProviderProfileUpdateRequest,
    TestProviderConnectionRequest,
    UpdateApiKeyRequest,
    UpdateProviderConfigRequest,
)
from scripts.app_settings import config_manager
from scripts.utils.system_utils import sanitize_for_json
from scripts.core.services.custom_provider_profile_service import CustomProviderProfileService
from scripts.core.reasoning_policy import (
    describe_reasoning_settings,
    resolve_reasoning_parameters,
    validate_custom_parameters,
)

router = APIRouter()

LOCAL_OPENAI_COMPATIBLE_PROVIDERS = {"lm_studio", "vllm", "koboldcpp", "oobabooga", "text-generation-webui"}
OPENAI_ENDPOINT_SUFFIXES = ("/chat/completions", "/responses")
LOCAL_PROVIDER_IDS = LOCAL_OPENAI_COMPATIBLE_PROVIDERS | {"ollama"}


def _profile_service() -> CustomProviderProfileService:
    """Resolve dependencies per request so tests and runtime config stay isolated."""
    return CustomProviderProfileService(config_manager, API_PROVIDERS)


def _validate_local_openai_base_url(provider_id: str, api_url: str) -> None:
    if provider_id not in LOCAL_OPENAI_COMPATIBLE_PROVIDERS or not api_url:
        return

    normalized_path = api_url.strip().rstrip("/").lower()
    if any(normalized_path.endswith(suffix) for suffix in OPENAI_ENDPOINT_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=(
                "API URL must be a Base URL, not a concrete endpoint. "
                "For LM Studio, use http://localhost:1234/v1, not /responses "
                "or /chat/completions."
            ),
        )


def _local_provider_display_name(provider_id: str) -> str:
    return API_PROVIDERS.get(provider_id, {}).get("name", provider_id.replace("_", " ").title())

@router.get("/api/config")
def get_config():
    """Returns the global configuration for the frontend."""
    profiles = _profile_service().list_profiles()
    api_providers_list = []
    
    # Load overrides from AppData
    provider_overrides = config_manager.get_value("provider_config", {})
    
    logging.info(f"[CONFIG] API_PROVIDERS count: {len(API_PROVIDERS)}")

    for pid, pconf in API_PROVIDERS.items():
        if pid == "your_favourite_api":
            continue
        # Merge overrides
        override = provider_overrides.get(pid, {})
        
        # Base config
        provider_data = {
            "value": pid,
            "label": pconf.get("name", pid.title()),
            "available_models": pconf.get("available_models", []),
            "default_model": pconf.get("default_model"),
            "selected_model": override.get("selected_model", pconf.get("default_model")),
            "prompt_prefix": override.get("prompt_prefix", ""),
            "system_prompt_suffix": override.get("system_prompt_suffix", ""),
        }
        
        # Add custom models and URL if present
        if "models" in override:
            provider_data["custom_models"] = override["models"]
        if "api_url" in override:
            provider_data["api_url"] = override["api_url"]
        elif "base_url" in pconf:
             provider_data["api_url"] = pconf["base_url"]

        api_providers_list.append(provider_data)

    for profile in profiles:
        api_providers_list.append({
            "value": profile["profile_id"],
            "profile_id": profile["profile_id"],
            "adapter_id": profile["adapter_id"],
            "label": profile["display_name"],
            "available_models": profile["models"],
            "default_model": profile["selected_model"],
            "selected_model": profile["selected_model"],
            "custom_models": profile["models"],
            "api_url": profile["api_url"],
            "prompt_prefix": profile["prompt_prefix"],
            "system_prompt_suffix": profile["system_prompt_suffix"],
            "reasoning_builtin_enabled": profile["reasoning_builtin_enabled"],
            "reasoning_preset": profile["reasoning_preset"],
            "custom_parameters": profile["custom_parameters"],
            "has_key": profile["has_key"],
        })

    return sanitize_for_json({
        "game_profiles": GAME_PROFILES,
        "languages": LANGUAGES,
        "api_providers": api_providers_list,
        "profiles": profiles,
        "rpm_limit": config_manager.get_value("rpm_limit", 40)
    })

@router.get("/api/api-keys")
def get_api_keys():
    providers = []
    # Reload env to ensure we have the latest keys if they were changed externally
    load_dotenv(override=True)
    
    # Load overrides
    provider_overrides = config_manager.get_value("provider_config", {})
    
    for provider_id, config in API_PROVIDERS.items():
        if provider_id == "your_favourite_api":
            continue
        env_var = config.get("api_key_env")
        is_keyless = env_var is None
        
        api_key = get_api_key(provider_id, env_var) if env_var else None
        has_key = bool(api_key)
        
        masked_key = None
        if has_key and len(api_key) > 8:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        elif has_key:
            masked_key = "***"
            
        # Get overrides
        override = provider_overrides.get(provider_id, {})
            
        selected_model = override.get("selected_model", config.get("default_model"))
        effective_config = config.copy()
        effective_config["default_model"] = selected_model
        for key in (
            "reasoning_builtin_enabled",
            "reasoning_preset",
            "custom_parameters",
        ):
            if key in override:
                effective_config[key] = override[key]

        providers.append({
            "id": provider_id,
            "name": config.get("name", provider_id.replace("_", " ").title()),
            "description": config.get("description", ""),
            "description_key": config.get("description_key", ""),
            "is_keyless": is_keyless,
            "has_key": has_key,
            "masked_key": masked_key,
            "available_models": config.get("available_models", []),
            "selected_model": selected_model,
            "custom_models": override.get("models", []),
            "api_url": override.get("api_url", config.get("base_url", "")),
            "prompt_prefix": override.get("prompt_prefix", ""),
            "system_prompt_suffix": override.get("system_prompt_suffix", ""),
            "reasoning": describe_reasoning_settings(effective_config),
            "reasoning_models": (config.get("reasoning") or {}).get("models", {}),
        })
    return sanitize_for_json(providers)


def _profile_payload_dict(payload):
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_unset=True)
    return payload.dict(exclude_unset=True)


@router.get("/api/providers/profiles")
def get_custom_provider_profiles():
    return sanitize_for_json(_profile_service().list_profiles())


@router.post("/api/providers/profiles", status_code=201)
def create_custom_provider_profile(payload: CustomProviderProfileCreateRequest):
    try:
        profile = _profile_service().create_profile(_profile_payload_dict(payload))
        return sanitize_for_json(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logging.exception("Failed to create custom provider profile")
        raise HTTPException(status_code=500, detail="Failed to save provider profile") from exc


@router.patch("/api/providers/profiles/{profile_id}")
def update_custom_provider_profile(profile_id: str, payload: CustomProviderProfileUpdateRequest):
    try:
        profile = _profile_service().update_profile(profile_id, _profile_payload_dict(payload))
        return sanitize_for_json(profile)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logging.exception("Failed to update custom provider profile")
        raise HTTPException(status_code=500, detail="Failed to save provider profile") from exc


@router.delete("/api/providers/profiles/{profile_id}")
def delete_custom_provider_profile(profile_id: str):
    try:
        _profile_service().delete_profile(profile_id)
        # The selector must explicitly be cleared by the caller; no fallback
        # profile is selected implicitly after deletion.
        return {
            "status": "deleted",
            "profile_id": profile_id,
            "selected_profile_id": None,
            "selection_required": True,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider profile not found") from exc
    except Exception as exc:
        logging.exception("Failed to delete custom provider profile")
        raise HTTPException(status_code=500, detail="Failed to delete provider profile") from exc

@router.post("/api/api-keys")
def update_api_key(payload: UpdateApiKeyRequest):
    provider_id = payload.provider_id
    new_key = payload.api_key
    
    if provider_id not in API_PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid provider ID")
        
    config = API_PROVIDERS[provider_id]
    env_var = config.get("api_key_env")
    
    if not env_var:
        raise HTTPException(status_code=400, detail="This provider does not require an API key")
        
    # Save to AppData config.json
    try:
        # Use ConfigManager for consistency
        config_manager.update_nested_value("api_keys", provider_id, new_key)
            
    except Exception as e:
        logging.error(f"Failed to save to AppData config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save API key to config file: {str(e)}")
    
    # Update current environment variable immediately
    os.environ[env_var] = new_key
    
    return {"status": "success"}

@router.post("/api/providers/config")
def update_provider_config(payload: UpdateProviderConfigRequest):
    """Updates configuration for a specific provider (key, models, url)."""
    provider_id = payload.provider_id
    
    if provider_id not in API_PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid provider ID")
        
    config = API_PROVIDERS[provider_id]
    env_var = config.get("api_key_env")

    # Build and validate the complete provider update before any configuration
    # or process-environment side effect occurs.
    # We store these in a separate "provider_config" dict in config.json
    # Structure: "provider_config": { "openai": { "models": [...], "api_url": "..." } }
    
    current_overrides = copy.deepcopy(config_manager.get_value("provider_config", {}))
    if provider_id not in current_overrides:
        current_overrides[provider_id] = {}
        
    if payload.models is not None:
        current_overrides[provider_id]["models"] = payload.models
        
    if payload.api_url is not None:
        _validate_local_openai_base_url(provider_id, payload.api_url)
        current_overrides[provider_id]["api_url"] = payload.api_url

    if payload.selected_model is not None:
        current_overrides[provider_id]["selected_model"] = payload.selected_model

    if payload.prompt_prefix is not None:
        current_overrides[provider_id]["prompt_prefix"] = payload.prompt_prefix

    if payload.system_prompt_suffix is not None:
        current_overrides[provider_id]["system_prompt_suffix"] = payload.system_prompt_suffix

    if payload.reasoning_builtin_enabled is not None:
        current_overrides[provider_id]["reasoning_builtin_enabled"] = (
            payload.reasoning_builtin_enabled
        )

    if payload.reasoning_preset is not None:
        current_overrides[provider_id]["reasoning_preset"] = payload.reasoning_preset

    if payload.custom_parameters is not None:
        try:
            current_overrides[provider_id]["custom_parameters"] = (
                validate_custom_parameters(payload.custom_parameters)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    effective_config = API_PROVIDERS[provider_id].copy()
    effective_config["default_model"] = current_overrides[provider_id].get(
        "selected_model",
        effective_config.get("default_model"),
    )
    effective_config.update({
        key: current_overrides[provider_id][key]
        for key in (
            "reasoning_builtin_enabled",
            "reasoning_preset",
            "custom_parameters",
        )
        if key in current_overrides[provider_id]
    })
    resolution = resolve_reasoning_parameters(effective_config)
    if resolution.builtin_enabled and not resolution.supported:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected model has no verified built-in reasoning mapping. "
                "Disable built-in reasoning and use custom parameters instead."
            ),
        )
    if (
        resolution.builtin_enabled
        and resolution.selected_preset not in resolution.available_presets
    ):
        raise HTTPException(
            status_code=400,
            detail="The selected reasoning preset is not supported by this model.",
        )

    if payload.api_key is not None and env_var:
        config_manager.update_nested_value("api_keys", provider_id, payload.api_key)
        os.environ[env_var] = payload.api_key

    config_manager.set_value("provider_config", current_overrides)
    
    return {"status": "success"}


@router.post("/api/providers/test-connection")
def test_provider_connection(payload: TestProviderConnectionRequest):
    """Checks whether a configured local LLM service is reachable."""
    if payload.provider_id not in LOCAL_PROVIDER_IDS:
        raise HTTPException(status_code=400, detail="Connection testing is only available for local providers")

    api_url = payload.api_url.strip().rstrip("/")
    if not api_url:
        raise HTTPException(status_code=400, detail="API URL is required")
    _validate_local_openai_base_url(payload.provider_id, api_url)

    endpoint = (
        f"{api_url}/api/version"
        if payload.provider_id == "ollama"
        else f"{api_url}/models"
    )
    provider_name = _local_provider_display_name(payload.provider_id)
    try:
        response = requests.get(endpoint, timeout=5)
        if response.status_code >= 400:
            raise requests.HTTPError(f"HTTP {response.status_code}")
    except (requests.RequestException, OSError) as exc:
        logging.warning("Local provider connection test failed for %s at %s: %s", provider_name, api_url, exc)
        raise HTTPException(
            status_code=502,
            detail=(
                f"无法连接 {provider_name}：Remis 正在访问 {api_url}。"
                "请检查本地服务是否已启动，并确认端口设置正确。"
            ),
        ) from exc

    return {"status": "success", "provider": provider_name, "api_url": api_url}

@router.post("/api/config/rpm")
def update_rpm_limit(payload: dict):
    """Updates the global RPM limit."""
    rpm = payload.get("rpm")
    if rpm is None:
        raise HTTPException(status_code=400, detail="RPM value is required")
    
    try:
        rpm_val = int(rpm)
        config_manager.set_value("rpm_limit", rpm_val)
        
        # Update current rate limiter immediately
        from scripts.utils.rate_limiter import rate_limiter
        rate_limiter.update_rpm(rpm_val)
        
        return {"status": "success", "rpm": rpm_val}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid RPM value")
    except Exception as e:
        logging.error(f"Failed to update RPM limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))
