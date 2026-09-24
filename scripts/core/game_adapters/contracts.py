"""Small, source-preserving contracts for local game resources.

Game versions describe discovery context, never the identity of a translation.
Adapters only read and render. The workflow owns approval, persistence and writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Entry:
    key: str
    value: str
    line_number: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "eligible"

    @property
    def line_start(self) -> int:
        return self.line_number

    def as_legacy_tuple(self) -> tuple[str, str, int]:
        return self.key, self.value, self.line_number


@dataclass(frozen=True)
class Document:
    path: Path
    source_text: str
    entries: tuple[Entry, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Resource:
    path: Path
    relative_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: str = ""
    severity: str = "warning"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message,
                "path": self.path, "severity": self.severity}


@dataclass(frozen=True)
class Discovery:
    resources: tuple[Resource, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class GameAdapter(Protocol):
    id: str
    game_id: str

    def discover(self, root: Path, source_lang: dict,
                 game_version: str | None = None) -> Discovery: ...

    def parse(self, path: Path, metadata: dict | None = None) -> Document: ...

    def parse_text(self, text: str, path: Path, metadata: dict | None = None) -> Document: ...

    def render(self, document: Document, translations: dict[str, str],
               target_lang: dict) -> dict[str, str]: ...

    def package_metadata(self, root: Path, target_lang: dict,
                         game_version: str | None = None) -> dict[str, str]: ...

    def validate(self, source: str, target: str) -> list[Diagnostic]: ...

    def language_folder(self, language: dict) -> str: ...
