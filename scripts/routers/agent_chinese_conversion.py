"""Advanced Chinese conversion service, no GUI or localization overwrite."""
from functools import lru_cache

from fastapi import APIRouter, Depends, Query

from scripts.core.chinese_conversion_service import ChineseConversionService
from scripts.core.chinese_conversion_transport import ChineseConversionTransport
from scripts.schemas.chinese_conversion import ChineseConversionRequest
from .agent_batch import get_batch_service, operation

router = APIRouter(prefix="/api/agent/chinese-conversion", tags=["Chinese conversion (advanced)"])


@lru_cache(maxsize=1)
def transport():
    return ChineseConversionTransport()


def service(batch=Depends(get_batch_service), wire=Depends(transport)):
    return ChineseConversionService(batch.repository, batch.artifacts, wire)


@router.get("/service-info")
async def info(current=Depends(service)):
    return await operation(current.info)


@router.post("/convert")
async def convert(request: ChineseConversionRequest, current=Depends(service)):
    return await operation(current.convert, request)


@router.get("/jobs")
async def history(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), current=Depends(service)):
    records = current.repository.list_jobs(limit=limit, offset=offset, kind="conversion")
    return {"jobs": [current.get(r["id"]) for r in records], "limit": limit, "offset": offset}


@router.get("/jobs/{identifier}")
async def read(identifier: str, current=Depends(service)):
    return await operation(current.get, identifier)


@router.get("/jobs/{identifier}/artifacts/{kind}")
async def artifact(identifier: str, kind: str, current=Depends(service)):
    return await operation(current.artifact, identifier, kind)
