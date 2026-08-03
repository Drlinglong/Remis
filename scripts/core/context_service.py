"""Application-facing domain service for draft and context release boundaries."""

from __future__ import annotations

from typing import Iterable

from scripts.core.repositories.context_repository import ContextRepository
from scripts.schemas.context import (
    ContextDraft,
    ContextDeliveryMembership,
    ContextRelease,
    ContextReleaseMetadata,
    EffectiveContext,
    GeneratedSynthesis,
    HumanOverride,
)


class ContextService:
    """Coordinate draft edits and one-way publication without model execution."""

    def __init__(self, repository: ContextRepository):
        self.repository = repository

    def start_draft(
        self, project_id: str, base_release_id: str | None = None
    ) -> ContextDraft:
        return self.repository.create_draft(project_id, base_release_id)

    def save_override(self, draft_id: str, override: HumanOverride) -> HumanOverride:
        """Persist a human edit as draft data; it never edits a release.

        Inherited overrides are replaced by the same target key. Removing an
        inherited override intentionally remains a future explicit tombstone
        or delete API; ``null`` is not treated as deletion.
        """
        return self.repository.save_draft_override(draft_id, override)

    def publish_draft(
        self,
        draft_id: str,
        metadata: ContextReleaseMetadata,
        aggregate_ids: Iterable[str],
        generated_syntheses: Iterable[GeneratedSynthesis],
        delivery_memberships: Iterable[ContextDeliveryMembership] = (),
    ) -> ContextRelease:
        """Create a new immutable release from current aggregate snapshots and draft edits."""
        return self.repository.publish_draft(
            draft_id,
            metadata,
            aggregate_ids,
            generated_syntheses,
            delivery_memberships,
        )

    def effective_context(self, release_id: str) -> EffectiveContext | None:
        return self.repository.get_effective_context(release_id)

    def list_releases(self, project_id: str) -> list[ContextRelease]:
        """Return published releases newest first for one project."""
        return self.repository.list_releases(project_id)

    def traceability(self, release_id: str) -> list[dict]:
        return self.repository.get_release_traceability(release_id)

    def delivery_memberships(self, release_id: str) -> list[dict]:
        return self.repository.list_release_delivery_memberships(release_id)
