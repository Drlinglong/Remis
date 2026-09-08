from scripts.core.services.context_workflow_status_service import (
    ContextWorkflowStatusService,
)


class StrictTaskBackend:
    """Mirror the shared task API so unsupported keywords fail in tests."""

    def __init__(self):
        self.calls = []

    def update_task(
        self,
        task_id,
        *,
        status=None,
        message=None,
        progress=None,
        summary=None,
        fields=None,
        append_log=None,
        push=True,
    ):
        self.calls.append({
            "task_id": task_id,
            "status": status,
            "message": message,
            "progress": progress,
            "summary": summary,
            "fields": fields,
            "append_log": append_log,
            "push": push,
        })


class RecordingCheckpointPort:
    def __init__(self):
        self.saved = []

    def save_checkpoint(self, task_id, checkpoint):
        self.saved.append((task_id, checkpoint))


def test_completed_archive_result_uses_supported_task_fields_contract():
    backend = StrictTaskBackend()
    checkpoints = RecordingCheckpointPort()
    service = ContextWorkflowStatusService(
        backend,
        checkpoint_port=checkpoints,
    )
    result = {
        "analysis_report": {"input": {"source_items": 347}},
        "context_release_id": "release-1",
    }

    service.mark_completed("project-1", "task-1", result, total_files=1)

    call = backend.calls[-1]
    assert call["status"] == "completed"
    assert call["fields"]["stage_code"] == "completed"
    assert call["fields"]["result"] == {
        "types": ["context_analysis_report"],
        "summary": "Project archive analysis completed.",
        "metadata": {
            "analysis_report": result["analysis_report"],
            "context_release_id": "release-1",
        },
    }
    assert checkpoints.saved[-1][1]["metadata"]["terminal_status"] == "completed"


def test_failed_release_gate_retains_audit_telemetry_in_checkpoint():
    backend = StrictTaskBackend()
    checkpoints = RecordingCheckpointPort()
    service = ContextWorkflowStatusService(
        backend,
        checkpoint_port=checkpoints,
    )
    service.mark_running(
        "project-1",
        "task-1",
        "narrative_context",
        total_files=1,
        source_snapshot_hash="snapshot-1",
        source_items=2,
        total_batches=1,
        workflow_context={
            "provider": "local",
            "model": "local-model",
            "target_lang": "zh-CN",
        },
    )
    telemetry = {
        "workflow_version": "context-workflow-v3",
        "analysis_run_id": "run-1",
        "source_snapshot_hash": "snapshot-1",
        "publication_status": "not_published",
        "model_execution": {
            "call_count": 1,
            "cost": {"amount": 0.12, "currency": "USD", "complete": True},
        },
        "cost": {"amount": 0.12, "currency": "USD", "complete": True},
        "corpus_read_amplification": {"value": 1.5, "call_count": 2},
    }

    service.record_telemetry("project-1", "task-1", telemetry)
    service.mark_failed(
        "project-1", "task-1", total_files=1, processed_files=1,
        error=RuntimeError("release gate rejected incomplete digest"),
    )

    status = service.get_status("project-1")
    assert status["workflow_telemetry"] == telemetry
    assert status["checkpoint"]["metadata"]["workflow_telemetry"] == telemetry
    assert checkpoints.saved[-1][1]["metadata"]["workflow_telemetry"] == telemetry
    assert any(
        call["fields"] == {"workflow_telemetry": telemetry}
        for call in backend.calls
        if call["fields"]
    )
