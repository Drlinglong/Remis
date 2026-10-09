"""Restart interruption policy for persisted tasks that lost their worker."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def restart_recovery(task: Dict[str, Any]) -> Optional[tuple[str, str, bool]]:
    """Return restart interruption messaging for work that has no live worker."""

    kind = task.get("kind")
    checkpoint = task.get("checkpoint") or {}
    if kind == "initial_translation":
        checkpoint_available = checkpoint.get("available") is True
        return (
            "The app restarted before this initial translation finished.",
            (
                "The previous translation worker is no longer running. "
                "Resume from the saved checkpoint or start a new translation."
                if checkpoint_available
                else "The previous translation worker is no longer running. "
                "Return to Initial Translation to check for saved progress or start again."
            ),
            checkpoint_available,
        )
    if kind == "deployment":
        return (
            "The app restarted before this deployment finished.",
            "This deployment cannot resume automatically. The target folder may be "
            "incomplete. Review it, then create a fresh preview and deploy again.",
            False,
        )
    if kind == "reference_library_maintenance":
        return (
            "The app restarted before official reference library maintenance finished.",
            "This reference library task cannot resume automatically. Review the current library state before retrying.",
            False,
        )
    if kind in {"neologism_mining", "context_archive_analysis"}:
        return (
            "The app restarted before this context-analysis task finished.",
            "This context-analysis task cannot resume automatically. Start it again.",
            False,
        )
    if (
        kind in {"agent_workshop", "agent_workshop_batch"}
        and checkpoint.get("resume_supported") is False
    ):
        return (
            "The app restarted before this repair task finished.",
            "This Agent Workshop task cannot resume automatically. Return to the workflow and review current validation results before retrying.",
            False,
        )
    return None


def mark_restart_interrupted(
    task: Dict[str, Any],
    message: str,
    attention_reason: str,
    *,
    preserve_checkpoint: bool = False,
) -> None:
    now = _utc_now_iso()
    task["status"] = "interrupted"
    task["updated_at"] = now
    task["finished_at"] = now
    task["message"] = message
    task["attention_reason"] = attention_reason
    task.setdefault("progress", {})["stage"] = "Interrupted"
    if not preserve_checkpoint:
        checkpoint = task.setdefault("checkpoint", {})
        checkpoint["available"] = False
        checkpoint["stage"] = "interrupted"
        checkpoint["updated_at"] = now
