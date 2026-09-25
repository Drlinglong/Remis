"""Game resource support information for existing project screens."""
from fastapi import APIRouter, HTTPException
from pathlib import Path

from scripts.core.services.game_support_service import inspect_game_support
from scripts.core.game_adapters.registry import resource_adapter
from scripts.shared.services import project_manager

router = APIRouter()


@router.get("/api/projects/{project_id}/game-support")
async def project_game_support(project_id: str, game_version: str | None = None):
    project = await project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return inspect_game_support(project["game_id"], project["source_path"],
                                project.get("source_language", "en"), game_version)


@router.get("/api/projects/{project_id}/game-resources/{file_id}/preview")
async def preview_game_source(project_id: str, file_id: str):
    project = await project_manager.get_project(project_id)
    adapter = resource_adapter(project.get("game_id")) if project else None
    if not adapter:
        raise HTTPException(status_code=404, detail="Game resource project not found")
    files = await project_manager.get_project_files(project_id)
    item = next((file for file in files if file["file_id"] == file_id and file.get("file_type") == "source"), None)
    if not item:
        raise HTTPException(status_code=404, detail="Source resource not found in this project")
    path = Path(item["file_path"]).resolve()
    discovery = adapter.discover(Path(project["source_path"]), {"code": project.get("source_language", "en")})
    if path not in {resource.path.resolve() for resource in discovery.resources}:
        raise HTTPException(status_code=404, detail="Source resource is no longer part of the active Mod")
    if path.stat().st_size > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Resource is too large for inline preview")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return {"content": handle.read(), "file_path": str(path), "read_only": True}
    except (OSError, UnicodeError) as exc:
        raise HTTPException(status_code=422, detail="Resource cannot be read as UTF-8") from exc
