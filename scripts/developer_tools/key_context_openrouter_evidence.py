"""Capture auditable OpenRouter completion evidence for benchmark-only calls."""

from __future__ import annotations

from typing import Any

import requests


SAFE_RESPONSE_HEADERS = (
    "cf-ray",
    "x-generation-id",
    "x-openrouter-generation-id",
    "x-request-id",
)


class OpenRouterAttemptError(RuntimeError):
    """A failed attempt that still carries sanitized provider evidence."""

    def __init__(self, message: str, evidence: dict[str, Any]):
        super().__init__(message)
        self.evidence = evidence


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unsupported OpenRouter response type: {type(value).__name__}")


def _safe_headers(headers: Any) -> dict[str, str]:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    return {key: lowered[key] for key in SAFE_RESPONSE_HEADERS if key in lowered}


def _safe_error(exc: Exception) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "message": str(exc),
    }
    response = getattr(exc, "response", None)
    if response is None:
        return evidence
    evidence["http_status"] = getattr(response, "status_code", None)
    try:
        evidence["response_body"] = response.json()
    except Exception:
        evidence["response_body"] = getattr(response, "text", None)
    evidence["response_headers"] = _safe_headers(getattr(response, "headers", {}))
    return evidence


def _fetch_generation(handler: Any, generation_id: str) -> dict[str, Any]:
    """Fetch billing/provider metadata without ever serializing credentials."""
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/generation",
            params={"id": generation_id},
            headers={"Authorization": f"Bearer {handler.client.api_key}"},
            timeout=30,
        )
        payload = response.json()
        return {
            "http_status": response.status_code,
            "response": payload,
        }
    except Exception as exc:
        return {"retrieval_error": _safe_error(exc)}


def call_openrouter_chat_with_evidence(
    handler: Any,
    prompt: str,
    *,
    max_completion_tokens: int = 4000,
    reasoning_effort: str | None = None,
    system_message: str = "You are a professional translator for game mods.",
    request_timeout_seconds: float = 60.0,
) -> tuple[str, dict[str, Any]]:
    """Return completion text plus sanitized response, routing, and billing evidence."""
    provider_config = handler.get_provider_config()
    request_kwargs: dict[str, Any] = {
        "model": provider_config.get("default_model"),
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": max_completion_tokens,
        "extra_headers": {"X-OpenRouter-Metadata": "enabled"},
        "timeout": request_timeout_seconds,
    }
    if reasoning_effort:
        request_kwargs["extra_body"] = {
            "reasoning": {"effort": reasoning_effort}
        }
    else:
        request_kwargs = handler._apply_reasoning_to_openai_kwargs(request_kwargs)

    try:
        raw_http = handler.client.chat.completions.with_raw_response.create(
            **request_kwargs
        )
        response = raw_http.parse()
        payload = _model_dump(response)
        generation_id = payload.get("id")
        evidence = {
            "response_headers": _safe_headers(raw_http.headers),
            "response": payload,
            "generation": (
                _fetch_generation(handler, generation_id) if generation_id else None
            ),
        }
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterAttemptError(
                "OpenRouter returned no final message.content", evidence
            )
        return content.strip(), evidence
    except OpenRouterAttemptError:
        raise
    except Exception as exc:
        raise OpenRouterAttemptError(
            "OpenRouter request failed", {"error": _safe_error(exc)}
        ) from exc
