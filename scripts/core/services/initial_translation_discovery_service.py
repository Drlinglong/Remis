import logging
import os
import re
from typing import Optional

from scripts.app_settings import SOURCE_DIR


def discover_localizable_files(
    mod_name: str,
    game_profile: dict,
    source_lang: dict,
    override_path: Optional[str] = None,
    source_dir: str = SOURCE_DIR,
) -> list[dict]:
    """
    Discover all localizable files in the mod directory.
    Supports recursive search for EU5-style multi-module structures.
    """
    source_loc_folder = game_profile["source_localization_folder"]
    mod_root_path = override_path if override_path else os.path.join(source_dir, mod_name)
    source_loc_path = os.path.join(mod_root_path, source_loc_folder)
    cust_loc_root = os.path.join(mod_root_path, "customizable_localization")

    lang_key = source_lang["key"][2:]
    suffix_pattern = re.compile(r"[\s_](l_)?" + re.escape(lang_key) + r"\.yml$", re.IGNORECASE)

    search_paths = _find_localization_roots(mod_root_path, source_loc_path, source_loc_folder)
    discovered_files = []

    for loc_path in search_paths:
        logging.info("Discovered localization directory: %s", loc_path)
        discovered_files.extend(_discover_standard_localization_files(loc_path, mod_root_path, suffix_pattern))

    discovered_files.extend(_discover_custom_localization_files(cust_loc_root, mod_root_path))

    if not discovered_files:
        _log_missing_source_language_diagnostics(search_paths, source_lang, lang_key)

    return discovered_files


def _find_localization_roots(
    mod_root_path: str,
    source_loc_path: str,
    source_loc_folder: str,
) -> list[str]:
    if os.path.isdir(source_loc_path):
        return [source_loc_path]

    logging.info(
        "Standard localization folder not found at %s. Searching recursively for '%s'...",
        source_loc_path,
        source_loc_folder,
    )
    search_paths = []
    for root, _, _ in os.walk(mod_root_path):
        if os.path.basename(root) == source_loc_folder:
            search_paths.append(root)
    return search_paths


def _discover_standard_localization_files(
    loc_path: str,
    mod_root_path: str,
    suffix_pattern: re.Pattern,
) -> list[dict]:
    discovered_files = []
    for root, _, files in os.walk(loc_path):
        for filename in files:
            if not suffix_pattern.search(filename):
                continue
            file_path = os.path.join(root, filename)
            discovered_files.append(
                {
                    "path": file_path,
                    "file_path": os.path.relpath(file_path, mod_root_path).replace(os.sep, "/"),
                    "filename": filename,
                    "root": root,
                    "is_custom_loc": False,
                    "loc_root": loc_path,
                }
            )
    return discovered_files


def _discover_custom_localization_files(cust_loc_root: str, mod_root_path: str) -> list[dict]:
    if not os.path.isdir(cust_loc_root):
        return []

    discovered_files = []
    for root, _, files in os.walk(cust_loc_root):
        for filename in files:
            if not filename.endswith(".txt"):
                continue
            file_path = os.path.join(root, filename)
            discovered_files.append(
                {
                    "path": file_path,
                    "file_path": os.path.relpath(file_path, mod_root_path).replace(os.sep, "/"),
                    "filename": filename,
                    "root": root,
                    "is_custom_loc": True,
                    "loc_root": "",
                }
            )
    return discovered_files


def _log_missing_source_language_diagnostics(
    search_paths: list[str],
    source_lang: dict,
    lang_key: str,
) -> None:
    found_others = []
    for loc_path in search_paths:
        for _, _, files in os.walk(loc_path):
            found_others.extend(filename for filename in files if filename.endswith(".yml"))

    if not found_others:
        return

    logging.warning(
        "No files found for source language '%s' matching pattern l_%s.yml.",
        source_lang["name"],
        lang_key,
    )
    logging.warning(
        "However, found %s other .yml files, e.g., %s",
        len(found_others),
        found_others[:3],
    )
    logging.warning("Please check if you selected the correct Source Language.")
