"""Persist source contributions and assemble immutable Context Release inputs."""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from typing import Any, Callable, Sequence

from scripts.core.neologism_extraction import AnalysisScope, StructuredNeologismExtraction
from scripts.core.context_local_units import LocalTextUnit
from scripts.core.services.context_source_parser import ParsedSourceFile
from scripts.core.services.source_snapshot_service import SourceChangeKind, SourceSnapshot
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextRelease,
    ContextReleaseFile,
    ContextReleaseLocalUnit,
    ContextReleaseManifest,
    ContextReleaseMetadata,
    ContextReleaseSourceItem,
    ContextSourceItem,
)


class ContextReleaseAssembler:
    """Own the evidence-to-aggregate persistence boundary for published archives."""

    def __init__(self, repository: Any):
        self.repository = repository

    def persist_sources(
        self, project_id: str, parsed_files: Sequence[ParsedSourceFile], snapshot_hash: str,
    ) -> dict[str, ContextSourceItem]:
        sources: dict[str, ContextSourceItem] = {}
        for source_file in parsed_files:
            for item in source_file.items:
                source = ContextSourceItem(
                    source_item_id=item.source_item_id,
                    project_id=project_id,
                    source_type="localization",
                    source_ref=f"{item.relative_path}::{item.source_order}:{item.item_key or ''}",
                    content=item.source_text,
                    content_hash=hashlib.sha256(item.source_text.encode("utf-8")).hexdigest(),
                    metadata={
                        "relative_path": item.relative_path,
                        "item_key": item.item_key,
                        "source_order": item.source_order,
                        "duplicate_key_ordinal": item.duplicate_key_ordinal,
                        "source_snapshot_hash": snapshot_hash,
                    },
                )
                existing = self.repository.get_source_item(source.source_item_id)
                if existing is None:
                    current = self.repository.create_source_item(source)
                elif existing.content_hash == source.content_hash:
                    current = existing
                else:
                    updater = getattr(self.repository, "upsert_source_item", None)
                    current = updater(source) if updater else source
                sources[source.source_item_id] = current
        return sources

    def persist_contributions(
        self,
        extractions: Sequence[StructuredNeologismExtraction],
        sources: dict[str, ContextSourceItem],
        aggregate_key_for_surface: Callable[[Any], str] | None = None,
    ) -> dict[str, ContextContribution]:
        contributions: dict[str, ContextContribution] = {}
        for extraction in extractions:
            for item in self._all_contributions(extraction):
                evidence = [entry.model_dump() for entry in item.evidence]
                source_item_id = evidence[0]["source_item_id"]
                if source_item_id not in sources:
                    raise ValueError("Extraction evidence referenced a source outside the parsed snapshot")
                subject_key = self._subject_key(item)
                if (
                    aggregate_key_for_surface is not None
                    and item.__class__.__name__ != "EventChainContribution"
                ):
                    governed_key = aggregate_key_for_surface(self._surface(item))
                    if governed_key:
                        subject_key = str(governed_key)
                contribution = ContextContribution(
                    contribution_id=str(uuid.uuid4()),
                    source_item_id=source_item_id,
                    contribution_type=self._contribution_type(item),
                    subject_key=subject_key,
                    payload={**item.model_dump(), "evidence": evidence},
                    provenance="text_inferred",
                )
                self.repository.create_contribution(contribution)
                contributions[contribution.contribution_id] = contribution
        return contributions

    @staticmethod
    def _all_contributions(extraction: StructuredNeologismExtraction) -> list[Any]:
        return [
            *extraction.terms,
            *extraction.entities,
            *extraction.facts,
            *extraction.events,
            *extraction.relationships,
        ]

    @staticmethod
    def _contribution_type(item: Any) -> str:
        return {
            "TermContribution": "mention",
            "EntityContribution": "mention",
            "FactContribution": "fact",
            "EventChainContribution": "event",
            "RelationshipContribution": "relationship",
        }[item.__class__.__name__]

    @staticmethod
    def _subject_key(item: Any) -> str:
        if item.__class__.__name__ == "EventChainContribution":
            return f"event:{item.chain_id.strip().casefold()}"
        value = getattr(item, "original", None) or getattr(item, "name", None) or getattr(item, "subject", None)
        return f"entity:{str(value).strip().casefold()}"

    @staticmethod
    def _surface(item: Any) -> str:
        return str(
            getattr(item, "original", None)
            or getattr(item, "name", None)
            or getattr(item, "subject", None)
            or ""
        )

    def build_aggregates(
        self,
        project_id: str,
        contributions: dict[str, ContextContribution],
        governance: Any | None = None,
    ) -> list[ContextAggregate]:
        governance_available = bool(getattr(governance, "available", False))
        groups: dict[str, list[str]] = defaultdict(list)
        for contribution in contributions.values():
            groups[contribution.subject_key].append(contribution.contribution_id)
        project_contribution_ids = [
            contribution.contribution_id
            for contribution in contributions.values()
            if governance is None
            or not governance_available
            or not governance.is_audit_only(contribution.subject_key)
        ]
        if project_contribution_ids:
            groups["project:summary"] = project_contribution_ids
        candidate_keys = (
            governance.candidate_aggregate_keys()
            if governance_available
            else frozenset()
        )
        aggregates = []
        for aggregate_key, contribution_ids in sorted(groups.items()):
            aggregate_type = "project" if aggregate_key == "project:summary" else (
                "event" if aggregate_key.startswith("event:") else "entity"
            )
            payload = {"active_contribution_count": len(contribution_ids)}
            if aggregate_key in candidate_keys:
                payload = governance.payload_for_aggregate(
                    aggregate_key, len(contribution_ids),
                )
            aggregates.append(ContextAggregate(
                aggregate_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"remis:{project_id}:{aggregate_key}")),
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_key=aggregate_key,
                payload=payload,
                contribution_ids=contribution_ids,
            ))
        return aggregates

    @staticmethod
    def aggregate_source_ids(
        aggregates: Sequence[ContextAggregate],
        contributions: dict[str, ContextContribution],
    ) -> list[str]:
        return list(dict.fromkeys(
            contributions[contribution_id].source_item_id
            for aggregate in aggregates
            for contribution_id in aggregate.contribution_ids
        ))

    @classmethod
    def metadata(
        cls,
        snapshot: SourceSnapshot,
        parsed_files: Sequence[ParsedSourceFile],
        diff: Any,
        parent: ContextRelease | None,
        api_provider: str,
        model_name: str | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
        description_language: str,
        chunk_config: dict[str, int],
        schema_version: str,
        prompt_version: str,
    ) -> ContextReleaseMetadata:
        config = dict(analysis_config or {})
        source_ids = {
            (
                source_file.relative_path,
                item.item_key,
                item.duplicate_key_ordinal,
                item.source_order,
            ): item.source_item_id
            for source_file in parsed_files
            for item in source_file.items
        }
        config.update({
            "reuse_strategy": "full_reextract",
            "description_language": description_language,
            "chunking": dict(chunk_config),
            "source_items": [
                {
                    "source_item_id": source_ids.get(
                        (
                            item.identity.relative_path,
                            item.identity.item_key,
                            item.identity.duplicate_key_ordinal,
                            item.source_order,
                        )
                    ),
                    "relative_path": item.identity.relative_path,
                    "item_key": item.identity.item_key,
                    "source_order": item.source_order,
                    "duplicate_key_ordinal": item.identity.duplicate_key_ordinal,
                    "source_sha256": item.source_sha256,
                }
                for item in snapshot.items
            ],
            "source_files": [
                {
                    "relative_path": item.relative_path,
                    "source_sha256": item.source_sha256,
                    "size": item.size,
                }
                for item in snapshot.files
            ],
            "affected_source_items": cls.affected_items(diff),
        })
        return ContextReleaseMetadata(
            source_snapshot_hash=snapshot.source_snapshot_hash,
            analysis_scope={
                "mode": AnalysisScope.NARRATIVE_CONTEXT.value,
                "files": [item.relative_path for item in parsed_files],
            },
            schema_version=schema_version,
            prompt_version=prompt_version,
            provider_id=api_provider,
            model_id=model_name or f"{api_provider}-default",
            analysis_config=config,
            parent_release_id=parent.release_id if parent else None,
            upstream_version=upstream_version,
        )

    @classmethod
    def build_manifest(
        cls,
        parsed_files: Sequence[ParsedSourceFile],
        snapshot: SourceSnapshot,
        local_units: Sequence[LocalTextUnit],
    ) -> ContextReleaseManifest:
        """Materialize the source/unit snapshot before publication."""

        snapshot_items = {
            (
                item.identity.relative_path,
                item.identity.item_key,
                item.identity.duplicate_key_ordinal,
                item.source_order,
            ): item
            for item in snapshot.items
        }
        source_items = []
        for source_file in parsed_files:
            for item in source_file.items:
                snapshot_item = snapshot_items[
                    (
                        item.relative_path,
                        item.item_key,
                        item.duplicate_key_ordinal,
                        item.source_order,
                    )
                ]
                content_hash = hashlib.sha256(item.source_text.encode("utf-8")).hexdigest()
                source_items.append(
                    ContextReleaseSourceItem(
                        source_item_id=item.source_item_id,
                        source_revision_id=cls._source_revision_id(
                            item.source_item_id, content_hash,
                        ),
                        relative_path=item.relative_path,
                        item_key=item.item_key,
                        duplicate_key_ordinal=item.duplicate_key_ordinal,
                        source_order=item.source_order,
                        source_ref=(
                            f"{item.relative_path}::{item.source_order}:{item.item_key or ''}"
                        ),
                        content=item.source_text,
                        content_hash=content_hash,
                    )
                )
                if snapshot_item.source_sha256 != content_hash:
                    raise ValueError("Release source item hash does not match its content")
        return ContextReleaseManifest(
            files=[
                ContextReleaseFile(
                    relative_path=item.relative_path,
                    source_sha256=item.source_sha256,
                    size=item.size,
                )
                for item in snapshot.files
            ],
            source_items=source_items,
            local_units=[
                ContextReleaseLocalUnit(
                    local_unit_id=unit.unit_id,
                    unit_key=unit.unit_key,
                    unit_order=index,
                    source_item_ids=[item.source_item_id for item in unit.items],
                )
                for index, unit in enumerate(local_units)
            ],
        )

    @staticmethod
    def _source_revision_id(source_item_id: str, content_hash: str) -> str:
        return hashlib.sha256(
            f"{source_item_id}\x00{content_hash}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def affected_items(diff: Any) -> list[dict[str, str]]:
        return [
            {
                "relative_path": item.identity.relative_path,
                "item_key": item.identity.item_key or "",
                "kind": item.kind.value,
            }
            for item in diff.item_changes
            if item.kind is not SourceChangeKind.UNCHANGED
        ]
