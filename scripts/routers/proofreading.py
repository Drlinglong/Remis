import os
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from scripts.shared.services import project_manager, archive_manager
from scripts.schemas.proofreading import SaveProofreadingRequest
from scripts.utils.quote_extractor import QuoteExtractor
from scripts.core.file_builder import patch_file_content
from scripts.utils.i18n_utils import iso_to_paradox

logger = logging.getLogger(__name__)

router = APIRouter()

def find_source_template(target_path: str, source_lang: str, current_lang: str, project_id: str = None) -> str:
    """
    Robustly finds the source template file path given the target file path.
    1. Try path manipulation (folder/suffix swap).
    2. Fallback: Search entire project for the matching source filename.
    """
    # --- Strategy 1: Path Manipulation ---
    try:
        path_obj = Path(target_path)
        parts = list(path_obj.parts)
        
        # 1. Identify the language folder index (case-insensitive)
        lang_folder_index = -1
        for i, part in enumerate(parts):
            if part.lower() == current_lang.lower():
                lang_folder_index = i
                break
        
        if lang_folder_index != -1:
            # Replace directory name
            parts[lang_folder_index] = source_lang 
            
            # Replace filename suffix
            filename = parts[-1]
            current_suffix = f"_l_{current_lang}"
            source_suffix = f"_l_{source_lang}"
            
            if current_suffix.lower() in filename.lower():
                new_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                parts[-1] = new_filename
                
                new_path = Path(*parts)
                if new_path.exists():
                    return str(new_path)

        # Fallback for Strategy 1: Simple String Replacement
        target_path_str = str(target_path)
        pattern_dir = re.compile(re.escape(os.sep + current_lang + os.sep), re.IGNORECASE)
        # Fix: Escape backslashes in replacement string for re.sub
        replacement_dir = (os.sep + source_lang + os.sep).replace('\\', '\\\\')
        new_path_str = pattern_dir.sub(replacement_dir, target_path_str)
        
        pattern_suffix = re.compile(re.escape(f"_l_{current_lang}"), re.IGNORECASE)
        new_path_str = pattern_suffix.sub(f"_l_{source_lang}", new_path_str)
        
        if os.path.exists(new_path_str):
            return new_path_str
            
    except Exception as e:
        logger.warning(f"Strategy 1 failed: {e}")
        # Continue to Strategy 2

    # --- Strategy 2: Project-wide Search (The "Nuclear Option") ---
    try:
        if project_id:
            # Calculate expected source filename
            filename = os.path.basename(target_path)
            current_suffix = f"_l_{current_lang}"
            source_suffix = f"_l_{source_lang}"
            
            if current_suffix.lower() in filename.lower():
                expected_source_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                
                # Search all project files
                files = project_manager.get_project_files(project_id)
                for f in files:
                    f_path = f['file_path']
                    if os.path.basename(f_path).lower() == expected_source_filename.lower():
                        if os.path.exists(f_path):
                            logger.info(f"Fallback found source file: {f_path}")
                            return f_path
                        else:
                            logger.warning(f"Fallback match found in DB but missing on disk: {f_path}")
    except Exception as e:
        logger.warning(f"Strategy 2 failed: {e}")

    # --- Strategy 3: Direct Disk Search in Source Path (The "Bunker Buster") ---
    # Scans the actual source directory recursively. Robust against DB sync issues.
    try:
        if project_id:
             # Calculate expected source filename (re-use from Strategy 2 logic)
            filename = os.path.basename(target_path)
            current_suffix = f"_l_{current_lang}"
            source_suffix = f"_l_{source_lang}"
            
            if current_suffix.lower() in filename.lower():
                expected_source_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                
                project = project_manager.get_project(project_id)
                if project and project.get('source_path') and os.path.exists(project['source_path']):
                    source_dir = project['source_path']
                    logger.info(f"Strategy 3: Searching for '{expected_source_filename}' in '{source_dir}'")
                    
                    found_file = False
                    for root, dirs, files in os.walk(source_dir):
                        for f in files:
                            if f.lower() == expected_source_filename.lower():
                                full_path = os.path.join(root, f)
                                logger.info(f"Strategy 3 found source file: {full_path}")
                                return full_path
    
    except Exception as e:
        logger.warning(f"Strategy 3 failed: {e}")

    return ""

@router.get("/api/proofread/{project_id}/{file_id}")
def get_proofread_data(project_id: str, file_id: str):
    """
    获取校对数据 - Patching Mode
    """
    # 1. 获取项目和目标文件信息
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    files = project_manager.get_project_files(project_id)
    target_file = next((f for f in files if f['file_id'] == file_id), None)
    if not target_file:
        raise HTTPException(status_code=404, detail="File not found in project")

    target_file_path = target_file['file_path']
    filename = os.path.basename(target_file_path)
    
    # 2. 确定当前文件的语言 (Target Language for this file)
    current_lang = "english" # Fallback
    lang_match = re.search(r"_l_(\w+)\.yml$", filename, re.IGNORECASE)
    if lang_match:
        current_lang = lang_match.group(1).lower() # Normalize to lowercase
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
    
    # 3. 确定源语言 (Source Language)
    iso_source = project.get('source_language', 'simp_chinese')
    source_lang = iso_to_paradox(iso_source)
    logger.info(f"Proofreading: Project '{project['name']}' (ID: {project_id}) Source Lang: '{source_lang}' (ISO: {iso_source})")
    
    # Validation: If source_lang is same as current_lang, checking if this is really the source file?
    # User Case: "remis_demo_l_japanese.yml" (Current=Japanese). Source should be Chinese.
    # If project['source_language'] is 'english' (wrongly), then source_lang='english'.
    # We will try to find a file ending in _l_english.yml.
    
    source_lang_key = f"l_{source_lang}"
    
    # 4. 定位模板文件 (Source File)
    template_file_path = ""
    
    logger.debug(f"Proofreading: Target '{target_file_path}' (Lang: {current_lang}). Seaching for Source ({source_lang})...")

    if current_lang.lower() == source_lang.lower():
        # If we are editing the source file itself
        template_file_path = target_file_path
        logger.info("Proofreading: Editing source file directly.")
    else:
        # Pass project_id for fallback search
        template_file_path = find_source_template(target_file_path, source_lang, current_lang, project_id)
        logger.info(f"Proofreading: Found template path: '{template_file_path}'")

    if not template_file_path or not os.path.exists(template_file_path):
        logger.warning(f"Source file not found for {target_file_path}. Using target as template (formatting may be lost).")
        template_file_path = target_file_path

    # 5. 解析源文件 (Master Template)
    try:
        original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(template_file_path)
    except Exception as e:
        logger.error(f"Failed to parse template file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to parse template file: {str(e)}")

    original_content = "".join(original_lines)

    # 6. 准备中间栏数据 (AI Draft) - 来自数据库
    # 数据库查询使用 Template Path (Source Path)
    # [FIX] Use Project Display Name as mod_name (matching ProjectManager.upload logic)
    mod_name = project['name']
    
    # Fix 2: Convert language key (e.g. "english") to code (e.g. "en") using strict schema
    from scripts.schemas.common import LanguageCode
    try:
        lang_code = LanguageCode.from_str(current_lang).value
    except ValueError:
        # Fallback if detection fails, though from_str is robust
        lang_code = "en"
            
    logger.debug(f"Fetching DB entries for mod='{mod_name}', file='{template_file_path}', lang='{lang_code}'")
    db_entries = archive_manager.get_entries(mod_name, template_file_path, lang_code)
    
    # [FALLBACK] If no entries found with display name, try with folder name (for older projects)
    if not db_entries:
        folder_mod_name = os.path.basename(project['source_path'])
        if folder_mod_name != mod_name:
            logger.debug(f"No entries for display name '{mod_name}'. Trying folder name '{folder_mod_name}'...")
            db_entries = archive_manager.get_entries(folder_mod_name, template_file_path, lang_code)

    logger.debug(f"Found {len(db_entries)} entries in DB.")
    db_translation_map = {e['key']: e['translation'] for e in db_entries if e['translation']}
    
    # 7. 准备右侧栏数据 (Final Edit) - 来自磁盘上的目标文件
    disk_translation_map = {}
    if os.path.exists(target_file_path):
        try:
            _, target_texts, target_map = QuoteExtractor.extract_from_file(target_file_path)
            for i, text in enumerate(target_texts):
                if i in target_map:
                    k = target_map[i]['key_part'].strip()
                    disk_translation_map[k] = text
        except Exception as e:
            logger.error(f"Failed to parse target file {target_file_path}: {e}", exc_info=True)

    # 8. 构建返回数据
    entries = []
    ai_translated_texts = []
    disk_translated_texts = []
    
    for i, text in enumerate(texts_to_translate):
        key_info = key_map[i]
        key = key_info['key_part'].strip()
        
        # AI 翻译
        # [FIX] Support:
        # 1. Actual keys (key:version format used in new uploads/trans)
        # 2. Stringified indices (str(i) format used in legacy initial_translate)
        # 3. Pure keys (key format used in legacy uploads)
        ai_trans = db_translation_map.get(key)
        if ai_trans is None:
            ai_trans = db_translation_map.get(str(i))
        if ai_trans is None and ":" in key:
            pure_curr_key = key.split(':')[0]
            ai_trans = db_translation_map.get(pure_curr_key)
        
        # [NEW FALLBACK] Legacy trailing colon support
        if ai_trans is None:
            ai_trans = db_translation_map.get(key + ":")
        
        if ai_trans is None:
            ai_trans = text # Final fallback

        ai_translated_texts.append(ai_trans)
        
        # 磁盘现有翻译
        disk_trans = disk_translation_map.get(key)
        if disk_trans is None and ":" in key:
            disk_trans = disk_translation_map.get(key.split(':')[0])
        if disk_trans is None:
            disk_trans = ai_trans
            
        disk_translated_texts.append(disk_trans)
        
        entries.append({
            "key": key,
            "original": text,
            "translation": disk_trans, 
            "line_number": key_info['line_num'] 
        })

    # 9. 生成 Patch 后的内容
    # AI Content (Middle Pane)
    try:
        ai_lines = patch_file_content(
            original_lines,
            texts_to_translate,
            ai_translated_texts,
            key_map,
            source_lang_key,
            current_lang_key 
        )
        ai_content = "".join(ai_lines)
    except Exception as e:
        logger.error(f"AI Patching failed: {e}", exc_info=True)
        ai_content = original_content

    # Final Content (Right Pane - Initial View)
    try:
        final_lines = patch_file_content(
            original_lines,
            texts_to_translate,
            disk_translated_texts,
            key_map,
            source_lang_key,
            current_lang_key
        )
        file_content = "".join(final_lines)
    except Exception as e:
        logger.error(f"Final Patching failed: {e}", exc_info=True)
        file_content = original_content

    return {
        "file_id": file_id,
        "file_path": target_file_path,
        "mod_name": project['name'],
        "entries": entries,
        "file_content": original_content, # Left: Source Template
        "ai_content": ai_content,         # Middle: Source + AI
        "final_content": file_content     # Right: Source + Disk
    }


@router.post("/api/proofread/save")
def save_proofreading_db(request: SaveProofreadingRequest):
    try:
        project = project_manager.get_project(request.project_id)
        files = project_manager.get_project_files(request.project_id)
        target_file = next((f for f in files if f['file_id'] == request.file_id), None)

        if not project or not target_file:
            raise HTTPException(status_code=404, detail="Project or File not found")

        target_file_path = target_file['file_path']
        filename = os.path.basename(target_file_path)

        # 1. Determine Current Language (Target Language)
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

        # 2. Determine Source Language (Adapter Layer)
        # DB has ISO ('zh-CN'), Disk needs Paradox ('simp_chinese')
        iso_source = project.get('source_language', 'en')
        disk_source_lang = iso_to_paradox(iso_source)
        
        source_lang_key = f"l_{disk_source_lang}"

        # 3. Locate Template
        # Use disk_source_lang here
        if current_lang == disk_source_lang:
            template_file_path = target_file_path
        else:
            template_file_path = find_source_template(target_file_path, disk_source_lang, current_lang, request.project_id)
        
        if not template_file_path or not os.path.exists(template_file_path):
            template_file_path = target_file_path

        # 4. 读取模板文件
        original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(template_file_path)
        
        # 5. 准备翻译数据
        user_translation_map = {e['key']: e['translation'] for e in request.entries}
        
        translated_texts = []
        for i, text in enumerate(texts_to_translate):
            key_info = key_map[i]
            key = key_info['key_part'].strip()
            trans = user_translation_map.get(key, text)
            translated_texts.append(trans)
            
        # 6. Patch 生成最终文件内容
        patched_lines = patch_file_content(
            original_lines,
            texts_to_translate,
            translated_texts,
            key_map,
            source_lang_key,
            current_lang_key
        )
        
        # 7. 写入磁盘 (直接覆盖 target_file_path)
        with open(target_file_path, 'w', encoding='utf-8-sig') as f:
            f.writelines(patched_lines)

        # 8. 更新数据库和状态
        # We DO NOT update the translation DB here. 
        # The DB should store the "AI Draft" (Original AI Translation).
        # User edits are stored in the file on disk.
        # archive_manager.update_translations(project['name'], template_file_path, request.entries)
        project_manager.update_file_status_by_id(request.file_id, "done")
        
        return {"status": "success", "output_path": target_file_path}
        
    except Exception as e:
        logger.error(f"Save failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
