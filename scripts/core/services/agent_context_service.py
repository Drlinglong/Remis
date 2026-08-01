"""Read-only Agent projections over published Mod Context releases."""

from __future__ import annotations

import ntpath
import re
from typing import Any

from scripts.core.context_service import ContextService
from scripts.core.repositories.context_repository import ContextRepository
from scripts.schemas.agent_context import (
    AgentContextAggregate,
    AgentContextContribution,
    AgentContextEffectiveResponse,
    AgentContextLatestReleaseResponse,
    AgentContextReleaseMetadata,
    AgentContextSelection,
    AgentContextSourceEvidence,
    AgentContextSynthesis,
    AgentContextTraceabilityItem,
    AgentContextTraceabilityResponse,
)
from scripts.schemas.context import ContextRelease


MAX_CONTEXT_ITEMS = 250
MAX_OBJECT_ITEMS = 50
MAX_LIST_ITEMS = 50
MAX_TEXT_LENGTH = 2000
MAX_SOURCE_REFS = 200
MAX_TRACEABILITY_ITEMS = 20
MAX_CONTRIBUTIONS = 50
MAX_SYNTHESES = 20
MAX_SOURCE_EVIDENCE = 50
_SKIP = object()
_SECRET_MARKERS = {
    "api_key",
    "api_token",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}
_PATH_KEYS = {
    "db_path",
    "file_path",
    "folder_path",
    "output_path",
    "path",
    "source_file",
    "source_path",
}
_SENSITIVE_TEXT = re.compile(
    r"(?i)\b(?:api[_-]?key|api[_-]?token|authorization)\s*[:=]\s*"
    r"(?:bearer\s+)?[^\s,;\"']+"
)


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def _is_secret_key(value: Any) -> bool:
    normalized = _normalized_key(value)
    return normalized in _SECRET_MARKERS or normalized.endswith("_secret") or normalized.endswith(
        "_token"
    )


def _safe_text(value: Any) -> str:
    text = str(value or "")
    return _SENSITIVE_TEXT.sub("[REDACTED]", text)[:MAX_TEXT_LENGTH]


def _bounded_value(value: Any, depth: int = 0) -> Any:
    """Copy JSON-like data while dropping secret/path fields and limiting size."""
    if depth >= 4:
        return _SKIP
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, nested in list(value.items())[:MAX_OBJECT_ITEMS]:
            if _is_secret_key(key) or _normalized_key(key) in _PATH_KEYS:
                continue
            bounded = _bounded_value(nested, depth + 1)
            if bounded is not _SKIP:
                result[str(key)[:120]] = bounded
        return result
    if isinstance(value, list):
        result = []
        for nested in value[:MAX_LIST_ITEMS]:
            bounded = _bounded_value(nested, depth + 1)
            if bounded is not _SKIP:
                result.append(bounded)
        return result
    if isinstance(value, str):
        return _safe_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_TEXT_LENGTH]


def _bounded_mapping(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, nested in sorted(value.items(), key=lambda item: str(item[0]))[:MAX_CONTEXT_ITEMS]:
        bounded = _bounded_value(nested)
        result[str(key)[:200]] = bounded if isinstance(bounded, dict) else {}
    return result


def _safe_source_ref(value: Any) -> str | None:
    normalized = str(value or "").strip().replace("\\", "/")
    if not normalized or ntpath.isabs(normalized) or normalized.startswith("//"):
        return None
    return normalized[:MAX_TEXT_LENGTH]


def _release_source_refs(release: ContextRelease) -> list[str]:
    metadata = release.metadata
    candidates: list[Any] = []
    scope = metadata.analysis_scope
    if isinstance(scope, dict):
        candidates.extend(scope.get("files") or [])
    config = metadata.analysis_config
    if isinstance(config, dict):
        candidates.extend(
            item.get("relative_path")
            for item in config.get("source_items") or []
            if isinstance(item, dict)
        )
    refs: list[str] = []
    for candidate in candidates:
        safe_ref = _safe_source_ref(candidate)
        if safe_ref and safe_ref not in refs:
            refs.append(safe_ref)
        if len(refs) >= MAX_SOURCE_REFS:
            break
    return refs


class AgentContextService:
    """Project published context data into a bounded Agent-safe read model."""

    def __init__(
        self,
        repository: ContextRepository,
        context_service: ContextService | None = None,
    ):
        self.repository = repository
        self.context_service = context_service or ContextService(repository)

    def latest_release(self, project_id: str) -> AgentContextLatestReleaseResponse | None:
        releases = self.repository.list_releases(project_id)
        if not releases:
            return None
        release = self._release_metadata(releases[0])
        return AgentContextLatestReleaseResponse(
            **release.model_dump(),
            allowed_actions=["read_effective_context", "read_context_traceability"],
            links={
                "effective": f"/api/agent/context/releases/{release.release_id}/effective",
                "traceability": (
                    f"/api/agent/context/releases/{release.release_id}/traceability"
                    "?aggregate_key={aggregate_key}&context_key={context_key}"
                ),
            },
        )

    def effective_context(self, release_id: str) -> AgentContextEffectiveResponse | None:
        effective = self.context_service.effective_context(release_id)
        if effective is None:
            return None
        release = self._release_metadata(effective.release)
        return AgentContextEffectiveResponse(
            release=release,
            generated_synthesis=_bounded_mapping(effective.generated_synthesis),
            human_overrides=_bounded_mapping(effective.human_overrides),
            effective_context=_bounded_mapping(effective.effective_context),
            allowed_actions=["read_context_traceability"],
            links={
                "traceability": (
                    f"/api/agent/context/releases/{release_id}/traceability"
                    "?aggregate_key={aggregate_key}&context_key={context_key}"
                )
            },
        )

    def traceability(
        self,
        release_id: str,
        *,
        aggregate_key: str | None,
        context_key: str | None,
    ) -> AgentContextTraceabilityResponse | None:
        release = self.repository.get_release(release_id)
        if release is None:
            return None
        selected = []
        truncated = False
        for item in self.context_service.traceability(release_id):
            aggregate = item.get("aggregate") or {}
            if aggregate_key and aggregate.get("aggregate_key") != aggregate_key:
                continue
            syntheses = [
                synthesis
                for synthesis in item.get("syntheses") or []
                if not context_key or synthesis.get("context_key") == context_key
            ]
            if context_key and not syntheses:
                continue
            if len(selected) >= MAX_TRACEABILITY_ITEMS:
                truncated = True
                continue
            selected.append({**item, "syntheses": syntheses})
            truncated = truncated or len(item.get("contributions") or []) > MAX_CONTRIBUTIONS
            truncated = truncated or len(syntheses) > MAX_SYNTHESES
        if not selected:
            return None
        items = [self._traceability_item(item) for item in selected]
        return AgentContextTraceabilityResponse(
            release=self._release_metadata(release),
            selection=AgentContextSelection(
                aggregate_key=aggregate_key,
                context_key=context_key,
            ),
            traceability=items,
            truncated=truncated,
            allowed_actions=[],
            links={
                "effective": f"/api/agent/context/releases/{release_id}/effective",
            },
        )

    @staticmethod
    def _release_metadata(release: ContextRelease) -> AgentContextReleaseMetadata:
        metadata = release.metadata
        scope = metadata.analysis_scope if isinstance(metadata.analysis_scope, dict) else {}
        safe_scope: dict[str, Any] = {}
        if isinstance(scope.get("mode"), str):
            safe_scope["mode"] = scope["mode"][:120]
        safe_scope["source_file_count"] = len(_release_source_refs(release))
        return AgentContextReleaseMetadata(
            release_id=release.release_id,
            project_id=release.project_id,
            source_snapshot_hash=metadata.source_snapshot_hash,
            analysis_scope=safe_scope,
            schema_version=metadata.schema_version,
            prompt_version=metadata.prompt_version,
            provider_id=metadata.provider_id,
            model_id=metadata.model_id,
            created_at=metadata.created_at,
            parent_release_id=metadata.parent_release_id,
            upstream_version=metadata.upstream_version,
            source_refs=_release_source_refs(release),
        )

    def _traceability_item(self, item: dict[str, Any]) -> AgentContextTraceabilityItem:
        aggregate = item.get("aggregate") or {}
        raw_contributions = item.get("contributions") or []
        contributions: list[AgentContextContribution] = []
        evidence: list[AgentContextSourceEvidence] = []
        seen_source_ids: set[str] = set()
        for raw in raw_contributions[:MAX_CONTRIBUTIONS]:
            contribution = raw.get("contribution") or {}
            source = raw.get("source_item") or {}
            source_id = str(
                contribution.get("source_item_id")
                or source.get("source_item_id")
                or ""
            )
            if not source_id:
                continue
            contributions.append(
                AgentContextContribution(
                    contribution_id=str(contribution.get("contribution_id") or ""),
                    source_item_id=source_id,
                    contribution_type=str(contribution.get("contribution_type") or ""),
                    subject_key=str(contribution.get("subject_key") or ""),
                    provenance=str(contribution.get("provenance") or ""),
                    payload=_bounded_value(contribution.get("payload") or {}) or {},
                )
            )
            if source_id not in seen_source_ids and len(evidence) < MAX_SOURCE_EVIDENCE:
                safe_ref = _safe_source_ref(source.get("source_ref"))
                if safe_ref:
                    evidence.append(
                        AgentContextSourceEvidence(
                            source_item_id=source_id,
                            source_type=str(source.get("source_type") or ""),
                            source_ref=safe_ref,
                            content_excerpt=_safe_text(source.get("content")),
                            content_hash=str(source.get("content_hash") or ""),
                            created_at=str(source.get("created_at") or ""),
                        )
                    )
                    seen_source_ids.add(source_id)
        syntheses = [
            AgentContextSynthesis(
                synthesis_id=str(synthesis.get("synthesis_id") or ""),
                context_key=str(synthesis.get("context_key") or ""),
                content=_bounded_value(synthesis.get("content") or {}) or {},
            )
            for synthesis in (item.get("syntheses") or [])[:MAX_SYNTHESES]
        ]
        return AgentContextTraceabilityItem(
            aggregate=AgentContextAggregate(
                aggregate_id=str(aggregate.get("aggregate_id") or ""),
                aggregate_type=str(aggregate.get("aggregate_type") or ""),
                aggregate_key=str(aggregate.get("aggregate_key") or ""),
                payload=_bounded_value(aggregate.get("payload") or {}) or {},
            ),
            contributions=contributions,
            syntheses=syntheses,
            source_evidence=evidence,
        )
