import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from scripts.core.services.agent_workshop_run_service import (
    AgentWorkshopRunCoordinator,
)
from scripts.routers.agent_workshop import BatchResultItem, FixBatchResponse
from scripts.shared import task_state
from scripts.shared.state import tasks
from scripts.web_server import app


client = TestClient(app)


def _issue(index: int) -> dict:
    return {
        "file_name": "events/test_l_simp_chinese.yml",
        "key": f"demo.{index}:0",
        "source_str": f"Source {index}",
        "target_str": f"坏译文 {index}",
        "error_type": "validation_error",
        "details": "broken",
    }


def _run_payload(*, project_id: str, issue_count: int, concurrency: int = 2) -> dict:
    return {
        "project_id": project_id,
        "api_provider": "gemini",
        "api_model": "gemini-3-flash-preview",
        "approval": {
            "approved": True,
            "issue_count": issue_count,
            "api_provider": "gemini",
            "api_model": "gemini-3-flash-preview",
        },
        "idempotency_key": f"workshop-run-{project_id}",
        "batch_size_limit": 1,
        "concurrency_limit": concurrency,
        "rpm_limit": 600_000,
        "max_retries": 3,
        "issues": [_issue(index) for index in range(issue_count)],
    }


def test_fix_run_concurrent_workers_preserve_all_batch_results():
    tasks.clear()
    active_calls = 0
    maximum_active_calls = 0
    release_calls = asyncio.Event()

    async def fake_run_batch(request):
        nonlocal active_calls, maximum_active_calls
        active_calls += 1
        maximum_active_calls = max(maximum_active_calls, active_calls)
        if maximum_active_calls == 2:
            release_calls.set()
        await asyncio.wait_for(release_calls.wait(), timeout=1)
        await asyncio.sleep(0)
        active_calls -= 1
        issue = request.issues[0]
        return FixBatchResponse(
            results=[
                BatchResultItem(
                    file_name=issue["file_name"],
                    key=issue["key"],
                    suggested_fix=f"修复 {issue['key']}",
                    status="SUCCESS",
                    parity_message="Validation passed",
                )
            ],
        )

    with (
        patch(
            "scripts.routers.agent_workshop._require_repairable_project",
            new_callable=AsyncMock,
            return_value={"project_id": "p-run-concurrent", "status": "active"},
        ),
        patch("scripts.routers.agent_workshop._run_fix_batch", side_effect=fake_run_batch),
    ):
        response = client.post(
            "/api/agent-workshop/fix-run",
            json=_run_payload(project_id="p-run-concurrent", issue_count=4),
        )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    assert maximum_active_calls == 2
    assert tasks[task_id]["status"] == "completed"
    assert tasks[task_id]["summary"]["completed"] == 4
    assert tasks[task_id]["summary"]["successCount"] == 4
    assert tasks[task_id]["summary"]["failedCount"] == 0
    assert len(tasks[task_id]["summary"]["results"]) == 4
    assert len(tasks[task_id]["result"]["metadata"]["batch_task_ids"]) == 4


def test_fix_run_batch_exception_preserves_success_and_marks_review_state():
    tasks.clear()

    async def fake_run_batch(request):
        issue = request.issues[0]
        if issue["key"] == "demo.1:0":
            raise RuntimeError("provider batch failed")
        return FixBatchResponse(
            results=[
                BatchResultItem(
                    file_name=issue["file_name"],
                    key=issue["key"],
                    suggested_fix="修复",
                    status="SUCCESS",
                    parity_message="Validation passed",
                )
            ],
        )

    with (
        patch(
            "scripts.routers.agent_workshop._require_repairable_project",
            new_callable=AsyncMock,
            return_value={"project_id": "p-run-batch-failure", "status": "active"},
        ),
        patch("scripts.routers.agent_workshop._run_fix_batch", side_effect=fake_run_batch),
    ):
        response = client.post(
            "/api/agent-workshop/fix-run",
            json=_run_payload(project_id="p-run-batch-failure", issue_count=2),
        )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    assert tasks[task_id]["status"] == "partial_failed"
    assert tasks[task_id]["summary"]["completed"] == 2
    assert tasks[task_id]["summary"]["successCount"] == 1
    assert tasks[task_id]["summary"]["failedCount"] == 1
    assert tasks[f"{task_id}:batch:1"]["status"] == "completed"
    assert tasks[f"{task_id}:batch:2"]["status"] == "failed"
    assert tasks[f"{task_id}:batch:2"]["result"]["summary"] == (
        "No repairs from this batch were applied."
    )


async def test_coordinator_rate_limit_uses_injected_clock_without_real_waits():
    tasks.clear()
    task_id = "rate-limited-run"
    task_state.create_task(task_id, status="queued")
    current_time = 0.0
    waits: list[float] = []

    def monotonic() -> float:
        return current_time

    async def sleep(seconds: float) -> None:
        nonlocal current_time
        waits.append(seconds)
        current_time += seconds

    async def run_batch(request):
        issue = request.issues[0]
        return FixBatchResponse(
            results=[
                BatchResultItem(
                    file_name=issue["file_name"],
                    key=issue["key"],
                    suggested_fix="修复",
                    status="SUCCESS",
                    parity_message="Validation passed",
                )
            ],
        )

    request = SimpleNamespace(
        project_id="p-rate-limited",
        api_provider="gemini",
        api_model="gemini-3-flash-preview",
        issues=[_issue(index) for index in range(3)],
        batch_size_limit=1,
        concurrency_limit=1,
        rpm_limit=60,
        max_retries=3,
        created_by=SimpleNamespace(
            model_dump=lambda: {"kind": "user", "label": "User"}
        ),
    )
    coordinator = AgentWorkshopRunCoordinator(
        task_id=task_id,
        request=request,
        task_store=task_state,
        batch_runner=run_batch,
        batch_request_factory=lambda batch, max_retries: SimpleNamespace(
            issues=batch,
            max_retries=max_retries,
        ),
        sleep=sleep,
        monotonic=monotonic,
        wall_time=lambda: current_time,
    )

    await coordinator.run()

    assert waits == [1.0, 1.0]
    assert tasks[task_id]["status"] == "completed"
    assert tasks[task_id]["summary"]["durationMs"] == 2000
