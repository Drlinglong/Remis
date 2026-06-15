import os
import json
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone

from scripts.shared.services import project_manager
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.schemas.project import (
    CreateProjectRequest, 
    UpdateProjectStatusRequest, 
    UpdateProjectNotesRequest, 
    UpdateProjectMetadataRequest, 
    UpdateFileStatusRequest,
    IncrementalUpdateRequest
)
from scripts.schemas.config import UpdateConfigRequest
from scripts.utils.system_utils import sanitize_for_json
from scripts.utils.validation_logger import ValidationLogger

router = APIRouter()


def _write_incremental_logs(output_dirs: list[str], log_lines: list[str], telemetry: Optional[Dict[str, Any]] = None):
    if not output_dirs:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    telemetry_lines = []
    if telemetry:
        telemetry_lines.append("")
        telemetry_lines.append("[Telemetry]")
        for key, value in telemetry.items():
            if key == "languages" and isinstance(value, list):
                for lang_item in value:
                    target_lang = lang_item.get("target_lang", "unknown")
                    telemetry_lines.append(f"- {target_lang}: {lang_item}")
            else:
                telemetry_lines.append(f"- {key}: {value}")

    content = "\n".join(
        [f"# Incremental Update Log", f"# Generated at: {timestamp}", ""] +
        [str(line) for line in log_lines] +
        telemetry_lines
    )

    for output_dir in output_dirs:
        try:
            os.makedirs(output_dir, exist_ok=True)
            log_path = os.path.join(output_dir, "incremental_update.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except Exception as exc:
            logging.error(f"Failed to write incremental log file to {output_dir}: {exc}")


def _active_validation_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        issue for issue in issues
        if str(issue.get("status", "detected")).lower() not in {"fixed", "ignored"}
    ]


def _load_workshop_issue_file(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Failed to read workshop issue file %s: %s", path, exc)
        return []

    issues = payload.get("issues", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    return [issue for issue in issues if isinstance(issue, dict)]


def _format_file_mtime(path: Path) -> Optional[str]:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None


def _validation_issue_counts(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for issue in issues:
        label = issue.get("error_code") or issue.get("error_type") or "unknown"
        counts[label] = counts.get(label, 0) + 1
    return counts


def _sidecar_candidate(path: Path, kind: str) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    issues = _active_validation_issues(_load_workshop_issue_file(path))
    return {
        "path": str(path),
        "kind": kind,
        "issue_count": len(issues),
        "last_updated_at": _format_file_mtime(path),
    }


def _list_validation_sidecar_candidates(project_root: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen_paths = set()

    def add_candidate(path: Path, kind: str):
        resolved = str(path.resolve(strict=False)).lower()
        if resolved in seen_paths:
            return
        candidate = _sidecar_candidate(path, kind)
        if candidate:
            seen_paths.add(resolved)
            candidates.append(candidate)

    add_candidate(ValidationLogger._get_log_path(project_root), "source")

    try:
        config = ProjectJsonManager(project_root).get_config()
    except Exception as exc:
        logging.warning("Failed to read project translation dirs for validation status: %s", exc)
        config = {}

    for trans_dir in config.get("translation_dirs", []) or []:
        trans_path = Path(trans_dir)
        add_candidate(trans_path / "workshop_issues.json", "translation")
        add_candidate(trans_path / ValidationLogger.FILENAME, "translation")

    candidates.sort(
        key=lambda item: item.get("last_updated_at") or "",
        reverse=True,
    )
    return candidates


def _load_validation_status_from_sidecars(candidates: List[Dict[str, Any]], selected_sidecar_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    selected_candidate = next(
        (candidate for candidate in candidates if candidate.get("kind") == "translation"),
        candidates[0],
    )
    if selected_sidecar_path:
        requested = str(Path(selected_sidecar_path).resolve(strict=False)).lower()
        for candidate in candidates:
            if str(Path(candidate["path"]).resolve(strict=False)).lower() == requested:
                selected_candidate = candidate
                break
        else:
            raise HTTPException(status_code=400, detail="Unknown validation sidecar path")

    selected_path = Path(selected_candidate["path"])

    merged: Dict[tuple, Dict[str, Any]] = {}
    selected_kind = selected_candidate.get("kind")
    source_mode = selected_kind == "source" or selected_sidecar_path
    source_paths = [selected_path] if source_mode else [
        Path(candidate["path"]) for candidate in candidates if candidate.get("kind") == "translation"
    ]

    for candidate_path in source_paths:
        for issue in _load_workshop_issue_file(candidate_path):
            identity = (
                str(issue.get("target_lang", "")),
                str(issue.get("file_name", "")),
                str(issue.get("key", "")),
                str(issue.get("error_code") or issue.get("error_type") or ""),
            )
            if identity not in merged:
                merged[identity] = issue

    active_issues = _active_validation_issues(list(merged.values()))

    return {
        "issues": active_issues,
        "issue_type_counts": _validation_issue_counts(active_issues),
        "sidecar_path": str(selected_path),
        "last_updated_at": _format_file_mtime(selected_path),
    }

@router.get("/api/projects")
async def list_projects(status: Optional[str] = None):
    """Returns a list of all projects, optionally filtered by status."""
    projects = await project_manager.get_projects(status)
    return sanitize_for_json(projects)

@router.post("/api/project/create")
async def create_project(request: CreateProjectRequest):
    """Creates a new project."""
    try:
        if not os.path.exists(request.folder_path):
             raise HTTPException(status_code=404, detail=f"Path not found: {request.folder_path}")

        project = await project_manager.create_project(
            request.name,
            request.folder_path,
            request.game_id,
            request.source_language,
            import_mode=request.import_mode,
        )
        return {"status": "success", "project": project}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/files")
async def list_project_files(project_id: str):
    """Lists files for a given project."""
    return await project_manager.get_project_files(project_id)

@router.post("/api/project/{project_id}/status")
async def update_project_status(project_id: str, request: UpdateProjectStatusRequest):
    """Updates a project's status."""
    try:
        await project_manager.update_project_status(project_id, request.status)
        return {"status": "success", "message": f"Project status updated to {request.status}"}
    except Exception as e:
        logging.error(f"Error updating project status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/metadata")
async def update_project_metadata(project_id: str, request: UpdateProjectMetadataRequest):
    """Updates a project's metadata (game_id, source_language)."""
    try:
        await project_manager.update_project_metadata(project_id, request.game_id, request.source_language)
        return {"status": "success", "message": "Project metadata updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error updating project metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/notes")
async def update_project_notes(project_id: str, request: UpdateProjectNotesRequest):
    """Adds a new note to the project."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        # Also update the summary in DB for backward compatibility
        await project_manager.update_project_notes(project_id, request.notes)
        
        # Add to JSON history
        json_manager = ProjectJsonManager(project['source_path'])
        json_manager.add_note(request.notes)
        
        return {"status": "success", "message": "Note added"}
    except Exception as e:
        logging.error(f"Error updating project notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/notes")
async def list_project_notes(project_id: str):
    """Lists all notes for a project."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        json_manager = ProjectJsonManager(project['source_path'])
        return json_manager.get_notes()
    except Exception as e:
        logging.error(f"Error listing project notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/project/{project_id}/notes/{note_id}")
async def delete_project_note(project_id: str, note_id: str):
    """Deletes a note from a project."""
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        json_manager = ProjectJsonManager(project['source_path'])
        json_manager.delete_note(note_id)
        return {"status": "success", "message": "Note deleted"}
    except Exception as e:
        logging.error(f"Error deleting project note: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/kanban")
async def get_project_kanban(project_id: str):
    try:
        return await project_manager.get_project_kanban(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/kanban")
async def save_project_kanban(project_id: str, kanban_data: Dict[str, Any]):
    try:
        await project_manager.save_project_kanban(project_id, kanban_data)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/project/{project_id}/file/{file_id}/status")
async def update_file_status(project_id: str, file_id: str, request: UpdateFileStatusRequest):
    """Updates a single file's status, syncs with Kanban, and logs activity."""
    try:
        await project_manager.update_file_status_with_kanban_sync(project_id, file_id, request.status)
        return {"status": "success", "message": f"File status updated to {request.status}"}
    except Exception as e:
        logging.error(f"Error updating individual file status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/refresh")
async def refresh_project_files(project_id: str):
    try:
        await project_manager.refresh_project_files(project_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/repair-metadata")
async def repair_project_metadata(project_id: str):
    try:
        return await project_manager.repair_project_metadata(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/upload-translations")
async def upload_project_translations(project_id: str):
    """Scans and uploads existing translations to the archive."""
    try:
        result = await project_manager.upload_project_translations(project_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error uploading translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/config")
async def get_project_config(project_id: str):
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        json_manager = ProjectJsonManager(project['source_path'])
        config = json_manager.get_config()
        return {
            "source_path": project['source_path'],
            "translation_dirs": config.get("translation_dirs", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/config")
async def update_project_config(project_id: str, request: UpdateConfigRequest):
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        new_source_path = request.source_path

        # 1. Update source path if provided (delegates to service layer)
        if new_source_path:
            try:
                await project_manager.update_source_path(project_id, new_source_path)
                # Refresh project data after source path update
                project = await project_manager.get_project(project_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))


        # 2. Update config file (kanban, translation directories, etc)
        json_manager = ProjectJsonManager(project['source_path'])
        
        if request.translation_dirs is not None:
            # Bulk update
            json_manager.update_config({"translation_dirs": request.translation_dirs})
        elif request.action == 'add_dir':
            logging.info(f"Adding translation dir: {request.path}")
            if not os.path.exists(request.path):
                 logging.error(f"Directory not found: {request.path}")
                 raise HTTPException(status_code=404, detail=f"Directory not found: {request.path}")
            if not os.path.isdir(request.path):
                 logging.error(f"Path is not a directory: {request.path}")
                 raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")
            json_manager.add_translation_dir(request.path)
        elif request.action == 'remove_dir':
            json_manager.remove_translation_dir(request.path)
        elif new_source_path is not None:
            # We updated source_path, but didn't provide translation_dirs / action
            pass
        else:
            raise HTTPException(status_code=400, detail="Invalid action or missing parameters")

        await project_manager.refresh_project_files(project_id)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/project/{project_id}")
async def delete_project(project_id: str, delete_files: bool = False):
    """
    Permanently delete a project.
    
    Args:
        project_id: The ID of the project to delete
        delete_files: If True, also delete the source files from disk
    """
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        await project_manager.delete_project(project_id, delete_source_files=delete_files)
        return {"status": "success", "message": f"Project deleted successfully (delete_files={delete_files})"}
    except Exception as e:
        logging.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/history")
async def get_project_history(project_id: str):
    """Retrieves the history/timeline for a project."""
    try:
        return await project_manager.get_project_history(project_id)
    except Exception as e:
        logging.error(f"Error fetching project history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/project/history/{history_id}")
async def delete_history_event(history_id: str):
    """Deletes a specific history event."""
    try:
        await project_manager.delete_history_event(history_id)
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Error deleting history event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/project/{project_id}/check-archive")
async def check_project_archive(project_id: str):
    """Checks if the project has sufficient archive data for incremental update."""
    return await project_manager.check_project_archive(project_id)


@router.get("/api/project/{project_id}/validation-status")
async def get_project_validation_status(project_id: str, sidecar_path: Optional[str] = None):
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_root = project["source_path"]
    candidates = _list_validation_sidecar_candidates(project_root)
    sidecar_status = _load_validation_status_from_sidecars(candidates, sidecar_path)
    if sidecar_status:
        active_issues = sidecar_status["issues"]
        counts = sidecar_status["issue_type_counts"]
        selected_sidecar_path = sidecar_status["sidecar_path"]
        last_updated_at = sidecar_status["last_updated_at"]
    else:
        active_issues = []
        counts = {}
        selected_sidecar_path = str(ValidationLogger._get_log_path(project_root))
        last_updated_at = None

    report_dir = os.path.join(project_root, ".agent_workshop_reports")
    report_count = 0
    if os.path.isdir(report_dir):
        try:
            report_count = len([name for name in os.listdir(report_dir) if name.lower().endswith(".md")])
        except Exception:
            report_count = 0

    return {
        "project_id": project_id,
        "issues_count": len(active_issues),
        "issue_type_counts": counts,
        "last_updated_at": last_updated_at,
        "sidecar_path": selected_sidecar_path,
        "sidecar_candidates": candidates,
        "report_count": report_count,
        "report_dir": report_dir if os.path.isdir(report_dir) else None,
    }

def run_incremental_update_background(task_id: str, project_id: str, request: IncrementalUpdateRequest):
    from scripts.shared import task_state
    import asyncio

    task_state.update_task(
        task_id,
        status="processing",
        progress={
            "percent": 0,
            "stage": "Initializing",
            "stage_code": "initializing",
            "message": "Starting...",
        },
        push=True,
    )
    
    def progress_callback(data: Dict[str, Any]):
        task_state.update_task(
            task_id,
            progress=data,
            append_log=data.get("message"),
            push=True,
        )

    try:
        # Run the async workflow in this thread's event loop
        result = asyncio.run(project_manager.run_incremental_update_workflow(request, progress_callback))
        
        if result.get("status") == "error":
            task_state.update_task(
                task_id,
                status="failed",
                append_log=f"Error: {result.get('message')}",
                push=True,
            )
        else:
            fields = {
                "file_summaries": result.get("file_summaries", []),
                "telemetry": result.get("telemetry", {}),
                "output_dir": result.get("output_dir"),
                "output_dirs": result.get("output_dirs", []),
                "warnings": result.get("warnings", []),
                "warning_count": result.get("warning_count", 0),
                "workshop_issue_exports": result.get("workshop_issue_exports", []),
            }
            task_state.update_task(
                task_id,
                status="completed",
                progress={"percent": 100, "stage": "Completed", "stage_code": "completed"},
                summary=result.get("summary"),
                fields=fields,
                append_log="Incremental update completed successfully.",
                push=False,
            )
            task = task_state.get_task(task_id) or {}
            if fields["warning_count"] > 0:
                task = task_state.update_task(
                    task_id,
                    append_log=f"Runtime translation warnings: {fields['warning_count']}.",
                    push=False,
                )
            total_validation_issues = sum(
                int(export_info.get("issue_count", 0) or 0)
                for export_info in fields["workshop_issue_exports"]
            )
            if total_validation_issues > 0:
                task = task_state.update_task(
                    task_id,
                    append_log=(
                        f"Post-build validation issues: {total_validation_issues}. "
                        "See workshop_issues.json for structured diagnostics."
                    ),
                    push=False,
                )
            for export_info in fields["workshop_issue_exports"]:
                issues_path = export_info.get("issues_path")
                if issues_path:
                    task = task_state.update_task(
                        task_id,
                        append_log=(
                            f"Workshop issue sidecar generated: {issues_path} "
                            f"({export_info.get('issue_count', 0)} issue(s))."
                        ),
                        push=False,
                    )
            task = task_state.get_task(task_id) or task
            _write_incremental_logs(fields["output_dirs"], task.get("log", []), fields["telemetry"])
            logging.info(f"Incremental task {task_id} completed successfully.")

    except Exception as e:
        import traceback
        logging.error(f"Incremental update background task failed: {e}")
        task_state.update_task(
            task_id,
            status="failed",
            append_log=f"Critical Failure: {str(e)}\n{traceback.format_exc()}",
            push=True,
        )
    finally:
        task_state.push_task_update(task_id)

@router.post("/api/project/{project_id}/incremental-update")
async def run_incremental_update(project_id: str, request: IncrementalUpdateRequest, background_tasks: BackgroundTasks):
    """Triggers the incremental update workflow in background."""
    from scripts.shared import task_state
    import uuid
    
    task_id = str(uuid.uuid4())
    task_state.create_task(task_id, status="pending", log_message="Queuing incremental update...")
    
    if request.project_id != project_id:
        request.project_id = project_id
        
    background_tasks.add_task(run_incremental_update_background, task_id, project_id, request)
    
    return {"task_id": task_id, "status": "started"}
