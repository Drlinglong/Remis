"""Authoritative provider capability labels for structured output."""

from __future__ import annotations


# Context analysis (generate_structured_with_messages) enforcement.
STRICT_JSON_SCHEMA_PROVIDERS = frozenset({"openrouter"})

# Batch translation envelope (translation_output_contract) requested natively.
# Model and local-server support varies, so an explicit capability rejection
# falls back to prompt JSON; the local envelope validation always applies.
BATCH_SCHEMA_PROVIDERS = frozenset({
    "openrouter", "openai", "gemini", "anthropic", "lm_studio", "vllm", "ollama",
})
# OpenRouter routes between upstreams, so it must never silently drop the schema.
BATCH_SCHEMA_NO_DOWNGRADE_PROVIDERS = frozenset({"openrouter"})


def _normalize(provider_id: str | None) -> str:
    return (provider_id or "").strip().casefold()


def structured_output_mode(provider_id: str | None) -> str:
    """Describe enforcement truthfully; prompt JSON is not native schema enforcement."""

    if _normalize(provider_id) in STRICT_JSON_SCHEMA_PROVIDERS:
        return "strict_json_schema"
    return "prompt_json_with_local_validation"


def batch_translation_output_mode(provider_id: str | None) -> str:
    """Describe how the batch translation envelope is requested from a provider."""

    normalized = _normalize(provider_id)
    if normalized in BATCH_SCHEMA_NO_DOWNGRADE_PROVIDERS:
        return "strict_json_schema"
    if normalized in BATCH_SCHEMA_PROVIDERS:
        return "json_schema_with_capability_fallback"
    return "prompt_json_with_local_validation"
