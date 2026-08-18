from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import StdioServerParameters
from mcp.client import Client
from mcp.client.stdio import stdio_client

from scripts.mcp_adapter.client import AgentApiClient
from scripts.mcp_adapter.server import create_server

EXPECTED_TOOLS = {
    "remis_preflight",
    "remis_capabilities",
    "remis_list_projects",
    "remis_inspect_project",
    "remis_create_translation_plan",
    "remis_start_approved_plan",
    "remis_get_job",
}
READY_PREFLIGHT = {
    "status": "ready",
    "release_check": {"checked": True, "update_available": False},
    "provider_setup": {"setup_required": False},
    "required_before_every_workflow": True,
    "allowed_actions": ["continue"],
}


def response(request: httpx.Request, payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


def result_data(result) -> dict[str, Any]:
    assert result.structured_content is not None
    return result.structured_content


@pytest.mark.asyncio
async def test_tool_discovery_exposes_allowlist_schemas_and_safety_annotations():
    async with Client(create_server()) as client:
        listed = await client.list_tools()

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == EXPECTED_TOOLS
    assert all(tool.input_schema for tool in tools.values())
    assert all(tool.output_schema for tool in tools.values())
    assert tools["remis_list_projects"].annotations.read_only_hint is True
    assert tools["remis_create_translation_plan"].annotations.destructive_hint is False
    assert tools["remis_start_approved_plan"].annotations.destructive_hint is True
    job_output_schema = json.dumps(tools["remis_get_job"].output_schema)
    assert "partial_failed" in job_output_schema
    assert "allowed_actions" in job_output_schema
    assert "validation" in job_output_schema
    context_schema = tools["remis_create_translation_plan"].input_schema["properties"]
    assert context_schema["translation_context_mode"]["enum"] == [
        "none",
        "glossaries",
        "archive",
    ]


@pytest.mark.asyncio
async def test_preflight_success_uses_real_mcp_call_tool():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        assert request.url.path == "/api/agent/preflight"
        return response(request, READY_PREFLIGHT)

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool("remis_preflight", {})

    assert result.is_error is False
    assert result_data(result)["data"]["status"] == "ready"


@pytest.mark.asyncio
async def test_preflight_unreachable_is_structured_actionable_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("fixture offline", request=request)

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool("remis_preflight", {})

    payload = result_data(result)
    assert result.is_error is True
    assert payload["error"]["code"] == "remis_unreachable"
    assert payload["error"]["retryable"] is True
    assert "run-dev.bat" in payload["error"]["action"]
    assert "fixture offline" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_capabilities_remove_secret_fields_recursively():
    secret = "provider-secret-fixture"

    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            request,
            {
                "service": "remis-agent-api",
                "providers": [
                    {
                        "id": "fixture",
                        "credential_status": "configured",
                        "api_key": secret,
                        "provider_api_key": secret,
                        "nested": {"authorization": f"Bearer {secret}"},
                    }
                ],
                "safety": {"api_keys_returned": False},
            },
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool("remis_capabilities", {})

    payload = result_data(result)
    serialized = json.dumps(payload)
    assert secret not in serialized
    provider = payload["data"]["providers"][0]
    assert "api_key" not in provider
    assert "provider_api_key" not in provider
    assert "authorization" not in provider["nested"]


@pytest.mark.asyncio
async def test_list_and_inspect_projects_use_governed_agent_routes():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        if request.url.path == "/api/agent/projects":
            assert request.url.params["status"] == "active"
            return response(request, [{"project_id": "project-1", "name": "Demo"}])
        if request.url.path == "/api/agent/projects/project-1/status":
            return response(
                request,
                {
                    "project_id": "project-1",
                    "validation": {"errors": 0, "warnings": 1},
                    "allowed_actions": ["create_translation_plan"],
                },
            )
        raise AssertionError(request.url)

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        listed = await client.call_tool("remis_list_projects", {"status": "active"})
        inspected = await client.call_tool(
            "remis_inspect_project", {"project_id": "project-1"}
        )

    assert result_data(listed)["data"][0]["project_id"] == "project-1"
    assert result_data(inspected)["data"]["validation"]["warnings"] == 1
    assert calls == [
        ("GET", "/api/agent/preflight"),
        ("GET", "/api/agent/projects"),
        ("GET", "/api/agent/preflight"),
        ("GET", "/api/agent/projects/project-1/status"),
    ]


@pytest.mark.asyncio
async def test_inspect_missing_project_preserves_backend_error_code():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        return response(
            request,
            {"detail": {"code": "project_not_found", "message": "Project not found"}},
            status=404,
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool(
            "remis_inspect_project", {"project_id": "missing"}
        )

    payload = result_data(result)
    assert result.is_error is True
    assert payload["error"]["code"] == "project_not_found"
    assert payload["error"]["http_status"] == 404


@pytest.mark.asyncio
async def test_illegal_project_id_is_rejected_before_any_http_call():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(request, READY_PREFLIGHT)

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool(
            "remis_inspect_project", {"project_id": "../capabilities"}
        )

    assert result.is_error is True
    assert result_data(result)["error"]["code"] == "invalid_project_id"
    assert calls == 0


@pytest.mark.asyncio
async def test_create_plan_calls_plan_endpoint_only_and_does_not_execute():
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        assert request.url.path == "/api/agent/jobs/plan"
        return response(
            request,
            {
                "plan_id": "plan-1",
                "status": "awaiting_approval",
                "requires_approval": True,
                "allowed_actions": ["approve_start"],
                "expires_at": "2026-08-19T00:10:00Z",
            },
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool(
            "remis_create_translation_plan",
            {
                "project_id": "project-1",
                "target_lang_codes": ["zh-CN"],
                "api_provider": "lm_studio",
                "model": "fixture-model",
            },
        )

    assert result_data(result)["data"]["plan_id"] == "plan-1"
    assert [path for _, path, _ in calls] == [
        "/api/agent/preflight",
        "/api/agent/jobs/plan",
    ]
    assert not any(path == "/api/agent/jobs" for _, path, _ in calls)


@pytest.mark.asyncio
async def test_start_plan_sends_approved_false_and_backend_rejects_it():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        assert json.loads(request.content) == {"plan_id": "plan-1", "approved": False}
        return response(
            request,
            {
                "detail": {
                    "code": "approval_required",
                    "message": "Explicit approval is required.",
                    "retryable": False,
                }
            },
            status=409,
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool(
            "remis_start_approved_plan", {"plan_id": "plan-1", "approved": False}
        )

    assert result.is_error is True
    assert result_data(result)["error"]["code"] == "approval_required"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("plan_expired", 410),
        ("plan_not_found", 404),
        ("plan_already_used", 409),
    ],
)
async def test_start_plan_preserves_expired_invalid_and_consumed_errors(code, status):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        return response(
            request,
            {"detail": {"code": code, "message": "Safe fixture failure"}},
            status=status,
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool(
            "remis_start_approved_plan", {"plan_id": "plan-1", "approved": True}
        )

    assert result.is_error is True
    assert result_data(result)["error"]["code"] == code
    assert result_data(result)["error"]["http_status"] == status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", ["queued", "running", "completed", "partial_failed", "failed"]
)
async def test_get_job_preserves_persisted_statuses(status):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        return response(
            request,
            {
                "job_id": "job-1",
                "status": status,
                "progress": {"percent": 50},
                "validation": {"errors": 1},
                "result": {"types": []},
                "allowed_actions": ["poll"] if status in {"queued", "running"} else [],
            },
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool("remis_get_job", {"job_id": "job-1"})

    assert result_data(result)["data"]["status"] == status


@pytest.mark.asyncio
async def test_backend_500_is_structured_without_echoing_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/agent/preflight":
            return response(request, READY_PREFLIGHT)
        return httpx.Response(
            500,
            text="internal trace with provider-secret-fixture",
            request=request,
        )

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool("remis_get_job", {"job_id": "job-1"})

    serialized = json.dumps(result_data(result))
    assert result.is_error is True
    assert result_data(result)["error"]["code"] == "backend_http_error"
    assert result_data(result)["error"]["retryable"] is True
    assert "provider-secret-fixture" not in serialized


@pytest.mark.asyncio
async def test_timeout_is_structured_and_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    server = create_server(AgentApiClient(transport=httpx.MockTransport(handler)))
    async with Client(server) as client:
        result = await client.call_tool("remis_preflight", {})

    assert result.is_error is True
    assert result_data(result)["error"]["code"] == "remis_timeout"
    assert result_data(result)["error"]["retryable"] is True


class _StubHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler contract
        if self.path.startswith("/api/agent/preflight"):
            payload = READY_PREFLIGHT
        elif self.path == "/api/agent/capabilities":
            payload = {"service": "remis-agent-api", "safety": {"api_keys_returned": False}}
        else:
            payload = {"detail": {"code": "not_found", "message": "Not found"}}
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200 if "detail" not in payload else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):  # noqa: A002 - stdlib handler contract
        return


@pytest.mark.asyncio
async def test_stdio_round_trip_keeps_stdout_protocol_clean():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    env = os.environ.copy()
    env["REMIS_BACKEND_PORT"] = str(httpd.server_port)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "scripts.mcp_adapter.server"],
        cwd=Path(__file__).parents[1],
        env=env,
        encoding="utf-8",
    )
    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
            async with Client(stdio_client(params, errlog=stderr)) as client:
                listed = await client.list_tools()
                called = await client.call_tool("remis_capabilities", {})
            stderr.seek(0)
            stderr_text = stderr.read()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS
    assert called.is_error is False
    assert result_data(called)["data"]["service"] == "remis-agent-api"
    assert "Traceback" not in stderr_text
