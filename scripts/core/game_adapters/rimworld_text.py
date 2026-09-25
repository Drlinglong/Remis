"""RimWorld line-based String lists and RulePack grammar strings."""
from __future__ import annotations

import html
import re
from pathlib import Path

from .contracts import Diagnostic, Document, Entry

_GRAMMAR_ARROW_RE = re.compile(r"(?<!-)->")
_TOKEN_RE = re.compile(r"\{(?:\d+|[A-Za-z_][A-Za-z0-9_]*)(?:_[A-Za-z][A-Za-z0-9]*)?\}|\[[^\[\]\r\n]+\]|</?[A-Za-z][^<>]*>")


def parse_strings(text: str, path: Path, metadata: dict | None = None) -> Document:
    info = dict(metadata or {})
    lines = text.splitlines(keepends=True)
    entries: list[Entry] = []
    diagnostics: list[dict[str, str]] = []
    for number, raw_line in enumerate(lines, 1):
        value = raw_line.rstrip("\r\n")
        if not value.strip() or value.lstrip().startswith("#"):
            continue
        relative = info.get("relative_key_path") or _relative_strings_path(path)
        key = f"strings::{relative}:{number}"
        entries.append(Entry(key, value, number, {
            "kind": "strings", "line_index": number - 1,
            "output_path": info.get("relative_output_path", path.name),
        }))
    info.update({"kind": "strings", "line_ending": "\r\n" if "\r\n" in text else "\n", "diagnostics": diagnostics})
    return Document(path, text, tuple(entries), info)


def parse_rules_strings(text: str, path: Path, metadata: dict | None = None) -> Document:
    info = dict(metadata or {})
    info["kind"] = "rules_strings"
    entries: list[Entry] = []
    diagnostics: list[dict[str, str]] = []
    lines = text.splitlines(keepends=True)
    key = str(info.get("key", "rulesStrings"))
    for index, raw in enumerate(lines):
        value = raw.rstrip("\r\n")
        if not value.strip():
            continue
        match = _GRAMMAR_ARROW_RE.search(value)
        if not match:
            diagnostics.append(Diagnostic("unknown_grammar_rule", "No unambiguous '->' separator; left for review", str(path)).as_dict())
            continue
        rhs_start = match.end()
        while rhs_start < len(value) and value[rhs_start] in " \t":
            rhs_start += 1
        rhs_end = len(value)
        while rhs_end > rhs_start and value[rhs_end - 1] in " \t":
            rhs_end -= 1
        value_text = value[rhs_start:rhs_end]
        item_key = f"{key}.{index}"
        entries.append(Entry(item_key, value_text, index + 1, {
            "kind": "rules_strings", "line_index": index,
            "prefix": value[:rhs_start], "suffix": value[rhs_end:],
            "output_path": info.get("relative_output_path", path.name),
        }))
    info["diagnostics"] = diagnostics
    return Document(path, text, tuple(entries), info)


def render_text(document: Document, translations: dict[str, str]) -> dict[str, str]:
    kind = document.metadata.get("kind")
    if kind not in {"strings", "rules_strings"}:
        return {}
    lines = document.source_text.splitlines(keepends=True)
    ending = document.metadata.get("line_ending", "\n")
    for entry in document.entries:
        if entry.key not in translations:
            continue
        index = entry.line_number - 1 if kind == "strings" else entry.metadata["line_index"]
        if index >= len(lines):
            continue
        final_ending = "\r\n" if lines[index].endswith("\r\n") else "\n" if lines[index].endswith("\n") else ""
        if kind == "strings":
            lines[index] = str(translations[entry.key]) + final_ending
        else:
            lines[index] = entry.metadata["prefix"] + str(translations[entry.key]) + entry.metadata["suffix"] + final_ending
    return {str(document.metadata.get("relative_output_path", document.path.name)): "".join(lines)}


def validate_tokens(source: str, target: str) -> list[Diagnostic]:
    from collections import Counter
    source_tokens = Counter(_TOKEN_RE.findall(source))
    target_tokens = Counter(_TOKEN_RE.findall(target))
    diagnostics: list[Diagnostic] = []
    for token, count in (source_tokens - target_tokens).items():
        diagnostics.extend(Diagnostic("missing_token", f"Missing protected token {token!r}", severity="error") for _ in range(count))
    for token, count in (target_tokens - source_tokens).items():
        diagnostics.extend(Diagnostic("unexpected_token", f"Unexpected protected token {token!r}", severity="error") for _ in range(count))
    if "->" in source or "->" in target:
        source_arrows = source.count("->")
        target_arrows = target.count("->")
        if source_arrows != target_arrows:
            diagnostics.append(Diagnostic("grammar_separator_changed", "Grammar rule separator count changed", severity="error"))
    return diagnostics


def _relative_strings_path(path: Path) -> str:
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if part.casefold() == "strings":
            return Path(*parts[index + 1:]).as_posix()
    return path.name
