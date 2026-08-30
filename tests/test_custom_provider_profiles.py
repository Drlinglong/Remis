import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scripts.core.config_manager import ConfigManager
from scripts.core.services.custom_provider_profile_service import (
    CUSTOM_ADAPTER_ID,
    CUSTOM_PROFILES_CONFIG_KEY,
    LEGACY_PROFILE_ID,
    PROFILE_SECRET_PREFIX,
    SECRET_REF_PREFIX,
    CustomProviderProfileService,
)
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot
from scripts.web_server import app


ADAPTER_CATALOG = {
    CUSTOM_ADAPTER_ID: {
        "name": "Custom (OpenAI Compatible)",
        "base_url": "YOUR_BASE_URL_HERE",
        "default_model": "YOUR_MODEL_NAME_HERE",
    }
}


@pytest.fixture
def profile_service(tmp_path):
    manager = ConfigManager(str(tmp_path / "static"), str(tmp_path / "user"))
    return CustomProviderProfileService(manager, ADAPTER_CATALOG), manager


def profile_payload(**overrides):
    payload = {
        "display_name": "Provider A",
        "api_url": "https://provider.example/v1/",
        "models": ["translation-model"],
        "selected_model": "translation-model",
        "prompt_prefix": "/no_think",
        "system_prompt_suffix": "",
        "reasoning_builtin_enabled": False,
        "reasoning_preset": "medium",
        "custom_parameters": {"temperature": 0.2},
        "api_key": "secret-provider-a",
    }
    payload.update(overrides)
    return payload


def test_crud_uses_stable_id_and_never_returns_api_key(profile_service):
    service, manager = profile_service

    created = service.create_profile(profile_payload())
    profile_id = created["profile_id"]
    assert profile_id
    assert created["adapter_id"] == CUSTOM_ADAPTER_ID
    assert created["has_key"] is True
    assert "api_key" not in created
    assert "secret_ref" not in created

    resolved = service.resolve_profile_selection(profile_id)
    assert resolved["profile_id"] == profile_id
    assert resolved["adapter_id"] == CUSTOM_ADAPTER_ID
    assert resolved["base_url"] == "https://provider.example/v1"
    assert resolved["default_model"] == "translation-model"
    assert resolved["secret_ref"].startswith(SECRET_REF_PREFIX)
    assert "api_key" not in resolved
    secret_ref = resolved["secret_ref"]
    assert service.resolve_profile_secret(secret_ref) == "secret-provider-a"

    updated = service.update_profile(profile_id, {"display_name": "Provider A renamed"})
    assert updated["profile_id"] == profile_id
    assert updated["display_name"] == "Provider A renamed"
    assert service.resolve_profile_secret(secret_ref) == "secret-provider-a"

    service.delete_profile(profile_id)
    assert service.list_profiles() == []
    assert service.resolve_profile_secret(secret_ref) is None
    stored = json.loads(open(manager.user_config_path, encoding="utf-8").read())
    assert stored[CUSTOM_PROFILES_CONFIG_KEY] == []
    assert all("secret-provider-a" != value for value in stored.get("api_keys", {}).values())


def test_delete_selected_copilot_profile_requires_explicit_switch(profile_service):
    service, manager = profile_service
    created = service.create_profile(profile_payload())
    manager.set_value("copilot_settings", {
        "provider": created["profile_id"],
        "model": created["selected_model"],
    })

    with pytest.raises(ValueError, match="Switch the Copilot provider"):
        service.delete_profile(created["profile_id"])

    assert service.list_profiles()[0]["profile_id"] == created["profile_id"]


def test_legacy_provider_config_and_key_migrate_once(profile_service):
    service, manager = profile_service
    manager.set_value(
        "provider_config",
        {
            CUSTOM_ADAPTER_ID: {
                "api_url": "https://legacy.example/v1",
                "models": ["legacy-model"],
                "selected_model": "legacy-model",
                "prompt_prefix": "/legacy",
            }
        },
    )
    manager.update_nested_value("api_keys", CUSTOM_ADAPTER_ID, "legacy-secret")

    first = service.list_profiles()
    second = service.list_profiles()
    assert len(first) == len(second) == 1
    assert first[0]["profile_id"] == LEGACY_PROFILE_ID
    assert first[0]["api_url"] == "https://legacy.example/v1"
    assert first[0]["selected_model"] == "legacy-model"
    assert first[0]["has_key"] is True
    legacy = service.resolve_profile_selection(LEGACY_PROFILE_ID)
    assert service.resolve_profile_secret(legacy["secret_ref"]) == "legacy-secret"

    persisted_profiles = manager.get_value(CUSTOM_PROFILES_CONFIG_KEY)
    assert len(persisted_profiles) == 1
    assert persisted_profiles[0]["profile_id"] == LEGACY_PROFILE_ID
    assert manager.get_value("api_keys")[CUSTOM_ADAPTER_ID] == "legacy-secret"
    migrated_key = f"{PROFILE_SECRET_PREFIX}{LEGACY_PROFILE_ID}"
    assert migrated_key not in manager.get_value("api_keys")


@pytest.mark.parametrize(
    "api_url",
    [
        "https://provider.example/v1/chat/completions",
        "https://provider.example/v1/responses",
        "ftp://provider.example/v1",
        "https://user:password@provider.example/v1",
        "https://provider.example/v1?token=secret",
    ],
)
def test_create_rejects_non_base_or_unsafe_openai_url(profile_service, api_url):
    service, _ = profile_service
    with pytest.raises(ValueError, match="Base URL"):
        service.create_profile(profile_payload(api_url=api_url))


def test_explicit_empty_api_key_clears_secret(profile_service):
    service, _ = profile_service
    created = service.create_profile(profile_payload())
    secret_ref = service.resolve_profile_selection(created["profile_id"])["secret_ref"]
    service.update_profile(created["profile_id"], {"api_key": ""})
    assert service.resolve_profile_secret(secret_ref) is None


def test_runtime_resolves_legacy_selection_and_captures_key(profile_service):
    service, manager = profile_service
    manager.set_value(
        "provider_config",
        {CUSTOM_ADAPTER_ID: {"api_url": "https://legacy.example/v1", "selected_model": "legacy-model"}},
    )
    manager.update_nested_value("api_keys", CUSTOM_ADAPTER_ID, "runtime-secret")

    runtime = service.resolve_runtime(CUSTOM_ADAPTER_ID, model_id="override-model")
    assert isinstance(runtime, ProviderRuntimeSnapshot)
    assert runtime.selection_id == LEGACY_PROFILE_ID
    assert runtime.adapter_id == CUSTOM_ADAPTER_ID
    assert runtime.model_id == "override-model"
    assert runtime.api_key == "runtime-secret"
    assert runtime.config["base_url"] == "https://legacy.example/v1"
    assert runtime.config["default_model"] == "override-model"
    assert "api_key" not in runtime.config
    assert service.resolve_profile_selection(CUSTOM_ADAPTER_ID)["profile_id"] == LEGACY_PROFILE_ID


def test_runtime_is_a_start_time_snapshot_across_profile_edits(profile_service):
    service, _ = profile_service
    created = service.create_profile(
        profile_payload(
            api_url="https://provider-a.example/v1",
            selected_model="model-a",
            api_key="key-a",
        )
    )

    old_runtime = service.resolve_runtime(created["profile_id"])
    service.update_profile(
        created["profile_id"],
        {
            "api_url": "https://provider-b.example/v1",
            "selected_model": "model-b",
            "api_key": "key-b",
        },
    )
    new_runtime = service.resolve_runtime(created["profile_id"])

    assert old_runtime.config["base_url"] == "https://provider-a.example/v1"
    assert old_runtime.config["default_model"] == "model-a"
    assert old_runtime.api_key == "key-a"
    assert new_runtime.config["base_url"] == "https://provider-b.example/v1"
    assert new_runtime.config["default_model"] == "model-b"
    assert new_runtime.api_key == "key-b"


def test_profile_routes_and_config_selector_are_safe(tmp_path):
    manager = ConfigManager(str(tmp_path / "static"), str(tmp_path / "user"))
    catalog = {
        "gemini": {
            "name": "Gemini",
            "default_model": "gemini-model",
            "available_models": ["gemini-model"],
        },
        CUSTOM_ADAPTER_ID: ADAPTER_CATALOG[CUSTOM_ADAPTER_ID],
    }
    with patch("scripts.routers.config.config_manager", manager), patch(
        "scripts.routers.config.API_PROVIDERS", catalog
    ):
        client = TestClient(app)
        response = client.post(
            "/api/providers/profiles",
            json=profile_payload(api_key="route-secret"),
        )
        assert response.status_code == 201
        body = response.json()
        profile_id = body["profile_id"]
        assert "api_key" not in body

        config = client.get("/api/config").json()
        assert all(option["value"] != CUSTOM_ADAPTER_ID for option in config["api_providers"])
        selector = next(option for option in config["api_providers"] if option["value"] == profile_id)
        assert selector["value"] == profile_id
        assert selector["adapter_id"] == CUSTOM_ADAPTER_ID
        assert selector["label"] == "Provider A"
        assert "route-secret" not in json.dumps(config)

        profiles = client.get("/api/providers/profiles").json()
        assert profiles[0]["profile_id"] == profile_id
        assert "api_key" not in profiles[0]

        deleted = client.delete(f"/api/providers/profiles/{profile_id}")
        assert deleted.status_code == 200
        assert deleted.json()["selected_profile_id"] is None
        assert deleted.json()["selection_required"] is True


def test_profile_write_schema_rejects_unscoped_fields(tmp_path):
    manager = ConfigManager(str(tmp_path / "static"), str(tmp_path / "user"))
    with patch("scripts.routers.config.config_manager", manager), patch(
        "scripts.routers.config.API_PROVIDERS", ADAPTER_CATALOG
    ):
        response = TestClient(app).post(
            "/api/providers/profiles",
            json=profile_payload(unbounded_routing_rules={"failover": True}),
        )
    assert response.status_code == 422
