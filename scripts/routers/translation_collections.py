"""Translation collection APIs used by both the desktop and operators."""
from fastapi import APIRouter, HTTPException, Query

from scripts.core.translation_collections import service, sources
from scripts.core.translation_collections.contracts import (
    CreateCollection, UpdateCollection, PublicationBinding, ExportApproval,
)
from scripts.core.translation_collections.repository import CollectionConflict
from scripts.core.services.translation_package_workflow import PackageWorkflowError

router = APIRouter(tags=["Translation collections"])


async def _respond(operation):
    try:
        return await operation
    except PackageWorkflowError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    except (CollectionConflict, FileExistsError) as exc:
        raise HTTPException(409, detail={"code": "collection_conflict", "message": str(exc)}) from exc
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "collection_not_found", "message": "Collection no longer exists."}) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, detail={"code": "invalid_collection", "message": str(exc)}) from exc


@router.get("/api/translation-collections")
@router.get("/api/agent/translation-collections")
async def list_collections():
    return await _respond(service.list_collections())


@router.post("/api/translation-collections")
@router.post("/api/agent/translation-collections")
async def create_collection(request: CreateCollection):
    return await _respond(service.create_collection(request.model_dump()))


@router.get("/api/translation-collections/project-options/{project_id}")
@router.get("/api/agent/translation-collections/project-options/{project_id}")
async def project_options(project_id: str):
    return await _respond(sources.project_options(project_id))


@router.get("/api/translation-collections/{collection_id}")
@router.get("/api/agent/translation-collections/{collection_id}")
async def get_collection(collection_id: str):
    return await _respond(service.get_collection(collection_id))


@router.put("/api/translation-collections/{collection_id}")
@router.put("/api/agent/translation-collections/{collection_id}")
async def update_collection(collection_id: str, request: UpdateCollection):
    return await _respond(service.update_collection(collection_id, request.model_dump()))


@router.delete("/api/translation-collections/{collection_id}")
@router.delete("/api/agent/translation-collections/{collection_id}")
async def delete_collection(collection_id: str, expected_revision: int = Query(ge=1)):
    return await _respond(service.delete_collection(collection_id, expected_revision))


@router.put("/api/translation-collections/{collection_id}/publication")
@router.put("/api/agent/translation-collections/{collection_id}/publication")
async def bind_publication(collection_id: str, request: PublicationBinding):
    return await _respond(service.bind_publication(collection_id, request.model_dump()))


@router.post("/api/translation-collections/{collection_id}/plan")
@router.post("/api/agent/translation-collections/{collection_id}/plan")
async def plan_export(collection_id: str):
    return await _respond(service.plan_export(collection_id))


@router.post("/api/translation-collections/{collection_id}/export")
@router.post("/api/agent/translation-collections/{collection_id}/export")
async def export_collection(collection_id: str, request: ExportApproval):
    return await _respond(service.export_collection(collection_id, request.plan_id, request.approved))


@router.get("/api/translation-collections/{collection_id}/history")
@router.get("/api/agent/translation-collections/{collection_id}/history")
async def export_history(collection_id: str):
    return await _respond(service.export_history(collection_id))
