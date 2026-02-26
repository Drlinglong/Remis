import os
import logging
import asyncio
import datetime
import uuid
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from scripts.core.archive_manager import archive_manager
from scripts.shared.services import project_manager
from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.core.file_builder import rebuild_and_write_file
from scripts.core.parallel_processor import ParallelProcessor, FileTask
from scripts.core.api_handler import get_handler
from scripts.app_settings import SOURCE_DIR, DEST_DIR
from scripts.utils import i18n, read_text_bom

logger = logging.getLogger(__name__)

async def run_incremental_update(
    project_id: str, 
    target_lang_infos: List[Dict[str, Any]], 
    source_lang_info: Dict[str, Any],
    game_profile: Dict[str, Any],
    selected_provider: str = "gemini",
    model_name: Optional[str] = None,
    mod_context: str = "",
    dry_run: bool = False,
    custom_source_path: Optional[str] = None,
    use_resume: bool = True
) -> Dict[str, Any]:
    """
    Runs the incremental translation workflow for multiple target languages.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": f"Project {project_id} not found"}

    source_path = custom_source_path or project['source_path']
    project_name = project['name']
    
    # We want to ONLY scan files belonging to the source language to avoid processing 11 original languages
    source_lang_name_en = source_lang_info.get('name_en', 'English').lower()
    
    paradox_lang_map = {
        'simplified chinese': 'simp_chinese',
        'traditional chinese': 'trad_chinese',
        'brazilian portuguese': 'braz_por'
    }
    
    filter_lang_string = paradox_lang_map.get(source_lang_name_en, source_lang_name_en)
    
    target_codes_str = ", ".join([lang['code'] for lang in target_lang_infos])
    logger.info(f"Starting incremental update for: {project_name} -> [{target_codes_str}]")
    logger.info(f"Scanning source path: {source_path} (Filtering for '{filter_lang_string}')")

    # 1. Discover and Parse current source files (DONE ONCE for all targets)
    current_files_data = []
    for root, dirs, files in os.walk(source_path):
        path_parts = [p.lower() for p in Path(root).parts]
        if 'localization' in path_parts or 'localisation' in path_parts:
            current_folder = os.path.basename(root).lower()
            known_languages = ['english', 'french', 'german', 'spanish', 'russian', 'polish', 'braz_por', 'japanese', 'chinese', 'simp_chinese', 'korean', 'turkish']
            if current_folder in known_languages and current_folder != filter_lang_string:
                 dirs[:] = []
                 continue

        for file in files:
            if file.endswith(('.yml', '.yaml')):
                if f"l_{filter_lang_string}" not in file.lower() and any(f"l_{lang}" in file.lower() for lang in known_languages):
                    continue

                full_path = Path(os.path.join(root, file))
                try:
                    entries_with_lines = parse_loc_file_with_lines(full_path)
                    if entries_with_lines:
                        raw_content = read_text_bom(full_path)
                        original_lines = raw_content.splitlines(keepends=True)
                        
                        current_files_data.append({
                            'filename': os.path.basename(full_path),
                            'full_path': full_path,
                            'root': root,
                            'original_lines': original_lines,
                            'parsed_entries': entries_with_lines
                        })
                except Exception as e:
                    logger.error(f"Failed to parse {full_path}: {e}")

    if not current_files_data:
        logger.warning(f"No source files found in {source_path}")
        return {
            "status": "warning", 
            "message": f"No source files found. Please verify the source language setting.",
            "summary": {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
        }

    # Output directory base
    base_output_dir = Path(source_path).parent / "Remis_Incremental_Update"
    os.makedirs(base_output_dir, exist_ok=True)

    # Initialize overall summary
    overall_summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
    overall_warnings = []
    all_written_files = []

    # Process EACH target language independently
    for target_lang_info in target_lang_infos:
        target_lang_code = target_lang_info['code']
        logger.info(f"--- Processing Target Language: {target_lang_code} ---")
        
        summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
        file_tasks_for_ai = []
        processing_records = []
        
        # 2. Compare with Archive & Prepare Tasks for THIS language
        for fd in current_files_data:
            filename = fd['filename']
            history_entries = archive_manager.get_entries(project_name, filename, language=target_lang_code)
            history_map = {e['key']: e for e in history_entries}

            texts_to_translate = []
            key_delta_indices = []
            full_file_entries = []

            for key, source_text, line_num in fd['parsed_entries']:
                summary["total"] += 1
                hist = history_map.get(key)
                
                entry_info = {
                    'key': key, 
                    'source': source_text, 
                    'line_num': line_num - 1, 
                    'translation': None, 
                    'is_dirty': False
                }

                if not hist or hist['original'] != source_text:
                    global_trans = archive_manager.find_global_translation(key, source_text, target_lang_code)
                    if global_trans:
                        summary["unchanged"] += 1
                        summary["reused_global"] = summary.get("reused_global", 0) + 1
                        entry_info['translation'] = global_trans
                        entry_info['is_dirty'] = False
                    else:
                        if not hist: summary["new"] += 1
                        else: summary["changed"] += 1
                        
                        entry_info['is_dirty'] = True
                        texts_to_translate.append(source_text)
                        key_delta_indices.append(len(full_file_entries))
                else:
                    summary["unchanged"] += 1
                    entry_info['translation'] = hist['translation']
                
                full_file_entries.append(entry_info)
            
            record = {
                'fd': fd,
                'full_file_entries': full_file_entries,
                'key_delta_indices': key_delta_indices
            }
            processing_records.append(record)
            
            if texts_to_translate:
                # Output folder is lang-specific if there are multiple, or just the base if single
                lang_dest_dir = base_output_dir if len(target_lang_infos) == 1 else base_output_dir / target_lang_code
                
                task = FileTask(
                    filename=filename,
                    root=fd['root'],
                    original_lines=fd['original_lines'],
                    texts_to_translate=texts_to_translate,
                    key_map={'indices': key_delta_indices},
                    is_custom_loc=False,
                    target_lang=target_lang_info,
                    source_lang=source_lang_info,
                    game_profile=game_profile,
                    mod_context=mod_context,
                    provider_name=selected_provider,
                    output_folder_name=f"IncrementalUpdate_{target_lang_code}",
                    source_dir=source_path,
                    dest_dir=str(lang_dest_dir),
                    client=None,
                    mod_name=project_name
                )
                file_tasks_for_ai.append(task)

        # Aggregate summaries
        overall_summary["total"] += summary["total"]
        overall_summary["new"] += summary["new"]
        overall_summary["changed"] += summary["changed"]
        overall_summary["unchanged"] += summary["unchanged"]

        if dry_run:
            continue # Skip translation for this language

        lang_output_dir = base_output_dir if len(target_lang_infos) == 1 else base_output_dir / target_lang_code
        os.makedirs(lang_output_dir, exist_ok=True)

        if not use_resume:
            from scripts.core.checkpoint_manager import CheckpointManager
            checkpoint_mgr = CheckpointManager(str(lang_output_dir))
            checkpoint_mgr.clear_checkpoint()

        if file_tasks_for_ai:
            # 3. Parallel Translation for THIS language
            handler = get_handler(selected_provider, model_name=model_name)
            if not handler or not handler.client:
                return {"status": "error", "message": f"API Provider {selected_provider} not configured."}
            
            for task in file_tasks_for_ai:
                task.client = handler.client

            processor = ParallelProcessor()
            
            def translate_batch(batch):
                return handler.translate_batch(batch)

            logger.info(f"Translating {len(file_tasks_for_ai)} files incrementally for {target_lang_code}...")
            translated_results, warnings = processor.process_files_parallel(file_tasks_for_ai, translate_batch)
            overall_warnings.extend(warnings)
        else:
            translated_results = {}
            logger.info(f"Everything is up to date for {target_lang_code}.")

        # 4. Merge results and Write files for THIS language
        written_files = []
        for record in processing_records:
            fd = record['fd']
            filename = fd['filename']
            full_entries = record['full_file_entries']
            delta_indices = record['key_delta_indices']
            
            ai_results = translated_results.get(filename, [])
            for delta_idx, trans_text in zip(delta_indices, ai_results):
                full_entries[delta_idx]['translation'] = trans_text
                
            all_texts = [e['source'] for e in full_entries]
            all_translations = [e['translation'] or e['source'] for e in full_entries]
            
            rebuild_key_map = {
                i: {
                    "line_num": e['line_num'],
                    "key_part": e['key']
                }
                for i, e in enumerate(full_entries)
            }
            
            try:
                rel_path = os.path.relpath(fd['root'], source_path)
                dest_root = lang_output_dir / rel_path
                os.makedirs(dest_root, exist_ok=True)
                
                out_path = rebuild_and_write_file(
                    original_lines=fd['original_lines'],
                    texts_to_translate=all_texts,
                    translated_texts=all_translations,
                    key_map=rebuild_key_map,
                    dest_dir=str(dest_root),
                    filename=filename,
                    source_lang=source_lang_info,
                    target_lang=target_lang_info,
                    game_profile=game_profile
                )
                written_files.append(out_path)
                all_written_files.append(out_path)
            except Exception as e:
                logger.error(f"Failed to rebuild file {filename}: {e}")

        # 5. Archive the NEW state for THIS language
        archive_files_data = []
        archive_results = {}
        
        for record in processing_records:
            fd = record['fd']
            filename = fd['filename']
            archive_files_data.append({
                'filename': filename,
                'texts_to_translate': [e['source'] for e in record['full_file_entries']],
                'key_map': [{'key_part': e['key']} for e in record['full_file_entries']]
            })
            archive_results[filename] = [e['translation'] or e['source'] for e in record['full_file_entries']]

        mod_id = archive_manager.get_or_create_mod_entry(project_name, remote_file_id="")
        if mod_id:
            new_version_id = archive_manager.create_source_version(mod_id, archive_files_data)
            if new_version_id:
                archive_manager.archive_translated_results(new_version_id, archive_results, archive_files_data, target_lang_code)

        # 6. Log History for THIS language
        history_desc = f"Build incremental update ({target_lang_code}). {summary['new']} new, {summary['changed']} changed, {summary['unchanged']} reused lines."
        await project_manager.log_history_event(
            project_id=project_id,
            action_type="translate",
            description=history_desc,
            snapshot_id=new_version_id if mod_id and new_version_id else None,
            metadata={
                "summary": summary,
                "output_dir": str(lang_output_dir),
                "files_count": len(written_files),
                "target_lang": target_lang_code
            }
        )

    if dry_run:
        return {"status": "success", "summary": overall_summary}

    return {
        "status": "success", 
        "summary": overall_summary, 
        "warnings": overall_warnings, 
        "output_dir": str(base_output_dir),
        "history_desc": f"Built incremental updates for {len(target_lang_infos)} languages."
    }
