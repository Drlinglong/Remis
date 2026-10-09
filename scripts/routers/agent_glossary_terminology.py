"""Agent entry points over the existing editable glossary infrastructure."""
from fastapi import APIRouter, Depends, Query

from scripts.core.glossary_terminology_service import GlossaryTerminologyService
from scripts.schemas.glossary_terminology import (
    GlossaryTermAppendRequest, GlossaryTermReleaseRequest, TerminologyGlossaryImport, GlossaryTermReviewRequest,
)
from .agent_batch import get_batch_service, operation

router = APIRouter(prefix="/api/agent", tags=["Agent terminology"])


def get_terminology_service(batch=Depends(get_batch_service)):
    from scripts.shared.services import glossary_manager
    return GlossaryTerminologyService(glossary_manager.db_manager, batch.terms)


@router.post("/glossaries/terminology")
async def import_terms(request: TerminologyGlossaryImport, service=Depends(get_terminology_service)):
    return await operation(service.import_glossary, request)


@router.get("/glossaries/{glossary_id}/terminology")
async def preview_terms(glossary_id: int, locale: str, service=Depends(get_terminology_service)):
    return await operation(service.preview, glossary_id, locale)


@router.get("/glossaries/{glossary_id}/terminology/distribution")
async def export_distribution(glossary_id: int, locale: str,
                              expected_fingerprint: str = Query(min_length=64, max_length=64),
                              service=Depends(get_terminology_service)):
    return await operation(service.distribution, glossary_id, locale, expected_fingerprint)


@router.post("/glossaries/{glossary_id}/terminology/append")
async def append_terms(glossary_id: int, request: GlossaryTermAppendRequest, service=Depends(get_terminology_service)):
    return await operation(service.append, glossary_id, request)


@router.post("/term-releases/from-glossary")
async def freeze_terms(request: GlossaryTermReleaseRequest, service=Depends(get_terminology_service)):
    return await operation(service.publish, request)


@router.post("/glossaries/{glossary_id}/terminology/review")
async def review_terms(glossary_id: int, request: GlossaryTermReviewRequest, service=Depends(get_terminology_service)):
    return await operation(service.review, glossary_id, request)
