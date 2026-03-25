from typing import Any, Dict, List, Optional, Tuple


class IncrementalDiffService:
    def build_history_index(self, archived_entries: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for entry in archived_entries:
            file_path = (entry.get("file_path") or "").replace("\\", "/")
            key = self._normalize_key(entry.get("key", ""))
            index[(file_path, key)] = entry
        return index

    def classify_entry(
        self,
        file_path: str,
        key: str,
        source_text: str,
        history_index: Dict[Tuple[str, str], Dict[str, Any]],
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        normalized_key = self._normalize_key(key)
        normalized_file_path = file_path.replace("\\", "/")

        history_entry = history_index.get((normalized_file_path, normalized_key))
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
