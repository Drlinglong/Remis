import os
import uuid
import shutil
import zipfile
import logging
import traceback
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, WebSocket
from fastapi.responses import FileResponse

from scripts.shared.services import project_manager, glossary_manager, archive_manager
from scripts.shared.task_state import (
    create_task,
    get_task,
    get_task_payload,
    init_progress,
    push_task_update,
    update_progress,
    update_task,
)
from scripts.schemas.translation import InitialTranslationRequest, TranslationRequestV2, CustomLangConfig, CheckpointStatusRequest
from scripts.app_settings import GAME_PROFILES, LANGUAGES, API_PROVIDERS, SOURCE_DIR, DEST_DIR
from scripts.workflows import initial_translate
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii
from scripts.core.checkpoint_manager import CheckpointManager
import asyncio
from scripts.shared.ws_manager import ws_manager
router = APIRouter()


def _build_output_folder_name(mod_name: str, target_languages: List[dict]) -> str:
    sanitized_mod_name = slugify_to_ascii(mod_name)
    if len(target_languages) > 1:
        return f"Multilanguage-{sanitized_mod_name}"
    return f"{target_languages[0]['folder_prefix']}{sanitized_mod_name}"
def run_translation_workflow(task_id: str, mod_name: str, game_profile_id: str, source_lang_code: str, target_lang_codes: List[str], api_provider: str, mod_context: str, project_id: Optional[str] = None):
    """
    A wrapper for the core translation logic to be run in the background.
    """
    # Initialize i18n for the background task
    i18n.load_language('en_US')

    update_task(task_id, status="processing", append_log="Background translation task started.", push=False)

    if project_id:
        try:
            import asyncio
            asyncio.run(project_manager.log_history_event(
                project_id=project_id,
                action_type='translation_workflow',
                description="Translation task started"
            ))
        except Exception as e:
            logging.error(f"Failed to log activity: {e}")

    try:
        # 1. Retrieve full config objects from IDs/codes
        game_profile = GAME_PROFILES.get(game_profile_id)
        source_lang = next((lang for lang in LANGUAGES.values() if lang["code"] == source_lang_code), None)
        target_languages = [lang for lang in LANGUAGES.values() if lang["code"] in target_lang_codes]

        if not all([game_profile, source_lang, target_languages]):
            raise ValueError("无效的游戏配置、源语言或目标语言。")

        # 2. Call the core translation function
        workflow_result = initial_translate.run(
            mod_name=mod_name,
            game_profile=game_profile,
            source_lang=source_lang,
            target_languages=target_languages,
            selected_provider=api_provider,
            mod_context=mod_context,
        )
        workflow_status = (workflow_result or {}).get("status", "failed")
        workflow_message = (workflow_result or {}).get("message", "Translation workflow did not return a valid result.")
        failed_files = (workflow_result or {}).get("failed_files", [])

        # 3. Once done, update status and prepare result
        update_task(
            task_id,
            status=workflow_status,
            message=workflow_message,
            append_log=workflow_message,
            summary={"failed_files": failed_files},
            push=False,
        )

        # Prepare the result for download
        output_folder_name = _build_output_folder_name(mod_name, target_languages)
        result_dir = os.path.join(DEST_DIR, output_folder_name)

        if workflow_status in ("completed", "partial_failed"):
            # Hyper-detailed logging for debugging
            logging.info(f"--- ZIPPING LOGS for Task {task_id} ---")
            logging.info(f"Final check before zipping. Target directory: {result_dir}")
            logging.info(f"Does it exist? {os.path.exists(result_dir)}")
            logging.info(f"Is it a directory? {os.path.isdir(result_dir)}")
            if os.path.exists(result_dir) and os.path.isdir(result_dir):
                logging.info(f"Contents: {os.listdir(result_dir)}")
            logging.info(f"------------------------------------")

            zip_path = shutil.make_archive(result_dir, "zip", result_dir)
            update_task(task_id, result_path=zip_path, push=False)
            if failed_files:
                update_task(task_id, append_log=f"Partial fallback applied to: {', '.join(failed_files)}", push=False)

        if project_id:
            try:
                import asyncio
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type="translation_workflow",
                    description="Translation completed successfully" if workflow_status == "completed" else (
                        "Translation completed with partial failures" if workflow_status == "partial_failed" else "Translation workflow failed"
                    )
                ))
            except Exception as e:
                logging.error(f"Failed to log completion activity: {e}")
        push_task_update(task_id)


    except Exception as e:
        tb_str = traceback.format_exc()
        error_message = f"工作流执行失败 (Workflow execution failed): {e}\n{tb_str}"
        logging.error(f"任务 {task_id} 失败: {error_message}")
        update_task(
            task_id,
            status="failed",
            message=error_message,
            append_log=error_message,
            progress={"stage": "Failed"},
            clear_result_path=True,
            push=False,
        )
        if project_id:
            try:
                import asyncio
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation workflow failed"
                ))
            except Exception as e:
                logging.error(f"Failed to log failure activity: {e}")
        push_task_update(task_id)

def run_translation_workflow_v2(
    task_id: str, mod_name: str, game_profile_id: str, source_lang_code: str,
    target_lang_codes: List[str], api_provider: str, mod_context: str,
    selected_glossary_ids: List[int], model_name: Optional[str], use_main_glossary: bool,
    custom_lang_config: Optional[CustomLangConfig] = None,
    project_id: Optional[str] = None,
    use_resume: bool = True,
    clean_source: bool = False
):
    i18n.load_language('en_US')
    update_task(task_id, status="processing", append_log="Background translation task started (V2).", push=False)
    
    import asyncio

    if project_id:
        try:
            asyncio.run(project_manager.log_history_event(
                project_id=project_id,
                action_type='translation_workflow',
                description="Translation task (V2) started"
            ))
        except Exception as e:
            logging.error(f"Failed to log activity (v2): {e}")

    # Initialize progress structure
    init_progress(task_id)

    last_update_time = [0] # Use a list to make it mutable in the closure
    
    def progress_callback(current, total, current_file, stage="Translating", 
                          current_batch=0, total_batches=0,
                          successful_batches=0, failed_batches=0,
                          error_count=0, glossary_issues=0, format_issues=0,
                          log_message: str = None):
        if not get_task(task_id):
            return

        update_progress(
            task_id,
            current=current,
            total=total,
            current_file=current_file,
            stage=stage,
            current_batch=current_batch,
            total_batches=total_batches,
            successful_batches=successful_batches,
            failed_batches=failed_batches,
            error_count=error_count,
            glossary_issues=glossary_issues,
            format_issues=format_issues,
            log_message=log_message,
            push=False,
        )

        # ───────────── WebSocket Throttling (Issue #133) ─────────────
        import time
        current_time = time.time()

        # Only send update if:
        # 1. 200ms has passed since last update
        # 2. OR it's a critical stage (Completed, Failed)
        # 3. OR it's the 100% mark
        is_final = stage in ("Completed", "Failed") or (total > 0 and current >= total)
        if not is_final and (current_time - last_update_time[0] < 0.2):
            return

        last_update_time[0] = current_time
        push_task_update(task_id)

    try:
        # Debug Logging
        logging.info(f"Starting V2 Workflow for Task {task_id}")
        logging.info(f"Params: game_profile_id={game_profile_id}, source={source_lang_code}, targets={target_lang_codes}")
        
        # Handle legacy/alias 'vic3' -> 'victoria3'
        normalized_game_id = game_profile_id
        if game_profile_id == 'vic3':
            normalized_game_id = 'victoria3'
            logging.info(f"Normalized game_id 'vic3' to '{normalized_game_id}'")

        game_profile = GAME_PROFILES.get(normalized_game_id)
        # Fallback: Try finding by 'id' field in values if key lookup fails
        if not game_profile:
             game_profile = next((p for p in GAME_PROFILES.values() if p['id'] == normalized_game_id), None)

        source_lang = next((lang for lang in LANGUAGES.values() if lang["code"] == source_lang_code), None)
        target_languages = [lang for lang in LANGUAGES.values() if lang["code"] in target_lang_codes]
        
        logging.info(f"Resolved: GameProfile={game_profile is not None}, SourceLang={source_lang is not None}, TargetLangs={len(target_languages)}")

        # If custom language is provided, use it instead (or in addition? For now, let's assume it replaces if target_lang_codes contains 'custom')
        if custom_lang_config:
            # Convert Pydantic model to dict
            custom_lang = custom_lang_config.dict()
            # Ensure it has necessary fields
            if not custom_lang.get('name_en'): custom_lang['name_en'] = custom_lang['name']
            target_languages = [custom_lang]
            logging.info(f"Using Custom Language Config: {custom_lang}")

        if not all([game_profile, source_lang]) or (not target_languages and not custom_lang_config):
            logging.error(f"Validation Failed: GameProfile={game_profile}, SourceLang={source_lang}, TargetLangs={target_languages}")
            raise ValueError("无效的游戏配置、源语言或目标语言。")
        
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
        workflow_result = initial_translate.run(
            mod_name=mod_name, game_profile=game_profile, source_lang=source_lang,
            target_languages=target_languages, selected_provider=api_provider,
            mod_context=mod_context, selected_glossary_ids=final_glossary_ids,
            model_name=model_name, use_glossary=True, progress_callback=progress_callback,
            override_path=override_path, project_id=project_id, use_resume=use_resume,
            clean_source=clean_source
        )
        logging.info("Returned from initial_translate.run")
        workflow_status = (workflow_result or {}).get("status", "failed")
        workflow_message = (workflow_result or {}).get("message", "Translation workflow did not return a valid result.")
        failed_files = (workflow_result or {}).get("failed_files", [])
        update_task(
            task_id,
            status=workflow_status,
            message=workflow_message,
            append_log=workflow_message,
            summary={"failed_files": failed_files},
            progress={
                "percent": 100,
                "stage": "Completed" if workflow_status in ("completed", "partial_failed") else "Failed",
            },
            push=False,
        )
        output_folder_name = _build_output_folder_name(mod_name, target_languages)
        result_dir = os.path.join(DEST_DIR, output_folder_name)
        if workflow_status in ("completed", "partial_failed"):
            zip_path = shutil.make_archive(result_dir, 'zip', result_dir)
            update_task(task_id, result_path=zip_path, push=False)
            if failed_files:
                update_task(task_id, append_log=f"Partial fallback applied to: {', '.join(failed_files)}", push=False)

        if project_id:
            try:
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation completed successfully" if workflow_status == "completed" else (
                        "Translation completed with partial failures" if workflow_status == "partial_failed" else "Translation workflow failed"
                    )
                ))
            except Exception as e:
                logging.error(f"Failed to log completion activity (v2): {e}")
        push_task_update(task_id)
    except Exception as e:
        tb_str = traceback.format_exc()
        error_message = f"工作流执行失败: {e}\n{tb_str}"
        logging.error(error_message) # Log to console!
        update_task(
            task_id,
            status="failed",
            message=error_message,
            append_log=error_message,
            progress={"stage": "Failed"},
            clear_result_path=True,
            push=False,
        )
        if project_id:
            try:
                asyncio.run(project_manager.log_history_event(
                    project_id=project_id,
                    action_type='translation_workflow',
                    description="Translation workflow failed"
                ))
            except Exception as e:
                logging.error(f"Failed to log failure activity (v2): {e}")
        push_task_update(task_id)
@router.post("/api/translate/start")
async def start_translation_project(request: InitialTranslationRequest, background_tasks: BackgroundTasks):
    """
    Starts the initial translation workflow for a project.
    """
    project = await project_manager.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_id = str(uuid.uuid4())
    create_task(task_id)

    # Prepare arguments for the workflow
    # Use the actual folder name from source_path to ensure it matches the directory on disk
    mod_name = os.path.basename(project['source_path'])
    # Ensure source path exists
    if not os.path.exists(project['source_path']):
         raise HTTPException(status_code=400, detail=f"Project source path not found: {project['source_path']}")

    update_task(task_id, status="starting", append_log=f"Starting translation for project: '{mod_name}'", push=False)

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
        clean_source=request.clean_source
    )

    # Auto-register translation path (Optimistic registration)
    # We predict the output path based on the request
    try:
        target_lang_codes = request.target_lang_codes
        if len(target_lang_codes) > 1:
            output_folder_name = f"Multilanguage-{mod_name}"
        else:
            target_code = target_lang_codes[0]
            target_lang = next((l for l in LANGUAGES.values() if l["code"] == target_code), None)
            sanitized_mod_name = slugify_to_ascii(mod_name)
            if target_lang:
                prefix = target_lang.get("folder_prefix", f"{target_lang['code']}-")
                output_folder_name = f"{prefix}{sanitized_mod_name}"
            else:
                output_folder_name = f"{target_code}-{sanitized_mod_name}"
        
        result_dir = os.path.join(DEST_DIR, output_folder_name)
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
    create_task(task_id)
    try:
        mod_name = file.filename.replace(".zip", "")
        source_path = os.path.join(SOURCE_DIR, mod_name)
        if os.path.exists(source_path):
            shutil.rmtree(source_path)
        temp_zip_path = os.path.join(SOURCE_DIR, file.filename)
        with open(temp_zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall(source_path)
        extracted_items = os.listdir(source_path)
        if len(extracted_items) == 1:
            potential_inner_folder = os.path.join(source_path, extracted_items[0])
            if os.path.isdir(potential_inner_folder):
                for item_name in os.listdir(potential_inner_folder):
                    shutil.move(os.path.join(potential_inner_folder, item_name), os.path.join(source_path, item_name))
                os.rmdir(potential_inner_folder)
        os.remove(temp_zip_path) # Clean up the zip file
        update_task(task_id, status="starting", append_log=f"Mod '{mod_name}' 已上传并解压。", push=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")

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

    return {"task_id": task_id, "message": "翻译任务已开始"}

@router.post("/api/translate_v2")
async def start_translation_v2(
    background_tasks: BackgroundTasks,
    payload: TranslationRequestV2
):
    task_id = str(uuid.uuid4())
    create_task(task_id)

    if not os.path.exists(payload.project_path) or not os.path.isdir(payload.project_path):
        raise HTTPException(status_code=400, detail="Invalid project path.")

    mod_name = os.path.basename(payload.project_path)
    source_path = os.path.join(SOURCE_DIR, mod_name)

    try:
        if not payload.is_existing_source:
            if os.path.exists(source_path):
                shutil.rmtree(source_path)
            shutil.copytree(payload.project_path, source_path)
        
        update_task(task_id, status="starting", append_log=f"Using source: '{mod_name}'", push=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")

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
        clean_source=payload.clean_source
    )

    return {"task_id": task_id, "message": "翻译任务已开始"}

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
    task = get_task_payload(task_id)
    if task:
        return task
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    # 限制返回的日志条数，避免响应体过大导致前端卡顿
    # 完整日志仍保留在内存中（后续可改为持久化到文件）
    MAX_LOG_LINES = 100
    result = dict(task)  # 浅拷贝，避免修改原始数据
    if "log" in result and len(result["log"]) > MAX_LOG_LINES:
        result["log"] = result["log"][-MAX_LOG_LINES:]
    return result

@router.websocket("/api/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await ws_manager.connect(websocket, task_id)
    try:
        # Send initial state
        task_data = get_task_payload(task_id)
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
    task = get_task(task_id)
    if not task or task["status"] not in ("completed", "partial_failed"):
        raise HTTPException(status_code=404, detail="任务未完成或结果文件未找到")
    return FileResponse(task["result_path"], media_type='application/zip', filename=os.path.basename(task["result_path"]))

@router.post("/api/translation/checkpoint-status")
def check_checkpoint_status(payload: CheckpointStatusRequest):
    """Checks if a checkpoint exists for the given configuration."""
    try:
        # Determine output folder name logic (duplicated from initial_translate, ideally shared)
        # NOTE: This logic must match initial_translate.py exactly
        is_batch_mode = len(payload.target_lang_codes) > 1
        sanitized_mod_name = slugify_to_ascii(payload.mod_name)
        if is_batch_mode:
            output_folder_name = f"Multilanguage-{sanitized_mod_name}"
        else:
            # We need the folder prefix. This is tricky without the full language object.
            # Assuming standard prefix or we need to look it up.
            # Let's look up the language object from LANGUAGES
            target_code = payload.target_lang_codes[0]
            target_lang = next((l for l in LANGUAGES.values() if l["code"] == target_code), None)
            if target_lang:
                prefix = target_lang.get("folder_prefix", f"{target_lang['code']}-")
                output_folder_name = f"{prefix}{sanitized_mod_name}"
            else:
                # Fallback if lang not found (shouldn't happen if frontend sends valid codes)
                output_folder_name = f"{target_code}-{sanitized_mod_name}"

        output_dir = os.path.join(DEST_DIR, output_folder_name)
        # Use the same language-specific filename as initial_translate.py
        target_code = payload.target_lang_codes[0] if payload.target_lang_codes else "unknown"
        checkpoint_filename = f".remis_checkpoint_{target_code}.json"
        
        cm = CheckpointManager(output_dir, checkpoint_filename=checkpoint_filename)
        info = cm.get_checkpoint_info()
        
        total_files = 0
        if info["exists"]:
            source_path = os.path.join(SOURCE_DIR, payload.mod_name)
            # Quick count
            for root, _, files in os.walk(source_path):
                for f in files:
                    if f.endswith(".yml") or f.endswith(".txt"):
                        total_files += 1
        
        return {
            "exists": info["exists"],
            "completed_count": info["completed_count"],
            "total_files_estimate": total_files,
            "metadata": info["metadata"]
        }
    except Exception as e:
        logging.error(f"Error checking checkpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/translation/checkpoint")
def delete_checkpoint(payload: CheckpointStatusRequest):
    """Deletes the checkpoint file for the given configuration."""
    try:
        # Determine output folder name logic (duplicated)
        is_batch_mode = len(payload.target_lang_codes) > 1
        sanitized_mod_name = slugify_to_ascii(payload.mod_name)
        if is_batch_mode:
            output_folder_name = f"Multilanguage-{sanitized_mod_name}"
        else:
            target_code = payload.target_lang_codes[0]
            target_lang = next((l for l in LANGUAGES.values() if l["code"] == target_code), None)
            if target_lang:
                prefix = target_lang.get("folder_prefix", f"{target_lang['code']}-")
                output_folder_name = f"{prefix}{sanitized_mod_name}"
            else:
                output_folder_name = f"{target_code}-{sanitized_mod_name}"

        output_dir = os.path.join(DEST_DIR, output_folder_name)
        # Use the same language-specific filename as initial_translate.py
        target_code = payload.target_lang_codes[0] if payload.target_lang_codes else "unknown"
        checkpoint_filename = f".remis_checkpoint_{target_code}.json"
        
        cm = CheckpointManager(output_dir, checkpoint_filename=checkpoint_filename)
        cm.clear_checkpoint()
        return {"status": "success", "message": "Checkpoint deleted."}
    except Exception as e:
        logging.error(f"Error deleting checkpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
