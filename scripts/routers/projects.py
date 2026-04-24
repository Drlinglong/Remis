import os
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any, Callable
from datetime import datetime

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

        project = await project_manager.create_project(request.name, request.folder_path, request.game_id, request.source_language)
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
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return project_manager.kanban_service.get_board(project['source_path'])
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
async def get_project_validation_status(project_id: str):
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_root = project["source_path"]
    log_path = ValidationLogger._get_log_path(project_root)
    issues = ValidationLogger.load_errors(project_root)
    active_issues = [
        issue for issue in issues
        if str(issue.get("status", "detected")).lower() not in {"fixed", "ignored"}
    ]

    counts: Dict[str, int] = {}
    for issue in active_issues:
        label = issue.get("error_code") or issue.get("error_type") or "unknown"
        counts[label] = counts.get(label, 0) + 1

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
        "last_updated_at": datetime.fromtimestamp(os.path.getmtime(log_path)).isoformat() if log_path.exists() else None,
        "sidecar_path": str(log_path),
        "report_count": report_count,
        "report_dir": report_dir if os.path.isdir(report_dir) else None,
    }

def run_incremental_update_background(task_id: str, project_id: str, request: IncrementalUpdateRequest):
    from scripts.shared.state import tasks
    from scripts.shared.ws_manager import ws_manager
    import threading
    import asyncio
    
    # Initialize task state in sync way if needed, but it's already done in the route
    task_lock = threading.Lock()
    tasks[task_id]["status"] = "processing"
    tasks[task_id]["progress"] = {"percent": 0, "stage": "Initializing", "stage_code": "initializing", "message": "Starting..."}
    
    def progress_callback(data: Dict[str, Any]):
        with task_lock:
            if task_id not in tasks: return
            tasks[task_id]["progress"].update(data)
            if "message" in data:
                tasks[task_id]["log"].append(data["message"])
            
            # WebSocket Push
            ws_manager.sync_send_task_update(task_id, dict(tasks[task_id]))

    try:
        # Run the async workflow in this thread's event loop
        result = asyncio.run(project_manager.run_incremental_update_workflow(request, progress_callback))
        
        if result.get("status") == "error":
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["log"].append(f"Error: {result.get('message')}")
        else:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"]["percent"] = 100
            tasks[task_id]["progress"]["stage"] = "Completed"
            tasks[task_id]["progress"]["stage_code"] = "completed"
            tasks[task_id]["log"].append("Incremental update completed successfully.")
            tasks[task_id]["summary"] = result.get("summary")
            tasks[task_id]["file_summaries"] = result.get("file_summaries", [])
            tasks[task_id]["telemetry"] = result.get("telemetry", {})
            tasks[task_id]["output_dir"] = result.get("output_dir")
            tasks[task_id]["output_dirs"] = result.get("output_dirs", [])
            tasks[task_id]["warnings"] = result.get("warnings", [])
            tasks[task_id]["warning_count"] = result.get("warning_count", 0)
            tasks[task_id]["workshop_issue_exports"] = result.get("workshop_issue_exports", [])
            if tasks[task_id]["warning_count"] > 0:
                tasks[task_id]["log"].append(
                    f"Runtime translation warnings: {tasks[task_id]['warning_count']}."
                )
            total_validation_issues = sum(
                int(export_info.get("issue_count", 0) or 0)
                for export_info in tasks[task_id]["workshop_issue_exports"]
            )
            if total_validation_issues > 0:
                tasks[task_id]["log"].append(
                    f"Post-build validation issues: {total_validation_issues}. "
                    "See workshop_issues.json for structured diagnostics."
                )
            for export_info in tasks[task_id]["workshop_issue_exports"]:
                issues_path = export_info.get("issues_path")
                if issues_path:
                    tasks[task_id]["log"].append(
                        f"Workshop issue sidecar generated: {issues_path} "
                        f"({export_info.get('issue_count', 0)} issue(s))."
                    )
            _write_incremental_logs(tasks[task_id]["output_dirs"], tasks[task_id]["log"], tasks[task_id]["telemetry"])
            logging.info(f"Incremental task {task_id} completed successfully.")
            
    except Exception as e:
        import traceback
        logging.error(f"Incremental update background task failed: {e}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["log"].append(f"Critical Failure: {str(e)}\n{traceback.format_exc()}")
    finally:
        # Final WS push
        if task_id in tasks:
            ws_manager.sync_send_task_update(task_id, dict(tasks[task_id]))

@router.post("/api/project/{project_id}/incremental-update")
async def run_incremental_update(project_id: str, request: IncrementalUpdateRequest, background_tasks: BackgroundTasks):
    """Triggers the incremental update workflow in background."""
    from scripts.shared.state import tasks
    import uuid
    
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "log": ["Queuing incremental update..."]}
    
    if request.project_id != project_id:
        request.project_id = project_id
        
    background_tasks.add_task(run_incremental_update_background, task_id, project_id, request)
    
    return {"task_id": task_id, "status": "started"}
