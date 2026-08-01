"""Immutable source snapshot and diff contracts shared by Remis workflows.

The service deliberately stops at source identity and content fingerprints. It
does not decide whether a translation should be retried, reused, or written.
Those are workflow policies owned by the monitor and incremental translation
integrations.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional, Union


PathLike = Union[str, Path]
Content = Union[str, bytes]


class SourceChangeKind(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


def normalize_relative_path(value: PathLike) -> str:
    """Return one stable POSIX relative path representation.

    Source identities must not depend on whether a caller came from a Windows
    file scanner or a POSIX-oriented archive reader. Absolute paths and paths
    escaping the source root are rejected because they cannot be project-local
    identities.
    """

    raw = str(value).strip().replace("\\", "/")
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        raise ValueError(f"Source path must be relative: {value!r}")
    normalized = posixpath.normpath(raw)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise ValueError(f"Source path must stay within the project: {value!r}")
    return normalized


def normalize_source_key(value: Optional[str]) -> Optional[str]:
    """Normalize archive/parser key spelling without changing its meaning."""

    if value is None:
        return None
    normalized = str(value).strip()
    if normalized.endswith(":"):
        normalized = normalized[:-1].strip()
    return normalized or None


def sha256_bytes(value: bytes) -> str:
    """Hash bytes using the same SHA-256 algorithm as file snapshots."""

    return hashlib.sha256(value).hexdigest()


def sha256_file(path: PathLike) -> str:
    """Hash a file in bounded chunks so large localization files stay cheap."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SourceItemIdentity:
    relative_path: str
    item_key: Optional[str] = None
    source_order: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "relative_path", normalize_relative_path(self.relative_path))
        object.__setattr__(self, "item_key", normalize_source_key(self.item_key))
        if self.source_order is not None and self.source_order < 0:
            raise ValueError("Source order cannot be negative")

    @property
    def canonical(self) -> str:
        """A length-delimited identity safe for deterministic sorting/hashing."""

        key = self.item_key or ""
        if self.source_order is None:
            return f"{len(self.relative_path)}:{self.relative_path}:{len(key)}:{key}"
        return f"{len(self.relative_path)}:{self.relative_path}:{len(key)}:{key}:{self.source_order}"


@dataclass(frozen=True)
class SourceItemInput:
    """One parsed source item supplied by a scanner or archive adapter."""

    key: Optional[str]
    source_text: Optional[Content] = None
    source_sha256: Optional[str] = None
    source_order: Optional[int] = None

    def __post_init__(self) -> None:
        if self.source_text is None and self.source_sha256 is None:
            raise ValueError("Source item requires source_text or source_sha256")
        if self.source_text is not None and self.source_sha256 is not None:
            raise ValueError("Provide source_text or source_sha256, not both")


@dataclass(frozen=True)
class SourceFileInput:
    """File material for snapshot construction.

    A caller may provide content, a filesystem path, or a precomputed SHA-256.
    The last form lets an existing monitor reuse its verified file metadata
    without rereading the file.
    """

    relative_path: str
    content: Optional[Content] = None
    path: Optional[PathLike] = None
    source_sha256: Optional[str] = None
    size: Optional[int] = None
    items: tuple[SourceItemInput, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relative_path", normalize_relative_path(self.relative_path))
        if self.content is not None and (self.path is not None or self.source_sha256 is not None):
            raise ValueError("Provide content, path, or source_sha256, not multiple")
        if self.content is None and self.path is None and self.source_sha256 is None:
            raise ValueError("Source file requires content, path, or source_sha256")
        if self.size is not None and self.size < 0:
            raise ValueError("Source file size cannot be negative")
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True)
class SourceItemSnapshot:
    identity: SourceItemIdentity
    source_sha256: str


@dataclass(frozen=True)
class SourceFileSnapshot:
    relative_path: str
    source_sha256: str
    size: int
    items: tuple[SourceItemSnapshot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relative_path", normalize_relative_path(self.relative_path))
        if self.size < 0:
            raise ValueError("Source file size cannot be negative")
        object.__setattr__(
            self,
            "items",
            tuple(sorted(self.items, key=SourceSnapshotService._item_sort_key)),
        )


@dataclass(frozen=True)
class SourceSnapshot:
    files: tuple[SourceFileSnapshot, ...]
    source_snapshot_hash: str
    items: tuple[SourceItemSnapshot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        sorted_files = tuple(sorted(self.files, key=lambda item: item.relative_path))
        object.__setattr__(self, "files", sorted_files)
        object.__setattr__(
            self,
            "items",
            tuple(sorted(self.items, key=SourceSnapshotService._item_sort_key)),
        )

    def diff(self, previous: Optional["SourceSnapshot"]) -> "SourceSnapshotDiff":
        return SourceSnapshotService.diff(previous, self)


@dataclass(frozen=True)
class SourceFileChange:
    relative_path: str
    kind: SourceChangeKind
    current: Optional[SourceFileSnapshot] = None
    previous: Optional[SourceFileSnapshot] = None


@dataclass(frozen=True)
class SourceItemChange:
    identity: SourceItemIdentity
    kind: SourceChangeKind
    current: Optional[SourceItemSnapshot] = None
    previous: Optional[SourceItemSnapshot] = None


@dataclass(frozen=True)
class SourceSnapshotDiff:
    previous_hash: Optional[str]
    current_hash: str
    file_changes: tuple[SourceFileChange, ...]
    item_changes: tuple[SourceItemChange, ...]

    @property
    def has_changes(self) -> bool:
        return any(change.kind != SourceChangeKind.UNCHANGED for change in self.file_changes) or any(
            change.kind != SourceChangeKind.UNCHANGED for change in self.item_changes
        )

    @property
    def files(self) -> tuple[SourceFileChange, ...]:
        return self.file_changes

    @property
    def items(self) -> tuple[SourceItemChange, ...]:
        return self.item_changes


class SourceSnapshotService:
    """Build deterministic source snapshots and compare two snapshots."""

    def build_snapshot(self, files: Iterable[SourceFileInput]) -> SourceSnapshot:
        file_snapshots = tuple(self._build_file_snapshot(file_input) for file_input in files)
        self._ensure_unique_paths(file_snapshots)
        ordered_files = tuple(sorted(file_snapshots, key=lambda item: item.relative_path))
        items = tuple(
            item
            for source_file in ordered_files
            for item in source_file.items
        )
        self._ensure_unique_items(items)
        return SourceSnapshot(
            files=ordered_files,
            source_snapshot_hash=self._project_hash(ordered_files),
            items=items,
        )

    @staticmethod
    def diff(
        previous: Optional[SourceSnapshot],
        current: SourceSnapshot,
    ) -> SourceSnapshotDiff:
        previous_files = {item.relative_path: item for item in previous.files} if previous else {}
        current_files = {item.relative_path: item for item in current.files}
        file_changes = tuple(
            SourceFileChange(
                relative_path=relative_path,
                kind=SourceSnapshotService._classify_file(
                    previous_files.get(relative_path), current_files.get(relative_path)
                ),
                current=current_files.get(relative_path),
                previous=previous_files.get(relative_path),
            )
            for relative_path in sorted(previous_files.keys() | current_files.keys())
        )

        previous_items = {
            item.identity: item for item in (previous.items if previous else ())
        }
        current_items = {item.identity: item for item in current.items}
        item_changes = tuple(
            SourceItemChange(
                identity=identity,
                kind=SourceSnapshotService._classify_item(
                    previous_items.get(identity), current_items.get(identity)
                ),
                current=current_items.get(identity),
                previous=previous_items.get(identity),
            )
            for identity in sorted(
                previous_items.keys() | current_items.keys(),
                key=SourceSnapshotService._identity_sort_key,
            )
        )
        return SourceSnapshotDiff(
            previous_hash=previous.source_snapshot_hash if previous else None,
            current_hash=current.source_snapshot_hash,
            file_changes=file_changes,
            item_changes=item_changes,
        )

    def _build_file_snapshot(self, file_input: SourceFileInput) -> SourceFileSnapshot:
        source_sha256, size = self._file_fingerprint(file_input)
        items = tuple(
            SourceItemSnapshot(
                identity=SourceItemIdentity(
                    file_input.relative_path, item.key, item.source_order
                ),
                source_sha256=self._item_fingerprint(item),
            )
            for item in file_input.items
        )
        return SourceFileSnapshot(
            relative_path=file_input.relative_path,
            source_sha256=source_sha256,
            size=size,
            items=items,
        )

    @staticmethod
    def _file_fingerprint(file_input: SourceFileInput) -> tuple[str, int]:
        if file_input.content is not None:
            content = (
                file_input.content
                if isinstance(file_input.content, bytes)
                else file_input.content.encode("utf-8")
            )
            return sha256_bytes(content), len(content)
        if file_input.path is not None:
            path = Path(file_input.path)
            return sha256_file(path), path.stat().st_size
        return file_input.source_sha256 or "", file_input.size or 0

    @staticmethod
    def _item_fingerprint(item: SourceItemInput) -> str:
        if item.source_text is not None:
            content = (
                item.source_text
                if isinstance(item.source_text, bytes)
                else item.source_text.encode("utf-8")
            )
            return sha256_bytes(content)
        return item.source_sha256 or ""

    @staticmethod
    def _project_hash(files: tuple[SourceFileSnapshot, ...]) -> str:
        material = [
            {
                "relative_path": item.relative_path,
                "sha256": item.source_sha256,
                "items": [
                    {
                        "identity": source_item.identity.canonical,
                        "sha256": source_item.source_sha256,
                    }
                    for source_item in item.items
                ],
            }
            for item in files
        ]
        encoded = json.dumps(material, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return sha256_bytes(encoded)

    @staticmethod
    def _classify_file(
        previous: Optional[SourceFileSnapshot], current: Optional[SourceFileSnapshot]
    ) -> SourceChangeKind:
        if previous is None:
            return SourceChangeKind.ADDED
        if current is None:
            return SourceChangeKind.DELETED
        if previous.source_sha256 != current.source_sha256:
            return SourceChangeKind.MODIFIED
        return SourceChangeKind.UNCHANGED

    @staticmethod
    def _classify_item(
        previous: Optional[SourceItemSnapshot], current: Optional[SourceItemSnapshot]
    ) -> SourceChangeKind:
        if previous is None:
            return SourceChangeKind.ADDED
        if current is None:
            return SourceChangeKind.DELETED
        if previous.source_sha256 != current.source_sha256:
            return SourceChangeKind.MODIFIED
        return SourceChangeKind.UNCHANGED

    @staticmethod
    def _ensure_unique_paths(files: tuple[SourceFileSnapshot, ...]) -> None:
        paths = [item.relative_path for item in files]
        if len(paths) != len(set(paths)):
            raise ValueError("A source snapshot cannot contain duplicate file paths")

    @staticmethod
    def _ensure_unique_items(items: tuple[SourceItemSnapshot, ...]) -> None:
        identities = [item.identity for item in items]
        if len(identities) != len(set(identities)):
            raise ValueError("A source snapshot cannot contain duplicate item identities")

    @staticmethod
    def _identity_sort_key(identity: SourceItemIdentity) -> tuple[str, str, int]:
        return identity.relative_path, identity.item_key or "", identity.source_order or -1

    @staticmethod
    def _item_sort_key(item: SourceItemSnapshot) -> tuple[str, str, int]:
        return SourceSnapshotService._identity_sort_key(item.identity)
