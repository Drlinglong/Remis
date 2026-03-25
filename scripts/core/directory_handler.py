# scripts/core/directory_handler.py
import os
import shutil
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.utils import i18n
from scripts.app_settings import SOURCE_DIR
# ↓↓↓ nowo dodane importy ↓↓↓
from scripts.utils.text_clean import strip_pl_diacritics
# ↑↑↑------------------------↑↑↑
import logging


def select_mod_directory():
    """扫描source_mod目录，让用户选择一个mod文件夹。"""
    # 检查源目录是否存在
    if not os.path.exists(SOURCE_DIR):
        logging.error(i18n.t("error_source_dir_not_exists", dir=SOURCE_DIR))
        logging.error(i18n.t("error_source_dir_instructions"))
        logging.error(i18n.t("error_source_dir_condition1"))
        logging.error(i18n.t("error_source_dir_condition2"))
        logging.error(i18n.t("error_source_dir_condition3"))
        return None
    
    logging.info(i18n.t("scan_source_folder", dir=SOURCE_DIR))
    try:
        mod_folders = [d for d in os.listdir(SOURCE_DIR) if os.path.isdir(os.path.join(SOURCE_DIR, d))]
        if not mod_folders:
            logging.error(i18n.t("error_no_mods_found", dir=SOURCE_DIR))
            logging.error(i18n.t("error_add_mods_to_source_folder"))
            return None

        logging.info(i18n.t("select_mod_prompt"))
        for i, folder_name in enumerate(mod_folders):
            logging.info(f"  [{i + 1}] {folder_name}")

        while True:
            try:
                choice = int(input(i18n.t("enter_choice_prompt"))) - 1
                if 0 <= choice < len(mod_folders):
                    selected_mod = mod_folders[choice]
                    logging.info(i18n.t("you_selected", mod_name=selected_mod))
                    return selected_mod
                else:
                    logging.warning(i18n.t("invalid_input_number"))
            except ValueError:
                logging.warning(i18n.t("invalid_input_not_number"))
    except FileNotFoundError:
        logging.error(i18n.t("error_source_folder_not_found", dir=SOURCE_DIR))
        return None
    except PermissionError:
        logging.error(i18n.t("error_permission_denied", dir=SOURCE_DIR))
        return None
    except Exception as e:
        logging.error(i18n.t("error_scan_directory_unknown", error=e))
        return None


def scan_source_directory(source_dir):
    """
    扫描源目录，返回所有mod文件夹的列表
    
    Args:
        source_dir: 源目录路径
        
    Returns:
        list: mod文件夹名称列表
    """
    if not os.path.exists(source_dir):
        logging.error(i18n.t("error_source_dir_not_exists", dir=source_dir))
        return []
    
    try:
        mod_folders = [d for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))]
        return mod_folders
    except Exception as e:
        logging.error(i18n.t("error_scan_directory", error=e))
        return []


def select_mod(mods):
    """
    从mod列表中选择一个mod
    
    Args:
        mods: mod文件夹名称列表
        
    Returns:
        str or None: 选中的mod名称，如果用户取消则返回None
    """
    if not mods:
        logging.error(i18n.t("error_no_mods_found", dir=SOURCE_DIR))
        return None
    
    logging.info(i18n.t("select_mod_prompt"))
    for i, folder_name in enumerate(mods):
        logging.info(f"  [{i + 1}] {folder_name}")

    while True:
        try:
            choice = int(input(i18n.t("enter_choice_prompt"))) - 1
            if 0 <= choice < len(mods):
                selected_mod = mods[choice]
                logging.info(i18n.t("you_selected", mod_name=selected_mod))
                return selected_mod
            else:
                logging.warning(i18n.t("invalid_input_number"))
        except ValueError:
            logging.warning(i18n.t("invalid_input_not_number"))
        except (EOFError, KeyboardInterrupt):
            logging.info(i18n.t("user_cancelled_selection"))
            return None


def cleanup_source_directory(mod_name, game_profile):
    """清理源mod文件夹，现在会根据游戏档案来决定保护哪些文件。"""
    logging.info(i18n.t("cleanup_start", mod_name=mod_name))

    mod_path = os.path.join(SOURCE_DIR, mod_name)
    protected_items = game_profile.get('protected_items', set())

    logging.info(i18n.t("cleanup_deleting"))
    try:
        for item in os.listdir(mod_path):
            if item not in protected_items:
                item_path = os.path.join(mod_path, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        logging.info(i18n.t("cleanup_deleted_folder", item=item))
                    else:
                        os.remove(item_path)
                        logging.info(i18n.t("cleanup_deleted_file", item=item))
                except Exception as e:
                    logging.error(i18n.t("cleanup_delete_error", path=item_path, error=e))
        logging.info(i18n.t("cleanup_success"))
        return True
    except Exception as e:
        logging.error(i18n.t("cleanup_error", error=e))
        return False


# ────────────────────────────────────────────────────────────────
# ↓↓↓        NOWA FUNKCJA – zapis plików tłumaczenia        ↓↓↓
# ────────────────────────────────────────────────────────────────
def write_localisation_file(dest_path: str, content: str, game_profile: dict):
    """
    Zapisuje przetłumaczony plik lokalizacji z uwzględnieniem
    specyfiki gry (ANSI vs UTF-8, usuwanie ogonków dla EU4).

    Parametry:
        dest_path    – pełna ścieżka docelowa
        content      – tekst po tłumaczeniu
        game_profile – słownik z config.GAME_PROFILES[...]
    """
    # 1) EU4 → zdejmujemy diakrytyki, inne gry bez zmian
    if game_profile.get("strip_pl_diacritics", False):
        content = strip_pl_diacritics(content)

    # 2) wybór kodowania (EU4: cp1252, reszta: utf-8)
    encoding = game_profile.get("encoding", "utf-8")

    # 3) upewniamy się, że folder docelowy istnieje
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # 4) zapis
    with open(dest_path, "w", encoding=encoding, newline="") as f:
        f.write(content)


def create_output_structure(mod_name: str, output_folder_name: str, game_profile: dict, base_dest_dir: str = None):
    """
    ????????
    
    Args:
        mod_name: mod??
        output_folder_name: ???????
        game_profile: ????
        
    Returns:
        bool: ??????
    """
    try:
        from scripts.app_settings import DEST_DIR

        dest_root = base_dest_dir or DEST_DIR
        main_output_dir = os.path.join(dest_root, output_folder_name)
        logging.info(f"DEBUG: Attempting to create directory: {main_output_dir}")
        logging.info(f"DEBUG: DEST_DIR is: {dest_root}")
        os.makedirs(main_output_dir, exist_ok=True)
        logging.info(f"DEBUG: Directory exists after creation? {os.path.exists(main_output_dir)}")

        source_loc_folder = game_profile.get("source_localization_folder", "localization")
        loc_dir = os.path.join(main_output_dir, source_loc_folder)
        os.makedirs(loc_dir, exist_ok=True)

        logging.info(i18n.t("output_structure_created", path=main_output_dir))
        return True

    except Exception as e:
        logging.error(i18n.t("output_structure_creation_failed", error=e))
        raise
