"""Build the base CSV layer for a prepared Mars text-only package."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scripts.core.services import mars_translation_package as package
from scripts.core.mars_pipeline.delivery_metadata import DeliveryMetadataError, _text_only_metadata_items
from scripts.core.mars_pipeline.publication_metadata import (
    PublicationMetadataError, prepare_text_only_publication,
)


def _render_files(entries: dict[str, dict[str, Any]], localized: dict[str, dict[str, str]],
                  selected: set[str], source_id: str, title: str,
                  conditional_loader: bool) -> tuple[dict[str, bytes], str, set[str]]:
    from scripts.core.mars_pipeline import delivery
    output_id = "RemisText" + hashlib.sha256(
        f"remis-text-only\0{source_id}".encode("utf-8")
    ).hexdigest()[:12]
    registrations = []
    files = {}
    for code, values in localized.items():
        language = package._language(code)
        relative = f"{delivery.OUTPUT_SUBDIR}/{language}/RemisLua.csv"
        files[relative] = delivery._entry_rows(entries, values, selected).encode("utf-8")
        registrations.append({"language": language, "path": relative})
    try:
        metadata, items = _text_only_metadata_items(
            output_id, source_id, f"[Remis text] {title}", registrations, conditional_loader
        )
    except DeliveryMetadataError as error:
        raise delivery.MarsDeliveryError(str(error)) from error
    files["metadata.lua"] = metadata.encode("utf-8")
    files["items.lua"] = items.encode("utf-8")
    return files, output_id, selected


def build_plan(
    source: Path, fingerprint: str, source_id: str, manifest: dict[str, Any],
    entries: dict[str, dict[str, Any]], translations: dict[str, dict[str, str]],
    metadata_overrides: dict[str, Any] | None, conditional_loader: bool,
) -> dict[str, Any]:
    from scripts.core.mars_pipeline import delivery
    approved_raw = manifest.get("approved_ids")
    approved = {str(value) for value in approved_raw} if isinstance(approved_raw, list) else set()
    pending = []
    if not isinstance(approved_raw, list):
        pending.append({"id": "", "reason": "No explicit text-only approved_ids snapshot is recorded."})
    eligible = {key for key, row in entries.items() if row.get("kind") == "existing_t"}
    selected = eligible & approved
    if not selected:
        pending.append({"id": "", "reason": "No approved existing_t manifest IDs are available."})
    localized = delivery._language_tables(translations, entries, selected)
    output_id = "RemisText" + hashlib.sha256(
        f"remis-text-only\0{source_id}".encode("utf-8")
    ).hexdigest()[:12]
    generated: dict[str, bytes] = {}
    if selected:
        generated, output_id, selected = _render_files(
            entries, localized, selected, source_id,
            str(package.read_source_metadata(source).get("title") or source_id), conditional_loader,
        )
        try:
            metadata, cover_files = prepare_text_only_publication(
                generated.pop("metadata.lua"), output_id, metadata_overrides
            )
        except PublicationMetadataError as error:
            raise delivery.MarsDeliveryError(str(error)) from error
        generated["metadata.lua"] = metadata
        generated.update(cover_files)
    warnings = [{"id": key, "reason": "This hardcoded or unapproved entry is not covered by text-only delivery."}
                for key in sorted(set(entries) - selected, key=int)]
    return {"mode": "text_only", "source_fingerprint": fingerprint, "source_id": source_id,
            "entries": entries, "selected_ids": selected, "generated": generated,
            "selected_ids_by_language": {code: set(selected) for code in translations},
            "pending": pending, "warnings": warnings, "complete": not pending,
            "profile": "text_only_existing_csv-v1", "runtime_verified": False, "mod_id": output_id}
