import asyncio
import json
import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from typing import Dict, List

from scripts.core.api_handler import get_handler
from scripts.core.glossary_health_reviewer import GlossaryHealthReviewer
from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot
from scripts.core.copilot.runtime_bridge import handler_for_runtime
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot
from scripts.shared import task_state
from scripts.shared.services import glossary_manager
from scripts.schemas.glossary import (
    SearchGlossaryRequest,
    GlossaryEntryCreate,
    GlossaryEntryIn,
    CreateGlossaryRequest,
    DuplicateGlossaryRequest,
    UpdateGlossaryMetadataRequest,
    GlossaryBatchSelectionRequest,
    BatchDeleteGlossariesRequest,
    GlossaryHealthCheckRequest,
    GlossaryMergeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_glossary_runtime(
    payload: Dict,
) -> ProviderRuntimeSnapshot:
    return resolve_provider_runtime_snapshot(
        payload.get("api_provider"),
        payload.get("model_name"),
    )


async def _run_glossary_merge_task(task_id: str, payload: Dict) -> None:
    task_state.update_task(
        task_id,
        status="running",
        message="Merging glossary entries.",
        append_log="Validated sources; merge started.",
        progress={"current": 1, "total": 2, "percent": 50, "stage": "Merging"},
    )
    try:
        result = await glossary_manager.merge_glossaries(**payload)
        task_state.update_task(
            task_id,
            status="completed",
            message="Glossary merge completed.",
            append_log=f"Merged into glossary {result['name']}.",
            progress={"current": 2, "total": 2, "percent": 100, "stage": "Completed"},
            fields={
                "result": {
                    "types": ["glossary_merge", "change_summary"],
                    "summary": (
                        f"Merged {len(result['merged_from'])} glossaries into {result['name']}; "
                        f"created {result['created_entry_count']} and updated {result['updated_entry_count']} entries."
                    ),
                    "metadata": result,
                },
                "source_route": (
                    f"/glossary-manager?game_id={result['game_id']}&glossary_id={result['glossary_id']}"
                ),
            },
        )
    except Exception as exc:
        logger.exception("Glossary merge task %s failed", task_id)
        task_state.update_task(
            task_id,
            status="failed",
            message=str(exc),
            append_log=f"Glossary merge failed: {exc}",
            progress={"percent": 100, "stage": "Failed", "error_count": 1},
        )


async def _run_glossary_health_task(
    task_id: str,
    payload: Dict,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> None:
    task_state.update_task(
        task_id,
        status="running",
        message="Running deterministic glossary checks.",
        append_log="Deterministic glossary checks started.",
        progress={"current": 1, "total": 3, "percent": 33, "stage": "Deterministic checks"},
    )
    report = None
    try:
        report = await glossary_manager.check_glossary_health(
            payload["glossary_ids"],
            target_lang=payload.get("target_lang"),
        )
        report["ai_advice"] = []
        report["ai_review_status"] = "not_requested"
        task_state.update_task(
            task_id,
            append_log=f"Deterministic checks found {report['issue_count']} issue(s).",
            progress={"current": 2, "total": 3, "percent": 67, "stage": "Reviewing results"},
        )

        if payload.get("include_ai_advice"):
            runtime = provider_runtime or _resolve_glossary_runtime(payload)
            task_state.update_task(
                task_id,
                message="Requesting advisory model review. No glossary data will be changed.",
                append_log="Explicitly approved advisory model review started.",
                progress={"stage": "AI advice"},
            )
            report["ai_provider"] = runtime.selection_id
            report["ai_model"] = runtime.model_id
            report["ai_provider_runtime"] = runtime.safe_metadata()
            report["ai_concurrency_limit"] = payload.get("concurrency_limit", 1)
            try:
                handler = handler_for_runtime(runtime, get_handler)
                reviewer = GlossaryHealthReviewer(handler)
                report["ai_review_plan"] = reviewer.plan(report)
                report["ai_advice"] = await asyncio.to_thread(
                    reviewer.review,
                    report,
                    concurrency_limit=payload.get("concurrency_limit", 1),
                )
                report["ai_review_status"] = "completed"
            except Exception as exc:
                error_type = type(exc).__name__
                logger.warning(
                    "Advisory model review failed for glossary health task %s (%s)",
                    task_id,
                    error_type,
                )
                report["ai_review_status"] = "failed"
                report["ai_review_error"] = error_type
                report["completion_outcome"] = "partial_success"

        summary = (
            f"Glossary health score {report['score']}/100 with "
            f"{report['issue_count']} deterministic issue(s)."
        )
        ai_review_failed = report["ai_review_status"] == "failed"
        task_state.update_task(
            task_id,
            status="completed",
            message=(
                "Glossary inspection completed; AI advice was unavailable."
                if ai_review_failed
                else "Glossary health check completed."
            ),
            append_log=(
                "Deterministic health report completed; optional AI advice was unavailable."
                if ai_review_failed
                else "Health report completed without changing glossary data."
            ),
            progress={
                "current": 3,
                "total": 3,
                "percent": 100,
                "stage": "Completed",
                "error_count": 0,
                "warning_count": 1 if ai_review_failed else 0,
            },
            fields={
                "result": {
                    "types": (
                        ["glossary_health_report", "advisory_review"]
                        if report["ai_review_status"] == "completed"
                        else ["glossary_health_report"]
                    ),
                    "summary": (
                        f"{summary} Optional AI advice was unavailable."
                        if ai_review_failed
                        else summary
                    ),
                    "metadata": report,
                },
            },
        )
    except Exception as exc:
        logger.exception("Glossary health task %s failed", task_id)
        result = None
        if report is not None:
            report["ai_review_status"] = "failed"
            report["ai_review_error"] = str(exc)
            result = {
                "types": ["glossary_health_report"],
                "summary": "Deterministic checks completed, but advisory model review failed.",
                "metadata": report,
            }
        task_state.update_task(
            task_id,
            status="failed",
            message=str(exc),
            append_log=f"Glossary health task failed: {exc}",
            progress={"percent": 100, "stage": "Failed", "error_count": 1},
            fields={"result": result} if result else None,
        )

def _transform_storage_to_frontend_format(entry: Dict) -> Dict:
    """
    Transforms a glossary entry from the database storage format to the format
    expected by the frontend.
    """
    new_entry = entry.copy()
    
    # Map entry_id to id for frontend compatibility
    if 'entry_id' in new_entry:
        new_entry['id'] = new_entry['entry_id']
    
    translations = new_entry.get('translations', {})
    metadata = new_entry.get('raw_metadata', {})
    source_lang = metadata.get('source_lang')

    # Source and target can use the same language code, so source text must not
    # rely on a translations entry that the final translation can overwrite.
    new_entry['source'] = (
        metadata.get('source_text')
        or (translations.get(source_lang) if source_lang else None)
        or translations.get('en')
        or next((value for value in translations.values() if value), '')
    )

    # Extract notes from remarks inside raw_metadata
    new_entry['notes'] = metadata.get('remarks', '')

    # Pass the full raw_metadata object to the frontend as 'metadata'
    new_entry['metadata'] = new_entry.get('raw_metadata', {})

    # Ensure variants and abbreviations are present
    if 'variants' not in new_entry: new_entry['variants'] = {}
    if 'abbreviations' not in new_entry: new_entry['abbreviations'] = {}
    
    return new_entry

def _transform_entry_to_storage_format(entry: Dict) -> Dict:
    entry = entry.copy()
    if 'translations' not in entry: entry['translations'] = {}
    if 'metadata' not in entry: entry['metadata'] = {}
    source_text = entry.get('source', '')
    source_lang = entry['metadata'].get('source_lang', 'en')
    target_lang = entry['metadata'].get('target_lang')
    if source_text:
        entry['metadata']['source_text'] = source_text
        if source_lang != target_lang:
            entry['translations'][source_lang] = source_text
    if 'notes' in entry:
        entry['metadata']['remarks'] = entry['notes']
        del entry['notes']
    if 'source' in entry: del entry['source']
    # Ensure entry_id is present if id is present
    if 'id' in entry and 'entry_id' not in entry:
        entry['entry_id'] = entry['id']
    return entry

@router.get("/api/glossaries")
async def get_all_glossaries():
    return await glossary_manager.get_all_glossaries()

@router.get("/api/glossaries/overview")
async def get_glossary_overview():
    return await glossary_manager.get_glossary_overview()

@router.get("/api/glossaries/{game_id}")
async def get_game_glossaries(game_id: str):
    return await glossary_manager.get_available_glossaries(game_id)

@router.get("/api/glossary/tree")
async def get_glossary_tree():
    return await glossary_manager.get_glossary_tree_data()

@router.get("/api/glossary/content")
async def get_glossary_content(glossary_id: int, page: int = Query(1, alias="page"), pageSize: int = Query(25, alias="pageSize")):
    data = await glossary_manager.get_glossary_entries_paginated(glossary_id, page, pageSize)
    transformed_entries = [_transform_storage_to_frontend_format(entry) for entry in data.get("entries", [])]
    return {"entries": transformed_entries, "totalCount": data.get("totalCount", 0)}

@router.post("/api/glossary/search")
async def search_glossary(payload: SearchGlossaryRequest):
    glossary_ids_to_search = []
    if payload.scope == 'file':
        if not payload.file_name:
            raise HTTPException(status_code=400, detail="file_name (as key 'game|id|name') is required.")
        try:
            glossary_ids_to_search.append(int(payload.file_name.split('|')[1]))
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid key format.")
    elif payload.scope == 'game':
        if not payload.game_id:
            raise HTTPException(status_code=400, detail="game_id is required.")
        game_glossaries = await glossary_manager.get_available_glossaries(payload.game_id)
        glossary_ids_to_search = [g['glossary_id'] for g in game_glossaries]
    elif payload.scope == 'all':
        tree = await glossary_manager.get_glossary_tree_data()
        for game_node in tree:
            for file_node in game_node.get('children', []):
                try:
                    glossary_ids_to_search.append(int(file_node['key'].split('|')[1]))
                except (ValueError, IndexError):
                    continue
    if not glossary_ids_to_search:
        return {"entries": [], "totalCount": 0}
    
    logger.debug(f"Searching glossaries {glossary_ids_to_search} for query '{payload.query}'")
    
    result_data = await glossary_manager.search_glossary_entries_paginated(
        query=payload.query, glossary_ids=glossary_ids_to_search,
        page=payload.page, page_size=payload.pageSize
    )
    transformed_entries = [_transform_storage_to_frontend_format(entry) for entry in result_data.get("entries", [])]
    return {"entries": transformed_entries, "totalCount": result_data.get("totalCount", 0)}

@router.post("/api/glossary/entry", status_code=201)
async def create_glossary_entry(glossary_id: int, payload: GlossaryEntryCreate):
    new_entry_dict = payload.dict()
    new_entry_dict['id'] = str(uuid.uuid4())
    storage_entry = _transform_entry_to_storage_format(new_entry_dict)
    if not await glossary_manager.add_entry(glossary_id, storage_entry):
        logger.error(f"Failed to create glossary entry in glossary {glossary_id}")
        raise HTTPException(status_code=500, detail="Failed to create glossary entry.")
    
    logger.info(f"Created new glossary entry {new_entry_dict['id']} in glossary {glossary_id}")
    return new_entry_dict

@router.put("/api/glossary/entry/{entry_id}")
async def update_glossary_entry(entry_id: str, payload: GlossaryEntryIn):
    entry_dict = payload.dict()
    entry_dict['id'] = entry_id # Ensure ID matches URL
    
    storage_entry = _transform_entry_to_storage_format(entry_dict)
    
    if not await glossary_manager.update_entry(entry_id, storage_entry):
        logger.error(f"Failed to update glossary entry {entry_id}")
        raise HTTPException(status_code=500, detail="Failed to update glossary entry.")
    
    logger.info(f"Updated glossary entry {entry_id}")
    return entry_dict

@router.delete("/api/glossary/entry/{entry_id}")
async def delete_glossary_entry(entry_id: str):
    if not await glossary_manager.delete_entry(entry_id):
        logger.error(f"Failed to delete glossary entry {entry_id}")
        raise HTTPException(status_code=500, detail="Failed to delete glossary entry.")
    
    logger.info(f"Deleted glossary entry {entry_id}")
    return {"message": "Entry deleted successfully"}

@router.post("/api/glossary", status_code=201)
@router.post("/api/glossary/file", status_code=201, include_in_schema=False)
async def create_glossary(payload: CreateGlossaryRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Glossary name is required.")
    if not await glossary_manager.create_glossary(payload.game_id, name):
        logger.error("Failed to create glossary %s for game %s", name, payload.game_id)
        raise HTTPException(status_code=500, detail="Failed to create glossary.")

    logger.info("Created glossary %s for game %s", name, payload.game_id)
    return {"message": "Glossary created successfully", "name": name}

@router.post("/api/glossary/file/{glossary_id}/duplicate", status_code=201)
async def duplicate_glossary_file(glossary_id: int, payload: DuplicateGlossaryRequest):
    target_name = payload.name.strip()
    if not target_name:
        raise HTTPException(status_code=422, detail="Glossary name is required.")

    try:
        duplicated = await glossary_manager.duplicate_glossary(glossary_id, target_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if duplicated is None:
        raise HTTPException(status_code=404, detail="Source glossary not found.")

    logger.info(
        "Duplicated glossary %s as %s (%s entries)",
        glossary_id,
        duplicated["glossary_id"],
        duplicated["entry_count"],
    )
    return duplicated

@router.put("/api/glossary/file/{glossary_id}")
async def update_glossary_metadata(glossary_id: int, payload: UpdateGlossaryMetadataRequest):
    try:
        updated = await glossary_manager.update_glossary_metadata(
            glossary_id,
            name=payload.name,
            description=payload.description,
            kind=payload.kind,
            project_ids=payload.project_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="Glossary not found.")

    logger.info("Updated glossary metadata for %s", glossary_id)
    return updated

@router.post("/api/glossaries/batch-delete/preview")
async def preview_batch_delete_glossaries(payload: GlossaryBatchSelectionRequest):
    try:
        return await glossary_manager.get_batch_delete_impact(payload.glossary_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/api/glossaries/batch-delete")
async def batch_delete_glossaries(payload: BatchDeleteGlossariesRequest):
    try:
        return await glossary_manager.batch_delete_glossaries(
            payload.glossary_ids,
            confirm_main_glossaries=payload.confirm_main_glossaries,
            confirm_project_bindings=payload.confirm_project_bindings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/glossaries/merge/preview")
async def preview_glossary_merge(payload: GlossaryMergeRequest):
    try:
        return await glossary_manager.preview_glossary_merge(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/glossaries/merge")
async def start_glossary_merge(payload: GlossaryMergeRequest, background_tasks: BackgroundTasks):
    request_data = payload.model_dump()
    try:
        preview = await glossary_manager.preview_glossary_merge(**request_data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    task_id = str(uuid.uuid4())
    dedupe_payload = json.dumps(request_data, sort_keys=True, ensure_ascii=True)
    try:
        task_state.create_task(
            task_id,
            status="queued",
            log_message="Glossary merge queued after a fresh read-only preview.",
            fields={
                "kind": "glossary_merge",
                "title": f"Merge glossaries into {preview['target_name']}",
                "source_route": "/glossary-manager",
                "created_by": {"type": "user"},
                "blocking": True,
                "result": {
                    "types": ["glossary_merge_preview"],
                    "summary": (
                        f"Preview: {preview['unique_term_count']} unique terms, "
                        f"{preview['conflict_count']} conflicts."
                    ),
                    "metadata": {"preview": preview},
                },
            },
            dedupe_key=f"glossary_merge:{dedupe_payload}",
            reject_duplicate=True,
        )
    except task_state.DuplicateTaskError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "An identical glossary merge is already active.",
                "task_id": exc.existing_task.get("task_id"),
            },
        ) from exc
    task_state.init_progress(task_id, {
        "total": 2,
        "current": 0,
        "percent": 0,
        "stage": "Queued",
    })
    background_tasks.add_task(_run_glossary_merge_task, task_id, request_data)
    return {"task_id": task_id, "status": "queued", "preview": preview}


@router.post("/api/glossaries/health-check")
async def start_glossary_health_check(
    payload: GlossaryHealthCheckRequest,
    background_tasks: BackgroundTasks,
):
    request_data = payload.model_dump()
    provider_runtime = None
    runtime_metadata = None
    if payload.include_ai_advice:
        try:
            provider_runtime = resolve_provider_runtime_snapshot(
                payload.api_provider,
                payload.model_name,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        runtime_metadata = provider_runtime.safe_metadata()
    try:
        deterministic_preview = await glossary_manager.check_glossary_health(
            payload.glossary_ids,
            target_lang=payload.target_lang,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    task_id = str(uuid.uuid4())
    dedupe_data = dict(request_data)
    if runtime_metadata is not None:
        dedupe_data["provider_runtime"] = runtime_metadata
    dedupe_payload = json.dumps(dedupe_data, sort_keys=True, ensure_ascii=True)
    try:
        task_state.create_task(
            task_id,
            status="queued",
            log_message="Glossary health check queued.",
            fields={
                "kind": "glossary_health_check",
                "title": f"Check {len(payload.glossary_ids)} glossary asset(s)",
                "source_route": "/glossary-manager",
                "created_by": {"type": "user"},
                "blocking": False,
                "result": {
                    "types": ["glossary_health_preview"],
                    "summary": (
                        f"Deterministic preview score {deterministic_preview['score']}/100."
                    ),
                    "metadata": {
                        "preview": deterministic_preview,
                        "ai_advice_requested": payload.include_ai_advice,
                        "ai_provider": (
                            payload.api_provider if payload.include_ai_advice else None
                        ),
                        "ai_model": (
                            payload.model_name if payload.include_ai_advice else None
                        ),
                        "ai_provider_runtime": runtime_metadata,
                    },
                },
            },
            dedupe_key=f"glossary_health:{dedupe_payload}",
            reject_duplicate=True,
        )
    except task_state.DuplicateTaskError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "An identical glossary health check is already active.",
                "task_id": exc.existing_task.get("task_id"),
            },
        ) from exc
    task_state.init_progress(task_id, {
        "total": 3,
        "current": 0,
        "percent": 0,
        "stage": "Queued",
    })
    background_tasks.add_task(
        _run_glossary_health_task,
        task_id,
        request_data,
        provider_runtime,
    )
    ai_review_plan = (
        GlossaryHealthReviewer.plan(deterministic_preview)
        if payload.include_ai_advice
        else None
    )
    return {
        "task_id": task_id,
        "status": "queued",
        "deterministic_preview": deterministic_preview,
        "ai_advice_requested": payload.include_ai_advice,
        "ai_review_plan": ai_review_plan,
        "mutations_applied": False,
    }

@router.delete("/api/glossary/file/{glossary_id}")
async def delete_glossary_file(glossary_id: int):
    """Deletes an entire glossary file and all its entries."""
    if not await glossary_manager.delete_glossary(glossary_id):
        logger.error(f"Failed to delete glossary {glossary_id}")
        raise HTTPException(status_code=500, detail="Failed to delete glossary.")
    
    logger.info(f"Deleted glossary {glossary_id}")
    return {"message": "Glossary deleted successfully"}
