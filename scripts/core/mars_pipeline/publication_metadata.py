"""Apply reviewed text and cover overrides to a source-copy Mod package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.core.mars_pipeline.cover_asset import CoverAssetError, read_cover_snapshot
from scripts.core.mars_pipeline.delivery_metadata import (
    DeliveryMetadataError,
    _override_source_copy_metadata,
    _prefix_source_copy_title,
)


_TEXT_FIELDS = {"title", "description", "short_description", "last_changes"}


class PublicationMetadataError(ValueError):
    """Raised for malformed or stale source-copy publication metadata."""


def prepare_source_copy_publication(
    metadata_raw: bytes,
    source_files: list[tuple[str, Path, int, str]],
    delivery_id: str,
    overrides: dict[str, Any] | None,
) -> tuple[bytes, dict[str, bytes]]:
    """Apply metadata overrides and return any validated generated cover asset."""
    values = {key: value for key, value in dict(overrides or {}).items() if value is not None}
    allowed = _TEXT_FIELDS | {"cover_asset_path", "cover_asset_sha256"}
    if values.keys() - allowed:
        raise PublicationMetadataError("Publication metadata contains unsupported fields.")
    cover_path = values.pop("cover_asset_path", None)
    cover_hash = values.pop("cover_asset_sha256", None)
    if (cover_path is None) != (cover_hash is None):
        raise PublicationMetadataError("Cover image path and SHA-256 snapshot must be supplied together.")
    if any(not isinstance(value, str) or "\x00" in value for value in values.values()):
        raise PublicationMetadataError("Publication text fields must be valid strings.")
    fields = {key: value for key, value in values.items() if value is not None}
    try:
        metadata = metadata_raw
        if "title" not in fields:
            metadata = _prefix_source_copy_title(metadata)
        cover_files: dict[str, bytes] = {}
        if cover_path is not None:
            snapshot = read_cover_snapshot(str(cover_path), str(cover_hash))
            relative = f"Images/RemisCover-{snapshot['sha256'][:12]}{snapshot['extension']}"
            existing = {row[0].casefold() for row in source_files}
            if relative.casefold() in existing:
                raise PublicationMetadataError("Generated cover path conflicts with an existing Mod asset.")
            cover_files[relative] = snapshot["data"]
            fields["image"] = f"Mod/{delivery_id}/{relative}"
        metadata = _override_source_copy_metadata(metadata, fields)
    except (CoverAssetError, DeliveryMetadataError) as error:
        raise PublicationMetadataError(str(error)) from error
    return metadata, cover_files
