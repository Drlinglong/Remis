"""Surviving Mars / Relaunched ``ModItemLocTable`` CSV support.

The game consumes a five-column CSV table and keeps the localization key in
the first column.  This adapter deliberately owns the CSV syntax boundary so
the existing Paradox workflow can continue to operate on ``(key, text)``
entries without flattening or rewriting unrelated columns.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


FORMAT_ADAPTER_ID = "surviving_mars_csv"
HEADER = ("ID", "Text", "Translation", "VoiceActor", "Context")
_ASCII_ID_RE = re.compile(r"[0-9]+\Z")
_TAG_RE = re.compile(r"<[^<>\r\n]*>")


class SurvivingMarsCsvError(ValueError):
    """Raised when a file claims the Surviving Mars table shape but is invalid."""


class NotSurvivingMarsCsv(SurvivingMarsCsvError):
    """Raised when a CSV does not have the exact ModItemLocTable header."""


@dataclass(frozen=True)
class CsvEntry:
    """One translatable CSV row, represented like a Paradox localization entry."""

    key: str
    value: str
    line_number: int
    row_index: int

    status: str = "eligible"

    @property
    def line_start(self) -> int:
        return self.line_number

    def as_legacy_tuple(self) -> tuple[str, str, int]:
        return self.key, self.value, self.line_number


@dataclass(frozen=True)
class CsvDocument:
    """Parsed table with enough information to perform safe column writeback."""

    rows: tuple[tuple[str, ...], ...]
    entries: tuple[CsvEntry, ...]
    source_text: str
    line_ending: str

    @property
    def data_row_count(self) -> int:
        return max(0, len(self.rows) - 1)


@dataclass(frozen=True)
class CsvTagMismatch:
    """Exact tag multiset difference between source and target text."""

    missing: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def is_mismatch(self) -> bool:
        return bool(self.missing or self.unexpected)


def _read_utf8(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def _line_ending(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _rows_from_text(text: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise SurvivingMarsCsvError(f"CSV syntax error: {exc}") from exc


def _validate_rows(rows: list[list[str]]) -> None:
    if not rows or tuple(rows[0]) != HEADER:
        raise NotSurvivingMarsCsv(
            "Expected header: " + ",".join(HEADER)
        )

    seen_ids: set[str] = set()
    for row_index, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        if len(row) != len(HEADER):
            raise SurvivingMarsCsvError(
                f"Row {row_index + 1} has {len(row)} columns; expected 5"
            )
        key = row[0]
        if not _ASCII_ID_RE.fullmatch(key):
            raise SurvivingMarsCsvError(
                f"Row {row_index + 1} has a non-ASCII-decimal ID: {key!r}"
            )
        if key in seen_ids:
            raise SurvivingMarsCsvError(f"Duplicate ID at row {row_index + 1}: {key}")
        seen_ids.add(key)


def parse_text(text: str) -> CsvDocument:
    """Parse and validate a complete ModItemLocTable CSV document."""

    rows = _rows_from_text(text)
    _validate_rows(rows)
    entries: list[CsvEntry] = []
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    for row_index, row in enumerate(reader):
        if row_index == 0 or not row or not row[1].strip():
            continue
        entries.append(
            CsvEntry(
                key=row[0],
                value=row[1],
                line_number=reader.line_num,
                row_index=row_index,
            )
        )
    return CsvDocument(
        rows=tuple(tuple(row) for row in rows),
        entries=tuple(entries),
        source_text=text,
        line_ending=_line_ending(text),
    )


def parse_file(path: Path) -> CsvDocument:
    """Read a UTF-8 CSV and validate the exact game table schema."""

    return parse_text(_read_utf8(path))


def is_table_file(path: str | Path) -> bool:
    """Return whether the file has the exact table header.

    A syntactically malformed file with this header still returns ``True`` so
    callers can report it as an invalid Surviving Mars source rather than
    silently treating it as an unrelated CSV.
    """

    candidate = Path(path)
    if candidate.suffix.lower() != ".csv":
        return False
    try:
        with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
            first_row = next(csv.reader(handle, strict=True), None)
    except (OSError, UnicodeError, csv.Error):
        return False
    return first_row is not None and tuple(first_row) == HEADER


def extract_file(
    path: str | Path,
) -> tuple[list[str], list[str], dict[int, dict[str, Any]]]:
    """Return the existing parser contract for an eligible CSV file."""

    document = parse_file(Path(path))
    original_lines = document.source_text.splitlines(keepends=True)
    texts = [entry.value for entry in document.entries]
    key_map = {
        index: {
            "key_part": entry.key,
            "line_num": entry.line_number - 1,
            "line_number": entry.line_number,
            "row_index": entry.row_index,
        }
        for index, entry in enumerate(document.entries)
    }
    return original_lines, texts, key_map


def entries(path: str | Path, value_column: str = "Text") -> list[CsvEntry]:
    """Read entries from one table using ``Text`` or ``Translation`` values."""

    if value_column not in {"Text", "Translation"}:
        raise ValueError("value_column must be Text or Translation")
    document = parse_file(Path(path))
    column_index = HEADER.index(value_column)
    result: list[CsvEntry] = []
    reader = csv.reader(io.StringIO(document.source_text, newline=""), strict=True)
    for row_index, row in enumerate(reader):
        if row_index == 0 or not row or not row[column_index].strip():
            continue
        result.append(
            CsvEntry(
                key=row[0],
                value=row[column_index],
                line_number=reader.line_num,
                row_index=row_index,
            )
        )
    return result


def rewrite_text(
    source_text: str,
    translated_texts: Iterable[str],
    key_map: dict[int, dict[str, Any]],
) -> str:
    """Replace only the ``Translation`` column, preserving all other fields."""

    document = parse_text(source_text)
    rows = [list(row) for row in document.rows]
    translations = list(translated_texts)
    if len(translations) != len(key_map):
        raise SurvivingMarsCsvError(
            f"Translation count ({len(translations)}) does not match key map ({len(key_map)})"
        )

    for index, translated in enumerate(translations):
        entry_info = key_map.get(index)
        if not entry_info:
            raise SurvivingMarsCsvError(f"Missing key map entry at index {index}")
        row_index = entry_info.get("row_index")
        key = str(entry_info.get("key_part", ""))
        if not isinstance(row_index, int) or row_index <= 0 or row_index >= len(rows):
            raise SurvivingMarsCsvError(f"Invalid row index for translation {index}: {row_index!r}")
        if not rows[row_index] or rows[row_index][0] != key:
            raise SurvivingMarsCsvError(
                f"CSV key map mismatch at row {row_index + 1}: expected {key!r}"
            )
        rows[row_index][2] = str(translated)

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator=document.line_ending)
    writer.writerows(rows)
    return output.getvalue()


def compare_tags(source_text: str, target_text: str) -> CsvTagMismatch:
    """Compare exact ``<...>`` tag identity and multiplicity.

    Parameters inside tags remain part of the identity.  This protects tags
    such as ``<resource(res)>`` and ``<image UI/... 2000>`` without masking or
    replacing semantic tokens before model translation.
    """

    source_counts = Counter(_TAG_RE.findall(source_text))
    target_counts = Counter(_TAG_RE.findall(target_text))
    missing = tuple(sorted(
        tag for tag, count in (source_counts - target_counts).items()
        for _ in range(count)
    ))
    unexpected = tuple(sorted(
        tag for tag, count in (target_counts - source_counts).items()
        for _ in range(count)
    ))
    return CsvTagMismatch(missing=missing, unexpected=unexpected)


def parse_summary(document: CsvDocument) -> dict[str, int]:
    """Expose the parser counters used by Remis snapshots and context trees."""

    nonblank_rows = sum(1 for row in document.rows[1:] if row)
    return {
        "raw": document.data_row_count,
        "syntax_parsed": nonblank_rows,
        "policy_excluded": nonblank_rows - len(document.entries),
        "eligible": len(document.entries),
        "parse_errors": 0,
    }
