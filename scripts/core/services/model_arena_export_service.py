"""Build privacy-reviewed Model Arena export artifacts.

The arena keeps full local evidence so a result can be audited. Export is a
separate boundary: file-system locations and credentials are never allowed to
cross it, even when they appear inside a prompt or user note.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any


EXPORT_SCHEMA_VERSION = "remis.model-arena.export.v1"
EXPORT_MODES = {"evidence", "summary-only"}

_ALWAYS_EXCLUDED_FIELDS = {
    "api_key",
    "api_key_env",
    "api_url",
    "account",
    "account_id",
    "active_retry_key",
    "authorization",
    "base_url",
    "entry_key",
    "file_path",
    "glossary_entries",
    "masked_key",
    "password",
    "relative_file_path",
    "request_headers",
    "response_envelope",
    "retry_tasks",
    "start_idempotency_key",
    "task_id",
    "token",
    "username",
}
_SUMMARY_CONTENT_FIELDS = {
    "completion_text_before_parse",
    "note",
    "prompt_text",
    "source_text",
    "system_instruction",
    "translated_text",
}

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)\b(api[_ -]?key|access[_ -]?token|auth(?:orization)?|token)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
)
_PATH_PATTERNS = (
    re.compile(r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/][^\s\r\n\"'<>|]+"),
    re.compile(r"\\\\[^\\\s]+\\[^\s\r\n\"'<>|]+"),
    re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|var|tmp|opt|etc)/[^\s\"'<>|]+"),
)
_URL_PATTERN = re.compile(r"(?i)\bhttps?://[^\s\r\n\"'<>]+")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_excluded_field(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in _ALWAYS_EXCLUDED_FIELDS
        or lowered.endswith("_path")
        or lowered.endswith("_url")
        or lowered.endswith("_api_key")
        or lowered.endswith("_masked_key")
        or lowered.endswith("_account")
        or lowered.endswith("_account_id")
        or (
            lowered.endswith("_token")
            and not lowered.endswith("_tokens")
        )
    )


def _redact_text(value: str, redactions: Counter[str]) -> str:
    sanitized = value
    for pattern in _SECRET_PATTERNS:
        sanitized, count = pattern.subn("[REDACTED_SECRET]", sanitized)
        if count:
            redactions["secret"] += count
    for pattern in _PATH_PATTERNS:
        sanitized, count = pattern.subn("[REDACTED_PATH]", sanitized)
        if count:
            redactions["path"] += count
    sanitized, count = _URL_PATTERN.subn("[REDACTED_URL]", sanitized)
    if count:
        redactions["url"] += count
    return sanitized


def _sanitize(
    value: Any,
    *,
    mode: str,
    redactions: Counter[str],
    field_name: str = "",
) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            key_name = str(key)
            lowered = key_name.lower()
            if _is_excluded_field(lowered):
                redactions["excluded_field"] += 1
                continue
            if "reasoning" in lowered or "thinking" in lowered:
                redactions["excluded_reasoning"] += 1
                continue
            if mode == "summary-only" and lowered in _SUMMARY_CONTENT_FIELDS:
                continue
            result[key_name] = _sanitize(
                nested,
                mode=mode,
                redactions=redactions,
                field_name=lowered,
            )
        return result
    if isinstance(value, list):
        return [
            _sanitize(
                item,
                mode=mode,
                redactions=redactions,
                field_name=field_name,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _sanitize(
                item,
                mode=mode,
                redactions=redactions,
                field_name=field_name,
            )
            for item in value
        ]
    if isinstance(value, str):
        return _redact_text(value, redactions)
    return value


def build_model_arena_export(
    run_bundle: dict[str, Any],
    *,
    mode: str = "evidence",
    remis_version: str = "unknown",
) -> dict[str, Any]:
    """Return the exact JSON-ready artifact shown in export preview.

    ``run_bundle`` is the repository detail bundle. The function deliberately
    accepts dictionaries so export policy remains independent from persistence
    models and can be applied to historical schema versions.
    """

    if mode not in EXPORT_MODES:
        raise ValueError(f"Unsupported model arena export mode: {mode}")

    redactions: Counter[str] = Counter()
    sanitized = _sanitize(
        copy.deepcopy(run_bundle),
        mode=mode,
        redactions=redactions,
    )
    artifact_timestamp = str(run_bundle.get("completed_at") or _utc_now_iso())
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        # A completed run is immutable. Reusing its completion timestamp keeps
        # GET preview byte-for-byte equivalent to the later approved download.
        "exported_at": artifact_timestamp,
        "export_mode": mode,
        "remis_version": remis_version,
        "redactions": [
            {"type": category, "count": count}
            for category, count in sorted(redactions.items())
            if count
        ],
        "arena_run": sanitized,
    }
