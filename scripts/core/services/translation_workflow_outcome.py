from scripts.shared import task_state


def workflow_outcome_values(outcome: object) -> tuple[str, str, int]:
    status = getattr(outcome, "status", None)
    if status not in {"completed", "partial_failed"}:
        return "completed", "Translation workflow completed successfully.", 0
    message = (
        getattr(outcome, "message", None)
        or "Translation workflow completed successfully."
    )
    return status, message, int(getattr(outcome, "issue_count", 0) or 0)


def history_completion_description(status: str) -> str:
    if status == "partial_failed":
        return "Translation completed with source-file warnings"
    return "Translation completed successfully"


def record_context_metadata(task_id: str, workflow_result: object) -> None:
    context_metadata = (
        workflow_result.get("context")
        if isinstance(workflow_result, dict)
        else getattr(workflow_result, "context_metadata", None)
    )
    if not context_metadata:
        return
    warning = context_metadata.get("warning") or {}
    task_state.update_task(
        task_id,
        fields={
            "context": context_metadata,
            "result": {"metadata": {"context": context_metadata}},
        },
        append_log=(
            f"Project context warning: {warning.get('code')}."
            if warning.get("code")
            else None
        ),
        push=False,
    )
