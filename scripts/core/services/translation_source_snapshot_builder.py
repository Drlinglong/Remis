"""Build canonical and legacy-compatible snapshots from translation inventory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.core.services.source_snapshot_service import (
    SourceFileInput,
    SourceItemInput,
    SourceSnapshot,
    SourceSnapshotService,
)


def _source_items(
    file_data: Mapping[str, Any], *, trim_source_text: bool = False,
) -> list[SourceItemInput]:
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
            source_text=(
                str(entry.get("source", "")).strip()
                if trim_source_text else entry.get("source", "")
            ),
        )
        for index, entry in enumerate(entries)
        if entry.get("key") is not None
    ]


def _source_file_inputs(
    files_data: Iterable[Mapping[str, Any]], *, trim_source_text: bool = False,
) -> list[SourceFileInput]:
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
            content = "".join(original_lines) if original_lines is not None else ""
        inputs.append(SourceFileInput(
            relative_path=relative_path,
            content=content,
            items=tuple(_source_items(file_data, trim_source_text=trim_source_text)),
        ))
    return inputs


def build_translation_source_snapshot(
    files_data: Iterable[Mapping[str, Any]],
    snapshot_service: SourceSnapshotService | None = None,
) -> SourceSnapshot:
    """Build the canonical snapshot from the exact translation source values."""

    return (snapshot_service or SourceSnapshotService()).build_snapshot(
        _source_file_inputs(files_data),
    )


def build_legacy_trimmed_source_snapshot(
    files_data: Iterable[Mapping[str, Any]],
    snapshot_service: SourceSnapshotService | None = None,
) -> SourceSnapshot:
    """Reproduce archives made when Pydantic stripped source-value whitespace.

    This compatibility snapshot still hashes the current raw file bytes, paths,
    keys, order, and every value. It differs only in the historical trimming of
    leading and trailing whitespace from individual localization values.
    """

    return (snapshot_service or SourceSnapshotService()).build_snapshot(
        _source_file_inputs(files_data, trim_source_text=True),
    )
