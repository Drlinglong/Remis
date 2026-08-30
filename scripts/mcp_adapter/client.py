"""Localhost-only HTTP client for the governed Remis Agent API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import httpx

from scripts.mcp_adapter.models import AdapterError

DEFAULT_PORT = 1453
DEFAULT_TIMEOUT_SECONDS = 10.0
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set-cookie",
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "secret",
    }
)
SENSITIVE_NORMALIZED_KEYS = frozenset(
    item.replace("-", "").replace("_", "") for item in SENSITIVE_KEYS
)


class AgentApiFailure(RuntimeError):
    """Carries a stable, safe error across the MCP boundary."""

    def __init__(self, error: AdapterError):
        super().__init__(error.message)
        self.error = error


def _configured_port() -> int:
    raw = os.getenv("REMIS_BACKEND_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw)
    except ValueError as exc:
        raise AgentApiFailure(
            AdapterError(
                code="invalid_backend_port",
                message="REMIS_BACKEND_PORT must be an integer between 1 and 65535.",
                action="Correct REMIS_BACKEND_PORT in the MCP host configuration.",
            )
        ) from exc
    if not 1 <= port <= 65535:
        raise AgentApiFailure(
            AdapterError(
                code="invalid_backend_port",
                message="REMIS_BACKEND_PORT must be an integer between 1 and 65535.",
                action="Correct REMIS_BACKEND_PORT in the MCP host configuration.",
            )
        )
    return port


def sanitize(value: Any) -> Any:
    """Remove secret-bearing fields without altering normal Agent API data."""
    if isinstance(value, Mapping):
        return {
            str(key): sanitize(item)
            for key, item in value.items()
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "").replace("_", "")
    return (
        normalized in SENSITIVE_NORMALIZED_KEYS
        or normalized.endswith("apikey")
        or normalized.endswith("token")
        or "secret" in normalized
    )


class AgentApiClient:
    """Calls only the allowlisted localhost Agent API routes."""

    def __init__(
        self,
        *,
        port: int | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        resolved_port = _configured_port() if port is None else port
        if not 1 <= resolved_port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        self.base_url = f"http://127.0.0.1:{resolved_port}/api/agent"
        self.timeout = httpx.Timeout(timeout_seconds)
        self.transport = transport

    async def preflight(self, provider_id: str | None = None) -> dict[str, Any]:
        params = {"provider_id": provider_id} if provider_id else None
        payload = await self.request("GET", "/preflight", params=params)
        if not isinstance(payload, dict):
            raise AgentApiFailure(
                AdapterError(
                    code="invalid_backend_response",
                    message="Remis preflight returned an unexpected response shape.",
                    action="Check the running Remis version and its Agent API logs.",
                )
            )
        return payload

    async def governed_request(
        self,
        method: str,
        path: str,
        *,
        provider_id: str | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], Any]:
        preflight = await self.preflight(provider_id)
        return preflight, await self.request(method, path, json=json, params=params)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if not path.startswith("/") or ".." in path:
            raise ValueError("Agent API path must be an absolute, contained route")
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
                headers={"Accept": "application/json"},
            ) as client:
                response = await client.request(method, path, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise AgentApiFailure(
                AdapterError(
                    code="remis_timeout",
                    message="The localhost Remis Agent API did not respond before the timeout.",
                    retryable=True,
                    action="Confirm Remis is responsive, then retry the same safe operation.",
                )
            ) from exc
        except httpx.RequestError as exc:
            raise AgentApiFailure(
                AdapterError(
                    code="remis_unreachable",
                    message="The localhost Remis Agent API is not reachable.",
                    retryable=True,
                    action=(
                        "Start Remis, or run scripts\\developer_tools\\windows\\run-dev.bat "
                        "from this checkout, then retry preflight."
                    ),
                )
            ) from exc

        if response.is_redirect:
            raise AgentApiFailure(
                AdapterError(
                    code="backend_redirect_refused",
                    message="Remis returned a redirect; the localhost adapter will not follow it.",
                    http_status=response.status_code,
                    action="Check that REMIS_BACKEND_PORT points to the Remis backend.",
                )
            )
        if response.is_error:
            raise AgentApiFailure(_backend_error(response))
        try:
            return sanitize(response.json())
        except ValueError as exc:
            raise AgentApiFailure(
                AdapterError(
                    code="invalid_backend_response",
                    message="Remis returned a non-JSON response.",
                    http_status=response.status_code,
                    action="Check the running Remis version and its Agent API logs.",
                )
            ) from exc


def _backend_error(response: httpx.Response) -> AdapterError:
    try:
        payload = sanitize(response.json())
    except ValueError:
        payload = {}
    detail = payload.get("detail", {}) if isinstance(payload, dict) else {}
    if not isinstance(detail, dict):
        detail = {}
    return AdapterError(
        code=str(detail.get("code") or "backend_http_error"),
        message=str(detail.get("message") or "The Remis Agent API rejected the operation."),
        retryable=bool(detail.get("retryable", response.status_code >= 500)),
        http_status=response.status_code,
        action=_error_action(str(detail.get("code") or "")),
        details=detail.get("details", {}) if isinstance(detail.get("details"), dict) else {},
    )


def _error_action(code: str) -> str | None:
    return {
        "approval_required": (
            "Review the exact plan and call again with approved=true only after "
            "explicit approval."
        ),
        "plan_expired": "Create a new translation plan and obtain fresh approval.",
        "plan_already_used": (
            "Do not replay the consumed plan; inspect its job or create a new plan."
        ),
        "plan_not_found": "Create a new plan; do not reconstruct an unknown plan identifier.",
        "project_not_found": "List projects and use a current project_id.",
        "job_not_found": "Use the persisted job_id returned by an approved start operation.",
    }.get(code)
