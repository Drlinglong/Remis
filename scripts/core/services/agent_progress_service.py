"""Separate file progress from the translation runner's batch counters."""


def project_agent_progress(task, kind):
    progress = task.get("progress") or {}
    files = task.get("file_progress") or {}
    if kind == "dry_run":
        files = {"completed": progress.get("current", 0), "total": progress.get("total", 0), "scope": "project"}
    return {
        "completed_files": files.get("completed"),
        "total_files": files.get("total"),
        "file_count_scope": files.get("scope", "unavailable"),
        "current_batch": int(progress.get("current_batch") or 0),
        "total_batches": int(progress.get("total_batches") or 0),
        "percent": int(progress.get("percent") or 0),
        "current_file": str(progress.get("current_file") or ""),
        "stage": str(progress.get("stage") or ""),
        "successful_batches": int(progress.get("successful_batches") or 0),
        "failed_batches": int(progress.get("failed_batches") or 0),
    }
