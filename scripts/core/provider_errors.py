"""Classify provider failures that cannot succeed on a batch retry."""

from __future__ import annotations

from typing import Any, Optional


FATAL_STATUS_CODES = {400, 401, 403, 404, 422}
FATAL_ERROR_CODES = {
    "authentication_error",
    "forbidden",
    "invalid_api_key",
    "invalid_model",
    "model_not_found",
    "permission_denied",
    "unknown_model",
    "unsupported_model",
}
FATAL_MESSAGE_MARKERS = (
    "api key is invalid",
    "authentication failed",
    "authentication_error",
    "does not exist or you do not have access",
    "forbidden",
    "incorrect api key",
    "invalid api key",
    "invalid model",
    "invalid_api_key",
    "model does not exist",
    "model is not available",
    "model not found",
    "model_not_found",
    "no such model",
    "permission denied",
    "permission_denied",
    "unknown model",
    "unsupported model",
)


class ProviderFatalError(RuntimeError):
    """A provider/configuration failure that must abort the translation run."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: Optional[int] = None,
        reason_code: str = "provider_invalid_request",
    ):
        self.provider = provider
        self.status_code = status_code
        self.reason_code = reason_code
        super().__init__(message)


def _reason_code(status_code: Optional[int], error_code: str, message: str) -> str:
    if status_code == 401 or error_code in {"authentication_error", "invalid_api_key"} or any(
        marker in message
        for marker in ("api key is invalid", "authentication failed", "incorrect api key", "invalid api key")
    ):
        return "provider_authentication_failed"
    if status_code == 403 or error_code in {"forbidden", "permission_denied"} or any(
        marker in message for marker in ("forbidden", "permission denied", "permission_denied")
    ):
        return "provider_forbidden"
    if error_code in {"invalid_model", "model_not_found", "unknown_model", "unsupported_model"} or any(
        marker in message
        for marker in (
            "invalid model",
            "model does not exist",
            "model is not available",
            "model not found",
            "model_not_found",
            "no such model",
            "unknown model",
            "unsupported model",
        )
    ):
        return "provider_invalid_model"
    return "provider_invalid_request"


def provider_failure_task_fields(error: BaseException) -> dict[str, str]:
    """Return stable user-facing task metadata for a fatal provider failure."""

    if not isinstance(error, ProviderFatalError):
        return {}
    messages = {
        "provider_authentication_failed": "Provider authentication failed. Check the API key in Remis Settings.",
        "provider_forbidden": "Provider access was forbidden. Check account and model permissions.",
        "provider_invalid_model": "The selected model is invalid or unavailable. Select a loaded or supported model.",
        "provider_invalid_request": "The provider rejected this request as non-recoverable. Check provider settings.",
    }
    return {
        "attention_reason_code": error.reason_code,
        "attention_reason": messages[error.reason_code],
    }


def _status_code(error: BaseException) -> Optional[int]:
    candidates: list[Any] = [
        getattr(error, "status_code", None),
        getattr(getattr(error, "response", None), "status_code", None),
    ]
    for value in candidates:
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _error_code(error: BaseException) -> str:
    for source in (error, getattr(error, "body", None), getattr(error, "error", None)):
        if isinstance(source, dict):
            value = source.get("code") or source.get("type")
        else:
            value = getattr(source, "code", None) or getattr(source, "type", None)
        if value:
            return str(value).strip().lower()
    return ""


def classify_provider_fatal_error(
    error: BaseException,
    *,
    provider: str,
) -> Optional[ProviderFatalError]:
    """Return a run-fatal wrapper for non-retryable provider failures."""

    if isinstance(error, ProviderFatalError):
        return error

    status_code = _status_code(error)
    error_code = _error_code(error)
    message = str(error).strip() or type(error).__name__
    normalized_message = " ".join(message.lower().split())
    fatal = (
        status_code in FATAL_STATUS_CODES
        or error_code in FATAL_ERROR_CODES
        or any(marker in normalized_message for marker in FATAL_MESSAGE_MARKERS)
    )
    if not fatal:
        return None

    return ProviderFatalError(
        message,
        provider=provider,
        status_code=status_code,
        reason_code=_reason_code(status_code, error_code, normalized_message),
    )
