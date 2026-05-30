from typing import Any, Dict, List, Optional, Tuple


class IncrementalDiffService:
    def build_history_index(self, archived_entries: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        unique_key_entries: Dict[str, Optional[Dict[str, Any]]] = {}
        for entry in archived_entries:
            file_path = self._normalize_file_path(entry.get("file_path", ""))
            key = self._normalize_key(entry.get("key", ""))
            index[(file_path, key)] = entry
            if key not in unique_key_entries:
                unique_key_entries[key] = entry
            else:
                unique_key_entries[key] = None

        for key, entry in unique_key_entries.items():
            if entry is not None:
                index[("", key)] = entry
        return index

    def classify_entry(
        self,
        file_path: str,
        key: str,
        source_text: str,
        history_index: Dict[Tuple[str, str], Dict[str, Any]],
        target_lang_code: Optional[str] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        normalized_key = self._normalize_key(key)
        normalized_file_path = self._normalize_file_path(file_path)

        history_entry = history_index.get((normalized_file_path, normalized_key))
        if history_entry is None:
            history_entry = history_index.get(("", normalized_key))

        if not history_entry:
            return "new", None

        # Check for invalid translations (empty or untranslated same-as-english)
        translation = history_entry.get("translation")
        is_invalid_translation = False
        if translation is None:
            is_invalid_translation = True
        elif isinstance(translation, str):
            if translation.strip() == "":
                is_invalid_translation = True
            elif target_lang_code and target_lang_code != "en" and translation == source_text:
                # Check if it contains actual English words to translate
                import re
                if re.search(r'[a-zA-Z]', source_text):
                    cleaned = source_text.strip()
                    is_placeholder = (
                        (cleaned.startswith("$") and cleaned.endswith("$") and cleaned.count("$") == 2) or
                        (cleaned.startswith("@") and cleaned.endswith("!") and cleaned.count("@") == 1)
                    )
                    if not is_placeholder:
                        import string
                        chars_to_ignore = string.digits + string.punctuation + " "
                        is_pure_symbols = all(c in chars_to_ignore for c in cleaned)
                        if not is_pure_symbols:
                            is_invalid_translation = True

        if is_invalid_translation:
            return "changed", history_entry

        if history_entry.get("original") != source_text:
            return "changed", history_entry
        return "unchanged", history_entry

    def _normalize_key(self, key: str) -> str:
        key = key.strip()
        if key.endswith(":"):
            key = key[:-1].strip()
        return key

    def _normalize_file_path(self, file_path: str) -> str:
        return (file_path or "").replace("\\", "/").strip()
