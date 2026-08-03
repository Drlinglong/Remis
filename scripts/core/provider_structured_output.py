"""Authoritative provider capability labels for structured context output."""

from __future__ import annotations


STRICT_JSON_SCHEMA_PROVIDERS = frozenset({"openrouter"})


def structured_output_mode(provider_id: str | None) -> str:
    """Describe enforcement truthfully; prompt JSON is not native schema enforcement."""

    normalized = (provider_id or "").strip().casefold()
    if normalized in STRICT_JSON_SCHEMA_PROVIDERS:
        return "strict_json_schema"
    return "prompt_json_with_local_validation"
