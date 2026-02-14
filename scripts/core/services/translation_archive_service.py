import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.archive_manager import archive_manager
from scripts.core.loc_parser import parse_loc_file
from scripts.schemas.common import LanguageCode

logger = logging.getLogger(__name__)

class TranslationArchiveService:
    """
    Service to handle scanning and archiving of translation files.
    Extracts logic previously in ProjectManager to ensure SRP.
    """
    def __init__(self, am=None):
        self.archive_manager = am or archive_manager

    def upload_project_translations(self, project_id: str, project_name: str, source_path: str) -> Dict[str, Any]:
        """
        Scans existing translation files in the project and uploads them to the archive.
        
        Args:
            project_id: The UUID of the project.
            project_name: The display name of the project.
            source_path: The absolute path to the project's source directory.
            
        Returns:
            Dict containing status and message.
        """
        # 1. Get Project Config
        try:
            json_manager = ProjectJsonManager(source_path)
            config = json_manager.get_config()
            translation_dirs = config.get('translation_dirs', [])
        except Exception as e:
            logger.error(f"Failed to load project config for {project_id}: {e}")
            return {"status": "error", "message": f"Failed to load project config: {e}"}
        
        if not translation_dirs:
            return {"status": "warning", "message": "No translation directories configured."}

        # 2. Parse Source Files
        source_files_data = []
        all_source_keys = {} # key -> filename
        
        logger.info(f"Scanning source files in {source_path}...")
        for root, _, files in os.walk(source_path):
            for file in files:
                if file.endswith(('.yml', '.yaml')):
                    full_path = Path(os.path.join(root, file))
                    try:
                        entries = parse_loc_file(full_path)
                        if entries:
                            filename = os.path.basename(full_path)
                            source_files_data.append({
                                'filename': filename,
                                'key_map': [e[0] for e in entries],
                                'texts_to_translate': [e[1] for e in entries]
                            })
                            for e in entries:
                                all_source_keys[e[0]] = filename
                    except Exception as e:
                        logger.error(f"Failed to parse source file {full_path}: {e}")

        if not source_files_data:
            return {"status": "warning", "message": "No source files found to match against."}

        # 3. Initialize Archive Version
        mod_id = archive_manager.get_or_create_mod_entry(project_name, project_id)
        if not mod_id:
            return {"status": "error", "message": "Failed to initialize mod archive entry."}
        
        version_id = archive_manager.create_source_version(mod_id, source_files_data)
        if not version_id:
            return {"status": "error", "message": "Failed to create source version snapshot."}

        # 4. Scan and Match Translation Files
        file_results = {} 
        match_count = 0

        for trans_dir in translation_dirs:
            if not os.path.exists(trans_dir): continue
            for root, _, files in os.walk(trans_dir):
                for file in files:
                    if file.endswith(('.yml', '.yaml', '.txt')):
                        full_path = Path(os.path.join(root, file))
                        
                        # Determine Language
                        lang_code_iso = "zh-CN"
                        lang_match = re.search(r"_l_(\w+)\.(yml|yaml)$", file, re.IGNORECASE)
                        if lang_match:
                            try:
                                lang_code_iso = LanguageCode.from_str(lang_match.group(1)).value
                            except Exception: 
                                pass
                        
                        if lang_code_iso not in file_results:
                            file_results[lang_code_iso] = {}

                        try:
                            entries = parse_loc_file(full_path)
                            if not entries: continue
                            
                            for key, value in entries:
                                source_filename = all_source_keys.get(key)
                                # Fallback for keys that might include : lines (Paradox oddities)
                                if not source_filename and ":" in key:
                                    source_filename = all_source_keys.get(key.split(':')[0])
                                
                                if source_filename:
                                    source_file_data = next((fd for fd in source_files_data if fd['filename'] == source_filename), None)
                                    if not source_file_data: continue

                                    if source_filename not in file_results[lang_code_iso]:
                                        file_results[lang_code_iso][source_filename] = list(source_file_data['texts_to_translate'])
                                    
                                    try:
                                        # Find index of key to place translation correctly
                                        try:
                                            idx = source_file_data['key_map'].index(key)
                                        except ValueError:
                                            if ":" in key:
                                                sanitized_key_map = [k.split(':')[0] for k in source_file_data['key_map']]
                                                idx = sanitized_key_map.index(key.split(':')[0])
                                            else:
                                                raise ValueError("Key not found")

                                        file_results[lang_code_iso][source_filename][idx] = value
                                        match_count += 1
                                    except ValueError:
                                        pass
                        except Exception as e:
                            logger.error(f"Failed to parse translation file {full_path}: {e}")

        # 5. Archive Results
        if match_count > 0:
            for lang_iso, results in file_results.items():
                if results:
                    archive_manager.archive_translated_results(version_id, results, source_files_data, lang_iso)
            
            # Note: Logging to History is done by the caller (ProjectManager) or we inject a repo?
            # Keeping it pure: Return the count, let ProjectManager log the history event.
            
            return {
                "status": "success", 
                "message": f"Successfully uploaded {match_count} translations across {len(file_results)} files.",
                "match_count": match_count
            }
        else:
            return {"status": "info", "message": "No matching keys found in translation files."}
