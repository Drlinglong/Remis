# -*- coding: utf-8 -*-
"""Compatibility adapter over the canonical Paradox localization parser."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scripts.core.paradox_localization_parser import (
    LocalizationEntry,
    ParseDiagnostic,
    parse_text,
)

try:
    from . import i18n
except ImportError:  # pragma: no cover - standalone utility import
    i18n = None


class QuoteExtractor:
    """Legacy return-shape adapter; syntax parsing lives in ``parse_text``."""

    @staticmethod
    def extract_from_line(line: str) -> Optional[str]:
        """Return the first eligible value in one localization line."""

        report = parse_text(line)
        entry = next(iter(report.eligible_entries), None)
        return entry.value if entry else None

    @staticmethod
    def _read_lines(file_path: str) -> List[str]:
        with open(file_path, "r", encoding="utf-8-sig", newline="") as handle:
            return handle.readlines()

    @staticmethod
    def _customizable_entries(
        file_path: str, original_lines: List[str]
    ) -> Tuple[List[str], Dict[int, Dict[str, Any]]]:
        texts: List[str] = []
        key_map: Dict[int, Dict[str, Any]] = {}
        add_custom_loc_re = re.compile(r'add_custom_loc\s*=\s*"((?:\\.|[^"\\])*)"')
        for line_num, line in enumerate(original_lines):
            if "add_custom_loc" not in line:
                continue
            match = add_custom_loc_re.search(line)
            if not match:
                continue
            value = match.group(1)
            index = len(texts)
            texts.append(value)
            key_map[index] = {
                "key_part": "add_custom_loc",
                "original_value_part": line.split("=", 1)[1].strip(),
                "line_num": line_num,
            }
        return texts, key_map

    @staticmethod
    def _entry_map(entry: LocalizationEntry) -> Dict[str, Any]:
        return {
            "key_part": entry.key,
            "original_value_part": entry.raw_value,
            "line_num": entry.line_start - 1,
            "line_start": entry.line_start,
            "line_end": entry.line_end,
            "value_start_offset": entry.value_start_offset,
            "value_end_offset": entry.value_end_offset,
            "opening_quote_offset": entry.opening_quote_offset,
            "closing_quote_offset": entry.closing_quote_offset,
            "entry": entry,
        }

    @staticmethod
    def extract_from_file(
        file_path: str,
        *,
        strict: bool = False,
    ) -> Tuple[List[str], List[str], Dict[int, Dict[str, Any]]]:
        """Extract eligible values and exact source spans from a localization file."""

        original_lines, texts, key_map, diagnostics = (
            QuoteExtractor.extract_from_file_with_diagnostics(file_path)
        )
        if diagnostics and strict:
            raise ValueError(
                f"Canonical localization parse failed for {file_path}: "
                + ", ".join(d.code for d in diagnostics)
            )
        return original_lines, texts, key_map

    @staticmethod
    def extract_from_file_with_diagnostics(
        file_path: str,
    ) -> Tuple[
        List[str],
        List[str],
        Dict[int, Dict[str, Any]],
        Tuple[ParseDiagnostic, ...],
    ]:
        """Extract eligible values while retaining structured syntax diagnostics."""

        try:
            rel_path = os.path.relpath(file_path)
        except ValueError:
            rel_path = os.path.basename(file_path)
        logging.info(
            i18n.t("parsing_file", filename=rel_path)
            if i18n
            else f"Parsing file: {rel_path}"
        )

        original_lines = QuoteExtractor._read_lines(file_path)
        is_txt = (
            file_path.lower().endswith(".txt")
            and "customizable_localization" in file_path.replace("\\", "/")
        )
        if is_txt:
            texts, key_map = QuoteExtractor._customizable_entries(file_path, original_lines)
            return original_lines, texts, key_map, ()

        report = parse_text("".join(original_lines))
        if report.diagnostics:
            logging.warning(
                "Canonical localization parser found %d syntax errors in %s: %s",
                len(report.diagnostics),
                rel_path,
                ", ".join(d.code for d in report.diagnostics),
            )

        texts: List[str] = []
        key_map: Dict[int, Dict[str, Any]] = {}
        for entry in report.eligible_entries:
            index = len(texts)
            texts.append(entry.value)
            key_map[index] = QuoteExtractor._entry_map(entry)
        logging.info(
            "Canonical localization parse summary for %s: %s",
            rel_path,
            report.summary,
        )
        return original_lines, texts, key_map, report.diagnostics
