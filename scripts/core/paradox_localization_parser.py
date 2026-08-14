"""Canonical parser for Paradox localization files.

The project historically had two subtly different quote scanners.  This
module owns syntax recognition and source spans; callers may apply their own
eligibility policy, but they must not re-parse the source text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Iterator, Optional

from scripts.utils import read_text_bom


ENTRY_PREFIX_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<base_key>[^:\s]+)\s*:\s*"
    r"(?P<version>\d*)\s*\""
)
LANGUAGE_HEADER_RE = re.compile(r"^\s*l_[\w-]+:\s*(?:#.*)?$")
PURE_VARIABLE_RE = re.compile(r"^\$[^$\r\n]+\$")


@dataclass(frozen=True)
class ParseDiagnostic:
    """A syntax diagnostic tied to a physical source line."""

    code: str
    message: str
    line_number: int
    severity: str = "error"
    key: Optional[str] = None
    recoverable: bool = False
    opening_quote_offset: Optional[int] = None
    line_end_offset: Optional[int] = None


@dataclass(frozen=True)
class LocalizationEntry:
    """One syntactically parsed localization row and its exact source span."""

    key: str
    base_key: str
    version: Optional[str]
    raw_value: str
    value: str
    line_start: int
    line_end: int
    opening_quote_offset: int
    closing_quote_offset: int
    value_start_offset: int
    value_end_offset: int
    opening_column: int
    closing_column: int
    status: str
    policy_exclusion_reason: Optional[str] = None

    @property
    def line_number(self) -> int:
        """Compatibility alias used by existing snapshot and validator code."""

        return self.line_start

    @property
    def full_key(self) -> str:
        return self.key

    def as_legacy_tuple(self) -> tuple[str, str, int]:
        return self.key, self.value, self.line_start


@dataclass(frozen=True)
class ParseReport:
    """Complete parser output, including excluded rows and diagnostics."""

    entries: tuple[LocalizationEntry, ...]
    diagnostics: tuple[ParseDiagnostic, ...]
    source_text: str

    @property
    def syntax_parsed_count(self) -> int:
        return len(self.entries)

    @property
    def eligible_entries(self) -> tuple[LocalizationEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status == "eligible")

    @property
    def policy_excluded_entries(self) -> tuple[LocalizationEntry, ...]:
        return tuple(
            entry for entry in self.entries if entry.status == "policy_excluded"
        )

    @property
    def summary(self) -> dict[str, int]:
        """Return stable counters for workflow diagnostics and telemetry."""

        return {
            "raw": self.syntax_parsed_count + len(self.diagnostics),
            "syntax_parsed": self.syntax_parsed_count,
            "policy_excluded": len(self.policy_excluded_entries),
            "eligible": len(self.eligible_entries),
            "parse_errors": len(self.diagnostics),
        }


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def _line_end(text: str, start: int) -> int:
    newline = text.find("\n", start)
    return len(text) if newline < 0 else newline


def _is_escaped(text: str, offset: int) -> bool:
    backslashes = 0
    index = offset - 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def normalize_raw_value(raw_value: str) -> str:
    """Decode only escaped quotes, preserving Paradox tags and ``\\n``."""

    normalized: list[str] = []
    index = 0
    while index < len(raw_value):
        char = raw_value[index]
        if char != "\\":
            normalized.append(char)
            index += 1
            continue

        slash_start = index
        while index < len(raw_value) and raw_value[index] == "\\":
            index += 1
        slash_count = index - slash_start
        if index < len(raw_value) and raw_value[index] == '"' and slash_count % 2:
            normalized.extend("\\" * (slash_count - 1))
            normalized.append('"')
            index += 1
        else:
            normalized.extend("\\" * slash_count)
    return "".join(normalized)


def escape_value(value: str) -> str:
    """Encode a model value for a Paradox quoted value without double escaping."""

    escaped: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            escaped.append('\\"' if char == '"' else char)
            index += 1
            continue

        slash_start = index
        while index < len(value) and value[index] == "\\":
            index += 1
        slash_count = index - slash_start
        if index < len(value) and value[index] == '"':
            escaped.extend("\\" * (slash_count + (slash_count % 2 == 0)))
            escaped.append('"')
            index += 1
        else:
            escaped.extend("\\" * slash_count)
    return "".join(escaped)


def _closing_quote_candidates(
    text: str,
    opening_offset: int,
    line_end: int,
) -> list[int]:
    candidates: list[int] = []
    for offset in range(opening_offset + 1, line_end):
        if text[offset] == '"' and not _is_escaped(text, offset):
            candidates.append(offset)
    return candidates


def _find_closing_quote(text: str, opening_offset: int, line_end: int) -> Optional[int]:
    """Find the outer quote, tolerating raw internal quotes and tail comments."""

    candidates = _closing_quote_candidates(text, opening_offset, line_end)
    if not candidates:
        return None

    # Prefer a quote immediately before a tail comment.  This avoids treating
    # a quote in ``# a comment "`` as the value terminator.
    for offset in reversed(candidates):
        if text[offset + 1 : line_end].lstrip().startswith("#"):
            return offset
    # With no comment, the outer quote is the final unescaped quote on the row.
    return candidates[-1]


def _classify(base_key: str, version: Optional[str], value: str) -> tuple[str, Optional[str]]:
    key = f"{base_key}:{version}" if version else base_key
    if not value:
        return "policy_excluded", "empty_value"
    if value == key or value == base_key:
        return "policy_excluded", "self_referencing_value"
    if PURE_VARIABLE_RE.fullmatch(value):
        return "policy_excluded", "pure_variable"
    return "eligible", None


def _build_entry(
    text: str,
    starts: list[int],
    match: re.Match[str],
    opening_offset: int,
    closing_offset: int,
    line_index: int,
    end_line_index: int,
) -> LocalizationEntry:
    base_key = match.group("base_key").strip()
    version_text = match.group("version").strip()
    version = version_text or None
    key = f"{base_key}:{version_text}" if version_text else base_key
    raw_value = text[opening_offset + 1 : closing_offset]
    value = normalize_raw_value(raw_value)
    status, reason = _classify(base_key, version, value)
    return LocalizationEntry(
        key=key,
        base_key=base_key,
        version=version,
        raw_value=raw_value,
        value=value,
        line_start=line_index + 1,
        line_end=end_line_index + 1,
        opening_quote_offset=opening_offset,
        closing_quote_offset=closing_offset,
        value_start_offset=opening_offset + 1,
        value_end_offset=closing_offset,
        opening_column=opening_offset - starts[line_index],
        closing_column=closing_offset - starts[end_line_index],
        status=status,
        policy_exclusion_reason=reason,
    )


def parse_text(text: str) -> ParseReport:
    """Parse a UTF-8 decoded localization document into canonical entries."""

    starts = _line_starts(text)
    entries: list[LocalizationEntry] = []
    diagnostics: list[ParseDiagnostic] = []
    line_index = 0
    total_lines = len(starts)

    while line_index < total_lines:
        start = starts[line_index]
        end = _line_end(text, start)
        line = text[start:end]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or LANGUAGE_HEADER_RE.match(line):
            line_index += 1
            continue

        match = ENTRY_PREFIX_RE.match(line)
        if not match:
            line_index += 1
            continue

        opening_offset = start + match.end() - 1
        closing_offset = _find_closing_quote(text, opening_offset, end)
        end_line_index = line_index
        boundary_is_certain = True
        while closing_offset is None and end_line_index + 1 < total_lines:
            candidate_line = end_line_index + 1
            next_start = starts[candidate_line]
            next_end = _line_end(text, next_start)
            next_line = text[next_start:next_end]
            if (
                ENTRY_PREFIX_RE.match(next_line)
                or LANGUAGE_HEADER_RE.match(next_line)
                or next_line.strip().startswith("#")
            ):
                break
            boundary_is_certain = False
            end_line_index = candidate_line
            closing_offset = _find_closing_quote(text, opening_offset, next_end)

        if closing_offset is None:
            base_key = match.group("base_key").strip()
            version_text = match.group("version").strip()
            key = f"{base_key}:{version_text}" if version_text else base_key
            diagnostics.append(
                ParseDiagnostic(
                    code="unterminated_value",
                    message="Localization value has no closing quote.",
                    line_number=line_index + 1,
                    key=key,
                    recoverable=boundary_is_certain,
                    opening_quote_offset=opening_offset,
                    line_end_offset=end,
                )
            )
            line_index += 1
            continue

        entries.append(
            _build_entry(
                text,
                starts,
                match,
                opening_offset,
                closing_offset,
                line_index,
                end_line_index,
            )
        )
        line_index = end_line_index + 1

    return ParseReport(tuple(entries), tuple(diagnostics), text)


def parse_file(path: Path) -> ParseReport:
    """Read and parse a Paradox localization file with explicit UTF-8 BOM support."""

    return parse_text(read_text_bom(path))


def patch_text(text: str, replacements: Iterable[tuple[LocalizationEntry, str]]) -> str:
    """Patch canonical value spans from right to left, preserving all syntax."""

    patched = text
    ordered = sorted(replacements, key=lambda item: item[0].value_start_offset, reverse=True)
    for entry, value in ordered:
        encoded = escape_value(value)
        patched = (
            patched[: entry.value_start_offset]
            + encoded
            + patched[entry.value_end_offset :]
        )
    return patched


def patch_text_with_recoveries(
    text: str,
    replacements: Iterable[tuple[LocalizationEntry, str]],
    recoveries: Iterable[ParseDiagnostic],
) -> str:
    """Patch valid values and replace recoverable malformed values with empty strings."""

    edits: list[tuple[int, int, str]] = [
        (entry.value_start_offset, entry.value_end_offset, escape_value(value))
        for entry, value in replacements
    ]
    for diagnostic in recoveries:
        if (
            not diagnostic.recoverable
            or diagnostic.opening_quote_offset is None
            or diagnostic.line_end_offset is None
        ):
            continue
        edits.append(
            (
                diagnostic.opening_quote_offset,
                diagnostic.line_end_offset,
                '""',
            )
        )

    patched = text
    for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
        patched = patched[:start] + replacement + patched[end:]
    return patched


def patch_lines(
    lines: list[str],
    replacements: Iterable[tuple[LocalizationEntry, str]],
    recoveries: Iterable[ParseDiagnostic] = (),
) -> list[str]:
    """Line-list adapter used by the existing file builder."""

    return patch_text_with_recoveries(
        "".join(lines), replacements, recoveries
    ).splitlines(keepends=True)


def iter_eligible(path: Path) -> Iterator[LocalizationEntry]:
    """Yield only policy-eligible entries for small read-only consumers."""

    yield from parse_file(path).eligible_entries
