"""Strict OpenRouter batch translation envelope; content checks remain separate."""

import json


def translation_response_format(expected_count: int) -> dict:
    if type(expected_count) is not int or expected_count < 1:
        raise ValueError("Translation count must be a positive integer")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "translation_batch_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "translations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": expected_count,
                        "maxItems": expected_count,
                    },
                },
                "required": ["translations"],
                "additionalProperties": False,
            },
        },
    }


def validate_translation_response(raw: str, expected_count: int) -> list[str]:
    """Reject malformed envelopes before the legacy repair parser can hide them."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {"translations"}:
        raise ValueError("Structured translation response must contain only translations")
    values = payload["translations"]
    if (
        not isinstance(values, list)
        or len(values) != expected_count
        or any(not isinstance(value, str) for value in values)
    ):
        raise ValueError("Structured translation response has invalid types or item count")
    return values
