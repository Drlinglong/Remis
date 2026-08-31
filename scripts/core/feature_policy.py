"""Build-channel feature policy for unfinished production workflows."""

from scripts.app_settings import BUILD_PROFILE


def mod_archive_enabled() -> bool:
    """Expose project archive workflows only in the isolated Agent Preview build."""
    return BUILD_PROFILE.channel == "agent-preview"


def checkpoint_resume_enabled() -> bool:
    """Keep checkpoint consumption out of stable builds until its state model is rebuilt."""
    return BUILD_PROFILE.channel == "agent-preview"


def enforce_checkpoint_resume_policy(requested: bool) -> bool:
    return bool(requested and checkpoint_resume_enabled())


def apply_translation_request_policy(request) -> dict | None:
    """Mutate a translation request to the safe policy for its build channel."""
    warning = None
    if request.translation_context_mode == "archive" and not mod_archive_enabled():
        request.translation_context_mode = "glossaries"
        request.use_project_context = False
        request.context_release_id = None
        warning = {
            "code": "project_archive_disabled",
            "message": "Project Archive is disabled in the stable build. Translation will continue with glossaries.",
        }
    if not checkpoint_resume_enabled():
        request.use_resume = False
    return warning


def apply_agent_capability_policy(actions: dict) -> dict:
    """Project build-channel policy into the public Agent capability contract."""
    result = {name: dict(capability) for name, capability in actions.items()}
    result["resume_from_checkpoint"]["supported"] = checkpoint_resume_enabled()
    if not checkpoint_resume_enabled():
        result["resume_from_checkpoint"]["reason"] = (
            "Checkpoint resume is temporarily disabled in the stable build."
        )
    result["cancel"] = {
        "supported": True,
        "requires_approval": True,
        "endpoint": "/api/tasks/{task_id}/cancel",
        "task_kinds": ["initial_translation", "translation"],
    }
    if not mod_archive_enabled():
        for name in (
            "read_context_release",
            "read_effective_context",
            "read_context_traceability",
            "remove_context_archive",
            "context_analysis",
        ):
            result[name]["supported"] = False
            result[name]["reason"] = "Project Archive is disabled in the stable build."
    return result
