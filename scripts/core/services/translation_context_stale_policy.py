"""Pure stale-release policy helpers for translation context selection."""

from __future__ import annotations

from typing import Any, Mapping


STALE_USE_OLD_ARCHIVE = "use_old_archive"
STALE_DISABLE_ARCHIVE = "disable_archive"


def normalize_stale_choice(
    choice: str | Mapping[str, Any] | None,
    acknowledgement: Mapping[str, Any] | None,
) -> str | None:
    value: Any = choice
    if isinstance(value, Mapping):
        value = value.get("choice") or value.get("user_choice") or value.get("selection")
    if value is None and acknowledgement:
        value = (
            acknowledgement.get("choice")
            or acknowledgement.get("user_choice")
            or acknowledgement.get("selection")
        )
    aliases = {
        "use_old_archive": STALE_USE_OLD_ARCHIVE,
        "use_old_context": STALE_USE_OLD_ARCHIVE,
        "continue_old_archive": STALE_USE_OLD_ARCHIVE,
        "continue": STALE_USE_OLD_ARCHIVE,
        "old_archive": STALE_USE_OLD_ARCHIVE,
        "continue_using_old_archive": STALE_USE_OLD_ARCHIVE,
        "disable_archive": STALE_DISABLE_ARCHIVE,
        "disable": STALE_DISABLE_ARCHIVE,
        "disabled": STALE_DISABLE_ARCHIVE,
        "no_archive": STALE_DISABLE_ARCHIVE,
        "without_archive": STALE_DISABLE_ARCHIVE,
        "use_glossaries_only": STALE_DISABLE_ARCHIVE,
        "glossaries_only": STALE_DISABLE_ARCHIVE,
    }
    return aliases.get(str(value or "").strip().casefold())


def stale_decision(
    stale_choice: str | Mapping[str, Any] | None,
    acknowledgement: Mapping[str, Any] | None,
    release_id: str,
    release_hash: str,
    current_hash: str,
) -> tuple[str | None, bool]:
    if acknowledgement is None and isinstance(stale_choice, Mapping):
        acknowledgement = stale_choice
    requested_choice = normalize_stale_choice(stale_choice, None)
    acknowledged_choice = normalize_stale_choice(None, acknowledgement)
    if requested_choice and acknowledged_choice and requested_choice != acknowledged_choice:
        return requested_choice, False
    choice = requested_choice or acknowledged_choice
    if not choice or not acknowledgement:
        return choice, False
    acknowledged_release = (
        acknowledgement.get("context_release_id")
        or acknowledgement.get("release_id")
    )
    acknowledged_hash = (
        acknowledgement.get("current_source_snapshot_hash")
        or acknowledgement.get("source_snapshot_hash")
    )
    return choice, (
        str(acknowledged_release or "") == str(release_id)
        and str(acknowledged_hash or "") == str(current_hash)
    )


def stale_warning(
    release_id: str | None,
    release_hash: str | None,
    current_hash: str | None,
    choice: str | None,
    next_actions: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "context_release_stale",
        "code": "context_release_stale",
        "message": "The context release is stale; choose how to continue.",
        "allowed_actions": list(next_actions),
        "required_user_choice": [STALE_USE_OLD_ARCHIVE, STALE_DISABLE_ARCHIVE],
        "user_choice": choice,
        "context_release_id": release_id,
        "release_source_snapshot_hash": release_hash,
        "current_source_snapshot_hash": current_hash,
    }


def project_summary(
    effective_context: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "context_key": str(context_key),
            "aggregate_type": "project",
            "summary": summary,
        }
        for context_key, summary in sorted(effective_context.items())
        if str(context_key).startswith("project:")
    ]


__all__ = [
    "STALE_DISABLE_ARCHIVE", "STALE_USE_OLD_ARCHIVE", "normalize_stale_choice",
    "project_summary", "stale_decision", "stale_warning",
]
