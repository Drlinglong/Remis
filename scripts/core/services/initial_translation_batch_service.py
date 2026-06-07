import logging
from contextlib import contextmanager
from typing import Iterable, Optional

from scripts.app_settings import RECOMMENDED_MAX_WORKERS
from scripts.utils.rate_limiter import rate_limiter


LOCAL_SERIAL_PROVIDERS = {
    "ollama",
    "lm_studio",
    "local",
    "vllm",
    "koboldcpp",
    "oobabooga",
    "hunyuan",
}


def resolve_max_workers(concurrency_limit: Optional[int], selected_provider: str) -> int:
    if concurrency_limit:
        return max(1, int(concurrency_limit))
    if selected_provider in LOCAL_SERIAL_PROVIDERS:
        return 1
    return RECOMMENDED_MAX_WORKERS


def summarize_batch_warning_codes(warnings: Iterable) -> str:
    warning_codes = []
    for warning in warnings:
        warning_codes.append(get_batch_warning_code(warning))
    return ", ".join(sorted(set(warning_codes))[:6]) or "unknown"


def get_batch_warning_code(warning) -> str:
    if isinstance(warning, dict):
        if warning.get("type"):
            return str(warning["type"])
        if warning.get("source_term") or warning.get("target_term"):
            return "glossary_mismatch"
        return str(warning.get("level") or "warning")
    return str(getattr(warning, "code", None) or getattr(warning, "message", "warning"))


def format_batch_warning_detail(warning, index: int, total: int) -> str:
    code = get_batch_warning_code(warning)
    if not isinstance(warning, dict):
        return f"Batch warning detail {index}/{total}: code={code}; message={str(warning)}"

    parts = [f"Batch warning detail {index}/{total}: code={code}"]
    for key in ("batch_num", "batch_id", "attempt", "provider"):
        if key in warning:
            parts.append(f"{key}={warning[key]}")
    if warning.get("source_term") or warning.get("target_term"):
        parts.append(
            "glossary="
            f"{warning.get('source_term', '')}({warning.get('source_count', '?')})"
            " -> "
            f"{warning.get('target_term', '')}({warning.get('translated_count', '?')})"
        )
    if warning.get("message"):
        message = " ".join(str(warning["message"]).split())
        if len(message) > 300:
            message = message[:297] + "..."
        parts.append(f"message={message}")
    return "; ".join(parts)


def log_batch_warnings(filename: str, warnings: Iterable):
    warnings = list(warnings or [])
    if not warnings:
        return

    logging.warning(
        "Preliminary batch response validation reported %s issue(s) for %s (%s); "
        "final file format validation will run next.",
        len(warnings),
        filename,
        summarize_batch_warning_codes(warnings),
    )
    for index, warning in enumerate(warnings, start=1):
        logging.warning("%s; file=%s", format_batch_warning_detail(warning, index, len(warnings)), filename)



@contextmanager
def temporary_rpm_limit(rpm_limit: Optional[int]):
    previous_rpm = rate_limiter.rpm
    if rpm_limit:
        rate_limiter.update_rpm(int(rpm_limit))
    try:
        yield
    finally:
        if rpm_limit and previous_rpm != rate_limiter.rpm:
            rate_limiter.update_rpm(previous_rpm)
