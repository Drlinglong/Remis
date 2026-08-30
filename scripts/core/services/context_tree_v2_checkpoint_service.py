"""Durable v2 checkpoint adapter over the existing analysis batch store."""

from __future__ import annotations

from typing import Any, Sequence

from scripts.core.services.context_tree_v2_contract import (
    ContextTreeV2Extraction,
    TreeCatalogResult,
)
from scripts.schemas.context_tree_v2_entity_digest import EntityDigestRunResult


class ContextTreeV2CheckpointService:
    def __init__(self, repository: Any | None) -> None:
        self.repository = repository

    def restore_extraction(
        self, run: Any | None, index: int, source_ids: Sequence[str],
    ) -> ContextTreeV2Extraction | None:
        payload = self._restore(run, "extraction", index, source_ids)
        return (
            ContextTreeV2Extraction.model_validate(payload["tree_v2_extraction"])
            if payload and "tree_v2_extraction" in payload else None
        )

    def save_extraction(
        self, run: Any | None, index: int, source_ids: Sequence[str], result: Any,
    ) -> None:
        self._save(
            run, "extraction", index, source_ids,
            {"tree_v2_extraction": result.model_dump(mode="json")},
        )

    def restore_catalog(
        self, run: Any | None, source_ids: Sequence[str],
    ) -> TreeCatalogResult | None:
        payload = self._restore(run, "aggregation", 0, source_ids)
        return (
            TreeCatalogResult.model_validate(payload["tree_v2_catalog"])
            if payload and "tree_v2_catalog" in payload else None
        )

    def save_catalog(
        self, run: Any | None, source_ids: Sequence[str], result: Any,
    ) -> None:
        self._save(
            run, "aggregation", 0, source_ids,
            {"tree_v2_catalog": result.model_dump(mode="json")},
        )

    def restore_digests(
        self, run: Any | None, source_ids: Sequence[str],
    ) -> EntityDigestRunResult | None:
        payload = self._restore(run, "synthesis", 0, source_ids)
        return (
            EntityDigestRunResult.model_validate(payload["tree_v2_entity_digests"])
            if payload and "tree_v2_entity_digests" in payload else None
        )

    def save_digests(
        self, run: Any | None, source_ids: Sequence[str], result: Any,
    ) -> None:
        self._save(
            run, "synthesis", 0, source_ids,
            {"tree_v2_entity_digests": result.model_dump(mode="json")},
        )

    def _restore(
        self, run: Any | None, phase: str, index: int, source_ids: Sequence[str],
    ) -> dict[str, Any] | None:
        if self.repository is None or run is None:
            return None
        saved = self.repository.get_batch(run.run_id, phase, index)
        if saved is None or saved.status != "succeeded":
            return None
        expected = tuple(dict.fromkeys(str(item) for item in source_ids))
        if saved.source_item_ids != expected:
            raise ValueError(f"Saved tree v2 {phase} batch does not match current evidence")
        return saved.payload

    def _save(
        self, run: Any | None, phase: str, index: int,
        source_ids: Sequence[str], payload: dict[str, Any],
    ) -> None:
        if self.repository is None or run is None:
            return
        self.repository.save_batch(run.run_id, phase, index, source_ids, payload)


__all__ = ["ContextTreeV2CheckpointService"]
