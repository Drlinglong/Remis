"""UTF-8 source parsing for the unified context extraction workflow."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from scripts.core.file_parser import extract_translatable_content
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.source_snapshot_service import (
    SourceFileInput,
    SourceItemInput,
    SourceSnapshot,
    SourceSnapshotService,
    normalize_relative_path,
)


@dataclass(frozen=True)
class ParsedSourceFile:
    path: Path
    relative_path: str
    content: bytes
    items: tuple[SourceItem, ...]

    def snapshot_input(self) -> SourceFileInput:
        return SourceFileInput(
            relative_path=self.relative_path,
            content=self.content,
            items=tuple(
                SourceItemInput(
                    key=item.item_key,
                    source_order=item.source_order,
                    source_text=item.source_text,
                )
                for item in self.items
            ),
        )


class ContextSourceParser:
    """Parse eligible localization values without losing source order."""

    def parse_files(self, paths: Iterable[str], source_root: str) -> tuple[ParsedSourceFile, ...]:
        root = Path(source_root).resolve(strict=True)
        parsed = tuple(self.parse_file(Path(path), root) for path in paths)
        if len({item.relative_path for item in parsed}) != len(parsed):
            raise ValueError("Context source files must have unique relative paths")
        return tuple(sorted(parsed, key=lambda item: item.relative_path))

    def parse_file(self, path: Path, source_root: Path) -> ParsedSourceFile:
        resolved = path.resolve(strict=True)
        relative_path = normalize_relative_path(str(resolved.relative_to(source_root)))
        content = resolved.read_bytes()
        text = content.decode("utf-8-sig")
        if resolved.suffix.lower() == ".json":
            raw_items = self._parse_json(text)
        elif resolved.suffix.lower() == ".csv":
            raw_items = self._parse_csv(text)
        else:
            _, texts, key_map = extract_translatable_content(str(resolved))
            raw_items = [
                (key_map.get(index, {}).get("key_part"), value)
                for index, value in enumerate(texts)
            ]
        items = tuple(
            self._source_item(relative_path, order, key, value)
            for order, (key, value) in enumerate(raw_items)
            if str(value).strip()
        )
        return ParsedSourceFile(resolved, relative_path, content, items)

    @staticmethod
    def _parse_json(text: str) -> list[tuple[str, str]]:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            return []
        return [(str(key).strip(), str(value)) for key, value in payload.items()]

    @staticmethod
    def _parse_csv(text: str) -> list[tuple[str, str]]:
        values: list[tuple[str, str]] = []
        for row_index, row in enumerate(csv.reader(io.StringIO(text))):
            for column_index, value in enumerate(row):
                if value and value.strip():
                    values.append((f"row:{row_index}:column:{column_index}", value))
        return values

    @staticmethod
    def _source_item(
        relative_path: str, source_order: int, item_key: str | None, source_text: str
    ) -> SourceItem:
        normalized_key = str(item_key).strip() if item_key else None
        identity = json.dumps(
            [relative_path, normalized_key, source_order, source_text],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return SourceItem(
            source_item_id=f"source-item-{hashlib.sha256(identity).hexdigest()}",
            relative_path=relative_path,
            item_key=normalized_key,
            source_order=source_order,
            source_text=source_text,
            provenance="text_inferred",
        )

    @staticmethod
    def build_snapshot(
        parsed_files: Iterable[ParsedSourceFile],
        snapshot_service: SourceSnapshotService | None = None,
    ) -> SourceSnapshot:
        service = snapshot_service or SourceSnapshotService()
        return service.build_snapshot(item.snapshot_input() for item in parsed_files)
