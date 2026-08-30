"""Experimental stdio MCP server backed by the Remis localhost Agent API."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import ValidationError

from scripts.mcp_adapter.client import AgentApiClient, AgentApiFailure
from scripts.mcp_adapter.models import (
    AdapterError,
    AdapterResult,
    CapabilitiesData,
    JobData,
    PreflightData,
    ProjectSummaryData,
    TranslationPlanData,
    TranslationPlanInput,
)

LOGGER = logging.getLogger("remis.mcp")
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
PLAN_ONLY = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
APPROVED_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _success(
    operation: str,
    data: Any,
    *,
    preflight: dict[str, Any] | None = None,
) -> AdapterResult:
    return AdapterResult(ok=True, operation=operation, data=data, preflight=preflight)


def _failure(operation: str, failure: AgentApiFailure) -> CallToolResult:
    result = AdapterResult(ok=False, operation=operation, error=failure.error)
    structured = result.model_dump(mode="json")
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(structured, ensure_ascii=False))],
        structuredContent=structured,
        isError=True,
    )


def _checked_id(value: str, kind: str) -> str:
    if IDENTIFIER_PATTERN.fullmatch(value):
        return value
    raise AgentApiFailure(
        AdapterError(
            code=f"invalid_{kind}_id",
            message=f"The {kind}_id must contain only letters, digits, hyphens, or underscores.",
            action=f"Use a current {kind}_id returned by the Remis Agent API.",
        )
    )


class RemisMcpTools:
    """Focused tool handlers over an injectable Agent API client."""

    def __init__(self, api: AgentApiClient) -> None:
        self.api = api

    async def remis_preflight(
        self, provider_id: str | None = None
    ) -> AdapterResult[PreflightData]:
        """Check Remis reachability, release status, and provider readiness. No side effects."""
        try:
            return _success("preflight", await self.api.preflight(provider_id))
        except AgentApiFailure as failure:
            return _failure("preflight", failure)  # type: ignore[return-value]

    async def remis_capabilities(self) -> AdapterResult[CapabilitiesData]:
        """Return sanitized allowlisted Agent capabilities; never returns provider secrets."""
        try:
            return _success(
                "capabilities", await self.api.request("GET", "/capabilities")
            )
        except AgentApiFailure as failure:
            return _failure("capabilities", failure)  # type: ignore[return-value]

    async def remis_list_projects(
        self, status: str | None = None
    ) -> AdapterResult[list[ProjectSummaryData]]:
        """Read sanitized project summaries. Runs preflight first and makes no changes."""
        try:
            preflight, data = await self.api.governed_request(
                "GET", "/projects", params={"status": status} if status else None
            )
            return _success("list_projects", data, preflight=preflight)
        except AgentApiFailure as failure:
            return _failure("list_projects", failure)  # type: ignore[return-value]

    async def remis_inspect_project(
        self, project_id: str
    ) -> AdapterResult[ProjectSummaryData]:
        """Read one registered project's status, validation summary, and allowed actions."""
        try:
            checked_project_id = _checked_id(project_id, "project")
            preflight, data = await self.api.governed_request(
                "GET", f"/projects/{checked_project_id}/status"
            )
            return _success("inspect_project", data, preflight=preflight)
        except AgentApiFailure as failure:
            return _failure("inspect_project", failure)  # type: ignore[return-value]

    async def remis_create_translation_plan(
        self,
        project_id: str,
        target_lang_codes: list[str] | None = None,
        api_provider: str = "lm_studio",
        model: str = "local-model",
        batch_size_limit: int | None = None,
        concurrency_limit: int | None = 1,
        rpm_limit: int | None = 40,
        use_resume: bool = True,
        use_main_glossary: bool = True,
        translation_context_mode: Literal["none", "glossaries", "archive"] = "archive",
        embedded_workshop_enabled: bool = True,
        dry_run: bool = False,
    ) -> AdapterResult[TranslationPlanData]:
        """Create an expiring server plan only; does not run a model or write translation output."""
        try:
            plan_input = TranslationPlanInput(
                project_id=_checked_id(project_id, "project"),
                target_lang_codes=(
                    target_lang_codes
                    if target_lang_codes is not None
                    else ["zh-CN"]
                ),
                api_provider=api_provider,
                model=model,
                batch_size_limit=batch_size_limit,
                concurrency_limit=concurrency_limit,
                rpm_limit=rpm_limit,
                use_resume=use_resume,
                use_main_glossary=use_main_glossary,
                translation_context_mode=translation_context_mode,
                embedded_workshop_enabled=embedded_workshop_enabled,
                dry_run=dry_run,
            )
            preflight, data = await self.api.governed_request(
                "POST",
                "/jobs/plan",
                provider_id=api_provider,
                json=plan_input.model_dump(mode="json"),
            )
            return _success("create_translation_plan", data, preflight=preflight)
        except ValidationError:
            failure = AgentApiFailure(
                AdapterError(
                    code="invalid_plan_request",
                    message="The translation plan input does not match the Agent API contract.",
                    action="Review the discovered tool schema and correct the plan parameters.",
                )
            )
            return _failure("create_translation_plan", failure)  # type: ignore[return-value]
        except AgentApiFailure as failure:
            return _failure("create_translation_plan", failure)  # type: ignore[return-value]

    async def remis_start_approved_plan(
        self,
        plan_id: str,
        approved: bool = False,
    ) -> AdapterResult[JobData]:
        """Start one exact server plan after explicit approval.

        This may spend model credits and write translation output. The backend
        enforces approved=true, TTL, and one-time consumption.
        """
        try:
            checked_plan_id = _checked_id(plan_id, "plan")
            preflight, data = await self.api.governed_request(
                "POST", "/jobs", json={"plan_id": checked_plan_id, "approved": approved}
            )
            return _success("start_approved_plan", data, preflight=preflight)
        except AgentApiFailure as failure:
            return _failure("start_approved_plan", failure)  # type: ignore[return-value]

    async def remis_get_job(self, job_id: str) -> AdapterResult[JobData]:
        """Read persisted status, progress, validation, result, and allowed actions.

        A start response is not completion; only persisted terminal status is.
        """
        try:
            checked_job_id = _checked_id(job_id, "job")
            preflight, data = await self.api.governed_request(
                "GET", f"/jobs/{checked_job_id}"
            )
            return _success("get_job", data, preflight=preflight)
        except AgentApiFailure as failure:
            return _failure("get_job", failure)  # type: ignore[return-value]


def create_server(client: AgentApiClient | None = None) -> MCPServer:
    """Build an injectable MCP server; production defaults remain localhost-only."""
    server = MCPServer(
        "remis-localhost-agent",
        title="Remis Localhost Agent Adapter",
        description="Governed MCP tools backed only by the Remis localhost Agent API.",
        instructions=(
            "Call remis_preflight before a workflow. Planning has no translation execution "
            "side effect. Never call remis_start_approved_plan with approved=true until the "
            "user has explicitly approved the exact unexpired plan. A successful start only "
            "means the API accepted the operation; use remis_get_job for persisted terminal state."
        ),
        version="0.1.0-experimental",
        log_level="WARNING",
    )
    tools = RemisMcpTools(client or AgentApiClient())
    registrations = (
        (tools.remis_preflight, READ_ONLY),
        (tools.remis_capabilities, READ_ONLY),
        (tools.remis_list_projects, READ_ONLY),
        (tools.remis_inspect_project, READ_ONLY),
        (tools.remis_create_translation_plan, PLAN_ONLY),
        (tools.remis_start_approved_plan, APPROVED_WRITE),
        (tools.remis_get_job, READ_ONLY),
    )
    for handler, tool_annotations in registrations:
        server.tool(annotations=tool_annotations, structured_output=True)(handler)

    return server


def main() -> None:
    """Run the local adapter over stdio without writing logs to stdout."""
    logging.basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
