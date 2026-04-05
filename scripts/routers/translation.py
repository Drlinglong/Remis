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
from scripts.schemas.translation import InitialTranslationRequest, TranslationRequestV2, CustomLangConfig, CheckpointStatusRequest
from scripts.app_settings import GAME_PROFILES, LANGUAGES, API_PROVIDERS, SOURCE_DIR, DEST_DIR
from scripts.workflows import initial_translate
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii
from scripts.core.checkpoint_manager import CheckpointManager
import threading
import asyncio
from scripts.shared.ws_manager import ws_manager
router = APIRouter()
task_lock = threading.Lock()


def _resolve_target_languages(target_lang_codes: List[str]):
    resolved = []
    for target_code in target_lang_codes:
        lang = next((item for item in LANGUAGES.values() if item["code"] == target_code), None)
        if lang:
            resolved.append(lang)
    return resolved


def _resolve_requested_target_languages(target_lang_codes: List[str], custom_lang_config: Optional[CustomLangConfig] = None) -> List[dict]:
    if custom_lang_config:
        return [custom_lang_config.dict()]
    return _resolve_target_languages(target_lang_codes)


def _get_output_folder_name(mod_name: str, target_lang: dict) -> str:
    prefix = target_lang.get("folder_prefix", f"{target_lang.get('code', 'unknown')}-")
    return f"{prefix}{slugify_to_ascii(mod_name)}"


def _get_output_directories(mod_name: str, target_languages: List[dict]) -> List[str]:
    if len(target_languages) > 1:
        return [os.path.join(DEST_DIR, f"Multilanguage-{slugify_to_ascii(mod_name)}")]
    return [os.path.join(DEST_DIR, _get_output_folder_name(mod_name, target_lang)) for target_lang in target_languages]


def _get_checkpoint_output_dir(mod_name: str, target_languages: List[dict]) -> str:
    return _get_output_directories(mod_name, target_languages)[0]


def push_task_update(task_id: str):
    """Best-effort push of the latest task snapshot to connected WebSocket clients."""
    if task_id not in tasks:
        return

    try:
        max_log_lines = 100
        task_data = dict(tasks[task_id])
        if "log" in task_data and len(task_data["log"]) > max_log_lines:
            task_data["log"] = task_data["log"][-max_log_lines:]
        ws_manager.sync_send_task_update(task_id, task_data)
    except Exception as e:
        logging.error(f"WebSocket push failed: {e}")


def finalize_task(task_id: str, status: str, log_message: Optional[str] = None, stage: Optional[str] = None):
    """Persist terminal task state and force a final status push to the frontend."""
    with task_lock:
        if task_id not in tasks:
            return

        tasks[task_id]["status"] = status
        if "progress" in tasks[task_id]:
            if status == "completed":
                tasks[task_id]["progress"]["percent"] = 100
            if stage:
                tasks[task_id]["progress"]["stage"] = stage
        if log_message:
            tasks[task_id]["log"].append(log_message)

    push_task_update(task_id)


def run_translation_workflow(task_id: str, mod_name: str, game_profile_id: str, source_lang_code: str, target_lang_codes: List[str], api_provider: str, mod_context: str, project_id: Optional[str] = None):
    """
    A wrapper for the core translation logic to be run in the background.
    """
    i18n.load_language('en_US')

    tasks[task_id]["status"] = "processing"
    tasks[task_id]["log"].append("Initializing translation workflow...")

    if project_id:
        try:
            asyncio.run(project_manager.log_history_event(
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

        initial_translate.run(
            mod_name=mod_name,
            game_profile=game_profile,
            source_lang=source_lang,
            target_languages=target_languages,
            selected_provider=api_provider,
            mod_context=mod_context,
        )

        tasks[task_id]["output_dirs"] = _get_output_directories(mod_name, target_languages)
        finalize_task(task_id, "completed", "Translation workflow completed successfully.")

        if project_id:
            try:
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation completed successfully"
                ))
            except Exception as e:
                logging.error(f"Failed to log completion activity: {e}")

    except Exception as e:
        tb_str = traceback.format_exc()
        error_message = f"Translation workflow execution failed: {e}\n{tb_str}"
        logging.error(f"Task {task_id} failed: {error_message}")
        finalize_task(task_id, "failed", error_message, "Failed")
        if project_id:
            try:
                asyncio.run(project_manager.log_history_event(
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
    concurrency_limit: Optional[int] = None,
    rpm_limit: Optional[int] = 40,
    embedded_workshop: Optional[dict] = None,
):
    i18n.load_language('en_US')
    tasks[task_id]["status"] = "processing"
    tasks[task_id]["log"].append("Initializing translation workflow (V2)...")

    if project_id:
        try:
            asyncio.run(project_manager.log_history_event(
                project_id=project_id,
                action_type='translation_workflow',
                description="Translation task (V2) started"
            ))
        except Exception as e:
            logging.error(f"Failed to log activity (v2): {e}")

    tasks[task_id]["progress"] = {
        "total": 0,
        "current": 0,
        "percent": 0,
        "current_file": "",
        "stage": "Initializing",
        "total_batches": 0,
        "current_batch": 0,
        "error_count": 0,
        "glossary_issues": 0,
        "format_issues": 0
    }

    last_update_time = [0]

    def progress_callback(current, total, current_file, stage="Translating",
                          current_batch=0, total_batches=0,
                          error_count=0, glossary_issues=0, format_issues=0,
                          log_message: str = None):
        with task_lock:
            if task_id not in tasks:
                return

            tasks[task_id]["progress"]["current"] = current
            tasks[task_id]["progress"]["total"] = total
            tasks[task_id]["progress"]["current_file"] = current_file
            tasks[task_id]["progress"]["stage"] = stage
            tasks[task_id]["progress"]["current_batch"] = current_batch
            tasks[task_id]["progress"]["total_batches"] = total_batches
            tasks[task_id]["progress"]["error_count"] = error_count
            tasks[task_id]["progress"]["glossary_issues"] = glossary_issues
            tasks[task_id]["progress"]["format_issues"] = format_issues

            if log_message:
                tasks[task_id]["log"].append(log_message)
                if len(tasks[task_id]["log"]) > 1000:
                    tasks[task_id]["log"] = tasks[task_id]["log"][-500:]

            if total > 0:
                tasks[task_id]["progress"]["percent"] = int((current / total) * 100)

            import time
            current_time = time.time()
            is_final = stage in ("Completed", "Failed") or (total > 0 and current >= total)
            if not is_final and (current_time - last_update_time[0] < 0.2):
                return

            last_update_time[0] = current_time
            push_task_update(task_id)

    try:
        logging.info(f"Starting V2 Workflow for Task {task_id}")
        logging.info(f"Params: game_profile_id={game_profile_id}, source={source_lang_code}, targets={target_lang_codes}")

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
            custom_lang = custom_lang_config.dict()
            if not custom_lang.get('name_en'):
                custom_lang['name_en'] = custom_lang['name']
            target_languages = [custom_lang]
            logging.info(f"Using Custom Language Config: {custom_lang}")

        if not all([game_profile, source_lang]) or (not target_languages and not custom_lang_config):
            logging.error(f"Validation Failed: GameProfile={game_profile}, SourceLang={source_lang}, TargetLangs={target_languages}")
            raise ValueError("Failed to resolve game profile, source language, or target languages.")

        final_glossary_ids = list(selected_glossary_ids) if selected_glossary_ids else []
        if use_main_glossary:
            available = asyncio.run(glossary_manager.get_available_glossaries(game_profile["id"]))
            main_glossary = next((g for g in available if g.get('is_main')), None)
            if main_glossary and main_glossary['glossary_id'] not in final_glossary_ids:
                final_glossary_ids.append(main_glossary['glossary_id'])

        override_path = None
        if project_id:
            try:
                proj = asyncio.run(project_manager.get_project(project_id))
                if proj and 'source_path' in proj:
                    override_path = proj['source_path']
                    logging.info(f"Using override source path from project: {override_path}")
            except Exception as e:
                logging.error(f"Failed to fetch override path: {e}")

        logging.info("Calling initial_translate.run...")
        initial_translate.run(
            mod_name=mod_name, game_profile=game_profile, source_lang=source_lang,
            target_languages=target_languages, selected_provider=api_provider,
            mod_context=mod_context, selected_glossary_ids=final_glossary_ids,
            model_name=model_name, use_glossary=True, progress_callback=progress_callback,
            override_path=override_path, project_id=project_id, use_resume=use_resume,
            clean_source=clean_source, batch_size_limit=batch_size_limit,
            concurrency_limit=concurrency_limit, rpm_limit=rpm_limit,
            embedded_workshop=embedded_workshop
        )
        logging.info("Returned from initial_translate.run")
        tasks[task_id]["output_dirs"] = _get_output_directories(mod_name, target_languages)
        finalize_task(task_id, "completed", "Translation workflow completed successfully.", "Completed")
        push_task_update(task_id)

        if project_id:
            try:
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation completed successfully"
                ))
            except Exception as e:
                logging.error(f"Failed to log completion activity (v2): {e}")
    except Exception as e:
        tb_str = traceback.format_exc()
        error_message = f"Translation workflow failed: {e}\n{tb_str}"
        logging.error(error_message)
        finalize_task(task_id, "failed", error_message, "Failed")
        if project_id:
            try:
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation workflow failed"
                ))
            except Exception as e:
                logging.error(f"Failed to log failure activity (v2): {e}")

@router.post("/api/translate/start")
async def start_translation_project(request: InitialTranslationRequest, background_tasks: BackgroundTasks):
    """
    Starts the initial translation workflow for a project.
    """
    project = await project_manager.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "log": []}

    # Prepare arguments for the workflow
    # Use the actual folder name from source_path to ensure it matches the directory on disk
    mod_name = os.path.basename(project['source_path'])
    # Ensure source path exists
    if not os.path.exists(project['source_path']):
         raise HTTPException(status_code=400, detail=f"Project source path not found: {project['source_path']}")

    tasks[task_id]["status"] = "starting"
    tasks[task_id]["log"].append(f"Starting translation for project: '{mod_name}'")

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
        concurrency_limit=request.concurrency_limit,
        rpm_limit=request.rpm_limit,
        embedded_workshop=request.embedded_workshop.model_dump() if request.embedded_workshop else None,
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

@router.post("/api/translate")
async def start_translation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    game_profile_id: str = Form(...),
    source_lang_code: str = Form(...),
    target_lang_codes: str = Form(...), # Received as a comma-separated string
    api_provider: str = Form(...),
    mod_context: str = Form("")
):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "log": []}
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
        tasks[task_id]["status"] = "starting"
        tasks[task_id]["log"].append(f"Mod '{mod_name}' uploaded and extracted.")
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
        project_id=None # Zip upload has no project ID
    )

    return {"task_id": task_id, "message": "Translation task started."}

@router.post("/api/translate_v2")
async def start_translation_v2(
    background_tasks: BackgroundTasks,
    payload: TranslationRequestV2
):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "log": []}

    if not os.path.exists(payload.project_path) or not os.path.isdir(payload.project_path):
        raise HTTPException(status_code=400, detail="Invalid project path.")

    mod_name = os.path.basename(payload.project_path)
    source_path = os.path.join(SOURCE_DIR, mod_name)

    try:
        if not payload.is_existing_source:
            if os.path.exists(source_path):
                shutil.rmtree(source_path)
            shutil.copytree(payload.project_path, source_path)

        tasks[task_id]["status"] = "starting"
        tasks[task_id]["log"].append(f"Using source: '{mod_name}'")

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
    )

    return {"task_id": task_id, "message": "Translation task started."}

@router.get("/api/source-mods")
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
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    # Limit returned log lines to avoid oversized responses or UI stalls.
    MAX_LOG_LINES = 100
    result = dict(task)  # Shallow copy to avoid mutating the original task state.
    if "log" in result and len(result["log"]) > MAX_LOG_LINES:
        result["log"] = result["log"][-MAX_LOG_LINES:]
    return result

@router.websocket("/api/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await ws_manager.connect(websocket, task_id)
    try:
        # Send initial state
        if task_id in tasks:
            MAX_LOG_LINES = 100
            task_data = dict(tasks[task_id])
            if "log" in task_data and len(task_data["log"]) > MAX_LOG_LINES:
                task_data["log"] = task_data["log"][-MAX_LOG_LINES:]
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

@router.post("/api/translation/checkpoint-status")
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

@router.delete("/api/translation/checkpoint")
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
