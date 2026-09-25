"""Read-only game support inspection using the shared product contract."""
from fastapi import APIRouter, HTTPException
from scripts.core.services.game_support_service import inspect_project_game_support

router = APIRouter(prefix="/api/agent", tags=["Agent API"])


@router.get("/projects/{project_id}/game-support")
async def get_project_game_support(project_id: str, game_version: str | None = None):
    try:
        return await inspect_project_game_support(project_id, game_version)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "project_not_found", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "invalid_game", "message": str(exc)}) from exc
