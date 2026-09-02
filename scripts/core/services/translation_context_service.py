"""Deterministic, release-gated context selection for translation prompts.

This module is deliberately a translation integration boundary.  It reads a
published context release once before batch workers start, builds a small
source-identity index, and returns immutable selections for individual
batches.  It does not analyse source text, perform retrieval, or call a
provider.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.context_service import ContextService
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.repositories.context_tree_v2_repository import ContextTreeV2Repository
from scripts.core.services.context_tree_v2_translation_adapter import (
    ContextTreeV2TranslationAdapter,
)
from scripts.core.services.source_snapshot_service import (
    SourceFileInput,
    SourceItemInput,
    SourceSnapshot,
    SourceSnapshotService,
    normalize_relative_path,
    normalize_source_key,
)
from scripts.core.services.translation_context_gate import (
    TranslationContextGate,
)
from scripts.core.services.translation_context_request import context_workflow_kwargs
from scripts.core.services.translation_context_stale_policy import (
    STALE_DISABLE_ARCHIVE,
    STALE_USE_OLD_ARCHIVE,
    project_summary,
    stale_decision,
    stale_warning,
)


DEFAULT_CONTEXT_CHARACTER_BUDGET = 4000
CONTEXT_NEXT_ACTIONS = ("analyze_context", "update_context_archive")
CONTEXT_SELECTION_STATUSES = frozenset({
    "ready", "stale_summary_only", "disabled", "blocked",
})


def prepare_translation_context(
    *,
    project_id: str | None,
    files_data: Iterable[Mapping[str, Any]],
    enabled: bool,
    requested_release_id: str | None,
    character_budget: int,
    mode: str | None = None,
    context_service: Any = None,
    snapshot_service: Any = None,
    stale_choice: str | Mapping[str, Any] | None = None,
    stale_acknowledgement: Mapping[str, Any] | None = None,
    stale_ack: Mapping[str, Any] | None = None,
    workflow_kind: str | None = None,
) -> "ContextSelection":
    selection = TranslationContextService(
        context_service=context_service,
        snapshot_service=snapshot_service,
        character_budget=character_budget,
    ).prepare(
        project_id=project_id,
        files_data=files_data,
        enabled=enabled,
        requested_release_id=requested_release_id,
        mode=mode,
        stale_choice=stale_choice,
        stale_acknowledgement=stale_acknowledgement or stale_ack,
        workflow_kind=workflow_kind or "initial",
    )
    effective_mode = mode or ("archive" if enabled else "none")
    if selection.status == "disabled" and selection.user_choice == STALE_DISABLE_ARCHIVE:
        effective_mode = "glossaries"
    TranslationContextGate.require_ready(effective_mode, selection)
    if selection.warning:
        logging.warning(
            "Translation context unavailable (%s).",
            selection.warning["code"],
        )
    return selection


def prepare_workflow_context(
    project_id,
    files_data,
    enabled,
    release_id,
    budget,
    context_service=None,
    snapshot_service=None,
    mode=None,
    stale_choice=None,
    stale_acknowledgement=None,
    stale_ack=None,
    workflow_kind=None,
):
    return prepare_translation_context(
        project_id=project_id,
        files_data=files_data,
        enabled=enabled,
        requested_release_id=release_id,
        character_budget=budget,
        mode=mode,
        context_service=context_service,
        snapshot_service=snapshot_service,
        stale_choice=stale_choice,
        stale_acknowledgement=stale_acknowledgement or stale_ack,
        workflow_kind=workflow_kind,
    )


def prepare_context_with_warnings(
    project_id,
    files_data,
    enabled,
    release_id,
    budget,
    context_service=None,
    snapshot_service=None,
    mode=None,
    stale_choice=None,
    stale_acknowledgement=None,
    stale_ack=None,
    workflow_kind=None,
):
    selection = prepare_workflow_context(
        project_id,
        files_data,
        enabled,
        release_id,
        budget,
        context_service,
        snapshot_service,
        mode,
        stale_choice,
        stale_acknowledgement,
        stale_ack,
        workflow_kind or "incremental",
    )
    return selection, [selection.warning] if selection.warning else []


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _source_identity(source_item: Mapping[str, Any]) -> tuple[str, str] | None:
    metadata = source_item.get("metadata") or {}
    relative_path = (
        metadata.get("relative_path")
        or metadata.get("file_path")
        or metadata.get("path")
    )
    item_key = (
        metadata.get("item_key")
        or metadata.get("localization_key")
        or metadata.get("source_key")
        or metadata.get("key")
    )
    source_ref = str(source_item.get("source_ref") or "").strip()
    if not relative_path and source_ref:
        for separator in ("::", "#", "|"):
            if separator in source_ref:
                relative_path, item_key = source_ref.split(separator, 1)
                break
        else:
            candidate_path, separator, candidate_key = source_ref.rpartition(":")
            if separator and candidate_key and not candidate_key.isdigit():
                relative_path, item_key = candidate_path, candidate_key
            else:
                relative_path = source_ref
    if not relative_path or not item_key:
        return None
    try:
        normalized_path = normalize_relative_path(relative_path)
        normalized_key = normalize_source_key(str(item_key))
    except ValueError:
        return None
    return (normalized_path, normalized_key) if normalized_key else None


def _source_items(file_data: Mapping[str, Any]) -> list[SourceItemInput]:
    entries = file_data.get("source_entries") or []
    if not entries and file_data.get("parsed_entries"):
        entries = [
            {"key": item[0], "source": item[1]}
            for item in file_data["parsed_entries"]
        ]
    if not entries:
        key_map = file_data.get("key_map") or {}
        entries = []
        for index, source in enumerate(file_data.get("texts_to_translate") or []):
            key_info = key_map[index] if isinstance(key_map, list) and index < len(key_map) else {}
            if isinstance(key_map, dict):
                key_info = key_map.get(index, {})
            entries.append({
                "key": key_info.get("key", key_info.get("key_part")),
                "source": source,
            })
    return [
        SourceItemInput(
            key=entry.get("key"),
            source_order=index,
            source_text=entry.get("source", ""),
        )
        for index, entry in enumerate(entries)
        if entry.get("key") is not None
    ]


def build_translation_source_snapshot(
    files_data: Iterable[Mapping[str, Any]],
    snapshot_service: SourceSnapshotService | None = None,
) -> SourceSnapshot:
    """Build the shared snapshot from the same parsed file material used by translation."""

    inputs = []
    for file_data in files_data:
        relative_path = file_data.get("file_path") or file_data.get("filename")
        if not relative_path:
            continue
        disk_path = file_data.get("path") or file_data.get("full_path")
        if disk_path and Path(disk_path).is_file():
            content = Path(disk_path).read_bytes()
        else:
            original_lines = file_data.get("original_lines")
            if original_lines is not None:
                content = "".join(original_lines)
            else:
                content = ""
        inputs.append(
            SourceFileInput(
                relative_path=relative_path,
                content=content,
                items=tuple(_source_items(file_data)),
            )
        )
    return (snapshot_service or SourceSnapshotService()).build_snapshot(inputs)


@dataclass(frozen=True)
class ContextSelection:
    """A frozen release view safe to share with batch construction."""

    enabled: bool
    status: str
    release_id: str | None
    source_snapshot_hash: str | None
    release_source_snapshot_hash: str | None
    project_summary: tuple[dict[str, Any], ...] = ()
    direct_index: Mapping[tuple[str, str], tuple[dict[str, Any], ...]] = MappingProxyType({})
    character_budget: int = DEFAULT_CONTEXT_CHARACTER_BUDGET
    warning: dict[str, Any] | None = None
    user_choice: str | None = None
    workflow_kind: str = "unknown"

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "context_release_id": self.release_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "release_source_snapshot_hash": self.release_source_snapshot_hash,
            "character_budget": self.character_budget,
            "user_choice": self.user_choice,
            "workflow": self.workflow_kind,
            "selected_contexts": [],
            "telemetry": {
                "release_id": self.release_id,
                "source_snapshot_hash": self.source_snapshot_hash,
                "user_choice": self.user_choice,
                "workflow": self.workflow_kind,
                "contexts": [],
            },
            "warning": self.warning,
        }

    def _metadata_for(self, selected: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        actual = []
        for item in selected:
            summary = item.get("summary", {})
            chars = len(json.dumps(
                summary, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ))
            actual.append({
                "context_key": str(item.get("context_key", "")),
                "context_type": str(item.get("aggregate_type", "")),
                "chars": chars,
                "tokens": math.ceil(chars / 4) if chars else 0,
            })
        metadata = self.metadata
        metadata["selected_contexts"] = actual
        metadata["telemetry"] = {
            **metadata["telemetry"],
            "contexts": actual,
        }
        return metadata

    def select_for_batch(
        self,
        relative_path: str,
        source_entries: Iterable[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.status not in {"ready", "stale_summary_only"}:
            return [], self._metadata_for(())
        try:
            normalized_path = normalize_relative_path(relative_path)
        except ValueError:
            return [], self._metadata_for(())

        candidates: list[tuple[tuple[str, str, str], dict[str, Any]]] = []
        for item in self.project_summary:
            candidates.append((("", "", str(item["context_key"])), item))
        identities = []
        for entry in source_entries:
            key = normalize_source_key(entry.get("key"))
            if key:
                identities.append((normalized_path, key))
        for identity in sorted(set(identities)):
            for item in self.direct_index.get(identity, ()):
                candidates.append(((identity[0], identity[1], str(item["context_key"])), item))

        selected: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        remaining = self.character_budget
        for _, item in candidates:
            context_key = str(item["context_key"])
            if context_key in seen_keys:
                continue
            cost = _json_size(item)
            if cost > remaining:
                continue
            selected.append(item)
            seen_keys.add(context_key)
            remaining -= cost
        return selected, self._metadata_for(selected)


class TranslationContextService:
    """Resolve and index one immutable context release per translation workflow."""

    def __init__(
        self,
        context_service: Any | None = None,
        snapshot_service: SourceSnapshotService | None = None,
        character_budget: int = DEFAULT_CONTEXT_CHARACTER_BUDGET,
        tree_v2_repository: Any | None = None,
        workflow_kind: str = "unknown",
    ):
        self.context_service = context_service
        self.tree_v2_repository = tree_v2_repository
        self.tree_v2_enabled = tree_v2_repository is not None or context_service is None
        self.snapshot_service = snapshot_service or SourceSnapshotService()
        self.character_budget = max(0, int(character_budget))
        self.workflow_kind = workflow_kind

    def prepare(
        self,
        *,
        project_id: str | None,
        files_data: Iterable[Mapping[str, Any]],
        enabled: bool = True,
        requested_release_id: str | None = None,
        mode: str | None = None,
        stale_choice: str | Mapping[str, Any] | None = None,
        stale_acknowledgement: Mapping[str, Any] | None = None,
        stale_ack: Mapping[str, Any] | None = None,
        workflow_kind: str | None = None,
    ) -> ContextSelection:
        materialized_files = list(files_data)
        workflow = workflow_kind or self.workflow_kind
        acknowledgement = stale_acknowledgement or stale_ack
        if mode in {"none", "glossaries", "disabled"} or (not enabled and mode != "archive"):
            return self._disabled_selection(workflow_kind=workflow)

        if not project_id:
            if mode == "archive":
                return self._warning_selection(
                    "blocked",
                    "context_release_unverified",
                    None,
                    requested_release_id,
                    workflow_kind=workflow,
                )
            return self._disabled_selection(workflow_kind=workflow)

        snapshot = self._build_snapshot(materialized_files)
        current_hash = snapshot.source_snapshot_hash
        tree_selection = self._tree_v2_selection(
            project_id, requested_release_id, current_hash,
            stale_choice=stale_choice,
            stale_acknowledgement=acknowledgement,
            workflow_kind=workflow,
        )
        if tree_selection is not None:
            return tree_selection
        service = self._get_context_service()
        release_id, effective, release_is_project, release_hash, effective_is_project = (
            self._release_metadata(service, project_id, requested_release_id)
        )
        source_match = (
            None if release_hash is None else release_hash == current_hash
        )
        effective_items = (
            len((effective.effective_context or {}))
            if effective_is_project
            else None
        )
        if mode == "archive":
            decision = TranslationContextGate.decide(
                mode,
                release_id=(release_id if release_is_project else None),
                source_snapshot_match=source_match,
                effective_context_items=effective_items,
            )
            if decision.blocked and decision.reason_code != "context_release_stale":
                return self._warning_selection(
                    "blocked",
                    decision.reason_code or "context_release_unverified",
                    current_hash,
                    release_id,
                    release_hash,
                    warning={
                        "type": "context_release_blocked",
                        "code": decision.reason_code,
                        "message": (
                            "Project context was not injected: "
                            f"{decision.reason_code}."
                        ),
                        "allowed_actions": decision.allowed_actions,
                    },
                    workflow_kind=workflow,
                )

        if effective is None or effective.release.project_id != project_id:
            return self._warning_selection(
                "blocked", "context_release_missing", current_hash, release_id,
                workflow_kind=workflow,
            )

        if release_hash != current_hash:
            return self._stale_selection(
                current_hash, release_id, release_hash, effective,
                stale_choice=stale_choice,
                stale_acknowledgement=acknowledgement,
                workflow_kind=workflow,
            )

        effective_context = effective.effective_context or {}
        if not effective_context:
            return self._warning_selection(
                "blocked",
                "context_release_empty",
                current_hash,
                release_id,
                release_hash,
                workflow_kind=workflow,
            )
        traceability = service.traceability(release_id)
        memberships = (
            service.delivery_memberships(release_id)
            if hasattr(service, "delivery_memberships") else []
        )
        project_summary, direct_index = self._build_index(
            effective_context, traceability, memberships,
        )
        return ContextSelection(
            enabled=True,
            status="ready",
            release_id=release_id,
            source_snapshot_hash=current_hash,
            release_source_snapshot_hash=release_hash,
            project_summary=tuple(project_summary),
            direct_index=MappingProxyType({key: tuple(value) for key, value in direct_index.items()}),
            character_budget=self.character_budget, workflow_kind=workflow,
        )

    def _get_context_service(self) -> Any:
        if self.context_service is None:
            self.context_service = ContextService(ContextRepository(PROJECTS_DB_PATH))
        return self.context_service

    def _tree_v2_selection(
        self,
        project_id: str,
        requested_release_id: str | None,
        current_hash: str,
        *,
        stale_choice: str | Mapping[str, Any] | None,
        stale_acknowledgement: Mapping[str, Any] | None,
        workflow_kind: str,
    ) -> ContextSelection | None:
        if not self.tree_v2_enabled:
            return None
        if self.tree_v2_repository is None:
            self.tree_v2_repository = ContextTreeV2Repository(PROJECTS_DB_PATH)
        projected = ContextTreeV2TranslationAdapter(
            self.tree_v2_repository
        ).resolve(project_id, requested_release_id)
        if projected is None:
            return None
        if projected.source_snapshot_hash != current_hash:
            return self._stale_projection_selection(
                projected,
                current_hash,
                stale_choice=stale_choice,
                stale_acknowledgement=stale_acknowledgement,
                workflow_kind=workflow_kind,
            )
        return ContextSelection(
            enabled=True,
            status="ready",
            release_id=projected.release_id,
            source_snapshot_hash=current_hash,
            release_source_snapshot_hash=projected.source_snapshot_hash,
            project_summary=projected.project_summary,
            direct_index=MappingProxyType(projected.direct_index),
            character_budget=self.character_budget,
            workflow_kind=workflow_kind,
        )

    def _stale_projection_selection(
        self,
        projected: Any,
        current_hash: str,
        *,
        stale_choice: str | Mapping[str, Any] | None,
        stale_acknowledgement: Mapping[str, Any] | None,
        workflow_kind: str,
    ) -> ContextSelection:
        choice, acknowledged = stale_decision(
            stale_choice, stale_acknowledgement,
            projected.release_id, projected.source_snapshot_hash, current_hash,
        )
        warning = stale_warning(
            projected.release_id, projected.source_snapshot_hash, current_hash, choice,
            CONTEXT_NEXT_ACTIONS,
        )
        if acknowledged and choice == STALE_USE_OLD_ARCHIVE:
            return ContextSelection(
                enabled=True,
                status="stale_summary_only",
                release_id=projected.release_id,
                source_snapshot_hash=current_hash,
                release_source_snapshot_hash=projected.source_snapshot_hash,
                project_summary=projected.project_summary,
                direct_index=MappingProxyType({}),
                character_budget=self.character_budget,
                warning=warning,
                user_choice=choice,
                workflow_kind=workflow_kind,
            )
        if acknowledged and choice == STALE_DISABLE_ARCHIVE:
            return self._disabled_selection(
                workflow_kind=workflow_kind,
                release_id=projected.release_id,
                current_hash=current_hash,
                release_hash=projected.source_snapshot_hash,
                user_choice=choice,
                warning=warning,
            )
        return self._warning_selection(
            "blocked", "context_release_stale", current_hash,
            projected.release_id, projected.source_snapshot_hash,
            warning=warning, workflow_kind=workflow_kind,
        )

    def _stale_selection(
        self,
        current_hash: str,
        release_id: str | None,
        release_hash: str | None,
        effective: Any,
        *,
        stale_choice: str | Mapping[str, Any] | None,
        stale_acknowledgement: Mapping[str, Any] | None,
        workflow_kind: str,
    ) -> ContextSelection:
        choice, acknowledged = stale_decision(
            stale_choice, stale_acknowledgement,
            str(release_id or ""), str(release_hash or ""), current_hash,
        )
        warning = stale_warning(
            release_id, release_hash, current_hash, choice,
            CONTEXT_NEXT_ACTIONS,
        )
        if acknowledged and choice == STALE_USE_OLD_ARCHIVE:
            project_summary_items = project_summary(effective.effective_context or {})
            return ContextSelection(
                enabled=True,
                status="stale_summary_only",
                release_id=release_id,
                source_snapshot_hash=current_hash,
                release_source_snapshot_hash=release_hash,
                project_summary=tuple(project_summary_items),
                direct_index=MappingProxyType({}),
                character_budget=self.character_budget,
                warning=warning,
                user_choice=choice,
                workflow_kind=workflow_kind,
            )
        if acknowledged and choice == STALE_DISABLE_ARCHIVE:
            return self._disabled_selection(
                workflow_kind=workflow_kind,
                release_id=release_id,
                current_hash=current_hash,
                release_hash=release_hash,
                user_choice=choice,
                warning=warning,
            )
        return self._warning_selection(
            "blocked", "context_release_stale", current_hash, release_id,
            release_hash, warning=warning, workflow_kind=workflow_kind,
        )

    def _build_snapshot(self, files_data: Iterable[Mapping[str, Any]]) -> SourceSnapshot:
        # The injected service is intentionally used when tests or callers need
        # to prove the exact snapshot contract without opening a database.
        if hasattr(self.snapshot_service, "build_snapshot") and not isinstance(self.snapshot_service, SourceSnapshotService):
            return self.snapshot_service.build_snapshot(files_data)
        return build_translation_source_snapshot(files_data, self.snapshot_service)

    @staticmethod
    def _release_metadata(service: Any, project_id: str, requested_release_id: str | None):
        releases = service.list_releases(project_id)
        release_id = requested_release_id
        effective = None
        if requested_release_id:
            release = next(
                (item for item in releases if item.release_id == requested_release_id),
                None,
            )
            if release is not None:
                effective = service.effective_context(requested_release_id)
        else:
            release = releases[0] if releases else None
            release_id = release.release_id if release else None
            if release_id:
                effective = service.effective_context(release_id)
        release_is_project = release is not None and release.project_id == project_id
        release_hash = (
            release.metadata.source_snapshot_hash
            if release_is_project
            else (
                effective.release.metadata.source_snapshot_hash
                if effective is not None and effective.release.project_id == project_id
                else None
            )
        )
        effective_is_project = effective is not None and effective.release.project_id == project_id
        return release_id, effective, release_is_project, release_hash, effective_is_project

    def _warning_selection(
        self,
        status: str,
        code: str,
        current_hash: str | None,
        release_id: str | None,
        release_hash: str | None = None,
        warning: dict[str, Any] | None = None,
        *,
        workflow_kind: str | None = None,
    ) -> ContextSelection:
        if status not in CONTEXT_SELECTION_STATUSES:
            raise ValueError(f"Unsupported context selection status: {status}")
        warning = warning or {
            "type": "context_release_warning",
            "code": code,
            "message": f"Project context was not injected: {code}.",
            "allowed_actions": list(CONTEXT_NEXT_ACTIONS),
        }
        return ContextSelection(
            enabled=True,
            status=status,
            release_id=release_id,
            source_snapshot_hash=current_hash,
            release_source_snapshot_hash=release_hash,
            character_budget=self.character_budget,
            warning=warning,
            workflow_kind=workflow_kind or self.workflow_kind,
        )

    def _disabled_selection(
        self,
        *,
        workflow_kind: str | None = None,
        release_id: str | None = None,
        current_hash: str | None = None,
        release_hash: str | None = None,
        user_choice: str | None = None,
        warning: dict[str, Any] | None = None,
    ) -> ContextSelection:
        return ContextSelection(
            enabled=False,
            status="disabled",
            release_id=release_id,
            source_snapshot_hash=current_hash,
            release_source_snapshot_hash=release_hash,
            character_budget=self.character_budget,
            warning=warning,
            user_choice=user_choice,
            workflow_kind=workflow_kind or self.workflow_kind,
        )

    @staticmethod
    def _build_index(
        effective_context: Mapping[str, Mapping[str, Any]],
        traceability: Iterable[Mapping[str, Any]],
        delivery_memberships: Iterable[Mapping[str, Any]] = (),
    ) -> tuple[list[dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
        project_summary: list[dict[str, Any]] = []
        direct_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
        seen: set[str] = set()
        for row in traceability:
            aggregate = row.get("aggregate") or {}
            context_key = str(aggregate.get("aggregate_key") or "")
            if not context_key or context_key not in effective_context or context_key in seen:
                continue
            item = {
                "context_key": context_key,
                "aggregate_type": str(aggregate.get("aggregate_type") or "entity"),
                "summary": effective_context[context_key],
            }
            seen.add(context_key)
            if item["aggregate_type"] == "project" or context_key.startswith("project:"):
                project_summary.append(item)
                continue
            for contribution in row.get("contributions") or []:
                identity = _source_identity(contribution.get("source_item") or {})
                if identity:
                    direct_index.setdefault(identity, []).append(item)

        for context_key, summary in sorted(effective_context.items()):
            if context_key in seen or not context_key.startswith("project:"):
                continue
            project_summary.append({
                "context_key": context_key,
                "aggregate_type": "project",
                "summary": summary,
            })
        for membership in delivery_memberships:
            role = (membership.get("membership") or {}).get("role") or membership.get("role")
            if role and role not in {"primary_member", "supporting_context"}:
                continue
            aggregate = membership.get("aggregate") or {}
            context_key = str(aggregate.get("aggregate_key") or "")
            identity = _source_identity(membership.get("source_item") or {})
            if not identity or context_key not in effective_context:
                continue
            direct_index.setdefault(identity, []).append({
                "context_key": context_key,
                "aggregate_type": str(aggregate.get("aggregate_type") or "event"),
                "summary": effective_context[context_key],
            })
        project_summary.sort(key=lambda item: str(item["context_key"]))
        for items in direct_index.values():
            unique = {str(item["context_key"]): item for item in items}
            items[:] = sorted(unique.values(), key=lambda item: str(item["context_key"]))
        return project_summary, direct_index
