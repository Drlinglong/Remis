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
        push=True,
    ):
        self.calls.append({
            "task_id": task_id,
            "status": status,
            "message": message,
            "progress": progress,
            "summary": summary,
            "fields": fields,
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
