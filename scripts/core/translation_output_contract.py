"""Batch translation output envelope shared by every provider adapter.

The envelope is ``{"translations": ["..."]}``. Providers whose APIs enforce a
JSON Schema receive it natively; every response is still validated locally.
Content checks (tokens, formatting, review findings) remain separate.
"""

import json

from scripts.core.provider_structured_output import batch_translation_output_mode
from scripts.core.provider_errors import raise_safe_provider_request_error

BATCH_ENVELOPE_SYSTEM_PROMPT = (
    "You are a professional translator for game mods. Return a JSON object "
    "with a translations array in input order. This output envelope supersedes "
    "any instruction requesting a bare array; preserve all translation rules."
)

_SCHEMA_REJECTION_MARKERS = (
    "response_format", "json_schema", "response_schema", "response_json_schema",
    "output_config", "output_format", "structured output", "structured_output",
    "schema", "format",
)
_SCHEMA_REJECTION_STATUS = frozenset({400, 404, 415, 422, 501})


class TranslationContractError(ValueError):
    """A provider answered, but the answer violates the batch envelope."""


def _validated_count(expected_count: int) -> int:
    if type(expected_count) is not int or expected_count < 1:
        raise ValueError("Translation count must be a positive integer")
    return expected_count


def translation_batch_schema(expected_count: int, *, count_bounds: bool = True) -> dict:
    """Plain JSON Schema for the envelope; omit bounds where a provider rejects them."""
    _validated_count(expected_count)
    items = {"type": "array", "items": {"type": "string"}}
    if count_bounds:
        items.update(minItems=expected_count, maxItems=expected_count)
    return {
        "type": "object",
        "properties": {"translations": items},
        "required": ["translations"],
        "additionalProperties": False,
    }


def translation_response_format(expected_count: int) -> dict:
    """OpenAI-compatible ``response_format`` (OpenAI, OpenRouter, LM Studio, vLLM)."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "translation_batch_v1",
            "strict": True,
            "schema": translation_batch_schema(expected_count),
        },
    }


def anthropic_output_config(expected_count: int) -> dict:
    """Anthropic ``output_config.format``; array length bounds are checked locally."""
    return {"format": {
        "type": "json_schema",
        "schema": translation_batch_schema(expected_count, count_bounds=False),
    }}


def gemini_generation_config(expected_count: int) -> dict:
    """google-genai ``GenerateContentConfig`` fields for native JSON output."""
    return {
        "response_mime_type": "application/json",
        "response_json_schema": translation_batch_schema(expected_count),
    }


def validate_translation_response(raw: str, expected_count: int) -> list[str]:
    """Reject malformed envelopes before the legacy repair parser can hide them."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TranslationContractError(f"Structured translation response is not JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"translations"}:
        raise TranslationContractError("Structured translation response must contain only translations")
    values = payload["translations"]
    if (
        not isinstance(values, list)
        or len(values) != expected_count
        or any(not isinstance(value, str) for value in values)
    ):
        raise TranslationContractError("Structured translation response has invalid types or item count")
    return values


def _status_code(exc: Exception):
    for candidate in (exc, getattr(exc, "response", None)):
        for attribute in ("status_code", "code", "status"):
            value = getattr(candidate, attribute, None)
            if isinstance(value, int):
                return value
    return None


def is_schema_capability_rejection(exc: Exception) -> bool:
    """True only when the request itself was refused for its output-format field.

    Contract violations, transport failures, rate limits and server errors are
    never treated as a missing capability, so they cannot trigger a downgrade.
    """
    if isinstance(exc, (TranslationContractError, json.JSONDecodeError)):
        return False
    message = str(exc).casefold()
    if not any(marker in message for marker in _SCHEMA_REJECTION_MARKERS):
        return False
    if isinstance(exc, TypeError) or exc.__class__.__name__ == "ValidationError":
        return True  # The installed SDK cannot express the schema field.
    return _status_code(exc) in _SCHEMA_REJECTION_STATUS


def call_batch_with_contract(handler, client, prompt: str, expected_count: int) -> str:
    """Dispatch a batch request through the provider's native schema when available.

    A handler opts in by implementing ``_call_schema_batch_api`` and being listed
    in ``provider_structured_output``. A capability rejection disables the schema
    for that handler and resends prompt-only JSON once; any other failure,
    including an invalid envelope, propagates to the batch retry loop.
    """
    schema_call = getattr(handler, "_call_schema_batch_api", None)
    provider = getattr(handler, "provider_name", None)
    if (
        schema_call is not None
        and batch_translation_output_mode(provider) != "prompt_json_with_local_validation"
        and not getattr(handler, "_batch_schema_rejected", False)
    ):
        try:
            raw = schema_call(client, prompt, expected_count)
        except Exception as exc:
            if not is_schema_capability_rejection(exc):
                raise_safe_provider_request_error(exc, provider=provider or "unknown")
            handler._batch_schema_rejected = True
            handler.logger.warning(
                "Provider %s rejected the batch JSON schema (%s); "
                "falling back to prompt-only JSON with local validation.",
                provider, type(exc).__name__,
            )
        else:
            validate_translation_response(raw, expected_count)
            return raw
    return handler._call_api(client, prompt)
