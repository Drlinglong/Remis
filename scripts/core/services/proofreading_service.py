import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any

from scripts.utils.quote_extractor import QuoteExtractor
from scripts.core.file_builder import patch_file_content
from scripts.utils.i18n_utils import iso_to_paradox
from scripts.schemas.common import LanguageCode

logger = logging.getLogger(__name__)

class ProofreadingService:
    def __init__(self, project_manager, archive_manager):
        self.project_manager = project_manager
        self.archive_manager = archive_manager

    def find_source_template(self, target_path: str, source_lang: str, current_lang: str, project_id: str = None) -> str:
        """
        Robustly finds the source template file path given the target file path.
        """
        # --- Strategy 1: Path Manipulation ---
        try:
            path_obj = Path(target_path)
            parts = list(path_obj.parts)
            
            lang_folder_index = -1
            for i, part in enumerate(parts):
                if part.lower() == current_lang.lower():
                    lang_folder_index = i
                    break
            
            if lang_folder_index != -1:
                parts[lang_folder_index] = source_lang 
                filename = parts[-1]
                current_suffix = f"_l_{current_lang}"
                source_suffix = f"_l_{source_lang}"
                
                if current_suffix.lower() in filename.lower():
                    new_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                    parts[-1] = new_filename
                    new_path = Path(*parts)
                    if new_path.exists():
                        return str(new_path)

            target_path_str = str(target_path)
            pattern_dir = re.compile(re.escape(os.sep + current_lang + os.sep), re.IGNORECASE)
            replacement_dir = (os.sep + source_lang + os.sep).replace('\\', '\\\\')
            new_path_str = pattern_dir.sub(replacement_dir, target_path_str)
            pattern_suffix = re.compile(re.escape(f"_l_{current_lang}"), re.IGNORECASE)
            new_path_str = pattern_suffix.sub(f"_l_{source_lang}", new_path_str)
            
            if os.path.exists(new_path_str):
                return new_path_str
        except Exception as e:
            logger.warning(f"ProofreadingService: Strategy 1 failed: {e}")

        # --- Strategy 2: Project-wide Search ---
        try:
            if project_id:
                filename = os.path.basename(target_path)
                current_suffix = f"_l_{current_lang}"
                source_suffix = f"_l_{source_lang}"
                
                if current_suffix.lower() in filename.lower():
                    expected_source_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                    files = self.project_manager.get_project_files(project_id)
                    for f in files:
                        if os.path.basename(f['file_path']).lower() == expected_source_filename.lower():
                            if os.path.exists(f['file_path']):
                                return f['file_path']
        except Exception as e:
            logger.warning(f"ProofreadingService: Strategy 2 failed: {e}")

        # --- Strategy 3: Direct Disk Search ---
        try:
            if project_id:
                filename = os.path.basename(target_path)
                current_suffix = f"_l_{current_lang}"
                source_suffix = f"_l_{source_lang}"
                
                if current_suffix.lower() in filename.lower():
                    expected_source_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                    project = self.project_manager.get_project(project_id)
                    if project and project.get('source_path') and os.path.exists(project['source_path']):
                        for root, dirs, files in os.walk(project['source_path']):
                            for f in files:
                                if f.lower() == expected_source_filename.lower():
                                    return os.path.join(root, f)
        except Exception as e:
            logger.warning(f"ProofreadingService: Strategy 3 failed: {e}")

        return ""

    def get_proofread_data(self, project_id: str, file_id: str) -> Dict[str, Any]:
        project = self.project_manager.get_project(project_id)
        if not project:
            return None
            
        files = self.project_manager.get_project_files(project_id)
        target_file = next((f for f in files if f['file_id'] == file_id), None)
        if not target_file:
            return None

        target_file_path = target_file['file_path']
        filename = os.path.basename(target_file_path)
        
        # 1. Detect Languages
        current_lang = "english"
        lang_match = re.search(r"_l_(\w+)\.yml$", filename, re.IGNORECASE)
        if lang_match:
            current_lang = lang_match.group(1).lower()
        else:
            try:
                with open(target_file_path, 'r', encoding='utf-8-sig') as f:
                    first_line = f.readline()
                    header_match = re.match(r"^\s*l_(\w+):", first_line, re.IGNORECASE)
                    if header_match:
                        current_lang = header_match.group(1).lower()
            except: pass

        current_lang_key = f"l_{current_lang}"
        iso_source = project.get('source_language', 'en')
        source_lang = iso_to_paradox(iso_source)
        source_lang_key = f"l_{source_lang}"
        
        # 2. Locate Template
        if current_lang.lower() == source_lang.lower():
            template_file_path = target_file_path
        else:
            template_file_path = self.find_source_template(target_file_path, source_lang, current_lang, project_id)

        if not template_file_path or not os.path.exists(template_file_path):
            template_file_path = target_file_path

        # 3. Parse and Patch
        try:
            original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(template_file_path)
            original_content = "".join(original_lines)
            
            # AI Draft
            lang_code = LanguageCode.from_str(current_lang).value
            db_entries = self.archive_manager.get_entries(project['name'], template_file_path, lang_code)
            if not db_entries:
                folder_mod_name = os.path.basename(project['source_path'])
                db_entries = self.archive_manager.get_entries(folder_mod_name, template_file_path, lang_code)

            db_translation_map = {e['key']: e['translation'] for e in db_entries if e['translation']}
            
            # Disk State
            disk_translation_map = {}
            if os.path.exists(target_file_path):
                _, target_texts, target_map = QuoteExtractor.extract_from_file(target_file_path)
                for i, text in enumerate(target_texts):
                    if i in target_map:
                        disk_translation_map[target_map[i]['key_part'].strip()] = text

            entries = []
            ai_translated_texts = []
            disk_translated_texts = []
            
            for i, text in enumerate(texts_to_translate):
                key = key_map[i]['key_part'].strip()
                
                # AI Logic
                ai_trans = db_translation_map.get(key)
                if ai_trans is None: ai_trans = db_translation_map.get(str(i))
                if ai_trans is None and ":" in key: ai_trans = db_translation_map.get(key.split(':')[0])
                if ai_trans is None: ai_trans = db_translation_map.get(key + ":")
                if ai_trans is None: ai_trans = text
                ai_translated_texts.append(ai_trans)
                
                # Disk Logic
                disk_trans = disk_translation_map.get(key)
                if disk_trans is None and ":" in key: disk_trans = disk_translation_map.get(key.split(':')[0])
                if disk_trans is None: disk_trans = ai_trans
                disk_translated_texts.append(disk_trans)
                
                entries.append({
                    "key": key,
                    "original": text,
                    "translation": disk_trans, 
                    "line_number": key_map[i]['line_num'] 
                })

            ai_lines = patch_file_content(original_lines, texts_to_translate, ai_translated_texts, key_map, source_lang_key, current_lang_key)
            final_lines = patch_file_content(original_lines, texts_to_translate, disk_translated_texts, key_map, source_lang_key, current_lang_key)

            return {
                "file_id": file_id,
                "file_path": target_file_path,
                "mod_name": project['name'],
                "entries": entries,
                "file_content": original_content,
                "ai_content": "".join(ai_lines),
                "final_content": "".join(final_lines)
            }
        except Exception as e:
            logger.error(f"ProofreadingService: Data preparation failed: {e}", exc_info=True)
            return None

    def save_proofread_data(self, project_id: str, file_id: str, entries_list: List[Dict]) -> bool:
        """
        Saves user-corrected translations back to the target file.
        """
        try:
            project = self.project_manager.get_project(project_id)
            files = self.project_manager.get_project_files(project_id)
            target_file = next((f for f in files if f['file_id'] == file_id), None)

            if not project or not target_file:
                return False

            target_file_path = target_file['file_path']
            filename = os.path.basename(target_file_path)

            # 1. Detect Languages
            current_lang = "english"
            lang_match = re.search(r"_l_(\w+)\.yml$", filename, re.IGNORECASE)
            if lang_match:
                current_lang = lang_match.group(1).lower()
            else:
                try:
                    with open(target_file_path, 'r', encoding='utf-8-sig') as f:
                        first_line = f.readline()
                        header_match = re.match(r"^\s*l_(\w+):", first_line, re.IGNORECASE)
                        if header_match:
                            current_lang = header_match.group(1).lower()
                except:
                    pass
            
            current_lang_key = f"l_{current_lang}"
            iso_source = project.get('source_language', 'en')
            disk_source_lang = iso_to_paradox(iso_source)
            source_lang_key = f"l_{disk_source_lang}"

            # 2. Locate Template
            if current_lang == disk_source_lang:
                template_file_path = target_file_path
            else:
                template_file_path = self.find_source_template(target_file_path, disk_source_lang, current_lang, project_id)
            
            if not template_file_path or not os.path.exists(template_file_path):
                template_file_path = target_file_path

            # 3. Read Template and Prepare Data
            original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(template_file_path)
            user_translation_map = {e['key']: e['translation'] for e in entries_list}
            
            translated_texts = []
            for i, text in enumerate(texts_to_translate):
                key = key_map[i]['key_part'].strip()
                translated_texts.append(user_translation_map.get(key, text))
                
            # 4. Patch and Write
            patched_lines = patch_file_content(original_lines, texts_to_translate, translated_texts, key_map, source_lang_key, current_lang_key)
            
            with open(target_file_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(patched_lines)

            # 5. Update Project State
            self.project_manager.update_file_status_by_id(file_id, "done")
            return True
            
        except Exception as e:
            logger.error(f"ProofreadingService: Save failed: {e}", exc_info=True)
            return False

