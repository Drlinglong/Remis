"""Message-history extraction and redaction helpers for trace ledgers."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Mapping


_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|secret|credential)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|"
    r"password|secret|credential)\s*([:=])\s*([^\s,;]+)"
)
_BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def extract_message_history_trace(messages: Any, *, result_max_chars: int = 100_000) -> dict[str, Any]:
    """Extract plan/todo calls and compact tool activity from Pydantic history."""

    planning: list[dict[str, Any]] = []
    tool_activity: list[dict[str, Any]] = []
    planning_tools = {
        "write_plan", "read_plan", "add_task", "update_task_status",
        "update_task_statuses", "remove_task", "add_subtask", "set_dependency",
        "get_available_tasks",
    }
    for message_index, message in enumerate(messages or ()):
        message_timestamp = _message_timestamp(message)
        for part_index, part in enumerate(getattr(message, "parts", ())):
            tool_name = getattr(part, "tool_name", None)
            part_kind = str(getattr(part, "part_kind", ""))
            if not tool_name:
                continue
            common = {
                "tool": str(tool_name),
                "tool_call_id": getattr(part, "tool_call_id", None),
                "message_index": message_index,
                "part_index": part_index,
                "timestamp": _part_timestamp(part, message_timestamp),
            }
            if "return" in part_kind:
                result = _tool_result_digest(getattr(part, "content", None), result_max_chars)
                tool_activity.append({
                    **common, "kind": "result", "status": getattr(part, "outcome", "success"),
                    "result": result,
                })
                continue
            if "call" not in part_kind:
                continue
            arguments = _bounded_safe(_decode_tool_args(getattr(part, "args", None)))
            activity = {**common, "kind": "call", "status": "requested", "arguments": arguments}
            tool_activity.append(activity)
            if tool_name in planning_tools:
                planning.append(activity)
    return {"planning": planning, "tool_activity": tool_activity}


def _message_timestamp(message: Any) -> str | None:
    timestamp = getattr(message, "timestamp", None)
    return timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp


def _part_timestamp(part: Any, fallback: str | None) -> str | None:
    timestamp = getattr(part, "timestamp", None)
    if timestamp is None:
        return fallback
    return timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp


def _decode_tool_args(arguments: Any) -> Any:
    if not isinstance(arguments, str):
        return arguments
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return arguments


def _tool_result_digest(content: Any, max_chars: int) -> dict[str, Any]:
    safe = _safe(content)
    serialized = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
    explicit_truncated = bool(safe.get("truncated")) if isinstance(safe, Mapping) else False
    return {
        "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "char_count": len(serialized),
        "truncated": explicit_truncated or len(serialized) > max_chars,
    }


def _bounded_safe(value: Any, max_chars: int = 4_000) -> Any:
    safe = _safe(value)
    serialized = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
    if len(serialized) <= max_chars:
        return safe
    return {
        "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "char_count": len(serialized),
        "truncated": True,
    }


def _safe(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _safe(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    if dataclasses.is_dataclass(value):
        return _safe(dataclasses.asdict(value))
    if hasattr(value, "model_dump"):
        return _safe(value.model_dump())
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _safe(vars(value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _redact_error_message(message: str, *, max_chars: int = 1_000) -> str:
    """Remove common credential forms before an error reaches developer trace."""

    redacted = _SENSITIVE_VALUE.sub(r"\1\2[REDACTED]", message)
    redacted = _BEARER_VALUE.sub("Bearer [REDACTED]", redacted)
    if len(redacted) <= max_chars:
        return redacted
    return redacted[:max_chars] + "…"


__all__ = ["extract_message_history_trace"]
