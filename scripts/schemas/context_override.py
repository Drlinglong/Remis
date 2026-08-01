"""Bounded contracts for normal-user Context Release overrides."""

from __future__ import annotations

import math
import re
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


MAX_CONTEXT_KEY_LENGTH = 200
MAX_OVERRIDE_FIELDS = 20
MAX_OVERRIDE_LIST_ITEMS = 50
MAX_OVERRIDE_DEPTH = 4
MAX_OVERRIDE_KEY_LENGTH = 120
MAX_OVERRIDE_TEXT_LENGTH = 1200
MAX_OVERRIDE_NOTE_LENGTH = 1000
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|api[_-]?token|authorization|password|secret|token)\s*[:=]"
)
_SENSITIVE_KEYS = {
    "api_key",
    "api_token",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}


def _normalized_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def validate_override_value(value: Any, depth: int = 0) -> Any:
    """Validate a small JSON-like override without retaining credentials."""
    if depth > MAX_OVERRIDE_DEPTH:
        raise ValueError("Human override values are nested too deeply")
    if isinstance(value, dict):
        if len(value) > MAX_OVERRIDE_FIELDS:
            raise ValueError("Human override values contain too many fields")
        result: dict[str, Any] = {}
        for raw_key, nested in value.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError("Human override field names must be non-empty strings")
            key = raw_key.strip()
            normalized = _normalized_key(key)
            if (
                len(key) > MAX_OVERRIDE_KEY_LENGTH
                or normalized in _SENSITIVE_KEYS
                or normalized.endswith("_secret")
                or normalized.endswith("_token")
            ):
                raise ValueError("Human override values cannot contain credential fields")
            result[key] = validate_override_value(nested, depth + 1)
        return result
    if isinstance(value, list):
        if len(value) > MAX_OVERRIDE_LIST_ITEMS:
            raise ValueError("Human override lists contain too many items")
        return [validate_override_value(item, depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > MAX_OVERRIDE_TEXT_LENGTH:
            raise ValueError("Human override text is too long")
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Human override numbers must be finite")
        return value
    raise ValueError("Human override values must be JSON-compatible")


class StartContextDraftRequest(BaseModel):
    """Start editing one published release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_release_id: str = Field(min_length=1, max_length=200)


class SaveContextOverrideRequest(BaseModel):
    """One structured edit for an existing published context key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_key: str = Field(
        min_length=1,
        max_length=MAX_CONTEXT_KEY_LENGTH,
        validation_alias=AliasChoices("context_key", "target_key"),
    )
    value: dict[str, Any] = Field(
        min_length=1,
        max_length=MAX_OVERRIDE_FIELDS,
    )
    note: str | None = Field(default=None, max_length=MAX_OVERRIDE_NOTE_LENGTH)

    _validate_value = field_validator("value")(validate_override_value)

    @field_validator("note")
    @classmethod
    def _reject_secret_like_notes(cls, value: str | None) -> str | None:
        if value is not None and _SENSITIVE_ASSIGNMENT.search(value):
            raise ValueError("Human override notes cannot contain credential assignments")
        return value


class StartContextDraftBody(BaseModel):
    """Compatibility body for clients that submit project_id in the payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1, max_length=200)
    base_release_id: str = Field(min_length=1, max_length=200)
