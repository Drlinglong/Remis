"""Convert application JSON schemas into strict structured-output schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy suitable for providers that enforce structured outputs.

    Strict structured-output APIs require closed objects and require every
    declared property. Optional application fields remain nullable through
    their existing ``anyOf`` schema; requiring them removes model ambiguity.
    """

    normalized = deepcopy(schema)
    _normalize_node(normalized)
    return normalized


def _normalize_node(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _normalize_node(item)
        return
    if not isinstance(node, dict):
        return

    node.pop("default", None)
    properties = node.get("properties")
    if isinstance(properties, dict):
        node["additionalProperties"] = False
        node["required"] = list(properties)
    for value in node.values():
        _normalize_node(value)
