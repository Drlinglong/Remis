from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


SENSITIVE_CONFIG_TOKENS = ("key", "secret", "authorization", "credential", "token")


def _safe_config_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _safe_config_value(item)
            for key, item in value.items()
            if not any(token in str(key).casefold() for token in SENSITIVE_CONFIG_TOKENS)
        }
    if isinstance(value, list):
        return [_safe_config_value(item) for item in value]
    return copy.deepcopy(value)


@dataclass(frozen=True)
class ProviderRuntimeSnapshot:
    """In-memory provider settings resolved once when a task is accepted."""

    selection_id: str
    adapter_id: str
    display_name: str
    model_id: str | None
    config: dict[str, Any] = field(repr=False)
    api_key: str | None = field(default=None, repr=False)
    secret_ref: str | None = field(default=None, repr=False)

    def handler_kwargs(self) -> dict[str, Any]:
        return {
            "provider_config_snapshot": copy.deepcopy(self.config),
            "api_key_override": self.api_key,
        }

    def safe_metadata(self) -> dict[str, Any]:
        safe_config = _safe_config_value(self.config)
        fingerprint_payload = {
            "selection_id": self.selection_id,
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "config": safe_config,
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return {
            "selection_id": self.selection_id,
            "profile_id": self.selection_id,
            "adapter_id": self.adapter_id,
            "display_name": self.display_name,
            "model_id": self.model_id,
            "config": safe_config,
            "config_fingerprint": fingerprint,
            "secret_ref": self.secret_ref,
        }


def handler_from_runtime(
    runtime: ProviderRuntimeSnapshot,
    handler_factory=None,
):
    if handler_factory is None:
        from scripts.core.api_handler import get_handler

        handler_factory = get_handler
    return handler_factory(
        runtime.adapter_id,
        model_name=runtime.model_id,
        **runtime.handler_kwargs(),
    )


def handler_for_selection(
    selection_id: str,
    model_id: str | None,
    runtime: ProviderRuntimeSnapshot | None,
):
    if runtime is not None:
        return handler_from_runtime(runtime)
    from scripts.core.api_handler import get_handler

    return get_handler(selection_id, model_name=model_id)


def provider_task_fields(runtime: ProviderRuntimeSnapshot | None) -> dict[str, Any]:
    return {"provider_snapshot": runtime.safe_metadata()} if runtime else {}


def resolve_provider_runtime(
    selection_id: str,
    model_id: str | None = None,
) -> ProviderRuntimeSnapshot | None:
    """Resolve custom profile selections; built-in providers keep legacy routing."""

    from scripts.app_settings import API_PROVIDERS, config_manager
    from scripts.core.services.custom_provider_profile_service import (
        CUSTOM_ADAPTER_ID,
        CustomProviderProfileService,
    )

    if selection_id in API_PROVIDERS and selection_id != CUSTOM_ADAPTER_ID:
        return None
    service = CustomProviderProfileService(config_manager, API_PROVIDERS)
    return service.resolve_runtime(selection_id, model_id=model_id)


def provider_selection_exists(selection_id: str) -> bool:
    """Return whether a built-in provider or saved custom profile can be selected."""

    from scripts.app_settings import API_PROVIDERS, config_manager
    from scripts.core.services.custom_provider_profile_service import (
        CUSTOM_ADAPTER_ID,
        CustomProviderProfileService,
    )

    if selection_id in API_PROVIDERS and selection_id != CUSTOM_ADAPTER_ID:
        return True
    try:
        CustomProviderProfileService(config_manager, API_PROVIDERS).resolve_profile_selection(selection_id)
    except KeyError:
        return False
    return True
