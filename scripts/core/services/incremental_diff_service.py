import os
from typing import Any, Dict, List, Optional, Tuple


class IncrementalDiffService:
    def build_history_index(self, archived_entries: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        unique_key_entries: Dict[str, Optional[Dict[str, Any]]] = {}
        for entry in archived_entries:
            file_path = self._normalize_file_path(entry.get("file_path", ""))
            key = self._normalize_key(entry.get("key", ""))
            index[(file_path, key)] = entry
            basename = os.path.basename(file_path)
            if basename:
                index.setdefault((basename, key), entry)
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
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        normalized_key = self._normalize_key(key)
        normalized_file_path = self._normalize_file_path(file_path)
        basename = os.path.basename(normalized_file_path)

        history_entry = history_index.get((normalized_file_path, normalized_key))
        if history_entry is None and basename:
            history_entry = history_index.get((basename, normalized_key))
        if history_entry is None:
            history_entry = history_index.get(("", normalized_key))

        if not history_entry:
            return "new", None
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
