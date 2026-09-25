"""Apply a project-owned publication binding after removing source platform IDs."""
from __future__ import annotations

import re

from scripts.core.mars_pipeline.delivery_metadata import (
    DeliveryMetadataError, _override_source_copy_metadata,
)


def apply_publication_binding(metadata: bytes, binding: dict | None,
                              source_mod_id: str, output_mod_id: str) -> bytes:
    """Only an explicit bound identity may add a top-level Steam item ID."""
    if binding is None:
        return metadata
    if (binding.get("source_mod_id") != source_mod_id
            or binding.get("output_mod_id") != output_mod_id):
        raise DeliveryMetadataError("Publication binding belongs to another Mod identity.")
    if binding.get("status") == "unbound" and binding.get("steam_id") is None:
        return metadata
    steam_id = binding.get("steam_id")
    if (binding.get("status") != "bound" or not isinstance(steam_id, str)
            or not re.fullmatch(r"[1-9][0-9]{0,19}", steam_id)
            or int(steam_id) > 2**64 - 1):
        raise DeliveryMetadataError("Invalid publication binding; refusing to export as a new item.")
    return _override_source_copy_metadata(metadata, {"steam_id": steam_id})
