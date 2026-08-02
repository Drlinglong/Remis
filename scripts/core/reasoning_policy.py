"""Resolve safe provider/model-specific reasoning request parameters."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any


PROTECTED_CUSTOM_PARAMETER_KEYS = {
    "api_key",
    "authorization",
    "input",
    "messages",
    "model",
    "prompt",
    "stream",
    "system",
}
MAX_CUSTOM_PARAMETERS_BYTES = 16_384


@dataclass(frozen=True)
class ReasoningResolution:
    supported: bool
    builtin_enabled: bool
    selected_preset: str
    available_presets: tuple[str, ...]
    builtin_parameters: dict[str, Any]
    custom_parameters: dict[str, Any]
    parameters: dict[str, Any]
    overridden_paths: tuple[str, ...]
    source_url: str | None
    reviewed_at: str | None


def validate_custom_parameters(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Custom API parameters must be a JSON object.")
    protected = sorted(PROTECTED_CUSTOM_PARAMETER_KEYS.intersection(value))
    if protected:
        raise ValueError(
            "Custom API parameters cannot override protected fields: "
            + ", ".join(protected)
        )
    encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_CUSTOM_PARAMETERS_BYTES:
        raise ValueError("Custom API parameters exceed the 16 KiB safety limit.")
    return copy.deepcopy(value)


def _deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    prefix: str = "",
) -> tuple[dict[str, Any], list[str]]:
    merged = copy.deepcopy(base)
    conflicts: list[str] = []
    for key, value in override.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key], nested = _deep_merge(merged[key], value, path)
            conflicts.extend(nested)
        else:
            if key in merged and merged[key] != value:
                conflicts.append(path)
            merged[key] = copy.deepcopy(value)
    return merged, conflicts


def resolve_reasoning_parameters(provider_config: dict[str, Any]) -> ReasoningResolution:
    model = str(provider_config.get("default_model") or "")
    reasoning = provider_config.get("reasoning") or {}
    model_capability = (reasoning.get("models") or {}).get(model)
    supported = isinstance(model_capability, dict)
    presets = (model_capability or {}).get("presets") or {}
    available_presets = tuple(presets)
    default_preset = str(reasoning.get("default_preset") or "medium")
    selected_preset = str(
        provider_config.get("reasoning_preset") or default_preset
    )
    builtin_enabled = bool(
        provider_config.get(
            "reasoning_builtin_enabled",
            reasoning.get("default_enabled", False),
        )
    )

    builtin_parameters: dict[str, Any] = {}
    if builtin_enabled and supported:
        preset_parameters = presets.get(selected_preset)
        if isinstance(preset_parameters, dict):
            builtin_parameters = copy.deepcopy(preset_parameters)

    custom_parameters = validate_custom_parameters(
        provider_config.get("custom_parameters")
    )
    parameters, conflicts = _deep_merge(
        builtin_parameters,
        custom_parameters,
    )
    return ReasoningResolution(
        supported=supported,
        builtin_enabled=builtin_enabled,
        selected_preset=selected_preset,
        available_presets=available_presets,
        builtin_parameters=builtin_parameters,
        custom_parameters=custom_parameters,
        parameters=parameters,
        overridden_paths=tuple(conflicts),
        source_url=(model_capability or {}).get("source_url"),
        reviewed_at=(model_capability or {}).get("reviewed_at"),
    )


def describe_reasoning_settings(provider_config: dict[str, Any]) -> dict[str, Any]:
    resolution = resolve_reasoning_parameters(provider_config)
    return {
        "supported": resolution.supported,
        "builtin_enabled": resolution.builtin_enabled,
        "selected_preset": resolution.selected_preset,
        "available_presets": list(resolution.available_presets),
        "mapping_preview": resolution.builtin_parameters,
        "custom_parameters": resolution.custom_parameters,
        "overridden_paths": list(resolution.overridden_paths),
        "source_url": resolution.source_url,
        "reviewed_at": resolution.reviewed_at,
    }
