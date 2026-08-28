from pathlib import Path
from typing import Any, Dict, List

from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.vanilla_reference_factory import create_reference_resolver_strict


class ReferenceReusePreviewService:
    """Read-only exact-match preview for user-reviewable vanilla reuse."""

    def __init__(self, resolver_factory=create_reference_resolver_strict) -> None:
        self._resolver_factory = resolver_factory

    def preview(
        self,
        *,
        source_path: str,
        game_profile: Dict[str, Any],
        source_lang: Dict[str, Any],
        target_languages: List[Dict[str, Any]],
        localization_path: str | None = None,
    ) -> Dict[str, Any]:
        source_files = IncrementalSnapshotService().build_snapshot(source_path, source_lang)
        matches: List[Dict[str, Any]] = []
        language_metrics: List[Dict[str, Any]] = []
        total_source_entries = sum(len(item["parsed_entries"]) for item in source_files)

        for target_lang in target_languages:
            resolver = self._resolver_factory(
                {"enabled": True, "localization_path": localization_path},
                game_profile=game_profile,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            if resolver is None:
                continue
            for file_data in source_files:
                file_path = file_data["file_path"]
                for key, source_text, line_num in file_data["parsed_entries"]:
                    result = resolver.lookup(key, source_text, file_path)
                    if not result.hit:
                        continue
                    matches.append({
                        "file_path": file_path,
                        "key": key,
                        "source_text": source_text,
                        "target_text": result.translation,
                        "target_lang_code": target_lang.get("code", ""),
                        "line_number": line_num,
                    })
            language_metrics.append({
                "target_lang_code": target_lang.get("code", ""),
                "game_version": resolver.info.game_version,
                "content_fingerprint": resolver.info.content_fingerprint,
                "stale": resolver.info.stale,
                **resolver.metrics(),
            })

        matches.sort(key=lambda item: (
            item["target_lang_code"],
            item["file_path"].casefold(),
            item["line_number"],
            item["key"],
        ))
        return {
            "status": "success",
            "source_path": str(Path(source_path).resolve()),
            "localization_path": (
                str(Path(localization_path).resolve()) if localization_path else None
            ),
            "total_source_entries": total_source_entries,
            "matched_count": len(matches),
            "matches": matches,
            "languages": language_metrics,
        }
