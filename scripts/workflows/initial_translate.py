# scripts/workflows/initial_translate.py
import os
import logging
from typing import Any, Optional, List, Iterator

from scripts.core import file_parser, api_handler, file_builder, asset_handler, directory_handler
from scripts.core.glossary_manager import glossary_manager
from scripts.core.proofreading_tracker import create_proofreading_tracker
from scripts.core.parallel_processor import ParallelProcessor, FileTask
from scripts.core.loc_parser import parse_loc_file
from scripts.core.archive_manager import archive_manager
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.shared.services import project_manager
from scripts.app_settings import SOURCE_DIR, DEST_DIR, LANGUAGES, RECOMMENDED_MAX_WORKERS, ARCHIVE_RESULTS_AFTER_TRANSLATION, CHUNK_SIZE, GEMINI_CLI_CHUNK_SIZE, OLLAMA_CHUNK_SIZE
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii


def run(mod_name: str,
        source_lang: dict,
        target_languages: list[dict],
        game_profile: dict,
        mod_context: str,
        selected_provider: str = "gemini",
        selected_glossary_ids: Optional[List[int]] = None,
        mod_id_for_archive: Optional[int] = None,
        model_name: Optional[str] = None,
        use_glossary: bool = True,
        project_id: Optional[str] = None,
        custom_lang_config: Optional[dict] = None,
        progress_callback: Optional[Any] = None,
        override_path: Optional[str] = None,
        use_resume: bool = True,
        clean_source: bool = False):
    """【最终版】初次翻译工作流（多语言 & 多游戏兼容）- 流式处理 & 断点续传版"""
    logging.info("Entered initial_translate.run")
    logging.info(f"--- Starting 'Initial Translation' workflow for: {mod_name} ---")
    # ───────────── 1. 路径与模式 ─────────────
    is_batch_mode = len(target_languages) > 1
    if is_batch_mode:
        output_folder_name = f"Multilanguage-{slugify_to_ascii(mod_name)}"
        primary_target_lang = LANGUAGES["1"]  # English
    else:
        target_lang = target_languages[0]
        prefix = target_lang.get("folder_prefix", f"{target_lang['code']}-")
        # Sanitize folder name but keep prefix readable
        output_folder_name = f"{prefix}{slugify_to_ascii(mod_name)}"
        primary_target_lang = target_lang

    logging.info(i18n.t("start_workflow",
                 workflow_name=i18n.t("workflow_initial_translate_name"),
                 mod_name=mod_name))
    logging.info(i18n.t("log_selected_provider", provider=selected_provider))

    # ───────────── 2. 初始化客户端 ─────────────
    gemini_cli_model = model_name
    if selected_provider == "gemini_cli" and not gemini_cli_model:
        logging.warning("No model specified for Gemini CLI. Defaulting to 'gemini-1.5-flash'.")
        gemini_cli_model = "gemini-1.5-flash"

    handler = api_handler.get_handler(selected_provider, model_name=gemini_cli_model)
    if not handler or not handler.client:
        logging.warning(i18n.t("api_key_not_configured", provider=selected_provider))
        return

    # ───────────── 2.5. 加载词典 ─────────────
    game_id = game_profile.get("id", "")
    game_id = game_profile.get("id", "")
    if game_id and use_glossary:
        import asyncio
        if selected_glossary_ids:
            asyncio.run(glossary_manager.load_selected_glossaries(selected_glossary_ids))
        else:
            asyncio.run(glossary_manager.load_game_glossary(game_id))

    # ───────────── 3. 创建输出目录 & 初始化断点管理器 ─────────────
    directory_handler.create_output_structure(mod_name, output_folder_name, game_profile)
    asset_handler.copy_assets(mod_name, output_folder_name, game_profile)
    
    output_dir_path = os.path.join(DEST_DIR, output_folder_name)
    
    # ───────────── 3.5. [NEW] 清理源文件 (如果启用) ─────────────
    if clean_source:
        logging.info("Cleaning source directory to save disk space (keeping only localization and metadata)...")
        mod_root_path = override_path if override_path else os.path.join(SOURCE_DIR, mod_name)
        
        # Whitelist: Only these top-level items will be preserved.
        WHITELIST_FOLDERS = {'localisation', 'localization', 'customizable_localization'}
        WHITELIST_FILES = {'descriptor.mod', 'thumbnail.png', 'thumbnail.jpg', 'metadata.json', 'remote_file_id.txt'}
        
        files_removed = 0
        folders_removed = 0
        bytes_freed = 0
        
        for item_name in os.listdir(mod_root_path):
            item_path = os.path.join(mod_root_path, item_name)
            item_lower = item_name.lower()
            
            if os.path.isdir(item_path):
                if item_lower not in WHITELIST_FOLDERS:
                    try:
                        folder_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(item_path) for f in fns)
                        shutil.rmtree(item_path)
                        folders_removed += 1
                        bytes_freed += folder_size
                        logging.debug(f"Deleted directory: {item_name}")
                    except OSError as e:
                        logging.warning(f"Failed to delete directory {item_name}: {e}")
            else:
                if item_lower not in WHITELIST_FILES:
                    try:
                        file_size = os.path.getsize(item_path)
                        os.remove(item_path)
                        files_removed += 1
                        bytes_freed += file_size
                        logging.debug(f"Deleted file: {item_name}")
                    except OSError as e:
                        logging.warning(f"Failed to delete file {item_name}: {e}")
        
        logging.info(f"Clean Source: Removed {folders_removed} folders and {files_removed} files, freed {bytes_freed/1024/1024:.2f} MB.")

    # ───────────── 4. 发现所有源文件 (Discovery Phase) ─────────────
    all_file_paths = discover_files(mod_name, game_profile, source_lang, override_path=override_path)

    if not all_file_paths:
        logging.warning(i18n.t("no_localisable_files_found", lang_name=source_lang['name']))
        return

    # Update progress total
    total_files = len(all_file_paths)
    if progress_callback:
        progress_callback(0, total_files, "", "Analyzing Files")

    # ───────────── 4.5. 强制全量备份 (Brute Force Backup) ─────────────
    # 策略变更：数据安全第一。在开始任何翻译前，强制将所有源文件读入内存并创建快照。
    # 即使是大 Mod，文本数据通常也不超过 50MB，内存不是瓶颈。
    
    logging.info("Reading all source files for backup...")
    all_files_content = []
    
    for idx, file_info in enumerate(all_file_paths):
        fp = file_info["path"]
        if progress_callback:
             progress_callback(idx, total_files, file_info["filename"], "Reading Source")
        try:
            orig, texts, km = file_parser.extract_translatable_content(fp)
            # 仅存储包含可翻译文本的文件
            if texts: 
                file_info["original_lines"] = orig
                file_info["texts_to_translate"] = texts
                file_info["key_map"] = km
                all_files_content.append(file_info)
            else:
                # 空文件也保留
                file_info["original_lines"] = orig
                file_info["texts_to_translate"] = []
                file_info["key_map"] = []
                all_files_content.append(file_info)
                
        except Exception as e:
            logging.error(f"Failed to parse file {fp} for backup: {e}")
            logging.error("Aborting workflow due to file read error.")
            return

    # Calculate Total Batches (Pre-calculation)
    total_batches = 0
    # Determine chunk size based on provider
    if selected_provider == "gemini_cli":
        chunk_size = GEMINI_CLI_CHUNK_SIZE
    elif selected_provider == "ollama":
        chunk_size = OLLAMA_CHUNK_SIZE
    else:
        chunk_size = CHUNK_SIZE

    for file_data in all_files_content:
        if not file_data["texts_to_translate"]: continue
        total_batches += (len(file_data["texts_to_translate"]) + chunk_size - 1) // chunk_size

    # Determine display name for archive (consistent with ProjectManager and Proofreading)
    archive_mod_name = mod_name # Fallback to folder name
    if project_id:
        try:
            from scripts.shared.services import project_manager
            proj = project_manager.get_project(project_id)
            if proj:
                archive_mod_name = proj['name']
        except Exception as e:
            logging.error(f"Failed to fetch project name for archive: {e}")

    # 创建源版本快照
    mod_id = archive_manager.get_or_create_mod_entry(archive_mod_name, f"local_{mod_name}")
    if not mod_id:
        logging.error("Failed to get/create mod entry in database. Aborting.")
        return

    logging.info("Creating source version snapshot...")
    if progress_callback:
        progress_callback(0, total_files, "", "Creating Backup", total_batches=total_batches)
        
    version_id = archive_manager.create_source_version(mod_id, all_files_content)
    
    if not version_id:
        logging.error("Failed to create source version snapshot. Aborting workflow to prevent data loss.")
        return
        
    logging.info(f"Source snapshot created successfully (Version ID: {version_id}). Proceeding to translation.")

    # ───────────── 5. 多语言并行翻译 (Streaming from Memory) ─────────────
    
    # 准备归档 (如果需要)
    should_archive = ARCHIVE_RESULTS_AFTER_TRANSLATION or (project_id is not None)
    version_id_for_archive = None
    if should_archive and not mod_id_for_archive:
         mod_id_for_archive = archive_manager.get_or_create_mod_entry(mod_name, f"local_{mod_name}")

    import threading

    for target_lang in target_languages:
        logging.info(i18n.t("translating_to_language", lang_name=target_lang["name"]))
        
        proofreading_tracker = create_proofreading_tracker(
            mod_name, output_folder_name, target_lang.get("code", "zh-CN")
        )

        # Initialize Checkpoint Manager for this language
        current_config = {
            "model_name": gemini_cli_model or selected_provider,
            "source_lang": source_lang.get("code"),
            "target_lang_code": target_lang.get("code")
        }
        # Use a unique checkpoint file for each language to prevent conflicts in batch mode
        checkpoint_filename = f".remis_checkpoint_{target_lang.get('code', 'unknown')}.json"
        checkpoint_manager = CheckpointManager(output_dir_path, current_config=current_config, checkpoint_filename=checkpoint_filename)

        # If use_resume is False, clear any existing checkpoint for a fresh start
        if not use_resume:
            checkpoint_manager.clear_checkpoint()
            logging.info(f"use_resume is False - cleared checkpoint for {target_lang.get('code')}")



        # Progress Tracking State
        completed_batches = 0
        processed_files_count = 0
        error_count = 0
        glossary_issues = 0
        format_issues = 0
        progress_lock = threading.Lock()

        def update_progress(current_file_name="", stage="Translating", log_message=None, format_issues_override=None):
            nonlocal format_issues
            if format_issues_override is not None:
                format_issues = format_issues_override

            if progress_callback:
                # PROGRESS FIX: Use batch counts for 'current' and 'total' so the progress bar is smooth.
                # 'processed_files_count' and 'total_files' are still tracked but not used for the percentage calculation.
                progress_callback(
                    current=completed_batches,
                    total=total_batches,
                    current_file=current_file_name,
                    stage=stage,
                    current_batch=completed_batches,
                    total_batches=total_batches,
                    error_count=error_count,
                    glossary_issues=glossary_issues,
                    format_issues=format_issues,
                    log_message=log_message
                )

        # 定义文件任务生成器 (Producer) - 现在从内存读取
        def file_task_generator() -> Iterator[FileTask]:
            for file_data in all_files_content:
                # 检查断点
                if checkpoint_manager.is_file_completed(file_data["filename"]):
                    logging.info(f"Skipping completed file: {file_data['filename']}")
                    continue

                texts = file_data["texts_to_translate"]
                orig = file_data["original_lines"]
                km = file_data["key_map"]

                # 如果是空文件，直接处理并跳过生成器
                if not texts:
                    _handle_empty_file(file_data, orig, texts, km, source_lang, target_lang, game_profile, output_folder_name, mod_name, proofreading_tracker)
                    checkpoint_manager.mark_file_completed(file_data["filename"])
                    # Update progress for empty files
                    nonlocal processed_files_count
                    processed_files_count += 1
                    update_progress(file_data["filename"], log_message=f"Skipped empty file: {file_data['filename']}")
                    continue

                yield FileTask(
                    filename=file_data["filename"],
                    root=file_data["root"],
                    original_lines=orig,
                    texts_to_translate=texts,
                    key_map=km,
                    is_custom_loc=file_data["is_custom_loc"],
                    target_lang=target_lang,
                    source_lang=source_lang,
                    game_profile=game_profile,
                    mod_context=mod_context,
                    provider_name=handler.provider_name,
                    output_folder_name=output_folder_name,
                    source_dir=SOURCE_DIR,
                    dest_dir=DEST_DIR,
                    client=handler.client,
                    mod_name=mod_name,
                    loc_root=file_data.get("loc_root", "")
                )

        # 初始化并行处理器
        max_workers = RECOMMENDED_MAX_WORKERS
        if selected_provider == "ollama":
            max_workers = 1 # Ollama usually can't handle parallel requests well locally
        
        processor = ParallelProcessor(max_workers=max_workers)

        # 定义翻译函数 (Consumer)
        def translation_wrapper(batch_task):
            result = handler.translate_batch(batch_task)
            with progress_lock:
                nonlocal completed_batches
                completed_batches += 1
                update_progress(batch_task.file_task.filename)
            return result

        # ───────────── Log Capture Handler ─────────────
        class CallbackHandler(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    if "GET /api/status" in msg: return 
                    update_progress(log_message=msg)
                except Exception:
                    self.handleError(record)

        log_handler = CallbackHandler()
        log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(log_handler)

        try:
            # 开始流式处理
            for file_task, translated_texts, warnings, is_failed in processor.process_files_stream(file_task_generator(), translation_wrapper):
                processed_files_count += 1
                
                # Aggregate warnings and send logs
                if is_failed:
                    error_count += 1
                    logging.error(f"File {file_task.filename} failed to translate (partially or fully). Using fallback.")
                    update_progress(file_task.filename, "Failed", log_message=f"ERROR: File {file_task.filename} failed to translate. Rolled back to original text.")
                
                if warnings:
                    # (Already handled by log handler but good for internal state)
                    pass

                # 这里的 update_progress 主要是为了更新文件计数，日志已经在 logging.info 中捕获
                update_progress(file_task.filename, log_message=f"SUCCESS: {file_task.filename} translated.")

                # 构建目标目录
                dest_dir = _build_dest_dir(file_task, target_lang, output_folder_name, game_profile)
                os.makedirs(dest_dir, exist_ok=True)

                # 重建并写入文件
                dest_file_path = file_builder.rebuild_and_write_file(
                    file_task.original_lines,
                    file_task.texts_to_translate,
                    translated_texts,
                    file_task.key_map,
                    dest_dir,
                    file_task.filename,
                    file_task.source_lang,
                    file_task.target_lang,
                    file_task.game_profile,
                )

                # 更新校对进度
                if dest_file_path:
                    source_file_path = os.path.join(file_task.root, file_task.filename)
                    proofreading_tracker.add_file_info({
                        'source_path': source_file_path,
                        'dest_path': dest_file_path,
                        'translated_lines': len(file_task.texts_to_translate),
                        'filename': file_task.filename,
                        'is_custom_loc': file_task.is_custom_loc
                    })
                    logging.info(i18n.t("file_build_completed", filename=os.path.basename(dest_file_path)))

                # 标记断点
                checkpoint_manager.mark_file_completed(file_task.filename)

                # --- [SYNC] Update Database Status ---
                if project_id:
                    try:
                        # Find the file in DB to update its status
                        source_file_path = os.path.join(file_task.root, file_task.filename)
                        # We use the repository directly or via project_manager if it has a helper
                        # For now, let's use repository via project_manager for consistency
                        import uuid
                        # Re-generate the file_id using the same logic as FileService
                        fid = str(uuid.uuid5(uuid.NAMESPACE_URL, source_file_path.lower().replace('\\', '/')))
                        project_manager.repository.update_file_status_by_id(fid, 'translated')
                    except Exception as e:
                        logging.error(f"Failed to update DB status for {file_task.filename}: {e}")

                # 实时归档翻译结果 (Incremental Archiving)
                if version_id:
                    try:
                        archive_manager.archive_translated_results(
                            version_id,
                            {file_task.filename: translated_texts},
                            all_files_content,
                            target_lang.get("code")
                        )
                    except Exception as e:
                        logging.error(f"Failed to archive results for {file_task.filename}: {e}")

        finally:
            logging.getLogger().removeHandler(log_handler)

        # ───────────── 6. 后处理 & 归档 ─────────────
        # (Post-processing logic remains similar, but runs after all files are done)
        _run_post_processing(mod_name, game_profile, target_lang, source_lang, output_folder_name, proofreading_tracker, update_progress)

        # 保存校对看板
        proofreading_tracker.save_proofreading_progress()

    # ───────────── 7. 元数据处理 ─────────────
    if is_batch_mode:
        process_metadata_for_language(mod_name, handler, source_lang, primary_target_lang, output_folder_name, mod_context, game_profile)
    else:
        process_metadata_for_language(mod_name, handler, source_lang, target_lang, output_folder_name, mod_context, game_profile)

    # ───────────── 8. 清理断点 ─────────────
    checkpoint_manager.clear_checkpoint()
    
    logging.info(i18n.t("translation_workflow_completed"))
    logging.info(i18n.t("output_folder_created", folder=output_folder_name))

    # ───────────── 9. 自动同步项目 ─────────────
    if project_id:
        try:
            logging.info(f"Automatically syncing project {project_id}...")
            # 1. 注册输出目录
            project_manager.add_translation_path(project_id, output_dir_path)
            # 2. 触发全量刷新以确保 UI 一致
            project_manager.refresh_project_files(project_id)
        except Exception as e:
            logging.error(f"Failed to auto-sync project: {e}")


def _handle_empty_file(file_info, orig, texts, km, source_lang, target_lang, game_profile, output_folder_name, mod_name, proofreading_tracker):
    """处理空文件的辅助函数"""
    # 创建临时的 FileTask (用于复用 _build_dest_dir)
    # 这里为了简单，直接手动构建路径
    # ... (Simplified logic)
    pass # Implementation detail, can be expanded if needed.
    # Actually, let's just use the file_builder directly if possible.
    # We need dest_dir.
    temp_task = FileTask(
        filename=file_info["filename"], root=file_info["root"], original_lines=orig, texts_to_translate=texts, key_map=km,
        is_custom_loc=file_info["is_custom_loc"], target_lang=target_lang, source_lang=source_lang, game_profile=game_profile,
        mod_context="", provider_name="", output_folder_name=output_folder_name, source_dir=SOURCE_DIR, dest_dir=DEST_DIR, client=None, mod_name=mod_name,
        loc_root=file_info.get("loc_root", "")
    )
    dest_dir = _build_dest_dir(temp_task, target_lang, output_folder_name, game_profile)
    os.makedirs(dest_dir, exist_ok=True)
    
    dest_file_path = file_builder.create_fallback_file(
        os.path.join(file_info["root"], file_info["filename"]), 
        dest_dir, file_info["filename"], source_lang, target_lang, game_profile
    )
    
    if dest_file_path:
        proofreading_tracker.add_file_info({
            'source_path': os.path.join(file_info["root"], file_info["filename"]),
            'dest_path': dest_file_path,
            'translated_lines': 0,
            'filename': file_info["filename"],
            'is_custom_loc': file_info["is_custom_loc"]
        })


def _run_post_processing(mod_name, game_profile, target_lang, source_lang, output_folder_name, proofreading_tracker, update_progress_callback=None):
    """运行后处理验证"""
    try:
        from scripts.core.post_processing_manager import PostProcessingManager
        from scripts.utils import tag_scanner
        
        dynamic_tags = None
        official_tags_path = game_profile.get("official_tags_codex")
        
        if official_tags_path:
            mod_loc_path_for_scan = os.path.join(SOURCE_DIR, mod_name, game_profile["source_localization_folder"])
            dynamic_tags = tag_scanner.analyze_mod_and_get_all_valid_tags(mod_loc_path=mod_loc_path_for_scan, official_tags_json_path=official_tags_path)
        
        output_folder_path = os.path.join(DEST_DIR, output_folder_name)
        post_processor = PostProcessingManager(game_profile, output_folder_path)
        validation_success = post_processor.run_validation(target_lang, source_lang, dynamic_valid_tags=dynamic_tags)
        
        # Get validation stats and update frontend
        stats = post_processor.get_validation_stats()
        total_issues = stats.get('total_errors', 0) + stats.get('total_warnings', 0)
        
        if update_progress_callback:
            # Update the format_issues count in the frontend
            # We use "Translating" stage or maybe "Verifying"? Let's keep it simple.
            update_progress_callback(log_message=f"Validation completed. Found {total_issues} issues.", format_issues_override=total_issues)

        if validation_success:
            post_processor.attach_results_to_proofreading_tracker(proofreading_tracker)
            
    except Exception as e:
        logging.error(f"Post-processing failed: {e}")


def _build_dest_dir(file_task: FileTask, target_lang: dict, output_folder_name: str, game_profile: dict) -> str:
    """构建目标目录路径"""
    # Collect all known language folder names for robust checking
    known_lang_folders = set()
    for lang_def in LANGUAGES.values():
        if "name_en" in lang_def:
            known_lang_folders.add(lang_def["name_en"].lower())
        if "key" in lang_def:
            known_lang_folders.add(lang_def["key"][2:].lower()) # e.g. "english" from "l_english"
        known_lang_folders.add("english") # Always include english
            
    if file_task.is_custom_loc:
        cust_loc_root = os.path.join(SOURCE_DIR, file_task.mod_name, "customizable_localization")
        rel = os.path.relpath(file_task.root, cust_loc_root)
        dest_dir = os.path.join(DEST_DIR, output_folder_name, "customizable_localization", target_lang["key"][2:], rel)
    else:
        # 使用 loc_root 来计算相对路径，确保多模块结构被保留
        if file_task.loc_root:
            # file_task.root 是文件所在的目录 (e.g. .../main_menu/localization/english/replace)
            # file_task.loc_root 是该模块的 localization 根目录 (e.g. .../main_menu/localization)
            
            # 1. 计算相对于 loc_root 的路径 (e.g. english/replace)
            rel_from_loc_root = os.path.relpath(file_task.root, file_task.loc_root)
            
            # 2. 处理语言文件夹替换
            parts = rel_from_loc_root.split(os.sep)
            
            # Check if the first folder is a known language folder
            if parts and parts[0].lower() in known_lang_folders:
                 # Replace with target language folder
                 parts[0] = target_lang["key"][2:]
            else:
                 # If no language folder found (e.g. at root of loc), insert target language
                 if parts[0] == ".": 
                     parts = [target_lang["key"][2:]]
                 else:
                     parts.insert(0, target_lang["key"][2:])
            
            new_rel_path = os.path.join(*parts)
            
            # 3. 计算模块路径 (相对于 mod root)
            mod_root = os.path.join(SOURCE_DIR, file_task.mod_name)
            module_rel_path = os.path.relpath(file_task.loc_root, mod_root)
            
            # 4. 组合最终路径
            dest_dir = os.path.join(DEST_DIR, output_folder_name, module_rel_path, new_rel_path)
            
        else:
            # Fallback for legacy behavior (single localization folder)
            source_loc_folder = game_profile["source_localization_folder"]
            source_loc_path = os.path.join(SOURCE_DIR, file_task.mod_name, source_loc_folder)
            
            # Handle case where file might be in a subfolder of source_loc_folder not discovered as loc_root
            # This logic is a bit fragile, loc_root should cover most cases now.
            if file_task.root.startswith(source_loc_path):
                 rel = os.path.relpath(file_task.root, source_loc_path)
            else:
                 # Should not happen if discovered correctly, but fallback
                 rel = os.path.basename(file_task.root)

            # 尝试替换语言文件夹
            parts = rel.split(os.sep)
            if parts and parts[0].lower() in known_lang_folders:
                 parts[0] = target_lang["key"][2:]
                 rel = os.path.join(*parts)
            else:
                 rel = os.path.join(target_lang["key"][2:], rel)

            dest_dir = os.path.join(DEST_DIR, output_folder_name, source_loc_folder, rel)
            
    return dest_dir


def process_metadata_for_language(mod_name, handler, source_lang, target_lang, output_folder_name, mod_context, game_profile):
    """为指定语言处理元数据"""
    try:
        asset_handler.process_metadata(mod_name, handler, source_lang, target_lang, output_folder_name, mod_context, game_profile)
    except Exception as e:
        logging.exception(i18n.t("metadata_processing_failed", error=e))


def discover_files(mod_name: str, game_profile: dict, source_lang: dict, override_path: Optional[str] = None) -> List[dict]:
    """
    Discover all localizable files in the mod directory.
    Supports recursive search for EU5-style multi-module structures.
    """
    source_loc_folder = game_profile["source_localization_folder"]
    if override_path:
        mod_root_path = override_path
    else:
        mod_root_path = os.path.join(SOURCE_DIR, mod_name)
    source_loc_path = os.path.join(mod_root_path, source_loc_folder)
    cust_loc_root = os.path.join(mod_root_path, "customizable_localization")

    # 仅收集文件路径，不读取内容
    all_file_paths = []
    # Use regex for flexible matching (allow space or underscore before l_lang)
    import re
    lang_key = source_lang['key'][2:] # e.g. "english"
    suffix_pattern = re.compile(r'[\s_]l_' + re.escape(lang_key) + r'\.yml$', re.IGNORECASE)

    # 策略：如果标准路径存在，仅使用标准路径（保持兼容性）
    # 如果标准路径不存在，则递归搜索所有名为 source_loc_folder 的目录 (EU5 模式)
    search_paths = []
    
    if os.path.isdir(source_loc_path):
        search_paths.append(source_loc_path)
    else:
        # 递归搜索所有匹配的文件夹
        logging.info(f"Standard localization folder not found at {source_loc_path}. Searching recursively for '{source_loc_folder}'...")
        for root, dirs, files in os.walk(mod_root_path):
            if os.path.basename(root) == source_loc_folder:
                search_paths.append(root)
    
    for loc_path in search_paths:
        logging.info(f"Discovered localization directory: {loc_path}")
        for root, _, files in os.walk(loc_path):
            for fn in files:
                if suffix_pattern.search(fn):
                    # loc_path 是当前模块的 localization 根目录
                    all_file_paths.append({
                        "path": os.path.join(root, fn), 
                        "filename": fn, 
                        "root": root, 
                        "is_custom_loc": False,
                        "loc_root": loc_path # 记录 loc_root
                    })

    if os.path.isdir(cust_loc_root):
        for root, _, files in os.walk(cust_loc_root):
            for fn in files:
                if fn.endswith(".txt"):
                    all_file_paths.append({
                        "path": os.path.join(root, fn), 
                        "filename": fn, 
                        "root": root, 
                        "is_custom_loc": True,
                        "loc_root": "" # Custom loc doesn't use standard localization structure
                    })
                    
    if not all_file_paths:
        # Diagnostic scan: Check if files exist for other languages
        found_others = []
        for loc_path in search_paths:
            for root, _, files in os.walk(loc_path):
                for fn in files:
                    if fn.endswith(".yml"):
                        found_others.append(fn)
        
        if found_others:
            logging.warning(f"No files found for source language '{source_lang['name']}' matching pattern l_{lang_key}.yml.")
            logging.warning(f"However, found {len(found_others)} other .yml files, e.g., {found_others[:3]}")
            logging.warning("Please check if you selected the correct Source Language.")

    return all_file_paths
    
    # 注意：流式处理模式下，我们无法在开始前创建完整的 Source Version Snapshot，
    # 除非我们再次遍历所有文件读取内容。
    # 为了性能，我们可以在流式处理过程中收集数据，或者接受 Snapshot 创建需要额外一次IO的成本。
    # 鉴于 Snapshot 很重要，我们先快速读取一遍用于归档（如果启用了归档）。
    # 或者，我们可以推迟归档到处理过程中？不，Source Version 应该是原始状态。
    # 现在的逻辑是：如果启用了归档，我们还是得读一遍。
    # 但为了避免内存爆炸，我们可以分批读并写入归档？ArchiveManager目前不支持流式写入。
    # 暂时保留：如果启用归档，可能会消耗较多内存。但通常归档是在本地数据库，压力稍小。
    # 为了真正解决内存问题，ArchiveManager 也应该优化，但那是另一个任务。
    # 这里我们先假设归档步骤仍然是一次性的，或者我们跳过它以专注于翻译流。
    # *决定*: 暂时跳过 Source Version 的自动创建，或者仅记录元数据。
    # 为了保持兼容性，如果文件非常多，这步确实是瓶颈。
    # 暂时保留原逻辑的简化版：只有在文件数可控时才归档？
    # 实际上，我们可以让 ArchiveManager 逐个文件添加？
    # 现有的 archive_manager.create_source_version 需要 all_files_data。
    # 我们先略过这步的优化，专注于翻译过程的流式化。

