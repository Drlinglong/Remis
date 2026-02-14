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
    target_lang_info: Dict[str, Any], 
    source_lang_info: Dict[str, Any],
    game_profile: Dict[str, Any],
    selected_provider: str = "gemini",
    model_name: Optional[str] = None,
    mod_context: str = "",
    dry_run: bool = False,
    custom_source_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs the incremental translation workflow.
    """
    project = await project_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": f"Project {project_id} not found"}

    source_path = custom_source_path or project['source_path']
    project_name = project['name']
    target_lang_code = target_lang_info['code']
    
    # We want to ONLY scan files belonging to the source language to avoid processing 11 original languages
    # Paradox mods usually have localization/english, localization/french, etc.
    source_lang_name_en = source_lang_info.get('name_en', 'English').lower()
    
    logger.info(f"Starting incremental update for: {project_name} -> {target_lang_code}")
    logger.info(f"Scanning source path: {source_path} (Filtering for {source_lang_name_en})")

    # 1. Discover and Parse current source files
    current_files_data = []
    for root, dirs, files in os.walk(source_path):
        # OPTIMIZATION: Filter folders to only search in the source language directory
        # e.g., only go into 'english' folder if source is English.
        # This prevents the "388 batches" issue where it scans all 11 languages.
        
        # Simple heuristic: if 'localization' or 'localisation' is in path, 
        # only proceed if the folder name contains the source language name.
        path_parts = [p.lower() for p in Path(root).parts]
        if 'localization' in path_parts or 'localisation' in path_parts:
            # Check if any parent part matches a language folder name we DON'T want
            # This is tricky because we might be at the root of localization/
            # If we are in 'localization/french' and source is 'english', we skip.
            current_folder = os.path.basename(root).lower()
            
            # If the current folder is a known language folder but NOT ours, prune it
            known_languages = ['english', 'french', 'german', 'spanish', 'russian', 'polish', 'braz_por', 'japanese', 'chinese', 'simp_chinese', 'korean', 'turkish']
            if current_folder in known_languages and current_folder != source_lang_name_en:
                 logger.debug(f"Skipping non-source language folder: {root}")
                 dirs[:] = [] # Don't go deeper
                 continue

        for file in files:
            if file.endswith(('.yml', '.yaml')):
                # Also check filename for language suffix if not in a specific folder
                # e.g. events_l_french.yml
                if f"l_{source_lang_name_en}" not in file.lower() and any(f"l_{lang}" in file.lower() for lang in known_languages):
                    continue

                full_path = Path(os.path.join(root, file))
                try:
                    # We need line numbers and raw content to use the patcher
                    entries_with_lines = parse_loc_file_with_lines(full_path)
                    if entries_with_lines:
                        # Read raw lines for the patcher
                        raw_content = read_text_bom(full_path)
                        original_lines = raw_content.splitlines(keepends=True)
                        
                        current_files_data.append({
                            'filename': os.path.basename(full_path),
                            'full_path': full_path,
                            'root': root,
                            'original_lines': original_lines,
                            'parsed_entries': entries_with_lines # List of (key, source_text, line_num)
                        })
                except Exception as e:
                    logger.error(f"Failed to parse {full_path}: {e}")

    if not current_files_data:
        return {"status": "warning", "message": "No source files found."}

    # 2. Compare with Archive & Prepare Tasks
    summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
    
    file_tasks_for_ai = []
    
    # Store complete metadata for merging back
    # Each file will have a list of all its entries, dirty ones will be updated from AI results
    processing_records = []

    for fd in current_files_data:
        filename = fd['filename']
        # Fetch historical entries for this file
        history_entries = archive_manager.get_entries(project_name, filename, language=target_lang_code)
        history_map = {e['key']: e for e in history_entries} # key -> {original, translation}

        texts_to_translate = []
        key_delta_indices = [] # Indices within the FULL file's entry list that are dirty
        
        full_file_entries = [] # List of {'key': k, 'source': s, 'line_num': n, 'translation': t, 'is_dirty': bool}

        for key, source_text, line_num in fd['parsed_entries']:
            summary["total"] += 1
            hist = history_map.get(key)
            
            # Note: line_num is 1-based from parser, but patcher wants 0-based in some places and we handle it here
            entry_info = {
                'key': key, 
                'source': source_text, 
                'line_num': line_num - 1, 
                'translation': None, 
                'is_dirty': False
            }

            if not hist or hist['original'] != source_text:
                # NEW or CHANGED -> Try Global Archive Fallback first
                summary["total_to_check"] = summary.get("total_to_check", 0) + 1
                global_trans = archive_manager.find_global_translation(key, source_text, target_lang_code)
                
                if global_trans:
                    summary["unchanged"] += 1 # Reused from global
                    summary["reused_global"] = summary.get("reused_global", 0) + 1
                    entry_info['translation'] = global_trans
                    entry_info['is_dirty'] = False
                    logger.debug(f"Smart Reuse (Global) for {key}: {filename}")
                else:
                    if not hist: summary["new"] += 1
                    else: summary["changed"] += 1
                    
                    entry_info['is_dirty'] = True
                    texts_to_translate.append(source_text)
                    key_delta_indices.append(len(full_file_entries))
            else:
                # UNCHANGED (Project Local)
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
            # Create a FileTask for the ParallelProcessor
            task = FileTask(
                filename=filename,
                root=fd['root'],
                original_lines=fd['original_lines'],
                texts_to_translate=texts_to_translate,
                key_map={'indices': key_delta_indices}, # Not used by processor, but we keep it here
                is_custom_loc=False,
                target_lang=target_lang_info,
                source_lang=source_lang_info,
                game_profile=game_profile,
                mod_context=mod_context,
                provider_name=selected_provider,
                output_folder_name="IncrementalUpdate",
                source_dir=source_path,
                dest_dir=str(Path(source_path).parent / "Incremental"),
                client=None, # Will be set below
                mod_name=project_name
            )
            file_tasks_for_ai.append(task)

    if dry_run:
        return {"status": "success", "summary": summary}

    if not file_tasks_for_ai:
        # Check if we should still produce translation files (e.g. if we have only reused items)
        # For a full rebuild, we might need all files
        # But for "Update", maybe just informing the user is enough if nothing changed.
        return {"status": "info", "message": "Everything is up to date.", "summary": summary}

    # 3. Parallel Translation
    handler = get_handler(selected_provider, model_name=model_name)
    if not handler or not handler.client:
        return {"status": "error", "message": f"API Provider {selected_provider} not configured."}
    
    # Inject client into tasks
    for task in file_tasks_for_ai:
        task.client = handler.client

    processor = ParallelProcessor()
    
    def translate_batch(batch):
        return handler.translate_batch(batch)

    logger.info(f"Translating {len(file_tasks_for_ai)} files incrementally ({summary['new'] + summary['changed']} items)...")
    translated_results, warnings = processor.process_files_parallel(file_tasks_for_ai, translate_batch)

    # 4. Merge results and Write files
    output_dir = Path(source_path).parent / "Remis_Incremental_Update"
    os.makedirs(output_dir, exist_ok=True)
    
    written_files = []
    
    for record in processing_records:
        fd = record['fd']
        filename = fd['filename']
        full_entries = record['full_file_entries']
        delta_indices = record['key_delta_indices']
        
        ai_results = translated_results.get(filename, [])
        
        # Apply AI results back to merged entries
        for delta_idx, trans_text in zip(delta_indices, ai_results):
            full_entries[delta_idx]['translation'] = trans_text
            
        # Rebuild and write using standard patcher
        # Prepare data for rebuild_and_write_file
        # We pass ALL entries to ensure a complete file is generated
        all_texts = [e['source'] for e in full_entries]
        all_translations = [e['translation'] or e['source'] for e in full_entries] # Fallback to source if missing
        
        # patch_file_content expects key_map to be Dict[int, Dict] where int is index in texts_to_translate
        rebuild_key_map = {
            i: {
                "line_num": e['line_num'],
                # Patcher needs key_part to find position. 
                # Our key in Paradox usually includes :version.
                # If the key in the file is 'key:0', we need to pass 'key:0'.
                "key_part": e['key']
            }
            for i, e in enumerate(full_entries)
        }
        
        try:
            # We save in a structured way mimicking source path
            rel_path = os.path.relpath(fd['root'], source_path)
            dest_root = output_dir / rel_path
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
        except Exception as e:
            logger.error(f"Failed to rebuild file {filename}: {e}")

    # 5. Archive the NEW state
    # This creates a NEW source version and stores the NEW translations.
    # Future incremental updates will compare against this version.
    
    # We need to prepare data for ArchiveManager.create_source_version
    # Format: List[Dict] with 'filename' and 'texts_to_translate' (actually source texts) and 'key_map'
    archive_files_data = []
    archive_results = {} # filename -> list of translations
    
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

    # 6. Log History
    history_desc = f"Build incremental update. {summary['new']} new, {summary['changed']} changed, {summary['unchanged']} reused lines."
    await project_manager.log_history_event(
        project_id=project_id,
        action_type="translate",
        description=history_desc,
        snapshot_id=new_version_id if mod_id and new_version_id else None,
        metadata={
            "summary": summary,
            "output_dir": str(output_dir),
            "files_count": len(written_files)
        }
    )

    return {
        "status": "success", 
        "summary": summary, 
        "warnings": warnings, 
        "output_dir": str(output_dir),
        "history_desc": history_desc
    }
