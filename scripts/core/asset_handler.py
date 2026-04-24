# scripts/core/asset_handler.py
import os
import re
import json
import shutil
import logging
from pathlib import Path
from typing import Any

from scripts.utils import i18n
from scripts.app_settings import SOURCE_DIR, DEST_DIR
# REMOVED: from scripts.core.api_handler import translate_single_text
# NOTE: The functions 'read_text_bom' and 'write_text_bom' are used but not defined/imported in the original file.
# Assuming they are available from another utility module. If not, this will need to be fixed.
# from scripts.utils.file_io import read_text_bom, write_text_bom # Hypothetical import


# ──────────────────────────────────────────────────────────────────
# VICTORIA 3
# ──────────────────────────────────────────────────────────────────
def _process_victoria3_metadata(mod_name: str, handler: Any, source_lang: dict, target_lang: dict,
                                output_folder_name: str, mod_context: str, game_profile: dict,
                                source_mod_path: str = None, dest_base_dir: str = DEST_DIR):
    """【V3专用】处理 Victoria 3 的 .metadata/metadata.json 文件。"""
    source_root = source_mod_path or os.path.join(SOURCE_DIR, mod_name)
    source_meta_file = os.path.join(source_root, game_profile['metadata_file'])
    dest_meta_dir = os.path.join(dest_base_dir, output_folder_name, '.metadata')

    if not os.path.exists(source_meta_file):
        logging.warning(i18n.t("metadata_not_found"))
        return

    with open(source_meta_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    original_name = data.get('name', '')
    translated_name = handler.translate_single_text(
        original_name, "mod name", mod_name,
        source_lang, target_lang, mod_context, game_profile
    )

    is_batch_mode = "Multilanguage" in output_folder_name
    if is_batch_mode:
        suffix = " (Multilingual Patch)"
    elif target_lang['key'] == 'l_simp_chinese':
        suffix = " (中文汉化)"
    else:
        suffix = f" ({target_lang['name']} Translation)"
    data['name'] = f"{translated_name}{suffix}"

    original_desc = data.get('short_description', '')
    data['short_description'] = handler.translate_single_text(
        original_desc, "mod short description", mod_name,
        source_lang, target_lang, mod_context, game_profile
    )

    os.makedirs(dest_meta_dir, exist_ok=True)
    dest_meta_file = os.path.join(dest_meta_dir, 'metadata.json')
    with open(dest_meta_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    logging.info(i18n.t("metadata_success"))


# ──────────────────────────────────────────────────────────────────
# STELLARIS
# ──────────────────────────────────────────────────────────────────
def _process_stellaris_metadata(mod_name: str, handler: Any, source_lang: dict, target_lang: dict,
                                output_folder_name: str, mod_context: str, game_profile: dict,
                                source_mod_path: str = None, dest_base_dir: str = DEST_DIR):
    """【群星专用】生成两份 .mod 文件。"""
    source_root = source_mod_path or os.path.join(SOURCE_DIR, mod_name)
    source_mod_file = os.path.join(source_root, game_profile['metadata_file'])
    if not os.path.exists(source_mod_file):
        logging.warning(i18n.t("metadata_not_found"))
        return

    with open(source_mod_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # ── translate name ────────────────────────────────────────────
    original_name = ""
    for line in lines:
        if line.strip().startswith('name='):
            match = re.search(r'"(.*)"', line)
            if match:
                original_name = match.group(1)
            break

    translated_name = handler.translate_single_text(
        original_name, "mod name", mod_name,
        source_lang, target_lang, mod_context, game_profile
    )

    is_batch_mode = "Multilanguage" in output_folder_name
    if is_batch_mode:
        suffix = " (Multilingual Patch)"
    elif target_lang['key'] == 'l_simp_chinese':
        suffix = " (汉化)"
    else:
        suffix = f" ({target_lang['name']} Translation)"
    final_name = f"{translated_name}{suffix}"

    new_content_lines = []
    in_tags_block = False
    tags_block_written = False

    for line in lines:
        stripped_line = line.strip()
        if in_tags_block:
            if '}' in stripped_line:
                in_tags_block = False
            continue
        if stripped_line.startswith('name='):
            new_content_lines.append(f'name="{final_name}"\n')
        elif stripped_line.startswith('tags={'):
            new_content_lines.append('tags={\n\t"Translation"\n}\n')
            tags_block_written = True
            if '}' not in stripped_line:
                in_tags_block = True
        elif stripped_line.startswith('remote_file_id='):
            continue
        elif stripped_line.startswith('replace_path='):
            continue
        else:
            new_content_lines.append(line)

    if not tags_block_written:
        insertion_point = next(
            (i + 1 for i, l in enumerate(new_content_lines) if l.strip().startswith('version=')), 0
        )
        new_content_lines.insert(insertion_point, 'tags={\n\t"Translation"\n}\n')

    dest_mod_dir = os.path.join(dest_base_dir, output_folder_name)
    os.makedirs(dest_mod_dir, exist_ok=True)

    with open(os.path.join(dest_mod_dir, 'descriptor.mod'), 'w', encoding='utf-8') as f:
        f.writelines(new_content_lines)

    launcher_mod_content = new_content_lines + [f'\npath="mod/{output_folder_name}"']
    with open(os.path.join(dest_base_dir, f"{output_folder_name}.mod"), 'w', encoding='utf-8') as f:
        f.writelines(launcher_mod_content)

    logging.info(i18n.t("metadata_success"))


# ──────────────────────────────────────────────────────────────────
# EU4
# ──────────────────────────────────────────────────────────────────
def _process_eu4_metadata(mod_name: str, handler: Any, source_lang: dict, target_lang: dict,
                           output_folder_name: str, mod_context: str, game_profile: dict,
                           source_mod_path: str = None, dest_base_dir: str = DEST_DIR):
    """【EU4专用】处理 descriptor.mod。"""
    source_root = source_mod_path or os.path.join(SOURCE_DIR, mod_name)
    source_mod_file = os.path.join(source_root, game_profile['metadata_file'])
    if not os.path.exists(source_mod_file):
        logging.warning("Warning: descriptor.mod not found, skipping metadata.")
        return

    with open(source_mod_file, 'r', encoding='utf-8-sig') as f:
        lines = f.read().splitlines()

    original_name = ""
    for ln in lines:
        if ln.strip().startswith('name='):
            m = re.search(r'"(.*)"', ln)
            if m:
                original_name = m.group(1)
            break

    translated_name = handler.translate_single_text(
        original_name, "mod name", mod_name,
        source_lang, target_lang, mod_context, game_profile
    )

    is_batch_mode = "Multilanguage" in output_folder_name
    if is_batch_mode:
        suffix = " (Multilingual Patch)"
    elif target_lang['key'] == 'l_simp_chinese':
        suffix = " (汉化)"
    else:
        suffix = f" ({target_lang['name']} Translation)"
    final_name = f"{translated_name}{suffix}"

    new_lines = []
    tags_written = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith('name='):
            new_lines.append(f'name="{final_name}"')
        elif stripped.startswith('tags={'):
            tags_written = True
            new_lines.append('tags={')
            new_lines.append('\t"Translation"')
            new_lines.append('}')
            continue
        elif stripped.startswith('remote_file_id='):
            continue
        else:
            new_lines.append(ln)

    if not tags_written:
        idx = next(
            (i + 1 for i, l in enumerate(new_lines) if l.strip().startswith('version=')),
            len(new_lines)
        )
        new_lines.insert(idx, 'tags={\n\t"Translation"\n}')

    dest_mod_dir = os.path.join(dest_base_dir, output_folder_name)
    os.makedirs(dest_mod_dir, exist_ok=True)

    dest_file_path = os.path.join(dest_mod_dir, 'descriptor.mod')
    with open(dest_file_path, 'w', encoding='utf-8-sig') as f:
        f.write("\n".join(new_lines))

    launcher_lines = new_lines + [f'\npath="mod/{output_folder_name}"']
    launcher_file_path = os.path.join(dest_base_dir, f"{output_folder_name}.mod")
    with open(launcher_file_path, 'w', encoding='utf-8-sig') as f:
        f.write("\n".join(launcher_lines))

    logging.info(i18n.t("metadata_success"))


def process_metadata(mod_name: str, handler: Any, source_lang: dict, target_lang: dict,
                     output_folder_name: str, mod_context: str, game_profile: dict,
                     source_mod_path: str = None, dest_base_dir: str = DEST_DIR):
    """【总调度】元数据处理器，根据游戏档案调用对应的处理函数。"""
    logging.info(i18n.t("processing_metadata"))

    game_id = game_profile.get('id')
    
    if game_id in ['stellaris', 'hoi4', 'ck3']:
        _process_stellaris_metadata(mod_name, handler, source_lang, target_lang,
                                    output_folder_name, mod_context, game_profile, source_mod_path, dest_base_dir)
    elif game_id == 'victoria3':
        _process_victoria3_metadata(mod_name, handler, source_lang, target_lang,
                                      output_folder_name, mod_context, game_profile, source_mod_path, dest_base_dir)
    elif game_id == 'eu4':
        _process_eu4_metadata(mod_name, handler, source_lang, target_lang,
                              output_folder_name, mod_context, game_profile, source_mod_path, dest_base_dir)
    else:
        logging.warning(i18n.t("unsupported_metadata", game_name=game_profile['name']))


def copy_assets(mod_name: str, output_folder_name: str, game_profile: dict, source_mod_path: str = None, dest_base_dir: str = DEST_DIR):
    """根据游戏档案中的保护名单，复制所有必要的资产文件。"""
    logging.info(i18n.t("processing_assets"))
    source_dir = source_mod_path or os.path.join(SOURCE_DIR, mod_name)
    dest_dir = os.path.join(dest_base_dir, output_folder_name)

    assets_to_copy = game_profile.get('protected_items', set())
    metadata_filename = os.path.basename(game_profile.get('metadata_file', ''))

    for item in assets_to_copy:
        if item == metadata_filename or (
            game_profile['id'] == 'victoria3' and item == '.metadata'
        ):
            continue

        source_path = os.path.join(source_dir, item)
        if os.path.exists(source_path):
            dest_path = os.path.join(dest_dir, item)
            try:
                if os.path.isdir(source_path):
                    shutil.copytree(source_path, dest_path)
                else:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                logging.info(i18n.t("asset_copied", asset_name=item))
            except FileExistsError:
                 logging.warning(i18n.t("log_warn_asset_exists", item=item))
            except Exception as e:
                logging.exception(f"Error copying asset {item}: {e}")
        else:
            logging.warning(i18n.t("asset_not_found", asset_name=item))
