"""Provider-independent, read-only preview of a project's next source revision."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from scripts.schemas.common import LanguageCode
from scripts.shared.services import project_manager
from scripts.core.services.agent_incremental_preview_service import build_incremental_preview

router = APIRouter(prefix="/api/agent", tags=["agent-incremental"])


class IncrementalPreviewRequest(BaseModel):
    custom_source_path: str | None = None
    target_lang_codes: list[LanguageCode] = Field(min_length=1)


@router.post("/projects/{project_id}/incremental-preview")
async def preview_incremental(project_id: str, request: IncrementalPreviewRequest):
    try:
        return await build_incremental_preview(
            project_id, request.custom_source_path,
            [code.value for code in request.target_lang_codes], project_manager=project_manager,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, detail={"code": "incremental_preview_invalid", "message": str(exc)}) from exc
