"""Expose preserved source-change review flags from the current job's packages."""
import json
from pathlib import Path

from scripts.core.game_adapters.workflow_bridge import MANIFEST, safe_output
from scripts.core.services.agent_game_output_service import _walk_without_links, _contained_existing_root
from scripts.core.services.agent_validation_policy import classify_issues


def merge_game_review_payload(payload, game_id, output_paths, destination_root):
    if game_id not in {"project_zomboid", "rimworld"} or payload.get("_suppressed"):
        return payload
    reviews = []
    seen = set()
    for raw_root in output_paths:
        root = _contained_existing_root(raw_root, Path(destination_root).resolve())
        if root is None:
            continue
        for path in _walk_without_links(root):
            if path.name != MANIFEST:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("game_id") != game_id:
                    continue
                for relative, record in data.get("files", {}).items():
                    target = safe_output(path.parent, relative)
                    if not target.is_file():
                        continue
                    for entry in record.get("entries", []):
                        identity = (str(target), entry.get("key"))
                        if entry.get("needs_review") and identity not in seen:
                            seen.add(identity)
                            reviews.append({"error_code": "source_changed_review_required", "file_name": str(target),
                                "key": entry["key"], "requires_human_review": True, "severity": "warning",
                                "message": "Source text changed; the preserved translation requires human review.",
                                "status": "needs_review"})
            except (OSError, ValueError, TypeError, AttributeError, KeyError):
                continue
    if not reviews:
        return payload
    raw = list(payload.get("_raw_items", []))
    existing = {(item.get("file_name"), item.get("key"), item.get("error_code")) for item in raw}
    raw.extend(item for item in reviews if (item["file_name"], item["key"], item["error_code"]) not in existing)
    items, summary = classify_issues(raw)
    summary.truncated = len(items) > 100
    return {**payload, "_raw_items": raw, "items": items[:100], "summary": summary}
