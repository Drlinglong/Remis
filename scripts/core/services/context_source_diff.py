"""Build source diffs from persisted release manifests with legacy fallback."""

from __future__ import annotations

from typing import Any

from scripts.core.services.source_snapshot_service import (
    SourceFileSnapshot,
    SourceItemIdentity,
    SourceItemSnapshot,
    SourceSnapshot,
)
from scripts.schemas.context import ContextRelease


def build_context_source_diff(
    repository: Any,
    parent: ContextRelease | None,
    current: SourceSnapshot,
) -> Any:
    """Use release-owned source rows before consulting legacy audit metadata."""

    if not parent:
        return current.diff(None)
    manifest_loader = getattr(repository, "get_release_manifest", None)
    manifest = manifest_loader(parent.release_id) if manifest_loader else None
    if manifest is not None:
        items = [
            SourceItemSnapshot(
                identity=SourceItemIdentity(
                    item.relative_path,
                    item.item_key,
                    item.duplicate_key_ordinal,
                ),
                source_sha256=item.content_hash,
                source_order=item.source_order,
            )
            for item in manifest.source_items
        ]
        items_by_path: dict[str, list[SourceItemSnapshot]] = {}
        for item in items:
            items_by_path.setdefault(item.identity.relative_path, []).append(item)
        previous = SourceSnapshot(
            files=tuple(
                SourceFileSnapshot(
                    relative_path=file.relative_path,
                    source_sha256=file.source_sha256,
                    size=file.size,
                    items=tuple(items_by_path.get(file.relative_path, ())),
                )
                for file in manifest.files
            ),
            source_snapshot_hash=parent.metadata.source_snapshot_hash,
            items=tuple(items),
        )
        return current.diff(previous)
    previous_items = tuple(
        SourceItemSnapshot(
            identity=SourceItemIdentity(
                item["relative_path"],
                item.get("item_key"),
                item.get("duplicate_key_ordinal", 0),
            ),
            source_sha256=item["source_sha256"],
            source_order=item.get("source_order"),
        )
        for item in parent.metadata.analysis_config.get("source_items", [])
    )
    previous = SourceSnapshot(
        files=(),
        source_snapshot_hash=parent.metadata.source_snapshot_hash,
        items=previous_items,
    )
    return current.diff(previous)
