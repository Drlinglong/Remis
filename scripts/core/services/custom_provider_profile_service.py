"""Persistence and resolution for saved OpenAI-compatible provider profiles.

The service deliberately owns only profile metadata and the boundary to the
existing ``api_keys`` configuration area.  It does not create a new adapter or
implement a second inference path.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import uuid
from typing import Any, Mapping
from urllib.parse import urlsplit

from scripts.core.reasoning_policy import resolve_reasoning_parameters, validate_custom_parameters
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


logger = logging.getLogger(__name__)

CUSTOM_ADAPTER_ID = "your_favourite_api"
CUSTOM_PROFILES_CONFIG_KEY = "custom_provider_profiles"
LEGACY_PROFILE_ID = "custom-legacy"
PROFILE_SECRET_PREFIX = "custom_provider_profile:"
SECRET_REF_PREFIX = "api_keys."

PROFILE_FIELDS = (
    "display_name",
    "api_url",
    "models",
    "selected_model",
    "prompt_prefix",
    "system_prompt_suffix",
    "reasoning_builtin_enabled",
    "reasoning_preset",
    "custom_parameters",
)


class CustomProviderProfileService:
    """CRUD, migration, and safe resolution for custom provider profiles."""

    def __init__(self, config_manager: Any, adapter_catalog: Mapping[str, Mapping[str, Any]]):
        self.config_manager = config_manager
        self.adapter_catalog = adapter_catalog

    def list_profiles(self) -> list[dict[str, Any]]:
        self._ensure_legacy_migrated()
        return [self._safe_profile(profile) for profile in self._load_profiles()]

    def create_profile(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._ensure_legacy_migrated()
        values = self._normalize_payload(payload, partial=False)
        profile_id = str(uuid.uuid4())
        profile = self._build_profile(profile_id, values)
        profiles = self._load_profiles()
        profiles.append(profile)
        api_keys = self._load_api_keys()
        self._persist_state(profiles, api_keys, profile_secret=profile["secret_ref"], payload=payload)
        return self._safe_profile(profile)

    def update_profile(self, profile_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._ensure_legacy_migrated()
        profiles = self._load_profiles()
        index, current = self._find_profile(profiles, profile_id)
        values = dict(current)
        values.update(self._normalize_payload(payload, partial=True, current=current))
        profile = self._build_profile(profile_id, values)
        profiles[index] = profile
        api_keys = self._load_api_keys()
        self._persist_state(profiles, api_keys, profile_secret=profile["secret_ref"], payload=payload)
        return self._safe_profile(profile)

    def delete_profile(self, profile_id: str) -> None:
        self._ensure_legacy_migrated()
        copilot_settings = self.config_manager.get_value("copilot_settings", {}) or {}
        selected = copilot_settings.get("provider") if isinstance(copilot_settings, dict) else None
        if selected == profile_id or (profile_id == LEGACY_PROFILE_ID and selected == CUSTOM_ADAPTER_ID):
            raise ValueError("Switch the Copilot provider before deleting this profile")
        profiles = self._load_profiles()
        index, profile = self._find_profile(profiles, profile_id)
        profiles.pop(index)
        api_keys = self._load_api_keys()
        api_keys.pop(self._secret_key(profile["secret_ref"]), None)
        self._persist_state(profiles, api_keys)

    def resolve_profile_selection(self, selection_id: str) -> dict[str, Any]:
        """Resolve a selector value to safe profile/adapter settings.

        The returned mapping includes no API key.  ``base_url`` and
        ``default_model`` are adapter-facing aliases derived from the existing
        Custom adapter contract; they are not separately persisted fields.
        """

        self._ensure_legacy_migrated()
        if selection_id == CUSTOM_ADAPTER_ID:
            selection_id = LEGACY_PROFILE_ID
        profiles = self._load_profiles()
        _, profile = self._find_profile(profiles, selection_id)
        resolved = self._safe_profile(profile, include_secret_ref=True)
        resolved["base_url"] = resolved["api_url"]
        resolved["default_model"] = resolved["selected_model"]
        return resolved

    def resolve_runtime(
        self,
        selection_id: str,
        model_id: str | None = None,
    ) -> ProviderRuntimeSnapshot:
        """Resolve a custom selection and capture its key/config atomically in memory."""

        resolved = self.resolve_profile_selection(selection_id)
        effective_model = (model_id or resolved["selected_model"] or "").strip()
        config = {
            key: copy.deepcopy(resolved[key])
            for key in PROFILE_FIELDS
            if key in resolved
        }
        config["base_url"] = resolved["base_url"]
        config["default_model"] = effective_model
        config["selected_model"] = effective_model
        return ProviderRuntimeSnapshot(
            selection_id=resolved["profile_id"],
            adapter_id=resolved["adapter_id"],
            display_name=resolved["display_name"],
            model_id=effective_model or None,
            config=config,
            api_key=self.resolve_profile_secret(resolved["secret_ref"]),
            secret_ref=resolved["secret_ref"],
        )

    def resolve_profile_secret(self, secret_ref: str) -> str | None:
        """Resolve a profile secret reference through the existing key store."""

        key_name = self._secret_key(secret_ref)
        if not key_name:
            raise ValueError("Invalid provider profile secret reference")
        value = self._load_api_keys().get(key_name)
        return value if isinstance(value, str) and value else None

    def _ensure_legacy_migrated(self) -> None:
        profiles = self._load_profiles()
        provider_config = self.config_manager.get_value("provider_config", {})
        provider_config = provider_config if isinstance(provider_config, dict) else {}
        legacy_override = provider_config.get(CUSTOM_ADAPTER_ID)
        legacy_override = legacy_override if isinstance(legacy_override, dict) else {}
        api_keys = self._load_api_keys()
        legacy_key = api_keys.get(CUSTOM_ADAPTER_ID)
        if not legacy_override and not legacy_key:
            return

        profile = next((item for item in profiles if item.get("profile_id") == LEGACY_PROFILE_ID), None)
        changed_profiles = False
        if profile is None:
            profile = self._legacy_profile(legacy_override)
            profiles.append(profile)
            changed_profiles = True

        if changed_profiles:
            self._persist_state(profiles, api_keys)

    def _legacy_profile(self, override: Mapping[str, Any]) -> dict[str, Any]:
        adapter = self.adapter_catalog.get(CUSTOM_ADAPTER_ID, {}) or {}
        api_url = override.get("api_url") or override.get("base_url") or adapter.get("base_url", "")
        selected_model = (
            override.get("selected_model")
            or override.get("default_model")
            or adapter.get("default_model", "")
        )
        values = {
            "display_name": adapter.get("name", "Custom (OpenAI Compatible)"),
            "api_url": api_url,
            "models": override.get("models", []),
            "selected_model": selected_model,
            "prompt_prefix": override.get("prompt_prefix", ""),
            "system_prompt_suffix": override.get("system_prompt_suffix", ""),
            "reasoning_builtin_enabled": override.get("reasoning_builtin_enabled", False),
            "reasoning_preset": override.get("reasoning_preset"),
            "custom_parameters": override.get("custom_parameters", {}),
        }
        return self._build_profile(LEGACY_PROFILE_ID, values, validate_url=False)

    def _normalize_payload(
        self,
        payload: Mapping[str, Any],
        *,
        partial: bool,
        current: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = dict(payload)
        if partial:
            allowed = set(PROFILE_FIELDS) | {"api_key"}
            values = {key: value for key, value in values.items() if key in allowed}
        if not partial:
            for required in ("display_name", "api_url", "selected_model"):
                if not str(values.get(required) or "").strip():
                    raise ValueError(f"{required} is required")

        if "display_name" in values:
            values["display_name"] = self._required_text(values["display_name"], "display_name")
        if "api_url" in values:
            values["api_url"] = self._validate_openai_base_url(values["api_url"])
        if "selected_model" in values:
            values["selected_model"] = self._required_text(values["selected_model"], "selected_model")
        if "models" in values:
            values["models"] = self._normalize_models(values["models"])
        for field in ("prompt_prefix", "system_prompt_suffix"):
            if field in values and values[field] is None:
                values[field] = ""
        if "custom_parameters" in values:
            try:
                values["custom_parameters"] = validate_custom_parameters(values["custom_parameters"])
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        if "api_key" in values and values["api_key"] is not None and not isinstance(values["api_key"], str):
            raise ValueError("api_key must be a string")

        effective = dict(current or {})
        effective.update({key: value for key, value in values.items() if key != "api_key"})
        self._validate_reasoning(effective)
        return values

    def _validate_reasoning(self, profile: Mapping[str, Any]) -> None:
        adapter = dict(self.adapter_catalog.get(CUSTOM_ADAPTER_ID, {}) or {})
        adapter["default_model"] = profile.get("selected_model") or adapter.get("default_model")
        adapter.update({key: profile[key] for key in (
            "reasoning_builtin_enabled",
            "reasoning_preset",
            "custom_parameters",
        ) if key in profile})
        resolution = resolve_reasoning_parameters(adapter)
        if resolution.builtin_enabled and not resolution.supported:
            raise ValueError(
                "The selected model has no verified built-in reasoning mapping. "
                "Disable built-in reasoning and use custom parameters instead."
            )
        if resolution.builtin_enabled and resolution.selected_preset not in resolution.available_presets:
            raise ValueError("The selected reasoning preset is not supported by this model.")

    def _build_profile(
        self,
        profile_id: str,
        values: Mapping[str, Any],
        *,
        validate_url: bool = True,
    ) -> dict[str, Any]:
        profile = {
            "profile_id": profile_id,
            "adapter_id": CUSTOM_ADAPTER_ID,
            "secret_ref": (
                f"{SECRET_REF_PREFIX}{CUSTOM_ADAPTER_ID}"
                if profile_id == LEGACY_PROFILE_ID
                else f"{SECRET_REF_PREFIX}{PROFILE_SECRET_PREFIX}{profile_id}"
            ),
            "display_name": str(values.get("display_name") or "Custom Provider").strip(),
            "api_url": str(values.get("api_url") or "").strip().rstrip("/"),
            "models": copy.deepcopy(values.get("models") or []),
            "selected_model": str(values.get("selected_model") or "").strip(),
            "prompt_prefix": str(values.get("prompt_prefix") or ""),
            "system_prompt_suffix": str(values.get("system_prompt_suffix") or ""),
            "reasoning_builtin_enabled": bool(values.get("reasoning_builtin_enabled", False)),
            "reasoning_preset": values.get("reasoning_preset"),
            "custom_parameters": copy.deepcopy(values.get("custom_parameters") or {}),
        }
        if validate_url:
            profile["api_url"] = self._validate_openai_base_url(profile["api_url"])
        return profile

    def _safe_profile(
        self,
        profile: Mapping[str, Any],
        *,
        include_secret_ref: bool = False,
    ) -> dict[str, Any]:
        safe = {key: copy.deepcopy(profile.get(key)) for key in (
            "profile_id",
            "adapter_id",
            *PROFILE_FIELDS,
        )}
        if include_secret_ref:
            safe["secret_ref"] = profile.get("secret_ref")
        secret_ref = profile.get("secret_ref")
        safe["has_key"] = bool(
            secret_ref and self.resolve_profile_secret(secret_ref)
        )
        return safe

    def _persist_state(
        self,
        profiles: list[dict[str, Any]],
        api_keys: dict[str, Any],
        *,
        profile_secret: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if profile_secret and payload and "api_key" in payload:
            api_key = payload.get("api_key")
            secret_key = self._secret_key(profile_secret)
            if api_key:
                api_keys[secret_key] = api_key
            else:
                api_keys.pop(secret_key, None)
        self._atomic_update({CUSTOM_PROFILES_CONFIG_KEY: profiles, "api_keys": api_keys})

    def _atomic_update(self, updates: Mapping[str, Any]) -> None:
        path = getattr(self.config_manager, "user_config_path", None)
        if not isinstance(path, str) or not path:
            for key, value in updates.items():
                self.config_manager.set_value(key, value)
            return
        config = self.config_manager._load_user_config()
        if not isinstance(config, dict):
            config = {}
        config.update(copy.deepcopy(dict(updates)))
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=4, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise

    def _load_profiles(self) -> list[dict[str, Any]]:
        raw = self.config_manager.get_value(CUSTOM_PROFILES_CONFIG_KEY, [])
        if isinstance(raw, dict):
            raw = list(raw.values())
        if not isinstance(raw, list):
            return []
        return [copy.deepcopy(item) for item in raw if isinstance(item, dict) and item.get("profile_id")]

    def _load_api_keys(self) -> dict[str, Any]:
        raw = self.config_manager.get_value("api_keys", {})
        return copy.deepcopy(raw) if isinstance(raw, dict) else {}

    @staticmethod
    def _find_profile(profiles: list[dict[str, Any]], profile_id: str) -> tuple[int, dict[str, Any]]:
        for index, profile in enumerate(profiles):
            if profile.get("profile_id") == profile_id:
                return index, profile
        raise KeyError(f"Provider profile not found: {profile_id}")

    @staticmethod
    def _required_text(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
        return value.strip()

    @staticmethod
    def _normalize_models(value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("models must be a list")
        result = []
        for model in value:
            if not isinstance(model, str) or not model.strip():
                raise ValueError("models must contain non-empty strings")
            model = model.strip()
            if model not in result:
                result.append(model)
        return result

    @staticmethod
    def _validate_openai_base_url(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("api_url must be a valid OpenAI-compatible Base URL")
        normalized = value.strip().rstrip("/")
        try:
            parsed = urlsplit(normalized)
            hostname = parsed.hostname
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("api_url must be a valid OpenAI-compatible Base URL") from exc
        if (
            any(char.isspace() for char in normalized)
            or parsed.scheme.lower() not in {"http", "https"}
            or not hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("api_url must be a valid OpenAI-compatible Base URL")
        path = parsed.path.lower().rstrip("/")
        if path.endswith(("/chat/completions", "/responses")):
            raise ValueError("api_url must be a Base URL, not a concrete OpenAI endpoint")
        return normalized

    @staticmethod
    def _secret_key(secret_ref: str) -> str:
        if not isinstance(secret_ref, str) or not secret_ref.startswith(SECRET_REF_PREFIX):
            raise ValueError("Invalid provider profile secret reference")
        key_name = secret_ref[len(SECRET_REF_PREFIX):]
        if not key_name or "." in key_name or "/" in key_name or "\\" in key_name:
            raise ValueError("Invalid provider profile secret reference")
        return key_name
