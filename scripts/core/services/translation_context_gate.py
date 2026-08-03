"""Shared fail-closed policy for archive-backed translation context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ARCHIVE_CONTEXT_MODE = "archive"
ARCHIVE_BLOCKING_REASONS = frozenset({
    "context_release_missing",
    "context_release_stale",
    "context_release_unverified",
    "context_release_empty",
})
ARCHIVE_ALLOWED_ACTIONS = ("analyze_context", "update_context_archive")


@dataclass(frozen=True)
class ArchiveGateDecision:
    """The same archive decision shape used by Agent and workflow callers."""

    reason_code: str | None
    status: str
    can_start: bool

    @property
    def blocked(self) -> bool:
        return self.reason_code is not None

    @property
    def allowed_actions(self) -> list[str]:
        if not self.blocked:
            return []
        return list(ARCHIVE_ALLOWED_ACTIONS)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "can_start": self.can_start,
            "reason_code": self.reason_code,
            "allowed_actions": self.allowed_actions,
        }


@dataclass(frozen=True)
class TranslationContextGateEvaluation:
    """A release comparison suitable for both low-level and Agent callers."""

    can_start: bool
    blockers: tuple[str, ...]
    archive: dict[str, Any]

    def warning_payload(self) -> dict[str, Any]:
        reason_code = self.blockers[0] if self.blockers else None
        return {
            "type": "context_release_warning",
            "code": reason_code,
            "message": (
                f"Project context was not injected: {reason_code}."
                if reason_code else "Project context is ready."
            ),
            "allowed_actions": list(ARCHIVE_ALLOWED_ACTIONS),
            "archive": dict(self.archive),
        }


class TranslationContextGateError(RuntimeError):
    """Structured workflow failure when archive context cannot be trusted."""

    def __init__(self, reason_code: str, *, selection: Any):
        self.reason_code = reason_code
        self.code = "project_context_not_ready"
        self.detail = {
            "code": self.code,
            "reason_code": reason_code,
            "message": (
                "The requested archive context is not ready for translation: "
                f"{reason_code}."
            ),
            "allowed_actions": list(ARCHIVE_ALLOWED_ACTIONS),
            "context": selection.metadata,
        }
        super().__init__(self.detail["message"])


class TranslationContextGate:
    """Centralize archive readiness semantics at both workflow boundaries."""

    def __init__(self, *, context_service: Any, snapshot_service: Any):
        self.context_service = context_service
        self.snapshot_service = snapshot_service

    def evaluate(
        self,
        project_id: str,
        mode: str,
        *,
        current_snapshot: Any,
        requested_release_id: str | None = None,
    ) -> TranslationContextGateEvaluation:
        if mode != ARCHIVE_CONTEXT_MODE:
            return TranslationContextGateEvaluation(True, (), {})
        effective = None
        release_id = requested_release_id
        if requested_release_id:
            effective = self.context_service.effective_context(requested_release_id)
        else:
            releases = self.context_service.list_releases(project_id)
            latest = releases[0] if releases else None
            release_id = latest.release_id if latest else None
            if release_id:
                effective = self.context_service.effective_context(release_id)
        release = effective.release if effective is not None else None
        release_hash = (
            release.metadata.source_snapshot_hash if release is not None else None
        )
        current_hash = getattr(current_snapshot, "source_snapshot_hash", None)
        archive = {
            "release_id": release_id,
            "source_snapshot_hash": release_hash,
            "current_source_snapshot_hash": current_hash,
            "source_snapshot_match": (
                None
                if release_hash is None or current_hash is None
                else release_hash == current_hash
            ),
            "effective_context_items": len(
                (effective.effective_context if effective is not None else {}) or {}
            ),
        }
        reason_code = self.archive_reason(
            archive["release_id"],
            archive["source_snapshot_match"],
            archive["effective_context_items"] if release is not None else None,
        )
        return TranslationContextGateEvaluation(
            can_start=reason_code is None,
            blockers=(reason_code,) if reason_code else (),
            archive=archive,
        )

    @staticmethod
    def archive_reason(
        release_id: str | None,
        source_snapshot_match: bool | None,
        effective_context_items: int | None,
    ) -> str | None:
        if not release_id:
            return "context_release_missing"
        if source_snapshot_match is False:
            return "context_release_stale"
        if source_snapshot_match is None:
            return "context_release_unverified"
        if effective_context_items is None:
            return "context_release_unverified"
        if effective_context_items == 0:
            return "context_release_empty"
        return None

    @classmethod
    def decide(
        cls,
        mode: str,
        *,
        release_id: str | None = None,
        source_snapshot_match: bool | None = None,
        effective_context_items: int | None = None,
    ) -> ArchiveGateDecision:
        if mode != ARCHIVE_CONTEXT_MODE:
            return ArchiveGateDecision(None, "ready", True)
        reason_code = cls.archive_reason(
            release_id, source_snapshot_match, effective_context_items,
        )
        return ArchiveGateDecision(
            reason_code,
            "blocked" if reason_code else "ready",
            reason_code is None,
        )

    @classmethod
    def require_ready(cls, mode: str, selection: Any) -> Any:
        """Return a usable selection or fail before a translation call starts."""
        if mode != ARCHIVE_CONTEXT_MODE:
            return selection
        if not getattr(selection, "enabled", False):
            raise TranslationContextGateError(
                "context_release_unverified",
                selection=selection,
            )
        warning = getattr(selection, "warning", None) or {}
        reason_code = warning.get("code")
        if reason_code not in ARCHIVE_BLOCKING_REASONS:
            if getattr(selection, "status", "") == "ready":
                return selection
            reason_code = "context_release_unverified"
        raise TranslationContextGateError(reason_code, selection=selection)


def require_workflow_context_ready(mode: str | None, selection: Any) -> Any:
    """Small adapter for legacy initial/update workflow boundaries."""
    effective_mode = mode or (
        ARCHIVE_CONTEXT_MODE if getattr(selection, "enabled", False) else "none"
    )
    return TranslationContextGate.require_ready(effective_mode, selection)


def prepare_and_require_workflow_context(
    prepare_context: Any,
    context_args: tuple[Any, ...],
    mode: str | None,
) -> Any:
    """Prepare context and enforce the shared gate at a workflow boundary."""
    prepared = prepare_context(*context_args, mode)
    selection = prepared[0] if isinstance(prepared, tuple) else prepared
    require_workflow_context_ready(mode, selection)
    return prepared


def archive_readiness_payload(
    mode: str,
    *,
    release_id: str | None,
    source_snapshot_match: bool | None,
    effective_context_items: int | None,
) -> dict[str, Any]:
    """Serialize a decision without making callers duplicate policy logic."""
    return TranslationContextGate.decide(
        mode,
        release_id=release_id,
        source_snapshot_match=source_snapshot_match,
        effective_context_items=effective_context_items,
    ).as_dict()
