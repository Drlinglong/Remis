from __future__ import annotations

import uuid
from typing import Any

from scripts.core.services.steam_workshop_service import SteamWorkshopService
from scripts.core.services.workshop_description_generation_service import (
    GeneratedWorkshopDescription,
    WorkshopDescriptionGenerationService,
)
from scripts.shared import task_state

COVER_TASK_KIND = "steam_workshop_cover"
DESCRIPTION_TASK_KIND = "steam_workshop_description_generation"


def _task_result(
    workspace_id: str,
    asset_type: str,
    version_id: str | None,
    summary: str,
) -> dict[str, Any]:
    return {
        "types": ["steam_workshop_asset"],
        "summary": summary,
        "metadata": {
            "workspace_id": workspace_id,
            "version_id": version_id,
            "asset_type": asset_type,
        },
    }


def _create_asset_task(
    workspace: dict[str, Any],
    *,
    asset_type: str,
    kind: str,
    title: str,
    log_message: str,
    progress: dict[str, Any],
    workflow_context: dict[str, Any] | None = None,
) -> str:
    task_id = str(uuid.uuid4())
    workspace_id = workspace["workspace_id"]
    task_state.create_task(
        task_id,
        status="running",
        log_message=log_message,
        fields={
            "kind": kind,
            "project_id": workspace.get("project_id"),
            "project_context": {
                "name": workspace["name"],
                "game_id": workspace.get("game_id"),
            },
            "title": title,
            "source_route": f"/steam-workshop/{workspace_id}/{asset_type}",
            "created_by": {"type": "user"},
            "blocking": False,
            "progress": progress,
            "workflow_context": workflow_context or {
                "workspace_id": workspace_id,
                "asset_type": asset_type,
            },
            "result": _task_result(
                workspace_id,
                asset_type,
                None,
                f"{title} is running.",
            ),
        },
    )
    return task_id


def _complete_asset_task(
    task_id: str,
    *,
    workspace_id: str,
    asset_type: str,
    version_id: str,
    message: str,
    total: int,
    stage_code: str,
) -> None:
    task_state.update_task(
        task_id,
        status="completed",
        message=message,
        append_log=message,
        progress={
            "current": total,
            "total": total,
            "percent": 100,
            "stage": "Completed",
            "stage_code": stage_code,
        },
        fields={
            "result": _task_result(
                workspace_id,
                asset_type,
                version_id,
                message,
            ),
        },
    )


def _fail_asset_task(
    task_id: str,
    *,
    workspace_id: str,
    asset_type: str,
    message: str,
) -> None:
    task_state.update_task(
        task_id,
        status="failed",
        message=message,
        append_log=message,
        progress={
            "stage": "Failed",
            "stage_code": f"steam_{asset_type}_failed",
            "error_count": 1,
        },
        fields={
            "attention_reason": message,
            "result": _task_result(
                workspace_id,
                asset_type,
                None,
                message,
            ),
        },
    )


def _description_version_data(
    request: dict[str, Any],
    generated: GeneratedWorkshopDescription,
    workspace: dict[str, Any],
) -> dict[str, Any]:
    return {
        "bbcode": generated.bbcode,
        "language": request["language"],
        "source": "model",
        "parent_version_id": workspace.get("current_description_version_id"),
        "metadata": {
            "provider": generated.provider,
            "model": generated.model,
            "workshop_item_id": generated.workshop_item_id,
            "generator": "steam-workshop-description",
        },
        "source_description": generated.source_description,
        "source_description_sha256": generated.source_description_sha256,
    }


def generate_description_candidate(
    *,
    workspace: dict[str, Any],
    workshop_item_id: str,
    request: dict[str, Any],
    workshop_service: SteamWorkshopService,
    generation_service: WorkshopDescriptionGenerationService,
) -> dict[str, Any]:
    workspace_id = workspace["workspace_id"]
    task_id = _create_asset_task(
        workspace,
        asset_type="description",
        kind=DESCRIPTION_TASK_KIND,
        title="Generate Steam Workshop description",
        log_message="Preparing Steam Workshop description generation.",
        progress={
            "current": 0,
            "total": 3,
            "percent": 0,
            "stage": "Reading Steam Workshop description",
            "stage_code": "steam_description_fetching_source",
        },
        workflow_context={
            "workspace_id": workspace_id,
            "asset_type": "description",
            "workshop_item_id": workshop_item_id,
            "provider": request["provider"],
            "model": request["model"],
        },
    )

    def report_stage(stage_code: str, message: str) -> None:
        current = 1 if stage_code == "generating_description" else 0
        task_state.update_task(
            task_id,
            append_log=message,
            progress={
                "current": current,
                "total": 3,
                "percent": 33 if current else 0,
                "stage": message,
                "stage_code": f"steam_description_{stage_code}",
            },
        )

    try:
        generated = generation_service.generate(
            workshop_item_id=workshop_item_id,
            user_template=request["user_template"],
            target_language_name=request["target_language_name"],
            provider=request["provider"],
            model=request["model"],
            progress_callback=report_stage,
        )
        task_state.update_task(
            task_id,
            append_log="Model output received. Saving the candidate version.",
            progress={
                "current": 2,
                "total": 3,
                "percent": 67,
                "stage": "Saving description candidate",
                "stage_code": "steam_description_saving_candidate",
            },
        )
        version = workshop_service.create_description_version(
            workspace_id,
            _description_version_data(request, generated, workspace),
        )
        _complete_asset_task(
            task_id,
            workspace_id=workspace_id,
            asset_type="description",
            version_id=version["version_id"],
            message="Steam Workshop description candidate saved.",
            total=3,
            stage_code="steam_description_completed",
        )
        return {**version, "task_id": task_id}
    except Exception:
        _fail_asset_task(
            task_id,
            workspace_id=workspace_id,
            asset_type="description",
            message="Steam Workshop description generation failed.",
        )
        raise


def save_cover_candidate(
    *,
    workspace: dict[str, Any],
    request: dict[str, Any],
    workshop_service: SteamWorkshopService,
) -> dict[str, Any]:
    workspace_id = workspace["workspace_id"]
    task_id = _create_asset_task(
        workspace,
        asset_type="cover",
        kind=COVER_TASK_KIND,
        title="Save Steam Workshop cover",
        log_message="Validating and saving the Steam Workshop cover.",
        progress={
            "current": 0,
            "total": 1,
            "percent": 0,
            "stage": "Saving cover PNG and canvas",
            "stage_code": "steam_cover_saving",
        },
    )
    try:
        version = workshop_service.create_cover_version(workspace_id, request)
        _complete_asset_task(
            task_id,
            workspace_id=workspace_id,
            asset_type="cover",
            version_id=version["version_id"],
            message="Steam Workshop cover candidate saved.",
            total=1,
            stage_code="steam_cover_completed",
        )
        return {**version, "task_id": task_id}
    except Exception:
        _fail_asset_task(
            task_id,
            workspace_id=workspace_id,
            asset_type="cover",
            message="Steam Workshop cover save failed.",
        )
        raise
