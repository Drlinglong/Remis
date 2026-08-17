import re
import logging

from scripts.core.paradox_localization_parser import (
    LocalizationEntry,
    ParseDiagnostic,
    patch_lines,
)


def _patch_canonical_spans(
    original_lines: list[str],
    translated_texts: list[str],
    key_map: dict[int, dict],
    recovered_entries: list[dict] | None = None,
) -> list[str] | None:
    replacements: list[tuple[LocalizationEntry, str]] = []
    for index, translated_text in enumerate(translated_texts):
        line_info = key_map.get(index)
        entry = line_info.get("entry") if isinstance(line_info, dict) else None
        if not isinstance(entry, LocalizationEntry):
            return None
        replacements.append((entry, str(translated_text)))
    recoveries = [
        item.get("diagnostic")
        for item in (recovered_entries or [])
        if isinstance(item.get("diagnostic"), ParseDiagnostic)
    ]
    return patch_lines(original_lines, replacements, recoveries)


def _patch_legacy_lines(
    original_lines: list[str],
    texts_to_translate: list[str],
    translated_texts: list[str],
    key_map: dict[int, dict],
) -> list[str]:
    """Keep the public adapter usable for custom hooks with old key maps."""

    new_lines = list(original_lines)
    for index, original_text in enumerate(texts_to_translate):
        if index >= len(translated_texts) or index not in key_map:
            break
        line_info = key_map[index]
        line_num = line_info["line_num"]
        key_part = line_info["key_part"]
        original_line = original_lines[line_num]
        key_pos = original_line.find(key_part)
        first_quote = original_line.find('"', key_pos + len(key_part))
        if key_pos < 0 or first_quote < 0:
            logging.warning("Could not locate localization span for '%s'", key_part)
            continue
        closing_quote = original_line.rfind('"')
        if closing_quote <= first_quote:
            logging.warning("Could not locate closing quote for '%s'", key_part)
            continue
        safe_value = str(translated_texts[index]).replace('"', r'\"')
        new_lines[line_num] = (
            original_line[: first_quote + 1]
            + safe_value
            + original_line[closing_quote:]
        )
    return new_lines


def _replace_language_header(lines: list[str], target_lang_key: str) -> list[str]:
    header_pattern = re.compile(r"^\s*l_[\w-]+:\s*")
    first_header_index = -1
    duplicate_indices: list[int] = []
    for index, line in enumerate(lines):
        if not header_pattern.match(line):
            continue
        if first_header_index < 0:
            first_header_index = index
        else:
            duplicate_indices.append(index)
    for index in reversed(duplicate_indices):
        lines.pop(index)
    if first_header_index >= 0:
        lines[first_header_index] = f"{target_lang_key}:\n"
    else:
        lines.insert(0, f"{target_lang_key}:\n")
    return lines

def patch_file_content(
    original_lines: list[str],
    texts_to_translate: list[str],
    translated_texts: list[str],
    key_map: dict[int, dict],
    source_lang_key: str,
    target_lang_key: str,
    recovered_entries: list[dict] | None = None,
) -> list[str]:
    """
    Patches the original file content with translated texts.
    Preserves comments, indentation, and structure.
    Replaces the language header.
    """
    canonical_lines = _patch_canonical_spans(
        original_lines, translated_texts, key_map, recovered_entries
    )
    new_lines = canonical_lines or _patch_legacy_lines(
        original_lines, texts_to_translate, translated_texts, key_map
    )
    return _replace_language_header(new_lines, target_lang_key)

def rebuild_and_write_file(
    original_lines: list[str],
    texts_to_translate: list[str],
    translated_texts: list[str],
    key_map: dict[int, dict],
    dest_dir: str,
    filename: str,
    source_lang: dict,
    target_lang: dict,
    game_profile: dict,
    recovered_entries: list[dict] | None = None,
) -> str:
    """
    Rebuilds the file content with translated texts and writes it to the output path.
    This is a wrapper around patch_file_content that handles file writing.
    """
    import os
    from scripts.utils.punctuation_handler import clean_punctuation_core
    
    # 1. Determine Target Filename
    # Replace the source language key in the filename with the target language key
    # e.g. "foo_l_simp_chinese.yml" -> "foo_l_english.yml"
    source_lang_key_clean = source_lang.get("key", "").replace(":", "").strip()
    target_lang_key_clean = target_lang.get("key", "").replace(":", "").strip()
    
    logging.info(f"DEBUG: filename='{filename}', source_key='{source_lang_key_clean}', target_key='{target_lang_key_clean}'")
    
    # Handle cases where key might be "l_english" or just "english" depending on config
    # We try to be robust: if filename contains source_lang_key, replace it.
    if source_lang_key_clean and source_lang_key_clean in filename:
        target_filename = filename.replace(source_lang_key_clean, target_lang_key_clean)
    else:
        # Fallback: if filename ends with .yml, insert target key? 
        # Or just append? This is tricky. 
        # Let's assume standard Paradox format: name_l_language.yml
        # If we can't find the source key, we might just prepend/append?
        # But usually source_lang_key IS in the filename for the source file.
        # Let's try to find the last occurrence of l_xxxx
        import re
        # Match _l_something.yml or _l_something.txt
        match = re.search(r"(_l_[a-zA-Z0-9_-]+)\.(yml|txt)$", filename)
        if match:
            # Replace the found suffix with target suffix
            # target_lang["key"] usually is "l_english"
            suffix = f"_{target_lang_key_clean}"
            target_filename = filename[:match.start(1)] + suffix + "." + match.group(2)
        else:
            # Worst case: just use the original filename (which was the bug)
            # But we should try to at least append the language
            name, ext = os.path.splitext(filename)
            target_filename = f"{name}_{target_lang_key_clean}{ext}"

    output_path = os.path.join(dest_dir, target_filename)
    source_lang_key = source_lang.get("key", f"l_{source_lang.get('code', 'english')}")
    target_lang_key = target_lang.get("key", f"l_{target_lang.get('code', 'english')}")

    # 2. Punctuation Cleaning (Using robust handler)
    source_code = source_lang.get("code", "zh-CN")
    target_code = target_lang.get("code", "en")
    
    cleaned_translations = []
    for text in translated_texts:
        # Use the centralized punctuation handler
        cleaned = clean_punctuation_core(text, source_code, target_code)
        # Clean up double spaces that might result from the mapping (e.g. ", " + " ")
        cleaned = cleaned.replace("  ", " ")
        cleaned_translations.append(cleaned)

    # 3. Patch the content
    new_lines = patch_file_content(
        original_lines,
        texts_to_translate,
        cleaned_translations,
        key_map,
        source_lang_key,
        target_lang_key,
        recovered_entries,
    )
    
    # 4. Write to file
    try:
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.writelines(new_lines)
        return output_path
    except Exception as e:
        logging.error(f"Failed to write file to {output_path}: {e}")
        raise e

def create_fallback_file(
    source_path: str,
    dest_dir: str,
    filename: str,
    source_lang: dict,
    target_lang: dict,
    game_profile: dict
) -> str | None:
    """
    Creates a fallback file by copying the source file and updating the language header.
    Used when the source file has no translatable content but still needs to exist in the target mod
    (e.g., file with only comments or empty structure).
    """
    import os
    import re

    try:
        # 1. Determine Target Filename (Logic consistent with rebuild_and_write_file)
        source_lang_key_clean = source_lang.get("key", "").replace(":", "").strip()
        target_lang_key_clean = target_lang.get("key", "").replace(":", "").strip()
        
        target_filename = filename
        if source_lang_key_clean and source_lang_key_clean in filename:
            target_filename = filename.replace(source_lang_key_clean, target_lang_key_clean)
        else:
            match = re.search(r"(_l_[a-zA-Z0-9_-]+)\.(yml|txt)$", filename)
            if match:
                suffix = f"_{target_lang_key_clean}"
                target_filename = filename[:match.start(1)] + suffix + "." + match.group(2)
            else:
                name, ext = os.path.splitext(filename)
                target_filename = f"{name}_{target_lang_key_clean}{ext}"

        output_path = os.path.join(dest_dir, target_filename)
        
        # 2. Read Source Content
        with open(source_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            
        # 3. Update Language Header
        target_lang_key = target_lang.get("key", f"l_{target_lang.get('code', 'english')}")
        
        # Reuse logic to find/replace header
        header_pattern = re.compile(r"^\s*l_[\w-]+:\s*")
        new_lines = list(lines)
        
        first_header_index = -1
        indices_to_remove = []
        
        for i, line in enumerate(new_lines):
            if header_pattern.match(line):
                if first_header_index == -1:
                    first_header_index = i
                else:
                    indices_to_remove.append(i)
        
        for i in reversed(indices_to_remove):
            new_lines.pop(i)
            
        if first_header_index != -1:
            new_lines[first_header_index] = f"{target_lang_key}:\n"
        else:
            if new_lines and not new_lines[0].strip():
                 # Try to find first non-empty line or just insert at top
                 new_lines.insert(0, f"{target_lang_key}:\n")
            else:
                 new_lines.insert(0, f"{target_lang_key}:\n")

        # 4. Write to Destination
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.writelines(new_lines)
            
        logging.info(f"Created fallback file: {output_path}")
        return output_path

    except Exception as e:
        logging.error(f"Failed to create fallback file for {filename}: {e}")
        return None
