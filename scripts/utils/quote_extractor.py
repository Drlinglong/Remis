# scripts/utils/quote_extractor.py
# -*- coding: utf-8 -*-
"""
统一的引号内容提取工具类
整合了翻译流程和后处理验证器中的引号提取逻辑，消除重复代码
"""

import re
import os
import logging
from typing import Optional, List, Tuple, Dict, Any

# 导入国际化支持
try:
    from . import i18n
except ImportError:
    i18n = None


class QuoteExtractor:
    """统一的引号内容提取工具类"""
    
    @staticmethod
    def extract_from_line(line: str) -> Optional[str]:
        """
        从YAML行中提取需要翻译的内容（引号内的内容）
        
        处理各种情况：
        1. key: "value" #注释
        2. key: "He said \"Hello World\" to me" #注释
        3. key: "value"
        4. key: "value" #注释
        5. 无效格式（没有引号）
        
        Args:
            line: YAML行内容
            
        Returns:
            str: 引号内的内容，如果没有找到则返回None
        """
        # 先移除行内注释（#后面的内容）
        # 但要小心不要移除引号内的#符号
        comment_pos = -1
        in_quotes = False
        escape_next = False
        
        for i, char in enumerate(line):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_quotes = not in_quotes
            elif char == '#' and not in_quotes:
                comment_pos = i
                break
        
        # 如果有注释，移除注释部分
        if comment_pos != -1:
            line = line[:comment_pos].strip()
        
        # 查找 key:0 "value" 或 key: "value" 格式
        # 先找到冒号后的第一个引号
        colon_pos = line.find(':')
        if colon_pos == -1:
            return None
        
        # 从冒号后开始查找引号
        after_colon = line[colon_pos + 1:].strip()
        
        # 查找引号位置（可能在数字后面）
        quote_pos = after_colon.find('"')
        if quote_pos == -1:
            return None
        
        # 从引号位置开始处理
        after_colon = after_colon[quote_pos:]
        
        # 找到第一个引号的位置
        first_quote_pos = after_colon.find('"')
        if first_quote_pos == -1:
            return None
        
        # 从第一个引号后开始查找匹配的结束引号
        content_start = first_quote_pos + 1
        content = ""
        i = content_start
        escape_next = False
        
        while i < len(after_colon):
            char = after_colon[i]
            
            if escape_next:
                # 转义字符，直接添加到内容中
                content += char
                escape_next = False
            elif char == '\\':
                # 反斜杠，标记下一个字符为转义，但不添加到内容中（也就是消耗掉这个反斜杠）
                # content += char  <-- REMOVED
                escape_next = True
            elif char == '"':
                # 找到结束引号
                # 允许提取空值，即 ""
                return content
            else:
                # 普通字符
                content += char
            
            i += 1
        
        # 如果没有找到结束引号，返回None
        return None
    
    @staticmethod
    def extract_from_file(file_path: str) -> Tuple[List[str], List[str], Dict[int, Dict[str, Any]]]:
        """
        从文件中提取所有可翻译内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            tuple: (original_lines, texts_to_translate, key_map)
        """
        try:
            rel_path = os.path.relpath(file_path)
        except ValueError:
            # 当 file_path 和当前工作目录不在同一个驱动器时，os.path.relpath 会抛出 ValueError
            # 在这种情况下，我们回退到使用绝对路径或文件名
            rel_path = os.path.basename(file_path)
        logging.info(i18n.t("parsing_file", filename=rel_path) if i18n else f"Parsing file: {rel_path}")

        # 1) Read file lines with a fallback to cp1252 for unexpected encodings.
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                original_lines = f.readlines()
        except UnicodeDecodeError:
            # First fallback: cp1252 (Western European)
            try:
                with open(file_path, "r", encoding="cp1252") as f:
                    original_lines = f.readlines()
            except UnicodeDecodeError:
                # Second fallback: gb18030 (Chinese Legacy) - Critical for older CN mods
                try:
                    with open(file_path, "r", encoding="gb18030") as f:
                        original_lines = f.readlines()
                except UnicodeDecodeError:
                    # Final fallback: ignore errors to prevent crash
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        original_lines = f.readlines()

        texts_to_translate: List[str] = []
        key_map: Dict[int, Dict[str, Any]] = {}

        # Check if this is a .txt file in a customizable_localization directory.
        is_txt = file_path.lower().endswith(".txt") and "customizable_localization" in file_path.replace("\\", "/")

        for line_num, line in enumerate(original_lines):
            stripped = line.strip()

            # Common check: skip comments and empty lines.
            if not stripped or stripped.startswith("#"):
                continue

            if is_txt:
                # Handle the format: add_custom_loc = "Text"
                if "add_custom_loc" not in stripped:
                    continue
                match = re.search(r'add_custom_loc\s*=\s*"(.*?)"', stripped)
                if not match:
                    continue
                value = match.group(1)
                key_part = "add_custom_loc"
                value_part = stripped.split("=", 1)[1]
            else:
                # --- Handle the classic Paradox-yml format: key:0 "Text" or key : 0 "Text" ---
                # Skip headers like l_english, l_polish etc.
                if any(stripped.startswith(pref) for pref in (
                    "l_english", "l_simp_chinese", "l_french", "l_german",
                    "l_spanish", "l_russian", "l_polish", "l_japanese", "l_korean", "l_turkish", "l_braz_por"
                )):
                    continue

                # Use unified regex to extract key and version
                from scripts.core.loc_parser import ENTRY_RE
                match = ENTRY_RE.match(stripped)
                if not match:
                    continue
                
                base_key, version, value_tmp = match.groups()
                # Universal Normalization: No spaces, handle version
                key_part = f"{base_key.strip()}:{version.strip()}" if version.strip() else base_key.strip()
                
                # Split at first colon for value_part (for legacy reasons/file patching)
                value_part = stripped.split(":", 1)[1]

                # 使用统一的引号提取方法
                value = QuoteExtractor.extract_from_line(line)
                if value is None:
                    continue

            # --- Filtering Logic ---

            # 【核心修正 1】Filter out self-referencing keys (e.g., a_key: "a_key").
            # We strip the key_part to get a clean key for comparison.
            if key_part.strip() == value:
                continue

            # 【核心修正 2】Filter out pure variables (e.g., "$VAR$").
            is_pure_variable = False
            if value.startswith('$') and value.endswith('$'):
                if value.count('$') == 2:
                    is_pure_variable = True

            # 【核心修正 3】Filter out pure variables AND empty values (e.g., key: "").
            if is_pure_variable or not value:
                continue

            # Save the extracted text and its metadata to the lists.
            idx = len(texts_to_translate)
            texts_to_translate.append(value)
            key_map[idx] = {
                "key_part": key_part,
                "original_value_part": value_part.strip(),
                "line_num": line_num,
            }

        return original_lines, texts_to_translate, key_map
