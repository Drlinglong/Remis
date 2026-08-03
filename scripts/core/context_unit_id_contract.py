"""Strict, provider-facing contracts for model-generated local-unit IDs."""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any

from pydantic import BeforeValidator, Field


logger = logging.getLogger(__name__)

UNIT_ID_PATTERN = r"^unit_\d+$"
_UNIT_ID_TOKEN = re.compile(r"unit_\d+")


def normalize_unit_id_list(value: Any) -> Any:
    """Recover explicit unit tokens from prose-tainted list entries.

    Models occasionally place several valid IDs plus an explanation inside one
    JSON string. Extracting only explicit ``unit_N`` tokens is deterministic;
    the caller's project-level contract still rejects every unknown token.
    Values with no unit token are preserved so normal schema validation fails.
    """

    if not isinstance(value, list):
        return value
    normalized: list[Any] = []
    malformed_entries = 0
    for item in value:
        if not isinstance(item, str) or re.fullmatch(UNIT_ID_PATTERN, item):
            normalized.append(item)
            continue
        tokens = _UNIT_ID_TOKEN.findall(item)
        if not tokens:
            normalized.append(item)
            continue
        malformed_entries += 1
        normalized.extend(tokens)
    deduplicated: list[Any] = []
    seen_strings: set[str] = set()
    for item in normalized:
        if isinstance(item, str):
            if item in seen_strings:
                continue
            seen_strings.add(item)
        deduplicated.append(item)
    if malformed_entries:
        logger.warning(
            "Normalized %d prose-tainted event evidence unit ID entr%s",
            malformed_entries,
            "y" if malformed_entries == 1 else "ies",
        )
    return deduplicated


UnitId = Annotated[str, Field(pattern=UNIT_ID_PATTERN)]
EvidenceUnitIds = Annotated[list[UnitId], BeforeValidator(normalize_unit_id_list)]
