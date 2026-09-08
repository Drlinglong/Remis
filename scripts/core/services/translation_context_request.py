"""Normalize translation context controls at request/config boundaries."""

from __future__ import annotations

from typing import Any, Mapping


def context_workflow_kwargs(source: Any = None, **overrides: Any) -> dict[str, Any]:
    """Preserve typed context controls when crossing legacy workflow seams."""

    def read(key: str, default: Any) -> Any:
        if source is None:
            return default
        if isinstance(source, Mapping):
            return source.get(key, default)
        value = getattr(source, key, default)
        if isinstance(default, bool):
            return value if isinstance(value, bool) else default
        if isinstance(default, int):
            return value if isinstance(value, int) and not isinstance(value, bool) else default
        if default is None:
            return value if value is None or isinstance(value, (str, Mapping)) else default
        return value

    result = {
        "use_project_context": overrides.get("use_project_context", read("use_project_context", False)),
        "translation_context_mode": overrides.get("translation_context_mode", read("translation_context_mode", None)),
        "context_release_id": overrides.get("context_release_id", read("context_release_id", None)),
        "context_character_budget": overrides.get("context_character_budget", read("context_character_budget", 4000)),
        "stale_choice": overrides.get("stale_choice", read("stale_choice", None)),
        "stale_acknowledgement": overrides.get(
            "stale_acknowledgement", read("stale_acknowledgement", None)
        ),
    }
    return {
        key: value for key, value in result.items()
        if key not in {"stale_choice", "stale_acknowledgement"} or value is not None
    }


__all__ = ["context_workflow_kwargs"]
