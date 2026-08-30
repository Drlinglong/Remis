from __future__ import annotations

import pytest

from scripts.core.copilot import task_status
from scripts.core.copilot.help_agent import task_ids_requiring_status_lookup
from scripts.schemas.agent import AgentValidationSummary


TASK_ID = "fe6a41a6-795c-4b24-86bb-404113c5a34d"


def test_status_question_uses_most_recent_task_id_from_conversation():
    history = [
        {"role": "assistant", "content": f"翻译任务已启动，任务 ID 为 {TASK_ID}。"},
        {"role": "user", "content": "翻译进度如何？"},
    ]

    assert task_ids_requiring_status_lookup(history) == [TASK_ID]


def test_general_task_center_question_does_not_force_status_lookup():
    history = [
        {"role": "assistant", "content": f"上次任务 ID 为 {TASK_ID}。"},
        {"role": "user", "content": "任务中心在哪里？"},
    ]

    assert task_ids_requiring_status_lookup(history) == []


@pytest.mark.asyncio
async def test_completed_task_returns_authoritative_progress_and_validation(monkeypatch):
    persisted_task = {
        "id": TASK_ID,
        "project_id": "project-demo",
        "kind": "initial_translation",
        "status": "completed",
        "progress": {
            "current": 4,
            "total": 4,
            "percent": 100,
            "successful_batches": 4,
            "failed_batches": 0,
        },
        "output_dirs": [r"C:\safe-demo\my_translation"],
    }
    monkeypatch.setattr(task_status.task_state, "get_task", lambda task_id: persisted_task)
    monkeypatch.setattr(
        task_status.agent_registry,
        "get_job",
        lambda task_id: {"project_id": "project-demo", "kind": "initial_translation"},
    )

    async def validation_summary(project_id):
        assert project_id == "project-demo"
        return AgentValidationSummary(
            errors=0,
            warnings=0,
            human_review_items=0,
            total=0,
            available=True,
        )

    monkeypatch.setattr(task_status, "_validation_summary", validation_summary)

    result = await task_status.get_copilot_task_status(TASK_ID)

    assert result["found"] is True
    assert result["status"] == "completed"
    assert result["progress"] == {
        "completed_files": 4,
        "total_files": 4,
        "percent": 100,
        "current_file": "",
        "stage": "",
        "successful_batches": 4,
        "failed_batches": 0,
    }
    assert result["validation"]["available"] is True
    assert result["output_paths"] == [r"C:\safe-demo\my_translation"]
    assert result["allowed_actions"] == ["inspect_validation", "approve_export"]
    assert result["recovery_source"] == "task_center_ledger"
    assert result["read_only"] is True


@pytest.mark.asyncio
async def test_completed_task_exposes_persisted_glossary_human_review_evidence(monkeypatch):
    persisted_task = {
        "project_id": "project-demo",
        "kind": "initial_translation",
        "status": "completed",
        "progress": {
            "current": 3,
            "total": 3,
            "percent": 100,
            "glossary_issues": 3,
            "glossary_issue_details": [
                {
                    "requires_human_review": True,
                    "severity": "warning",
                    "error_code": "glossary_mismatch",
                    "file_name": "demo.yml",
                    "batch_id": index,
                    "source_term": f"source-{index}",
                    "target_term": f"target-{index}",
                }
                for index in range(3)
            ],
        },
        "output_dirs": [r"C:\safe-demo\my_translation"],
    }
    monkeypatch.setattr(task_status.task_state, "get_task", lambda task_id: persisted_task)
    monkeypatch.setattr(
        task_status.agent_registry,
        "get_job",
        lambda task_id: {"project_id": "project-demo", "kind": "initial_translation"},
    )

    async def no_sidecar_validation(project_id):
        return AgentValidationSummary()

    monkeypatch.setattr(task_status, "_validation_summary", no_sidecar_validation)

    result = await task_status.get_copilot_task_status(TASK_ID)

    assert result["status"] == "completed"
    assert result["validation"] == {
        "errors": 0,
        "warnings": 0,
        "human_review_items": 3,
        "total": 3,
        "available": True,
        "truncated": False,
    }
    assert "approve_export" not in result["allowed_actions"]


@pytest.mark.asyncio
async def test_partial_failure_is_not_reported_as_completed(monkeypatch):
    persisted_task = {
        "id": TASK_ID,
        "project_id": "project-demo",
        "kind": "initial_translation",
        "status": "partial_failed",
        "message": "One batch failed validation.",
        "progress": {"current": 3, "total": 4, "percent": 75, "failed_batches": 1},
    }
    monkeypatch.setattr(task_status.task_state, "get_task", lambda task_id: persisted_task)
    monkeypatch.setattr(task_status.agent_registry, "get_job", lambda task_id: None)

    async def no_validation(project_id):
        return AgentValidationSummary()

    monkeypatch.setattr(task_status, "_validation_summary", no_validation)

    result = await task_status.get_copilot_task_status(TASK_ID)

    assert result["status"] == "partial_failed"
    assert result["failure_summary"] == "One batch failed validation."
    assert result["progress"]["failed_batches"] == 1
    assert "approve_export" not in result["allowed_actions"]


@pytest.mark.asyncio
async def test_missing_task_returns_stable_machine_code(monkeypatch):
    monkeypatch.setattr(task_status.task_state, "get_task", lambda task_id: None)
    monkeypatch.setattr(task_status.agent_registry, "get_job", lambda task_id: None)

    assert await task_status.get_copilot_task_status(TASK_ID) == {
        "found": False,
        "code": "task_not_found",
        "task_id": TASK_ID,
        "retryable": False,
    }
