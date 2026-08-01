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
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.context_service import ContextService
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.services.source_snapshot_service import (
    SourceFileInput,
    SourceItemInput,
    SourceSnapshot,
    SourceSnapshotService,
    normalize_relative_path,
    normalize_source_key,
)


DEFAULT_CONTEXT_CHARACTER_BUDGET = 4000
CONTEXT_NEXT_ACTIONS = ("analyze_context", "update_context_archive")


def context_workflow_kwargs(source: Any = None, **overrides: Any) -> dict[str, Any]:
    """Normalize request/config context controls at workflow boundaries."""
    def read(key: str, default: Any) -> Any:
        if source is None:
            return default
        if isinstance(source, Mapping):
            return source.get(key, default)
        return getattr(source, key, default)

    return {
        "use_project_context": overrides.get("use_project_context", read("use_project_context", True)),
        "context_release_id": overrides.get("context_release_id", read("context_release_id", None)),
        "context_character_budget": overrides.get("context_character_budget", read("context_character_budget", 4000)),
    }


def prepare_translation_context(
    *,
    project_id: str | None,
    files_data: Iterable[Mapping[str, Any]],
    enabled: bool,
    requested_release_id: str | None,
    character_budget: int,
    context_service: Any = None,
    snapshot_service: Any = None,
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
    )
    if selection.warning:
        logging.warning(
            "Translation context unavailable (%s); continuing without stale context.",
            selection.warning["code"],
        )
    return selection


def prepare_workflow_context(project_id, files_data, enabled, release_id, budget, context_service=None, snapshot_service=None):
    return prepare_translation_context(
        project_id=project_id,
        files_data=files_data,
        enabled=enabled,
        requested_release_id=release_id,
        character_budget=budget,
        context_service=context_service,
        snapshot_service=snapshot_service,
    )


def prepare_context_with_warnings(project_id, files_data, enabled, release_id, budget, context_service=None, snapshot_service=None):
    selection = prepare_workflow_context(project_id, files_data, enabled, release_id, budget, context_service, snapshot_service)
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
        SourceItemInput(key=entry.get("key"), source_text=entry.get("source", ""))
        for entry in entries
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
        original_lines = file_data.get("original_lines")
        if original_lines is not None:
            content = "".join(original_lines)
        elif file_data.get("full_path"):
            content = Path(file_data["full_path"]).read_text(encoding="utf-8")
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

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "context_release_id": self.release_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "release_source_snapshot_hash": self.release_source_snapshot_hash,
            "character_budget": self.character_budget,
            "warning": self.warning,
        }

    def select_for_batch(
        self,
        relative_path: str,
        source_entries: Iterable[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.status != "ready":
            return [], self.metadata
        try:
            normalized_path = normalize_relative_path(relative_path)
        except ValueError:
            return [], self.metadata

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
        return selected, self.metadata


class TranslationContextService:
    """Resolve and index one immutable context release per translation workflow."""

    def __init__(
        self,
        context_service: Any | None = None,
        snapshot_service: SourceSnapshotService | None = None,
        character_budget: int = DEFAULT_CONTEXT_CHARACTER_BUDGET,
    ):
        self.context_service = context_service
        self.snapshot_service = snapshot_service or SourceSnapshotService()
        self.character_budget = max(0, int(character_budget))

    def prepare(
        self,
        *,
        project_id: str | None,
        files_data: Iterable[Mapping[str, Any]],
        enabled: bool = True,
        requested_release_id: str | None = None,
    ) -> ContextSelection:
        if not enabled or not project_id:
            return ContextSelection(enabled=False, status="disabled", release_id=None, source_snapshot_hash=None, release_source_snapshot_hash=None)

        snapshot = self._build_snapshot(files_data)
        current_hash = snapshot.source_snapshot_hash
        service = self._get_context_service()
        effective = None
        release_id = requested_release_id
        if requested_release_id:
            effective = service.effective_context(requested_release_id)
        else:
            releases = service.list_releases(project_id)
            latest = releases[0] if releases else None
            release_id = latest.release_id if latest else None
            if release_id:
                effective = service.effective_context(release_id)

        if effective is None or effective.release.project_id != project_id:
            return self._warning_selection("missing", "context_release_missing", current_hash, release_id)

        release_hash = effective.release.metadata.source_snapshot_hash
        if release_hash != current_hash:
            return self._warning_selection("stale", "context_release_stale", current_hash, release_id, release_hash)

        traceability = service.traceability(release_id)
        project_summary, direct_index = self._build_index(effective.effective_context, traceability)
        return ContextSelection(
            enabled=True,
            status="ready",
            release_id=release_id,
            source_snapshot_hash=current_hash,
            release_source_snapshot_hash=release_hash,
            project_summary=tuple(project_summary),
            direct_index=MappingProxyType({key: tuple(value) for key, value in direct_index.items()}),
            character_budget=self.character_budget,
        )

    def _get_context_service(self) -> Any:
        if self.context_service is None:
            self.context_service = ContextService(ContextRepository(PROJECTS_DB_PATH))
        return self.context_service

    def _build_snapshot(self, files_data: Iterable[Mapping[str, Any]]) -> SourceSnapshot:
        # The injected service is intentionally used when tests or callers need
        # to prove the exact snapshot contract without opening a database.
        if hasattr(self.snapshot_service, "build_snapshot") and not isinstance(self.snapshot_service, SourceSnapshotService):
            return self.snapshot_service.build_snapshot(files_data)
        return build_translation_source_snapshot(files_data, self.snapshot_service)

    def _warning_selection(
        self,
        status: str,
        code: str,
        current_hash: str,
        release_id: str | None,
        release_hash: str | None = None,
    ) -> ContextSelection:
        warning = {
            "type": "context_release_warning",
            "code": code,
            "message": f"Project context was not injected: {code}.",
            "allowed_actions": list(CONTEXT_NEXT_ACTIONS),
        }
        return ContextSelection(
            enabled=True,
            status=status,
            release_id=None,
            source_snapshot_hash=current_hash,
            release_source_snapshot_hash=release_hash,
            character_budget=self.character_budget,
            warning=warning,
        )

    @staticmethod
    def _build_index(
        effective_context: Mapping[str, Mapping[str, Any]],
        traceability: Iterable[Mapping[str, Any]],
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
        project_summary.sort(key=lambda item: str(item["context_key"]))
        for items in direct_index.values():
            items.sort(key=lambda item: str(item["context_key"]))
        return project_summary, direct_index
