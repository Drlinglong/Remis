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
        if isinstance(warning, dict):
            warning_codes.append(str(warning.get("type") or warning.get("level") or "warning"))
        else:
            warning_codes.append(str(getattr(warning, "code", None) or getattr(warning, "message", "warning")))
    return ", ".join(sorted(set(warning_codes))[:6]) or "unknown"


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
