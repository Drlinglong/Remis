# scripts/core/file_parser.py
# ---------------------------------------------------------------
"""
Domyślny parser dla plików .yml (Paradox localisation) oraz
*.txt w customizable_localization (add_custom_loc hook).

⚠️  *Hook system*  
Jeśli potrzebujesz obsłużyć dodatkowe formaty albo niestandardowe reguły
(np. inne pliki), utwórz plik:

    hooks/file_parser_hook.py

i zdefiniuj w nim funkcję `register_hooks()`, która zwraca listę
callable’ów o sygnaturze:

    def my_hook(file_path: str,
                original_lines: list[str],
                texts: list[str],
                key_map: dict[int, dict]) -> None: ...
"""
# ---------------------------------------------------------------
from __future__ import annotations

import os
import re
from types import ModuleType
from typing import Callable, List
import logging

from scripts.utils import i18n  # komunikaty wielojęzykowe
from scripts.utils.quote_extractor import QuoteExtractor

# ───────────────────── 1. PRÓBA ZAŁADOWANIA HOOKÓW ─────────────────────
HOOKS: List[Callable[[str, list[str], list[str], dict[int, dict]], None]] = []

try:
    import importlib.util

    # [FIX] Use absolute package path 'scripts.hooks.file_parser_hook'
    spec = importlib.util.find_spec("scripts.hooks.file_parser_hook")
    if spec is not None:
        module: ModuleType = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore
        if hasattr(module, "register_hooks"):
            _hooks: list = module.register_hooks()  # type: ignore
            if isinstance(_hooks, list):
                HOOKS.extend(_hooks)
except Exception as e:  # pragma: no cover – hook opcjonalny
    # Warn but don't fail, unless it's critical. 
    # With the new path, it should work if properly bundled.
    logging.warning(f"[parser-hook] ⚠️  Failed to load hooks: {e}")


def extract_translatable_content(
    file_path: str,
) -> tuple[list[str], list[str], dict[int, dict]]:
    """
    Extracts translatable texts from a single .yml file or a .txt file
    from a customizable_localization directory, now with improved filtering.

    Returns:
        original_lines (list[str]): The original lines of the file.
        texts_to_translate (list[str]): A list of strings to be translated.
        key_map (dict): A map to reconstruct the file: {index: {key_part, original_value_part, line_num}}.
    """
    # 使用统一的引号提取工具类
    original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(file_path)
    
    # --- (The Hook system logic remains the same) ---
    if HOOKS:
        for hook in HOOKS:
            try:
                hook(file_path, original_lines, texts_to_translate, key_map)
            except Exception as e:
                logging.error(f"[parser-hook] ⚠️  {hook.__name__} failed: {e}")

    # --- Final Summary ---
    logging.info(i18n.t("extracted_texts", count=len(texts_to_translate)))
    return original_lines, texts_to_translate, key_map