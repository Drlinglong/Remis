"""Small runtime bridge shared by model-backed router entry points."""

from __future__ import annotations

from typing import Any, Callable

from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


def runtime_for_selection(
    provider: str | None,
    model: str | None,
) -> ProviderRuntimeSnapshot:
    return resolve_provider_runtime_snapshot(provider, model)


def handler_for_runtime(
    runtime: ProviderRuntimeSnapshot,
    handler_factory: Callable[..., Any],
) -> Any:
    return handler_factory(
        runtime.adapter_id,
        model_name=runtime.model_id,
        **runtime.handler_kwargs(),
    )


def bind_runtime(request: Any, runtime: ProviderRuntimeSnapshot) -> Any:
    request._provider_runtime = runtime
    return request


def agent_workshop_task_fields(
    request: Any,
    operation_fingerprint: str,
    runtime: ProviderRuntimeSnapshot,
) -> dict[str, Any]:
    metadata = runtime.safe_metadata()
    provider_metadata = {
        "issue_count": len(request.issues),
        "api_provider": request.api_provider,
        "api_model": request.api_model,
        "provider_runtime": metadata,
    }
    return {
        "kind": "agent_workshop",
        "project_id": request.project_id,
        "title": "Format Repair",
        "source_route": "/agent-workshop",
        "created_by": request.created_by.model_dump(),
        "blocking": True,
        "blocking_reason": (
            "Format Repair is repairing project files. "
            "Conflicting writes are blocked until it finishes."
        ),
        "idempotency_key": request.idempotency_key,
        "operation_fingerprint": operation_fingerprint,
        "workflow_context": {"mode": "repair", "project_id": request.project_id, **provider_metadata},
        "approval_snapshot": {"approved": True, **provider_metadata},
        "checkpoint": {
            "available": False,
            "resume_supported": False,
            "stage": "queued",
            "metadata": provider_metadata,
        },
    }
