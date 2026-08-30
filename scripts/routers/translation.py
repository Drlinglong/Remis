import os
import uuid
import shutil
import logging
import traceback
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, WebSocket
from fastapi.responses import FileResponse

from scripts.shared.state import tasks
from scripts.shared.services import project_manager, glossary_manager, archive_manager
from scripts.shared import task_state
from scripts.schemas.translation import (
    CheckpointDeleteResponse,
    CheckpointStatusRequest,
    CheckpointStatusResponse,
    InitialTranslationRequest,
    SourceModResponse,
    TranslationRequestV2,
    TranslationTaskResponse,
    CustomLangConfig,
)
from scripts.schemas.reference import ReferenceReusePreviewRequest
from scripts.app_settings import (
    API_PROVIDERS,
    DEST_DIR,
    GAME_ID_ALIASES,
    GAME_PROFILES,
    GAME_PROFILES_BY_ID,
    LANGUAGES,
    SOURCE_DIR,
)
from scripts.core.services.reference_reuse_preview_service import ReferenceReusePreviewService
from scripts.core.services.translation_progress_callback import build_translation_progress_callback
from scripts.core.services.translation_workflow_outcome import (
    history_completion_description as _history_completion_description,
    record_context_metadata as _record_context_metadata,
    workflow_outcome_values as _workflow_outcome_values,
)
from scripts.workflows import initial_translate
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.services.translation_context_service import context_workflow_kwargs
from scripts.core.services.translation_resource_policy import resolve_translation_run_resources
from scripts.routers.provider_runtime import provider_task_fields, resolve_runtime_or_400
from scripts.core.services.translation_context_readiness_service import (
    TranslationContextReadinessService,
)
from scripts.core.neologism_manager import neologism_manager
import asyncio
from scripts.shared.ws_manager import ws_manager
router = APIRouter()
translation_context_readiness = TranslationContextReadinessService(
    glossary_manager,
    neologism_manager,
)


def _run_async(coro):
    """Run async project services from the synchronous background workflow thread."""
    return asyncio.run(coro)


def _resolve_target_languages(target_lang_codes: List[str]):
    resolved = []
    for target_code in target_lang_codes:
        lang = next((item for item in LANGUAGES.values() if item["code"] == target_code), None)
        if lang:
            resolved.append(lang)
    return resolved


def _resolve_requested_target_languages(target_lang_codes: List[str], custom_lang_config: Optional[CustomLangConfig] = None) -> List[dict]:
    if custom_lang_config:
        return [custom_lang_config.model_dump()]
    return _resolve_target_languages(target_lang_codes)


def _reject_source_language_targets(source_lang_code: str, target_languages: List[dict]):
    duplicates = [
        lang.get("code")
        for lang in target_languages
        if lang.get("code") and lang.get("code") == source_lang_code
    ]
    if duplicates:
        target_codes = [lang.get("code") for lang in target_languages]
        raise ValueError(
            "Target language must be different from the source language. "
            f"source={source_lang_code}, targets={target_codes}"
        )


@router.post("/api/reference-reuse/preview")
async def preview_reference_reuse(request: ReferenceReusePreviewRequest):
    project = await project_manager.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    game_id = str(project.get("game_id") or "victoria3")
    normalized_game_id = GAME_ID_ALIASES.get(game_id.casefold(), game_id)
    game_profile = GAME_PROFILES_BY_ID.get(normalized_game_id) or GAME_PROFILES.get(game_id)
    source_lang_code = request.source_lang_code.value
    source_lang = next(
        (lang for lang in LANGUAGES.values() if lang["code"] == source_lang_code),
        None,
    )
    target_languages = _resolve_target_languages([
        target.value for target in request.target_lang_codes
    ])
    if (
        not game_profile
        or not source_lang
        or len(target_languages) != len(request.target_lang_codes)
    ):
        raise HTTPException(
            status_code=400,
            detail="Failed to resolve game profile, source language, or target languages",
        )
    try:
        _reject_source_language_targets(source_lang_code, target_languages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source_path = request.custom_source_path or project["source_path"]
    if not os.path.isdir(source_path):
        raise HTTPException(status_code=400, detail="Source path is not a directory")

    try:
        return ReferenceReusePreviewService().preview(
            source_path=source_path,
            game_profile=game_profile,
            source_lang=source_lang,
            target_languages=target_languages,
            localization_path=request.localization_path,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _get_output_folder_name(mod_name: str, target_lang: dict) -> str:
    prefix = target_lang.get("folder_prefix", f"{target_lang.get('code', 'unknown')}-")
    return f"{prefix}{slugify_to_ascii(mod_name)}"


def _get_output_directories(mod_name: str, target_languages: List[dict]) -> List[str]:
    if len(target_languages) > 1:
        return [os.path.join(DEST_DIR, f"Multilanguage-{slugify_to_ascii(mod_name)}")]
    return [os.path.join(DEST_DIR, _get_output_folder_name(mod_name, target_lang)) for target_lang in target_languages]


def _get_checkpoint_output_dir(mod_name: str, target_languages: List[dict]) -> str:
    return _get_output_directories(mod_name, target_languages)[0]


def finalize_task(
    task_id: str,
    status: str,
    log_message: Optional[str] = None,
    stage: Optional[str] = None,
    error_count: Optional[int] = None,
):
    """Persist terminal task state and force a final status push to the frontend."""
    progress = {}
    if status in {"completed", "partial_failed"}:
        progress["percent"] = 100
    if error_count is not None:
        progress["error_count"] = error_count
    if stage:
        progress["stage"] = stage
    task_state.update_task(
        task_id,
        status=status,
        append_log=log_message,
        progress=progress or None,
        push=True,
    )


def run_translation_workflow(task_id: str, mod_name: str, game_profile_id: str, source_lang_code: str, target_lang_codes: List[str], api_provider: str, mod_context: str, project_id: Optional[str] = None, provider_runtime=None):
    """
    A wrapper for the core translation logic to be run in the background.
    """
    i18n.load_language('en_US')

    task_state.update_task(
        task_id,
        status="processing",
        append_log="Initializing translation workflow...",
        push=True,
    )

    if project_id:
        try:
            _run_async(project_manager.log_history_event(
                project_id=project_id,
                action_type='translation_workflow',
                description="Translation task started"
            ))
        except Exception as e:
            logging.error(f"Failed to log activity: {e}")

    try:
        game_profile = GAME_PROFILES.get(game_profile_id)
        source_lang = next((lang for lang in LANGUAGES.values() if lang["code"] == source_lang_code), None)
        target_languages = _resolve_target_languages(target_lang_codes)

        if not all([game_profile, source_lang, target_languages]):
            raise ValueError("Failed to resolve game profile, source language, or target languages.")

        outcome = initial_translate.run(
            mod_name=mod_name,
            game_profile=game_profile,
            source_lang=source_lang,
            target_languages=target_languages,
            selected_provider=api_provider,
            mod_context=mod_context,
            provider_runtime=provider_runtime,
        )

        task_state.update_task(
            task_id,
            fields={"output_dirs": _get_output_directories(mod_name, target_languages)},
            push=False,
        )
        status, message, issue_count = _workflow_outcome_values(outcome)
        finalize_task(task_id, status, message, "Completed", issue_count)

        if project_id:
            try:
                _run_async(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description=_history_completion_description(status)
                ))
            except Exception as e:
                logging.error(f"Failed to log completion activity: {e}")

    except Exception as e:
        tb_str = traceback.format_exc()
        user_error = f"Translation workflow failed: {e}"
        logging.error(f"Task {task_id} failed: {user_error}\n{tb_str}")
        finalize_task(task_id, "failed", user_error, "Failed")
        task_state.append_task_event(
            task_id,
            tb_str,
            audience="diagnostic",
            level="error",
            event_type="traceback",
        )
        if project_id:
            try:
                _run_async(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation workflow failed"
                ))
            except Exception as e:
                logging.error(f"Failed to log failure activity: {e}")


def run_translation_workflow_v2(
    task_id: str, mod_name: str, game_profile_id: str, source_lang_code: str,
    target_lang_codes: List[str], api_provider: str, mod_context: str,
    selected_glossary_ids: List[int], model_name: Optional[str], use_main_glossary: bool,
    custom_lang_config: Optional[CustomLangConfig] = None,
    project_id: Optional[str] = None,
    use_resume: bool = True,
    clean_source: bool = False,
    batch_size_limit: Optional[int] = None,
    source_context_overlap: int = 0,
    concurrency_limit: Optional[int] = None,
    rpm_limit: Optional[int] = 40,
    embedded_workshop: Optional[dict] = None,
    reference_reuse: Optional[dict] = None,
    use_project_context: bool = True,
    context_release_id: Optional[str] = None,
    context_character_budget: int = 4000,
    translation_context_mode: Optional[str] = None,
    provider_runtime=None,
):
    i18n.load_language('en_US')
    task_state.update_task(
        task_id,
        status="processing",
        append_log="Initializing translation workflow (V2)...",
        push=True,
    )
    if project_id:
        try:
            _run_async(project_manager.log_history_event(
                project_id=project_id,
                action_type='translation_workflow',
                description="Translation task (V2) started"
            ))
        except Exception as e:
            logging.error(f"Failed to log activity (v2): {e}")
    task_state.init_progress(task_id)
    progress_callback = build_translation_progress_callback(
        task_id,
        use_resume=use_resume,
    )
    try:
        logging.info(f"Starting V2 Workflow for Task {task_id}"); logging.info(f"Params: game_profile_id={game_profile_id}, source={source_lang_code}, targets={target_lang_codes}")
        normalized_game_id = game_profile_id
        if game_profile_id == 'vic3':
            normalized_game_id = 'victoria3'
            logging.info(f"Normalized game_id 'vic3' to '{normalized_game_id}'")
        game_profile = GAME_PROFILES.get(normalized_game_id)
        if not game_profile:
            game_profile = next((p for p in GAME_PROFILES.values() if p['id'] == normalized_game_id), None)

        source_lang = next((lang for lang in LANGUAGES.values() if lang["code"] == source_lang_code), None)
        target_languages = _resolve_target_languages(target_lang_codes)

        logging.info(f"Resolved: GameProfile={game_profile is not None}, SourceLang={source_lang is not None}, TargetLangs={len(target_languages)}")

        if custom_lang_config:
            custom_lang = custom_lang_config.model_dump()
            if not custom_lang.get('name_en'):
                custom_lang['name_en'] = custom_lang['name']
            target_languages = [custom_lang]
            logging.info(f"Using Custom Language Config: {custom_lang}")

        if not all([game_profile, source_lang]) or (not target_languages and not custom_lang_config):
            logging.error(f"Validation Failed: GameProfile={game_profile}, SourceLang={source_lang}, TargetLangs={target_languages}")
            raise ValueError("Failed to resolve game profile, source language, or target languages.")
        _reject_source_language_targets(source_lang_code, target_languages)

        resources = resolve_translation_run_resources(
            game_id=game_profile["id"],
            project_id=project_id,
            selected_glossary_ids=selected_glossary_ids,
            mode=translation_context_mode,
            legacy_use_main_glossary=use_main_glossary,
            legacy_use_project_context=use_project_context,
            project_manager=project_manager,
            glossary_manager=glossary_manager,
            run_async=_run_async,
        )
        resource_policy = resources.policy
        final_glossary_ids = list(resources.glossary_ids)
        override_path = resources.override_path
        if override_path:
            logging.info("Using override source path from project: %s", override_path)
        if resources.project_glossary_id:
            logging.info(
                "Mounted project neologism glossary %s for project %s",
                resources.project_glossary_id,
                project_id,
            )

        logging.info("Calling initial_translate.run...")
        outcome = initial_translate.run(
            mod_name=mod_name, game_profile=game_profile, source_lang=source_lang,
            target_languages=target_languages, selected_provider=api_provider,
            mod_context=mod_context, selected_glossary_ids=final_glossary_ids,
            model_name=model_name, use_glossary=resource_policy.use_glossaries,
            progress_callback=progress_callback,
            override_path=override_path, project_id=project_id, use_resume=use_resume,
            clean_source=clean_source, batch_size_limit=batch_size_limit,
            source_context_overlap=source_context_overlap,
            concurrency_limit=concurrency_limit, rpm_limit=rpm_limit,
            embedded_workshop=embedded_workshop,
            reference_reuse=reference_reuse,
            provider_runtime=provider_runtime,
            **context_workflow_kwargs({
                "use_project_context": resource_policy.include_project_context,
                "context_release_id": context_release_id,
                "context_character_budget": context_character_budget,
            }, translation_context_mode=translation_context_mode),
        )
        _record_context_metadata(task_id, outcome)
        logging.info("Returned from initial_translate.run")
        task_state.update_task(
            task_id,
            fields={
                "output_dirs": _get_output_directories(mod_name, target_languages),
                "reference_metrics": list(getattr(outcome, "reference_metrics", ())),
                "checkpoint": {
                    "available": False,
                    "resume_supported": bool(use_resume),
                    "stage": "Completed",
                    "updated_at": task_state.utc_now_iso(),
                },
            },
            push=False,
        )
        status, message, issue_count = _workflow_outcome_values(outcome)
        finalize_task(task_id, status, message, "Completed", issue_count)

        if project_id:
            try:
                _run_async(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description=_history_completion_description(status)
                ))
            except Exception as e:
                logging.error(f"Failed to log completion activity (v2): {e}")
    except Exception as e:
        tb_str = traceback.format_exc()
        user_error = f"Translation workflow failed: {e}"
        logging.error(f"{user_error}\n{tb_str}")
        finalize_task(task_id, "failed", user_error, "Failed")
        task_state.append_task_event(
            task_id,
            tb_str,
            audience="diagnostic",
            level="error",
            event_type="traceback",
        )
        if project_id:
            try:
                _run_async(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation workflow failed"
                ))
            except Exception as e:
                logging.error(f"Failed to log failure activity (v2): {e}")

@router.post(
    "/api/translate/start",
    response_model=TranslationTaskResponse,
    response_model_exclude_none=True,
)
async def start_translation_project(request: InitialTranslationRequest, background_tasks: BackgroundTasks):
    """
    Starts the initial translation workflow for a project.
    """
    project = await project_manager.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    provider_runtime = resolve_runtime_or_400(request.api_provider, request.model)
    if request.translation_context_mode == "archive":
        readiness = await translation_context_readiness.inspect(
            request.project_id,
            request.translation_context_mode,
            {
                "project_id": request.project_id,
                "project_name": project.get("name"),
                "game_id": project.get("game_id"),
                "source_path": project.get("source_path"),
                "source_language": request.source_lang_code,
            },
            requested_release_id=request.context_release_id,
        )
        if not readiness["can_start"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "project_context_not_ready",
                    "message": "The requested translation context is not ready for translation.",
                    "retryable": False,
                    "context_readiness": readiness,
                },
            )
    task_id = str(uuid.uuid4())
    try:
        task_state.create_task(
            task_id,
            status="pending",
            fields={
                "kind": "initial_translation",
                "project_id": request.project_id,
                "project_context": {"name": project["name"], "game_id": project.get("game_id")},
                "title": f"Translate {project['name']}",
                "source_route": "/translation",
                "created_by": {"type": "user"},
                "blocking": True,
                "idempotency_key": request.idempotency_key,
                "checkpoint": {
                    "available": False,
                    "resume_supported": request.use_resume,
                    "stage": "Queued",
                },
                "translation_context_mode": request.translation_context_mode,
                **provider_task_fields(provider_runtime),
            },
            dedupe_key=f"project_translation_write:{request.project_id}",
            reject_duplicate=True,
        )
    except task_state.DuplicateTaskError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_task",
                "message": "This project already has a translation task in progress.",
                "existing_task_id": exc.existing_task.get("task_id"),
            },
        ) from exc

    mod_name = os.path.basename(project['source_path'])
    # Ensure source path exists
    if not os.path.exists(project['source_path']):
         raise HTTPException(status_code=400, detail=f"Project source path not found: {project['source_path']}")

    task_state.update_task(
        task_id,
        status="starting",
        append_log=f"Starting translation for project: '{mod_name}'",
        push=True,
    )

    background_tasks.add_task(
        run_translation_workflow_v2,
        task_id,
        mod_name,
        project['game_id'], # Assuming game_id maps to game_profile_id
        request.source_lang_code,
        request.target_lang_codes,
        request.api_provider,
        request.mod_context,
        request.selected_glossary_ids,
        request.model,
        request.use_main_glossary,
        request.custom_lang_config,
        project_id=request.project_id,
        use_resume=request.use_resume,
        clean_source=request.clean_source,
        batch_size_limit=request.batch_size_limit,
        source_context_overlap=request.source_context_overlap,
        concurrency_limit=request.concurrency_limit,
        rpm_limit=request.rpm_limit,
        embedded_workshop=request.embedded_workshop.model_dump() if request.embedded_workshop else None,
        reference_reuse=request.reference_reuse.model_dump() if request.reference_reuse else None,
        **({"provider_runtime": provider_runtime} if provider_runtime else {}),
        **context_workflow_kwargs(request),
    )

    # Auto-register translation path (Optimistic registration)
    # We predict the output path based on the request
    try:
        target_languages = _resolve_requested_target_languages(
            [code.value for code in request.target_lang_codes],
            request.custom_lang_config,
        )
        for result_dir in _get_output_directories(mod_name, target_languages):
            await project_manager.add_translation_path(request.project_id, result_dir)
            logging.info(f"Auto-registered translation path: {result_dir}")
    except Exception as e:
        logging.error(f"Failed to auto-register translation path: {e}")

    return {"task_id": task_id, "status": "started", "message": f"Translation started for project {project['name']}"}

@router.post(
    "/api/translate",
    response_model=TranslationTaskResponse,
    response_model_exclude_none=True,
)
async def start_translation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    game_profile_id: str = Form(...),
    source_lang_code: str = Form(...),
    target_lang_codes: str = Form(...), # Received as a comma-separated string
    api_provider: str = Form(...),
    mod_context: str = Form("")
):
    provider_runtime = resolve_runtime_or_400(api_provider)
    task_id = str(uuid.uuid4())
    task_state.create_task(
        task_id,
        status="pending",
        fields={
            "kind": "initial_translation", "title": "Uploaded Mod translation",
            "source_route": "/translation",
            **provider_task_fields(provider_runtime),
        },
    )
    try:
        mod_name = file.filename.replace(".zip", "")
        source_path = os.path.join(SOURCE_DIR, mod_name)
        if os.path.exists(source_path):
            shutil.rmtree(source_path)
        temp_archive_path = os.path.join(SOURCE_DIR, file.filename)
        with open(temp_archive_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        import zipfile
        with zipfile.ZipFile(temp_archive_path, "r") as zip_ref:
            zip_ref.extractall(source_path)
        extracted_items = os.listdir(source_path)
        if len(extracted_items) == 1:
            potential_inner_folder = os.path.join(source_path, extracted_items[0])
            if os.path.isdir(potential_inner_folder):
                for item_name in os.listdir(potential_inner_folder):
                    shutil.move(os.path.join(potential_inner_folder, item_name), os.path.join(source_path, item_name))
                os.rmdir(potential_inner_folder)
        os.remove(temp_archive_path)
        task_state.update_task(
            task_id,
            status="starting",
            append_log=f"Mod '{mod_name}' uploaded and extracted.",
            push=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File processing failed: {e}")

    try:
        # Normalize languages using strict schema
        from scripts.schemas.common import LanguageCode
        source_lang_code = LanguageCode.from_str(source_lang_code).value
        target_codes = [LanguageCode.from_str(code.strip()).value for code in target_lang_codes.split(',')]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        run_translation_workflow,
        task_id,
        mod_name,
        game_profile_id,
        source_lang_code,
        target_codes,
        api_provider,
        mod_context,
        project_id=None,
        **({"provider_runtime": provider_runtime} if provider_runtime else {}),
    )

    return {"task_id": task_id, "message": "Translation task started."}

@router.post(
    "/api/translate_v2",
    response_model=TranslationTaskResponse,
    response_model_exclude_none=True,
)
async def start_translation_v2(
    background_tasks: BackgroundTasks,
    payload: TranslationRequestV2
):
    provider_runtime = resolve_runtime_or_400(payload.api_provider, payload.model_name)
    task_id = str(uuid.uuid4())
    task_state.create_task(
        task_id,
        status="pending",
        fields={
            "kind": "initial_translation", "title": "Mod translation",
            "source_route": "/translation",
            **provider_task_fields(provider_runtime),
        },
    )

    if not os.path.exists(payload.project_path) or not os.path.isdir(payload.project_path):
        raise HTTPException(status_code=400, detail="Invalid project path.")

    mod_name = os.path.basename(payload.project_path)
    source_path = os.path.join(SOURCE_DIR, mod_name)

    try:
        if not payload.is_existing_source:
            if os.path.exists(source_path):
                shutil.rmtree(source_path)
            shutil.copytree(payload.project_path, source_path)

        task_state.update_task(
            task_id,
            status="starting",
            append_log=f"Using source: '{mod_name}'",
            push=True,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File processing failed: {e}")

    background_tasks.add_task(
        run_translation_workflow_v2,
        task_id,
        mod_name,
        payload.game_profile_id,
        payload.source_lang_code,
        payload.target_lang_codes,
        payload.api_provider,
        payload.mod_context,
        payload.selected_glossary_ids,
        payload.model_name,
        payload.use_main_glossary,
        payload.custom_lang_config,
        project_id=None, # Path-based upload might not have project ID
        use_resume=payload.use_resume,
        clean_source=payload.clean_source,
        embedded_workshop=payload.embedded_workshop.model_dump() if payload.embedded_workshop else None,
        reference_reuse=payload.reference_reuse.model_dump() if payload.reference_reuse else None,
        **({"provider_runtime": provider_runtime} if provider_runtime else {}),
    )

    return {"task_id": task_id, "message": "Translation task started."}

@router.get("/api/source-mods", response_model=List[SourceModResponse])
def get_source_mods():
    """
    Returns a list of directories in the SOURCE_DIR.
    """
    if not os.path.exists(SOURCE_DIR):
        return []

    mods = []
    for item in os.listdir(SOURCE_DIR):
        item_path = os.path.join(SOURCE_DIR, item)
        if os.path.isdir(item_path):
            mods.append({
                "name": item,
                "path": item_path,
                "mtime": os.path.getmtime(item_path)
            })

    # Sort by modification time (newest first)
    mods.sort(key=lambda x: x["mtime"], reverse=True)
    return mods

@router.get("/api/status/{task_id}")
def get_status(task_id: str):
    task = task_state.get_task_payload(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    return task

@router.websocket("/api/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await ws_manager.connect(websocket, task_id)
    try:
        # Send initial state
        task_data = task_state.get_task_payload(task_id)
        if task_data:
            await websocket.send_json(task_data)
        
        while True:
            # Keep connection alive and wait for client to close
            await websocket.receive_text()
    except Exception:
        # Disconnect handled in ws_manager
        pass
    finally:
        ws_manager.disconnect(websocket, task_id)

@router.get("/api/result/{task_id}")
def get_result(task_id: str):
    raise HTTPException(status_code=410, detail="ZIP result downloads have been removed. Open the output folder instead.")

@router.post(
    "/api/translation/checkpoint-status",
    response_model=CheckpointStatusResponse,
)
def check_checkpoint_status(payload: CheckpointStatusRequest):
    """Checks if a checkpoint exists for the given configuration."""
    try:
        # Determine output folder name logic (duplicated from initial_translate, ideally shared)
        # NOTE: This logic must match initial_translate.py exactly
        target_codes = [code.value if hasattr(code, "value") else str(code) for code in payload.target_lang_codes]
        target_languages = _resolve_requested_target_languages(target_codes)
        checkpoint_infos = []
        output_dir = _get_checkpoint_output_dir(payload.mod_name, target_languages)
        for target_lang in target_languages:
            checkpoint_filename = f".remis_checkpoint_{target_lang['code']}.json"
            cm = CheckpointManager(output_dir, checkpoint_filename=checkpoint_filename)
            checkpoint_infos.append({
                "target_lang_code": target_lang["code"],
                **cm.get_checkpoint_info(),
            })
        
        total_files = 0
        if any(item["exists"] for item in checkpoint_infos):
            source_path = os.path.join(SOURCE_DIR, payload.mod_name)
            # Quick count
            for root, _, files in os.walk(source_path):
                for f in files:
                    if f.endswith(".yml") or f.endswith(".txt"):
                        total_files += 1
        
        return {
            "exists": any(item["exists"] for item in checkpoint_infos),
            "completed_count": sum(item["completed_count"] for item in checkpoint_infos),
            "total_files_estimate": total_files,
            "metadata": checkpoint_infos[0]["metadata"] if len(checkpoint_infos) == 1 else {"targets": checkpoint_infos},
            "targets": checkpoint_infos,
        }
    except Exception as e:
        logging.error(f"Error checking checkpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/api/translation/checkpoint",
    response_model=CheckpointDeleteResponse,
)
def delete_checkpoint(payload: CheckpointStatusRequest):
    """Deletes the checkpoint file for the given configuration."""
    try:
        # Determine output folder name logic (duplicated)
        target_codes = [code.value if hasattr(code, "value") else str(code) for code in payload.target_lang_codes]
        target_languages = _resolve_requested_target_languages(target_codes)
        output_dir = _get_checkpoint_output_dir(payload.mod_name, target_languages)
        for target_lang in target_languages:
            checkpoint_filename = f".remis_checkpoint_{target_lang['code']}.json"
            cm = CheckpointManager(output_dir, checkpoint_filename=checkpoint_filename)
            cm.clear_checkpoint()
        return {"status": "success", "message": "Checkpoint deleted."}
    except Exception as e:
        logging.error(f"Error deleting checkpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
