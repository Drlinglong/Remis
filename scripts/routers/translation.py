import os
import uuid
import shutil
import zipfile
import logging
import traceback
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
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
router = APIRouter()
task_lock = threading.Lock()

def run_translation_workflow(task_id: str, mod_name: str, game_profile_id: str, source_lang_code: str, target_lang_codes: List[str], api_provider: str, mod_context: str, project_id: Optional[str] = None):
    """
    A wrapper for the core translation logic to be run in the background.
    """
    # Initialize i18n for the background task
    i18n.load_language('en_US')

    tasks[task_id]["status"] = "processing"
    tasks[task_id]["log"].append("背景翻译任务开始...")

    if project_id:
        try:
            project_manager.repository.add_activity_log(
                project_id=project_id,
                activity_type='translation_workflow',
                description="Translation task started"
            )
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
        initial_translate.run(
            mod_name=mod_name,
            game_profile=game_profile,
            source_lang=source_lang,
            target_languages=target_languages,
            selected_provider=api_provider,
            mod_context=mod_context,
        )

        # 3. Once done, update status and prepare result
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["log"].append("翻译流程成功完成！")

        # Prepare the result for download
        sanitized_mod_name = slugify_to_ascii(mod_name)
        output_folder_name = f"{target_languages[0]['folder_prefix']}{sanitized_mod_name}"
        if len(target_languages) > 1:
            output_folder_name = f"Multilanguage-{sanitized_mod_name}"

        result_dir = os.path.join(DEST_DIR, output_folder_name)

        # Hyper-detailed logging for debugging
        logging.info(f"--- ZIPPING LOGS for Task {task_id} ---")
        logging.info(f"Final check before zipping. Target directory: {result_dir}")
        logging.info(f"Does it exist? {os.path.exists(result_dir)}")
        logging.info(f"Is it a directory? {os.path.isdir(result_dir)}")
        if os.path.exists(result_dir) and os.path.isdir(result_dir):
            logging.info(f"Contents: {os.listdir(result_dir)}")
        logging.info(f"------------------------------------")

        zip_path = shutil.make_archive(result_dir, 'zip', result_dir)
        tasks[task_id]["result_path"] = zip_path

        if project_id:
            try:
                project_manager.repository.add_activity_log(
                    project_id=project_id,
                    activity_type='translation_workflow',
                    description="Translation completed successfully"
                )
            except Exception as e:
                logging.error(f"Failed to log completion activity: {e}")

    except Exception as e:
        tb_str = traceback.format_exc()
        error_message = f"工作流执行失败 (Workflow execution failed): {e}\n{tb_str}"
        logging.error(f"任务 {task_id} 失败: {error_message}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["log"].append(error_message)
        # 确保失败的任务没有可下载的结果路径
        if "result_path" in tasks[task_id]:
            del tasks[task_id]["result_path"]
        if project_id:
            try:
                project_manager.repository.add_activity_log(
                    project_id=project_id,
                    activity_type='translation_workflow',
                    description="Translation workflow failed"
                )
            except Exception as e:
                logging.error(f"Failed to log failure activity: {e}")

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
    tasks[task_id]["status"] = "processing"
    tasks[task_id]["log"].append("背景翻译任务开始 (V2)...")
    
    if project_id:
        try:
            project_manager.repository.add_activity_log(
                project_id=project_id,
                activity_type='translation_workflow',
                description="Translation task (V2) started"
            )
        except Exception as e:
            logging.error(f"Failed to log activity (v2): {e}")

    # Initialize progress structure
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

    def progress_callback(current, total, current_file, stage="Translating", 
                          current_batch=0, total_batches=0, 
                          error_count=0, glossary_issues=0, format_issues=0,
                          log_message: str = None):
        with task_lock:
            if task_id not in tasks: return
            
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
            
            if total > 0:
                tasks[task_id]["progress"]["percent"] = int((current / total) * 100)

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
            available = glossary_manager.get_available_glossaries(game_profile["id"])
            main_glossary = next((g for g in available if g.get('is_main')), None)
            if main_glossary and main_glossary['glossary_id'] not in final_glossary_ids:
                final_glossary_ids.append(main_glossary['glossary_id'])
        
        override_path = None
        if project_id:
            try:
                proj = project_manager.get_project(project_id)
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
            clean_source=clean_source
        )
        logging.info("Returned from initial_translate.run")
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"]["percent"] = 100
        tasks[task_id]["progress"]["stage"] = "Completed"
        tasks[task_id]["log"].append("翻译流程成功完成！")
        output_folder_name = f"{target_languages[0]['folder_prefix']}{slugify_to_ascii(mod_name)}"
        if len(target_languages) > 1:
            output_folder_name = f"Multilanguage-{slugify_to_ascii(mod_name)}"
        result_dir = os.path.join(DEST_DIR, output_folder_name)
        zip_path = shutil.make_archive(result_dir, 'zip', result_dir)
        tasks[task_id]["result_path"] = zip_path

        if project_id:
            try:
                project_manager.repository.add_activity_log(
                    project_id=project_id,
                    activity_type='translation_workflow',
                    description="Translation completed successfully"
                )
            except Exception as e:
                logging.error(f"Failed to log completion activity (v2): {e}")
    except Exception as e:
        tb_str = traceback.format_exc()
        error_message = f"工作流执行失败: {e}\n{tb_str}"
        logging.error(error_message) # Log to console!
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["log"].append(error_message)
        if project_id:
            try:
                project_manager.repository.add_activity_log(
                    project_id=project_id,
                    activity_type='translation_workflow',
                    description="Translation workflow failed"
                )
            except Exception as e:
                logging.error(f"Failed to log failure activity (v2): {e}")
@router.post("/api/translate/start")
def start_translation_project(request: InitialTranslationRequest, background_tasks: BackgroundTasks):
    """
    Starts the initial translation workflow for a project.
    """
    project = project_manager.get_project(request.project_id)
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
        project_manager.add_translation_path(request.project_id, result_dir)
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
        tasks[task_id]["status"] = "starting"
        tasks[task_id]["log"].append(f"Mod '{mod_name}' 已上传并解压。")
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
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    # 限制返回的日志条数，避免响应体过大导致前端卡顿
    # 完整日志仍保留在内存中（后续可改为持久化到文件）
    MAX_LOG_LINES = 100
    result = dict(task)  # 浅拷贝，避免修改原始数据
    if "log" in result and len(result["log"]) > MAX_LOG_LINES:
        result["log"] = result["log"][-MAX_LOG_LINES:]
    return result

@router.get("/api/result/{task_id}")
def get_result(task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != "completed":
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
        cm = CheckpointManager(output_dir)
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
        cm = CheckpointManager(output_dir)
        cm.clear_checkpoint()
        return {"status": "success", "message": "Checkpoint deleted."}
    except Exception as e:
        logging.error(f"Error deleting checkpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
