"""Bounded hardcoded-text coverage, separate from translatable CSV resources."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path

from scripts.core.services.mars_lua_discovery import scan_lua_text

MAX_TOTAL_BYTES = 32_000_000
MAX_FILE_BYTES = 2_000_000
MAX_CANDIDATES = 2000


class LuaCoverage:
    """Collect evidence during the existing source walk without evaluating Lua."""

    def __init__(self, root: Path):
        self.root = root
        self.total_bytes = 0
        self.files_scanned = 0
        self.candidates: list[dict] = []
        self.diagnostics: list[dict] = []
        self.complete = True
        self.exhausted = False

    def inspect(self, path: Path) -> None:
        if self.exhausted:
            return
        relative = path.relative_to(self.root).as_posix()
        try:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError("Lua file exceeds the static scan size limit.")
            if self.total_bytes + size > MAX_TOTAL_BYTES:
                self.exhausted = True
                raise ValueError("Lua coverage byte budget reached; report is partial.")
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            self.total_bytes += len(data)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("Lua file grew beyond the static scan size limit.")
            source = data.decode("utf-8-sig", errors="strict")
            remaining = MAX_CANDIDATES - len(self.candidates)
            found = [asdict(item) for item in scan_lua_text(
                source, relative, max_candidates=remaining + 1
            )]
            source_hash = hashlib.sha256(data).hexdigest()
            for item in found:
                item["source_sha256"] = source_hash
            self.files_scanned += 1
            self.candidates.extend(found[:remaining])
            if len(found) > remaining:
                self.exhausted = True
                raise ValueError("Lua candidate limit reached; report is partial.")
        except (ValueError, OSError) as exc:
            self.complete = False
            self.diagnostics.append({"code": "lua_coverage_incomplete", "severity": "warning",
                                     "path": relative, "message": str(exc)})

    def result(self, walk_complete: bool) -> dict:
        literal = sum(item["classification"] == "literal" for item in self.candidates)
        return {
            "scan_complete": self.complete and walk_complete,
            "scope": "direct_untranslated_calls_only",
            "files_scanned": self.files_scanned,
            "candidate_count": len(self.candidates),
            "literal_count": literal,
            "dynamic_count": len(self.candidates) - literal,
            "candidates": self.candidates,
            "diagnostics": self.diagnostics,
            "included_in_translation": False,
            "automatic_rewrite_supported": False,
            "requires_review": bool(self.candidates) or not (self.complete and walk_complete),
            "limitations": [
                "Candidates are not confirmed UI text or approved edits.",
                "Aliases, indirect calls and ordinary Lua strings are not comprehensively discovered.",
                "Linked and hidden directories are not scanned; offsets refer to decoded UTF-8 text without BOM.",
                "Compiled packages and Lua bytecode are not scanned for hardcoded text.",
                "A zero count does not establish whole-Mod coverage.",
                "Candidate keys are provisional bindings, not persisted localization IDs.",
            ],
        }
