import os
import logging
import asyncio
import datetime
import uuid
from typing import List, Dict, Any, Tuple, Optional, Callable
from pathlib import Path

from scripts.core.archive_manager import archive_manager
from scripts.shared.services import project_manager
from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.core.file_builder import rebuild_and_write_file
from scripts.core.parallel_types import FileTask
from scripts.core.parallel_processor import ParallelProcessor
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
    use_resume: bool = True,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
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
                # Relaxed matching to catch files like "00 Bookmarks russian.yml"
                file_lower = file.lower()
                
                # If we have a filter language string (e.g. 'russian'), we check if the file matches the expected pattern
                # It should either have 'l_russian' or ' russian' at the end before extension
                expected_suffix1 = f"l_{filter_lang_string}.yml"
                expected_suffix2 = f"l_{filter_lang_string}.yaml"
                expected_suffix3 = f" {filter_lang_string}.yml"
                expected_suffix4 = f" {filter_lang_string}.yaml"
                
                if not (file_lower.endswith(expected_suffix1) or file_lower.endswith(expected_suffix2) or file_lower.endswith(expected_suffix3) or file_lower.endswith(expected_suffix4)):
                    # Allow fallback to checking if it contains another language's pattern
                    has_other_lang = False
                    for lang in known_languages:
                        if lang != filter_lang_string and (f"l_{lang}" in file_lower or f" {lang}." in file_lower):
                            has_other_lang = True
                            break
                    if has_other_lang:
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
        
        if progress_callback:
            progress_callback({
                "stage": "Scanning",
                "percent": 10,
                "message": f"Scanned {len(current_files_data)} files."
            })

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
        
        # [OPTIMIZATION] Pre-fetch all history entries for this mod/language to avoid N+1 queries
        logger.info(f"Pre-fetching archive for {project_name} ({target_lang_code})...")
        if progress_callback:
            progress_callback({
                "stage": "Preparing",
                "percent": 15,
                "message": f"Pre-fetching archive for {target_lang_code}..."
            })
        
        # We need to know which file each entry belongs to. 
        # get_entries for a mod returns a list. We need to tweak it or the archive_manager to support bulk fetch with filename.
        # However, for now, let's just fetch all and group them if the archive supports it.
        # Refactoring get_entries to be more efficient or using a new method.
        # Let's assume we can get a map of {filename: {key: entry}}
        
        history_map_by_file = {}
        # Fetch all entries for the project in this language
        all_entries = archive_manager.get_entries(project_name, language=target_lang_code)
        # Note: ArchiveManager.get_entries currently doesn't return filename in the list objects 
        # unless we modify it. Let's look at ArchiveManager.get_entries implementation.
        # Wait, if we can't easily group by file, we can at least group by key if keys are unique mod-wide.
        # Paradox keys are usually unique mod-wide.
        history_map_global = {e['key']: e for e in all_entries}
        
        # 2. Compare with Archive & Prepare Tasks for THIS language
        num_files = len(current_files_data)
        for i, fd in enumerate(current_files_data):
            filename = fd['filename']
            
            if progress_callback and i % 5 == 0:
                pct = 20 + int((i / num_files) * 30) # 20% to 50% for scanning
                progress_callback({
                    "stage": "Comparing",
                    "percent": pct,
                    "message": f"Comparing {filename} ({i+1}/{num_files})"
                })
            
            texts_to_translate = []
            key_delta_indices = []
            full_file_entries = []

            for key, source_text, line_num in fd['parsed_entries']:
                summary["total"] += 1
                
                # Normalize key for lookup
                lookup_key = key
                if lookup_key.endswith(":"):
                    lookup_key = lookup_key[:-1].strip()
                
                # Check history map
                hist = history_map_global.get(lookup_key)
                
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

            def internal_progress(current, total):
                if progress_callback:
                    # Map batch progress (20% to 90%)
                    pct = 20 + int((current / total) * 70)
                    progress_callback({
                        "stage": "Translating",
                        "percent": pct,
                        "batch_idx": current,
                        "total_batches": total,
                        "message": f"Translating {target_lang_code}: {current}/{total} batches"
                    })

            logger.info(f"Translating {len(file_tasks_for_ai)} files incrementally for {target_lang_code}...")
            translated_results, warnings = processor.process_files_parallel(file_tasks_for_ai, translate_batch, internal_progress)
            overall_warnings.extend(warnings)
        else:
            translated_results = {}
            logger.info(f"Everything is up to date for {target_lang_code}.")
            if progress_callback:
                progress_callback({
                    "stage": "Finishing",
                    "percent": 90,
                    "message": f"No new content for {target_lang_code}."
                })

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
        if progress_callback:
            progress_callback({
                "stage": "Completed",
                "percent": 100,
                "message": "Pre-scan completed.",
                "status": "completed", # Redundant but helps
                "summary": overall_summary
            })
        return {"status": "success", "summary": overall_summary}

    return {
        "status": "success", 
        "summary": overall_summary, 
        "warnings": overall_warnings, 
        "output_dir": str(base_output_dir),
        "history_desc": f"Built incremental updates for {len(target_lang_infos)} languages."
    }
