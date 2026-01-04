import os
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any

from scripts.shared.services import project_manager
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.schemas.project import CreateProjectRequest, UpdateProjectStatusRequest, UpdateProjectNotesRequest, UpdateProjectMetadataRequest, UpdateFileStatusRequest
from scripts.schemas.config import UpdateConfigRequest

router = APIRouter()

@router.get("/api/projects")
def list_projects(status: Optional[str] = None):
    """Returns a list of all projects, optionally filtered by status."""
    return project_manager.get_projects(status)

@router.post("/api/project/create")
def create_project(request: CreateProjectRequest):
    """Creates a new project."""
    try:
        if not os.path.exists(request.folder_path):
             raise HTTPException(status_code=404, detail=f"Path not found: {request.folder_path}")

        project = project_manager.create_project(request.name, request.folder_path, request.game_id, request.source_language)
        return {"status": "success", "project": project}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/files")
def list_project_files(project_id: str):
    """Lists files for a given project."""
    return project_manager.get_project_files(project_id)

@router.post("/api/project/{project_id}/status")
def update_project_status(project_id: str, request: UpdateProjectStatusRequest):
    """Updates a project's status."""
    try:
        project_manager.update_project_status(project_id, request.status)
        return {"status": "success", "message": f"Project status updated to {request.status}"}
    except Exception as e:
        logging.error(f"Error updating project status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/metadata")
def update_project_metadata(project_id: str, request: UpdateProjectMetadataRequest):
    """Updates a project's metadata (game_id, source_language)."""
    try:
        project_manager.update_project_metadata(project_id, request.game_id, request.source_language)
        return {"status": "success", "message": "Project metadata updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error updating project metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/notes")
def update_project_notes(project_id: str, request: UpdateProjectNotesRequest):
    """Adds a new note to the project."""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        # Also update the summary in DB for backward compatibility
        project_manager.update_project_notes(project_id, request.notes)
        
        # Add to JSON history
        json_manager = ProjectJsonManager(project['source_path'])
        json_manager.add_note(request.notes)
        
        return {"status": "success", "message": "Note added"}
    except Exception as e:
        logging.error(f"Error updating project notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/notes")
def list_project_notes(project_id: str):
    """Lists all notes for a project."""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        json_manager = ProjectJsonManager(project['source_path'])
        return json_manager.get_notes()
    except Exception as e:
        logging.error(f"Error listing project notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/project/{project_id}/notes/{note_id}")
def delete_project_note(project_id: str, note_id: str):
    """Deletes a note from a project."""
    project = project_manager.get_project(project_id)
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
def get_project_kanban(project_id: str):
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return project_manager.kanban_service.get_board(project['source_path'])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/kanban")
def save_project_kanban(project_id: str, kanban_data: Dict[str, Any]):
    try:
        project_manager.save_project_kanban(project_id, kanban_data)
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
def refresh_project_files(project_id: str):
    try:
        project_manager.refresh_project_files(project_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/project/{project_id}/upload-translations")
def upload_project_translations(project_id: str):
    """Scans and uploads existing translations to the archive."""
    try:
        result = project_manager.upload_project_translations(project_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error uploading translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/project/{project_id}/config")
def get_project_config(project_id: str):
    project = project_manager.get_project(project_id)
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
def update_project_config(project_id: str, request: UpdateConfigRequest):
    project = project_manager.get_project(project_id)
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
        project_manager.refresh_project_files(project_id)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/project/{project_id}")
def delete_project(project_id: str, delete_files: bool = False):
    """
    Permanently delete a project.
    
    Args:
        project_id: The ID of the project to delete
        delete_files: If True, also delete the source files from disk
    """
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        project_manager.delete_project(project_id, delete_source_files=delete_files)
        return {"status": "success", "message": f"Project deleted successfully (delete_files={delete_files})"}
    except Exception as e:
        logging.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

