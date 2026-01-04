import os
import json
import logging
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from scripts.app_settings import API_PROVIDERS, get_api_key, get_appdata_config_path, GAME_PROFILES, LANGUAGES
from scripts.schemas.config import UpdateApiKeyRequest, UpdateProviderConfigRequest
from scripts.core.config_manager import config_manager

router = APIRouter()

@router.get("/api/config")
def get_config():
    """Returns the global configuration for the frontend."""
    # Convert API_PROVIDERS dict to list for frontend select
    # Convert API_PROVIDERS dict to list for frontend select
    api_providers_list = []
    
    # Load overrides from AppData
    provider_overrides = config_manager.get_value("provider_config", {})
    
    logging.info(f"[CONFIG] API_PROVIDERS count: {len(API_PROVIDERS)}")

    for pid, pconf in API_PROVIDERS.items():
        # Merge overrides
        override = provider_overrides.get(pid, {})
        
        # Base config
        provider_data = {
            "value": pid,
            "label": pconf.get("name", pid.title()),
            "available_models": pconf.get("available_models", []),
            "default_model": pconf.get("default_model"),
            "selected_model": override.get("selected_model", pconf.get("default_model")),
        }
        
        # Add custom models and URL if present
        if "models" in override:
            provider_data["custom_models"] = override["models"]
        if "api_url" in override:
            provider_data["api_url"] = override["api_url"]
        elif "base_url" in pconf:
             provider_data["api_url"] = pconf["base_url"]

        api_providers_list.append(provider_data)

    return {
        "game_profiles": GAME_PROFILES,
        "languages": LANGUAGES,
        "api_providers": api_providers_list,
        "rpm_limit": config_manager.get_value("rpm_limit", 40)
    }

@router.get("/api/api-keys")
def get_api_keys():
    providers = []
    # Reload env to ensure we have the latest keys if they were changed externally
    load_dotenv(override=True)
    
    # Load overrides
    provider_overrides = config_manager.get_value("provider_config", {})
    
    for provider_id, config in API_PROVIDERS.items():
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
            
        providers.append({
            "id": provider_id,
            "name": config.get("name", provider_id.replace("_", " ").title()),
            "description": config.get("description", ""),
            "description_key": config.get("description_key", ""),
            "is_keyless": is_keyless,
            "has_key": has_key,
            "masked_key": masked_key,
            "available_models": config.get("available_models", []),
            "selected_model": override.get("selected_model", config.get("default_model")),
            "custom_models": override.get("models", []),
            "api_url": override.get("api_url", config.get("base_url", ""))
        })
    return providers

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
        
    # 1. Handle API Key
    if payload.api_key is not None:
        # Reuse the logic from update_api_key or call it
        # But here we just do it manually to avoid overhead
        config = API_PROVIDERS[provider_id]
        env_var = config.get("api_key_env")
        if env_var:
             config_manager.update_nested_value("api_keys", provider_id, payload.api_key)
             os.environ[env_var] = payload.api_key
    
    # 2. Handle Custom Models & URL
    # We store these in a separate "provider_config" dict in config.json
    # Structure: "provider_config": { "openai": { "models": [...], "api_url": "..." } }
    
    current_overrides = config_manager.get_value("provider_config", {})
    if provider_id not in current_overrides:
        current_overrides[provider_id] = {}
        
    if payload.models is not None:
        current_overrides[provider_id]["models"] = payload.models
        
    if payload.api_url is not None:
        current_overrides[provider_id]["api_url"] = payload.api_url

    if payload.selected_model is not None:
        current_overrides[provider_id]["selected_model"] = payload.selected_model
        
    config_manager.set_value("provider_config", current_overrides)
    
    return {"status": "success"}

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
