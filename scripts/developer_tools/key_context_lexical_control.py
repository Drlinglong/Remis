"""Load a frozen lexical control and attach it identically to every arm case."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def load_lexical_control(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    control = payload.get("lexical_control")
    if not isinstance(control, dict) or control.get("scope") != "shared_by_all_arms":
        raise ValueError("Lexical control must declare scope=shared_by_all_arms")
    entries = control.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Lexical control must contain at least one entry")
    converted = []
    seen = set()
    for item in entries:
        source = item.get("source_value")
        target = item.get("target_value")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Lexical control source_value must be non-empty")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("Lexical control target_value must be non-empty")
        identity = (source, target)
        if identity in seen:
            raise ValueError(f"Duplicate lexical control entry: {identity}")
        seen.add(identity)
        converted.append(
            {
                "entry_id": item.get("id") or f"control-{len(converted) + 1}",
                "translations": {"en": source, "zh-CN": target},
                "variants": {},
                "abbreviations": {},
                "raw_metadata": {
                    "remarks": "Frozen lexical control shared by every experiment arm."
                },
            }
        )
    return converted, raw


def attach_lexical_control(
    cases: list[dict[str, Any]], entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    attached = deepcopy(cases)
    for case in attached:
        existing = case.get("glossary_entries", [])
        if existing and existing != entries:
            raise ValueError(f"{case['id']} already contains a different glossary control")
        case["glossary_entries"] = deepcopy(entries)
    return attached
